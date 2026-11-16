"""Protocol tests exercise the real Python MCP SDK without an HTTP listener."""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from mcp import Client

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import server


class ProtocolTests(unittest.IsolatedAsyncioTestCase):
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
