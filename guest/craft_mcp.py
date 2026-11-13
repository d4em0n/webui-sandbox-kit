"""Authenticated native MCP adapter for the per-user Craft engines."""
import json
import os

import aiohttp
from mcp.server.mcpserver import Context, MCPServer
from mcp.types import CallToolResult, TextContent, ToolAnnotations

server = MCPServer("Craft document tools", version="0.1.0", instructions=
    "Use craft_tools to discover the official WordCraft/PdfCraft/DeckCraft tool schemas, then craft_call. "
    "Paths are inside this user's private workspace (/home/user/Documents). Each app has a separate per-user "
    "document session, shared across that user's chats. Inspect before editing; never replay ambiguous failures.")


async def call(ctx, operation, payload):
    authorization = (ctx.headers or {}).get("authorization", "")
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=300)) as session:
        async with session.post("http://host.microsandbox.internal:18800/craft/" + operation, json=payload,
            headers={"Authorization": authorization, "X-Controller-Key": os.environ["KIT_CONTROLLER_KEY"]}) as response:
            value = await response.json()
            if response.status >= 400:
                return CallToolResult(content=[TextContent(type="text", text=value.get("error", "Craft request rejected"))], isError=True)
            if operation == "call":
                return CallToolResult.model_validate(value)
            return CallToolResult(content=[TextContent(type="text", text=json.dumps(value))])


@server.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False))
async def craft_tools(app: str, ctx: Context, search: str = "", limit: int = 15) -> CallToolResult:
    """List official tools and input schemas. app: wordcraft, pdfcraft or deckcraft; search filters the catalogue."""
    return await call(ctx, "tools", {"app": app, "search": search, "limit": limit})


@server.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, openWorldHint=False))
async def craft_call(app: str, tool: str, arguments: dict, ctx: Context) -> CallToolResult:
    """Call a discovered official Craft tool in the caller's private VM. Inspect schemas first; use absolute workspace paths."""
    return await call(ctx, "call", {"app": app, "tool": tool, "arguments": arguments})


@server.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, openWorldHint=False))
async def craft_reset(app: str, ctx: Context) -> CallToolResult:
    """Close this app's per-user document session, discarding unsaved edits. Saved workspace files remain."""
    return await call(ctx, "reset", {"app": app})


if __name__ == "__main__":
    server.run(transport="streamable-http", host="127.0.0.1", port=8083,
               stateless_http=True, json_response=True, max_request_body_size=16 * 1024 * 1024)
