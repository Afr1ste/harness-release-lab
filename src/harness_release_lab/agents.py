from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import httpx

from .models import AgentResult, Scenario


@dataclass(frozen=True)
class AgentContext:
    """Public adapter contract. Only use these disposable test resources."""

    scenario: Scenario
    base_url: str
    token: str
    workspace: Path
    dsh_patches: tuple[Path, ...] = ()

    def operation_key(self) -> str:
        return f"refund:{self.scenario.operation.order_id}"

    @property
    def request_timeout(self) -> float:
        return 0.2 if "after_timeout" in self.scenario.faults else 3.0


async def reference_agent(context: AgentContext, stable_keys: bool = True) -> AgentResult:
    async with httpx.AsyncClient(timeout=context.request_timeout, trust_env=False) as client:

        async def attempt():
            key = context.operation_key() if stable_keys else str(uuid4())
            try:
                response = await client.post(
                    context.base_url + "/refund",
                    json=context.scenario.operation.model_dump(),
                    headers={
                        "Authorization": f"Bearer {context.token}",
                        "Idempotency-Key": key,
                    },
                )
                if response.status_code == 200:
                    return "completed"
                if response.status_code == 403:
                    return "denied"
                if response.status_code not in (429, 503):
                    return "failed"
            except httpx.TimeoutException:
                pass
            return "retry"

        if context.scenario.concurrent_calls > 1:
            results = await asyncio.gather(
                *(attempt() for _ in range(context.scenario.concurrent_calls))
            )
            outcome = "completed" if all(r == "completed" for r in results) else "failed"
            return AgentResult(outcome=outcome)
        for _ in range(context.scenario.max_attempts):
            result = await attempt()
            if result != "retry":
                return AgentResult(outcome=result)
        return AgentResult(outcome="failed", detail="attempt budget exhausted")
