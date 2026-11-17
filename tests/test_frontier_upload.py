import importlib.util
import base64
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from aiohttp import web
from aiohttp.test_utils import TestServer

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("frontier_openwebui", ROOT / "frontier/mcp-apps/openwebui.py")
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


class FrontierUploadTests(unittest.IsolatedAsyncioTestCase):
    async def test_file_operation_keeps_exact_workspace_path_and_defers_upload_until_display(self):
        uploads = []

        async def craft(request):
            self.assertEqual(request.headers.get("Authorization"), "Bearer synthetic-token")
            self.assertEqual(request.headers.get("X-Controller-Key"), "synthetic-router")
            body = await request.json()
            if request.match_info["operation"] == "inspect":
                self.assertFalse(body["inbox"])
                return web.json_response({"text": "Synthetic content"})
            return web.json_response({"name": "Synthetic.xlsx", "path": "/home/user/Inbox/Synthetic (2).xlsx",
                                      "b64": base64.b64encode(b"edited").decode()})

        async def upload(request):
            uploads.append(await request.read())
            return web.json_response({"id": "synthetic-id"})

        app = web.Application()
        app.router.add_post("/craft/{operation}", craft)
        app.router.add_post("/api/v1/files/", upload)
        async with TestServer(app) as server:
            base = str(server.make_url("/")).rstrip("/")
            with patch.object(bridge, "BASE", base), patch.object(bridge, "PUBLIC", base), \
                 patch.object(bridge, "CRAFT", {"url": base + "/craft", "token": "synthetic-router"}):
                auth = bridge.authorization.set("Bearer synthetic-token")
                context = bridge.file_context.set({"defer_display": True})
                try:
                    frontier = SimpleNamespace()
                    bridge.install(frontier)
                    name, data, path = await frontier._load_file("/home/user/Inbox/Synthetic (2).xlsx", None, None, {})
                    self.assertEqual(data, b"edited")
                    self.assertEqual(bridge.file_context.get()["path"], path)
                    import aiohttp
                    async with aiohttp.ClientSession() as session:
                        await frontier._bridge_call(session, bridge.CRAFT, "/inspect", {"name": name})
                    await frontier._store_file({}, name, data, "application/octet-stream")
                    self.assertEqual(uploads, [])
                    bridge.file_context.get()["defer_display"] = False
                    fid, url = await frontier._store_file({}, name, data, "application/octet-stream")
                    self.assertEqual(fid, "synthetic-id")
                    self.assertEqual(len(uploads), 1)
                    self.assertEqual(url, base + "/api/v1/files/synthetic-id/content")
                finally:
                    bridge.file_context.reset(context)
                    bridge.authorization.reset(auth)

    async def test_uploaded_filename_preserves_spaces_unicode_and_literal_percent(self):
        received = []

        async def upload(request):
            self.assertEqual(request.headers.get("Authorization"), "Bearer synthetic-token")
            part = await (await request.multipart()).next()
            received.append((part.filename, await part.read()))
            return web.json_response({"id": "synthetic-id"})

        app = web.Application()
        app.router.add_post("/api/v1/files/", upload)
        async with TestServer(app) as server:
            base = str(server.make_url("/")).rstrip("/")
            with patch.object(bridge, "BASE", base), patch.object(bridge, "PUBLIC", base):
                token = bridge.authorization.set("Bearer synthetic-token")
                try:
                    frontier = SimpleNamespace()
                    bridge.install(frontier)
                    names = ['Weekend plan.docx', 'Résumé "draft".docx', 'Literal%20name.docx']
                    for name in names:
                        await frontier._store_file({}, name, b"Synthetic bytes", "application/octet-stream")
                    self.assertEqual(received, [(name, b"Synthetic bytes") for name in names])
                finally:
                    bridge.authorization.reset(token)
