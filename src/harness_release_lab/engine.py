from __future__ import annotations

import asyncio
import hashlib
import importlib
import inspect
import platform
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from . import __version__
from .agents import AgentContext, reference_agent
from .models import AgentResult, CaseResult, Check, RunReport, Suite
from .server import business_app, local_server
from .world import World

BUILTIN_TARGETS = ("reference-broken", "reference-fixed", "dsh-broken", "dsh-fixed")


async def invoke(target: str, context: AgentContext) -> AgentResult:
    if target.startswith("reference-") and target in BUILTIN_TARGETS:
        return await reference_agent(context, target.endswith("fixed"))
    if target.startswith("dsh-") and target in BUILTIN_TARGETS:
        from .dsh import run_dsh

        return await asyncio.to_thread(run_dsh, context, target.endswith("fixed"))
    if ":" not in target:
        raise ValueError(f"unknown target {target!r}")
    module, name = target.split(":", 1)
    function = getattr(importlib.import_module(module), name)
    if not inspect.iscoroutinefunction(function):
        raise TypeError("custom agent entry point must be async def(context) -> AgentResult")
    return AgentResult.model_validate(await function(context))


def evaluate(scenario, snapshot, agent: AgentResult, error: str | None) -> list[Check]:
    effects = snapshot["effects"]
    faults = [e["fault"] for e in snapshot["events"] if e["kind"] == "fault"]
    expected_faults = [f for f in scenario.faults if f != "none"]
    arrivals = sum(e["kind"] == "concurrent_arrival" for e in snapshot["events"])
    overlap_ok = scenario.concurrent_calls == 1 or arrivals == scenario.concurrent_calls
    payload_ok = all(
        e["order_id"] == scenario.operation.order_id
        and e["amount_cents"] == scenario.operation.amount_cents
        for e in effects
    )
    return [
        Check(
            name="adapter_completed",
            passed=error is None,
            expected="no adapter error",
            actual=error or "no adapter error",
            explanation="Infrastructure failures cannot pass.",
        ),
        Check(
            name="effect_count",
            passed=len(effects) == scenario.expected_effects,
            expected=scenario.expected_effects,
            actual=len(effects),
            explanation="Count committed receipts in the business database.",
        ),
        Check(
            name="effect_payload",
            passed=payload_ok,
            expected=True,
            actual=payload_ok,
            explanation="Every committed receipt must match the requested order and amount.",
        ),
        Check(
            name="outcome",
            passed=agent.outcome == scenario.expected_outcome,
            expected=scenario.expected_outcome,
            actual=agent.outcome,
            explanation="Verify the declared outcome separately from business state.",
        ),
        Check(
            name="attempt_budget",
            passed=0 < snapshot["attempts"] <= scenario.max_attempts,
            expected=f"1..{scenario.max_attempts}",
            actual=snapshot["attempts"],
            explanation="Missing calls and runaway retries both fail.",
        ),
        Check(
            name="faults_exercised",
            passed=faults == expected_faults,
            expected=expected_faults,
            actual=faults,
            explanation="A scenario only passes if its entire fault schedule was exercised.",
        ),
        Check(
            name="delivery_exercised",
            passed=snapshot["attempts"] >= scenario.concurrent_calls,
            expected=f">={scenario.concurrent_calls}",
            actual=snapshot["attempts"],
            explanation="Every requested delivery must reach the business service.",
        ),
        Check(
            name="concurrency_exercised",
            passed=overlap_ok,
            expected=scenario.concurrent_calls if scenario.concurrent_calls > 1 else "not required",
            actual=arrivals if scenario.concurrent_calls > 1 else "not required",
            explanation="A server-side barrier proves requested deliveries overlapped.",
        ),
    ]


def run_suite(
    suite: Suite,
    target: str,
    root: Path,
    *,
    dsh_patches: tuple[Path, ...] = (),
    label: str = "",
) -> RunReport:
    if target not in BUILTIN_TARGETS and ":" not in target:
        raise ValueError(f"unknown target {target!r}")
    suite = suite.model_copy(deep=True)
    if dsh_patches and not target.startswith("dsh-"):
        raise ValueError("--dsh-patch requires a DSH target")
    dsh_patches = tuple(path.resolve(strict=True) for path in dsh_patches)
    patch_manifest = [
        {"name": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        for path in dsh_patches
    ]
    started = time.monotonic()
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%S") + "-" + uuid4().hex[:10]
    directory = root.resolve() / "runs" / run_id
    directory.mkdir(parents=True, exist_ok=False)
    results = []
    for scenario in suite.scenarios:
        start = time.monotonic()
        workspace = directory / scenario.id
        world = World(workspace / "world.sqlite", scenario)
        token = uuid4().hex
        error = None
        agent = AgentResult(outcome="failed")
        try:
            with local_server(business_app(world, token)) as base_url:
                context = AgentContext(
                    scenario.model_copy(deep=True), base_url, token, workspace, dsh_patches
                )
                # Extension coroutines must cooperate with cancellation. This is not process isolation.
                agent = asyncio.run(asyncio.wait_for(invoke(target, context), timeout=90))
        except Exception as exc:  # noqa: BLE001 - adapter failures are failed evidence, never success
            error = f"{type(exc).__name__}: {str(exc)[:4000]}"
        snapshot = world.snapshot()
        checks = evaluate(scenario, snapshot, agent, error)
        results.append(
            CaseResult(
                scenario=scenario,
                passed=all(c.passed for c in checks),
                duration_ms=round((time.monotonic() - start) * 1000),
                checks=checks,
                events=snapshot["events"],
                effects=snapshot["effects"],
                agent=agent,
                error=error,
            )
        )
    report = RunReport(
        id=run_id,
        created_at=datetime.now(UTC).isoformat(),
        target=target,
        label=label,
        suite_name=suite.name,
        suite_hash=suite.fingerprint(),
        version=__version__,
        evidence_mode=(
            "real-dsh-scripted-model"
            if target.startswith("dsh-")
            else "deterministic-reference"
            if target.startswith("reference-")
            else "custom-python-agent"
        ),
        cases=results,
        passed=all(c.passed for c in results),
        duration_ms=round((time.monotonic() - started) * 1000),
        environment={
            "python": platform.python_version(),
            "platform": platform.system(),
            "engine_sha256": source_fingerprint(),
            "dsh_patches": patch_manifest,
        },
    )
    (directory / "report.json").write_text(report.model_dump_json(indent=2), encoding="utf-8")
    from .reports import write_artifacts

    write_artifacts(report, directory)
    return report


def source_fingerprint() -> str:
    digest = hashlib.sha256()
    root = Path(__file__).parent
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix in (".py", ".mjs", ".yaml"):
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def read_report(path: Path) -> RunReport:
    return RunReport.model_validate_json(path.read_text(encoding="utf-8"))


def compare(baseline: RunReport, candidate: RunReport) -> dict:
    if baseline.suite_hash != candidate.suite_hash:
        raise ValueError("suite fingerprints differ; run both targets against the same suite")
    if baseline.evidence_mode != candidate.evidence_mode:
        raise ValueError(
            "evidence modes differ; reference controls and real harness runs are not interchangeable"
        )
    old = {case.scenario.id: case for case in baseline.cases}
    new = {case.scenario.id: case for case in candidate.cases}
    if old.keys() != new.keys():
        raise ValueError("scenario sets differ")
    regressions = [key for key in old if old[key].passed and not new[key].passed]
    improvements = [key for key in old if not old[key].passed and new[key].passed]
    return {
        "baseline": baseline.id,
        "candidate": candidate.id,
        "regressions": regressions,
        "improvements": improvements,
        "candidate_passed": candidate.passed,
        "release_allowed": candidate.passed and not regressions,
        "baseline_passed": sum(c.passed for c in baseline.cases),
        "candidate_passed_count": sum(c.passed for c in candidate.cases),
        "total": len(candidate.cases),
    }
