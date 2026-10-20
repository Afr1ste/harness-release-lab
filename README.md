# Harness Release Lab

**Test your agent's business writes before shipping a retry or plugin change.**

[中文](README.zh-CN.md) · [Architecture](docs/ARCHITECTURE.md) ·
[Connect your service](docs/HTTP_GUIDE.md) · [Competitive review](docs/COMPETITIVE_REVIEW.md) ·
[Acceptance evidence](docs/ACCEPTANCE.md)

Your agent sends an order. The service processes it. The response is lost.
The agent retries. Did it create two orders? Did the fix accidentally swallow the next order?

Harness Release Lab runs **your existing agent command** through a bounded HTTP fault
gateway and checks **your application's independent before/after state**. Use it from
Python, pytest or CI. DeepSeek Harness is tested through its published SDK and real
native tools. No live model or API key is needed for the included regression fixtures.

**Status: experimental v0.2.3.** A developer tool, not a production certification
or a commercially validated service. Install from this repository or a
[GitHub release](https://github.com/Afr1ste/harness-release-lab/releases).
There is no PyPI release.

[![Release contracts](https://github.com/Afr1ste/harness-release-lab/actions/workflows/ci.yml/badge.svg)](https://github.com/Afr1ste/harness-release-lab/actions/workflows/ci.yml)

## Try the application integration

From a checkout, with Python 3.11+:

```sh
git clone https://github.com/Afr1ste/harness-release-lab.git
cd harness-release-lab
python -m pip install -e .
python -m examples.http.verify
hrl serve
```

Open [HTTP release evidence](http://127.0.0.1:8787/http).

![Existing client and native DSH contract results](docs/assets/http-history.png)

| Real client + separate order service | Orders requested | Orders created | Gate |
|---|---:|---:|---|
| Stable key per intent | 2 | 2 | PASS |
| New key on every retry | 2 | 3 | BLOCK |
| One key reused across intents | 2 | 1 | BLOCK |

Run the same integration with an application-owned native DSH tool:

```sh
python -m pip install -e ".[dsh]"
python -m examples.http.verify --dsh
```

The model fixture controls tool selection and retry decisions; it does not prove
live-model judgment. The runtime, plugin, process, HTTP service and database are real.

### Pydantic AI

```sh
python -m pip install -e ".[pydantic-ai]"
python -m examples.http.verify --pydantic-ai
```

This uses the installed framework's Agent and ModelRetry path. All three variants
finish successfully; independent state checks catch duplicated and swallowed orders.
See the [integration evidence and scope](docs/PYDANTIC_AI.md).

## Bring your existing agent

Start a disposable instance of your tool service. Set `HRL_UPSTREAM` to its origin.
Configure your agent's tool base URL from `HRL_PROXY_URL`, and isolate its test data
using `HRL_RUN_ID` or a fresh database.

```sh
hrl check contracts/orders.yaml -- python tests/run_existing_agent.py
```

The YAML names the fault boundary, independent state endpoint and expected deltas.
The runner does not replace your business service or require an MCP server.
See the [complete contract and pytest recipe](docs/HTTP_GUIDE.md).

Each run produces JSON, standalone HTML, JUnit and a Markdown summary. Missing
observations, ignored faults, no-op commands, excessive retries and timeouts block
the gate. Selected state values are saved; raw traffic and credentials are not.

## Why choose it?

Use it when your team works in Python/pytest and wants a small executable test of
business effects, especially around DSH plugin changes. Existing tools already provide
fault injection and state contracts. Our current distinction is this integration path,
not a new category or a demonstrated moat. [The source-based comparison](docs/COMPETITIVE_REVIEW.md)
states where alternatives are broader and what is still unproven.

## Explore the original reference controls

![Release evidence dashboard](docs/assets/dashboard.png)

### Refund reference demo

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

### Exercise the real DeepSeek Harness

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

The original refund simulator remains a reference control. The v0.2 HTTP path tests
your own service, but requires a configurable endpoint, isolated test data and a
meaningful state observer. It does not automatically discover business correctness.
See [scope and tradeoffs](docs/HTTP_GUIDE.md#limits-you-must-account-for).

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
