"""End-to-end directory → SQ1 QR images → safe restored tree."""
from pathlib import Path

from sqr.bundle.builder import BUNDLE_SUFFIX, build_directory_bundle
from sqr.protocol import compute_md5, compute_sha256
from sqr.receiver.image_decoder import run_receiver_from_images
from sqr.sender.chunker import build_all_frames
from sqr.sender.qr_render import generate_matrix, matrix_to_ppm


def _tree_snapshot(root):
    result = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        result[rel + ("/" if path.is_dir() else "")] = None if path.is_dir() else path.read_bytes()
    return result


def test_directory_qr_image_roundtrip(tmp_path):
    source = tmp_path / "project 目录"
    (source / "src" / "empty-dir").mkdir(parents=True)
    (source / "README.md").write_text("# 测试\n", encoding="utf-8")
    (source / "src" / "main.txt").write_text("print('hello')\n" * 8, encoding="utf-8")
    (source / "src" / "zero.bin").write_bytes(b"")
    (source / "binary.dat").write_bytes(bytes(range(128)))

    bundle = build_directory_bundle(source)
    sha256 = compute_sha256(bundle.data)
    md5 = compute_md5(bundle.data)
    _, chunks = build_all_frames(
        source.name + BUNDLE_SUFFIX,
        bundle.data,
        sha256,
        md5,
        max_chars=1200,
    )

    frames = tmp_path / "frames"
    frames.mkdir()
    frame_paths = []
    for chunk in chunks:
        ppm = matrix_to_ppm(generate_matrix(chunk.encode()), module_size=10)
        path = frames / ("frame_%04d.ppm" % chunk.index)
        path.write_bytes(ppm)
        frame_paths.append(path)

    output_parent = tmp_path / "received"
    result = run_receiver_from_images(frame_paths, output_parent)

    restored = output_parent / source.name
    assert result.success, result.message
    assert restored.is_dir()
    assert _tree_snapshot(restored) == _tree_snapshot(source)


def test_corrupt_outer_bundle_is_not_published(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "file.txt").write_text("content")
    bundle = build_directory_bundle(source)
    corrupt = bundle.data[:-8] + b"corrupt!"
    sha256 = compute_sha256(bundle.data)
    _, chunks = build_all_frames(
        source.name + BUNDLE_SUFFIX,
        corrupt,
        sha256,
        compute_md5(bundle.data),
        max_chars=1200,
    )
    # Force the manifest to describe the original bundle while the data is corrupt.
    manifest_chunk = chunks[0]
    from sqr.protocol import FileManifest, Chunk, compute_crc32
    manifest = FileManifest(
        1, source.name + BUNDLE_SUFFIX, len(bundle.data), sha256,
        compute_md5(bundle.data), "gzip", "base64"
    )
    payload = manifest.encode_payload()
    chunks[0] = Chunk(manifest_chunk.file_id, 0, manifest_chunk.total, compute_crc32(payload), payload)

    frames = tmp_path / "frames"
    frames.mkdir()
    paths = []
    for chunk in chunks:
        path = frames / ("frame_%04d.ppm" % chunk.index)
        path.write_bytes(matrix_to_ppm(generate_matrix(chunk.encode()), module_size=10))
        paths.append(path)

    output_parent = tmp_path / "received"
    result = run_receiver_from_images(paths, output_parent)
    assert not result.success
    assert not (output_parent / source.name).exists()
