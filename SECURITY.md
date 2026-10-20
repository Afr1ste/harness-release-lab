# Security and trust model

Harness Release Lab executes trusted test code and forwards real HTTP requests to a
configured service. Use disposable test data. It is not a sandbox, authorization
boundary, payment system or production chaos gateway.

No telemetry is implemented. HTTP evidence stores selected state probe values and
transport metadata. Request/response bodies, headers, credentials and child output
are not retained by that runner. Probe values, contract text, legacy custom-adapter
metadata and raw runtime directories may still contain sensitive application data.
Review artifacts before sharing. Never commit `.env`, `.lab`, databases or DSH homes.

The web UI binds to loopback. Arbitrary commands are only accepted through the CLI,
not the browser. External HTTP reports are served with a sandboxed content policy.
Trusted child processes inherit your environment unless you supply an explicit one;
do not run unreviewed contracts, plugins or commands with production credentials.

For a vulnerability, use GitHub's private vulnerability reporting for the repository
when enabled by its owner. Do not put secrets or exploit details in a public issue.
There is no managed security response SLA or supported production release yet.
