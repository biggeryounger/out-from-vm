"""Validate and safely restore directory bundles."""
import hashlib
import json
import os
import shutil
import tempfile
import zipfile
from io import BytesIO
from pathlib import Path, PurePosixPath

from sqr.bundle.builder import BUNDLE_INDEX_NAME


DEFAULT_MAX_ENTRIES = 100000
DEFAULT_MAX_EXPANDED_BYTES = 2 * 1024 * 1024 * 1024
DEFAULT_MAX_INDEX_BYTES = 16 * 1024 * 1024


def is_directory_bundle(data):
    if not data.startswith(b"PK\x03\x04"):
        return False
    try:
        with zipfile.ZipFile(BytesIO(data), "r") as archive:
            return BUNDLE_INDEX_NAME in archive.namelist()
    except (OSError, zipfile.BadZipFile):
        return False


def _safe_parts(path):
    if not isinstance(path, str) or not path or "\x00" in path or "\\" in path:
        raise ValueError("unsafe bundle path: %r" % path)
    pure = PurePosixPath(path)
    if pure.is_absolute() or any(part in ("", ".", "..") for part in pure.parts):
        raise ValueError("unsafe bundle path: %r" % path)
    if pure.parts and ":" in pure.parts[0]:
        raise ValueError("unsafe bundle path: %r" % path)
    return pure.parts


def _load_index(archive, max_entries, max_expanded_bytes):
    names = archive.namelist()
    if len(names) != len(set(names)):
        raise ValueError("bundle contains duplicate ZIP paths")
    if BUNDLE_INDEX_NAME not in names:
        raise ValueError("bundle index is missing")
    if archive.getinfo(BUNDLE_INDEX_NAME).file_size > DEFAULT_MAX_INDEX_BYTES:
        raise ValueError("bundle index is too large")
    try:
        index = json.loads(archive.read(BUNDLE_INDEX_NAME).decode("utf-8"))
    except (UnicodeDecodeError, ValueError, KeyError) as exc:
        raise ValueError("invalid bundle index: %s" % exc)
    if index.get("schema_version") != 1 or index.get("kind") != "directory":
        raise ValueError("unsupported bundle index schema")
    entries = index.get("entries")
    if not isinstance(entries, list) or len(entries) > max_entries:
        raise ValueError("invalid or excessive bundle entry count")
    root_name = index.get("root_name")
    root_parts = _safe_parts(root_name)
    if len(root_parts) != 1:
        raise ValueError("bundle root_name must be one path component")

    expected_zip_names = {BUNDLE_INDEX_NAME}
    seen_paths = set()
    total_bytes = 0
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("invalid bundle entry")
        path = entry.get("path")
        parts = _safe_parts(path)
        if parts[0] != root_name or path in seen_paths:
            raise ValueError("bundle entry is outside root or duplicated: %r" % path)
        seen_paths.add(path)
        entry_type = entry.get("type")
        if entry_type == "directory":
            expected_zip_names.add(path.rstrip("/") + "/")
        elif entry_type == "file":
            size = entry.get("size")
            digest = entry.get("sha256")
            if not isinstance(size, int) or size < 0:
                raise ValueError("invalid file size for %s" % path)
            if not isinstance(digest, str) or len(digest) != 64:
                raise ValueError("invalid file digest for %s" % path)
            total_bytes += size
            expected_zip_names.add(path)
            if path not in names or archive.getinfo(path).file_size != size:
                raise ValueError("ZIP file size does not match bundle index: %s" % path)
        else:
            raise ValueError("unsupported bundle entry type: %r" % entry_type)
    if total_bytes > max_expanded_bytes:
        raise ValueError("bundle expands beyond configured byte limit")
    if set(names) != expected_zip_names:
        raise ValueError("ZIP contents do not match bundle index")
    if index.get("entry_count") != len(entries):
        raise ValueError("bundle entry_count does not match entries")
    if index.get("file_count") != sum(1 for entry in entries if entry["type"] == "file"):
        raise ValueError("bundle file_count does not match entries")
    if index.get("directory_count") != sum(1 for entry in entries if entry["type"] == "directory"):
        raise ValueError("bundle directory_count does not match entries")
    if index.get("total_file_bytes") != total_bytes:
        raise ValueError("bundle total_file_bytes does not match entries")
    return index


def extract_directory_bundle(
    data,
    output_parent,
    max_entries=DEFAULT_MAX_ENTRIES,
    max_expanded_bytes=DEFAULT_MAX_EXPANDED_BYTES,
):
    """Validate, extract to a staging directory, then atomically publish the root."""
    output_parent = Path(output_parent)
    output_parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".sqr-partial-", dir=str(output_parent)))
    try:
        with zipfile.ZipFile(BytesIO(data), "r") as archive:
            index = _load_index(archive, max_entries, max_expanded_bytes)
            root_name = index["root_name"]
            for entry in index["entries"]:
                target = staging.joinpath(*_safe_parts(entry["path"]))
                if entry["type"] == "directory":
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                payload = archive.read(entry["path"])
                if len(payload) != entry["size"]:
                    raise ValueError("file size mismatch: %s" % entry["path"])
                digest = hashlib.sha256(payload).hexdigest()
                if digest != entry["sha256"]:
                    raise ValueError("file SHA-256 mismatch: %s" % entry["path"])
                target.write_bytes(payload)

        staged_root = staging / root_name
        final_root = output_parent / root_name
        if final_root.exists():
            raise FileExistsError("restore target already exists: %s" % final_root)
        os.replace(str(staged_root), str(final_root))
        return final_root
    finally:
        shutil.rmtree(str(staging), ignore_errors=True)
