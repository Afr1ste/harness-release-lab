# Harness Release Lab

**A release gate for agents that write to the world.**

[中文](README.zh-CN.md) · [Architecture](docs/ARCHITECTURE.md) ·
[Product thesis](docs/PRODUCT.md) · [Acceptance evidence](docs/ACCEPTANCE.md)

An agent creates a refund. The write commits. The response times out.
The agent retries. Did it create one refund or two?

Harness Release Lab answers that question using **durable business state**, then
turns the answer into a reproducible release gate. Run the same contract against
two implementations, inspect the evidence, and block a regressing candidate.

![Release evidence dashboard](docs/assets/dashboard.png)

## Start in three commands

From a checkout, with Python 3.11+:

```sh
python -m pip install -e .
hrl demo
hrl serve
```

Open [the local dashboard](http://127.0.0.1:8787).

The package is **not published to PyPI yet**. Use a checkout or the locally built wheel.
Creating a virtual environment first is recommended.

The demo runs two deterministic reference adapters. The deliberately flawed adapter
passes 4/8 contracts; the corrected one passes 8/8. The failures expose repeated
business writes after lost acknowledgements and duplicate deliveries.

## Exercise the real DeepSeek Harness

```sh
python -m pip install -e ".[dsh]"
hrl demo --dsh
```

This starts the **published DSH runtime** through its Python SDK, loads a native
`lab_refund` tool, and feeds it a local Messages-protocol model fixture. Results
include SDK/runtime versions, actual model request tool inventories, runtime event
counts, tool feedback, and the business ledger.

No model API key, paid inference or account is required. These are **orchestration
contract tests**, not a live-model benchmark or proof that a prompt is reliable.
The fixture deliberately controls retry behavior; DSH is not being accused of
the duplicate-write behavior in the broken control.

## What gets checked

| Scenario | Fault boundary | Contract |
|---|---|---|
| Ordinary write | No injected fault | One complete operation |
| Lost acknowledgement | Commit → HTTP 503 | One receipt after retry |
| Repeated lost acknowledgement | Two ambiguous responses | One receipt after both retries |
| Timeout after commit | Durable commit → delayed response | Retry does not duplicate |
| Rate limit | HTTP 429 before commit | Bounded retry completes |
| Permission denial | HTTP 403 before commit | No write, no bypass |
| Persistent outage | Three HTTP 503s before commit | Stops at the attempt budget |
| Concurrent duplicate delivery | Barrier-synchronized requests | One durable receipt |

Every case also checks outcome, exact payload, fault consumption, nonzero execution
and retry bounds. A no-op adapter cannot pass by returning “done.” Concurrency is
verified by a server-side barrier, rather than inferred from two requests.

## Test your own DSH plugin change

Use the same scripted interaction while changing native DSH patches:

```sh
hrl run --target dsh-fixed --label baseline --suite examples/observer-contract.yaml
hrl run --target dsh-fixed --label candidate --suite examples/observer-contract.yaml --dsh-patch /absolute/path/to/candidate.patch.yml
hrl compare /path/to/baseline/report.json /path/to/candidate/report.json
```

Patches are native DSH configuration. Relative module paths resolve according to DSH;
use absolute `file:` URLs for local plugin modules. See the
[runnable observer regression](docs/DEMO.md#native-plugin-regression).

The test suite includes a real native observer plugin that throws **after** the write
has committed. The gate catches the broken result even when the receipt count is one.

## Test your Python agent

Implement an `async def run(context: AgentContext) -> AgentResult` adapter. Route its
business tool to the context's disposable API, preserve your actual retry and
idempotency behavior, and report its outcome. The engine owns the assertions.

```sh
python -m harness_release_lab.cli run --target examples.support_agent:run
```

Use an importable module from your project or installed package.
[The example](examples/support_agent.py) implements the full adapter contract.
Adapters are trusted Python code and must cooperate with cancellation; they do not
run in a security sandbox.

## CI and artifacts

`hrl run` exits **0** when all contracts pass, **1** on contract failure, and **2**
on command/configuration errors. `hrl demo` succeeds only if the broken control
fails and the corrected control passes.

Each run produces:

```text
.lab/runs/<run-id>/
  report.json          # versioned machine-readable evidence
  report.html          # standalone, offline interactive report
  junit.xml            # CI test results
  <scenario>/
    world.sqlite       # durable test business state and ordered events
    model-requests.json  # DSH only: protocol metadata, no provider credentials
```

Comparisons reject differing suite fingerprints and incompatible evidence modes.
A passing reference control cannot be substituted for a real DSH run.
The included [CI workflow](.github/workflows/ci.yml) tests Windows and Linux;
local verification details and remote-CI status are recorded separately.

## Why this exists

Replay, tracing and fault injection are established categories. This project focuses
on a small release workflow: **Python adapters + actual DSH composition + state-based
contracts + inspectable CI evidence**. It complements observability tools; it does
not replace a production monitoring or evaluation platform.

The first business simulator is intentionally narrow: a refund receipt API with
an atomic idempotency ledger. Real service semantics require an adapter and an
independent before/after observer; arbitrary production APIs are not supported
automatically. See [scope and tradeoffs](docs/ARCHITECTURE.md).

## Development

```sh
python -m pip install -e ".[dev,dsh]"
pytest -q
ruff check src tests examples
ruff format --check src tests examples
```

Tested DSH contract: `deepseek-harness-sdk==0.2.1rc2`. DSH is in developer preview;
compatibility outside the pinned version is not assumed.

MIT licensed. Independent project; not affiliated with DeepSeek.
