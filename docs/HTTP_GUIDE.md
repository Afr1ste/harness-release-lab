# Use your own service and agent

This is the v0.2 integration path. The agent runs as its normal command in a separate
process. Its HTTP tool endpoint is redirected through a temporary loopback gateway.
The gateway forwards to **your service**; the lab does not substitute a refund database.
A separate GET observes your application's state before and after the command.

## Run the complete recipe

From the repository root, with Python 3.11+:

```sh
python -m pip install -e ".[dev,dsh]"
python -m examples.http.verify
python -m examples.http.verify --dsh
hrl serve
```

Open `http://127.0.0.1:8787/http`. The first verification runs an ordinary Python HTTP
client. The second starts the published DeepSeek Harness runtime and loads an
application-owned `create_order` plugin. Both talk to the same independent SQLite
order service. Both exercise three implementations:

| Implementation | Requested orders | Observed orders | Gate |
|---|---:|---:|---|
| Key persists per user intent | 2 | 2 | PASS |
| New key on every physical attempt | 2 | 3 | BLOCK |
| One key shared by distinct intents | 2 | 1 | BLOCK |

The DSH model endpoint is scripted and local. It responds to actual tool feedback,
including the injected 503, but does not evaluate a real model's retry judgment.
The plugin, SDK, runtime, process, HTTP transport, service and persisted rows are real.
The service and plugin are examples we wrote, not an independent customer deployment.

## Integrate an existing application

You need:

1. A **disposable test service** with an authoritative, synchronous state observation.
2. A configurable business-tool base URL in the agent. Point it at `HRL_PROXY_URL`.
3. Isolated test data. Use `HRL_RUN_ID` as a tenant/test namespace, or run against
   a fresh dedicated database. A global counter shared with other jobs is unsafe evidence.
4. A normal command that terminates after the task, returning 0 on success.

The service stays outside the runner's lifecycle. Start it using your existing test
fixtures, Docker Compose or staging orchestration. The runner does not reset or delete
your service's data.

Example contract:

```yaml
schema_version: 1
kind: http
name: Two distinct orders survive a lost acknowledgement
upstream_env: HRL_UPSTREAM
method: POST
path: /orders
observer_path: /state/{run_id}
max_attempts: 4
command_timeout_s: 30
upstream_timeout_s: 5
faults:
  - at: 1
    type: after_503
probes:
  - id: two-orders
    pointer: /orders
    delta: 2
  - id: two-units
    pointer: /units
    delta: 2
```

`observer_path` returns JSON such as `{"orders": 2, "units": 2}`. Pointers follow RFC
6901, including escaped names and array indexes. `delta` requires integers; missing
values and booleans cannot stand in for zero. Use `equals` instead of `delta` for
an exact final integer, boolean or short string. Every declared probe must pass.

POSIX:

```sh
export HRL_UPSTREAM=http://127.0.0.1:8090
hrl check examples/http/order.yaml -- python examples/http/agent.py fixed
```

PowerShell:

```powershell
$env:HRL_UPSTREAM = "http://127.0.0.1:8090"
hrl check examples/http/order.yaml -- python examples/http/agent.py fixed
```

For the included service, start it separately with:

```sh
python -m uvicorn examples.http.service:create_app --factory --port 8090
```

No shell is invoked by the runner. Pass executable and arguments after `--`; use a
Python script for orchestration instead of `&&` or shell pipelines. The command inherits
the invoking environment, plus `HRL_PROXY_URL` and `HRL_RUN_ID`. Run only trusted code.

For observer authentication, map a header to an existing environment variable:

```yaml
observer_headers_env:
  Authorization: TEST_OBSERVER_AUTHORIZATION
```

The variable should hold the entire value, for example `Bearer ...`. Business request
authorization is forwarded unchanged. Neither credentials nor raw headers are stored.
Upstream URLs must be origins, without credentials, paths, fragments or query strings.

## Use pytest

Installing the package registers the `hrl_http` fixture automatically when pytest is
available. pytest is a development extra, not a requirement of the runtime package.

```python
import sys

def test_order_release(hrl_http):
    report = hrl_http(
        "contracts/orders.yaml",
        [sys.executable, "tests/run_existing_agent.py"],
    )
    assert report["passed"], report["checks"]
```

Use `env={...}` to replace the child/observer environment explicitly, and `cwd=...`
to set the command's working directory. Artifacts go into pytest's temporary directory.
The same engine is available as `run_http_contract(contract, argv, output_root)`.

## Fault semantics

| Fault | Boundary |
|---|---|
| `before_429`, `before_503`, `before_403` | Return status without forwarding the matching request |
| `after_503` | Forward, receive a complete 2xx response, then replace it with 503 |
| `after_delay` | Forward, receive a complete 2xx response, then delay up to 5 seconds |

`at` counts physical requests matching the exact method and decoded path. Other paths
are passed through, counted toward a total bound, and are not faulted. Query parameters
are forwarded but not used for matching. An after-response fault is **not consumed** on
an upstream 4xx/5xx: the gate fails, rather than claiming the intended fault happened.
Concurrent arrivals receive occurrence numbers under a lock; their order is not
deterministic. Use separate cases for order-dependent faults.

Receiving HTTP 2xx does **not** prove commit. Only the state observer supplies effect
evidence. The gateway seals admission and drains admitted requests before the after
observation. `settle_ms` allows a fixed additional wait (up to 5 seconds); this is not
proof that an eventually consistent or asynchronous business workflow has completed.
Do not use this gate to certify such a workflow without a domain-specific final-state
observer and explicit completion semantics.

Every passing run requires command exit 0, no timeout/transport error, at least one
matching call, bounded attempts, all configured faults consumed, and all state probes
passing. A no-op, missing observer, mismatched fault path or crashed command cannot pass.

## CI and comparison

```sh
hrl --root artifacts check contracts/orders.yaml -- python tests/run_agent.py
hrl http-compare baseline/report.json candidate/report.json
```

Use `hrl check --label candidate-v2 contracts/orders.yaml -- ...` to distinguish
implementations in the report history. Place options before the contract filename.
The generated [JSON Schema](../schemas/http-contract.schema.json) supports editor validation;
export it from an installed package with `hrl schema --output schema.json`.

Exit codes: 0 = contract passes, 1 = contract fails, 2 = invalid configuration.
Each run writes `report.json`, `report.html`, `junit.xml`, and `summary.md` under
`artifacts/http/<run-id>/`. Compare rejects different contract fingerprints.
Evidence files are not cryptographically signed; hashes identify content, not identity.

Upload the four files, not your service database or raw DSH home. For GitHub's job
summary append `summary.md` using your normal workflow. Commands, credentials, bodies,
headers, query values and child stdout/stderr are not persisted. **Selected probe
values are persisted**; choose non-sensitive counts/statuses, not customer records.
Contracts and probe IDs must also avoid secrets.

## Limits you must account for

- This is a trusted local CI tool, not a sandbox or a production traffic proxy.
- The child deadline terminates the command's current process tree on Windows and
  its process group on POSIX. Commands must not daemonize or detach background workers.
  Successful commands are responsible for closing their own children.
- The gateway supports bounded ordinary HTTP responses, not SSE/WebSocket/gRPC or
  transparent binary streaming. It caps request/response bodies at 2 MiB, total
  requests at 200 and recorded events at 500. Overflow blocks the gate.
- Command stdout/stderr are discarded by default. For local diagnosis, use
  `hrl check --show-agent-output contract.yaml -- ...` or `show_output=True` in
  the Python API. Output goes directly to the console, not the report. Your CI may
  capture that console output, so enable it only with appropriate test data.
- A malicious agent with the upstream origin/environment can bypass the gateway.
  State probes may catch resulting changes, but no network containment is promised.
- State measurements need authoritative reads and isolated test data. Equal counters
  alone cannot prove that the right records changed; add domain-specific probes.
- The HTML view is read-only. Starting arbitrary commands requires the local CLI.
