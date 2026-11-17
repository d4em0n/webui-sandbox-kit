"""Package verified public Craft web releases, preserving their notices and fonts."""
import gzip
import json
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
import zipfile

from fetch_assets import ROOT, download


def fetch(destination):
    versions = json.loads((ROOT / "versions.lock.json").read_text())["craft_web"]
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        temporary = Path(temporary)
        for app, asset in versions.items():
            archive = temporary / (app + ".zip")
            download(asset, archive)
            with zipfile.ZipFile(archive) as source:
                for member in source.infolist():
                    path = PurePosixPath(member.filename)
                    if path.is_absolute() or ".." in path.parts or stat.S_ISLNK(member.external_attr >> 16):
                        raise ValueError("Unexpected web release entry")
                source.extractall(temporary / app)
            target = destination / app / asset["version"]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(temporary / app / (app + "-web-" + asset["version"]), target)
            for path in target.rglob("*"):
                if path.suffix in (".wasm", ".js", ".css"):
                    path.with_name(path.name + ".gz").write_bytes(gzip.compress(path.read_bytes(), mtime=0))
    (destination / "apps.json").write_text(json.dumps({
        app: "/craft/" + app + "/" + asset["version"] + "/index.html" for app, asset in versions.items()
    }))


if __name__ == "__main__":
    import sys
    fetch(Path(sys.argv[1]))
