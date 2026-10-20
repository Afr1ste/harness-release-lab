# v0.2 release package — not published

## Repository metadata

- Name: `harness-release-lab` (availability not reserved)
- Description: Test existing Python agents and DSH tools against HTTP services. Independent state contracts, pytest and CI evidence.
- Topics: `dsh-plugin`, `deepseek-harness`, `agent-testing`, `python`, `reliability`,
  `fault-injection`, `developer-tools`
- License: MIT

## Suggested launch text

We built Harness Release Lab to test a specific agent failure:
a business write commits, its response disappears, and a retry duplicates the work.

It runs existing agent commands against your HTTP tool service, injects bounded
failures and reads independent state. Use the CLI or pytest fixture and export
HTML/JSON/JUnit/Markdown evidence. A native DSH order plugin example catches both
duplicate writes and over-broad idempotency keys that swallow legitimate operations.

The model is scripted in the demo, so these are reproducible orchestration tests,
not claims about model intelligence. We'd especially value feedback from maintainers
who want to test their own tool changes against a business contract.
Existing products already provide fault injection and state contracts. This is an
experimental Python/DSH integration tool, not production certification or validated demand.

## Publication checklist

- [ ] Owner reviews source, demo, project name and license.
- [ ] Choose the owner's GitHub namespace and create the repository.
- [ ] Push the reviewed source and verify remote Actions results.
- [ ] Replace local acceptance references with the matching commit/release identity.
- [ ] Publish a tagged source release and attach tested artifacts.
- [ ] If desired, reserve/publish the package only after a clean registry-install check.
- [ ] Obtain authorization before posting messages or submitting directory listings.

No public repository, package registry release or outreach has occurred.
