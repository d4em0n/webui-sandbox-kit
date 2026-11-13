import asyncio
import importlib.machinery
import importlib.util
import ipaddress
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch
import uuid

from aiohttp import ClientSession, web
from aiohttp.test_utils import TestServer, make_mocked_request

from controller.craft import Craft

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader("kit_cli", str(ROOT / "kit"))
spec = importlib.util.spec_from_loader(loader.name, loader)
cli = importlib.util.module_from_spec(spec)
loader.exec_module(cli)


class InitializationTests(unittest.TestCase):
    def test_unrelated_directory_is_never_chmodded_or_written(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            checkout, existing = root / "checkout", root / "other-service"
            checkout.mkdir()
            existing.mkdir(mode=0o755)
            (existing / "database").write_bytes(b"untouched")
            before = existing.stat().st_mode
            with patch.object(cli, "ROOT", checkout), self.assertRaisesRegex(SystemExit, "not empty"):
                cli.initialize(SimpleNamespace(data_dir=str(existing)))
            self.assertEqual(existing.stat().st_mode, before)
            self.assertEqual(list(existing.iterdir()), [existing / "database"])
            self.assertEqual((existing / "database").read_bytes(), b"untouched")

    def test_custom_data_inside_publishable_source_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(cli, "ROOT", root), self.assertRaisesRegex(SystemExit, "outside this checkout"):
                cli.initialize(SimpleNamespace(data_dir=str(root / "unignored-instance")))
            self.assertFalse((root / "unignored-instance").exists())

    def test_network_selection_excludes_docker_and_host_routes(self):
        networks = [{"IPAM": {"Config": [{"Subnet": "10.0.0.0/9"}, {"Subnet": "172.16.0.0/12"}]}}]
        routes = [{"dst": "default"}, {"dst": "10.128.0.0/10"}]
        with patch.object(cli.subprocess, "check_output", side_effect=["network-id\n", json.dumps(networks), json.dumps(routes)]):
            selected = ipaddress.ip_network(cli.available_subnet("test-installation"))
        self.assertTrue(selected.is_private)
        self.assertEqual(selected.prefixlen, 24)
        for existing in ["10.0.0.0/9", "10.128.0.0/10", "172.16.0.0/12"]:
            self.assertFalse(selected.overlaps(ipaddress.ip_network(existing)))


class CraftAuthenticationTests(unittest.IsolatedAsyncioTestCase):
    async def test_session_identity_wins_over_forged_user_header(self):
        user_id = str(uuid.uuid4())
        seen = []

        async def authenticated(request):
            seen.append(request.headers.get("Authorization"))
            self.assertEqual(request.headers.get("Accept-Encoding"), "identity")
            return web.json_response({"id": user_id})

        app = web.Application()
        app.router.add_get("/api/v1/auths/", authenticated)
        server = TestServer(app)
        await server.start_server()
        async with ClientSession(auto_decompress=False) as client:
            manager = SimpleNamespace(key="synthetic-router-key", client=client, allowed=AsyncMock(return_value=True))
            craft = Craft(manager, str(server.make_url("")).rstrip("/"))
            request = make_mocked_request("POST", "/craft/tools", headers={"X-Controller-Key": manager.key,
                "Authorization": "Bearer synthetic-session", "X-User-Id": str(uuid.uuid4())})
            self.assertEqual(await craft.authenticated_user(request), user_id)
            manager.allowed.assert_awaited_once_with(user_id)
        await server.close()
        self.assertEqual(seen, ["Bearer synthetic-session"])

    async def test_missing_controller_key_and_arbitrary_executable_are_rejected(self):
        manager = SimpleNamespace(key="synthetic-router-key", ensure=AsyncMock())
        craft = Craft(manager, "http://127.0.0.1:1")
        with self.assertRaises(web.HTTPUnauthorized):
            await craft.authenticated_user(make_mocked_request("POST", "/craft/tools"))
        with self.assertRaises(ValueError):
            await craft.invoke(str(uuid.uuid4()), "bash", "tools/call", {})
        manager.ensure.assert_not_awaited()
