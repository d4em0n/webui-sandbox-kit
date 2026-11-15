# Changes and issue tracking

Use this repository's issue as the main record for a problem affecting this integration.
Include the kit commit, pinned versions, host/KVM environment, client/build, model/provider,
expected behavior and a minimal synthetic reproducer. Never include production databases,
workspace files, bearer tokens, browser tickets, provider keys or private instance settings.

Before assigning blame, locate the failure: kit controller, native app, model provider,
Frontier adapter or upstream application. Record uncertain ownership honestly. A known
client limitation or a fix to our own adapter is not automatically an upstream defect.

If reproducible against upstream without the kit, search for an existing issue first.
Create or comment on an appropriate upstream issue only after the operator authorizes
external posting and after following that project's contribution rules. Link the upstream
report from the kit issue and link back to the kit reproducer where useful. Keep the public
report self-contained, factual and synthetic; do not send readers to private server evidence.

For a fix, update the issue with diagnosis, a regression case, local commit/PR and validation
scope. Add or update its stable entry in [the customization ledger](docs/customizations.md).
Use Git commits for adapter source and configuration templates. Retain official core images
unless an explicitly reviewed patch is necessary; then record the base, application step,
test and upstream replacement/removal condition. Avoid an untracked production hotfix.

Run unit/security checks and relevant integration checks as described in
[testing](docs/testing.md). Re-test only isolated instances with synthetic accounts. Note
untested physical devices or clean hosts explicitly. Close the kit issue with the shipped
release/commit and upstream status; remove workarounds only after a pinned update is verified.

Publishing a kit repository, issue, comment or upstream PR is a separate external action;
preparing these templates does not perform it. See [publishing](docs/publishing.md).
