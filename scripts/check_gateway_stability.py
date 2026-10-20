"""Repeat concurrency regressions; any failure stops the check, with no rerun-to-green."""

import subprocess
import sys
from pathlib import Path

repository = Path(__file__).resolve().parents[1]
for iteration in range(5):
    print(f"Gateway stability check {iteration + 1}/5", flush=True)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_http_contracts.py::test_delayed_response_is_drained_before_state_probe",
            "tests/test_http_contracts.py::test_seal_waits_for_admitted_request_and_rejects_new_requests",
        ],
        cwd=repository,
        check=True,
        timeout=60,
    )
