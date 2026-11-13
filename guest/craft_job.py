"""Run Frontier's existing file converters in one user's VM, without an HTTP daemon."""
import csv
import json
import os
import sys

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
        return bridge.inspect_file(body)
    if operation == "edit":
        return bridge.edit_file(body)
    if operation == "convert":
        return bridge.convert_file(body)
    if operation == "commands":
        if body.get("app") not in bridge.APPS:
            raise ValueError("This package includes WordCraft, PdfCraft and DeckCraft")
        return bridge.list_commands(body)
    raise ValueError("Desktop/editor opening is not available. Use generated file downloads and previews.")


if __name__ == "__main__":
    os.umask(0o077)
    try:
        result = main(sys.argv[1], json.loads(sys.stdin.buffer.read(16 * 1024 * 1024)))
    except Exception as error:
        result = {"error": str(error)[:600]}
    sys.stdout.write(json.dumps(result))
