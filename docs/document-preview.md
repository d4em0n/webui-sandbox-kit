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
Reopening reads current bytes; it does not preserve edits or interactive state.

The adapter selects PDF.js's supplied legacy build for WebViews without newer
TypedArray methods. Its small PDF pan/zoom adapter lets single-finger swipes at
1x scroll multipage documents; pinch and zoomed panning remain upstream behavior.
These compatibility changes do not alter the official application images.

The static shell contains no document data. Its CSP restricts resources to the
configured origin and embedded data/blobs. Documents cannot become arbitrary
HTML pages. The compatible Conduit experiment loads the viewer on a tap and
retains its native preview when `/document-preview/config.json` is unavailable.
Server installation alone does not update the mobile client.
