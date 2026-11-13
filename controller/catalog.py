"""Container-restart compatibility for the pinned Microsandbox 0.7.15 catalogue.

Numeric PIDs in a persisted catalogue belong to the old Docker PID namespace.
They can name an unrelated new VM after recreation. Repair only this installation's
latest run records, before any runtime starts, under the exclusive controller lock.
VM disks, configuration, image cache and application files are untouched.
"""
import fcntl
import os
from pathlib import Path
import sqlite3


def repair_catalog(home):
    database = home / "db/msb.db"
    if not database.exists():
        return
    with sqlite3.connect(database, timeout=15) as connection:
        columns = {row[1] for row in connection.execute('PRAGMA table_info("run")')}
        if not {"id", "sandbox_id", "pid", "status"} <= columns:
            raise RuntimeError("Unsupported Microsandbox catalogue schema; refusing PID repair")
        connection.execute('UPDATE "run" SET pid=NULL, status=CASE WHEN status=\'Running\' THEN \'Terminated\' ELSE status END '
                           'WHERE id IN (SELECT MAX(id) FROM "run" GROUP BY sandbox_id)')
        connection.execute("UPDATE sandbox SET status='Crashed', active_config=NULL WHERE status='Running'")


def own_home(home):
    if not Path("/.dockerenv").exists():
        raise RuntimeError("The controller must run inside its dedicated Docker container")
    home.mkdir(parents=True, exist_ok=True, mode=0o700)
    lease = (home / "controller.lock").open("a+b")
    try:
        fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for path in Path("/proc").glob("[0-9]*/cmdline"):
            try:
                args = path.read_bytes().split(b"\0")
            except (FileNotFoundError, ProcessLookupError):
                continue
            if len(args) > 1 and Path(os.fsdecode(args[0])).name == "msb" and args[1] == b"machine":
                raise RuntimeError("A runtime already exists in this PID namespace; refusing catalogue repair")
        repair_catalog(home)
    except BaseException:
        lease.close()
        raise
    return lease
