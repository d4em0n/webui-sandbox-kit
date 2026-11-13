"""Per-user sessions for the official Craft stdio MCP servers.

The controller starts only fixed binaries inside the owning user's microVM.
Mutations are never replayed after an ambiguous disconnect or timeout.
"""
import asyncio
import contextlib
import json
import time

from aiohttp import web

from .terminal import MSB

APPS = {"wordcraft", "pdfcraft", "deckcraft"}
MAX_FRAME = 16 * 1024 * 1024


class StdioSession:
    def __init__(self, vm, app, log):
        self.vm, self.app, self.log = vm, app, log
        self.process = None
        self.sequence = 0
        self.lock = asyncio.Lock()
        self.touched = time.monotonic()

    async def start(self):
        args = [MSB, "exec", "--stream", self.vm, "--", f"/opt/craft/bin/{self.app}-cli", "mcp"]
        if self.app == "pdfcraft":
            args += ["--root", "/home/user"]
        else:
            args += ["--automation-read-root", "/home/user", "--automation-write-root", "/home/user"]
        with self.log.open("ab") as error:
            self.process = await asyncio.create_subprocess_exec(*args, stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE, stderr=error, limit=MAX_FRAME)
        await self.rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                     "clientInfo": {"name": "webui-sandbox-kit", "version": "0.1.0"}})
        await self.send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    async def send(self, body):
        encoded = json.dumps(body).encode() + b"\n"
        if len(encoded) > MAX_FRAME:
            raise ValueError("Craft request exceeds the frame limit")
        self.process.stdin.write(encoded)
        await self.process.stdin.drain()

    async def rpc(self, method, params):
        self.sequence += 1
        identity = self.sequence
        await self.send({"jsonrpc": "2.0", "id": identity, "method": method, "params": params})
        async with asyncio.timeout(120):
            while True:
                line = await self.process.stdout.readline()
                if not line:
                    raise RuntimeError("Craft session disconnected; the operation may have run. Inspect before retrying.")
                result = json.loads(line)
                if result.get("id") != identity:
                    continue
                if "error" in result:
                    raise ValueError(str(result["error"].get("message", "Craft rejected the request")))
                self.touched = time.monotonic()
                return result.get("result", {})

    async def close(self):
        if self.process is None:
            return
        if self.process.stdin:
            self.process.stdin.close()
        try:
            await asyncio.wait_for(self.process.wait(), 3)
        except asyncio.TimeoutError:
            with contextlib.suppress(ProcessLookupError):
                self.process.kill()
            await self.process.wait()


class Craft:
    def __init__(self, manager, webui_url):
        self.manager, self.webui_url = manager, webui_url
        self.sessions = {}
        self.locks = {}

    async def close_vm(self, vm):
        for key, session in list(self.sessions.items()):
            if session.vm == vm:
                self.sessions.pop(key, None)
                await session.close()

    async def invoke(self, user_id, app, method, params):
        if app not in APPS:
            raise ValueError("Choose wordcraft, pdfcraft or deckcraft")
        entry = await self.manager.ensure(user_id)
        key = (user_id, app)
        async with self.locks.setdefault(key, asyncio.Lock()):
            session = self.sessions.get(key)
            try:
                if session is None or session.process.returncode is not None:
                    if session:
                        await session.close()
                    session = StdioSession(entry["vm"], app, self.manager.base / "users" /
                        entry["vm"].removeprefix("open-terminal-") / f"{app}.log")
                    session.log.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                    self.sessions[key] = session
                    await session.start()
                return await session.rpc(method, params)
            except BaseException:
                self.sessions.pop(key, None)
                if session:
                    await session.close()
                raise

    async def authenticated_user(self, request):
        import hmac
        if not hmac.compare_digest(request.headers.get("X-Controller-Key", ""), self.manager.key):
            raise web.HTTPUnauthorized(text="Invalid controller credentials")
        token = request.headers.get("Authorization", "")
        if not token.startswith("Bearer "):
            raise web.HTTPUnauthorized(text="Open WebUI session required")
        async with self.manager.client.get(self.webui_url + "/api/v1/auths/", headers={"Authorization": token, "Accept-Encoding": "identity"}) as response:
            if response.status != 200:
                raise web.HTTPUnauthorized(text="Open WebUI session is invalid")
            user = await response.json()
        if not await self.manager.allowed(user.get("id")):
            raise web.HTTPForbidden(text="Account is not approved")
        return user["id"]

    async def endpoint(self, request):
        user_id = await self.authenticated_user(request)
        body = await request.json()
        operation = request.match_info["operation"]
        try:
            if operation == "tools":
                result = await self.invoke(user_id, body["app"], "tools/list", {})
                search = str(body.get("search", "")).lower()
                result["tools"] = [item for item in result["tools"] if all(term in
                    (item["name"] + " " + item.get("title", "") + " " + item.get("description", "")).lower()
                    for term in search.split())]
                limit = max(1, min(int(body.get("limit", 15)), 100))
                result["total"] = len(result["tools"])
                result["tools"] = result["tools"][:limit]
            elif operation == "call":
                result = await self.invoke(user_id, body["app"], "tools/call", {
                    "name": body["tool"], "arguments": body.get("arguments", {})})
            elif operation == "reset":
                key = (user_id, body["app"])
                async with self.locks.setdefault(key, asyncio.Lock()):
                    session = self.sessions.pop(key, None)
                    if session:
                        await session.close()
                result = {"reset": True}
            else:
                return await self.file_operation(user_id, operation, body)
            return web.json_response(result)
        except (KeyError, ValueError) as error:
            return web.json_response({"error": str(error)}, status=400)
        except (OSError, RuntimeError, asyncio.TimeoutError):
            return web.json_response({"error": "Craft session interrupted. The operation may have run; inspect the document before retrying."}, status=502)

    async def file_operation(self, user_id, operation, body):
        entry = await self.manager.ensure(user_id)
        process = await asyncio.create_subprocess_exec(MSB, "exec", "--stream", entry["vm"], "--", "python",
            "/run/open-terminal-ops/craft_job.py", operation, stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, limit=MAX_FRAME)
        try:
            output, _ = await asyncio.wait_for(process.communicate(json.dumps(body).encode()), 180)
        except BaseException:
            with contextlib.suppress(ProcessLookupError):
                process.kill()
            await process.wait()
            raise
        if process.returncode:
            return web.json_response({"error": "Craft file job failed; inspect the input and supported format."}, status=400)
        result = json.loads(output)
        return web.json_response(result, status=400 if result.get("error") else 200)
