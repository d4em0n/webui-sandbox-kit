import base64
import json
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch
from types import SimpleNamespace

from controller.craft import Craft

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("frontier_craft_bridge", ROOT / "guest/frontier_craft_bridge.py")
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)
with patch.dict(sys.modules, {"frontier_craft_bridge": bridge}):
    spec = importlib.util.spec_from_file_location("craft_job", ROOT / "guest/craft_job.py")
    job = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(job)


class WorkspaceFileTests(unittest.TestCase):
    def test_file_reads_latest_bytes_and_rejects_outside_paths_directories_and_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / "home"
            home.mkdir()
            file = home / "Weekend plan.xlsx"
            file.write_bytes(b"original")
            outside = Path(directory) / "other-account.xlsx"
            outside.write_bytes(b"private")
            (home / "escape").symlink_to(outside)
            with patch.object(bridge, "HOME", str(home)):
                first = job.main("file", {"path": str(file)})
                file.write_bytes(b"edited chart")
                latest = job.main("file", {"path": str(file)})
                self.assertEqual(base64.b64decode(first["b64"]), b"original")
                self.assertEqual(base64.b64decode(latest["b64"]), b"edited chart")
                self.assertEqual(latest["path"], str(file))
                for path in (str(outside), str(home / "escape"), str(home), "Weekend plan.xlsx"):
                    with self.subTest(path=path), self.assertRaises(ValueError):
                        job.main("file", {"path": path})
                with self.assertRaises(FileNotFoundError):
                    job.main("file", {"path": str(home / "missing")})
                with file.open("wb") as stream:
                    stream.truncate(10 * 1024 * 1024 + 1)
                metadata = job.main("file", {"path": str(file), "metadata_only": True})
                self.assertEqual(metadata, {"path": str(file), "name": file.name, "size": 10 * 1024 * 1024 + 1})
                for invalid in (outside, home / "escape", home):
                    with self.assertRaises(ValueError):
                        job.main("file", {"path": str(invalid), "metadata_only": True})
                with self.assertRaisesRegex(ValueError, "10 MiB"):
                    job.main("file", {"path": str(file)})

    def test_read_edit_convert_return_exact_unique_saved_paths_without_overwriting(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(bridge, "INBOX", directory):
            original = Path(directory) / "Synthetic.docx"
            original.write_bytes(b"old")
            body = {"name": "Synthetic.docx", "b64": base64.b64encode(b"new").decode(), "inbox": True}
            for operation, method in (("inspect", "inspect_file"), ("edit", "edit_file"), ("convert", "convert_file")):
                with patch.object(bridge, method, return_value={**body, "text": "Synthetic content"}):
                    result = job.main(operation, body)
                saved = Path(result["path"])
                self.assertNotEqual(saved, original)
                self.assertEqual(saved.read_bytes(), b"new")
                self.assertEqual(original.read_bytes(), b"old")
            with patch.object(bridge, "inspect_file", return_value={"text": "Preview"}):
                self.assertNotIn("path", job.main("inspect", {**body, "inbox": False}))


class WorkspaceLinkTests(unittest.IsolatedAsyncioTestCase):
    async def test_display_connection_comes_from_configuration_after_account_routing(self):
        manager = SimpleNamespace(config={"terminal_id": "configured-workspace"},
                                  ensure=AsyncMock(return_value={"vm": "owning-account-vm"}))
        craft = Craft(manager, "http://webui.invalid")
        process = SimpleNamespace(returncode=0, communicate=AsyncMock(return_value=(
            json.dumps({"path": "/home/user/chart.xlsx", "name": "chart.xlsx", "size": 123}).encode(), b"")))
        with patch("controller.craft.asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=process) as spawn:
            response = await craft.file_operation("authenticated-account", "file", {
                "path": "/home/user/chart.xlsx", "metadata_only": True, "terminal_id": "forged-connection"})
        manager.ensure.assert_awaited_once_with("authenticated-account")
        self.assertIn("owning-account-vm", spawn.await_args.args)
        result = json.loads(response.body)
        self.assertEqual(result["terminal_id"], "configured-workspace")
        self.assertNotIn("b64", result)
