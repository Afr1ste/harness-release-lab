from __future__ import annotations

import socket
import threading
import time
from contextlib import contextmanager

import uvicorn
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse

from .models import Operation
from .world import World, deliver


def business_app(world: World, token: str) -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    barrier = threading.Barrier(world.scenario.concurrent_calls)
    arrival_lock = threading.Lock()
    arrivals = 0

    @app.post("/refund")
    def refund(
        operation: Operation,
        authorization: str = Header(default=""),
        idempotency_key: str = Header(default="", min_length=1, max_length=200),
    ):
        nonlocal arrivals
        if authorization != f"Bearer {token}":
            raise HTTPException(401, "invalid test token")
        with arrival_lock:
            arrivals += 1
            arrival = arrivals
        if 1 < world.scenario.concurrent_calls and arrival <= world.scenario.concurrent_calls:
            try:
                barrier.wait(timeout=1.5)
                world.note("concurrent_arrival", arrival=arrival)
            except threading.BrokenBarrierError:
                world.note("concurrency_timeout", arrival=arrival)
                return JSONResponse(
                    {"error": "concurrent deliveries did not overlap"}, status_code=409
                )
        status, body = deliver(world, idempotency_key, operation)
        return JSONResponse(body, status_code=status)

    return app


@contextmanager
def local_server(app: FastAPI):
    """Pre-bind an ephemeral port, avoiding find-free-port races."""
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            log_level="critical",
            access_log=False,
            lifespan="on",
            timeout_graceful_shutdown=3,
        )
    )
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    try:
        end = time.monotonic() + 10
        while not server.started:
            if not thread.is_alive() or time.monotonic() > end:
                raise RuntimeError("local server failed to start")
            time.sleep(0.01)
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        sock.close()
        if thread.is_alive():
            raise RuntimeError("local server did not stop")
