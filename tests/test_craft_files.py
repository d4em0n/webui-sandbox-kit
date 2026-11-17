import base64
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

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
