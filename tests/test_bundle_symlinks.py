"""Directory bundle symlink exclusion tests."""
import os
import zipfile
from io import BytesIO

import pytest

from sqr.bundle.builder import build_directory_bundle
from sqr.bundle.extractor import extract_directory_bundle


def _make_symlink(target, link):
    try:
        os.symlink(str(target), str(link))
    except (OSError, NotImplementedError) as exc:
        pytest.skip("symlinks are unavailable on this platform: %s" % exc)


def test_internal_file_and_directory_symlinks_are_skipped(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("must not be transferred")

    source = tmp_path / "source"
    source.mkdir()
    (source / "regular.txt").write_text("keep")
    _make_symlink(outside / "secret.txt", source / "linked-file.txt")
    _make_symlink(outside, source / "linked-directory")

    built = build_directory_bundle(source)

    assert built.skipped_symlink_count == 2
    assert built.file_count == 1
    with zipfile.ZipFile(BytesIO(built.data)) as archive:
        names = set(archive.namelist())
    assert "source/regular.txt" in names
    assert "source/linked-file.txt" not in names
    assert "source/linked-directory/" not in names
    assert not any("secret.txt" in name for name in names)

    restored = extract_directory_bundle(built.data, tmp_path / "restored")
    assert (restored / "regular.txt").read_text() == "keep"
    assert not (restored / "linked-file.txt").exists()
    assert not (restored / "linked-directory").exists()


def test_symlink_root_is_still_rejected(tmp_path):
    real_root = tmp_path / "real-root"
    real_root.mkdir()
    linked_root = tmp_path / "linked-root"
    _make_symlink(real_root, linked_root)

    with pytest.raises(ValueError, match="root must not be a symlink"):
        build_directory_bundle(linked_root)


def test_regex_never_includes_a_matching_symlink(tmp_path):
    outside = tmp_path / "outside.tcl"
    outside.write_text("secret")
    source = tmp_path / "source"
    source.mkdir()
    (source / "keep.tcl").write_text("keep")
    _make_symlink(outside, source / "linked.tcl")

    built = build_directory_bundle(source, include_regexes=[r"\.tcl$"])

    assert built.skipped_symlink_count == 1
    assert built.file_count == 1
    with zipfile.ZipFile(BytesIO(built.data)) as archive:
        assert "source/keep.tcl" in archive.namelist()
        assert "source/linked.tcl" not in archive.namelist()
