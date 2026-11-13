# WebUI Sandbox Kit

A standalone, self-hosted assistant stack built around **Open WebUI**, **Microsandbox/KVM**,
**Frontier MCP Apps**, **Open Terminal**, **Firecrawl**, and the **WordCraft, PdfCraft and DeckCraft** engines.

One Compose project starts the control plane and optional web services. The controller boots
the official Open WebUI image in a microVM and automatically creates a separate persistent
Open Terminal microVM for each approved account. No application core patches, Docker socket,
nested Docker daemon, privileged controller or existing DNS/reverse proxy are required.

## What you get

- Chat with your own OpenAI-compatible model endpoint; no model subscription is included.
- Frontier maps, routes, galleries, charts, calculators and controls through native MCP Apps.
- Persistent per-user files, code execution and sandboxed Chromium browser tools.
- Word/PDF/PowerPoint document tools through official Craft MCP engines and CLI commands.
- Frontier file exports routed into the requesting user's workspace.
- Firecrawl search/scraping, with its own browser, PostgreSQL, Redis and RabbitMQ services.
- Native WebUI accounts, chats, notes, document knowledge, memory and scheduled-task features.
- External state/secrets, restart recovery and verified stopped-stack backup/restore commands.

This is an independent integration, not an official Open WebUI or ChatGPT distribution.
See [feature and client limits](docs/limitations.md), especially full editor UI and iOS testing.

## Requirements

Linux **x86_64**, working `/dev/kvm`, Docker Engine with Compose v2+, Python 3.12+ and `iproute2`.
The initial supported/tested host is Ubuntu with rootful Docker. The controller itself runs
as your UID with only the KVM supplementary group. Other architectures and rootless Docker
are not verified. First boot needs registry/GitHub/Hugging Face internet access.

Plan for the WebUI VM's 4 GiB plus 2 GiB per active user, Firecrawl and host overhead.
Pinned application images and persistent caches also need substantial disk space.

## Start

```sh
git clone <your-published-repository-url> webui-sandbox-kit
cd webui-sandbox-kit
./kit init --provider-url https://api.openai.com/v1 --provider-key-file /path/to/api-key --model YOUR_MODEL_ID
./kit up
```

Open **http://localhost:3000** after startup and create the first administrator in Open WebUI.
The first account becomes admin; public signup is disabled afterward. Add/approve subsequent
users in the admin UI; their private VM appears on first workspace use, then is reused across chats.

The initial build verifies pinned public release checksums. First boot pulls the pinned OCI
images and initializes WebUI; allow several minutes. `./kit logs` shows progress.

For an existing service on port 3000, choose another port with `./kit init --port 3300`.
Choose any operator-owned storage directory with `--data-dir /srv/assistant-data`.
No existing Docker network or system service is reused. An unused Docker /24 subnet is
detected automatically; `--subnet` provides an explicit override without modifying daemon settings.

## Configure and operate

```sh
./kit doctor
./kit status
./kit logs                  # controller output; guest logs are under DATA_DIR/controller/logs
./kit stop
./kit up                    # repeatable; accounts, files and secrets are retained
./kit backup                # briefly stops this stack, verifies its archive, resumes prior services
./kit verify-backup /path/to/backup.tar.gz
./kit update                # backup, then rebuild/reconcile this checkout's pinned versions
./kit down                  # removes this project's containers/network; external data stays
```

Model credentials live in `DATA_DIR/controller/config/provider-key`, never in the repository
or a user's workspace. Edit `DATA_DIR/controller/config/settings.json` for resource/account
policy, or rerun `./kit init` for provider/public URL changes, then `./kit up`.
Kit-owned provider, terminal and MCP connections are reapplied on restart; other WebUI settings
remain in its database. Resource settings initially apply to new user VMs.

Use `--no-firecrawl` at init to omit the web-service containers. A private model endpoint is
explicitly opted into with `--allow-private-provider`; only that hostname/address and port
are added to the WebUI VM's policy. User workspaces still cannot reach private networks.

## Documentation

- [Configuration and external storage](docs/configuration.md)
- [Architecture and security boundaries](docs/architecture.md)
- [Backup, restore, upgrades and recovery](docs/operations.md)
- [Features, client limitations and Craft sessions](docs/limitations.md)
- [Verification and development](docs/testing.md)
- [Publishing and upstream notices](docs/publishing.md)
- [Third-party notices](THIRD_PARTY_NOTICES.md)

The kit's integration code is MIT licensed. Upstream components retain their own licenses;
Open WebUI branding remains intact. No Enterprise Terminals code or API is used.
