import tempfile
import unittest
from pathlib import Path

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from controller.document_preview import document_preview_routes


class DocumentPreviewTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.assets = self.root / "viewer"
        self.assets.mkdir()
        (self.assets / "index.html").write_text("<title>Open WebUI</title><script>window.viewer = true;</script>")
        (self.assets / "viewer.js").write_text("// viewer")
        (self.root / "private.json").write_text("private")
        (self.assets / "escape.json").symlink_to(self.root / "private.json")
        app = web.Application()
        app.add_routes(document_preview_routes(self.assets))

        async def ordinary_api(request):
            return web.json_response({"authorization": request.headers.get("Authorization"),
                                      "cookie": request.headers.get("Cookie")})
        app.router.add_route("*", "/{path:.*}", ordinary_api)
        self.client = TestClient(TestServer(app))
        await self.client.start_server()

    async def asyncTearDown(self):
        await self.client.close()
        self.temp.cleanup()

    async def test_shell_and_assets_never_embed_credentials_or_allow_external_resources(self):
        for path in ("/document-preview", "/document-preview/", "/document-preview/viewer.js"):
            response = await self.client.get(path, headers={"Authorization": "Bearer synthetic"})
            self.assertEqual(response.status, 200)
            self.assertNotIn("synthetic", await response.text())
            self.assertEqual(response.headers["Cache-Control"], "no-store")
            self.assertEqual(response.headers["Referrer-Policy"], "no-referrer")
            csp = response.headers["Content-Security-Policy"]
            self.assertIn("connect-src 'self'", csp)
            if path != "/document-preview/viewer.js":
                import base64, hashlib
                digest = base64.b64encode(hashlib.sha256(b"window.viewer = true;").digest()).decode()
                self.assertIn("'sha256-" + digest + "'", csp)
            self.assertIn("frame-src 'none'", csp)
            self.assertIn("frame-ancestors 'none'", csp)
            self.assertNotIn("unsafe-eval", csp.replace("wasm-unsafe-eval", ""))

    async def test_missing_assets_and_links_outside_dist_cannot_be_served(self):
        for path in ("missing.js", "escape.json", "%2e%2e%2fprivate.json"):
            response = await self.client.get("/document-preview/" + path)
            self.assertEqual(response.status, 404)

    async def test_normal_file_api_still_uses_original_authenticated_relay(self):
        response = await self.client.get("/api/v1/files/demo/content", headers={
            "Authorization": "Bearer synthetic", "Cookie": "token=synthetic-cookie"})
        self.assertEqual(await response.json(), {
            "authorization": "Bearer synthetic", "cookie": "token=synthetic-cookie"})
