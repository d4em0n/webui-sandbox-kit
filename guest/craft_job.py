"""Run Frontier's existing file converters in one user's VM, without an HTTP daemon."""
import csv
import base64
import json
import os
import sys
from pathlib import Path

os.environ["PATH"] = "/opt/craft/bin:" + os.environ.get("PATH", "")
import frontier_craft_bridge as bridge


def make_sheet(body, directory, output):
    rows = ([body["columns"]] if body.get("columns") else []) + (body.get("rows") or [])
    if output.endswith(".csv"):
        with open(output, "w", newline="") as stream:
            csv.writer(stream).writerows(rows)
    elif output.endswith(".xlsx"):
        from openpyxl import Workbook
        workbook = Workbook()
        for row in rows:
            workbook.active.append(row)
        workbook.save(output)
    else:
        raise ValueError("Spreadsheet exports support XLSX/CSV; use the workspace tools for other formats")


def main(operation, body):
    if not isinstance(body, dict):
        raise ValueError("Expected a JSON object")
    bridge.APPS = ["wordcraft", "pdfcraft", "deckcraft"]
    bridge.MAKERS["sheet"] = make_sheet
    if operation == "make":
        body = {**body, "open": False}
        return bridge.H.make(None, body)
    if operation == "inspect":
        result = bridge.inspect_file(body)
        if body.get("inbox"):
            result["path"] = save_file(body["name"], base64.b64decode(body["b64"]))
        return result
    if operation in ("edit", "convert"):
        result = {"edit": bridge.edit_file, "convert": bridge.convert_file}[operation](body)
        result["path"] = save_file(result["name"], base64.b64decode(result["b64"]))
        return result
    if operation == "file":
        path = Path(body["path"])
        if not path.is_absolute() or not path.resolve().is_relative_to(Path(bridge.HOME).resolve()):
            raise ValueError("Use an absolute file path inside /home/user.")
        path = path.resolve(strict=True)
        if not path.is_file():
            raise ValueError("Path must be a regular workspace file.")
        limit = 10 * 1024 * 1024  # Base64 plus JSON must fit the existing 16 MiB bridge frame.
        if path.stat().st_size > limit:
            raise ValueError("Workspace file exceeds the 10 MiB display limit.")
        with path.open("rb") as stream:
            data = stream.read(limit + 1)
        if len(data) > limit:
            raise ValueError("Workspace file exceeds the 10 MiB display limit.")
        return {"path": str(path), "name": path.name, "b64": base64.b64encode(data).decode(),
                "mime": bridge.MIME.get(path.suffix[1:].lower(), "application/octet-stream")}
    if operation == "commands":
        if body.get("app") not in bridge.APPS:
            raise ValueError("This package includes WordCraft, PdfCraft and DeckCraft")
        return bridge.list_commands(body)
    raise ValueError("Desktop/editor opening is not available. Use generated file downloads and previews.")


def save_file(name, data):
    Path(bridge.INBOX).mkdir(parents=True, exist_ok=True)
    path = bridge.unique(str(Path(bridge.INBOX) / Path(name).name))
    Path(path).write_bytes(data)
    return path


if __name__ == "__main__":
    os.umask(0o077)
    try:
        result = main(sys.argv[1], json.loads(sys.stdin.buffer.read(16 * 1024 * 1024)))
    except Exception as error:
        result = {"error": str(error)[:600]}
    sys.stdout.write(json.dumps(result))
