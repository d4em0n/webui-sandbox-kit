# Optional document viewer

The controller serves `/document-preview/` alongside the normal WebUI proxy. It is
an additional page, not a replacement WebUI/Terminal image or a Craft editor. The
build imports unmodified WebUI preview components from the source revision and
checksum in `versions.lock.json`, using that revision's npm lockfile. Preserve its
branding and the notices shipped at `/document-preview/licenses/`.

The page accepts either `file_id`, or `terminal_id` plus `path` and optional
`chat_id`; `page` selects a document page. These identify resources, not authority.
All content requests still use WebUI's existing authenticated Files/Terminal APIs,
including connection permissions and per-user workspace routing. It accepts no
remote resource URL, backend key or caller-selected user ID. Browser login is the
normal same-origin WebUI session; credentials must never appear in viewer URLs.

PDF, DOCX, PPTX, XLSX and XLS use the same components and limitations as the pinned
WebUI preview. Terminal Word/PowerPoint first request the existing PDF conversion,
with WebUI's browser fallback if conversion is unavailable. Spreadsheet styles,
merged cells and tabs are supported; this does not add Excel chart fidelity.
Reopening or pressing **Refresh** reads current bytes; it does not preserve edits
or interactive state. An open preview does not poll for workspace changes.

Frontier file cards include **Open preview** beside **Download** for supported
documents. Existing uploaded-file cards use their WebUI file ID; workspace cards
use the configured Terminal connection and resolved file path. Normal browser login
and Files/Terminal permissions still apply. Existing
thumbnails and downloads remain available. MCP hosts handle the standard open-link
request; an authenticated in-app browser depends on the mobile client's support.

File work and delivery are separate: `frontier_craft_file`, `frontier_craft_read`,
`frontier_craft_edit` and `frontier_craft_convert` return metadata and an exact saved
workspace path without a card or a WebUI upload. Existing uploads can be referenced
by owned file ID/name; workspace files use absolute `/home/user/...` paths. Use the
returned path directly for further Python/shell edits, then call
`frontier_craft_display(path=...)` once to deliver the finished file. That tool
checks the file in the caller's workspace and returns the existing file card with
authenticated Terminal download/preview links, without uploading a copy to WebUI.
It never edits/converts the file. Reopen or refresh to see later workspace changes;
moving/deleting the source breaks the old link. The viewer retains its 32 MiB fetch
limit; workspace reads for editing retain the 10 MiB bridge limit.
The widget Export action performs the same create-then-display sequence.

The adapter selects PDF.js's supplied legacy build for WebViews without newer
TypedArray methods. Its small PDF pan/zoom adapter lets single-finger swipes at
1x scroll multipage documents; pinch and zoomed panning remain upstream behavior.
These compatibility changes do not alter the official application images.

The static shell contains no document data. Its CSP restricts resources to the
configured origin and embedded data/blobs. Documents cannot become arbitrary
HTML pages. The compatible Conduit experiment loads the viewer on a tap and
retains its native preview when `/document-preview/config.json` is unavailable.
Server installation alone does not update the mobile client.

## Optional Craft editing

Workspace DOCX, PPTX and XLSX previews have **Edit in Craft**. It opens a separate
server-hosted page using the current authenticated Terminal connection/path. The
pinned WordCraft, DeckCraft or GridCraft web app receives document bytes through
its existing same-origin host bridge. This does not change Conduit navigation or
the default lightweight preview, and does not install the GridCraft CLI.

**Save** writes the original filename/directory through the normal Terminal upload
API and shows **Saved** only after a successful server response. It overwrites the
current file without conflict checks. **Refresh** passes current Terminal bytes to the running editor
and discards unsaved editor changes without restarting its WASM engine. Save As and exports do not overwrite the
opened file; this initial host rejects them. Reads/saves are bounded at 32 MiB.
No automatic retry, background saving or collaboration mechanism is added.

Only same-origin messages from the selected editor frame are accepted; the host
retains the opened filename and uses the current account session. CSP for the
existing preview is unchanged. The separate editor allows its packaged app frame;
app scripts/WASM/fonts/notices are pinned with checksums, compressed and cached at
versioned paths. Private document requests remain authenticated and uncached.
