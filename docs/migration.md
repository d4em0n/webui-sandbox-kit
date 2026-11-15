# Migrating an existing installation

Use an isolated kit checkout, port, project and private data directory. The kit does not
discover/import another application's credentials or workspaces automatically. An operator
must authorize migration; never include imported state in Git or container builds.

Record old image pins, account counts, terminal connection ID, active-user mappings,
secret-key continuity and optional adapters. Inventory root-overlay packages separately:
replacing a VM does not preserve software outside persistent mounts. Back up and verify
SQLite and workspace archives before stopping the old deployment.

Copy WebUI data with consistent SQLite semantics (stopped application or SQLite backup),
including uploads, vector state, model assets and sessions. Preserve `WEBUI_SECRET_KEY` in
private `controller/config/webui-secret`. Set `terminal_id` to the previous ID for old chat
links. Provider/search credentials stay in private config. Existing image/audio/model
permissions remain database state; kit-owned provider/terminal/MCP/search connections
are reconciled at startup.

Copy each approved user's workspace and backend config into `terminal/users/<hash>`.
Rewrite `terminal/private/users.json` paths for container `/data`; retain user IDs and
distinct backend keys. Runtime registrations are independent of the old runtime. Preserve
revoked users' retained files privately; do not activate them or mount the old live runtime.

## Optional local speech

The repo includes `guest/speech_server.py`, an opt-in Piper endpoint inside the WebUI VM.
With `local_speech=true`, it uses external `webui/data/deps/speech`,
`models/piper/en_US-lessac-medium.onnx` and its JSON config. Preserve/install the matching
dependencies and model/voice license notices; Whisper assets can remain in
`webui/data/models/faster-whisper-base`. Keep the speech key in private
`webui/config/speech-api-key` and matching native WebUI audio settings.
These optional assets are not downloaded automatically; record pinned public URLs/checksums
alongside the external assets for reproduction.

## Cutover and rollback

Test the copied instance privately: accounts/chats/file links, user separation, gateway,
browser, widgets, Craft, search, voice and memory. Prevent duplicate scheduled runs by
pausing automations in staging only. Stop the old writer, take a final consistent copy,
switch existing ingress to the verified instance, and verify externally. Keep the old
deployment stopped with backups/data intact. For rollback, stop the new writer before
restoring old ingress/runtime; never silently discard new conversations or file edits.
