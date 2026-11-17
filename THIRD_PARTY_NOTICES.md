# Third-party components

The root MIT license covers this kit's original integration code, not upstream applications.

- **Open WebUI**: official OCI image, version/digest pinned in `versions.lock.json`.
  [Repository](https://github.com/open-webui/open-webui), license copied under `licenses/`.
  Original branding remains visible. No endorsement or official affiliation is implied.
- **Open Terminal**: official OCI image and generated public discovery schema (0.17.7);
  snapshot descriptions omit build-host details. MIT notice under `licenses/`.
  The external router originated in the independent Open Terminal provisioner and preserves
  its upstream notice. [Repository](https://github.com/open-webui/open-terminal).
- **Frontier UI**: unchanged `frontier/frontier_ui.py` and reused file-conversion helpers,
  revision `74ef48595ff685a2f84893f9c4c5d9e15b075cc4` of
  [Jumbomuffin777/Frontier-UI](https://github.com/Jumbomuffin777/Frontier-UI).
  MIT notice under `licenses/`; MCP adapter is independent integration code.
- **Microsandbox/libkrun/libkrunfw**: checksum-pinned release binaries; upstream licenses
  apply. [Microsandbox](https://github.com/superradcompany/microsandbox),
  [libkrun](https://github.com/containers/libkrun), [libkrunfw](https://github.com/containers/libkrunfw).
  Microsandbox's Apache-2.0 notice is copied under `licenses/`.
- **WordCraft / PdfCraft / DeckCraft**: checksum-pinned official releases from
  [storytold](https://github.com/storytold). Their release license/NOTICE/font notices are
  retained alongside the binaries in `/opt/craft/<app>/licenses` in the controller image.
  Headless CLI engines and pinned WordCraft/DeckCraft/GridCraft web builds are packaged;
  full desktop applications are not bundled. Unmodified web distributions, including their
  licenses and font notices, are served under `/craft/<app>/<version>/`.
- **MCP Apps SDK**: official `@modelcontextprotocol/ext-apps` 2.1.0, bundled using the lockfile;
  [repository and license](https://github.com/modelcontextprotocol/ext-apps).
  Python MCP SDK runs from the pinned official WebUI image.
- **Firecrawl**: pinned official images. [Repository/license](https://github.com/firecrawl/firecrawl).
  Redis, RabbitMQ, PostgreSQL/NUQ and their images retain their own licenses/notices.
  This kit does not alter or relicense those binaries or expose their management ports.
- Docker base images, Python/npm packages, fonts and their transitive dependencies retain
  their upstream licenses. OCI images contain their own package-level notices.

Review upstream license changes when updating pins. Publishing this source repository does
not transfer model-provider credentials, accounts or licenses, or grant a model subscription.

## Document preview

The adapter page compiles unmodified preview components from Open WebUI at the
revision/checksum in `versions.lock.json`, with its locked dependencies. Official
WebUI/Terminal images remain unchanged. The built viewer includes Open WebUI
LICENSE/LICENSE_HISTORY and dependency notices under `/document-preview/licenses/`.
