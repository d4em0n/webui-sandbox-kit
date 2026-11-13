# Features and limits

- Use a model capable of reliable native tool calling. The kit supplies tools; it cannot
  make a weak model follow them reliably. Remote model access and billing are configured
  by the installer; the QA mock provider is never part of the release Compose services.
- Frontier keeps its original schema/resolvers/renderers and independent source. Its UI
  runs in an MCP App iframe/WebView. Host capabilities control links, downloads and follow-up
  messages. Conduit versions without `ui/message` show copyable follow-up text instead.
- Transient widget control state is not durable chat state. Refresh preserves current
  values while the app stays open; reopening starts from the saved tool result. Large
  resolved cards are bounded to 220 KB for mobile bridge compatibility.
- WordCraft/PdfCraft/DeckCraft are **headless engines** with official CLI/MCP support.
  Their full desktop/web editors are not embedded or streamed by this package. Frontier
  desktop-open actions return an explicit unsupported error; downloads/previews work.
- `craft_tools` discovers official schemas; `craft_call` invokes them; `craft_reset`
  discards a user's app session and unsaved edits. Sessions are separate per user and app,
  shared across that user's chats. Saved files survive VM/controller restarts; in-memory
  active documents do not. Inspect documents before editing and save frequently.
- Frontier file exports reuse its upstream converters inside the user VM. XLSX/CSV use
  Open Terminal's Python libraries because GridCraft is not included. Other optional Craft
  apps, desktop opening and screenshot-provider integrations are not included.
- File operations through MCP need an explicit owned WebUI file ID/name. The protocol does
  not forward current-chat attachments automatically. Model-accessible workspace files can
  also be managed through native Terminal tools.
- Basic native memory, knowledge and scheduled-task features are enabled. Memory extraction
  depends on conversations/model behavior; it is not guaranteed after every message.
- Provider image generation, real-time voice, OCR dependencies and local TTS models are not
  preconfigured. Native WebUI settings remain available for adding them separately.
- Firecrawl is self-hosted but search still queries an external search engine and sites
  may block scrapers. Advanced anti-bot services and paid search credentials are not included.
- Root overlay package installs are disposable when a managed VM image is replaced. Store
  files under the persistent workspace and use user-local packages when appropriate.
- The first supported platform is Linux/amd64 with KVM and rootful Docker. macOS Docker
  Desktop, Windows, ARM64 and rootless Docker require separate validation/implementation.
- Browser/Conduit protocol compatibility does not replace physical-device testing. A native
  iPhone/iOS simulator is not attached to the development host.
