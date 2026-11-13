import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import asynccontextmanager
from types import SimpleNamespace

from aiohttp import ServerDisconnectedError
from controller.runtime import WebUI
from controller.terminal import Manager
from controller.catalog import repair_catalog

from controller.bootstrap import prepare
from controller.settings import load_settings

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("backup", ROOT / "scripts/backup.py")
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)


class ConfigurationTests(unittest.TestCase):
    def test_two_installations_have_distinct_secrets_and_no_copied_accounts(self):
        with tempfile.TemporaryDirectory() as directory:
            a, b = Path(directory) / "one", Path(directory) / "two"
            prepare(a)
            prepare(b)
            first = (a / "config/webui-secret").read_text()
            self.assertNotEqual(first, (b / "config/webui-secret").read_text())
            (a / "webui/config/frontier.json").write_text('{"units":"imperial"}')
            prepare(a)
            self.assertEqual(first, (a / "config/webui-secret").read_text())
            self.assertFalse((a / "webui/data/webui.db").exists())
            self.assertEqual(a.stat().st_mode & 0o777, 0o700)
            self.assertEqual(json.loads((a / "webui/config/frontier.json").read_text())["units"], "imperial")

    def test_user_supplied_credentials_never_enter_workspace_templates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config").mkdir()
            (root / "config/provider-key").write_text("synthetic-private-provider-token")
            prepare(root)
            environment = json.loads((root / "webui/config/environment.json").read_text())
            self.assertEqual(environment["OPENAI_API_KEYS"], "synthetic-private-provider-token")
            self.assertNotIn("synthetic-private-provider-token", (root / "terminal/ops/workspace-guidelines.md").read_text())
            self.assertEqual((root / "webui/config/environment.json").stat().st_mode & 0o777, 0o600)

    def test_rejects_embedded_url_credentials_unknown_settings_and_invalid_limits(self):
        for change in [{"provider_url": "https://user:password@example.com/v1"}, {"dns": "operator-specific"},
                       {"user_cpus": 0}, {"max_users": True}, {"firecrawl": "yes"}]:
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "config").mkdir()
                (root / "config/settings.json").write_text(json.dumps(change))
                with self.assertRaises(ValueError):
                    load_settings(root)

    def test_default_configuration_contains_no_homeserver_dependencies(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = load_settings(Path(directory))
            text = json.dumps(settings)
            for forbidden in ["localup", "tailscale", "192.168.", "/mnt/data", "/home/"]:
                self.assertNotIn(forbidden, text)
            self.assertFalse(settings["provider_allow_private"])
            self.assertLessEqual(settings["webui_memory_mib"] + settings["user_memory_mib"] * settings["max_users"], 8192)


class BackupTests(unittest.TestCase):
    def test_hardlinks_and_absolute_workspace_symlinks_round_trip_safely(self):
        import os
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output, target = root / "source", root / "archives", root / "target"
            for path in [source, output, target]:
                path.mkdir()
            (source / "file").write_text("owned data")
            os.link(source / "file", source / "hardlink")
            (source / "python").symlink_to("/usr/bin/python3")
            backup.create(source, output, os.getuid(), os.getgid())
            archive = next(output.glob("*.tar.gz"))
            backup.restore(archive, target)
            self.assertEqual((target / "hardlink").read_text(), "owned data")
            self.assertEqual(os.readlink(target / "python"), "/usr/bin/python3")

    def test_round_trip_keeps_secrets_and_user_data_without_runtime_or_recursive_backups(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output, restored = root / "data", root / "archives", root / "restored"
            for path in [source / "controller/config", source / "controller/runtime", source / "backups", output, restored]:
                path.mkdir(parents=True)
            secret = source / "controller/config/key"
            secret.write_text("synthetic-secret")
            secret.chmod(0o600)
            (source / "controller/runtime/image").write_text("disposable")
            (source / "backups/previous.tar.gz").write_text("not included")
            backup.create(source, output, __import__("os").getuid(), __import__("os").getgid())
            archive = next(output.glob("*.tar.gz"))
            manifest = backup.verify(archive)
            self.assertEqual(set(manifest["files"]), {"controller/config/key"})
            backup.restore(archive, restored)
            self.assertEqual((restored / "controller/config/key").read_text(), "synthetic-secret")
            self.assertEqual((restored / "controller/config/key").stat().st_mode & 0o777, 0o600)
            with archive.open("ab") as stream:
                stream.write(b"corrupted")
            with self.assertRaises(ValueError):
                backup.verify(archive)


class HealthTests(unittest.IsolatedAsyncioTestCase):
    async def test_forwarded_port_without_ready_guest_does_not_abort_startup(self):
        @asynccontextmanager
        async def disconnected(*args, **kwargs):
            raise ServerDisconnectedError()
            yield

        manager = SimpleNamespace(client=SimpleNamespace(get=disconnected))
        runtime = WebUI(manager, {})
        self.assertFalse(await runtime.healthy())
        self.assertFalse(await Manager.healthy(manager, {"port": 18801}))


class CatalogueTests(unittest.TestCase):
    def test_pid_namespace_repair_keeps_disks_and_historical_records(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            (home / "db").mkdir()
            (home / "disk").write_bytes(b"persistent-overlay")
            with sqlite3.connect(home / "db/msb.db") as connection:
                connection.executescript('CREATE TABLE sandbox (id INTEGER, status TEXT, active_config TEXT); '
                    'CREATE TABLE run (id INTEGER, sandbox_id INTEGER, pid INTEGER, status TEXT); '
                    "INSERT INTO sandbox VALUES (1,'Running','{}'); "
                    "INSERT INTO run VALUES (1,1,50,'Terminated'); INSERT INTO run VALUES (2,1,177,'Running');")
            repair_catalog(home)
            with sqlite3.connect(home / "db/msb.db") as connection:
                self.assertEqual(connection.execute('SELECT pid,status FROM run WHERE id=2').fetchone(), (None, 'Terminated'))
                self.assertEqual(connection.execute('SELECT pid FROM run WHERE id=1').fetchone(), (50,))
                self.assertEqual(connection.execute('SELECT status FROM sandbox').fetchone(), ('Crashed',))
            self.assertEqual((home / "disk").read_bytes(), b"persistent-overlay")

    def test_unknown_catalogue_schema_fails_before_mutating(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            (home / "db").mkdir()
            with sqlite3.connect(home / "db/msb.db") as connection:
                connection.execute('CREATE TABLE run (id INTEGER)')
            with self.assertRaises(RuntimeError):
                repair_catalog(home)

    def test_rejects_traversal_even_with_a_matching_archive_digest(self):
        import hashlib
        import tarfile
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "unsafe.tar.gz"
            with tarfile.open(archive, "w:gz") as output:
                member = tarfile.TarInfo("../escape")
                member.size = 1
                output.addfile(member, io.BytesIO(b"x"))
            Path(str(archive) + ".json").write_text(json.dumps({"format": 1, "files": {"../escape": hashlib.sha256(b"x").hexdigest()},
                "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest()}))
            with self.assertRaises(ValueError):
                backup.verify(archive)


if __name__ == "__main__":
    unittest.main()
