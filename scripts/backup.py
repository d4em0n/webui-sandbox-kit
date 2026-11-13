"""Consistent stopped-stack archives with per-file hashes and guarded extraction."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tarfile

EXCLUDE = {"controller/runtime", "controller/logs", "controller/backups", "backups"}


def entries(source):
    for directory, directories, files in os.walk(source, followlinks=False):
        root = Path(directory)
        kept = []
        for name in directories:
            path = root / name
            if path.relative_to(source).as_posix() not in EXCLUDE:
                kept.append(name)
                yield path
        directories[:] = kept
        for name in files:
            yield root / name


def digest(stream):
    result = hashlib.sha256()
    while chunk := stream.read(1024 * 1024):
        result.update(chunk)
    return result.hexdigest()


def create(source, destination, uid, gid):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive = destination / ("webui-sandbox-kit-" + stamp + ".tar.gz")
    manifest = {"format": 1, "files": {}}
    with tarfile.open(archive, "w:gz", compresslevel=3, dereference=False) as output:
        for path in entries(source):
            relative = path.relative_to(source).as_posix()
            if any(relative == prefix or relative.startswith(prefix + "/") for prefix in EXCLUDE):
                continue
            if path.is_file() and not path.is_symlink():
                with path.open("rb") as stream:
                    manifest["files"][relative] = digest(stream)
            if path.is_file() or path.is_dir() or path.is_symlink():
                member = output.gettarinfo(path, arcname=relative)
                # Store hard-linked files independently without following symlinks.
                if member.islnk():
                    member.type, member.linkname, member.size = tarfile.REGTYPE, "", path.stat().st_size
                if member.isfile():
                    with path.open("rb") as stream:
                        output.addfile(member, stream)
                else:
                    output.addfile(member)
    manifest_path = Path(str(archive) + ".json")
    with archive.open("rb") as stream:
        manifest["archive_sha256"] = digest(stream)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    for path in [archive, manifest_path]:
        path.chmod(0o600)
        os.chown(path, uid, gid)
    verify(archive)
    print(json.dumps({"archive": archive.name, "files": len(manifest["files"]), "verified": True}))


def verify(archive):
    manifest = json.loads(Path(str(archive) + ".json").read_text())
    if manifest.get("format") != 1:
        raise ValueError("Unsupported backup format")
    with archive.open("rb") as stream:
        if digest(stream) != manifest["archive_sha256"]:
            raise ValueError("Backup archive digest mismatch")
    seen = set()
    names = set()
    with tarfile.open(archive) as source:
        for member in source:
            # Reject duplicates, special files, absolute paths and escaping links.
            if member.name in names or not (member.isfile() or member.isdir() or member.issym()):
                raise ValueError("Invalid archive entry")
            names.add(member.name)
            if Path(member.name).is_absolute() or ".." in Path(member.name).parts:
                raise ValueError("Unsafe archive path")
            if member.isfile():
                if digest(source.extractfile(member)) != manifest["files"].get(member.name):
                    raise ValueError("Backup file digest mismatch")
                seen.add(member.name)
    if seen != set(manifest["files"]):
        raise ValueError("Backup manifest does not match archive contents")
    return manifest


def restore(archive, destination, uid=None, gid=None):
    verify(archive)
    links = []

    def confined(member, path):
        # Create links only after all regular files, so they cannot redirect writes.
        if member.issym():
            links.append((member.name, member.linkname))
            return None
        filtered = tarfile.data_filter(member, path)
        if filtered and not member.issym():
            filtered.uid, filtered.gid = member.uid, member.gid
            if uid is not None and (member.name == "controller" or member.name.startswith("controller/")):
                filtered.uid, filtered.gid = uid, gid
        return filtered

    with tarfile.open(archive) as source:
        source.extractall(destination, filter=confined)
    root = destination.resolve()
    for name, target in links:
        path = destination / name
        if not path.parent.resolve().is_relative_to(root):
            raise ValueError("Backup symlink parent escapes destination")
        path.symlink_to(target)
    print(json.dumps({"restored": True}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["create", "verify", "restore"])
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path, nargs="?")
    parser.add_argument("--uid", type=int, default=os.getuid())
    parser.add_argument("--gid", type=int, default=os.getgid())
    args = parser.parse_args()
    if args.action == "create":
        create(args.source, args.destination, args.uid, args.gid)
    elif args.action == "verify":
        value = verify(args.source)
        print(json.dumps({"verified": True, "files": len(value["files"])}))
    else:
        restore(args.source, args.destination, args.uid, args.gid)
