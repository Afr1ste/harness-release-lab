"""Optional pytest fixture. The core CLI never imports pytest."""

from pathlib import Path

import pytest

from .http_contract import HttpContract, load_http_contract
from .http_runner import run_http_contract


@pytest.fixture
def hrl_http(tmp_path):
    """Run a contract and return its evidence; the caller owns the assertion."""

    def run(contract, command, **kwargs):
        parsed = (
            contract if isinstance(contract, HttpContract) else load_http_contract(Path(contract))
        )
        return run_http_contract(parsed, command, tmp_path / "hrl", **kwargs)

    return run
