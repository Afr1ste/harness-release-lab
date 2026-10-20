from __future__ import annotations

import html
import re
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse

from .engine import compare, read_report, run_suite
from .http_runner import read_http_report
from .models import StrictModel
from .scenarios import load_suite


class RunRequest(StrictModel):
    target: Literal["reference-broken", "reference-fixed", "dsh-broken", "dsh-fixed"]


def create_app(root: Path) -> FastAPI:
    root = root.resolve()
    executor = ThreadPoolExecutor(max_workers=1)
    jobs = {}

    @asynccontextmanager
    async def lifespan(app):
        yield
        executor.shutdown(wait=True, cancel_futures=True)

    app = FastAPI(title="Harness Release Lab", lifespan=lifespan)

    @app.middleware("http")
    async def origin_guard(request: Request, call_next):
        host = request.headers.get("host", "")
        if host.split(":")[0] not in ("127.0.0.1", "localhost", "testserver"):
            return JSONResponse({"detail": "local hosts only"}, status_code=403)
        origin = request.headers.get("origin")
        if origin and origin not in (f"http://{host}", f"https://{host}"):
            return JSONResponse({"detail": "cross-origin requests refused"}, status_code=403)
        if request.method == "POST" and not request.headers.get("content-type", "").startswith(
            "application/json"
        ):
            return JSONResponse({"detail": "JSON required"}, status_code=415)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    def report_path(run_id: str):
        if not re.fullmatch(r"\d{8}T\d{6}-[a-f0-9]{10}", run_id):
            raise HTTPException(404, "unknown run")
        path = root / "runs" / run_id / "report.json"
        if not path.is_file():
            raise HTTPException(404, "unknown run")
        return path

    @app.get("/", response_class=HTMLResponse)
    def index():
        return (Path(__file__).parent / "web" / "index.html").read_text(encoding="utf-8")

    @app.get("/http", response_class=HTMLResponse)
    def http_history():
        records = []
        for path in (root / "http").glob("*/report.json"):
            if not re.fullmatch(r"[a-f0-9]{32}", path.parent.name):
                continue
            try:
                report = read_http_report(path)
                records.append((str(report["created_at"]), path.parent.name, report))
            except (ValueError, OSError, KeyError, TypeError):
                continue
        rows = []
        for created, run_id, report in sorted(records, reverse=True)[:200]:
            rows.append(
                f"<tr><td>{'PASS' if report['passed'] else 'BLOCK'}</td>"
                f'<td><a href="/http/{run_id}">'
                f"{html.escape(str(report.get('label') or report['name']))}</a></td>"
                f"<td>{html.escape(created)}</td></tr>"
            )
        return (
            '<!doctype html><html lang="en"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            "<title>HTTP release evidence · Harness Lab</title>"
            "<style>body{font:16px/1.7 system-ui;max-width:1100px;margin:50px auto;padding:24px;"
            "background:#f5f6f1;color:#183a35}table{width:100%;background:white;border-collapse:"
            "collapse}td{padding:18px;border-bottom:1px solid #ddd}a{color:#15634c}</style>"
            '<a href="/">← Reference controls</a><h1>HTTP release evidence</h1>'
            "<p>Existing agent commands · independent service state · explicit release contracts</p>"
            f"<table>{''.join(rows)}</table>"
            "<p>Generate evidence with <code>hrl check contract.yaml -- your-agent-command</code>."
            " Only local CLI commands can launch external agents.</p></html>"
        )

    @app.get("/http/{run_id}", response_class=HTMLResponse)
    def http_evidence(run_id: str):
        if not re.fullmatch(r"[a-f0-9]{32}", run_id):
            raise HTTPException(404, "unknown HTTP run")
        path = root / "http" / run_id / "report.json"
        try:
            read_http_report(path)
            content = path.with_suffix(".html").read_text(encoding="utf-8")
        except (ValueError, OSError, KeyError, TypeError):
            raise HTTPException(404, "invalid HTTP evidence") from None
        return HTMLResponse(
            content,
            headers={
                "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; sandbox"
            },
        )

    @app.get("/api/runs")
    def runs():
        reports = []
        for path in sorted((root / "runs").glob("*/report.json"), reverse=True)[:200]:
            try:
                report = read_report(path)
            except (ValueError, OSError):
                continue
            reports.append(
                {
                    "id": report.id,
                    "target": report.target,
                    "created_at": report.created_at,
                    "passed": report.passed,
                    "count": sum(c.passed for c in report.cases),
                    "total": len(report.cases),
                    "evidence_mode": report.evidence_mode,
                    "suite_hash": report.suite_hash,
                    "label": report.label,
                }
            )
        return reports

    @app.get("/api/runs/{run_id}")
    def run(run_id: str):
        return read_report(report_path(run_id))

    @app.get("/api/runs/{run_id}/report.html", response_class=HTMLResponse)
    def download(run_id: str):
        path = report_path(run_id).with_name("report.html")
        return HTMLResponse(
            path.read_text(encoding="utf-8"),
            headers={"Content-Disposition": f'attachment; filename="{run_id}.html"'},
        )

    @app.post("/api/runs", status_code=202)
    def start(body: RunRequest):
        # Executed in a thread by FastAPI. Serialize admission with an explicit lock below.
        with admission:
            if any(not item.done() for item in jobs.values()):
                raise HTTPException(409, "a run is already active")
            job_id = uuid4().hex
            jobs.clear()
            jobs[job_id] = executor.submit(run_suite, load_suite(), body.target, root)
        return {"job_id": job_id}

    @app.get("/api/jobs/{job_id}")
    def job(job_id: str):
        with admission:
            future = jobs.get(job_id)
        if future is None:
            raise HTTPException(404, "unknown job")
        if not future.done():
            return {"status": "running"}
        try:
            result = future.result()
            return {"status": "completed", "run_id": result.id}
        except Exception as exc:  # noqa: BLE001 - return explicit failed-job state to the UI
            return {"status": "failed", "error": str(exc)[:1000]}

    @app.get("/api/compare")
    def comparison(baseline: str, candidate: str):
        try:
            return compare(read_report(report_path(baseline)), read_report(report_path(candidate)))
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    import threading

    admission = threading.Lock()
    return app
