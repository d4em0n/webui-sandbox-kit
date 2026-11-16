"""Protocol tests exercise the real Python MCP SDK without an HTTP listener."""
import json
import base64
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from mcp import Client

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import server


class ProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def test_initialize_delivers_file_presentation_instructions(self):
        async with Client(server.server) as client:
            self.assertIn("Frontier file cards already deliver their files", client.instructions)
            self.assertIn("do not call display_file", client.instructions)
            self.assertIn("explicit request for a separate inline/sidebar display", client.instructions)

    async def test_tool_schema_and_app_metadata(self):
        async with Client(server.server) as client:
            tools = (await client.list_tools()).tools
            self.assertEqual(len(tools), 8)
            render = next(t for t in tools if t.name == "render_frontier_ui")
            schema = render.input_schema
            self.assertEqual(set(schema["properties"]), {"spec"})
            self.assertEqual(render.meta["ui"]["resourceUri"], server.URI)
            self.assertEqual(render.meta["ui"]["visibility"], ["model", "app"])
            commands = next(t for t in tools if t.name == "craft_commands")
            self.assertFalse((commands.meta or {}).get("ui"))
            self.assertTrue(all(t.meta == server.META for t in tools if t.name != "craft_commands"))

    async def test_command_lookup_returns_text_without_an_app(self):
        with patch.object(server.frontier, "_bridge_call", new_callable=AsyncMock) as bridge:
            bridge.return_value = {"commands": "text.insert: Insert text"}
            async with Client(server.server) as client:
                result = await client.call_tool("craft_commands", {"app": "wordcraft", "search": "insert"})
                self.assertFalse(result.is_error)
                self.assertIsNone(result.structured_content)
                self.assertIn("text.insert", result.content[0].text)

    async def test_file_preview_links_only_identify_supported_local_files(self):
        base = "https://webui.example"
        blocks = [{"type": "file", "format": fmt, "url": base + "/api/v1/files/synthetic-id/content"}
                  for fmt in ("pdf", "docx", "pptx", "xlsx", "xls", "png")]
        blocks += [{"type": "file", "format": "docx", "url": url} for url in (
            "https://other.example/api/v1/files/synthetic-id/content",
            base + "/api/v1/files/synthetic-id/content?token=untrusted",
            base + "/api/v1/files/../content",
            None,
        )]
        with patch.object(server.openwebui, "PUBLIC", base):
            spec = await server.tools._card({"blocks": blocks})
        for block in spec["blocks"][:5]:
            self.assertEqual(block["preview_url"], base + "/document-preview/?file_id=synthetic-id")
            self.assertEqual(block["url"], base + "/api/v1/files/synthetic-id/content")
        self.assertTrue(all("preview_url" not in block for block in spec["blocks"][5:]))

    async def test_created_and_edited_files_share_preview_and_download_card(self):
        base = "https://webui.example"
        url = base + "/api/v1/files/synthetic-id/content"
        data = base64.b64encode(b"Synthetic document").decode()
        with patch.object(server.openwebui, "PUBLIC", base), \
             patch.object(server.frontier, "_bridge_call", new_callable=AsyncMock) as bridge, \
             patch.object(server.frontier, "_store_file", new_callable=AsyncMock, return_value=("synthetic-id", url)), \
             patch.object(server.frontier, "_load_file", new_callable=AsyncMock,
                          return_value=("Synthetic.docx", b"Original", "original-id")):
            bridge.side_effect = [
                {"name": "Synthetic.docx", "b64": data, "app": "wordcraft"},
                {"name": "Synthetic edited.docx", "b64": data, "app": "wordcraft"},
                {"preview": "synthetic-thumbnail"},
            ]
            async with Client(server.server) as client:
                created = await client.call_tool("craft_file", {"format": "docx", "markdown": "Synthetic content"})
                edited = await client.call_tool("craft_edit", {"file": "Synthetic.docx", "replace_json": '{"Original":"Edited"}'})
            for result in (created, edited):
                self.assertFalse(result.is_error)
                self.assertIn("Do not call display_file", result.content[0].text)
                block = result.structured_content["spec"]["blocks"][0]
                self.assertEqual(block["preview_url"], base + "/document-preview/?file_id=synthetic-id")
                self.assertEqual(block["url"], url)
            self.assertEqual(edited.structured_content["spec"]["blocks"][0]["preview"],
                             "data:image/jpeg;base64,synthetic-thumbnail")

    async def test_duplicate_display_guidance_only_applies_to_file_cards(self):
        spec = {"blocks": [{"type": "file", "name": "Synthetic.csv", "url": "https://webui.example/file"}]}
        result = server.as_result((spec, "File created."))
        self.assertEqual(result.structured_content, {"spec": spec})
        self.assertTrue(result.content[0].text.startswith("File created."))
        self.assertIn("Do not call display_file", result.content[0].text)
        self.assertIn("unless the user explicitly requests", result.content[0].text)
        for value in (({"blocks": [{"type": "text", "md": "Hello"}]}, "Card shown."),
                      "Frontier UI could not create the file", "Command lookup text"):
            result = server.as_result(value)
            self.assertEqual(result.content[0].text, value[1] if isinstance(value, tuple) else value)
            self.assertEqual(bool(result.is_error), isinstance(value, str) and value.startswith("Frontier UI could not"))

    async def test_resolver_reused_and_structured_result(self):
        fixture = json.loads((ROOT.parents[1] / "tests/kyoto.json").read_text())
        with patch.object(server.frontier, "_resolve", new_callable=AsyncMock) as resolve:
            async with Client(server.server) as client:
                result = await client.call_tool("render_frontier_ui", {"spec": fixture})
                self.assertFalse(result.is_error)
                self.assertEqual(result.structured_content["spec"]["title"], fixture["title"])
                self.assertNotIn("<html", result.content[0].text)
                self.assertEqual(len(result.structured_content["spec"]["blocks"]), 6)
                resolve.assert_awaited_once()

    async def test_resource_mime_csp_and_bundled_sdk(self):
        async with Client(server.server) as client:
            resource = (await client.read_resource(server.URI)).contents[0]
            self.assertEqual(resource.mime_type, server.MIME)
            self.assertIn("https://tiles.openfreemap.org", resource.meta["ui"]["csp"]["connectDomains"])
            self.assertNotIn('Content-Security-Policy', resource.text)
            self.assertNotIn("input:prompt:submit", resource.text)
            self.assertIn("ui/initialize", resource.text)

    async def test_oversized_result_fails_explicitly(self):
        with self.assertRaisesRegex(ValueError, "mobile host limit"):
            server.as_result(({"title": "x" * 220001}, "large"))

    async def test_no_service_secrets_in_result(self):
        with patch.object(server.frontier, "_resolve", new_callable=AsyncMock):
            async with Client(server.server) as client:
                result = await client.call_tool("render_frontier_ui", {"spec": {"title": "Safe", "blocks": [{"type": "text", "md": "Hello"}]}})
                output = result.model_dump_json()
                self.assertNotIn("craft_bridge_token", output)
                self.assertNotIn("embedding_api_key", output)

    async def test_card_actions_cannot_cross_users(self):
        with patch.object(server.openwebui, "BASE", "http://webui.invalid"), \
             patch.object(server.openwebui, "api", new_callable=AsyncMock) as api, \
             patch.object(server.frontier, "_resolve", new_callable=AsyncMock):
            api.return_value = {"id": "synthetic-owner"}
            async with Client(server.server) as client:
                card = await client.call_tool("render_frontier_ui", {"spec": {"title": "Private test card", "blocks": [{"type": "text", "md": "Synthetic content"}]}})
                card_id = card.structured_content["spec"]["_ui"]["card"]
                api.return_value = {"id": "another-synthetic-user"}
                denied = await client.call_tool("save_note", {"card": card_id})
                self.assertTrue(denied.is_error)
                self.assertIn("unavailable", denied.content[0].text)

if __name__ == "__main__":
    unittest.main()
