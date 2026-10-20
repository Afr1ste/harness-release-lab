import os
import sys
from pathlib import Path

import pytest

from examples.http.service import create_app
from harness_release_lab.http_contract import load_http_contract
from harness_release_lab.http_runner import run_http_contract
from harness_release_lab.server import local_server

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "mode,passed,orders", [("fixed", True, 2), ("broken", False, 3), ("over-dedup", False, 1)]
)
def test_installed_pydantic_tool_retry_loop(tmp_path, mode, passed, orders):
    pytest.importorskip("pydantic_ai")
    with local_server(create_app(tmp_path / "orders.db")) as url:
        report = run_http_contract(
            load_http_contract(ROOT / "examples/http/order.yaml"),
            [sys.executable, str(ROOT / "examples/http/pydantic_agent.py"), mode],
            tmp_path,
            env={**os.environ, "HRL_UPSTREAM": url},
            label=f"Pydantic AI · {mode}",
        )
    assert next(c for c in report["checks"] if c["name"] == "command_completed")["passed"], report
    assert report["passed"] is passed
    assert report["observations"]["after"]["two-orders"] == orders
