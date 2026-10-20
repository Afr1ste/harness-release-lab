from pathlib import Path

import yaml

from .models import Suite


def load_suite(path: str | Path | None = None) -> Suite:
    path = Path(path) if path else Path(__file__).parent / "data" / "release.yaml"
    if path.stat().st_size > 1_000_000:
        raise ValueError("suite exceeds 1 MB")
    return Suite.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
