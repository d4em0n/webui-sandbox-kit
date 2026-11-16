# Verification

Verified **2026-11-13** on Linux/amd64 with KVM, Docker 29.9.2 and Compose 5.6.1.
This is a tested initial release for a private single-host deployment, not a claim of
ChatGPT feature parity or a production multi-tenant security certification.

## Checked

- **42 unit/security checks**: approval/identity boundaries, separate keys/workspaces,
  HTTP/PTY/browser WebSocket authentication, binary frames, stale Chrome leases, safe
  initialization, subnet selection, persistent settings, namespace PID repair and backups.
- Official Open WebUI 0.13.3 and Open Terminal 0.17.7 boot inside Docker-hosted restricted
  Microsandbox 0.7.15/libkrunfw 5.6.1 VMs. Controller is non-root, with all capabilities
  dropped, no-new-privileges, read-only root, default Docker seccomp/AppArmor and `/dev/kvm`.
- Fresh native admin/approved/pending accounts; approved normal-user model discovery and
  completion using the QA-only local OpenAI-compatible endpoint. No personal gateway/key/DNS
  was used by the package. The mock verifies protocol plumbing, not model intelligence.
- First-use per-user VM provisioning; separate persistent files; native Chromium HTTPS
  navigation/accessibility snapshots/screenshots through WebUI with its sandbox enabled.
- Six official-SDK Frontier protocol checks. A real browser chat produced a native MCP App;
  its calculator updated interactively. Original Frontier source remains byte-identical.
- Official WordCraft 0.18.1/PdfCraft 0.21.1/DeckCraft 0.18.1 stdio MCP sessions behind the
  authenticated per-user gateway created/edited DOCX, PDF and PPTX; outside-root writes
  and invalid sessions were rejected. User sessions/files were separated.
- Frontier export cards generated DOCX, PDF, PPTX and XLSX in the caller's workspace and
  uploaded them through that caller's WebUI session. Private file references remained scoped.
- Fresh bundled Firecrawl API/browser/Redis/PostgreSQL/RabbitMQ deployment; actual public
  search returned results and scraping retrieved expected page text.
- A killed controller automatically restarted; the existing session and generated document
  survived. Normal stops/recreates recovered both registered user VMs.
- Stopped-stack backup verified **1,797 regular files** with SHA-256 manifests. It restored
  into a separate installation/port with original account sessions, all generated document
  bytes and a changed public URL. Native browser and Craft/Frontier MCP checks passed there.
- A clean exported-source checkout independently initialized/booted with a new first admin,
  secret, data directory and Docker subnet before the restore exercise. This was separate
  installation state on the same host, not a second physical computer or clean OS test.
- Repository scan found no private machine names/IPs, tracked instance data or credentials.
  The integration source contains no edits to the host's live application/proxy/DNS setup.

## Boundaries

No native iPhone/iOS simulator, ARM64/rootless Docker, host reboot, public multi-tenant
load test or full Craft editor embedding was tested. Memory/knowledge/automation permissions
are seeded, but provider-dependent feature behavior is not exhaustively tested by the mock.
GitHub CI configuration is included; no GitHub repository or remote CI run was created.

Default capacity was subsequently bounded to two workspaces for the 10-GiB controller
budget; unit checks cover that bound and persistent custom Frontier valves. See
[limits](docs/limitations.md), [testing](docs/testing.md) and [operations](docs/operations.md).

## 2026-11-15 file metadata correction

`display_file` now supplies canonical DOCX/PPTX/XLSX MIME metadata from the external
adapter. The official WebUI image lacks the OS MIME table; its tool-result middleware
otherwise falls back to `application/octet-stream`. File bytes and original MIME values
are preserved. **44 unit/security checks pass**, including the missing-table regression.
The matching live adapter passed five checks for metadata propagation, an intact six-slide
PPTX, PDF conversion, mobile-sized Chromium canvas rendering and service health.
An iPhone Safari black-panel report remains unverified on a physical device; WebUI's viewer
also uses filename extensions, so the wrong metadata alone does not establish that cause.

## 2026-11-15 repository maintenance and external services

**50 unit/security checks pass** after adding external Firecrawl mode. Synthetic HTTP
tests cover separate upstream credentials, missing-key self-hosted services, preserved
search/scrape paths and bodies, disabled/unauthenticated requests, no redirect replay,
and exclusion of bundled services. The controller image built successfully.
The later Frontier natural-height correction is now included: its build passes, and
four real-SDK Chromium checks cover content over 1,600px, shrinking after a shorter
result, explicit host height limits and no JavaScript exceptions. These are isolated
checks; they do not add physical-iPhone or full clean-host certification.

The kit now documents corrective changes, personal iOS usage, upstream patch ownership,
linked issue reporting and migration. Optional local speech source and terminal-ID
continuity support migration with external assets and settings; live migration acceptance
is recorded separately once complete.

## 2026-11-15 operator deployment from this repository

The operator's personal service now runs from this kit's Docker-built controller and its
independent Microsandbox runtime. Existing accounts, chats, files, memories, user workspaces,
session secret and optional local speech assets were retained in external private storage.
The previous deployment is stopped and retained for rollback. No private DNS or credentials
were added to the repository; the public-origin/provider/search choices are instance settings.

**51 unit/security checks pass**, including strict private-HTTPS provider policy. Staging
passed 16 grouped checks: real gateway completion, retained accounts/workspaces/file links,
PPTX-to-PDF preview, user denial, native MCP, document engines/exports, browser navigation/PNG,
existing external Firecrawl search/scrape, local speech round trip and network isolation.
After cutover, six API groups passed again and the existing HTTPS ingress returned healthy.
The running image matched 33 tracked adapter/guest/Frontier source and lock files at promotion;
the controller is unprivileged, without a Docker socket, and publishes only localhost:3000.

These results cover one Linux homeserver. No second physical machine, host reboot or physical
iPhone test was performed for this promotion. Conduit remains a separately installed client.
Optional speech assets are externally supplied as documented, not a default bundled download.

Post-promotion hardening adds an HTTPS-origin cookie/privacy regression: **52 unit/security
checks pass**. Secure cookies follow the public origin; telemetry and provider identity
forwarding are explicitly disabled. This updates integration defaults, not application cores.

## 2026-11-16 Frontier theme adapter correction

The real-SDK iframe reproduction failed in a dark host because SDK theme attributes did
not activate the preserved renderer's CSS/map classes. FIX-011 synchronizes those classes;
no upstream component or official application core is patched. Six Chromium cases now pass
for dark/light control contrast, opposite browser preferences, host theme notifications,
partial context updates, same-card re-rendering and retained calculator state. Four existing
iframe-sizing cases and 52 Python unit/security checks also pass. Both browser suites run
in hosted CI. These are isolated SDK/renderer checks, not physical-iPhone acceptance.

## 2026-11-16 Frontier file cards

Text-only `craft_commands` no longer advertises a UI resource. The actual pinned
WebUI MCP client returns its text without creating an app embed. A separate change
adds **Open preview** beside Download on supported Frontier document cards, using
normal authenticated Files APIs and the existing document viewer.

55 controller unit/security and nine MCP protocol tests pass. Real-SDK browser
checks cover file-card navigation, retained thumbnails/downloads and no eager file
fetch, alongside the existing sizing/theme suites. A disposable WebUI instance
created PDF/DOCX/PPTX/XLSX files and an edited DOCX through real Craft calls; preview
and download worked for their owner, another account was denied and anonymous access
required login. The chat had two file widgets and no command-lookup widget.

Agent Device on Android verified both card actions reach the existing confirmed
MCP link handler. No client code changed: generic authenticated in-app browsing is
still separate work. No new physical-iPhone acceptance is claimed.
