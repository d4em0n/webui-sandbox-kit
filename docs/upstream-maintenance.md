# Upstream sources and patches

The integration repository owns adapters and configuration, not full forks of every app.

- **Open WebUI / Open Terminal:** official OCI image digests in `versions.lock.json`.
  No application core patch is required. The optional [document viewer](document-preview.md)
  fetches checksum-pinned WebUI source at build time to compile its existing preview
  components into a separate adapter page; the official images remain unchanged. Our controller/guest adapters
  are source files with tests, included automatically in the built image.
- **Frontier UI:** original `frontier/frontier_ui.py` is a vendored snapshot of the locked
  revision, with its license. The separate MCP Apps adapter reuses its renderer; build
  assertions reject unexpected extraction anchors. Keep the original module independent.
  Users do not need a separate development checkout to build/install this kit.
- **Conduit:** separate client/fork, with its own commits and issue/PR lifecycle. Link that
  work; do not copy mobile source or assume a server update upgrades the client.

There is no `patches/` directory because the kit applies no upstream core patches. Saving
a second diff of our adapter files would duplicate the source of truth. The
[ledger](customizations.md), Git commits and regression tests retain our corrections.

If an upstream code patch becomes unavoidable, commit a version-specific patch with its
exact upstream revision/image base, checksum, owning issue, upstream PR, test and removal
condition. Apply it deterministically in the build, failing on unexpected input. Avoid
fuzzy patching or an unpinned branch. Record the derived image identity and retain licenses.
Rebase/re-test against new pins; remove only after the upstream replacement is verified.
Use a maintained fork when sustained changes outgrow a small patch series.

Update digests/checksums deliberately, review release/API changes, build from a clean checkout,
run regression and isolated integration checks, and record client/platform coverage before
promoting a release. Follow [issue tracking](../CONTRIBUTING.md) for cross-repository links.
