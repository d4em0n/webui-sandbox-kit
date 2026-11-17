"""Frontier's existing Tools implementation exposed through native MCP Apps."""
import inspect
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import quote, urlencode

from mcp.server.mcpserver import MCPServer, Context
from mcp.types import CallToolResult, TextContent, ToolAnnotations

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))
import frontier_ui as frontier
import openwebui
openwebui.install(frontier)

URI = "ui://frontier/ui.html"
MIME = "text/html;profile=mcp-app"
META = {"ui": {"resourceUri": URI, "visibility": ["model", "app"]}}


class FrontierTools(frontier.Tools):
    def _bridge(self):
        return openwebui.CRAFT

    async def craft_display(self, path: str, __user__: dict = None) -> tuple:
        """Display a finished workspace file as a Download/Open preview card, including files made or edited
        with Python/shell tools. Does not edit or convert it. Call once when the final file is ready.

        :param path: exact absolute path inside /home/user, returned by Craft tools or your workspace commands.
        """
        try:
            async with frontier.aiohttp.ClientSession() as session:
                value = await frontier._bridge_call(session, self._bridge(), "/file", {"path": path, "metadata_only": True})
            query = urlencode({"path": value["path"]})
            url = openwebui.PUBLIC + "/api/v1/terminals/" + quote(value["terminal_id"], safe="") + "/files/view?" + query
        except Exception as error:
            return f"Frontier UI could not display the file: {error}"
        block = {"type": "file", "name": value["name"], "format": Path(value["name"]).suffix[1:].lower(),
                 "size": value["size"], "url": url}
        if block["format"] in ("pdf", "docx", "pptx", "xlsx", "xls"):
            block["preview_url"] = openwebui.PUBLIC + "/document-preview/?" + urlencode({"terminal_id": value["terminal_id"], "path": value["path"]})
        return await self._file_card(block, None), f"File {value['name']} at {value['path']} is shown with Download and available preview actions. Links read the current workspace file; refresh an open preview after edits."

    async def _card(self, spec, __event_call__=None, req=None):
        spec.setdefault("_ui", {})["cdn"] = self.valves.maplibre_cdn
        if openwebui.PUBLIC:
            spec.setdefault("_ui", {})["base"] = openwebui.PUBLIC
            for block in spec.get("blocks", []):
                if block.get("type") != "file" or block.get("format") not in ("pdf", "docx", "pptx", "xlsx", "xls"):
                    continue
                url = block.get("url")
                if not isinstance(url, str):
                    continue
                match = re.fullmatch("(?:" + re.escape(openwebui.PUBLIC) + r")?/api/v1/files/([a-zA-Z0-9_-]+)/content", url)
                if match:
                    block["url"] = openwebui.PUBLIC + "/api/v1/files/" + match[1] + "/content"
                    block["preview_url"] = openwebui.PUBLIC + "/document-preview/?file_id=" + match[1]
        return spec


tools = FrontierTools()
settings = {"embedding_url": "", "page_screenshots": False, "units": "metric"}
if os.environ.get("FRONTIER_VALVES_FILE"):
    settings.update(json.loads(Path(os.environ["FRONTIER_VALVES_FILE"]).read_text()))
tools.valves = tools.Valves(**settings)

server = MCPServer("Frontier UI", version="0.1.0", instructions=
    "Use render_frontier_ui for interactive visual answers with Frontier's existing JSON spec. "
    "Use actual photo search queries and real place coordinates. After the tool returns, give a brief summary. "
    "All interactive cards use MCP Apps. Craft file tools run in the caller's private workspace. "
    "Desktop editor opening is unavailable. craft_file, craft_read, craft_edit and craft_convert return file details "
    "and an exact saved workspace path without displaying a card. Use that path directly for Python/shell edits; do not search for it. "
    "When the final file is ready, call frontier_craft_display with its exact path, including after Python/shell edits. "
    "Frontier file cards already deliver their files. After a successful frontier_craft_display result, do not call display_file or attach "
    "the same file again. Requests to create, edit, show, send or make a file downloadable are satisfied by that card. "
    "Give a brief confirmation. Use display_file for other files or an explicit request for a separate inline/sidebar display.")


def as_result(value):
    if isinstance(value, tuple) and len(value) == 2 and isinstance(value[0], dict):
        spec, summary = value
        # A Conduit bridge message is bounded to 256 KiB; fail explicitly rather than break its WebView.
        if len(json.dumps(spec).encode()) > 220_000:
            raise ValueError("Resolved card exceeds the mobile host limit. Split it into smaller cards.")
        if any(block.get("type") == "file" for block in spec.get("blocks", [])):
            summary = (str(summary) + " The file is already shown in this Frontier card. "
                       "Do not call display_file or add another attachment for the same file "
                       "unless the user explicitly requests a separate display.")
        return CallToolResult(content=[TextContent(type="text", text=str(summary))], structuredContent={"spec": spec})
    return CallToolResult(content=[TextContent(type="text", text=str(value))],
                          isError=isinstance(value, str) and value.startswith("Frontier UI could not"))


owners = {}
FILE_OPERATIONS = {"craft_file", "craft_read", "craft_edit", "craft_convert"}

def wrap(method):
    async def invoke(ctx: Context, **kwargs):
        token = openwebui.authorization.set((ctx.headers or {}).get("authorization", ""))
        file_token = openwebui.file_context.set({"defer_display": method.__name__ in FILE_OPERATIONS})
        try:
            user = await openwebui.api("/api/v1/auths/") if openwebui.BASE else {"id": "stdio"}
            if kwargs.get("card") and owners.get(kwargs["card"]) != user["id"]:
                raise PermissionError("Card is unavailable in this user's session. Render it again.")
            if "__user__" in inspect.signature(method).parameters:
                kwargs["__user__"] = user
            value = await method(**kwargs)
            if method.__name__ in FILE_OPERATIONS and isinstance(value, tuple) and isinstance(value[0], dict):
                block = value[0]["blocks"][0]
                details = {"name": block["name"], "path": openwebui.file_context.get().get("path"), "size": block["size"]}
                if not details["path"]:
                    raise RuntimeError("The file operation did not return a saved workspace path.")
                summary = value[1].replace("A preview card is shown.", "") if method.__name__ == "craft_read" else "File operation completed."
                summary += "\n" + json.dumps(details) + "\nUse this exact path for edits. When ready to deliver the final file, call frontier_craft_display(path=...) once. No file card has been shown yet."
                result = CallToolResult(content=[TextContent(type="text", text=summary)], structuredContent=details)
            else:
                result = as_result(value)
            spec = (result.structured_content or {}).get("spec", {})
            card = spec.get("_ui", {}).get("card")
            if card:
                owners[card] = user["id"]
                for old in set(owners) - set(frontier._CARDS):
                    owners.pop(old, None)
            return result
        except PermissionError as error:
            return CallToolResult(content=[TextContent(type="text", text=str(error))], isError=True)
        finally:
            openwebui.file_context.reset(file_token)
            openwebui.authorization.reset(token)
    signature = inspect.signature(method)
    invoke.__signature__ = signature.replace(parameters=[p for p in signature.parameters.values() if not p.name.startswith("__")] +
        [inspect.Parameter("ctx", inspect.Parameter.KEYWORD_ONLY, annotation=Context)], return_annotation=CallToolResult)
    invoke.__annotations__ = {p.name: p.annotation for p in invoke.__signature__.parameters.values()}
    invoke.__annotations__["return"] = CallToolResult
    invoke.__name__ = method.__name__
    return invoke


for name in ("render_frontier_ui", "craft_file", "craft_open", "save_note", "craft_read", "craft_edit", "craft_convert", "craft_commands", "craft_display"):
    method = getattr(tools, name)
    description = inspect.getdoc(method)
    if name in FILE_OPERATIONS:
        description = ("Returns file details and an exact workspace path, without a card. file accepts an absolute /home/user path or owned WebUI file ID/name. "
                       "Use craft_display(path=...) to deliver the final file.\n" + description)
    server.add_tool(wrap(method), name=name, description=description,
                    meta={"ui": {"visibility": ["model", "app"]}} if name in FILE_OPERATIONS else META if name != "craft_commands" else None,
                    annotations=ToolAnnotations(readOnlyHint=name == "render_frontier_ui", destructiveHint=False, openWorldHint=True))

# Network access is declared to the host, never inherited from Open WebUI's origin.
# Add origins explicitly for a custom image provider, tile server or ArtCraft deployment.
DOMAINS = ["https://cdn.jsdelivr.net", "https://tiles.openfreemap.org", "https://*.tiles.openfreemap.org",
           "https://server.arcgisonline.com", "https://*.wikimedia.org", "https://*.wikipedia.org",
           "https://images.unsplash.com", "https://images.pexels.com", "https://live.staticflickr.com",
           "https://icons.duckduckgo.com"]
DOMAINS += [x.strip() for x in os.environ.get("FRONTIER_RESOURCE_ORIGINS", "").split(",") if x.strip()]
CONNECT = ["https://tiles.openfreemap.org", "https://*.tiles.openfreemap.org", "https://server.arcgisonline.com"]
CONNECT += [x.strip() for x in os.environ.get("FRONTIER_CONNECT_ORIGINS", "").split(",") if x.strip()]
for url in (tools.valves.maplibre_cdn, tools.valves.tiles_url):
    origin = frontier._origin(url)
    if origin:
        DOMAINS.append(origin)
        CONNECT.append(origin)
DOMAINS.append("https://api.openverse.org")


@server.resource(URI, name="Frontier UI", mime_type=MIME,
                 meta={"ui": {"prefersBorder": False, "csp": {"resourceDomains": DOMAINS, "connectDomains": CONNECT}}})
def ui_resource() -> str:
    return (ROOT / "dist/frontier.html").read_text()


if __name__ == "__main__":
    if "--stdio" in sys.argv:
        server.run()
    else:
        server.run(transport="streamable-http", host="127.0.0.1", port=int(os.environ.get("FRONTIER_MCP_PORT", "8081")),
                   stateless_http=True, json_response=True, max_request_body_size=256 * 1024)
