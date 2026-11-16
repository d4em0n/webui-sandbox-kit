"""Frontier's existing Tools implementation exposed through native MCP Apps."""
import inspect
import json
import os
import re
import sys
from pathlib import Path

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
        return {"url": "http://host.microsandbox.internal:18800/craft",
                "token": os.environ.get("KIT_CONTROLLER_KEY", ""), "shots": False}

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
                match = re.fullmatch(re.escape(openwebui.PUBLIC) + r"/api/v1/files/([a-zA-Z0-9_-]+)/content", url)
                if match:
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
    "Desktop editor opening is unavailable; generated files have download cards.")


def as_result(value):
    if isinstance(value, tuple) and len(value) == 2 and isinstance(value[0], dict):
        spec, summary = value
        # A Conduit bridge message is bounded to 256 KiB; fail explicitly rather than break its WebView.
        if len(json.dumps(spec).encode()) > 220_000:
            raise ValueError("Resolved card exceeds the mobile host limit. Split it into smaller cards.")
        return CallToolResult(content=[TextContent(type="text", text=str(summary))], structuredContent={"spec": spec})
    return CallToolResult(content=[TextContent(type="text", text=str(value))],
                          isError=isinstance(value, str) and value.startswith("Frontier UI could not"))


owners = {}

def wrap(method):
    async def invoke(ctx: Context, **kwargs):
        token = openwebui.authorization.set((ctx.headers or {}).get("authorization", ""))
        try:
            user = await openwebui.api("/api/v1/auths/") if openwebui.BASE else {"id": "stdio"}
            if kwargs.get("card") and owners.get(kwargs["card"]) != user["id"]:
                raise PermissionError("Card is unavailable in this user's session. Render it again.")
            if "__user__" in inspect.signature(method).parameters:
                kwargs["__user__"] = user
            result = as_result(await method(**kwargs))
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
            openwebui.authorization.reset(token)
    signature = inspect.signature(method)
    invoke.__signature__ = signature.replace(parameters=[p for p in signature.parameters.values() if not p.name.startswith("__")] +
        [inspect.Parameter("ctx", inspect.Parameter.KEYWORD_ONLY, annotation=Context)], return_annotation=CallToolResult)
    invoke.__annotations__ = {p.name: p.annotation for p in invoke.__signature__.parameters.values()}
    invoke.__annotations__["return"] = CallToolResult
    invoke.__name__ = method.__name__
    return invoke


for name in ("render_frontier_ui", "craft_file", "craft_open", "save_note", "craft_read", "craft_edit", "craft_convert", "craft_commands"):
    method = getattr(tools, name)
    server.add_tool(wrap(method), name=name, description=inspect.getdoc(method),
                    meta=META if name != "craft_commands" else None,
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
