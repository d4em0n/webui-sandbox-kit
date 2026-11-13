import asyncio
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import AsyncMock
import uuid

from aiohttp import ClientSession, web
from aiohttp.test_utils import TestClient, TestServer

spec = importlib.util.spec_from_file_location('provisioner', Path(__file__).parents[1] / 'controller/terminal.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RoutingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        for directory in ('manager', 'config', 'private', 'workspace', 'ops'):
            (self.base / directory).mkdir()
        (self.base / 'config/api-key').write_text('router-secret')
        (self.base / 'manager/config.json').write_text(json.dumps({'max_users': 2}))
        (self.base / 'manager/api-config.json').write_text('{}')
        (self.base / 'manager/openapi.json').write_text('{}')
        (self.base / 'workspace/AGENTS.md').write_text('Owner private instructions')
        (self.base / 'ops/workspace-guidelines.md').write_text('Shared workspace instructions')
        self.database = self.base / 'users.db'
        self.users = [str(uuid.uuid4()) for _ in range(4)]
        with sqlite3.connect(self.database) as db:
            db.execute('CREATE TABLE user (id TEXT, role TEXT)')
            db.execute('CREATE TABLE auth (id TEXT, active INTEGER)')
            for uid, role, active in zip(self.users, ('user', 'admin', 'pending', 'user'), (1, 1, 1, 0)):
                db.execute('INSERT INTO user VALUES (?,?)', (uid, role))
                db.execute('INSERT INTO auth VALUES (?,?)', (uid, active))
        self.manager = module.Manager(self.base, self.database)
        self.manager.client = ClientSession(auto_decompress=False)
        self.servers = []

        async def backend(request):
            if request.headers.get('Upgrade', '').lower() == 'websocket':
                ws = web.WebSocketResponse()
                await ws.prepare(request)
                if request.path.startswith('/browser/view/'):
                    await ws.send_json({'authorization': request.headers.get('Authorization'),
                                        'user': request.headers.get('X-User-Id'),
                                        'scope': request.headers.get('X-Session-Id')})
                else:
                    await ws.receive_json()
                async for message in ws:
                    if message.type == module.WSMsgType.BINARY:
                        await ws.send_bytes(message.data)
                    else:
                        await ws.send_str(message.data)
                return ws
            return web.json_response({'authorization': request.headers.get('Authorization'),
                                      'user': request.headers.get('X-User-Id'),
                                      'scope': request.headers.get('X-Session-Id'),
                                      'body': (await request.read()).decode()})

        self.routes = {}
        for uid in self.users[:2]:
            app = web.Application()
            app.router.add_route('*', '/{path:.*}', backend)
            server = TestServer(app)
            await server.start_server()
            self.servers.append(server)
            entry = await self.manager.entry_for(uid)
            entry['port'] = server.port
            self.routes[uid] = entry

        async def ensure(uid):
            return self.routes[uid]
        self.manager.ensure = ensure
        app = self.manager.app()
        app.cleanup_ctx.clear()
        self.client = TestClient(TestServer(app))
        await self.client.start_server()

    async def asyncTearDown(self):
        await self.client.close()
        await self.manager.client.close()
        for server in self.servers:
            await server.close()
        self.temp.cleanup()

    def headers(self, uid=None, key='router-secret'):
        return {'Authorization': 'Bearer ' + key, **({'X-User-Id': uid} if uid else {})}

    async def test_invalid_and_unapproved_identities_cannot_route(self):
        for uid in [None, '../other', str(uuid.uuid4()), *self.users[2:]]:
            response = await self.client.get('/files/list', headers=self.headers(uid))
            self.assertEqual(response.status, 403)
        self.assertEqual(len(self.manager.entries), 2)

    async def test_backend_key_does_not_authenticate_router(self):
        key = (Path(self.routes[self.users[0]]['config']) / 'api-key').read_text().strip()
        response = await self.client.get('/files/list', headers=self.headers(self.users[0], key))
        self.assertEqual(response.status, 401)

    async def test_routes_payload_and_replaces_credentials(self):
        keys = []
        for uid in self.users[:2]:
            response = await self.client.post('/execute?wait=3', headers=self.headers(uid), data='test payload')
            self.assertEqual(response.status, 200)
            value = await response.json()
            self.assertEqual(value['user'], uid)
            self.assertEqual(value['body'], 'test payload')
            self.assertNotEqual(value['authorization'], 'Bearer router-secret')
            keys.append(value['authorization'])
        self.assertNotEqual(*keys)

    async def test_websocket_is_bidirectional(self):
        async with self.client.ws_connect('/events', headers=self.headers(self.users[0])) as ws:
            await ws.send_json({'type': 'auth', 'token': 'router-secret'})
            await ws.send_str('interactive input')
            response = await ws.receive(timeout=3)
            self.assertEqual(response.data, 'interactive input')

    async def test_websocket_requires_router_secret(self):
        async with self.client.ws_connect('/events', headers=self.headers(self.users[0])) as ws:
            await ws.send_json({'type': 'auth', 'token': 'wrong-secret'})
            message = await ws.receive(timeout=3)
            self.assertEqual(message.data, 4003)

    async def test_browser_viewer_uses_header_auth_without_consuming_protocol_frame(self):
        uid = self.users[0]
        for kind in ['stream', 'vnc', 'ws']:
            headers = {**self.headers(uid), 'X-Session-Id': 'saved-chat'}
            async with self.client.ws_connect('/browser/view/session/capability/' + kind, headers=headers) as ws:
                metadata = await ws.receive_json(timeout=3)
                self.assertEqual(metadata['user'], uid)
                self.assertEqual(metadata['scope'], 'saved-chat')
                backend_key = (Path(self.routes[uid]['config']) / 'api-key').read_text().strip()
                self.assertEqual(metadata['authorization'], 'Bearer ' + backend_key)
                await ws.send_json({'type': 'frames'})
                self.assertEqual(await ws.receive_json(timeout=3), {'type': 'frames'})
                await ws.send_bytes(b'frame-data')
                message = await ws.receive(timeout=3)
                self.assertEqual(message.data, b'frame-data')

    async def test_browser_viewer_rejects_missing_or_invalid_header_credentials(self):
        for headers in [{}, {'X-User-Id': self.users[0]}, self.headers(self.users[0], 'wrong-key')]:
            async with self.client.ws_connect('/browser/view/session/capability/stream', headers=headers) as ws:
                message = await ws.receive(timeout=3)
                self.assertEqual(message.data, 4003)

    async def test_browser_viewer_rejects_unknown_or_revoked_user(self):
        for uid in [str(uuid.uuid4()), *self.users[2:]]:
            async with self.client.ws_connect('/browser/view/session/capability/stream', headers=self.headers(uid)) as ws:
                message = await ws.receive(timeout=3)
                self.assertEqual(message.data, 4003)

    async def test_terminal_socket_still_requires_first_message_auth_with_valid_header(self):
        async with self.client.ws_connect('/events', headers=self.headers(self.users[0])) as ws:
            await ws.send_json({'type': 'auth', 'token': 'wrong-key'})
            message = await ws.receive(timeout=3)
            self.assertEqual(message.data, 4003)

    async def test_websocket_rejects_unknown_identity(self):
        async with self.client.ws_connect('/events', headers=self.headers(str(uuid.uuid4()))) as ws:
            await ws.send_json({'type': 'auth', 'token': 'router-secret'})
            message = await ws.receive(timeout=3)
            self.assertEqual(message.data, 4003)

    async def test_guest_identity_snapshot_includes_fresh_accounts(self):
        self.manager.config['identity_in_guest'] = True
        self.manager.command = AsyncMock(return_value=(0, json.dumps([self.users[0]]).encode()))
        self.assertTrue(await self.manager.allowed(self.users[0]))
        self.manager.command.return_value = (0, json.dumps(self.users[:2]).encode())
        self.assertTrue(await self.manager.allowed(self.users[1]))
        self.manager.identity_expires = 0
        self.manager.command.return_value = (0, b'[]')
        self.assertFalse(await self.manager.allowed(self.users[0]))

    async def test_guest_identity_failure_does_not_use_stale_approval(self):
        self.manager.config['identity_in_guest'] = True
        self.manager.identities = {self.users[0]}
        self.manager.identity_expires = 0
        self.manager.command = AsyncMock(side_effect=RuntimeError('Guest unavailable'))
        with self.assertRaises(web.HTTPServiceUnavailable):
            await self.manager.allowed(self.users[0])

    async def test_sidebar_and_unsaved_http_scopes_match_websocket_scope(self):
        for scope in ['sidebar-terminal', 'local:synthetic', 'temporary:synthetic', 'channel:synthetic']:
            headers = {**self.headers(self.users[0]), 'X-Session-Id': scope}
            response = await self.client.post('/api/terminals', headers=headers)
            self.assertEqual((await response.json())['scope'], '')
        saved = str(uuid.uuid4())
        response = await self.client.post('/api/terminals', headers={
            **self.headers(self.users[0]), 'X-Session-Id': saved})
        self.assertEqual((await response.json())['scope'], saved)

    async def test_discovery_requires_key_without_provisioning(self):
        self.assertEqual((await self.client.get('/openapi.json')).status, 401)
        self.assertEqual((await self.client.get('/openapi.json', headers=self.headers())).status, 200)
        self.assertEqual(len(self.manager.entries), 2)

    async def test_concurrent_requests_reuse_entry_and_secret(self):
        entries = await asyncio.gather(*(self.manager.entry_for(self.users[0]) for _ in range(20)))
        self.assertTrue(all(entry == entries[0] for entry in entries))
        self.assertEqual(len(self.manager.entries), 2)
        self.assertEqual(len(list((self.base / 'users').glob('*/config/api-key'))), 2)

    async def test_new_vm_uses_configured_resources_and_preserves_isolation(self):
        self.manager.config.update(cpus=2, memoryMiB=2048, image='official-image')
        self.manager.command = AsyncMock(side_effect=[(1, b''), (0, b'')])
        await self.manager.create(self.routes[self.users[0]])
        args = self.manager.command.call_args_list[1].args
        self.assertEqual(args[args.index('--cpus') + 1], '2')
        self.assertEqual(args[args.index('--memory') + 1], '2048M')
        self.assertEqual(args[args.index('--security') + 1], 'restricted')
        self.assertEqual(args[args.index('--user') + 1], '1000:1000')
        self.assertEqual(args[args.index('--net-default-egress') + 1], 'deny')
        self.assertTrue(args[args.index('--port') + 1].startswith('127.0.0.1:'))

    async def test_resource_settings_are_read_from_config_instead_of_fixed_values(self):
        self.manager.config.update(cpus=3, memoryMiB=3072, image='official-image')
        self.manager.command = AsyncMock(side_effect=[(1, b''), (0, b'')])
        await self.manager.create(self.routes[self.users[0]])
        args = self.manager.command.call_args_list[1].args
        self.assertEqual(args[args.index('--cpus') + 1], '3')
        self.assertEqual(args[args.index('--memory') + 1], '3072M')

    async def test_new_workspace_never_copies_owner_files(self):
        for uid in self.users[:2]:
            path = Path(self.routes[uid]['workspace']) / 'AGENTS.md'
            self.assertEqual(path.read_text(), 'Shared workspace instructions')
            self.assertNotIn('Owner private', path.read_text())

    async def test_approved_user_capacity_is_bounded(self):
        third = str(uuid.uuid4())
        with sqlite3.connect(self.database) as db:
            db.execute('INSERT INTO user VALUES (?,?)', (third, 'user'))
            db.execute('INSERT INTO auth VALUES (?,?)', (third, 1))
        with self.assertRaises(web.HTTPServiceUnavailable):
            await self.manager.entry_for(third)

    async def test_revocation_takes_effect_without_restart(self):
        uid = self.users[0]
        with sqlite3.connect(self.database) as db:
            db.execute('UPDATE auth SET active=0 WHERE id=?', (uid,))
        response = await self.client.get('/files/list', headers=self.headers(uid))
        self.assertEqual(response.status, 403)


class BrowserProvisioningTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        for directory in ('manager', 'config', 'private'):
            (self.base / directory).mkdir()
        (self.base / 'manager/config.json').write_text('{}')
        (self.base / 'config/api-key').write_text('router-secret')
        self.manager = module.Manager(self.base)
        self.manager.client = ClientSession()
        self.tabs = {}
        self.created = 0
        self.fail_start = False
        self.requests = []

        async def backend(request):
            scope = (request.headers.get('X-User-Id'), request.headers.get('X-Session-Id'))
            self.requests.append((request.method, scope, request.headers.get('Authorization')))
            if request.path == '/browser/tabs':
                tab = self.tabs.get(scope)
                return web.json_response({'current_session_id': tab['session_id'] if tab else None,
                                          'tabs': [tab] if tab else []})
            if request.method == 'POST':
                self.created += 1
                sid = str(uuid.uuid4())
                self.tabs[scope] = {'session_id': sid, 'mode': 'proxy'}
                return web.json_response({'id': sid})
            if request.method == 'DELETE':
                self.tabs.pop(scope, None)
                return web.json_response({'status': 'closed'})
            if self.fail_start:
                return web.json_response({'error': 'Chrome unavailable'}, status=409)
            self.tabs[scope]['mode'] = 'chrome'
            return web.json_response({'status': 'ok'})

        app = web.Application()
        app.router.add_route('*', '/{path:.*}', backend)
        self.server = TestServer(app)
        await self.server.start_server()
        self.entry = {'port': self.server.port}

    async def asyncTearDown(self):
        await self.manager.client.close()
        await self.server.close()
        self.temp.cleanup()

    def headers(self, user='user-a', chat='chat-a'):
        return {'X-User-Id': user, 'X-Session-Id': chat, 'Authorization': 'Bearer backend-secret'}

    async def test_concurrent_tools_share_one_owned_chrome_tab(self):
        await asyncio.gather(*(self.manager.ensure_browser(self.entry, self.headers()) for _ in range(4)))
        self.assertEqual(self.created, 1)
        self.assertEqual(self.tabs[('user-a', 'chat-a')]['mode'], 'chrome')
        self.assertTrue(all(item[2] == 'Bearer backend-secret' for item in self.requests))

    async def test_different_users_and_chats_get_separate_tabs(self):
        for headers in [self.headers(), self.headers(chat='chat-b'), self.headers(user='user-b')]:
            await self.manager.ensure_browser(self.entry, headers)
        self.assertEqual(self.created, 3)
        self.assertEqual(len(self.tabs), 3)

    async def test_existing_chrome_tab_is_preserved(self):
        self.tabs[('user-a', 'chat-a')] = {'session_id': 'existing', 'mode': 'chrome'}
        await self.manager.ensure_browser(self.entry, self.headers())
        self.assertEqual(self.created, 0)
        self.assertEqual([item[0] for item in self.requests], ['GET'])

    async def test_failed_start_removes_only_the_new_tab(self):
        self.fail_start = True
        with self.assertRaises(web.HTTPBadGateway):
            await self.manager.ensure_browser(self.entry, self.headers())
        self.assertEqual(self.tabs, {})
