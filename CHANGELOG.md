# Changelog

## Unreleased

- Refresh the verified environment snapshot to Pydantic 2.14.2 / pydantic-core
  2.50.2, addressing upstream validation-bypass advisories
  [GHSA-qpmf-fgh3-ff25](https://github.com/pydantic/pydantic/security/advisories/GHSA-qpmf-fgh3-ff25)
  and [GHSA-3r8g-cqwr-jr29](https://github.com/pydantic/pydantic/security/advisories/GHSA-3r8g-cqwr-jr29).
  No affected configuration was found in the project's models: contract/report
  models forbid extra data, and there are no aliased Pydantic dataclasses or
  TypedDict validators allowing extra data. The existing package dependency range
  already permits the fixed version; this refresh does not upgrade consumers'
  existing installations or change published v0.2.5 assets.
- Handle Pydantic AI's newer `ToolReturnPart(outcome="retried")` messages in the
  offline order example, and count only successful tool returns as completed
  intents. Preserve the 2.59.0 integration pin and legacy retry messages.
- Add a separate 2.63.0 compatibility check using the existing three real-framework
  order-state controls; retries must still preserve intent and produce 2 / 3 / 1 orders.

## 0.2.5 — 2026-10-22

- Update the optional Pydantic AI integration pin to 2.59.0, which fixes
  [GHSA-4whf-38hw-pxxh](https://github.com/pydantic/pydantic-ai/security/advisories/GHSA-4whf-38hw-pxxh).
  The affected `web_fetch_tool` can exhaust resources on attacker-controlled HTML.
  Our offline order examples do not register this tool; the update prevents the
  integration extra from forcing consumers to install the affected version.
- Retain the existing real-framework order-state regression controls and release
  evidence requirements. No model calls or new runtime features are introduced.

## 0.2.4 — 2026-10-20

- Include the timing fixes validated in v0.2.3.
- Explicitly include the selected reports under `.lab` in CI artifacts. Adding
  diagnostic glob paths exposed the upload action's hidden-directory exclusion.
- Fail CI if no report artifacts are found; successful test logs alone are not
  sufficient release evidence.

## 0.2.3 — 2026-10-20 (validation tag; artifact-upload issue found before release)

- Include the v0.2.2 request-count fix and event-controlled drain test.
- Reproduce a false block with 300ms service latency: a stable-key agent committed
  once but exhausted the fixture's 200ms deadlines. Use a 1-second client deadline
  and 2-second injected delay; ordinary reference calls retain 3 seconds.
- Give the external HTTP timeout regression the same larger timing margin.
- Compare event order instead of assuming millisecond-accurate sleep completion.
- Preserve synthetic test reports on CI failure and print failed web-run cases.
- Repeat five timing regressions five times per CI environment, stopping on failure.

## 0.2.2 — 2026-10-20 (validation tag only; no published release)

The tag exposed an additional Linux background-run failure. No release assets were
published. Its original log lacked per-scenario evidence, so its precise cause is
unconfirmed; v0.2.3 adds diagnostic evidence and a separately reproduced latency fix.

- Fix a timing-sensitive test that required exactly three requests, although a fourth
  retry was within the contract budget and produced the correct two orders.
- Verify every admitted response is drained, rather than asserting a host-dependent retry count.
- Add an event-controlled concurrent test: sealing waits for an admitted write and
  rejects new requests. Repeat both gateway tests five times in CI, failing on any error.
- Use a 3-second timeout for the ordinary HTTP example; only the injected-timeout
  regression opts into 250ms through `HRL_EXAMPLE_TIMEOUT_S`.
- Require the release tag's own CI run to finish before publishing release assets.

## 0.2.1 — 2026-10-20

- Integrate Pydantic AI's installed Agent, tool execution and ModelRetry path.
- Verify that final-response success can coexist with duplicate or missing business effects.
- Pin the optional integration dependency and exercise it in the CI matrix.
- Keep normal reference requests tolerant of service latency while preserving injected timeouts.
- Add opt-in child console output for diagnosing failed agent commands.
- Make checkout example imports work with both pytest entry points in clean CI.

## 0.2.0 — 2026-10-20

- Test existing executable agents against an HTTP tool service with YAML contracts.
- Add independent state probes, bounded fault gateway, process deadlines and pytest fixture.
- Detect both duplicated writes and swallowed distinct intents in an independent order service.
- Verify an application-owned native DSH order plugin through the published runtime.
- Add external HTTP HTML/JSON/JUnit/Markdown evidence, CLI comparison and read-only history.
- Document the competitive overlap, integration requirements and limits.

## 0.1.0 — 2026-10-20

- Initial refund controls, real DSH orchestration, local dashboard and release evidence.
- Local prototype; not published to a registry.
