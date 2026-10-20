# Changelog

## 0.2.2 — 2026-10-20

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
