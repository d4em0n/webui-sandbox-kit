"""Static Craft editor host; all document reads/writes use WebUI's Terminal APIs."""
import base64
import hashlib
import re
from pathlib import Path

from aiohttp import web

EDITOR_CSP = "; ".join((
    "default-src 'self'", "script-src 'self'", "style-src 'self'",
    "connect-src 'self'", "frame-src 'self'", "object-src 'none'",
    "base-uri 'none'", "frame-ancestors 'none'", "form-action 'none'",
))
APP_CSP = "; ".join((
    "default-src 'self'", "script-src 'self' 'wasm-unsafe-eval'",
    "style-src 'self' 'unsafe-inline'", "img-src 'self' blob: data:",
    "font-src 'self' blob: data:", "connect-src 'self'", "worker-src 'self' blob:",
    "frame-src 'none'", "object-src 'none'", "base-uri 'none'",
    "frame-ancestors 'self'", "form-action 'none'",
))


def craft_web_routes(editor: Path, apps: Path):
    editor, apps = editor.resolve(), apps.resolve()

    async def serve(request):
        craft = request.path.startswith('/craft/')
        root = apps if craft else editor
        name = request.match_info.get("path") or "index.html"
        if not craft and name == "apps.json":
            root = apps
        target = (root / name).resolve()
        if not target.is_relative_to(root) or not target.is_file() or any(p.startswith('.') for p in Path(name).parts):
            raise web.HTTPNotFound()
        policy = APP_CSP if craft else EDITOR_CSP
        if craft and target.suffix == ".html":
            hashes = " ".join("'sha256-" + base64.b64encode(hashlib.sha256(script.encode()).digest()).decode() + "'"
                for script in re.findall(r"<script(?:\s[^>]*)?>(.*?)</script>", target.read_text(), re.DOTALL))
            policy = policy.replace("'wasm-unsafe-eval'", "'wasm-unsafe-eval' " + hashes)
        return web.FileResponse(target, headers={
            "Content-Security-Policy": policy, "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "public, max-age=31536000, immutable" if craft else "no-store",
        })

    return [web.get("/document-editor", serve), web.get("/document-editor/{path:.*}", serve),
            web.get("/craft/{path:.*}", serve)]
