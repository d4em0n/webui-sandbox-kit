"""Generate isolated instance state and native Open WebUI integration defaults."""
import json
import shutil
from urllib.parse import urlparse, urlunparse

from .settings import CODE, DATA, atomic_json, load_settings, secret


GRANTS = [{"principal_type": "user", "principal_id": "*", "permission": "read"}]


def prepare(data=DATA):
    data.mkdir(parents=True, exist_ok=True, mode=0o700)
    data.chmod(0o700)
    for name in ["config", "webui/data", "webui/config", "terminal/manager", "terminal/config",
                 "terminal/private", "terminal/ops", "runtime", "logs", "backups"]:
        directory = data / name
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        directory.chmod(0o700)
    settings = load_settings(data)
    public = urlparse(settings["public_url"])
    origins = [settings["public_url"].rstrip("/")]
    if public.hostname in ("localhost", "127.0.0.1"):
        for hostname in ["localhost", "127.0.0.1"]:
            authority = hostname + (":" + str(public.port) if public.port else "")
            origins.append(urlunparse((public.scheme, authority, "", "", "", "")))
    if not (data / "config/settings.json").exists():
        atomic_json(data / "config/settings.json", settings)
    key = secret("terminal-key", data)
    secret("webui-secret", data)
    secret("firecrawl-key", data)
    (data / "terminal/config/api-key").write_text(key + "\n")
    (data / "terminal/config/api-key").chmod(0o600)
    for source, target in [("guest/terminal-start.sh", "guest-start.sh"),
                           ("controller/prepare_browser.py", "prepare-browser.py"),
                           ("controller/workspace-guidelines.md", "workspace-guidelines.md"),
                           ("guest/craft_job.py", "craft_job.py")]:
        shutil.copyfile(CODE / source, data / "terminal/ops" / target)
    shutil.copyfile(CODE / "guest/frontier_craft_bridge.py", data / "terminal/ops/frontier_craft_bridge.py")
    for source in (CODE / "controller/schema").iterdir():
        shutil.copyfile(source, data / "terminal/manager" / source.name)
    atomic_json(data / "terminal/ops/settings.json", {"public_url": settings["public_url"]})
    versions = json.loads((CODE / "versions.lock.json").read_text())
    atomic_json(data / "terminal/manager/config.json", {
        "max_users": settings["max_users"], "cpus": settings["user_cpus"],
        "memoryMiB": settings["user_memory_mib"], "image": versions["images"]["terminal"],
        "public_web": True, "auto_browser": True, "identity_in_guest": True,
        "root_disk_gib": settings["root_disk_gib"],
        "terminal_id": settings["terminal_id"],
    })
    terminal = {"id": settings["terminal_id"], "name": "My Workspace", "enabled": True,
                "url": "http://host.microsandbox.internal:18800", "path": "/openapi.json",
                "key": key, "auth_type": "bearer", "server_type": "terminal", "forward_cookies": False,
                "config": {"working_directory_context": True, "user_shell_tools": "auto", "access_grants": GRANTS}}
    tools = [{"url": f"http://127.0.0.1:{port}/mcp", "path": "", "type": "mcp",
              "auth_type": "session", "key": "", "config": {"enable": True, "access_grants": GRANTS},
              "info": {"id": name, "name": label, "description": label}}
             for port, name, label in [(8081, "frontier", "Frontier UI"), (8083, "craft", "Craft document tools")]]
    provider_key = data / "config/provider-key"
    env = {
        "HOME": "/app/backend/data/home", "HF_HOME": "/app/backend/data/cache/huggingface",
        "STATIC_DIR": "/app/backend/data/static",
        "WEBUI_SECRET_KEY": secret("webui-secret", data), "WEBUI_URL": settings["public_url"],
        "CORS_ALLOW_ORIGIN": ";".join(dict.fromkeys(origins)),
        "WEBUI_SESSION_COOKIE_SECURE": str(public.scheme == "https").lower(),
        "WEBUI_AUTH_COOKIE_SECURE": str(public.scheme == "https").lower(),
        "DO_NOT_TRACK": "true", "ANONYMIZED_TELEMETRY": "false",
        "ENABLE_VERSION_UPDATE_CHECK": "false", "ENABLE_EVALUATION_ARENA_MODELS": "false",
        "ENABLE_FORWARD_USER_INFO_HEADERS": "false",
        "ENABLE_SIGNUP": str(settings["signup"]).lower(), "DEFAULT_USER_ROLE": "pending",
        "ENABLE_OLLAMA_API": "false", "OPENAI_API_BASE_URLS": settings["provider_url"],
        "OPENAI_API_KEYS": provider_key.read_text().strip() if provider_key.exists() else "",
        "AIOHTTP_POOL_DNS_TTL": "0", "ENABLE_TOOL_SERVERS": "true",
        "SSL_CERT_FILE": "/etc/ssl/certs/ca-certificates.crt",
        "REQUESTS_CA_BUNDLE": "/etc/ssl/certs/ca-certificates.crt",
        "TOOL_SERVER_CONNECTIONS": json.dumps(tools), "TERMINAL_SERVER_CONNECTIONS": json.dumps([terminal]),
        "DEFAULT_MODEL_METADATA": json.dumps({"toolIds": ["server:mcp:frontier", "server:mcp:craft"],
            "terminalId": settings["terminal_id"], "capabilities": {"terminal": True, "file_upload": True, "web_search": True, "builtin_tools": True},
            "builtinTools": {"memory": True, "knowledge": True}, "defaultFeatureIds": ["web_search"]}),
        "DEFAULT_MODEL_PARAMS": json.dumps({"function_calling": "native", "system":
            "Use Frontier UI for interactive visuals. Use the private workspace for browser, code and file work. "
            "WordCraft, PdfCraft and DeckCraft are available through Craft tools or their CLI commands. "
            "Discover tool schemas with craft_tools before craft_call. Save documents under /home/user/Documents. "
            "Each Craft app maintains a separate document session for this user; do not assume another app has the same document open."}),
        "ENABLE_MEMORIES": "true", "ENABLE_MEMORY_BACKGROUND_REVIEW": "true",
        "DEFAULT_INTERFACE_SETTINGS": json.dumps({"memory": True}),
        "USER_PERMISSIONS_WORKSPACE_KNOWLEDGE_ACCESS": "true", "USER_PERMISSIONS_FEATURES_AUTOMATIONS": "true",
        "ENABLE_WEB_SEARCH": str(settings["firecrawl"]).lower(), "WEB_SEARCH_ENGINE": "firecrawl",
        "WEB_LOADER_ENGINE": "firecrawl", "FIRECRAWL_API_KEY": secret("firecrawl-key", data),
        "FIRECRAWL_API_BASE_URL": "http://host.microsandbox.internal:18800/firecrawl",
        "BYPASS_WEB_SEARCH_EMBEDDING_AND_RETRIEVAL": "true", "ENABLE_AUTOMATIONS": "true",
        "KIT_CONTROLLER_KEY": key, "KIT_PUBLIC_URL": settings["public_url"],
        "KIT_LOCAL_SPEECH": str(settings["local_speech"]).lower(),
    }
    if settings["default_model"]:
        env["DEFAULT_MODELS"] = settings["default_model"]
    if settings["local_speech"]:
        if (data / "webui/data/models/faster-whisper-base").is_dir():
            env.update(WHISPER_MODEL="/app/backend/data/models/faster-whisper-base",
                       WHISPER_COMPUTE_TYPE="int8", WHISPER_MODEL_AUTO_UPDATE="false")
        speech_key = data / "webui/config/speech-api-key"
        if not speech_key.exists():
            speech_key.write_text(secret("speech-key", data) + "\n")
            speech_key.chmod(0o600)
    atomic_json(data / "webui/config/environment.json", env)
    frontier = data / "webui/config/frontier.json"
    if not frontier.exists():
        atomic_json(frontier, {"embedding_url": "", "page_screenshots": False, "units": "metric"})
    return settings
