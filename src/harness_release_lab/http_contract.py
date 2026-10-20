"""Portable contracts for an existing HTTP tool service; no business model is assumed."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

import yaml
from pydantic import Field, model_validator

from .models import StrictModel


class Probe(StrictModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")
    pointer: str = Field(pattern=r"^(|/.*)$", max_length=300)
    delta: int | None = Field(default=None, strict=True)
    equals: int | str | bool | None = None

    @model_validator(mode="after")
    def one_assertion(self):
        if (self.delta is None) == (self.equals is None):
            raise ValueError("each probe requires exactly one of delta or equals (not null)")
        if re.search(r"~(?![01])", self.pointer):
            raise ValueError("invalid JSON Pointer escape")
        return self


class Injection(StrictModel):
    at: int = Field(ge=1, le=100, strict=True)
    type: Literal["before_429", "before_503", "before_403", "after_503", "after_delay"]
    delay_ms: int = Field(default=600, ge=1, le=5000, strict=True)


class HttpContract(StrictModel):
    schema_version: Literal[1] = 1
    kind: Literal["http"] = "http"
    name: str = Field(min_length=1, max_length=120)
    upstream_env: str = Field(default="HRL_UPSTREAM", pattern=r"^[A-Z][A-Z0-9_]*$")
    method: Literal["POST", "PUT", "PATCH", "DELETE"] = "POST"
    path: str = Field(min_length=1, max_length=500)
    observer_path: str = Field(min_length=1, max_length=500)
    observer_headers_env: dict[str, str] = Field(default_factory=dict)
    probes: list[Probe] = Field(min_length=1, max_length=30)
    faults: list[Injection] = Field(default_factory=list, max_length=30)
    max_attempts: int = Field(default=3, ge=1, le=100, strict=True)
    command_timeout_s: float = Field(default=30.0, gt=0, le=600)
    upstream_timeout_s: float = Field(default=5.0, gt=0, le=30)
    settle_ms: int = Field(default=0, ge=0, le=5000, strict=True)

    @model_validator(mode="after")
    def boundaries(self):
        for path in (self.path, self.observer_path):
            parts = urlsplit(path)
            if not path.startswith("/") or path.startswith("//") or parts.fragment or parts.netloc:
                raise ValueError("paths must be origin-relative, with no fragment or host")
            if "?" in self.path or "\\" in path or ".." in parts.path.split("/"):
                raise ValueError("fault path cannot have a query; paths cannot traverse")
            if "{" in path.replace("{run_id}", "") or "}" in path.replace("{run_id}", ""):
                raise ValueError("only {run_id} may be substituted in paths")
        if len({p.id for p in self.probes}) != len(self.probes):
            raise ValueError("probe IDs must be unique")
        if any(
            p.id in {"evidence_complete", "command_completed", "attempt_budget", "faults_exercised"}
            for p in self.probes
        ):
            raise ValueError("probe ID is reserved for an infrastructure check")
        if len({f.at for f in self.faults}) != len(self.faults):
            raise ValueError("fault occurrences must be unique")
        if any(f.at > self.max_attempts for f in self.faults):
            raise ValueError("fault occurrence exceeds max_attempts")
        for key, value in self.observer_headers_env.items():
            if not re.fullmatch(r"[A-Za-z0-9-]+", key) or not re.fullmatch(
                r"[A-Z][A-Z0-9_]*", value
            ):
                raise ValueError("observer headers map HTTP header names to environment names")
        return self

    def fingerprint(self) -> str:
        canonical = json.dumps(self.model_dump(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()


def load_http_contract(path: Path) -> HttpContract:
    if path.stat().st_size > 128_000:
        raise ValueError("contract exceeds 128 KB")
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        raise ValueError("invalid contract YAML") from None
    return HttpContract.model_validate(value)


def pointer_get(document, pointer: str):
    """RFC 6901 traversal. Missing data and bool-as-number never imply zero effects."""
    node = document
    if pointer:
        for escaped in pointer[1:].split("/"):
            key = escaped.replace("~1", "/").replace("~0", "~")
            if isinstance(node, dict):
                node = node[key]
            elif isinstance(node, list) and re.fullmatch(r"0|[1-9][0-9]*", key):
                node = node[int(key)]
            else:
                raise ValueError("pointer does not resolve")
    if type(node) not in (int, str, bool) or (isinstance(node, str) and len(node) > 500):
        raise ValueError("probe must select an integer, boolean or short string")
    return node
