# Competitive review and product decision

Reviewed 2026-10-20. The conclusion is deliberately narrower than “a novel agent platform.”

## Findings from source inspection

| Project | Evidence inspected | Actual overlap | Our useful distinction |
|---|---|---|---|
| [Agent Crash Test](https://github.com/pavloparaschakis/agent-crash-test/tree/3b69c5ad0dafe65726a9e78b6fb12e6a65389280) | README, `src/observer.ts`, `src/http-transport.ts`, observer integration tests, package manifest | Real before/after observers, HTTP transport, subprocesses, mutation contracts and CI reports already exist. Its published scope is broader. | A Python package and pytest fixture, plus a tested published DSH SDK/native-plugin path. This is integration convenience, not a new testing invention. |
| [DSH Plugin DevKit](https://github.com/CkEFFAF/dsh-plugin-devkit/tree/8af209dd6f0af52f76d0a90129ff7525ce2ab2cb) | README, fake-host/test file layout and references | Runtime inspection, isolated boot, host contract tests and real-runtime audit work. It cannot honestly be dismissed as “only mocks.” | Our primary assertion is external application state after an application-owned tool ran. We do not compete on developer inspection or client previews. |
| [Official DSH support](https://github.com/deepseek-ai/deepseek-harness/tree/687f282e8625c6b8d11ff58211a90524be2e4317/packages/test-support) | LLM replay and mock-server documentation, Python SDK and native runtime integration | Scripted Messages responses, replay, transport faults and runtime testing are already provided upstream. | Package an end-user Python CI workflow around business state and existing service endpoints, while using the shipped runtime. |
| [AgentChaos](https://github.com/floritange/AgentChaos) | Public project description | LLM API fault injection is an established alternative | Different boundary: business tool HTTP responses and authoritative state. No performance comparison was run. |

Reference commits are recorded to make the assessment reviewable. We did not execute
the competitors' complete test suites, measure their defect detection, or compare
adoption, revenue or support quality. No “they cannot do this” claim follows from
not finding an example. Their source was inspected, not copied into this project.

## What we removed from the pitch

- “State-based evaluation is novel.” It is not.
- “HTTP forwarding, replay, fault injection or HTML reports are a moat.” They are not.
- “A Python rewrite alone beats the competing products.” It does not.
- “A deterministic refund demo proves production readiness or customer demand.” It does not.
- “A popular upstream guarantees stars.” It does not.

## The narrower customer job

An engineering team has a Python agent and business APIs for orders, tickets or
operations. It changes a tool wrapper, retry policy, idempotency implementation or
DSH plugin composition. Before merging, it wants to answer:

> When the tool response is ambiguous, does this exact executable still produce the
> expected number and type of business effects?

The integration cost must stay small: redirect a configurable endpoint, provide
isolated test data and an independent JSON observation, run the team's existing
command, and publish a JUnit result. If a team already has Agent Crash Test integrated,
we do not currently have a strong reason to make it migrate.

## What v0.2 delivers toward that job

1. A Python CLI and pytest fixture for existing executable commands and HTTP services.
   No required Node process or MCP conversion for the HTTP-only path.
2. A real DSH example using a separate application's `create_order` native plugin,
   external order database and the same state contracts as the ordinary Python client.
3. Checks for both duplicate execution and **over-deduplication**: the test requests
   two distinct intents and catches both three orders and one order.
4. Fail-closed evidence: missing state, ignored fault, zero calls, timeout, transport
   error and overflow all block. An HTTP 2xx is never called a commit.
5. Reviewable JSON/HTML/JUnit/Markdown artifacts, contract fingerprints, CLI comparisons,
   a read-only HTTP history page and documented trust/consistency limits.

These are concrete current strengths for this customer segment. The feature set is
straightforward to copy; there is no demonstrated technical moat.

## Commercial thesis and falsification

**Potential buyer:** the engineering lead accountable for an agent's business writes.
The economic value would be less incident/reconciliation work and less manual release
testing. We have not measured either saving.

**Open-source entry:** a fast, local release gate that works inside pytest/CI. Keeping
the local runner useful is essential; an attractive dashboard alone is not enough.

**Possible paid work after usage:** initial integration with a customer's transaction
model, private CI deployment, maintaining domain contract packs and compatibility
coverage. A hosted history or approval product is a later hypothesis, not a reason
to build billing today.

**Next validation, requiring actual external users:**

- Ask five relevant maintainers/teams to try their own agent and service.
- At least two should integrate without changing the runner and rerun it on a later PR.
- Record time to first useful failing contract, setup changes, false blocks and
  whether a maintainer would otherwise have missed that defect.
- Seek a paid pilot only after recurring use; no pricing or willingness-to-pay is asserted.

Stop expanding this direction if existing tools solve the task more easily for those
teams, independent state is too expensive to expose, or nobody reruns the contracts.
More example cases or an invented market-size number would not resolve those failures.

## Release decision

Release as an **experimental developer tool with a verified integration path**.
Do not market it as production-certified, universally compatible, or commercially
validated. Public usefulness can be tested; commercial value cannot be established
by internal examples alone.
