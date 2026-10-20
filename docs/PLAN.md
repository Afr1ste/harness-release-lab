# Implementation and acceptance plan

Date: 2026-10-20. Status: v0.2.1 public release validation in progress.

## Autonomous release acceptance

- [x] Exercise the installed Pydantic AI framework's tool/retry path.
- [x] Detect both duplicate and swallowed orders through independent state.
- [x] Fix false blocks from the reference fixture's normal-request deadline.
- [x] Pass 66 local tests, including a deliberately slow concurrent service.
- [ ] Pass Windows/Linux and Python 3.11/3.12 on public GitHub Actions.
- [ ] Verify a clean installed wheel and publish an experimental release.

## v0.2 response to the commercial-value review

- [x] Audit closest competitors at pinned commits and state actual overlap.
- [x] Add real-service HTTP faults, independent state probes and command deadlines.
- [x] Integrate with pytest and verify duplicate and over-deduplicated orders.
- [x] Run an application-owned order tool through the published DSH runtime.
- [x] Add HTTP evidence, comparisons, read-only UI and integration documentation.
- [x] Complete error-path, native-runtime, UI and clean-wheel acceptance.
- [x] Prepare current evidence, release notes and versioned source for review.

Third-party adoption and commercial demand require external validation.

## Product decision

Build a Python-first reliability release gate for agents that perform business writes.
Initial adopter: a small engineering team shipping a tool-using support or operations agent.
Initial incident: a write commits, the response is lost, and an agent retry duplicates it.
DSH is the first real harness integration, not the boundary of the product.

Commercial hypothesis: teams will value a repeatable, inspectable pre-release workflow more
than another trace viewer. No customer interviews or paid demand have been established.
The project must earn validation; stars and revenue are outcomes, not acceptance claims.

## Scope

- Versioned scenario format; strict validation; immutable run evidence.
- Faulted business API backed by SQLite, with before/after state and append-only events.
- Deterministic faulty and corrected reference agents as positive/negative controls.
- Real DeepSeek Harness Python SDK integration with a local scripted model endpoint.
- Python extension interface for custom agent implementations.
- Gates based on durable effects, completion, retry bounds and actual fault consumption.
- Baseline/candidate comparisons, machine JSON, JUnit and standalone HTML.
- Local dashboard: run scenarios, inspect evidence, compare releases.
- Packaging, CLI, CI configuration, reproducible demo and maintainer documentation.

## Explicit boundaries

The local scripted model checks orchestration contracts, not real-model intelligence,
prompt quality, or production reliability. A green script is not a model benchmark.
The mock business service is a test environment, not a payment system or sandbox for
untrusted code. Included fixtures require no provider credentials or paid API requests.
No claim of novelty: competing fault injection, replay and evaluation tools exist.

## Acceptance

1. A clean installation can run a zero-key demonstration.
2. The deliberately flawed control passes the ordinary case and fails ambiguous commits.
3. The corrected control completes without duplicate effects in the same cases.
4. Missing actions and unconsumed faults cannot produce false green results.
5. Real DSH is exercised through its published Python SDK; captured runtime version,
   requests, finish status and business state distinguish it from the reference agents.
6. A custom Python agent can run the same suite without editing the engine.
7. A failed candidate causes a non-zero CLI exit and readable CI artifacts.
8. Report/dashboard behavior is checked in an actual browser.
9. Unit/integration tests exercise error paths, concurrent writes, restart persistence,
   malformed inputs and comparison validity.
10. README, architecture/tradeoffs, competitive evidence, demo and release materials
    are ready for review. Public publication includes remote CI verification.

## Milestones

- [x] Primary-source ecosystem research and product positioning.
- [x] Real runtime feasibility and protocol proof.
- [x] Core scenario engine, fault service and durable assertions.
- [x] CLI, reports and dashboard.
- [x] DSH scenarios and extension example.
- [x] Test, installation and browser verification.
- [x] Release and acceptance package.

See `ACCEPTANCE.md` for actual evidence and limitations. Customer validation
and star growth remain separate from engineering release acceptance.
