#!/bin/bash
set -euo pipefail
umask 077
export OPEN_TERMINAL_API_KEY_FILE=/run/open-terminal-config/api-key
export OPEN_TERMINAL_ENABLE_BROWSER=true
export OPEN_TERMINAL_BROWSER_MODE=managed
export OPEN_TERMINAL_BROWSER_NO_SANDBOX=false
export OPEN_TERMINAL_ENABLE_DESKTOP=false
export OPEN_TERMINAL_ENABLE_NOTEBOOKS=false
export OPEN_TERMINAL_FILE_BROWSER_ROOT=home
export OPEN_TERMINAL_START_DIR=Documents
export OPEN_TERMINAL_CORS_ALLOWED_ORIGINS="$(python -c 'import json; print(json.load(open("/run/open-terminal-ops/settings.json"))["public_url"])')"
export PATH=/opt/craft/bin:$PATH
export OPEN_TERMINAL_INFO='Private persistent workspace with a sandboxed Chromium browser and WordCraft, PdfCraft and DeckCraft CLI tools. Save downloadable files under /home/user/Documents. Public HTTP/HTTPS is available; private networks, host services and metadata are blocked.'
mkdir -p /home/user/Documents /home/user/.local/bin
cd /home/user
python /run/open-terminal-ops/prepare-browser.py
exec python -m open_terminal run --host 0.0.0.0 --port 8000 --isolated
