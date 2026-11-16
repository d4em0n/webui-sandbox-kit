"""Container entrypoint: one trusted controller, independent service and VM lifecycles."""
import asyncio
import contextlib
import logging
import os
import signal

from aiohttp import web

from .bootstrap import prepare
from .catalog import own_home
from .craft import Craft
from .document_preview import document_preview_routes
from .firecrawl import endpoint as firecrawl_endpoint
from .proxy import relay
from .runtime import WebUI
from .settings import CODE, DATA
from .terminal import Manager


async def serve():
    settings = prepare()
    lease = own_home(DATA / "runtime")
    manager = Manager()
    runtime = WebUI(manager, settings)
    craft = Craft(manager, runtime.url)
    manager.on_stop = craft.close_vm
    # Specific routes must be registered before the terminal's wildcard route.
    internal = web.Application(client_max_size=32 * 1024 * 1024)
    internal.cleanup_ctx.append(manager.lifecycle)
    internal.router.add_post("/craft/{operation}", craft.endpoint)

    internal.router.add_route("*", "/firecrawl/{path:.*}", firecrawl_endpoint(settings, manager))
    internal.router.add_route("*", "/{path:.*}", manager.proxy)
    internal_runner = web.AppRunner(internal, access_log=None, shutdown_timeout=20)
    await internal_runner.setup()
    await web.TCPSite(internal_runner, "127.0.0.1", 18800).start()

    async def frontend(request):
        if not runtime.ready:
            return web.Response(status=503, text="Assistant is starting. The first boot downloads the pinned application images; retry shortly.\n")
        try:
            return await relay(request, manager.client, runtime.url + request.raw_path)
        except (OSError, asyncio.TimeoutError):
            raise web.HTTPBadGateway(text="Assistant is recovering; retry shortly.")

    public = web.Application(client_max_size=100 * 1024 * 1024)
    public.add_routes(document_preview_routes(CODE / "document-preview/dist"))
    public.router.add_route("*", "/{path:.*}", frontend)
    public_runner = web.AppRunner(public, access_log=None, shutdown_timeout=20)
    await public_runner.setup()
    await web.TCPSite(public_runner, "0.0.0.0", 3000).start()
    task = asyncio.create_task(runtime.run())
    stopped = asyncio.Event()
    for name in (signal.SIGTERM, signal.SIGINT):
        asyncio.get_running_loop().add_signal_handler(name, stopped.set)
    try:
        await stopped.wait()
    finally:
        runtime.closing = True
        await public_runner.cleanup()
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        await internal_runner.cleanup()
        lease.close()


if __name__ == "__main__":
    os.umask(0o077)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        pass
