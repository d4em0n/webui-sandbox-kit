# Demo media

The README demo shows one Open WebUI chat in the light theme: browse Kyoto's official
tourism guide, render a Frontier itinerary/map/calculator, create a WordCraft DOCX,
then inspect the right sidebar's terminal and persistent files.

- [Full recording (MP4)](kyoto-workflow.mp4)
- [Animated preview (GIF)](kyoto-workflow.gif)
- [Still image](kyoto-workflow.png)

## Capture and provenance

Captured by [d4em0n](https://github.com/d4em0n),
[n0psledbyte@gmail.com](mailto:n0psledbyte@gmail.com), on 2026-11-15.
The kit ran in a separate Compose project, localhost port, data directory and account.
No personal chats, provider credentials or production databases were used.
Open WebUI 0.13.3 and Open Terminal 0.17.7 used the official image digests in
[the lockfile](../../versions.lock.json). Application cores were unchanged.

A deterministic QA provider selected the real `browser_action`, `render_frontier_ui`
and `craft_file` tools. This demonstrates the integration, not model reasoning or speed.
The browser opened <https://kyoto.travel/en/>; itinerary choices and costs are sample
planning assumptions. The DOCX was downloaded and its archive/text checked.
The recording continuously explores the completed chat; the opening load is trimmed.
The final terminal/files interaction inspects the same user's Inbox and opens the DOCX.

To reproduce, use a disposable installation and account as described in
[testing](../testing.md). Ask: "Use the browser to check Kyoto's tourism guide.
Plan a two-day Kyoto trip with an interactive map and budget calculator, then create
a downloadable DOCX itinerary." Use the light theme, inspect the resulting document,
then open the right sidebar's terminal and Inbox, and click the DOCX to preview it.
Record with Playwright/Chromium; encode MP4 and a smaller GIF preview with FFmpeg.
Review the recording before
publishing. Do not reuse a personal installation or commit session files/recording state.

The original application and widget branding remains visible. Map attribution is
retained in the capture: OpenFreeMap, OpenMapTiles and OpenStreetMap contributors.
Upstream software retains its [own licenses](../../THIRD_PARTY_NOTICES.md).
Only these reviewed documentation media are included, not runtime/container images.
