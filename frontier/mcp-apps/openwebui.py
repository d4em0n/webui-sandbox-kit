"""Optional per-request Open WebUI notes/files bridge, using the caller's session.

No service account or database access is needed. The application still checks
ownership and permissions on every API request.
"""
import contextvars
import os

import aiohttp

BASE = os.environ.get("OPENWEBUI_BASE_URL", "").rstrip("/")
PUBLIC = os.environ.get("OPENWEBUI_PUBLIC_URL", BASE).rstrip("/")
authorization = contextvars.ContextVar("frontier_authorization", default="")


async def api(path, *, method="GET", body=None, data=None, raw=False):
    if not BASE or not authorization.get():
        raise PermissionError("This action requires the optional authenticated Open WebUI bridge.")
    async with aiohttp.ClientSession(headers={"Authorization": authorization.get()}, timeout=aiohttp.ClientTimeout(total=60)) as session:
        async with session.request(method, BASE + path, json=body, data=data, allow_redirects=False) as response:
            response.raise_for_status()
            return await response.read() if raw else await response.json()


def install(frontier):
    if not BASE:
        return

    async def bridge_call(session, config, path, payload, timeout=60):
        async with session.post(config["url"].rstrip("/") + path, json=payload,
            headers={"Authorization": authorization.get(), "X-Controller-Key": config["token"]},
            timeout=aiohttp.ClientTimeout(total=timeout)) as response:
            value = await response.json()
            if response.status >= 400:
                raise RuntimeError(value.get("error", "Craft bridge rejected the request"))
            return value

    async def create_note(user, title, text):
        result = await api("/api/v1/notes/create", method="POST", body={"title": title[:200],
            "data": {"content": {"json": None, "html": frontier._md_to_html(text), "md": text}}, "meta": None, "access_grants": []})
        return result["id"]

    async def load_file(ref, files, messages, user):
        items = await api("/api/v1/files/")
        items = items.get("items", []) if isinstance(items, dict) else items
        # MCP hosts do not forward chat attachments. Explicit IDs/names are supported;
        # never guess which of the account's files was attached to this conversation.
        if not str(ref).strip():
            raise ValueError("Pass the uploaded file's explicit ID or name; MCP does not forward chat attachments.")
        refs = [{"id": f["id"], "name": f.get("filename", "")} for f in items if f.get("user_id") == user["id"]]
        name = str(ref).lower()
        pick = next((f for f in refs if f["id"] == ref), None) or next((f for f in refs if f["name"].lower() == name), None)
        if not pick:
            raise FileNotFoundError("No owned file matches that explicit ID or name.")
        from urllib.parse import quote
        data = await api("/api/v1/files/" + quote(pick["id"], safe="") + "/content", raw=True)
        return pick["name"], data, pick["id"]

    async def store_file(user, name, data, mime):
        form = aiohttp.FormData()
        form.add_field("file", data, filename=name, content_type=mime)
        result = await api("/api/v1/files/?process=false", method="POST", data=form)
        fid = result["id"]
        return fid, PUBLIC + "/api/v1/files/" + fid + "/content"

    frontier._create_note = create_note
    frontier._load_file = load_file
    frontier._store_file = store_file
    frontier._bridge_call = bridge_call
