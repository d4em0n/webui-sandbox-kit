# My self-hosted assistant setup

This kit grew out of a personal Linux homeserver setup: Open WebUI in a Microsandbox
microVM, persistent per-user Open Terminal/browser workspaces, Frontier interactive widgets,
Firecrawl and headless document engines. It is a reusable reference for a ChatGPT-style
experience with an operator's own model gateway, rather than a promise of feature parity.

The reference deployment starts at `http://localhost:3000`. Add your own reverse proxy,
domain or private VPN if needed; none of the author's DNS, accounts or provider credentials
are required or distributed. Keep personal preferences in the external instance configuration.
The kit's integration source is the reusable layer, similar to sharing dotfiles plus an installer.

## Browser and native iOS

The author uses **Conduit on iOS** with Open WebUI, alongside the web interface.
[Conduit](https://github.com/cogwheel0/conduit) is a separate client; configure it with your
own WebUI URL and account. It is not bundled into the server or required to use the kit.

The author's [Conduit fork](https://github.com/d4em0n/conduit) also contains ongoing MCP
widget and native document-handoff work. Changes to a fork do not imply inclusion in the
App Store release. Check the exact client build and upstream PR status before relying on
a feature. Install/sign mobile builds through their own documented process.

Web and native clients can differ: Frontier host permissions govern widget follow-up
actions/downloads; reviewed Conduit versions lack inline Office-to-PDF preview. Export an
actual PDF for preview, or use Open with in a build that supports native handoff. Preserve
the original PPTX/DOCX for editing. [Client limits](limitations.md) and the
[customization ledger](customizations.md) distinguish shipped behavior from plans.

## What this reference has verified

See [the verification record](../VERIFICATION.md) for tests of the packaged stack. Personal
iPhone use is an operator report, not a physical-device acceptance test of this kit.
Record the model/provider and exact client/server versions in bug reports; some failures,
including provider request-size limits, are independent of the server's available CPU/RAM.
