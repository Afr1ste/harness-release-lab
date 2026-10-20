"""Real DSH command with an application-owned tool and a zero-cost model fixture."""

import json
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml
from deepseek_harness import DeepSeekHarness
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response

from harness_release_lab.dsh import message_events, sse, tool_results
from harness_release_lab.server import local_server

app = FastAPI()
requests_seen = 0
native_tool_seen = False


@app.post("/v1/messages")
async def fixture(request: Request):
    global requests_seen, native_tool_seen
    body = await request.json()
    requests_seen += 1
    native_tool_seen = "create_order" in [tool["name"] for tool in body.get("tools", [])]
    if not native_tool_seen or requests_seen > 6:
        raise HTTPException(400, "native tool missing or fixture budget exceeded")
    results = tool_results(body.get("messages", []))
    successful = sum(r["http_status"] == 200 for r in results)
    if successful == 2:
        blocks, stop = [{"type": "text", "text": '{"complete":true}'}], "end_turn"
    elif results and results[-1]["http_status"] not in (200, 429, 503):
        blocks, stop = [{"type": "text", "text": '{"complete":false}'}], "end_turn"
    else:
        blocks, stop = (
            [
                {
                    "type": "tool_use",
                    "id": f"order-{len(results)}",
                    "name": "create_order",
                    "input": {"intent": "order-a" if successful == 0 else "order-b"},
                }
            ],
            "tool_use",
        )
    return Response(sse(message_events(blocks, stop)), media_type="text/event-stream")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "fixed"
    with TemporaryDirectory(prefix="hrl-dsh-order-") as directory:
        workspace = Path(directory)
        patch = workspace / "order.yml"
        patch.write_text(
            yaml.safe_dump(
                [
                    {
                        "insert": [
                            {
                                "id": "order-tool",
                                "name": Path(__file__).with_name("order-tool.mjs").as_uri(),
                                "config": {
                                    "endpoint": os.environ["HRL_PROXY_URL"],
                                    "runId": os.environ["HRL_RUN_ID"],
                                    "mode": mode,
                                },
                            }
                        ]
                    }
                ]
            ),
            encoding="utf-8",
        )
        with (
            local_server(app) as base,
            DeepSeekHarness(
                dsh_home=str(workspace / "home"),
                cwd=str(workspace),
                profile="sdk-minimal",
                patches=(str(patch),),
                base_url=base + "/v1",
                api_key="local-fixture",
                provider="deepseek-official",
                model="deepseek-v4-flash",
                initialize_timeout_seconds=20,
                request_timeout_seconds=20,
                shutdown_timeout_seconds=3,
            ) as harness,
        ):
            result = harness.run("Process both order intents.", session_id="order-contract")
        assert native_tool_seen and result.events and result.finish_reason == "completed"
        assert json.loads(result.final_response)["complete"]


if __name__ == "__main__":
    main()
