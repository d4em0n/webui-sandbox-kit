import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from aiohttp import ClientSession, web
from aiohttp.test_utils import TestClient, TestServer

from controller.bootstrap import prepare
from controller.firecrawl import endpoint
from controller.settings import atomic_json, load_settings
from test_boundaries import cli


class FirecrawlTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        (self.root / 'config').mkdir()
        (self.root / 'config/firecrawl-key').write_text('internal-secret')
        self.seen = []

        async def upstream(request):
            self.seen.append({'path': request.raw_path, 'headers': dict(request.headers), 'body': await request.json()})
            if request.path.endswith('/redirect'):
                raise web.HTTPTemporaryRedirect('/not-followed')
            return web.json_response({'success': True, 'data': []})

        app = web.Application()
        app.router.add_route('*', '/{path:.*}', upstream)
        self.upstream = TestServer(app)
        await self.upstream.start_server()
        self.session = ClientSession(auto_decompress=False)
        self.clients = []

    async def asyncTearDown(self):
        for client in self.clients:
            await client.close()
        await self.session.close()
        await self.upstream.close()
        self.directory.cleanup()

    async def client(self, mode='external', enabled=True):
        settings = {'firecrawl': enabled, 'firecrawl_mode': mode,
                    'firecrawl_url': str(self.upstream.make_url('/prefix/'))}
        app = web.Application()
        app.router.add_route('*', '/firecrawl/{path:.*}', endpoint(settings, self.session, self.root))
        client = TestClient(TestServer(app))
        await client.start_server()
        self.clients.append(client)
        return client

    async def test_existing_api_key_replaces_internal_credentials_and_preserves_api_path(self):
        (self.root / 'config/firecrawl-upstream-key').write_text('external-secret\n')
        client = await self.client()
        for path, body in [('/v2/search?mode=synthetic', {'query': 'synthetic'}),
                           ('/v2/scrape', {'url': 'https://example.com'})]:
            response = await client.post('/firecrawl' + path, json=body,
                headers={'Authorization': 'Bearer internal-secret', 'Cookie': 'session=private', 'X-User-Id': 'private'})
            self.assertEqual(response.status, 200)
            seen = self.seen[-1]
            self.assertEqual(seen['path'], '/prefix' + path)
            self.assertEqual(seen['body'], body)
            self.assertEqual(seen['headers'].get('Authorization'), 'Bearer external-secret')
            self.assertNotIn('Cookie', seen['headers'])
            self.assertNotIn('X-User-Id', seen['headers'])

    async def test_unauthenticated_external_service_receives_no_internal_token(self):
        client = await self.client()
        response = await client.post('/firecrawl/v2/search', data=b'{}',
            headers={'Authorization': 'Bearer internal-secret'})
        self.assertEqual(response.status, 200)
        self.assertNotIn('Authorization', self.seen[0]['headers'])

    async def test_bundled_does_not_use_external_key(self):
        (self.root / 'config/firecrawl-upstream-key').write_text('external-secret')
        client = await self.client('bundled')
        self.assertEqual((await client.post('/firecrawl/v2/search', json={},
            headers={'Authorization': 'Bearer internal-secret'})).status, 200)
        self.assertNotIn('Authorization', self.seen[0]['headers'])

    async def test_auth_disabled_and_redirect_are_not_bypassed(self):
        client = await self.client()
        self.assertEqual((await client.post('/firecrawl/v2/search', json={})).status, 401)
        disabled = await self.client(enabled=False)
        self.assertEqual((await disabled.post('/firecrawl/v2/search', json={})).status, 404)
        self.assertEqual(self.seen, [])
        response = await client.post('/firecrawl/v2/redirect', json={},
            headers={'Authorization': 'Bearer internal-secret'}, allow_redirects=False)
        self.assertEqual(response.status, 307)
        self.assertEqual(len(self.seen), 1)


class FirecrawlConfigurationTests(unittest.TestCase):
    def test_external_mode_keeps_key_out_of_guest_and_disables_bundled_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / 'instance/controller'
            atomic_json(data / 'config/settings.json', {'firecrawl_mode': 'external', 'firecrawl_url': 'https://search.example.com'})
            (data / 'config/firecrawl-upstream-key').write_text('synthetic-upstream-secret')
            prepare(data)
            env = json.loads((data / 'webui/config/environment.json').read_text())
            self.assertEqual(env['ENABLE_WEB_SEARCH'], 'true')
            self.assertNotIn('synthetic-upstream-secret', json.dumps(env))
            with patch.object(cli, 'ROOT', root), patch.object(cli, 'environment', return_value={'DATA_DIR': str(root / 'instance')}), \
                 patch.object(cli.subprocess, 'run') as run:
                cli.compose('config', '--services')
                self.assertNotIn('--profile', run.call_args.args[0])

    def test_invalid_modes_and_endpoint_credentials_are_rejected(self):
        for value in [{'firecrawl_mode': 'invalid'}, {'firecrawl_url': 'https://user:secret@example.com'},
                      {'firecrawl_url': 'https://example.com?token=secret'}]:
            with self.subTest(value=value), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                atomic_json(root / 'config/settings.json', value)
                with self.assertRaises(ValueError):
                    load_settings(root)
