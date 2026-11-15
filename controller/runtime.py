"""Lifecycle of the official Open WebUI image inside its own microVM."""
import asyncio
import json
import logging
import ipaddress
from aiohttp import ClientError
from urllib.parse import urlparse

from .settings import CODE, DATA
from .settings import atomic_json

LOG = logging.getLogger(__name__)


class WebUI:
    def __init__(self, manager, settings):
        self.manager, self.settings = manager, settings
        self.process = None
        self.closing = False
        self.ready = False
        self.url = "http://127.0.0.1:18080"

    async def create(self):
        code, _ = await self.manager.command("inspect", "webui", check=False)
        image = json.loads((CODE / "versions.lock.json").read_text())["images"]["webui"]
        desired = {key: self.settings[key] for key in ["webui_cpus", "webui_memory_mib", "root_disk_gib",
                                                       "provider_allow_private", "provider_url"]}
        desired["image"] = image
        provider = urlparse(self.settings["provider_url"])
        desired["tls_intercept"] = self.settings["provider_allow_private"] and provider.scheme == "https"
        record = DATA / "config/webui-vm.json"
        if code == 0:
            if record.exists() and json.loads(record.read_text()) == desired:
                return
            # Application state is in external mounts; the managed root overlay is disposable.
            await self.manager.command("remove", "--force", "webui")
        args = ["create", "--name", "webui", "--cpus", str(self.settings["webui_cpus"]),
            "--memory", str(self.settings["webui_memory_mib"]) + "M", "--root-disk", str(self.settings["root_disk_gib"]) + "G",
            "--security", "restricted", "--user", "1000:1000", "--mount-dir",
            str(DATA / "webui/data") + ":/app/backend/data:uid=1000,gid=1000", "--mount-dir",
            str(DATA / "webui/config") + ":/run/kit-config:ro,uid=1000,gid=1000", "--mount-dir",
            str(CODE) + ":/run/kit:ro,uid=1000,gid=1000", "--port", "127.0.0.1:18080:8080",
            "--net-default-egress", "deny", "--net-rule", "allow@public:tcp:80,allow@public:tcp:443,allow@dns",
            "--net-rule", "allow@host:tcp:18800", "--label", "application=webui-sandbox-kit"]
        if self.settings["provider_allow_private"]:
            port = provider.port or (443 if provider.scheme == "https" else 80)
            try:
                address = ipaddress.ip_address(provider.hostname)
                hostname = f"[{address}]" if address.version == 6 else str(address)
            except ValueError:
                hostname = "domain=" + provider.hostname
            args += ["--no-dns-rebind-protection", "--net-rule", f"allow@{hostname}:tcp:{port}"]
            if provider.scheme == "https":
                # Strict hostname rules require HTTP authority visibility inside TLS.
                args += ["--tls-intercept"]
        await self.manager.command(*args, image, timeout=1200)
        atomic_json(record, desired)

    async def healthy(self):
        try:
            async with self.manager.client.get(self.url + "/health", timeout=5) as response:
                return response.status == 200
        except (ClientError, OSError, asyncio.TimeoutError):
            return False

    async def stop(self):
        self.ready = False
        await self.manager.command("stop", "webui", check=False, timeout=45)
        if self.process and self.process.returncode is None:
            try:
                await asyncio.wait_for(self.process.wait(), 10)
            except asyncio.TimeoutError:
                self.process.kill()
                await self.process.wait()

    async def run(self):
        from .terminal import MSB
        while not self.closing:
            try:
                await self.create()
                await self.manager.command("stop", "webui", check=False)
                await self.manager.command("start", "webui")
                with (DATA / "logs/webui.log").open("ab") as output:
                    self.process = await asyncio.create_subprocess_exec(MSB, "exec", "--stream", "--no-stdin", "webui",
                        "--", "python", "/run/kit/guest/webui_start.py", stdout=output, stderr=output)
                for _ in range(600):
                    if self.process.returncode is not None:
                        raise RuntimeError("WebUI process exited during startup")
                    if await self.healthy():
                        self.ready = True
                        LOG.info("Open WebUI is ready")
                        break
                    await asyncio.sleep(1)
                else:
                    raise RuntimeError("WebUI startup health deadline exceeded")
                failures = 0
                while self.process.returncode is None and not self.closing:
                    await asyncio.sleep(10)
                    failures = 0 if await self.healthy() else failures + 1
                    if failures >= 3:
                        break
            except asyncio.CancelledError:
                raise
            except Exception as error:
                LOG.error("WebUI recovery required: %s", str(error)[-1000:])
            finally:
                await self.stop()
            if not self.closing:
                await asyncio.sleep(10)
