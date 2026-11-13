"""Installation configuration and atomic persistent files."""
import json
import os
import secrets
from pathlib import Path
from urllib.parse import urlparse

DATA = Path(os.environ.get("KIT_DATA", "/data"))
CODE = Path(__file__).resolve().parents[1]


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_suffix(".tmp")
    with temporary.open("w") as stream:
        stream.write(json.dumps(value, indent=2) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.chmod(0o600)
    temporary.replace(path)


def load_settings(data=DATA):
    defaults = {
        "public_url": "http://localhost:3000",
        "provider_url": "https://api.openai.com/v1",
        "provider_allow_private": False,
        "default_model": "",
        "webui_cpus": 4,
        "webui_memory_mib": 4096,
        "user_cpus": 2,
        "user_memory_mib": 2048,
        "max_users": 2,
        "signup": False,
        "firecrawl": True,
        "firecrawl_url": "http://firecrawl-api:3002",
        "root_disk_gib": 30,
    }
    path = data / "config/settings.json"
    if path.exists():
        value = json.loads(path.read_text())
        if not isinstance(value, dict):
            raise ValueError("settings.json must contain an object")
        unknown = set(value) - set(defaults)
        if unknown:
            raise ValueError("Unknown configuration settings: " + ", ".join(sorted(unknown)))
        defaults.update(value)
    for name in ["public_url", "provider_url", "firecrawl_url"]:
        if not isinstance(defaults[name], str) or any(ord(char) < 32 for char in defaults[name]):
            raise ValueError(f"{name} must be a URL string without control characters")
        url = urlparse(defaults[name])
        if url.scheme not in ("http", "https") or not url.hostname or url.username or url.password:
            raise ValueError(f"{name} must be an HTTP(S) URL without embedded credentials")
        if name == "public_url" and (url.path not in ("", "/") or url.query or url.fragment):
            raise ValueError("public_url must be an origin without a subpath, query or fragment")
    for name in ["webui_cpus", "webui_memory_mib", "user_cpus", "user_memory_mib", "max_users", "root_disk_gib"]:
        if type(defaults[name]) is not int or defaults[name] <= 0:
            raise ValueError(f"{name} must be a positive integer")
    for name in ["signup", "firecrawl", "provider_allow_private"]:
        if type(defaults[name]) is not bool:
            raise ValueError(f"{name} must be a boolean")
    if not isinstance(defaults["default_model"], str) or any(char.isspace() for char in defaults["default_model"]):
        raise ValueError("default_model must be a single model ID or an empty string")
    return defaults


def secret(name, data=DATA):
    path = data / "config" / name
    if not path.exists():
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            stream.write(secrets.token_urlsafe(48) + "\n")
    return path.read_text().strip()
