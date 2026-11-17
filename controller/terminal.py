"""Authenticated Open Terminal routing to persistent, isolated per-user microVMs."""
import asyncio
import contextlib
import hashlib
import hmac
import json
import logging
import mimetypes
import os
from pathlib import Path
import re
import secrets
import sqlite3
import time
import uuid
from urllib.parse import quote

from aiohttp import ClientError, ClientSession, ClientTimeout, WSMsgType, web

BASE = Path(os.environ.get('KIT_DATA', '/data')) / 'terminal'
DATABASE = Path(os.environ.get('KIT_DATA', '/data')) / 'webui/data/webui.db'
MSB = os.environ.get('MSB_BIN', '/opt/microsandbox/bin/msb')
HOP_HEADERS = {'connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization',
               'te', 'trailer', 'transfer-encoding', 'upgrade', 'host', 'content-length'}
LOG = logging.getLogger('terminal-provisioner')

OFFICE_MIMES = {
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
}

def file_display_metadata(result):
    """Supply metadata missing from slim WebUI images without changing file bytes."""
    if not isinstance(result, dict) or result.get('exists') is not True:
        return result
    path = result.get('full_path') or result.get('path')
    if not isinstance(path, str) or not path:
        return result
    mime = result.get('content_type') or result.get('mime_type')
    if not mime or mime == 'application/octet-stream':
        mime = OFFICE_MIMES.get(Path(path).suffix.lower()) or mimetypes.guess_type(path)[0]
    if not mime:
        return result
    return {**result, 'mime_type': mime, 'content_type': mime}


def atomic_json(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.chmod(0o600)
    temporary.replace(path)


def approved_user(database, user_id):
    try:
        if str(uuid.UUID(user_id)) != user_id:
            return False
    except (ValueError, TypeError, AttributeError):
        return False
    with sqlite3.connect(f'file:{database}?mode=ro', uri=True, timeout=5) as db:
        return db.execute('SELECT 1 FROM user u JOIN auth a ON a.id=u.id '
                          'WHERE u.id=? AND u.role IN (?,?) AND a.active=1',
                          (user_id, 'admin', 'user')).fetchone() is not None


def session_scope(value):
    """Conduit's unsaved/sidebar scopes are omitted from its WS auth frame."""
    value = value or ''
    if value == 'sidebar-terminal' or value.startswith(('local:', 'temporary:', 'channel:')):
        return ''
    return value


class Manager:
    def __init__(self, base=BASE, database=DATABASE):
        self.base = base
        self.database = database
        self.config = json.loads((base / 'manager/config.json').read_text())
        self.key = (base / 'config/api-key').read_text().strip()
        self.state_path = base / 'private/users.json'
        self.entries = json.loads(self.state_path.read_text()) if self.state_path.exists() else {}
        self.locks = {}
        self.browser_locks = {}
        self.processes = {}
        self.failures = {}
        self.retry_after = {}
        self.identities = set()
        self.identity_expires = 0
        self.identity_lock = asyncio.Lock()
        self.creation = asyncio.Lock()
        self.boots = asyncio.Semaphore(2)
        self.closing = False
        self.on_stop = None

    async def allowed(self, user_id):
        if not self.config.get('identity_in_guest'):
            return approved_user(self.database, user_id)
        try:
            if str(uuid.UUID(user_id)) != user_id:
                return False
        except (ValueError, TypeError, AttributeError):
            return False
        # Read where SQLite writes occur: host-side virtiofs reads can lag guest writes.
        async with self.identity_lock:
            if time.monotonic() >= self.identity_expires or user_id not in self.identities:
                script = ("import sqlite3,json; "
                          "c=sqlite3.connect('file:/app/backend/data/webui.db?mode=ro',uri=True); "
                          "print(json.dumps([r[0] for r in c.execute("
                          "\"SELECT u.id FROM user u JOIN auth a ON a.id=u.id "
                          "WHERE u.role IN ('admin','user') AND a.active=1\")]))")
                try:
                    _, output = await self.command('exec', '--no-stdin', '--user', '1000:1000',
                        'webui', '--', 'python', '-c', script, timeout=15)
                    identities = json.loads(output)
                    if not isinstance(identities, list):
                        raise ValueError('Unexpected identity snapshot')
                    self.identities = set(identities)
                    self.identity_expires = time.monotonic() + 1
                except Exception:
                    raise web.HTTPServiceUnavailable(text='Account verification temporarily unavailable.')
        return user_id in self.identities

    async def command(self, *args, check=True, timeout=120):
        process = await asyncio.create_subprocess_exec(
            MSB, *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        try:
            output, _ = await asyncio.wait_for(process.communicate(), timeout)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            with contextlib.suppress(ProcessLookupError):
                process.kill()
            await process.wait()
            raise
        if check and process.returncode:
            # Never include keys, user prompts or request payloads in logs.
            raise RuntimeError(f'msb {args[0]} failed: {output.decode(errors="replace")[-1500:]}')
        return process.returncode, output

    async def entry_for(self, user_id):
        async with self.creation:
            if user_id in self.entries:
                return self.entries[user_id]
            active = sum([await self.allowed(uid) for uid in self.entries])
            if active >= self.config['max_users']:
                raise web.HTTPServiceUnavailable(text='Workspace capacity reached; contact the administrator.')
            digest = hashlib.sha256(user_id.encode()).hexdigest()[:24]
            directory = self.base / 'users' / digest
            workspace = directory / 'workspace'
            config = directory / 'config'
            workspace.mkdir(parents=True, exist_ok=True, mode=0o700)
            config.mkdir(parents=True, exist_ok=True, mode=0o700)
            key = config / 'api-key'
            if not key.exists():
                key.write_text(secrets.token_urlsafe(48) + '\n')
                key.chmod(0o600)
            guidelines = self.base / 'ops/workspace-guidelines.md'
            if guidelines.exists():
                (workspace / 'AGENTS.md').write_text(guidelines.read_text())
            used = {entry['port'] for entry in self.entries.values()}
            port = next((p for p in range(18801, 18901) if p not in used), None)
            if port is None:
                raise web.HTTPServiceUnavailable(text='Workspace port capacity reached.')
            entry = {'vm': 'open-terminal-' + digest, 'port': port,
                     'workspace': str(workspace), 'config': str(config)}
            self.entries[user_id] = entry
            atomic_json(self.state_path, self.entries)
            LOG.info('Registered workspace %s', entry['vm'])
            return entry

    async def create(self, entry):
        exists, output = await self.command('inspect', entry['vm'], '--format', 'json', check=False)
        if exists == 0:
            actual = json.loads(output)['config']['image']['Oci']['reference']
            if actual == self.config['image']:
                return
            await self.command('remove', '--force', entry['vm'])
        await self.command('create', '--name', entry['vm'],
                           '--cpus', str(self.config.get('cpus', 2)),
                           '--memory', f'{self.config.get("memoryMiB", 2048)}M',
                           '--root-disk', f'{self.config.get("root_disk_gib", 30)}G', '--security', 'restricted', '--user', '1000:1000',
                           '--mount-dir', entry['workspace'] + ':/home/user:uid=1000,gid=1000',
                           '--mount-dir', entry['config'] + ':/run/open-terminal-config:ro,uid=1000,gid=1000',
                           '--mount-dir', str(self.base / 'ops') + ':/run/open-terminal-ops:ro,uid=1000,gid=1000',
                           '--mount-dir', '/opt/craft:/opt/craft:ro,uid=1000,gid=1000',
                           '--port', f'127.0.0.1:{entry["port"]}:8000',
                           '--net-default-egress', 'deny', '--net-default-ingress', 'allow',
                           *(['--net-rule', 'allow@public:tcp:80,allow@public:tcp:443,allow@dns']
                             if self.config.get('public_web') else []),
                           '--label', 'application=open-terminal', self.config['image'], timeout=300)

    async def healthy(self, entry):
        try:
            async with self.client.get(f'http://127.0.0.1:{entry["port"]}/health',
                                       timeout=ClientTimeout(total=3)) as response:
                return response.status == 200
        except (ClientError, OSError, asyncio.TimeoutError):
            return False

    async def stop(self, entry):
        if self.on_stop is not None:
            await self.on_stop(entry['vm'])
        await self.command('stop', entry['vm'], check=False, timeout=45)
        process = self.processes.pop(entry['vm'], None)
        if process and process.returncode is None:
            try:
                await asyncio.wait_for(process.wait(), 10)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()

    async def ensure(self, user_id):
        lock = self.locks.setdefault(user_id, asyncio.Lock())
        async with lock:
            if not await self.allowed(user_id):
                raise web.HTTPForbidden(text='Account is not approved for a workspace.')
            entry = await self.entry_for(user_id)
            process = self.processes.get(entry['vm'])
            if process and process.returncode is None and await self.healthy(entry):
                self.failures[user_id] = 0
                return entry
            if self.closing:
                raise web.HTTPServiceUnavailable(text='Workspace service is stopping.')
            if time.monotonic() < self.retry_after.get(user_id, 0):
                raise web.HTTPServiceUnavailable(text='Workspace is recovering; retry shortly.')
            async with self.boots:
                try:
                    await self.stop(entry)
                    await self.create(entry)
                    running, _ = await self.command('ping', entry['vm'], check=False)
                    if running:
                        await self.command('start', entry['vm'])
                    log = Path(entry['config']).parent / 'server.log'
                    log.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                    with log.open('ab') as stream:
                        process = await asyncio.create_subprocess_exec(
                            MSB, 'exec', '--stream', '--no-stdin', '--user', '1000:1000', entry['vm'],
                            '--', '/bin/bash', '/run/open-terminal-ops/guest-start.sh',
                            stdout=stream, stderr=stream)
                    self.processes[entry['vm']] = process
                    for _ in range(90):
                        if self.closing or process.returncode is not None:
                            break
                        if await self.healthy(entry):
                            LOG.info('Workspace healthy: %s', entry['vm'])
                            self.failures[user_id] = 0
                            return entry
                        await asyncio.sleep(1)
                    raise RuntimeError('Workspace application did not become healthy')
                except Exception:
                    self.retry_after[user_id] = time.monotonic() + 15
                    await self.stop(entry)
                    raise

    async def monitor(self):
        while not self.closing:
            for uid, entry in list(self.entries.items()):
                if self.closing:
                    break
                try:
                    if not await self.allowed(uid):
                        if entry['vm'] in self.processes:
                            async with self.locks.setdefault(uid, asyncio.Lock()):
                                await self.stop(entry)
                                LOG.info('Stopped revoked workspace %s; files retained', entry['vm'])
                        continue
                    process = self.processes.get(entry['vm'])
                    if process and process.returncode is None and not await self.healthy(entry):
                        self.failures[uid] = self.failures.get(uid, 0) + 1
                        if self.failures[uid] < 3:
                            continue
                        async with self.locks.setdefault(uid, asyncio.Lock()):
                            await self.stop(entry)
                    await self.ensure(uid)
                except Exception as error:
                    LOG.warning('Workspace recovery for %s: %s', entry['vm'], type(error).__name__)
            await asyncio.sleep(10)

    async def ensure_browser(self, entry, headers):
        """Prepare an owned Chrome tab for native tools, including headless clients."""
        scope = (headers['X-User-Id'], headers.get('X-Session-Id', ''))
        async with self.browser_locks.setdefault(scope, asyncio.Lock()):
            base = f'http://127.0.0.1:{entry["port"]}/browser'

            async def call(method, path, body=None):
                async with self.client.request(method, base + path, headers=headers,
                                               json=body, timeout=ClientTimeout(total=75)) as response:
                    if response.status >= 400:
                        raise web.HTTPBadGateway(text='Browser could not start; retry shortly.')
                    return await response.json()

            tabs = await call('GET', '/tabs')
            selected = tabs.get('current_session_id')
            tab = next((item for item in tabs.get('tabs', [])
                        if item['session_id'] == selected), None)
            if tab and tab.get('mode') == 'chrome':
                return
            created = None
            if tab is None:
                created = await call('POST', '/sessions', {'url': ''})
                selected = created['id']
            try:
                await call('PATCH', '/sessions/' + selected, {'mode': 'chrome', 'active': True})
            except BaseException:
                if created:
                    with contextlib.suppress(Exception):
                        await call('DELETE', '/sessions/' + selected)
                raise

    async def proxy(self, request):
        if request.path == '/health':
            return web.json_response({'status': 'ok'})
        if request.headers.get('Upgrade', '').lower() == 'websocket':
            return await self.websocket(request)
        token = request.headers.get('Authorization', '')
        if not hmac.compare_digest(token, 'Bearer ' + self.key):
            raise web.HTTPUnauthorized(text='Invalid terminal connection credentials.')
        user_id = request.headers.get('X-User-Id')
        if user_id is None:
            # Only discovery is available without an authenticated Open WebUI user.
            if request.method == 'GET' and request.path in ('/api/config', '/openapi.json', '/system'):
                filename = {'/api/config': 'api-config.json', '/openapi.json': 'openapi.json', '/system': 'system.json'}[request.path]
                return web.Response(body=(self.base / 'manager' / filename).read_bytes(),
                                    content_type='application/json')
            if request.path == '/api/v1/policies':
                raise web.HTTPNotFound()
            raise web.HTTPForbidden(text='Authenticated Open WebUI user identity required.')
        if not await self.allowed(user_id):
            raise web.HTTPForbidden(text='Account is not approved for a workspace.')
        try:
            entry = await self.ensure(user_id)
        except web.HTTPException:
            raise
        except Exception:
            LOG.exception('Workspace startup failed')
            raise web.HTTPServiceUnavailable(text='Workspace failed to start; retry shortly.')
        target = f'http://127.0.0.1:{entry["port"]}' + request.raw_path
        headers = {key: value for key, value in request.headers.items()
                   if key.lower() not in HOP_HEADERS | {'authorization', 'cookie', 'origin', 'sec-websocket-key',
                                                       'sec-websocket-version', 'sec-websocket-extensions',
                                                       'sec-websocket-protocol'}}
        headers['Authorization'] = 'Bearer ' + (Path(entry['config']) / 'api-key').read_text().strip()
        headers['X-User-Id'] = user_id
        headers['X-Session-Id'] = session_scope(request.headers.get('X-Session-Id'))
        display_request = request.method == 'GET' and request.path == '/files/display'
        if display_request:
            headers = {key: value for key, value in headers.items() if key.lower() != 'accept-encoding'}
            headers['Accept-Encoding'] = 'identity'
        try:
            if self.config.get('auto_browser') and request.path in (
                '/browser/snapshot', '/browser/screenshot', '/browser/action'
            ):
                await self.ensure_browser(entry, headers)
            async with self.client.request(request.method, target, headers=headers,
                                           data=request.content if request.can_read_body else None,
                                           allow_redirects=False) as upstream:
                if display_request and upstream.status == 200:
                    body = bytearray()
                    async for chunk in upstream.content.iter_chunked(4096):
                        body.extend(chunk)
                        if len(body) > 65536:
                            raise web.HTTPBadGateway(text='Invalid file display metadata.')
                    try:
                        result = json.loads(body)
                    except (ValueError, UnicodeDecodeError):
                        raise web.HTTPBadGateway(text='Invalid file display metadata.')
                    return web.json_response(file_display_metadata(result))
                response = web.StreamResponse(status=upstream.status,
                    headers={key: value for key, value in upstream.headers.items()
                             if key.lower() not in HOP_HEADERS})
                if request.method == 'GET' and request.path == '/files/view' and upstream.status == 200:
                    name = Path(request.query.get('path', '')).name
                    if name and request.query.get('preview', '').lower() != 'true':
                        response.headers.setdefault('Content-Disposition', "inline; filename*=UTF-8''" + quote(name, safe=''))
                await response.prepare(request)
                async for chunk in upstream.content.iter_chunked(65536):
                    await response.write(chunk)
                await response.write_eof()
                return response
        except (OSError, asyncio.TimeoutError):
            raise web.HTTPBadGateway(text='Workspace connection interrupted.')

    async def websocket(self, request):
        # Browser viewers authenticate through WebUI's signed ticket + relay header;
        # terminal/event sockets authenticate in their first message instead.
        browser_view = re.fullmatch(r'/browser/view/[^/]+/[^/]+/(ws|stream|vnc)', request.path)
        downstream = web.WebSocketResponse(max_msg_size=16 * 1024 * 1024)
        await downstream.prepare(request)
        try:
            if browser_view:
                auth = {}
                authenticated = hmac.compare_digest(
                    request.headers.get('Authorization', ''), 'Bearer ' + self.key
                )
            else:
                message = await downstream.receive(timeout=5)
                auth = json.loads(message.data) if message.type == WSMsgType.TEXT else {}
                authenticated = isinstance(auth, dict) and hmac.compare_digest(str(auth.get('token', '')), self.key)
            if not authenticated:
                await downstream.close(code=4003, message=b'Invalid terminal credentials')
                return downstream
            user_id = request.headers.get('X-User-Id')
            if not await self.allowed(user_id):
                await downstream.close(code=4003, message=b'Account not approved')
                return downstream
            entry = await self.ensure(user_id)
            target = f'http://127.0.0.1:{entry["port"]}' + request.raw_path
            backend_key = (Path(entry['config']) / 'api-key').read_text().strip()
            headers = {'X-User-Id': user_id,
                       'X-Session-Id': session_scope(request.headers.get('X-Session-Id', auth.get('chat_id', '')))}
            if browser_view:
                headers['Authorization'] = 'Bearer ' + backend_key
            async with self.client.ws_connect(target, headers=headers,
                                              max_msg_size=16 * 1024 * 1024) as upstream:
                if not browser_view:
                    await upstream.send_json({**auth, 'token': backend_key})

                async def forward(source, destination):
                    while True:
                        message = await source.receive()
                        if message.type == WSMsgType.TEXT:
                            await destination.send_str(message.data)
                        elif message.type == WSMsgType.BINARY:
                            await destination.send_bytes(message.data)
                        else:
                            await destination.close(code=source.close_code or 1000,
                                message=str(message.extra or '').encode()[:120])
                            break
                tasks = [asyncio.create_task(forward(downstream, upstream)),
                         asyncio.create_task(forward(upstream, downstream))]
                try:
                    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                    for task in done:
                        task.result()
                finally:
                    for task in tasks:
                        task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)
        except (ValueError, asyncio.TimeoutError):
            await downstream.close(code=4003, message=b'Authentication required')
        except Exception:
            LOG.warning('Workspace WebSocket interrupted', exc_info=True)
            await downstream.close(code=1011, message=b'Workspace connection interrupted')
        finally:
            await downstream.close()
        return downstream

    async def lifecycle(self, app):
        self.client = ClientSession(timeout=ClientTimeout(total=None, connect=15, sock_read=300),
                                    auto_decompress=False)
        monitor = asyncio.create_task(self.monitor())
        yield
        self.closing = True
        monitor.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await monitor
        await asyncio.gather(*(self.stop(entry) for entry in self.entries.values()), return_exceptions=True)
        await self.client.close()

    def app(self):
        app = web.Application(client_max_size=100 * 1024 * 1024)
        app.cleanup_ctx.append(self.lifecycle)
        app.router.add_route('*', '/{path:.*}', self.proxy)
        return app

