"""End-to-end recipe using an independent HTTP service and existing client commands."""

import json
import os
import sys
from pathlib import Path

from examples.http.service import create_app
from harness_release_lab.http_contract import load_http_contract
from harness_release_lab.http_runner import run_http_contract
from harness_release_lab.server import local_server

root = Path(__file__).resolve().parents[2]
contract = load_http_contract(root / "examples/http/order.yaml")
output = root / ".lab"
if "--dsh" in sys.argv:
    script, framework = "dsh_agent.py", "Native DSH"
elif "--pydantic-ai" in sys.argv:
    script, framework = "pydantic_agent.py", "Pydantic AI"
else:
    script, framework = "agent.py", "Python client"
with local_server(create_app(output / "http-orders.sqlite")) as url:
    reports = {
        mode: run_http_contract(
            contract,
            [sys.executable, str(root / "examples/http" / script), mode],
            output,
            env={**os.environ, "HRL_UPSTREAM": url},
            label=f"{framework} · {mode}",
        )
        for mode in ("fixed", "broken", "over-dedup")
    }
print(
    json.dumps(
        {
            mode: {"passed": r["passed"], "id": r["id"], "state": r["observations"]}
            for mode, r in reports.items()
        },
        indent=2,
    )
)
assert reports["fixed"]["passed"]
assert not reports["broken"]["passed"]
assert not reports["over-dedup"]["passed"]
