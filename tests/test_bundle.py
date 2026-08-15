"""Directory bundle format, integrity and safe extraction tests."""
import json
import os
import zipfile
from io import BytesIO

import pytest

from sqr.bundle.builder import BUNDLE_INDEX_NAME, build_directory_bundle
from sqr.bundle.extractor import extract_directory_bundle, is_directory_bundle


def _sample_tree(root):
    source = root / "资料 tree"
    (source / "nested" / "empty").mkdir(parents=True)
    (source / "hello.txt").write_text("hello 目录\n", encoding="utf-8")
    (source / "nested" / "empty.bin").write_bytes(b"")
    (source / "nested" / "bytes.bin").write_bytes(bytes(range(256)))
    return source


def _zip_with_index(index, members):
    stream = BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_STORED) as archive:
        archive.writestr(
            BUNDLE_INDEX_NAME,
            json.dumps(index, separators=(",", ":")).encode("utf-8"),
        )
        for name, data in members:
            archive.writestr(name, data)
    return stream.getvalue()


class TestBundleBuilder:
    def test_build_is_deterministic_and_self_describing(self, tmp_path):
        source = _sample_tree(tmp_path)
        first = build_directory_bundle(source)
        second = build_directory_bundle(source)

        assert first.data == second.data
        assert first.root_name == "资料 tree"
        assert first.file_count == 3
        assert first.directory_count == 3
        assert first.total_file_bytes == len("hello 目录\n".encode("utf-8")) + 256
        assert is_directory_bundle(first.data)

        with zipfile.ZipFile(BytesIO(first.data)) as archive:
            index = json.loads(archive.read(BUNDLE_INDEX_NAME))
            assert index["root_name"] == "资料 tree"
            assert index["entry_count"] == 6
            assert "资料 tree/nested/empty/" in archive.namelist()

    def test_rejects_symlink(self, tmp_path):
        source = tmp_path / "source"
        source.mkdir()
        target = tmp_path / "target.txt"
        target.write_text("secret")
        try:
            os.symlink(str(target), str(source / "link.txt"))
        except (OSError, NotImplementedError):
            pytest.skip("symlinks are unavailable on this platform")
        with pytest.raises(ValueError, match="symbolic links"):
            build_directory_bundle(source)


class TestBundleExtractor:
    def test_roundtrip_preserves_tree_and_bytes(self, tmp_path):
        source = _sample_tree(tmp_path / "inside")
        built = build_directory_bundle(source)
        output_parent = tmp_path / "restored"

        restored = extract_directory_bundle(built.data, output_parent)

        assert restored == output_parent / source.name
        assert (restored / "hello.txt").read_bytes() == (source / "hello.txt").read_bytes()
        assert (restored / "nested" / "bytes.bin").read_bytes() == bytes(range(256))
        assert (restored / "nested" / "empty.bin").read_bytes() == b""
        assert (restored / "nested" / "empty").is_dir()

    def test_existing_target_is_not_overwritten(self, tmp_path):
        source = _sample_tree(tmp_path / "inside")
        built = build_directory_bundle(source)
        existing = tmp_path / "out" / source.name
        existing.mkdir(parents=True)
        marker = existing / "keep.txt"
        marker.write_text("keep")

        with pytest.raises(FileExistsError):
            extract_directory_bundle(built.data, tmp_path / "out")
        assert marker.read_text() == "keep"
        assert not list((tmp_path / "out").glob(".sqr-partial-*"))

    @pytest.mark.parametrize("unsafe_path", ["../escape", "/absolute", "C:/escape", "a\\b"])
    def test_rejects_unsafe_paths(self, tmp_path, unsafe_path):
        index = {
            "schema_version": 1,
            "kind": "directory",
            "root_name": "root",
            "entry_count": 2,
            "file_count": 1,
            "directory_count": 1,
            "total_file_bytes": 1,
            "entries": [
                {"path": "root", "type": "directory"},
                {"path": unsafe_path, "type": "file", "size": 1, "sha256": "0" * 64},
            ],
        }
        data = _zip_with_index(index, [("root/", b""), (unsafe_path, b"x")])
        with pytest.raises(ValueError):
            extract_directory_bundle(data, tmp_path / "out")
        assert not (tmp_path / "escape").exists()

    def test_detects_file_digest_tampering(self, tmp_path):
        source = _sample_tree(tmp_path / "inside")
        built = build_directory_bundle(source)
        input_zip = zipfile.ZipFile(BytesIO(built.data))
        index = json.loads(input_zip.read(BUNDLE_INDEX_NAME))
        members = []
        for name in input_zip.namelist():
            if name == BUNDLE_INDEX_NAME:
                continue
            payload = input_zip.read(name)
            if name.endswith("hello.txt"):
                payload = b"tampered"
            members.append((name, payload))
        tampered = _zip_with_index(index, members)

        with pytest.raises(ValueError, match="file size|SHA-256 mismatch"):
            extract_directory_bundle(tampered, tmp_path / "out")
        assert not (tmp_path / "out" / source.name).exists()
