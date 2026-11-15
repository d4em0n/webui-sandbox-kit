"""Authenticated fixed-destination relay for bundled or operator-owned Firecrawl."""
import hmac

from aiohttp import web

from .proxy import relay
from .settings import DATA, secret


def endpoint(settings, manager, data=DATA):
    async def forward(request):
        if not settings["firecrawl"]:
            raise web.HTTPNotFound()
        if not hmac.compare_digest(request.headers.get("Authorization", ""), "Bearer " + secret("firecrawl-key", data)):
            raise web.HTTPUnauthorized(text="Invalid search credentials")
        # The caller's internal token and cookies must never reach an external service.
        headers = {key: value for key, value in request.headers.items() if key.lower() in
                   ("content-type", "accept", "accept-encoding", "user-agent")}
        if settings["firecrawl_mode"] == "external":
            key_file = data / "config/firecrawl-upstream-key"
            key = key_file.read_text().strip() if key_file.exists() else ""
            if key:
                headers["Authorization"] = "Bearer " + key
        target = settings["firecrawl_url"].rstrip("/") + request.raw_path.removeprefix("/firecrawl")
        return await relay(request, manager.client, target, headers)
    return forward
