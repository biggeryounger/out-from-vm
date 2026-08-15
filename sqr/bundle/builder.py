"""Build a deterministic, self-describing directory bundle using stdlib ZIP."""
import hashlib
import json
import os
import re
import stat
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Dict, List, NamedTuple


BUNDLE_SUFFIX = ".sqrbundle"
BUNDLE_INDEX_NAME = ".sqr-bundle.json"
_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


class BundleBuildResult(NamedTuple):
    data: bytes
    root_name: str
    file_count: int
    directory_count: int
    total_file_bytes: int


def _zip_info(name, is_dir=False):
    info = zipfile.ZipInfo(name, _ZIP_TIMESTAMP)
    info.compress_type = zipfile.ZIP_STORED
    info.create_system = 3
    mode = (stat.S_IFDIR | 0o755) if is_dir else (stat.S_IFREG | 0o644)
    info.external_attr = mode << 16
    if is_dir:
        info.external_attr |= 0x10
    return info


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _validate_component(name):
    if not name or name in (".", "..") or "\x00" in name or "\\" in name or ":" in name:
        raise ValueError("unsafe directory bundle path component: %r" % name)


def build_directory_bundle(source, include_regexes=None):
    """Return a deterministic bundle for *source* without exposing absolute paths.

    Only regular files and directories are accepted. Symlinks and special files
    are rejected because recreating them safely across platforms is ambiguous.
    If include_regexes is non-empty, a file is included when re.search against
    its basename matches any expression; only required ancestor dirs are kept.
    """
    source = Path(source)
    if not source.is_dir():
        raise ValueError("directory bundle source is not a directory: %s" % source)
    if source.is_symlink():
        raise ValueError("directory bundle root must not be a symlink: %s" % source)

    root_name = source.name
    _validate_component(root_name)

    try:
        patterns = [re.compile(value) for value in (include_regexes or [])]
    except re.error as exc:
        raise ValueError("invalid include regex: %s" % exc)

    entries = []  # type: List[Dict[str, object]]
    payloads = {}  # type: Dict[str, bytes]
    directory_paths = {root_name}

    for current, dir_names, file_names in os.walk(str(source), followlinks=False):
        current_path = Path(current)
        dir_names.sort()
        file_names.sort()

        for name in list(dir_names):
            _validate_component(name)
            path = current_path / name
            if path.is_symlink():
                raise ValueError("symbolic links are not supported: %s" % path)
            mode = path.stat().st_mode
            if not stat.S_ISDIR(mode):
                raise ValueError("special filesystem entry is not supported: %s" % path)
            rel = path.relative_to(source).as_posix()
            if not patterns:
                directory_paths.add(root_name + "/" + rel)

        for name in file_names:
            _validate_component(name)
            path = current_path / name
            if path.is_symlink():
                raise ValueError("symbolic links are not supported: %s" % path)
            before = path.stat()
            if not stat.S_ISREG(before.st_mode):
                raise ValueError("special filesystem entry is not supported: %s" % path)
            if patterns and not any(pattern.search(name) for pattern in patterns):
                continue
            data = path.read_bytes()
            after = path.stat()
            if before.st_size != after.st_size or before.st_mtime_ns != after.st_mtime_ns:
                raise ValueError("file changed while bundle was being created: %s" % path)
            rel = root_name + "/" + path.relative_to(source).as_posix()
            parent_parts = rel.split("/")[:-1]
            for depth in range(1, len(parent_parts) + 1):
                directory_paths.add("/".join(parent_parts[:depth]))
            payloads[rel] = data
            entries.append({
                "path": rel,
                "type": "file",
                "size": len(data),
                "sha256": _sha256(data),
            })

    entries.extend(
        {"path": path, "type": "directory"} for path in directory_paths
    )
    entries.sort(key=lambda entry: str(entry["path"]))
    file_count = sum(1 for entry in entries if entry["type"] == "file")
    directory_count = sum(1 for entry in entries if entry["type"] == "directory")
    total_bytes = sum(int(entry.get("size", 0)) for entry in entries)
    index = {
        "schema_version": 1,
        "kind": "directory",
        "root_name": root_name,
        "entry_count": len(entries),
        "file_count": file_count,
        "directory_count": directory_count,
        "total_file_bytes": total_bytes,
        "entries": entries,
    }
    index_bytes = json.dumps(
        index, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")

    stream = BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr(_zip_info(BUNDLE_INDEX_NAME), index_bytes)
        for entry in entries:
            name = str(entry["path"])
            if entry["type"] == "directory":
                archive.writestr(_zip_info(name.rstrip("/") + "/", is_dir=True), b"")
            else:
                archive.writestr(_zip_info(name), payloads[name])

    return BundleBuildResult(
        stream.getvalue(), root_name, file_count, directory_count, total_bytes
    )
