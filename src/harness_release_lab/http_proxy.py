"""Bounded HTTP fault gateway. Response receipt is never labelled a committed effect."""

from __future__ import annotations

import asyncio
import threading
import time
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

from .http_contract import HttpContract

MAX_BODY = 2 * 1024 * 1024
HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
    "host",
    "content-length",
}


def clean_headers(headers, *, decoded=False):
    blocked = HOP_HEADERS | {
        item.strip().lower() for item in headers.get("connection", "").split(",")
    }
    if decoded:
        blocked |= {"content-encoding"}
    items = headers.multi_items() if hasattr(headers, "multi_items") else headers.items()
    return [(key, value) for key, value in items if key.lower() not in blocked]


def validate_upstream(value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in ("", "/")
    ):
        raise ValueError("upstream must be an HTTP(S) origin; credentials belong in headers")
    return value.rstrip("/")


class FaultProxy:
    """Metadata-only evidence, bounded requests, explicit matching and fault consumption."""

    def __init__(self, contract: HttpContract, upstream: str, run_id: str):
        self.contract = contract.model_copy(deep=True)
        self.upstream = validate_upstream(upstream)
        self.path = contract.path.replace("{run_id}", run_id)
        self.lock = threading.Lock()
        self.events: list[dict] = []
        self.attempts = 0
        self.active = 0
        self.total = 0
        self.closed = False
        self.errors: set[str] = set()
        self.consumed: list[int] = []
        self.started = time.monotonic()
        self.app = self._app()

    def note(self, kind: str, **data):
        with self.lock:
            if len(self.events) >= 500:
                self.errors.add("event_limit")
                return
            self.events.append(
                {
                    "seq": len(self.events) + 1,
                    "ms": round((time.monotonic() - self.started) * 1000),
                    "kind": kind,
                    **data,
                }
            )

    def seal(self):
        """Stop admission before observing state; await all already admitted operations."""
        with self.lock:
            self.closed = True
        deadline = time.monotonic() + self.contract.upstream_timeout_s + 7
        while time.monotonic() < deadline:
            with self.lock:
                if not self.active:
                    return
            time.sleep(0.01)
        self.errors.add("inflight_did_not_settle")

    def _app(self):
        @asynccontextmanager
        async def lifespan(app):
            async with httpx.AsyncClient(
                timeout=self.contract.upstream_timeout_s,
                trust_env=False,
                follow_redirects=False,
            ) as client:
                app.state.client = client
                yield

        app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

        @app.api_route(
            "/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]
        )
        async def forward(request: Request, path: str):
            matching = request.method == self.contract.method and request.url.path == self.path
            with self.lock:
                self.total += 1
                if self.closed or self.total > 200:
                    self.errors.add("request_after_close" if self.closed else "request_limit")
                    return JSONResponse({"error": "gateway closed"}, status_code=503)
                self.active += 1
                if matching:
                    self.attempts += 1
                attempt = self.attempts if matching else None
            try:
                return await asyncio.wait_for(
                    self._forward(request, matching, attempt),
                    timeout=self.contract.upstream_timeout_s + 6,
                )
            except Exception as exc:  # noqa: BLE001 - transport errors must block the evidence gate
                # Do not persist exception messages: they can contain URL secrets or bodies.
                self.errors.add(type(exc).__name__)
                self.note("transport_error", attempt=attempt, error=type(exc).__name__)
                return JSONResponse({"error": "upstream unavailable"}, status_code=502)
            finally:
                with self.lock:
                    self.active -= 1

        return app

    async def _forward(self, request, matching, attempt):
        self.note("request", attempt=attempt, matched=matching, method=request.method)
        if matching and attempt > self.contract.max_attempts:
            self.errors.add("attempt_budget")
            return JSONResponse({"error": "attempt budget exceeded"}, status_code=429)
        fault = next((f for f in self.contract.faults if matching and f.at == attempt), None)
        if fault and fault.type.startswith("before_"):
            self.consumed.append(fault.at)
            self.note("injection", attempt=attempt, fault=fault.type, phase="before_forward")
            return JSONResponse({"error": "injected"}, status_code=int(fault.type[-3:]))
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > MAX_BODY:
                self.errors.add("request_body_limit")
                return JSONResponse({"error": "request too large"}, status_code=413)
        # raw_path preserves percent encoding. Concatenation cannot replace the configured origin.
        raw_path = request.scope["raw_path"].decode("ascii")
        query = request.scope["query_string"].decode("ascii")
        url = self.upstream + raw_path + ("?" + query if query else "")
        async with request.app.state.client.stream(
            request.method, url, headers=clean_headers(request.headers), content=bytes(body)
        ) as response:
            content = bytearray()
            async for chunk in response.aiter_bytes():
                content.extend(chunk)
                if len(content) > MAX_BODY:
                    raise ValueError("response too large")
            self.note("upstream_response", attempt=attempt, status=response.status_code)
            if fault and 200 <= response.status_code < 300:
                self.consumed.append(fault.at)
                self.note("injection", attempt=attempt, fault=fault.type, phase="after_2xx")
                if fault.type == "after_503":
                    return JSONResponse(
                        {"error": "injected after upstream success"}, status_code=503
                    )
                await asyncio.sleep(fault.delay_ms / 1000)
            outgoing = Response(bytes(content), status_code=response.status_code)
            outgoing.raw_headers = [
                (key.encode("latin1"), value.encode("latin1"))
                for key, value in clean_headers(response.headers, decoded=True)
            ]
            self.note("response_prepared", attempt=attempt, status=response.status_code)
            return outgoing
