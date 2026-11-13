"""Download only pinned public releases, verify digests, extract without executing installers."""
import hashlib
import json
import shutil
from pathlib import Path
import tarfile
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def download(asset, path):
    request = urllib.request.Request(asset["url"], headers={"User-Agent": "webui-sandbox-kit/0.1"})
    digest = hashlib.sha256()
    with urllib.request.urlopen(request, timeout=120) as response, path.open("wb") as stream:
        while chunk := response.read(1024 * 1024):
            digest.update(chunk)
            stream.write(chunk)
    if digest.hexdigest() != asset["sha256"]:
        raise ValueError("Release checksum mismatch: " + asset["url"])


def fetch(destination):
    versions = json.loads((ROOT / "versions.lock.json").read_text())
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        temporary = Path(temporary)
        archive = temporary / "release.tar.gz"
        download(versions["microsandbox"], archive)
        runtime = destination / "microsandbox"
        (runtime / "bin").mkdir(parents=True, exist_ok=True)
        (runtime / "lib").mkdir(exist_ok=True)
        with tarfile.open(archive) as source:
            source.extractall(temporary / "runtime", filter="data")
        shutil.copy2(temporary / "runtime/msb", runtime / "bin/msb")
        firmware = next((temporary / "runtime").glob("libkrunfw.so.*"))
        shutil.copy2(firmware, runtime / "lib" / firmware.name)
        for name in ["libkrunfw.so", "libkrunfw.so.5"]:
            (runtime / "lib" / name).symlink_to(firmware.name)
        craft = destination / "craft"
        (craft / "bin").mkdir(parents=True, exist_ok=True)
        for app, asset in versions["craft"].items():
            download(asset, archive)
            target = temporary / app
            with tarfile.open(archive) as source:
                source.extractall(target, filter="data")
            binary = next(target.rglob(app + "-cli"))
            install = craft / app / "bin"
            install.mkdir(parents=True, exist_ok=True)
            shutil.copy2(binary, install / binary.name)
            (craft / "bin" / binary.name).symlink_to(f"../{app}/bin/{binary.name}")
            licenses = craft / app / "licenses"
            licenses.mkdir()
            for item in target.rglob("*"):
                if item.is_file() and (item.name.startswith(("LICENSE", "NOTICE", "OFL-"))):
                    shutil.copy2(item, licenses / item.name)


if __name__ == "__main__":
    import sys
    fetch(Path(sys.argv[1]))
