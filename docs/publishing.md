# Publishing this repository

Publish source/templates and `versions.lock.json`, not a configured installation. `.gitignore`
and `.dockerignore` exclude `.env`, data, caches, reports, virtual environments and archives.
Review `git status` and run the tests before adding files. Never copy a production database,
VM catalogue, `.env`, provider key or account/workspace directory into the repository.

Create your own GitHub repository and add its URL as the remote. This working tree does not
create or publish an external repository automatically. Replace the README clone placeholder
with the final URL when you publish. Preserve `LICENSE`, `licenses/` and third-party notices.

Open WebUI retains its own license and branding rules; this kit does not rename/rebrand its
UI or imply upstream endorsement. Open Terminal and Frontier retain their MIT notices.
Craft runtime downloads carry their upstream license/font notices in the controller image.
Firecrawl and other downloaded images retain their own licenses. The integration's MIT
license does not relicense any upstream binary/image or the vendored Frontier code.

GitHub CI runs unit/security checks. KVM integration requires an isolated Linux machine;
do not run untrusted pull-request code on a personal self-hosted runner. This repository
does not use the separate Enterprise Terminals orchestrator or its APIs.
