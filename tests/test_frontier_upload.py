import importlib.util
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
