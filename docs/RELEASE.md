# Experimental release

Repository: [Afr1ste/harness-release-lab](https://github.com/Afr1ste/harness-release-lab).
License: MIT. Package name: `harness-release-lab`. No PyPI publication.

## Release checks

1. Run Ruff and the full tests with both optional integrations installed.
2. Run the native DSH controls, ordinary HTTP client, application-owned DSH tool,
   and Pydantic AI integration. Incorrect implementations must be blocked.
3. Build the wheel and validate its resources. Install it into a fresh environment
   outside the checkout and run both passing and failing pytest contracts.
4. Push and verify every Windows/Linux, Python 3.11/3.12 Actions job.
5. Push a tag for the verified commit and wait for the tag-triggered Actions run
   to pass all four environments too. Do not publish while that run is pending.
6. Attach the wheel, tracked source archive and SHA256 checksums to an experimental
   GitHub prerelease. Never move a published tag to hide a failure; issue a patch release.

Use the [Actions history](https://github.com/Afr1ste/harness-release-lab/actions/workflows/ci.yml)
and [release page](https://github.com/Afr1ste/harness-release-lab/releases)
for the exact executed commit and downloadable artifacts.

## Scope of the release

Runs existing agent commands against an HTTP tool service, injects bounded faults,
and reads independent state. The Python API, pytest fixture and CLI produce
HTML/JSON/JUnit/Markdown evidence. Real DSH and Pydantic AI examples catch both
repeat writes and idempotency keys that swallow legitimate operations.

Included model fixtures are scripted. These are reproducible orchestration tests,
not claims about model intelligence. Existing tools already provide fault injection
and state contracts. This is an experimental integration tool, not production
certification or proof of demand. No outreach or directory submissions are part of
this release process.
