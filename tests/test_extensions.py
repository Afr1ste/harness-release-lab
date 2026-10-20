import asyncio
import importlib.util
from pathlib import Path

import pytest
import yaml

from harness_release_lab.engine import invoke, run_suite
from harness_release_lab.scenarios import load_suite


def test_unknown_target_is_rejected():
    with pytest.raises(ValueError, match="unknown target"):
        asyncio.run(invoke("typo", None))


def test_patch_refused_for_non_dsh(tmp_path):
    with pytest.raises(ValueError, match="DSH target"):
        run_suite(load_suite(), "reference-fixed", tmp_path, dsh_patches=(Path("missing.yml"),))


@pytest.mark.skipif(
    importlib.util.find_spec("deepseek_harness") is None, reason="optional DSH extra not installed"
)
def test_real_plugin_regression_is_caught(tmp_path):
    root = Path(__file__).resolve().parents[1]
    patch = tmp_path / "observer.patch.yml"
    patch.write_text(
        yaml.safe_dump(
            [
                {
                    "insert": [
                        {
                            "id": "broken-observer",
                            "name": (root / "examples" / "broken-observer.mjs").as_uri(),
                        }
                    ]
                }
            ]
        ),
        encoding="utf-8",
    )
    suite = load_suite(root / "examples" / "observer-contract.yaml")
    report = run_suite(suite, "dsh-fixed", tmp_path, dsh_patches=(patch,))
    assert not report.passed
    case = report.cases[0]
    assert len(case.effects) == 1, case.error
    assert not next(c for c in case.checks if c.name == "outcome").passed
    assert report.environment["dsh_patches"][0]["sha256"]
