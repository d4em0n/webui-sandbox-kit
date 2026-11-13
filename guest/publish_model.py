"""Publish the operator's configured native model after the first admin exists."""
import asyncio
import os
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, "/app/backend")


async def publish():
    model_id = os.environ.get("DEFAULT_MODELS", "")
    if not model_id:
        return True
    database = Path("/app/backend/data/webui.db")
    try:
        with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
            row = connection.execute("SELECT id FROM user WHERE role='admin' LIMIT 1").fetchone()
    except sqlite3.OperationalError:
        return False
    if not row:
        return False
    from open_webui.models.models import ModelForm, Models
    if not await Models.get_model_by_id(model_id):
        await Models.insert_new_model(ModelForm(id=model_id, name=model_id, base_model_id=None,
            params={}, meta={}, access_grants=[{"principal_type": "user", "principal_id": "*", "permission": "read"}]), row[0])
        print("Configured default model is published for approved users", flush=True)
    return True


async def main():
    complete = False
    while True:
        if not complete:
            try:
                complete = await publish()
            except Exception as error:
                print("Default-model publication is waiting: " + type(error).__name__, flush=True)
        await asyncio.sleep(60 if complete else 5)


if __name__ == "__main__":
    asyncio.run(main())
