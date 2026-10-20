import importlib.util

import pytest

from harness_release_lab.dsh import message_events, tool_results
from harness_release_lab.engine import run_suite
from harness_release_lab.scenarios import load_suite


def test_protocol_results_require_real_tool_feedback():
    with pytest.raises(ValueError, match="unexpected"):
        tool_results([{"content": [{"type": "tool_result", "content": "not-json"}]}])
    with pytest.raises(ValueError, match="HTTP status"):
        tool_results([{"content": [{"type": "tool_result", "content": "{}"}]}])
    assert message_events([{"type": "text", "text": "hello"}], "end_turn")[-1] == {
        "type": "message_stop"
    }


@pytest.mark.skipif(
    importlib.util.find_spec("deepseek_harness") is None, reason="optional DSH extra not installed"
)
def test_published_dsh_runtime_and_native_tools(tmp_path):
    suite = load_suite()
    suite.scenarios = [s for s in suite.scenarios if s.id in ("lost-ack", "concurrent-delivery")]
    report = run_suite(suite, "dsh-fixed", tmp_path)
    assert report.passed, [c.error for c in report.cases]
    for case in report.cases:
        assert case.agent.metadata["runtime_event_count"] > 0
        assert case.agent.metadata["runtime_version"] == "0.2.1rc2"
        assert "lab_refund" in case.agent.metadata["model_requests"][0]["tools"]
        assert len(case.effects) == 1
