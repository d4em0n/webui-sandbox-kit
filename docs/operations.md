# Operations

Use `./kit status`, `./kit logs` and `./kit logs firecrawl-api`. WebUI logs are under
`DATA_DIR/controller/logs/`; per-user logs are under their hashed terminal directories.
Compose logs rotate at 10 MiB with three retained files. Treat diagnostic output as private.

Compose `restart: unless-stopped` restarts the controller/sidecars after crashes or host
reboot when Docker starts. The controller restarts unhealthy WebUI and approved registered
user VMs. First use is serialized per user, with two simultaneous boots; slow first image
downloads may exceed a client timeout, in which case retry after startup.

`./kit stop` stops only this installation. `./kit down` removes only its Compose resources,
retaining all external state. Do not run broad Docker pruning as an update mechanism.

## Backup

`./kit backup` stops configured running services, creates a compressed archive with a
per-file SHA-256 manifest, verifies it, then restarts the previously running services.
Archives are private and contain credentials, accounts and user data. The companion `.json`
manifest must travel with its archive. Use `./kit verify-backup ARCHIVE` after copying.

Runtime OCI caches, VM root overlays, logs and previous backups are excluded. Restore
recreates managed VMs from pinned images and external application/workspace data. This
preserves chats/accounts/files/browser profiles, but not unsaved documents or packages
installed only into a VM root overlay.

## Restore onto another machine

```sh
./kit init --data-dir /srv/restored-assistant --port 3300 --project restored-assistant
./kit restore /safe/path/webui-sandbox-kit-TIMESTAMP.tar.gz
./kit init --public-url http://localhost:3300
./kit up
```

Use a new empty application-data directory. The restore command refuses to overwrite
an existing WebUI data directory/PostgreSQL cluster. It verifies hashes and rejects escaping
archive paths; controller-owned data is remapped to the new host UID/GID while database
ownership is preserved. Existing account passwords and secrets come from the backup.

## Upgrade

Review changes to `versions.lock.json`, notices and tests, then run `./kit update`.
The command backs up first and rebuilds the pinned checkout; it does not fetch arbitrary
latest versions. WebUI's managed VM is recreated when its image/resources/network policy
change. User VMs use the new image on next managed boot; their workspace and credential
mounts remain. Roll back using a matching code revision and a verified backup, rather
than attempting to run an older application against a migrated database blindly.

Manual resource resizing of existing user VMs is not yet a public CLI command. New user
VMs read `user_cpus`/`user_memory_mib`; existing VMs retain their allocation.
