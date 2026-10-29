"""Real Pydantic AI tool/retry loop with its documented offline FunctionModel seam."""

import os
import sys
from uuid import uuid4

import httpx
from pydantic_ai import Agent, ModelRetry
from pydantic_ai.messages import (
    ModelResponse,
    RetryPromptPart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.models import override_allow_model_requests
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.usage import UsageLimits


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "fixed"
    run_id = os.environ["HRL_RUN_ID"]
    observed_retry = False

    def model(messages, info):
        nonlocal observed_retry
        assert "create_order" in {tool.name for tool in info.function_tools}
        parts = [part for message in messages for part in message.parts]
        # Since Pydantic AI 2.60, tool retries are ToolReturnPart(outcome='retried').
        # Keep the legacy branch for the pinned 2.59 integration.
        observed_retry |= any(
            isinstance(part, RetryPromptPart)
            or (isinstance(part, ToolReturnPart) and part.outcome == "retried")
            for part in parts
        )
        completed = sum(
            isinstance(part, ToolReturnPart)
            and part.tool_name == "create_order"
            and part.outcome == "success"
            for part in parts
        )
        if completed == 2:
            return ModelResponse(parts=[TextPart("Two order intents completed.")])
        return ModelResponse(
            parts=[
                ToolCallPart("create_order", {"intent": "order-a" if not completed else "order-b"})
            ]
        )

    agent = Agent(FunctionModel(model), retries=2)

    @agent.tool_plain
    def create_order(intent: str) -> dict:
        """Create an order for one user intent, retrying only on an explicit transient error."""
        key = f"{run_id}:{intent}"
        if mode == "broken":
            key = uuid4().hex
        elif mode == "over-dedup":
            key = run_id
        with httpx.Client(trust_env=False, timeout=2) as client:
            response = client.post(
                os.environ["HRL_PROXY_URL"] + "/orders",
                json={"run_id": run_id, "sku": "book", "units": 1},
                headers={"Idempotency-Key": key},
            )
        if response.status_code in (429, 503):
            # The installed framework owns this retry path. There is no manual retry loop here.
            raise ModelRetry("The outcome is unknown. Retry the SAME intent.")
        response.raise_for_status()
        return response.json()

    with override_allow_model_requests(False):
        result = agent.run_sync(
            "Create two distinct order intents.",
            usage_limits=UsageLimits(request_limit=5, tool_calls_limit=4),
        )
    assert result.output == "Two order intents completed."
    assert observed_retry, "this fixture must exercise the framework's retry path"


if __name__ == "__main__":
    main()
