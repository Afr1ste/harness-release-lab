# Contributing

Start with a reproducible failure and a precise business-state invariant.
Keep controls: a deliberately broken implementation must fail, and a corrected
one must pass the same contract.

```sh
python -m pip install -e ".[dev,dsh]"
ruff check src tests examples
ruff format --check src tests examples
pytest -q
hrl demo --dsh
```

For changes to the DSH bridge, test the published runtime, not a hand-built substitute.
Record runtime version and platform. A skipped optional integration is not verification.
Do not introduce live API calls into the default suite.

Keep engine, business-state observation and agent adapters separate. Add new fault
semantics to tests before making claims in documentation. Clearly label synthetic
fixtures and real-model experiments. Do not include user session logs, keys, or
private paths in examples.
