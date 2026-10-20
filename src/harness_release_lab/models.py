from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Operation(StrictModel):
    order_id: str = Field(default="order-1042", min_length=1, max_length=100)
    amount_cents: int = Field(default=4900, gt=0, le=10_000_000, strict=True)


Fault = Literal["none", "before_429", "before_503", "after_503", "after_timeout", "denied"]
Outcome = Literal["completed", "denied", "failed"]


class Scenario(StrictModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=2000)
    operation: Operation = Field(default_factory=Operation)
    faults: list[Fault] = Field(default_factory=list, max_length=20)
    concurrent_calls: int = Field(default=1, ge=1, le=8)
    expected_effects: int = Field(default=1, ge=0, le=8)
    expected_outcome: Outcome = "completed"
    max_attempts: int = Field(default=3, ge=1, le=20)

    @model_validator(mode="after")
    def fault_budget(self):
        if len(self.faults) > self.max_attempts:
            raise ValueError("fault schedule exceeds max_attempts; it cannot be fully consumed")
        if self.concurrent_calls > self.max_attempts:
            raise ValueError("concurrent_calls exceeds max_attempts")
        return self


class Suite(StrictModel):
    schema_version: Literal[1] = 1
    name: str = Field(min_length=1, max_length=100)
    scenarios: list[Scenario] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def unique_ids(self):
        ids = [s.id for s in self.scenarios]
        if len(set(ids)) != len(ids):
            raise ValueError("scenario IDs must be unique")
        return self

    def fingerprint(self) -> str:
        data = json.dumps(self.model_dump(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(data.encode()).hexdigest()


class AgentResult(StrictModel):
    outcome: Outcome
    detail: str = ""
    metadata: dict = Field(default_factory=dict)


class Check(StrictModel):
    name: str
    passed: bool
    expected: object
    actual: object
    explanation: str


class CaseResult(StrictModel):
    scenario: Scenario
    passed: bool
    duration_ms: int
    checks: list[Check]
    events: list[dict]
    effects: list[dict]
    agent: AgentResult
    error: str | None = None

    @model_validator(mode="after")
    def consistent_verdict(self):
        if not self.checks or self.passed != all(c.passed for c in self.checks):
            raise ValueError("case verdict disagrees with its checks")
        return self


class RunReport(StrictModel):
    schema_version: Literal[1] = 1
    id: str
    created_at: str
    target: str
    label: str = ""
    suite_name: str
    suite_hash: str
    version: str
    evidence_mode: str
    cases: list[CaseResult]
    passed: bool
    duration_ms: int
    environment: dict

    @model_validator(mode="after")
    def consistent_report(self):
        if not self.cases or self.passed != all(c.passed for c in self.cases):
            raise ValueError("run verdict disagrees with its cases")
        suite = Suite(name=self.suite_name, scenarios=[case.scenario for case in self.cases])
        if suite.fingerprint() != self.suite_hash:
            raise ValueError("report suite fingerprint does not match its scenarios")
        return self
