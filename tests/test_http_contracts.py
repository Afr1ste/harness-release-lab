import json
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from examples.http.service import create_app
from harness_release_lab.http_contract import HttpContract, load_http_contract, pointer_get
from harness_release_lab.http_proxy import FaultProxy
from harness_release_lab.http_runner import run_http_contract
from harness_release_lab.server import local_server

ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / "examples/http/agent.py"


def contract(**overrides):
    data = load_http_contract(ROOT / "examples/http/order.yaml").model_dump()
    return HttpContract.model_validate({**data, **overrides})


def run(tmp_path, url, command=None, *, show_output=False, **changes):
    return run_http_contract(
        contract(**changes),
        command or [sys.executable, str(AGENT)],
        tmp_path,
        env={**os.environ, "HRL_UPSTREAM": url},
        show_output=show_output,
    )


@pytest.mark.parametrize(
    "mode,passed,count", [("fixed", True, 2), ("broken", False, 3), ("over-dedup", False, 1)]
)
def test_actual_process_uses_existing_service(tmp_path, mode, passed, count):
    with local_server(create_app(tmp_path / "orders.db")) as url:
        report = run(tmp_path, url, [sys.executable, str(AGENT), mode])
    assert report["passed"] is passed, report
    assert report["observations"]["after"]["two-orders"] == count
    assert any(e["kind"] == "injection" and e["phase"] == "after_2xx" for e in report["events"])
    directory = tmp_path / "http" / report["id"]
    assert {p.name for p in directory.iterdir()} == {
        "report.json",
        "report.html",
        "junit.xml",
        "summary.md",
    }


def test_delayed_response_is_drained_before_state_probe(tmp_path):
    with local_server(create_app(tmp_path / "orders.db")) as url:
        report = run(tmp_path, url, faults=[{"at": 1, "type": "after_delay", "delay_ms": 500}])
    assert report["passed"], report
    assert report["observations"]["after"]["two-orders"] == 2
    assert len([e for e in report["events"] if e["kind"] == "upstream_response"]) == 3


def test_noop_cannot_pass_and_missing_fault_is_visible(tmp_path):
    with local_server(create_app(tmp_path / "orders.db")) as url:
        report = run(tmp_path, url, [sys.executable, "-c", "pass"])
    failed = {c["name"] for c in report["checks"] if not c["passed"]}
    assert {"attempt_budget", "faults_exercised", "two-orders"} <= failed


def test_missing_observer_stops_command_before_effect(tmp_path):
    marker = tmp_path / "executed"
    with local_server(create_app(tmp_path / "orders.db")) as url:
        report = run(
            tmp_path,
            url,
            [sys.executable, "-c", f"open({str(marker)!r}, 'w').close()"],
            observer_path="/missing",
        )
    assert not marker.exists()
    assert not report["passed"]
    assert not report["events"]


def test_failed_after_observer_cannot_pass(tmp_path):
    app = create_app(tmp_path / "orders.db")
    reads = 0

    @app.get("/probe")
    def probe():
        nonlocal reads
        reads += 1
        if reads == 1:
            return {"orders": 0, "units": 0}
        return JSONResponse({"error": "offline"}, status_code=503)

    with local_server(app) as url:
        report = run(tmp_path, url, observer_path="/probe")
    assert not report["passed"]
    assert next(c for c in report["checks"] if c["name"] == "two-orders")["actual"] == "unobserved"


def test_bool_is_not_a_numeric_state_delta(tmp_path):
    app = create_app(tmp_path / "orders.db")

    @app.get("/probe")
    def probe():
        return {"orders": True, "units": False}

    with local_server(app) as url:
        report = run(tmp_path, url, observer_path="/probe")
    assert not report["passed"]
    assert next(c for c in report["checks"] if c["name"] == "two-orders")["actual"] == "unobserved"


def test_upstream_failure_is_not_claimed_as_after_commit_injection(tmp_path):
    app = FastAPI()

    @app.get("/state/{run_id}")
    def state(run_id: str):
        return {"orders": 0, "units": 0}

    @app.post("/orders")
    def unavailable():
        return JSONResponse({}, status_code=503)

    with local_server(app) as url:
        report = run(tmp_path, url)
    assert not report["passed"]
    assert not any(e["kind"] == "injection" for e in report["events"])
    assert not next(c for c in report["checks"] if c["name"] == "faults_exercised")["passed"]


def test_process_deadline_is_real_even_for_noncooperative_client(tmp_path):
    with local_server(create_app(tmp_path / "orders.db")) as url:
        started = time.monotonic()
        report = run(
            tmp_path, url, [sys.executable, "-c", "while True: pass"], command_timeout_s=0.2
        )
    assert time.monotonic() - started < 5
    assert not report["passed"]
    check = next(c for c in report["checks"] if c["name"] == "command_completed")
    assert check["actual"]["timed_out"]


def test_proxy_preserves_auth_and_encoding_but_does_not_store_secrets(tmp_path):
    from fastapi import Request

    app = FastAPI()
    received = []

    @app.post("/orders")
    async def service(request: Request):
        received.append(
            (request.headers["authorization"], await request.json(), request.query_params["key"])
        )
        return {"ok": True}

    with local_server(app) as upstream:
        proxy = FaultProxy(contract(faults=[]), upstream, "a" * 32)
        with local_server(proxy.app) as url:
            response = httpx.post(
                url + "/orders?key=query-secret",
                json={"secret": "body-secret"},
                headers={"Authorization": "Bearer header-secret"},
                trust_env=False,
            )
            assert response.status_code == 200
            proxy.seal()
    assert received == [("Bearer header-secret", {"secret": "body-secret"}, "query-secret")]
    text = json.dumps(proxy.events)
    assert "secret" not in text


def test_failure_messages_and_child_output_do_not_leak_credentials(tmp_path):
    with local_server(create_app(tmp_path / "orders.db")) as url:
        report = run(
            tmp_path, url, [sys.executable, "-c", "print('private-token-123'); raise SystemExit(1)"]
        )
    for file in (tmp_path / "http" / report["id"]).iterdir():
        assert "private-token-123" not in file.read_text(encoding="utf-8")


def test_concurrent_proxy_calls_preserve_exact_attempt_budget(tmp_path):
    import concurrent.futures

    app = FastAPI()
    seen = []

    @app.post("/orders")
    def service():
        seen.append(1)
        return {}

    with local_server(app) as upstream:
        proxy = FaultProxy(contract(faults=[], max_attempts=3), upstream, "a" * 32)
        with local_server(proxy.app) as url:
            with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
                statuses = list(
                    executor.map(
                        lambda _: httpx.post(url + "/orders", trust_env=False).status_code, range(6)
                    )
                )
            proxy.seal()
    assert statuses.count(200) == 3
    assert statuses.count(429) == 3
    assert len(seen) == 3
    assert "attempt_budget" in proxy.errors


def test_cli_blocks_actual_regression(tmp_path):
    with local_server(create_app(tmp_path / "orders.db")) as url:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "harness_release_lab.cli",
                "--root",
                str(tmp_path),
                "check",
                str(ROOT / "examples/http/order.yaml"),
                "--",
                sys.executable,
                str(AGENT),
                "broken",
            ],
            env={**os.environ, "HRL_UPSTREAM": url},
            capture_output=True,
            check=False,
            text=True,
            timeout=15,
        )
    assert result.returncode == 1, result.stderr
    assert "BLOCK two-orders" in result.stdout


def test_pytest_fixture(hrl_http, tmp_path):
    with local_server(create_app(tmp_path / "orders.db")) as url:
        report = hrl_http(
            contract(), [sys.executable, str(AGENT)], env={**os.environ, "HRL_UPSTREAM": url}
        )
    assert report["passed"], report


@pytest.mark.parametrize("mode,passed,count", [("fixed", True, 2), ("broken", False, 3)])
def test_application_owned_tool_in_real_dsh(tmp_path, mode, passed, count):
    pytest.importorskip("deepseek_harness")
    with local_server(create_app(tmp_path / "orders.db")) as url:
        report = run(
            tmp_path,
            url,
            [sys.executable, str(AGENT.with_name("dsh_agent.py")), mode],
            show_output=True,
        )
    assert report["passed"] is passed, report
    assert report["observations"]["after"]["two-orders"] == count, report
    assert next(c for c in report["checks"] if c["name"] == "command_completed")["passed"]


@pytest.mark.parametrize(
    "changes",
    [
        {"path": "https://elsewhere/orders"},
        {"observer_path": "//elsewhere/state"},
        {"path": "/orders?q=1"},
        {"path": "/a/../orders"},
        {"faults": [{"at": 5, "type": "after_503"}]},
        {"faults": [{"at": 1, "type": "after_503"}, {"at": 1, "type": "before_503"}]},
        {"probes": [{"id": "p", "pointer": "/x"}]},
        {"probes": [{"id": "p", "pointer": "/x~2", "delta": 1}]},
    ],
)
def test_invalid_contracts_rejected(changes):
    with pytest.raises(ValueError):
        contract(**changes)


def test_json_pointer_handles_escaped_keys_and_lists():
    assert pointer_get({"a/b": [{"~key": 5}]}, "/a~1b/0/~0key") == 5
    with pytest.raises(ValueError):
        pointer_get([1], "/01")


def test_external_evidence_web_and_comparison(tmp_path):
    from fastapi.testclient import TestClient

    from harness_release_lab.http_runner import compare_http, read_http_report
    from harness_release_lab.webapp import create_app as create_web

    with local_server(create_app(tmp_path / "orders.db")) as url:
        fixed = run(tmp_path, url)
        broken = run(tmp_path, url, [sys.executable, str(AGENT), "broken"])
    fixed_path = tmp_path / "http" / fixed["id"] / "report.json"
    assert read_http_report(fixed_path)["passed"]
    result = compare_http(fixed, broken)
    assert not result["release_allowed"]
    assert result["regressions"] == ["two-orders", "two-units"]
    assert compare_http(broken, fixed)["release_allowed"]
    with TestClient(create_web(tmp_path)) as client:
        assert fixed["id"] in client.get("/http").text
        response = client.get("/http/" + broken["id"])
        assert response.status_code == 200
        assert "BLOCK" in response.text
        assert "sandbox" in response.headers["content-security-policy"]
        assert client.get("/http/not-a-run").status_code == 404
    fixed["passed"] = False
    fixed_path.write_text(json.dumps(fixed), encoding="utf-8")
    with pytest.raises(ValueError, match="inconsistent"):
        read_http_report(fixed_path)


@pytest.mark.parametrize("fault", ["before_429", "before_503"])
def test_before_fault_does_not_reach_service(tmp_path, fault):
    with local_server(create_app(tmp_path / "orders.db")) as url:
        report = run(tmp_path, url, faults=[{"at": 1, "type": fault}])
    assert report["passed"], report
    forwarded = [e for e in report["events"] if e["kind"] == "upstream_response"]
    assert len(forwarded) == 2


def test_denial_contract_has_no_effect(tmp_path):
    code = (
        "import os,urllib.request,urllib.error; "
        "r=urllib.request.Request(os.environ['HRL_PROXY_URL']+'/orders',data=b'{}');\n"
        "try: urllib.request.build_opener(urllib.request.ProxyHandler({})).open(r)\n"
        "except urllib.error.HTTPError as e: assert e.code==403\n"
    )
    with local_server(create_app(tmp_path / "orders.db")) as url:
        report = run(
            tmp_path,
            url,
            [sys.executable, "-c", code],
            faults=[{"at": 1, "type": "before_403"}],
            probes=[{"id": "no-orders", "pointer": "/orders", "delta": 0}],
        )
    assert report["passed"], report
    assert not any(e["kind"] == "upstream_response" for e in report["events"])


def test_manifest_error_produces_exit_two_without_traceback(tmp_path):
    invalid = tmp_path / "invalid.yml"
    invalid.write_text("name: [", encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "harness_release_lab.cli",
            "check",
            str(invalid),
            "--",
            sys.executable,
            "-c",
            "pass",
        ],
        capture_output=True,
        check=False,
        text=True,
        timeout=10,
    )
    assert result.returncode == 2
    assert "Traceback" not in result.stderr


def test_oversized_response_blocks_even_if_effect_has_happened(tmp_path):
    from fastapi.responses import Response

    app = FastAPI()

    @app.post("/orders")
    def large():
        return Response(b"x" * (2 * 1024 * 1024 + 1))

    with local_server(app) as upstream:
        proxy = FaultProxy(contract(), upstream, "a" * 32)
        with local_server(proxy.app) as url:
            result = httpx.post(url + "/orders", trust_env=False)
            assert result.status_code == 502
            proxy.seal()
    assert proxy.errors
    assert not proxy.consumed


def test_saved_yaml_defaults_are_readable_after_roundtrip(tmp_path):
    """A direct YAML load must work, not just an already revalidated test helper."""
    from harness_release_lab.http_runner import read_http_report

    original = load_http_contract(ROOT / "examples/http/order.yaml")
    with local_server(create_app(tmp_path / "orders.db")) as url:
        report = run_http_contract(
            original,
            [sys.executable, str(AGENT)],
            tmp_path,
            env={**os.environ, "HRL_UPSTREAM": url},
            label="release candidate",
        )
    reread = read_http_report(tmp_path / "http" / report["id"] / "report.json")
    assert reread["passed"]
    assert reread["label"] == "release candidate"
    assert reread["contract_hash"] == original.fingerprint()
