"""Explicit, disposable-stack API integration checks using the QA mock provider.

This creates test accounts and files. Never point it at a personal/production database.
It requires the operator to pass --disposable and stores test credentials privately.
"""
import argparse
import json
import secrets
from pathlib import Path
import time
import urllib.error
import urllib.request


class QA:
    def __init__(self, base, directory):
        self.base, self.directory = base.rstrip("/"), directory
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        directory.chmod(0o700)
        path = directory / "credentials.json"
        self.credentials = json.loads(path.read_text()) if path.exists() else {}
        self.results = []

    def api(self, path, body=None, token=None, method=None, raw=False, timeout=300):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = "Bearer " + token
        request = urllib.request.Request(self.base + path, data=json.dumps(body).encode() if body is not None else None,
                                         headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read() if raw else json.load(response)
        except urllib.error.HTTPError as error:
            message = error.read().decode(errors="replace")[:500]
            raise RuntimeError(f"HTTP {error.code}: {message}") from error

    def save(self):
        path = self.directory / "credentials.json"
        path.write_text(json.dumps(self.credentials, indent=2))
        path.chmod(0o600)

    def check(self, name, action):
        try:
            action()
            self.results.append({"name": name, "status": "passed"})
        except Exception as error:
            self.results.append({"name": name, "status": "failed", "message": str(error)[:500]})
        (self.directory / "tests.json").write_text(json.dumps(self.results, indent=2) + "\n")

    def accounts(self):
        owner = self.credentials.get("admin") or {"email": "kit-admin@example.com", "password": secrets.token_urlsafe(24), "name": "Kit QA Admin"}
        if "admin" not in self.credentials:
            self.credentials["admin"] = owner
            self.save()
            response = self.api("/api/v1/auths/signup", owner)
        else:
            response = self.api("/api/v1/auths/signin", {"email": owner["email"], "password": owner["password"]})
        owner.update(response)
        self.save()
        for key, role in [("one", "user"), ("two", "user"), ("pending", "pending")]:
            if key not in self.credentials:
                user = {"email": f"kit-qa-{key}@example.com", "password": secrets.token_urlsafe(24),
                        "name": "Kit QA " + key, "role": role}
                self.credentials[key] = user
                self.save()
                created = self.api("/api/v1/auths/add", user, owner["token"])
                user.update(created)
            user = self.credentials[key]
            if role == "user":
                response = self.api("/api/v1/auths/signin", {"email": user["email"], "password": user["password"]})
                user.update(response)
            self.save()

    def configuration(self):
        token = self.credentials["admin"]["token"]
        models = self.api("/api/v1/configs/models", token=token)
        assert set(models["DEFAULT_MODEL_METADATA"]["toolIds"]) >= {"server:mcp:frontier", "server:mcp:craft"}
        assert models["DEFAULT_MODEL_METADATA"]["terminalId"] == "workspace"
        servers = self.api("/api/v1/configs/tool_servers", token=token)["TOOL_SERVER_CONNECTIONS"]
        assert all(server["auth_type"] == "session" for server in servers)

    def completion(self):
        token = self.credentials["one"]["token"]
        for _ in range(30):
            models = self.api("/api/models", token=token)
            if any(item["id"] == "qa-model" for item in models["data"]):
                break
            time.sleep(1)
        else:
            raise AssertionError("Configured default model was not published for the normal user")
        result = self.api("/api/chat/completions", {"model": "qa-model", "stream": False,
            "messages": [{"role": "user", "content": "Verify the independent model connection."}]}, token)
        assert "independent sandbox kit" in json.dumps(result)

    def terminal_files(self):
        for name in ["one", "two"]:
            token = self.credentials[name]["token"]
            # First use may pull the official OCI image; wait for recovery without replaying a mutation.
            deadline = time.monotonic() + 1200
            while True:
                try:
                    self.api("/api/v1/terminals/workspace/files/list?directory=Documents", token=token)
                    break
                except Exception:
                    if time.monotonic() >= deadline:
                        raise
                    time.sleep(3)
            self.api("/api/v1/terminals/workspace/files/write", {"path": "Documents/isolation.txt", "content": name}, token)
        for name in ["one", "two"]:
            result = self.api("/api/v1/terminals/workspace/files/read?path=Documents/isolation.txt", token=self.credentials[name]["token"])
            assert name in json.dumps(result)
            assert ("two" if name == "one" else "one") not in json.dumps(result)

    def browser(self):
        token = self.credentials["one"]["token"]
        result = self.api("/api/v1/terminals/workspace/browser/action", {"actions": [{"action": "navigate", "url": "https://example.com"}]}, token)
        assert "Example Domain" in json.dumps(result)
        screenshot = self.api("/api/v1/terminals/workspace/browser/screenshot", token=token, raw=True)
        assert screenshot.startswith(b"\x89PNG")
        (self.directory / "browser.png").write_bytes(screenshot)

    def mcp_discovery(self):
        for identifier in ["frontier", "craft"]:
            tools = self.api("/api/v1/tools/id/server:mcp:" + identifier + "/specs", token=self.credentials["one"]["token"])
            assert "render_frontier_ui" in json.dumps(tools) if identifier == "frontier" else "craft_call" in json.dumps(tools)

    def run(self):
        for name, action in [("Fresh admin and approved/pending accounts", self.accounts),
            ("Global native Terminal and session-authenticated MCP defaults", self.configuration),
            ("Normal-user model discovery and completion via independent mock", self.completion),
            ("Automatic per-user provisioning and persistent file separation", self.terminal_files),
            ("Native browser navigation and screenshot through WebUI", self.browser),
            ("Native Frontier/Craft MCP discovery for a normal user", self.mcp_discovery)]:
            self.check(name, action)
        print(json.dumps(self.results, indent=2))
        return all(item["status"] == "passed" for item in self.results)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--disposable", action="store_true", required=True)
    args = parser.parse_args()
    raise SystemExit(not QA(args.base_url, args.state_dir).run())
