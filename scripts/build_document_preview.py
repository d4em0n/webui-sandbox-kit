"""Compile unmodified, pinned WebUI preview components into the adapter page."""
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tarfile
import tempfile

from fetch_assets import download

ROOT = Path(__file__).resolve().parents[1]


def build():
    pin = json.loads((ROOT / "versions.lock.json").read_text())["document_preview"]
    viewer = ROOT / "document-preview"
    upstream = viewer / ".upstream"
    with tempfile.TemporaryDirectory() as temporary:
        temporary = Path(temporary)
        archive = temporary / "source.tar.gz"
        download(pin, archive)
        with tarfile.open(archive) as source:
            for member in source.getmembers():
                path = PurePosixPath(member.name)
                if path.is_absolute() or ".." in path.parts or not (member.isfile() or member.isdir()):
                    raise ValueError("Unexpected source archive entry")
            source.extractall(temporary / "source")
        if upstream.exists():
            shutil.rmtree(upstream)
        shutil.move(temporary / "source" / ("open-webui-" + pin["revision"]), upstream)
    subprocess.run(["npm", "ci", "--ignore-scripts", "--no-audit", "--no-fund"], cwd=upstream, check=True)
    modules = viewer / "node_modules"
    if not modules.exists():
        modules.symlink_to(".upstream/node_modules", target_is_directory=True)
    subprocess.run(["node", "node_modules/@sveltejs/kit/svelte-kit.js", "sync"], cwd=upstream, check=True)
    subprocess.run(["npm", "run", "build"], cwd=viewer, check=True,
                   env={**os.environ, "WEBUI_SOURCE": str(upstream)})
    notices = viewer / "dist/licenses"
    for name in ("LICENSE", "LICENSE_HISTORY"):
        notices.mkdir(parents=True, exist_ok=True)
        if (upstream / name).is_dir():
            shutil.copytree(upstream / name, notices / name)
        else:
            shutil.copy2(upstream / name, notices / name)
    for source in (upstream / "node_modules").rglob("*"):
        if source.is_file() and source.name.upper().startswith(("LICENSE", "NOTICE", "COPYING")):
            destination = notices / "npm" / source.relative_to(upstream / "node_modules")
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)


if __name__ == "__main__":
    build()
