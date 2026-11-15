# Configuration and storage

`./kit init` creates an ignored `.env` for Compose project name, localhost port, host UID/GID,
KVM GID, data directory and an unused Docker subnet. It never reads another application's
credentials, account database, DNS configuration or runtime home. Use a separate checkout,
project, port and data directory for every concurrent installation.

Use an empty operator-owned directory or an existing kit installation. The initializer refuses unrelated nonempty directories and custom data directories inside the source checkout, protecting other services and preventing accidental publication. The default `./data` is ignored.

All persistent data is in the chosen external `DATA_DIR`:

```text
controller/
  config/                  # settings.json, provider-key and persistent generated secrets
  webui/data/              # accounts, chats, SQLite, settings, uploads and embedding assets
  webui/config/            # generated guest configuration; read-only inside WebUI VM
  terminal/private/        # user-to-VM registrations
  terminal/users/<hash>/   # that user's workspace, separate credential and logs
  terminal/manager/        # provisioner configuration and public API discovery snapshots
  runtime/                 # isolated Microsandbox catalogue, OCI cache and VM root overlays
  logs/
firecrawl/
  api.env, postgres-password
  postgres/, redis/, rabbitmq/
backups/
```

The host data root is private (0700). Guest mounts map data ownership to guest UID 1000;
the controller runs as the installation's host UID/GID. Do not mount an existing host
Microsandbox home here. The container's `/data` path is stable across machines.

`controller/config/settings.json` supports:

- `public_url`: defaults to `http://localhost:PORT`; set to your own reverse-proxy URL.
- `provider_url`, `provider_allow_private`, `default_model`: any compatible model gateway.
- `webui_cpus`, `webui_memory_mib`: default 4/4096.
- `user_cpus`, `user_memory_mib`, `max_users`: default 2/2048/2.
- `signup`: false by default. Enabled signups get the `pending` role until approved.
- `firecrawl`: true by default; `firecrawl_mode` is `bundled` or `external`, with `firecrawl_url` as the API root.
- `terminal_id`: defaults to `workspace`; preserve the previous ID when migrating chat history.
- `local_speech`: opt-in launcher for Piper; requires installed assets/packages (see [migration](migration.md)).
- `root_disk_gib`: sparse managed root overlays, default 30.

Unknown settings and invalid types/URLs are rejected. Provider credentials belong in
`provider-key` (0600). Never place them in a URL. The owner configures model access; no
particular gateway vendor, model name, domain, Tailscale or GPU is assumed.

Private HTTPS providers opt into TLS inspection so strict hostname policy can check the
HTTP authority. The guest trusts the runtime CA through its system bundle; upstream TLS
verification stays enabled. This grants only the configured provider host/port, not general
private-network access. Public-only providers and user workspaces keep their existing policy.

The configured `default_model` is published under its unchanged provider ID with a read
grant for approved users after the first admin is created. Existing model records and
their access controls are retained. Publish additional models through the native admin UI.

Frontier valves are in `controller/webui/config/frontier.json`; operator changes survive
restart. Custom CDN/tile origins are derived from those valves by the MCP resource CSP.

To expose through a reverse proxy, point it at the published localhost port and enable
WebSocket/SSE forwarding. Set `public_url` and restart the kit. The kit does not edit your
proxy or DNS. Change `BIND_ADDRESS` in `.env` only when you deliberately want a non-loopback
listener; configure your own TLS/authenticated network access before doing so.

The UI retains native Open WebUI branding. Creating a custom visual identity does not
change upstream license conditions.

## Reuse an existing Firecrawl

```sh
./kit init --firecrawl-url https://search.example.com --firecrawl-key-file /private/firecrawl-key
./kit up
```

The URL is an API root, without `/v1` or `/v2`. The key is optional for an unauthenticated
self-hosted service. Use HTTPS remotely. API versions are chosen by the pinned WebUI;
the relay preserves paths/payloads. The upstream key stays in the protected
`controller/config/firecrawl-upstream-key`; the guest uses a separate internal token.

For another Docker stack, add `--firecrawl-network NETWORK` and use an API URL reachable
on that network, such as `http://firecrawl-api:3002`. Only the controller joins it; the kit
does not manage that service/network. A host endpoint can use `http://host.docker.internal:PORT`
if it accepts connections from Docker's host gateway. Host-loopback-only services are not
reachable that way. External mode does not start the bundled API/browser/database/queue.

`--no-firecrawl` disables integration; `--bundled-firecrawl` selects the included stack again.
Reinitialization preserves keys/settings. Stop a running bundled kit before changing modes;
review its old containers separately instead of removing shared services.
