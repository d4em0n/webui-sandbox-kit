# Customizations and upstream tracking

This ledger describes the integration against the pins in `../versions.lock.json`.
Open WebUI core patches: **0**. Open Terminal core patches: **0**. The kit uses official
OCI images; our controller, launchers and MCP adapters carry the custom behavior.
This is an inventory of verified change groups, not a count of historical edits.

## Corrective changes included in source

| ID | Problem and solution | Location | Regression evidence |
| --- | --- | --- | --- |
| FIX-001 | Conduit sidebar/unsaved terminal scopes differed between HTTP creation and WebSocket attachment; normalize scopes and propagate backend close reasons. | `controller/terminal.py` | `tests/test_routing.py` scope and WebSocket cases |
| FIX-002 | Host reads could lag new guest accounts; check active/approved identity inside the WebUI VM and fail closed. | `controller/terminal.py` | `tests/test_routing.py` guest identity cases |
| FIX-003 | Restarted Chromium profiles retained stale singleton links; remove only stale managed links while holding the profile lease. | `controller/prepare_browser.py`, `guest/terminal-start.sh` | `tests/test_browser_profiles.py` |
| FIX-004 | Browser viewer frames were mistaken for terminal authentication; use protected header auth only for recognized browser viewer routes. | `controller/terminal.py` | `tests/test_routing.py` viewer authentication/binary cases |
| FIX-005 | Slim WebUI image lacked Office MIME guesses; supply explicit Office MIME metadata in successful display results. | `controller/terminal.py` | `tests/test_routing.py` file metadata cases; commit `4397054` |
| FIX-006 | Cached gateway DNS could outlive sandbox policy bindings; disable pooled DNS caching while retaining connection pooling. | `controller/bootstrap.py` | Live deployment idle-interval reproduction; kit initializes `AIOHTTP_POOL_DNS_TTL=0` |
| FIX-007 | Frontier defaulted to 1,600px without a host maximum, and viewport measurements prevented shrink; honor host bounds and measure natural body bounds. | `frontier/mcp-apps/app.js`, `build.py` | Synthetic SDK iframe expand/shrink verification recorded in `VERIFICATION.md` |
| FIX-008 | External search route registered before the manager's HTTP client existed; resolve that client when handling requests after startup. | `controller/firecrawl.py`, `main.py` | `tests/test_firecrawl.py` registers the route before assigning the client; staged container startup |
| FIX-009 | Private HTTPS model gateways failed closed under strict hostname policy without authority inspection; enable TLS inspection and use the guest system CA bundle. | `controller/runtime.py`, `bootstrap.py` | `tests/test_package.py` private HTTPS policy case; real staged gateway completion |
| FIX-010 | Preserve private deployment defaults during migration: derive Secure cookies from HTTPS and explicitly disable telemetry/provider identity forwarding. | `controller/bootstrap.py` | `tests/test_package.py` HTTPS/privacy settings case |

These are initially **kit-owned** fixes, not ten confirmed upstream bugs. Some correct
our own adapter assumptions. Upstream issue/PR links are pending unless explicitly listed;
do not invent an issue number or report an integration defect as an upstream regression.

## Included integration features

| ID | Feature | Source |
| --- | --- | --- |
| INT-001 | Persistent per-approved-user KVM workspace, public-web isolation and native browser/tab bootstrap. | `controller/terminal.py`, `runtime.py`, `guest/terminal-start.sh` |
| INT-002 | Frontier MCP Apps resource/tool bridge, caller-private file/note actions; original Frontier module retained. | `frontier/mcp-apps/`, `frontier/frontier_ui.py` |
| INT-003 | Per-user headless Craft engines, native MCP discovery/calls and Frontier exports. | `controller/craft.py`, `guest/craft_*.py`, `guest/frontier_craft_bridge.py` |
| INT-004 | Pinned independent deployment, external state, provider setup, Firecrawl and backup/recovery. | `compose.yaml`, `versions.lock.json`, `controller/`, `scripts/` |

## Known gaps and external changes

- **LIMIT-001: provider request size.** Large slide-image history can exceed provider byte
  limits even within a model's token window. Smaller previews and optional native context
  compaction help; no automatic byte-budget/image-resize guard is included. The operator
  continued the same conversation successfully after switching DeepSeek to GPT-6.1 Sol.
- **LIMIT-002: Conduit Office preview.** Reviewed client previews PDF/text/images, without
  requesting Office-to-PDF conversion. Native Open with is a separate Conduit fork feature,
  not an Office renderer in this kit. Use an actual PDF preview or an external editor.
- **EXT-001: Conduit fork.** MCP sizing, cache/scroll/gesture changes and native document
  handoff live in a separate client repository. See [personal setup](personal-setup.md).
  Server deployment does not install or update the mobile app.
- The live personal installation's Whisper/Piper assets, image-provider setup, automation
  preferences, private DNS and credentials are not packaged. See [limits](limitations.md).
- No physical-iPhone or second-physical-host acceptance claim applies to this kit. Live
  client observations and earlier checks of another deployment are not kit release tests.

## Maintenance contract

Every later correction gets a stable ID, owning component, minimal reproducer, regression
evidence, local commit and upstream link where applicable. Git carries the actual source;
do not maintain a second manually applied patch copy. If core patches become necessary,
record the exact upstream base, deterministic application step and removal condition.
Test every update against pins before retiring a workaround. See [contribution workflow](../CONTRIBUTING.md).
