"""Example extension: replace run() with your own agent under test.

From the repository root:
python -m harness_release_lab.cli run --target examples.support_agent:run
"""

import httpx

from harness_release_lab.agents import AgentContext
from harness_release_lab.models import AgentResult


async def run(context: AgentContext) -> AgentResult:
    """A small external adapter, including bounded retries and duplicate delivery."""
    import asyncio

    async def deliver(client):
        for _ in range(context.scenario.max_attempts):
            try:
                result = await client.post(
                    context.base_url + "/refund",
                    headers={
                        "Authorization": f"Bearer {context.token}",
                        "Idempotency-Key": context.operation_key(),
                    },
                    json=context.scenario.operation.model_dump(),
                )
                if result.status_code == 200:
                    return "completed"
                if result.status_code == 403:
                    return "denied"
                if result.status_code not in (429, 503):
                    return "failed"
            except httpx.TimeoutException:
                continue
        return "failed"

    async with httpx.AsyncClient(timeout=context.request_timeout, trust_env=False) as client:
        if context.scenario.concurrent_calls > 1:
            outcomes = await asyncio.gather(
                *(deliver(client) for _ in range(context.scenario.concurrent_calls))
            )
            outcome = "completed" if all(o == "completed" for o in outcomes) else "failed"
        else:
            outcome = await deliver(client)
    return AgentResult(outcome=outcome, metadata={"adapter": "external example"})
