"""Serve the standalone viewer; file data still goes through WebUI authorization."""
import base64
import hashlib
import re
from pathlib import Path

from aiohttp import web

CSP = "; ".join((
    "default-src 'self'", "script-src 'self' 'wasm-unsafe-eval'",
    "style-src 'self' 'unsafe-inline'", "img-src 'self' blob: data:",
    "font-src 'self' blob: data:", "connect-src 'self'", "worker-src 'self' blob:",
    "frame-src 'none'", "object-src 'none'", "base-uri 'none'",
    "frame-ancestors 'none'", "form-action 'none'",
))


def document_preview_routes(directory: Path):
    directory = directory.resolve()

    async def serve(request):
        name = request.match_info.get("path") or "index.html"
        target = (directory / name).resolve()
        if not target.is_relative_to(directory) or not target.is_file():
            raise web.HTTPNotFound()
        policy = CSP
        if target.name == "index.html":
            hashes = " ".join(
                "'sha256-" + base64.b64encode(hashlib.sha256(script.encode()).digest()).decode() + "'"
                for script in re.findall(r"<script(?:\s[^>]*)?>(.*?)</script>", target.read_text(), re.DOTALL))
            policy = CSP.replace("'wasm-unsafe-eval'", "'wasm-unsafe-eval' " + hashes)
        return web.FileResponse(target, headers={
            "Content-Security-Policy": policy,
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        })

    return [web.get("/document-preview", serve),
            web.get("/document-preview/{path:.*}", serve)]
