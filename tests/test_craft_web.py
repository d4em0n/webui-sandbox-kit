import base64
import hashlib
from pathlib import Path
import tempfile
import unittest

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from controller.craft_web import craft_web_routes


class CraftWebTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.editor = root / "editor"
        self.apps = root / "apps"
        self.editor.mkdir()
        app = self.apps / "wordcraft/0.18.1"
        app.mkdir(parents=True)
        (self.editor / "index.html").write_text('<script src="/document-editor/editor.js"></script>')
        (self.editor / "editor.js").write_text('// public host only')
        (self.apps / "apps.json").write_text('{"wordcraft":"/craft/wordcraft/0.18.1/index.html"}')
        (app / "index.html").write_text('<script type="module">window.craft = true;</script>')
        (app / "engine.wasm").write_bytes(b'public wasm')
        (root / "private").write_text('secret')
        (app / "escape").symlink_to(root / "private")
        (app / ".hidden").write_text('hidden')
        server = web.Application()
        server.add_routes(craft_web_routes(self.editor, self.apps))
        self.client = TestClient(TestServer(server))
        await self.client.start_server()

    async def asyncTearDown(self):
        await self.client.close()
        self.temporary.cleanup()

    async def test_host_contains_no_credentials_and_cannot_load_remote_scripts_or_frames(self):
        for path in ('/document-editor', '/document-editor/', '/document-editor/editor.js', '/document-editor/apps.json'):
            response = await self.client.get(path, headers={'Authorization': 'Bearer synthetic-private'})
            self.assertEqual(response.status, 200)
            self.assertNotIn('synthetic-private', await response.text())
            self.assertEqual(response.headers['Cache-Control'], 'no-store')
            csp = response.headers['Content-Security-Policy']
            self.assertIn("frame-src 'self'", csp)
            self.assertIn("frame-ancestors 'none'", csp)
            self.assertNotIn('unsafe-inline', csp)

    async def test_pinned_engine_caches_and_only_trusted_loader_script_hash_is_allowed(self):
        response = await self.client.get('/craft/wordcraft/0.18.1/index.html')
        self.assertEqual(response.status, 200)
        digest = base64.b64encode(hashlib.sha256(b'window.craft = true;').digest()).decode()
        self.assertIn("'sha256-" + digest + "'", response.headers['Content-Security-Policy'])
        self.assertIn("frame-ancestors 'self'", response.headers['Content-Security-Policy'])
        self.assertIn('immutable', response.headers['Cache-Control'])
        response = await self.client.get('/craft/wordcraft/0.18.1/engine.wasm')
        self.assertEqual(await response.read(), b'public wasm')
        self.assertEqual(response.headers['Content-Type'], 'application/wasm')

    async def test_static_routes_cannot_serve_outside_assets_or_hidden_files(self):
        for path in ('/craft/wordcraft/0.18.1/escape', '/craft/wordcraft/0.18.1/.hidden',
                     '/craft/%2e%2e%2fprivate', '/document-editor/%2e%2e%2fprivate'):
            response = await self.client.get(path)
            self.assertEqual(response.status, 404)
