"""Run existing agent commands against a fault proxy and independent HTTP state probes."""

from __future__ import annotations

import hashlib
import html
import json
import os
import platform
import signal
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4
from xml.etree.ElementTree import Element, SubElement, tostring

import httpx

from . import __version__
from .engine import source_fingerprint
from .http_contract import HttpContract, pointer_get
from .http_proxy import MAX_BODY, FaultProxy, validate_upstream
from .server import local_server


def observe(contract, upstream, run_id, env):
    deadline = time.monotonic() + contract.upstream_timeout_s
    headers = {key: env[name] for key, name in contract.observer_headers_env.items()}
    path = contract.observer_path.replace("{run_id}", run_id)
    with (
        httpx.Client(timeout=contract.upstream_timeout_s, trust_env=False) as client,
        client.stream("GET", upstream + path, headers=headers) as response,
    ):
        response.raise_for_status()
        body = bytearray()
        for chunk in response.iter_bytes():
            if time.monotonic() > deadline:
                raise TimeoutError("observer wall time exceeded")
            body.extend(chunk)
            if len(body) > MAX_BODY:
                raise ValueError("observer response too large")
    data = json.loads(body)
    return {probe.id: pointer_get(data, probe.pointer) for probe in contract.probes}


def stop_process(process):
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            timeout=10,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    if process.poll() is None:
        process.kill()
    process.wait(timeout=5)


def execute_command(command, env, cwd, timeout, show_output=False):
    options = (
        {"creationflags": subprocess.CREATE_NO_WINDOW}
        if os.name == "nt"
        else {"start_new_session": True}
    )
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        shell=False,
        stdin=subprocess.DEVNULL,
        stdout=None if show_output else subprocess.DEVNULL,
        stderr=None if show_output else subprocess.DEVNULL,
        **options,
    )
    try:
        return {"exit_code": process.wait(timeout=timeout), "timed_out": False}
    except subprocess.TimeoutExpired:
        stop_process(process)
        return {"exit_code": process.returncode, "timed_out": True}
    except BaseException:
        stop_process(process)
        raise


def run_http_contract(
    contract: HttpContract,
    command: list[str],
    root: Path,
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    label: str = "",
    show_output: bool = False,
) -> dict:
    """Public Python API, also usable from pytest. Explicit env replaces inherited env."""
    if not command or any(not isinstance(arg, str) or not arg for arg in command):
        raise ValueError("command must be a nonempty argv list")
    if not isinstance(label, str) or len(label) > 200:
        raise ValueError("label must be a string of at most 200 characters")
    contract = contract.model_copy(deep=True)
    environment = dict(os.environ if env is None else env)
    if not environment.get(contract.upstream_env):
        raise ValueError(f"set {contract.upstream_env} to your disposable test service origin")
    for name in contract.observer_headers_env.values():
        if name not in environment:
            raise ValueError(f"missing observer credential environment variable {name}")
    upstream = validate_upstream(environment[contract.upstream_env])
    run_id = uuid4().hex
    directory = root.resolve() / "http" / run_id
    directory.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    proxy = FaultProxy(contract, upstream, run_id)
    observations = {}
    errors = []
    process_result = {"exit_code": None, "timed_out": False}
    try:
        observations["before"] = observe(contract, upstream, run_id, environment)
        with local_server(proxy.app) as endpoint:
            child_env = {**environment, "HRL_PROXY_URL": endpoint, "HRL_RUN_ID": run_id}
            process_result = execute_command(
                command, child_env, cwd, contract.command_timeout_s, show_output=show_output
            )
            proxy.seal()
        if contract.settle_ms:
            time.sleep(contract.settle_ms / 1000)
        observations["after"] = observe(contract, upstream, run_id, environment)
    except Exception as exc:  # noqa: BLE001 - record failed evidence without leaking exception text
        errors.append(type(exc).__name__)
    checks = []

    def check(name, passed, expected, actual):
        checks.append(
            {"name": name, "passed": bool(passed), "expected": expected, "actual": actual}
        )

    check(
        "evidence_complete",
        not errors and not proxy.errors,
        "complete",
        errors + sorted(proxy.errors),
    )
    check(
        "command_completed",
        process_result["exit_code"] == 0 and not process_result["timed_out"],
        {"exit_code": 0, "timed_out": False},
        process_result,
    )
    check(
        "attempt_budget",
        0 < proxy.attempts <= contract.max_attempts,
        f"1..{contract.max_attempts}",
        proxy.attempts,
    )
    check(
        "faults_exercised",
        sorted(proxy.consumed) == sorted(f.at for f in contract.faults),
        sorted(f.at for f in contract.faults),
        sorted(proxy.consumed),
    )
    for probe in contract.probes:
        try:
            before = observations["before"][probe.id]
            after = observations["after"][probe.id]
            if probe.delta is not None:
                if type(before) is not int or type(after) is not int:
                    raise ValueError("delta requires integer observations")
                actual, expected = after - before, probe.delta
            else:
                actual, expected = after, probe.equals
            check(probe.id, type(actual) is type(expected) and actual == expected, expected, actual)
        except (KeyError, ValueError):
            check(
                probe.id,
                False,
                probe.delta if probe.delta is not None else probe.equals,
                "unobserved",
            )
    report = {
        "schema_version": 1,
        "kind": "http-contract",
        "id": run_id,
        "created_at": datetime.now(UTC).isoformat(),
        "name": contract.name,
        "label": label,
        "version": __version__,
        "contract_hash": contract.fingerprint(),
        "contract": contract.model_dump(),
        "passed": all(c["passed"] for c in checks),
        "evidence_mode": "external-http-state",
        "checks": checks,
        "observations": observations,
        "events": proxy.events,
        "duration_ms": round((time.monotonic() - start) * 1000),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.system(),
            "engine_sha256": source_fingerprint(),
        },
        # Executable arguments can contain credentials. Persist only a comparison fingerprint.
        "command_sha256": hashlib.sha256(json.dumps(command).encode()).hexdigest(),
    }
    write_http_report(report, directory)
    return report


def read_http_report(path: Path) -> dict:
    try:
        return _read_http_report(path)
    except (KeyError, TypeError, AttributeError):
        raise ValueError("malformed HTTP evidence") from None


def _read_http_report(path: Path) -> dict:
    if path.stat().st_size > 2_000_000:
        raise ValueError("HTTP report too large")
    report = json.loads(path.read_text(encoding="utf-8"))
    contract = HttpContract.model_validate(report["contract"])
    required = {"evidence_complete", "command_completed", "attempt_budget", "faults_exercised"}
    required |= {p.id for p in contract.probes}
    checks = report["checks"]
    if (
        report["kind"] != "http-contract"
        or report["schema_version"] != 1
        or report["contract_hash"] != contract.fingerprint()
        or len(checks) != len(required)
        or {c["name"] for c in checks} != required
        or any(type(c["passed"]) is not bool for c in checks)
        or type(report["passed"]) is not bool
        or report["passed"] != all(c["passed"] for c in checks)
    ):
        raise ValueError("inconsistent HTTP evidence")
    return report


def compare_http(baseline: dict, candidate: dict) -> dict:
    if baseline["contract_hash"] != candidate["contract_hash"]:
        raise ValueError("HTTP contract fingerprints differ")
    old = {c["name"]: c["passed"] for c in baseline["checks"]}
    new = {c["name"]: c["passed"] for c in candidate["checks"]}
    return {
        "baseline": baseline["id"],
        "candidate": candidate["id"],
        "regressions": [name for name in old if old[name] and not new[name]],
        "improvements": [name for name in old if not old[name] and new[name]],
        "release_allowed": candidate["passed"],
    }


def write_http_report(report: dict, directory: Path):
    (directory / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    suite = Element(
        "testsuite",
        name=report["name"],
        tests=str(len(report["checks"])),
        failures=str(sum(not c["passed"] for c in report["checks"])),
    )
    rows = []
    for c in report["checks"]:
        node = SubElement(suite, "testcase", name=c["name"], classname="http-contract")
        detail = f"Expected {c['expected']!r}; observed {c['actual']!r}"
        if not c["passed"]:
            SubElement(node, "failure", message=c["name"]).text = detail
        rows.append(
            f"<tr><td>{'PASS' if c['passed'] else 'BLOCK'}</td><td>{html.escape(c['name'])}</td>"
            f"<td>{html.escape(detail)}</td></tr>"
        )
    (directory / "junit.xml").write_text(tostring(suite, encoding="unicode"), encoding="utf-8")
    title = html.escape(report.get("label") or report["name"])
    verdict = "PASS" if report["passed"] else "BLOCK"
    evidence = html.escape(
        json.dumps({"observations": report["observations"], "events": report["events"]}, indent=2)
    )
    page = f"""<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{verdict} · {title}</title><style>
body{{font:16px/1.6 system-ui;background:#f5f6f1;color:#183a35;max-width:1100px;margin:40px auto;padding:24px}}
small{{letter-spacing:.12em}}h1{{font-size:40px}}table{{width:100%;border-collapse:collapse;background:white}}
td{{padding:14px;border-bottom:1px solid #ddd}}pre{{background:#102f2b;color:#dcf0e4;padding:24px;overflow:auto}}
</style><small>HARNESS RELEASE LAB · EXTERNAL HTTP EVIDENCE</small>
<h1>{verdict} · {title}</h1><p>Independent before/after state · {report["duration_ms"]} ms</p>
<table>{"".join(rows)}</table><h2>State and transport timeline</h2>
<p>HTTP success is not proof of commit. The selected state probes determine the effect.
Only declared probe values and transport metadata are persisted.</p><pre>{evidence}</pre>
<p>Contract SHA256: {report["contract_hash"]}</p></html>"""
    (directory / "report.html").write_text(page, encoding="utf-8")
    markdown = (
        f"## {verdict}: {report['name']}\n\n"
        + "\n".join(
            f"- {'PASS' if c['passed'] else 'BLOCK'} `{c['name']}`" for c in report["checks"]
        )
        + f"\n\nContract: `{report['contract_hash']}`\n"
    )
    (directory / "summary.md").write_text(markdown, encoding="utf-8")
