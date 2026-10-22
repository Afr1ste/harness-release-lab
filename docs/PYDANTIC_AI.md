# Pydantic AI integration

Tested version: `pydantic-ai-slim==2.59.0`.

The integration pins the patched release for
[GHSA-4whf-38hw-pxxh](https://github.com/pydantic/pydantic-ai/security/advisories/GHSA-4whf-38hw-pxxh).
These examples only register the order tool and use an offline FunctionModel;
they do not register the affected `web_fetch_tool`. Existing installations using
the optional integration should upgrade to HRL 0.2.5 or later.

```sh
python -m pip install -e ".[pydantic-ai]"
python -m examples.http.verify --pydantic-ai
```

The executable in `examples/http/pydantic_agent.py` uses the installed framework's
`Agent`, registered function tool, `ModelRetry`, usage limits and message history.
There is no handwritten outer retry loop. The local `FunctionModel` selects the tool
again after the framework records a retry prompt, preserving the business intent.

Three cases use identical tool arguments and the same state contract:

| Application tool variant | Agent finishes successfully | Orders committed | State gate |
|---|---|---:|---|
| Stable key per intent | Yes | 2 | PASS |
| New key on physical retry | Yes | 3 | BLOCK |
| Shared key across distinct intents | Yes | 1 | BLOCK |

This demonstrates why an assertion on the final agent response alone is insufficient.
All three agent processes return success; the independent business state distinguishes
them. These defects are deliberately in the example application tool, not alleged
defects in Pydantic AI.

Recorded evidence: [fixed](evidence/pydantic-fixed.html),
[duplicate](evidence/pydantic-broken.html),
[over-deduplicated](evidence/pydantic-over-dedup.html).

The [official testing seam](https://pydantic.dev/docs/ai/guides/testing/) replaces the
model with a function. Real provider calls are disabled using
`override_allow_model_requests(False)`. It tests framework orchestration and tool
effects, not model reasoning or provider compatibility.

This is an integration with a third-party framework, **not third-party adoption**.
The application service and contract are ours. No external team or paid customer is
claimed. The native DSH and plain HTTP recipes continue to use the same service contract.
