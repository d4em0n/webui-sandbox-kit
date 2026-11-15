# Verification and development

Unit/security checks do not require KVM:

```sh
python3 -m venv .venv
.venv/bin/pip install -r controller/requirements.lock
.venv/bin/python scripts/test.py reports/unit.json
```

They cover caller approval, concurrent user mapping, separate backend credentials, ordinary
HTTP/PTY WebSocket auth, browser-view header auth and binary frames, revoked accounts,
resource configuration, browser-profile lease safety, independent secrets and backup integrity.

Use a dedicated data directory, localhost port and project for full integration tests. The
default release Compose file has no QA model endpoint. `tests/compose.qa.yaml` adds a local
OpenAI-compatible mock so connection/tool plumbing can be tested without a paid model key
or the development machine's gateway/DNS. Explicitly opt the WebUI VM into that private
endpoint; never reuse a production instance/database for these checks.

Run API checks with `tests/integration.py --base-url URL --state-dir /private/qa --disposable`.
It creates synthetic accounts/files and saves test sessions privately. `tests/guest_mcp.py`
runs inside the disposable WebUI VM with those sessions supplied through stdin. The optional
Playwright check is `tests/browser/widgets.cjs`; set `KIT_QA_URL`, `KIT_QA_STATE` and, when
needed, `PLAYWRIGHT_MODULE`. These test helpers never need a real model-provider credential.

The original deployment's feasibility experiment is not a clean-install certification of
this package. Package-level results must identify the actual tested code/image and distinguish
native browser/MCP checks from a physical iOS app. See `VERIFICATION.md` for the current result.

When changing authentication or native upstream API contracts, rerun both routing tests and
the relevant integration scenarios. Keep failure logs private; do not commit bearer tokens,
browser capability URLs, chat data or user files. Report summaries should omit secrets.

The Frontier renderer build asserts upstream extraction anchors; a changed upstream HTML
layout must be reviewed rather than silently accepted. Build with the lockfile; no guest
Node runtime is needed. Keep `frontier/frontier_ui.py` independent and unchanged.

For the independent iframe height regression, run `npm ci --ignore-scripts` and
`npm run build` in `frontier/mcp-apps`, then
`FRONTIER_SIZING_REPORT=/tmp/frontier-sizing.json node tests/sizing.mjs`.
Install Playwright/Chromium in a QA environment, or set `PLAYWRIGHT_MODULE` to its
module path. The synthetic real-SDK host checks uncapped tall content, shrinking,
explicit host limits and JavaScript exceptions; no running stack/account is used.

The same SDK host also checks dark/light styling, text/control contrast and calculator
state across theme changes in `tests/theme.mjs`. After `npm ci --ignore-scripts`, install
Chromium with `npx playwright install chromium` (Linux may also need `--with-deps`). Run
`npm run build`, then `FRONTIER_SIZING_REPORT=/tmp/frontier-sizing.json
FRONTIER_THEME_REPORT=/tmp/frontier-theme.json npm run test:browser` on one shell line.
Both browser regressions run in GitHub CI. The original Frontier module stays unchanged.
