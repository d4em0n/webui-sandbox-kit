"""Run inside the disposable WebUI VM. Test tokens arrive only through stdin."""
import asyncio
import json
import sys
import traceback

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

results = []


async def checked(name, action):
    try:
        await action()
        results.append({"name": name, "status": "passed"})
    except Exception as error:
        traceback.print_exception(error, file=sys.stderr)
        results.append({"name": name, "status": "failed", "message": str(error)[:500]})


def parsed(result):
    if result.structured_content:
        return result.structured_content
    return json.loads(next(item.text for item in result.content if item.type == "text"))


async def request(port, token, action):
    async with httpx2.AsyncClient(headers={"Authorization": "Bearer " + token}, timeout=180) as http:
        async with Client(streamable_http_client(f"http://127.0.0.1:{port}/mcp", http_client=http)) as client:
            return await action(client)


async def main(credentials):
    async def documents(client):
        async def call(app, tool, arguments):
            value = await client.call_tool("craft_call", {"app": app, "tool": tool, "arguments": arguments})
            assert not value.is_error, str(value)
            return value
        catalogue = await client.call_tool("craft_tools", {"app": "wordcraft", "search": "new document"})
        assert "new_document" in str(catalogue)
        await call("wordcraft", "new_document", {"template": "blank"})
        await call("wordcraft", "type_text", {"text": "Independent Kit MCP Document"})
        await call("wordcraft", "save_document", {"path": "/home/user/Documents/craft.docx"})
        await call("wordcraft", "save_document", {"path": "/home/user/Documents/craft-word.pdf"})
        denied = await client.call_tool("craft_call", {"app": "wordcraft", "tool": "save_document", "arguments": {"path": "/tmp/outside.docx"}})
        assert denied.is_error
        await call("deckcraft", "new_presentation", {"blank": True})
        await call("deckcraft", "add_slide", {"title": "Independent Kit", "body": "Private presentation", "layout": "titleAndContent"})
        await call("deckcraft", "save_presentation", {"path": "/home/user/Documents/craft.pptx"})
        pdf = parsed(await call("pdfcraft", "doc_create", {"from": "text", "text": "Independent Kit PDF"}))
        doc = pdf.get("doc", pdf.get("id"))
        await call("pdfcraft", "doc_save", {"doc": doc, "path": "/home/user/Documents/craft.pdf"})
        await call("pdfcraft", "page_rotate", {"doc": doc, "degrees": 90})
        await call("pdfcraft", "doc_save", {"doc": doc, "path": "/home/user/Documents/craft-rotated.pdf"})

    async def separate(client):
        value = await client.call_tool("craft_call", {"app": "wordcraft", "tool": "new_document", "arguments": {"template": "blank"}})
        assert not value.is_error
        value = await client.call_tool("craft_call", {"app": "wordcraft", "tool": "get_text", "arguments": {}})
        assert not value.is_error and "Independent Kit MCP Document" not in str(value)
        value = await client.call_tool("craft_call", {"app": "wordcraft", "tool": "open_document", "arguments": {"path": "/home/user/Documents/craft.docx"}})
        assert value.is_error

    async def exports(client):
        value = await client.call_tool("render_frontier_ui", {"spec": {"title": "Kit Export", "blocks": [{"type": "text", "md": "Portable document export"}]}})
        assert not value.is_error
        card = value.structured_content["spec"]["_ui"]["card"]
        resource = (await client.read_resource("ui://frontier/ui.html")).contents[0]
        assert resource.mime_type == "text/html;profile=mcp-app" and "ui/initialize" in resource.text
        for extension in ["docx", "pdf", "pptx", "xlsx"]:
            value = await client.call_tool("craft_file", {"format": extension, "card": card,
                **({"rows_json": '[["Item","Cost"],["Train",1000]]'} if extension == "xlsx" else {})})
            assert not value.is_error and value.structured_content, str(value)
            assert "spec" not in value.structured_content
            value = await client.call_tool("craft_display", {"path": value.structured_content["path"]})
            assert not value.is_error and value.structured_content, str(value)
            file = value.structured_content["spec"]["blocks"][0]
            assert file["type"] == "file" and file["size"] > 0
        return card

    async def denied(client):
        value = await client.call_tool("craft_tools", {"app": "wordcraft"})
        assert value.is_error

    await checked("Craft HTTP-to-stdio MCP creates DOCX/PDF/PPTX and rejects outside-root writes",
                  lambda: request(8083, credentials["one"]["token"], documents))
    await checked("Craft active documents and saved files are separated between users",
                  lambda: request(8083, credentials["two"]["token"], separate))
    await checked("Frontier native MCP App resource and DOCX/PDF/PPTX/XLSX export cards",
                  lambda: request(8081, credentials["one"]["token"], exports))
    await checked("Craft rejects an invalid caller session",
                  lambda: request(8083, "invalid-test-session", denied))
    print(json.dumps(results, indent=2))
    return all(item["status"] == "passed" for item in results)


if __name__ == "__main__":
    raise SystemExit(not asyncio.run(main(json.load(sys.stdin))))
