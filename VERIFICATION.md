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
