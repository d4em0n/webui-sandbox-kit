"""Apply kit-owned connection settings through the pinned application's native model.

Runs before the WebUI process starts. Other administrator settings stay in SQLite.
The first run is seeded by the official application after its migrations.
"""
import asyncio
import json
import os
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, "/app/backend")


async def apply():
    database = Path("/app/backend/data/webui.db")
    if not database.exists():
        return
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        if not connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='config'").fetchone():
            return
    from open_webui.models.config import Config
    values = {
        "webui.url": os.environ["WEBUI_URL"],
        "openai.api_base_urls": [os.environ["OPENAI_API_BASE_URLS"]],
        "openai.api_keys": [os.environ["OPENAI_API_KEYS"]],
        "terminal_server.connections": json.loads(os.environ["TERMINAL_SERVER_CONNECTIONS"]),
        "tool_server.connections": json.loads(os.environ["TOOL_SERVER_CONNECTIONS"]),
        "web.search.enable": os.environ["ENABLE_WEB_SEARCH"] == "true",
        "web.search.engine": "firecrawl", "web.loader.engine": "firecrawl",
        "web.loader.firecrawl_api_url": os.environ["FIRECRAWL_API_BASE_URL"],
        "web.loader.firecrawl_api_key": os.environ["FIRECRAWL_API_KEY"],
    }
    if os.environ.get("DEFAULT_MODELS"):
        values["ui.default_models"] = os.environ["DEFAULT_MODELS"]
    await Config.upsert(values)


if __name__ == "__main__":
    asyncio.run(apply())
