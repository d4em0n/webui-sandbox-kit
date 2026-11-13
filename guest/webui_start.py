"""Supervise the official application and its independent MCP adapters."""
import json
import os
from pathlib import Path
import signal
import subprocess
import time

os.umask(0o077)
os.environ.update(json.loads(Path("/run/kit-config/environment.json").read_text()))
os.environ.update(OPENWEBUI_BASE_URL="http://127.0.0.1:8080", OPENWEBUI_PUBLIC_URL=os.environ["KIT_PUBLIC_URL"],
                  FRONTIER_VALVES_FILE="/run/kit-config/frontier.json")
for name in ["HOME", "HF_HOME"]:
    Path(os.environ[name]).mkdir(parents=True, exist_ok=True)
subprocess.run(["python", "/run/kit/guest/apply_config.py"], cwd="/app/backend", check=True)
children = []


def cleanup(*_):
    for process in children:
        if process.poll() is None:
            process.terminate()
    deadline = time.monotonic() + 10
    for process in children:
        try:
            process.wait(timeout=max(.1, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            process.kill()
    raise SystemExit(1)


signal.signal(signal.SIGTERM, cleanup)
signal.signal(signal.SIGINT, cleanup)
for command, cwd in [(["python", "/run/kit/frontier/mcp-apps/server.py"], "/app/backend"),
                     (["python", "/run/kit/guest/craft_mcp.py"], "/app/backend"),
                     (["python", "/run/kit/guest/publish_model.py"], "/app/backend"),
                     (["bash", "start.sh"], "/app/backend")]:
    children.append(subprocess.Popen(command, cwd=cwd))
while all(process.poll() is None for process in children):
    time.sleep(1)
cleanup()
