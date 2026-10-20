# Release package — not published

## Repository metadata

- Name: `harness-release-lab` (availability not reserved)
- Description: Python-first release gates for tool-using agents. Real DeepSeek Harness integration, fault injection, and durable business-state evidence.
- Topics: `dsh-plugin`, `deepseek-harness`, `agent-testing`, `python`, `reliability`,
  `fault-injection`, `developer-tools`
- License: MIT

## Suggested launch text

We built Harness Release Lab to test a specific agent failure:
a business write commits, its response disappears, and a retry duplicates the work.

It runs state-based contracts through the published DeepSeek Harness runtime,
supports Python adapters and native DSH patches, and exports offline evidence plus
JUnit for CI. The zero-key demo includes deliberately broken and corrected controls.

The model is scripted in the demo, so these are reproducible orchestration tests,
not claims about model intelligence. We'd especially value feedback from maintainers
who want to test a real plugin change against the same contract.

## Publication checklist

- [ ] Owner reviews source, demo, project name and license.
- [ ] Choose the owner's GitHub namespace and create the repository.
- [ ] Push the reviewed source and verify remote Actions results.
- [ ] Replace local acceptance references with the matching commit/release identity.
- [ ] Publish a tagged source release and attach tested artifacts.
- [ ] If desired, reserve/publish the package only after a clean registry-install check.
- [ ] Obtain authorization before posting messages or submitting directory listings.

No public repository, package registry release or outreach has occurred.
