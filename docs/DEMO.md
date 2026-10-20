# Demonstration and integration

## A 90-second story

1. Start the dashboard with `hrl serve`.
2. Run “DeepSeek Harness · broken fixture”.
3. Open “Committed, then 503”. Show the first commit, the lost acknowledgement,
   and a second commit. The gate fails because there are two receipts.
4. Run “DeepSeek Harness · fixed fixture”.
5. Select the broken run as baseline. The corrected candidate has 8/8 passing
   contracts and no extra writes.
6. Expand “Adapter and runtime evidence”. Show the published runtime version and
   actual `lab_refund` entry in the model request.
7. Export the report. It works offline without a server.

Explain explicitly: a scripted model drives the actual runtime to make faults
repeatable. These are engineering controls, not scores for DeepSeek reasoning.

## Native plugin regression

This experiment changes a DSH plugin while keeping the model fixture and business
contract identical. The faulty observer throws after a successful tool body.

Generate its patch from the repository root:

```sh
python examples/make_observer_patch.py
```

Then run:

```sh
hrl run --target dsh-fixed --suite examples/observer-contract.yaml --label observer-baseline
hrl run --target dsh-fixed --suite examples/observer-contract.yaml --label observer-candidate --dsh-patch .lab/observer.patch.yml
```

The candidate command should exit 1. A receipt is present, but the expected completed
outcome is absent. Compare the two printed `report.json` paths:

```sh
hrl compare BASELINE_REPORT_JSON CANDIDATE_REPORT_JSON
```

Use your own native DSH patch instead to test its integration. This does not discover
all plugin features automatically: add scenarios corresponding to the contracts
that your plugin affects.

## Python extension

The adapter receives:

- `scenario`: a detached copy with the operation, concurrency and retry requirements.
- `base_url` and `token`: the disposable test business endpoint and bearer token.
- `workspace`: a directory owned by this case.
- `operation_key()`: the demo's stable logical operation identifier.

It returns `AgentResult(outcome="completed" | "denied" | "failed", metadata={...})`.
Leave acceptance decisions to the engine. Preserve your own agent's logic when
adapting it; do not replace a faulty production retry policy with the reference
implementation merely to obtain a green result.

Run an adapter from an importable module:

```sh
python -m harness_release_lab.cli run --target examples.support_agent:run
```

For real-model experiments, install your own adapter and configure its credentials
outside reports. Such runs may cost money and are not part of the default demo.
One deterministic pass says nothing about stochastic reliability across models.
