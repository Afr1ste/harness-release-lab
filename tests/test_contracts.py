import asyncio
import json
import time
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
from pydantic import ValidationError

from harness_release_lab.agents import AgentContext, reference_agent
from harness_release_lab.engine import compare, evaluate, run_suite
from harness_release_lab.models import AgentResult, Operation, Suite
from harness_release_lab.reports import html_report
from harness_release_lab.scenarios import load_suite
from harness_release_lab.server import business_app, local_server
from harness_release_lab.world import World


@pytest.fixture(scope="module")
def pair(tmp_path_factory):
    path = tmp_path_factory.mktemp("runs")
    suite = load_suite()
    return (
        run_suite(suite, "reference-broken", path),
        run_suite(suite, "reference-fixed", path),
        path,
    )


def test_controls_and_actual_state(pair):
    broken, fixed, _ = pair
    assert not broken.passed and fixed.passed
    failures = {c.scenario.id for c in broken.cases if not c.passed}
    assert failures == {"lost-ack", "lost-ack-twice", "timeout-after-commit", "concurrent-delivery"}
    assert next(c for c in broken.cases if c.scenario.id == "lost-ack-twice").effects.__len__() == 3
    assert all(c.passed for c in fixed.cases)
    assert all(c.checks[-1].passed for c in fixed.cases)


def test_normal_concurrent_delivery_tolerates_service_latency(tmp_path, monkeypatch):
    from harness_release_lab import server

    original = server.deliver

    def slower_delivery(*args):
        result = original(*args)
        time.sleep(0.3)
        return result

    monkeypatch.setattr(server, "deliver", slower_delivery)
    suite = load_suite()
    suite.scenarios = [s for s in suite.scenarios if s.id == "concurrent-delivery"]
    report = run_suite(suite, "reference-fixed", tmp_path)
    assert report.passed, report
    assert len(report.cases[0].effects) == 1


def test_compare_detects_regressions_in_both_directions(pair):
    broken, fixed, _ = pair
    improvement = compare(broken, fixed)
    assert len(improvement["improvements"]) == 4
    assert improvement["release_allowed"]
    regression = compare(fixed, broken)
    assert len(regression["regressions"]) == 4
    assert not regression["release_allowed"]


def test_incomparable_suites_and_evidence_refused(pair):
    broken, fixed, _ = pair
    with pytest.raises(ValueError, match="fingerprints"):
        compare(broken, fixed.model_copy(update={"suite_hash": "different"}))
    with pytest.raises(ValueError, match="evidence modes"):
        compare(broken, fixed.model_copy(update={"evidence_mode": "real-dsh-scripted-model"}))


@pytest.mark.parametrize("scenario_id", ["happy-path", "permission-denied", "outage", "lost-ack"])
def test_noop_and_false_success_cannot_pass(scenario_id):
    scenario = next(s for s in load_suite().scenarios if s.id == scenario_id)
    checks = evaluate(
        scenario,
        {"events": [], "effects": [], "attempts": 0},
        AgentResult(outcome=scenario.expected_outcome),
        None,
    )
    assert not all(c.passed for c in checks)
    assert not next(c for c in checks if c.name == "attempt_budget").passed


def test_unconsumed_fault_cannot_pass():
    scenario = load_suite().scenarios[1]
    checks = evaluate(
        scenario,
        {
            "events": [],
            "effects": [{"order_id": "order-1042", "amount_cents": 4900}],
            "attempts": 1,
        },
        AgentResult(outcome="completed"),
        None,
    )
    assert not next(c for c in checks if c.name == "faults_exercised").passed


def test_wrong_payload_detected():
    scenario = load_suite().scenarios[0]
    checks = evaluate(
        scenario,
        {
            "events": [],
            "effects": [{"order_id": "wrong", "amount_cents": 4900}],
            "attempts": 1,
        },
        AgentResult(outcome="completed"),
        None,
    )
    assert not next(c for c in checks if c.name == "effect_payload").passed


def test_adapter_error_never_passes():
    s = load_suite().scenarios[6]
    checks = evaluate(
        s,
        {"events": [], "effects": [], "attempts": 3},
        AgentResult(outcome="failed"),
        "runtime boot failed",
    )
    assert not next(c for c in checks if c.name == "adapter_completed").passed


def test_restart_preserves_idempotency_and_payload_conflicts(tmp_path):
    scenario = load_suite().scenarios[0]
    path = tmp_path / "world.sqlite"
    first = World(path, scenario)
    assert first.apply("stable-key", Operation())[0] == 200
    restarted = World(path, scenario)
    assert restarted.apply("stable-key", Operation())[1]["receipt_id"] == 1
    assert restarted.apply("stable-key", Operation(amount_cents=200))[0] == 409
    assert len(restarted.snapshot()["effects"]) == 1


def test_actual_parallel_writes_are_atomic(tmp_path):
    world = World(tmp_path / "world.sqlite", load_suite().scenarios[0])
    with ThreadPoolExecutor(max_workers=12) as executor:
        results = list(executor.map(lambda _: world.apply("same-key", Operation()), range(30)))
    assert all(status == 200 for status, _, _ in results)
    assert len(world.snapshot()["effects"]) == 1
    assert world.snapshot()["attempts"] == 30


def test_serial_delivery_does_not_count_as_concurrency(tmp_path):
    scenario = load_suite().scenarios[-1]
    world = World(tmp_path / "world.sqlite", scenario)
    with local_server(business_app(world, "test")) as base:
        response = httpx.post(
            base + "/refund",
            json=Operation().model_dump(),
            headers={
                "Authorization": "Bearer test",
                "Idempotency-Key": "same",
            },
            timeout=3,
            trust_env=False,
        )
    assert response.status_code == 409
    checks = evaluate(scenario, world.snapshot(), AgentResult(outcome="failed"), None)
    assert not next(c for c in checks if c.name == "concurrency_exercised").passed


def test_cross_run_isolation(tmp_path):
    scenario = load_suite().scenarios[0]
    left = World(tmp_path / "left.sqlite", scenario)
    right = World(tmp_path / "right.sqlite", scenario)
    left.apply("key", Operation())
    assert len(left.snapshot()["effects"]) == 1
    assert right.snapshot()["effects"] == []


@pytest.mark.parametrize(
    "change",
    [
        {"unexpected": True},
        {"schema_version": 2},
        {"scenarios": []},
    ],
)
def test_suite_validation(change):
    data = load_suite().model_dump()
    data.update(change)
    with pytest.raises(ValidationError):
        Suite.model_validate(data)


def test_duplicate_ids_and_impossible_fault_schedule_rejected():
    data = load_suite().model_dump()
    data["scenarios"][1]["id"] = data["scenarios"][0]["id"]
    with pytest.raises(ValidationError, match="unique"):
        Suite.model_validate(data)
    data = load_suite().model_dump()
    data["scenarios"][1]["max_attempts"] = 1
    data["scenarios"][1]["faults"] = ["after_503", "after_503"]
    with pytest.raises(ValidationError, match="schedule"):
        Suite.model_validate(data)


def test_report_artifacts_and_html_escape(pair):
    _, fixed, path = pair
    directory = path / "runs" / fixed.id
    assert json.loads((directory / "report.json").read_text())["passed"]
    assert 'failures="0"' in (directory / "junit.xml").read_text()
    poisoned = fixed.model_copy(deep=True)
    poisoned.cases[0].scenario.title = "</script><img src=x onerror=alert(1)>"
    html = html_report(poisoned)
    assert "</script><img" not in html
    assert "\\u003c/script>" in html


def test_reference_adapter_can_be_called_by_external_users(tmp_path):
    scenario = load_suite().scenarios[1]
    world = World(tmp_path / "world.sqlite", scenario)
    with local_server(business_app(world, "test")) as base:
        result = asyncio.run(reference_agent(AgentContext(scenario, base, "test", tmp_path)))
    assert result.outcome == "completed"
    assert len(world.snapshot()["effects"]) == 1


def test_adapter_cannot_accidentally_rewrite_acceptance(monkeypatch, tmp_path):
    async def bad_adapter(target, context):
        context.scenario.expected_effects = 0
        return AgentResult(outcome="completed")

    monkeypatch.setattr("harness_release_lab.engine.invoke", bad_adapter)
    suite = load_suite()
    suite.scenarios = suite.scenarios[:1]
    report = run_suite(suite, "custom:run", tmp_path)
    assert not report.passed
    assert report.cases[0].scenario.expected_effects == 1


def test_inconsistent_saved_verdict_rejected(pair):
    from harness_release_lab.models import RunReport

    broken, _, _ = pair
    data = broken.model_dump()
    data["passed"] = True
    with pytest.raises(ValidationError, match="verdict"):
        RunReport.model_validate(data)
