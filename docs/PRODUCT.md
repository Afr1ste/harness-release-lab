# Product thesis and evidence

Research date: 2026-10-20.

**Revised after source audit:** use [COMPETITIVE_REVIEW.md](COMPETITIVE_REVIEW.md)
for the current v0.2 decision, pinned competitor sources and commercial validation plan.
Existing HTTP agents now have an integration path in [HTTP_GUIDE.md](HTTP_GUIDE.md).

## User and purchase hypothesis

Initial user: a DSH plugin maintainer or an Agent platform engineer who repeatedly
changes runtime composition and must ensure tools still finish correctly.
Secondary user: a Python team shipping an agent with business writes.

The expensive failure is ambiguous execution: work has happened, but a timeout,
retry or extension failure makes the agent behave as though it has not.
A release gate is valuable if it catches that before a customer-facing release.

This is a commercial hypothesis, not validated demand. No interviews, pilots,
paid customers, revenue or star growth are claimed.

## Primary evidence

1. [Official DeepSeek Harness repository](https://github.com/deepseek-ai/deepseek-harness):
   plugin-oriented architecture; developer-preview compatibility warning.
2. [Python SDK source documentation](https://github.com/deepseek-ai/deepseek-harness/blob/master/python/sdk/README.md):
   explicit homes, native profiles, patch layering and published runtime.
3. [Faulty post-execute listener report](https://github.com/deepseek-ai/deepseek-harness/discussions/1489):
   a plugin can make unrelated completed tools appear to fail.
4. [Plugin-tree failure discussion](https://github.com/deepseek-ai/deepseek-harness/discussions/6693):
   community report of a third-party contract violation disrupting boot.
5. [Official test-support documentation](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/test-support/llm-mock-server/README.md):
   DSH already has scripted model faults. This is not an unexplored invention.

The discussions are incident reports at the versions they name, not proof that the
latest release still has those defects. The shipped demo uses an intentionally
broken observer to test the same class of failure without alleging an upstream bug.

Source checkout inspected: `687f282e8625c6b8d11ff58211a90524be2e4317`.
Runtime actually tested: published `0.2.1rc2` Python wheel.

## Competitive landscape

| Existing project | Published scope | Implication for this project |
|---|---|---|
| [DSH llm-replay](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/test-support/llm-replay/README.md) | Replaying session-derived model streams | Do not build or market ordinary replay as new |
| [dsh-plugin-devkit](https://github.com/CkEFFAF/dsh-plugin-devkit) | Inspector, isolated boot, contract tests, slot preview | DSH developer tooling is already competitive |
| [AgentChaos](https://github.com/floritange/AgentChaos) | Runtime LLM API fault injection | Fault injection alone is not differentiation |
| [Agent Crash Test](https://github.com/pavloparaschakis/agent-crash-test) | Effect-level faults and contracts | Closest direct competitor; our initial scope is narrower |
| [LangChain testing guidance](https://www.langchain.com/blog/evaluating-deep-agents-our-learnings) | Task evaluation and reproducible agent tests | Complement established evaluation workflows |

The comparison is based on public descriptions, not a hands-on capability benchmark.
Do not claim those projects lack capabilities not inspected.

Our initial differentiation is implementation and integration: Python-first,
published DSH SDK, real native plugin regression example, barrier-proven concurrency,
and an inspectable local release workflow. This is a starting wedge, not a moat.

## Practical launch experiment

1. Publish a clean repository after owner review, with a working one-command demo,
   honest screenshots, pinned runtime and a short reproduction.
2. Offer a compact DSH observer-regression example that maintainers can use immediately.
3. Ask 3–5 relevant maintainers to run their own patch against it. Outreach requires
   the owner's authorization; no messages have been sent.
4. Measure clean-install success, time to first meaningful failure, adapter effort,
   repeat use, and feedback on false positives.
5. Prefer fixes and adopter integrations over adding generic dashboards.

Go/no-go signals: at least two independent users can integrate a real plugin or
agent, obtain actionable evidence, and want to rerun it on a later change.
Star count alone cannot establish this.

## Potential paid layer, only after adoption

Shared release history, private CI runners, policy ownership, scheduled compatibility
matrices and managed evidence retention may justify team payment. The open-source
runner and core evidence format should remain usable locally.
Do not build accounts, subscriptions and billing before users repeatedly use the gate.

## Job relevance

The implementation provides evidence of Python engineering, async execution,
transactional state, failure semantics, protocol integration, runtime lifecycle,
testing methodology and full-stack delivery. A
[Tencent recruiting result](https://careers.tencent.com/jobdesc.html?postId=2061654749727600640)
surfaced Python/asyncio and Agent framework/evaluation experience; its JavaScript-rendered
full posting was not available to the text reader, so it is a lead rather than a
complete job-market survey. The project is not claimed to satisfy every employer's bar.
