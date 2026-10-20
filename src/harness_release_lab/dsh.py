"""Real DSH orchestration driven by explicit model fixtures, never a live-model benchmark."""

from __future__ import annotations

import json
from importlib.metadata import version
from pathlib import Path

import yaml
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response

from .agents import AgentContext
from .models import AgentResult
from .server import local_server


def sse(events: list[dict]) -> str:
    return "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in events)


def message_events(blocks: list[dict], stop: str) -> list[dict]:
    events = [
        {
            "type": "message_start",
            "message": {
                "id": "lab-message",
                "type": "message",
                "role": "assistant",
                "model": "lab-script",
                "content": [],
                "usage": {"input_tokens": 1, "output_tokens": 0},
            },
        }
    ]
    for index, block in enumerate(blocks):
        events.extend(
            [
                {"type": "content_block_start", "index": index, "content_block": block},
                {"type": "content_block_stop", "index": index},
            ]
        )
    events.extend(
        [
            {
                "type": "message_delta",
                "delta": {"stop_reason": stop, "stop_sequence": None},
                "usage": {"output_tokens": 1},
            },
            {"type": "message_stop"},
        ]
    )
    return events


def tool_results(messages: list[dict]) -> list[dict]:
    values = []
    for message in messages:
        content = message.get("content", [])
        if not isinstance(content, list):
            continue
        for block in content:
            if block.get("type") != "tool_result":
                continue
            inner = block.get("content", [])
            text = (
                inner
                if isinstance(inner, str)
                else "".join(item.get("text", "") for item in inner if isinstance(item, dict))
            )
            if block.get("is_error"):
                values.append({"http_status": -1, "body": text[:1000]})
                continue
            try:
                value = json.loads(text)
            except (json.JSONDecodeError, TypeError):
                raise ValueError(f"unexpected native tool result: {text[:400]}") from None
            if not isinstance(value, dict) or "http_status" not in value:
                raise ValueError("tool result did not contain an HTTP status")
            values.append(value)
    return values


def model_app(context: AgentContext, stable_keys: bool, captures: list) -> FastAPI:
    app = FastAPI(docs_url=None, openapi_url=None)

    @app.post("/v1/messages")
    async def messages(request: Request):
        body = await request.json()
        # Store protocol evidence, but no prompts, credentials, or full request bodies.
        tools = [t.get("name") for t in body.get("tools", [])]
        try:
            results = tool_results(body.get("messages", []))
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        captures.append({"request": len(captures) + 1, "tools": tools, "tool_results": results})
        if len(captures) > context.scenario.max_attempts + 3:
            raise HTTPException(400, "model fixture request budget exceeded")
        if "lab_refund" not in tools:
            raise HTTPException(400, "native lab_refund tool missing from real DSH request")
        if results and results[-1]["http_status"] == 200:
            outcome = "completed"
        elif results and results[-1]["http_status"] == 403:
            outcome = "denied"
        elif (
            results
            and results[-1]["http_status"] not in (0, 429, 503)
            or len(results) >= context.scenario.max_attempts
        ):
            outcome = "failed"
        else:
            outcome = None
        if outcome is not None:
            events = message_events(
                [{"type": "text", "text": json.dumps({"outcome": outcome})}], "end_turn"
            )
        else:
            count = context.scenario.concurrent_calls if not results else 1
            blocks = []
            for index in range(count):
                number = len(results) + index + 1
                key = context.operation_key()
                if not stable_keys:
                    key += f":attempt-{number}"
                blocks.append(
                    {
                        "type": "tool_use",
                        "id": f"lab-call-{number}",
                        "name": "lab_refund",
                        "input": {"operation_key": key, **context.scenario.operation.model_dump()},
                    }
                )
            events = message_events(blocks, "tool_use")
        return Response(sse(events), media_type="text/event-stream")

    return app


def run_dsh(context: AgentContext, stable_keys: bool) -> AgentResult:
    try:
        from deepseek_harness import DeepSeekHarness
    except ImportError:
        raise RuntimeError(
            "install the DSH extra: pip install 'harness-release-lab[dsh]'"
        ) from None
    captures: list[dict] = []
    plugin = Path(__file__).with_name("dsh_plugin.mjs").resolve()
    patch = context.workspace / "lab.patch.yml"
    patch.write_text(
        yaml.safe_dump(
            [
                {
                    "insert": [
                        {
                            "id": "harness-release-lab",
                            "name": plugin.as_uri(),
                            "config": {
                                "endpoint": context.base_url,
                                "token": context.token,
                                "timeoutMs": round(context.request_timeout * 1000),
                            },
                        }
                    ]
                }
            ]
        ),
        encoding="utf-8",
    )
    try:
        with local_server(model_app(context, stable_keys, captures)) as base:
            with DeepSeekHarness(
                dsh_home=str(context.workspace / "dsh-home"),
                cwd=str(context.workspace),
                profile="sdk-minimal",
                patches=(str(patch), *(str(p) for p in context.dsh_patches)),
                base_url=base + "/v1",
                api_key="local-lab-no-provider-key",
                provider="deepseek-official",
                model="deepseek-v4-flash",
                initialize_timeout_seconds=30,
                request_timeout_seconds=30,
                shutdown_timeout_seconds=5,
            ) as harness:
                result = harness.run(
                    "Execute the local release-contract fixture using lab_refund only.",
                    session_id="release-lab",
                )
            if result.finish_reason != "completed":
                raise RuntimeError(f"DSH finish reason: {result.finish_reason!r}")
            parsed = json.loads(result.final_response)
            return AgentResult(
                outcome=parsed["outcome"],
                metadata={
                    "sdk_version": version("deepseek-harness-sdk"),
                    "runtime_version": version("deepseek-harness-runtime-bin"),
                    "finish_reason": result.finish_reason,
                    "model_requests": captures,
                    "runtime_event_count": len(result.events),
                    "model": "local scripted Messages fixture; no inference",
                },
            )
    finally:
        # Do not preserve the temporary business bearer token in distributable artifacts.
        patch.write_text("# Per-run patch removed after execution; see dsh.py.\n", encoding="utf-8")
        (context.workspace / "model-requests.json").write_text(
            json.dumps(captures, indent=2), encoding="utf-8"
        )
