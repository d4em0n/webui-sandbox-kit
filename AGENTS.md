# WebUI Sandbox Kit

This repository is an independent distributable. Do not read or import an operator's
other application databases, credentials, DNS, reverse proxies or existing runtime.
Use a separate Compose project, data directory and localhost port for QA.

Keep Open WebUI/Open Terminal core images and `frontier/frontier_ui.py` unchanged.
Host adaptation belongs in the controller or MCP adapters. Preserve upstream notices.
Do not commit `.env`, instance data, credentials, reports containing sessions, or images.

Run `python3 -m unittest discover -s tests -v` for unit/security checks.
Full integration QA needs Linux/amd64, Docker Compose and `/dev/kvm`.
Changes to proxy authentication need isolation and HTTP/WebSocket regression checks.
Never replay document/browser mutations automatically after ambiguous failures.
