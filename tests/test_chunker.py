"""sqr.sender.chunker 单元测试。

覆盖：分片边界、CRC 正确性、manifest 帧构建、build_all_frames 端到端。
"""
from __future__ import annotations

import pytest

from sqr.protocol import (
    Chunk,
    FileManifest,
    FrameType,
    MANIFEST_INDEX,
    compute_crc32,
    compute_file_id,
    compute_md5,
    compute_sha256,
)
from sqr.sender.chunker import (
    build_all_frames,
    build_manifest,
    build_manifest_frame,
    chunk_payload,
)
from sqr.sender.compressor import CompressedPayload


# ===========================================================================
# 辅助函数
# ===========================================================================


def _make_compressed(data_b64: str) -> CompressedPayload:
    return CompressedPayload(
        data_b64=data_b64,
        compression="gzip",
        encoding="base64",
    )


def _make_real_payload(text: str, max_chars: int = 1200):
    """从文本生成真实的压缩 payload 和元数据。"""
    raw = text.encode("utf-8")
    sha256 = compute_sha256(raw)
    md5 = compute_md5(raw)
    file_id = compute_file_id(sha256)
    return raw, sha256, md5, file_id


# ===========================================================================
# chunk_payload
# ===========================================================================


class TestChunkPayload:
    def test_single_chunk(self):
        compressed = _make_compressed("ABC")
        chunks = chunk_payload(compressed, "fid", max_chars=1200)
        assert len(chunks) == 1
        assert chunks[0].index == 1
        assert chunks[0].total == 1
        assert chunks[0].payload == "ABC"

    def test_empty_payload(self):
        compressed = _make_compressed("")
        chunks = chunk_payload(compressed, "fid", max_chars=1200)
        assert len(chunks) == 1
        assert chunks[0].index == 1
        assert chunks[0].total == 1
        assert chunks[0].payload == ""

    def test_exact_division(self):
        compressed = _make_compressed("A" * 300)
        chunks = chunk_payload(compressed, "fid", max_chars=100)
        assert len(chunks) == 3
        for i, chunk in enumerate(chunks):
            assert chunk.index == i + 1
            assert chunk.total == 3
            assert len(chunk.payload) == 100

    def test_remainder(self):
        compressed = _make_compressed("A" * 305)
        chunks = chunk_payload(compressed, "fid", max_chars=100)
        assert len(chunks) == 4  # ceil(305/100) = 4
        assert chunks[0].total == 4
        assert len(chunks[3].payload) == 5  # 最后一片 5 字符

    def test_one_char_remainder(self):
        compressed = _make_compressed("A" * 301)
        chunks = chunk_payload(compressed, "fid", max_chars=100)
        assert len(chunks) == 4
        assert len(chunks[3].payload) == 1

    def test_crc_correctness(self):
        compressed = _make_compressed("test_payload_data")
        chunks = chunk_payload(compressed, "fid", max_chars=5)
        for chunk in chunks:
            assert chunk.crc32 == compute_crc32(chunk.payload)
            assert chunk.verify_crc() is True

    def test_file_id_propagation(self):
        compressed = _make_compressed("data")
        chunks = chunk_payload(compressed, "my_file_id_", max_chars=1200)
        for chunk in chunks:
            assert chunk.file_id == "my_file_id_"

    def test_sequential_indices(self):
        compressed = _make_compressed("X" * 500)
        chunks = chunk_payload(compressed, "fid", max_chars=100)
        for i, chunk in enumerate(chunks):
            assert chunk.index == i + 1

    def test_all_chunks_same_total(self):
        compressed = _make_compressed("X" * 500)
        chunks = chunk_payload(compressed, "fid", max_chars=100)
        totals = {c.total for c in chunks}
        assert len(totals) == 1

    def test_payload_concatenation(self):
        """拼接所有 payload 应等于原始 Base64。"""
        original = "ABCDEFGHIJKLMNOP" * 50
        compressed = _make_compressed(original)
        chunks = chunk_payload(compressed, "fid", max_chars=100)
        restored = "".join(c.payload for c in chunks)
        assert restored == original


# ===========================================================================
# build_manifest
# ===========================================================================


class TestBuildManifest:
    def test_basic_manifest(self):
        compressed = _make_compressed("data")
        manifest = build_manifest(
            "test.txt", b"raw data", "a" * 64, "b" * 32, compressed
        )
        assert manifest.schema_version == 1
        assert manifest.filename == "test.txt"
        assert manifest.original_bytes == 8  # len(b"raw data")
        assert manifest.sha256 == "a" * 64
        assert manifest.md5 == "b" * 32
        assert manifest.compression == "gzip"
        assert manifest.encoding == "base64"

    def test_none_md5(self):
        compressed = _make_compressed("data")
        manifest = build_manifest("test.txt", b"raw", "a" * 64, None, compressed)
        assert manifest.md5 is None


# ===========================================================================
# build_manifest_frame
# ===========================================================================


class TestBuildManifestFrame:
    def test_manifest_frame_index_zero(self):
        compressed = _make_compressed("data")
        manifest = build_manifest("test.txt", b"raw", "a" * 64, None, compressed)
        frame = build_manifest_frame(manifest, "a" * 12, total=5)

        assert frame.index == MANIFEST_INDEX
        assert frame.total == 5
        assert frame.file_id == "a" * 12
        assert frame.frame_type == FrameType.MANIFEST

    def test_manifest_frame_crc(self):
        compressed = _make_compressed("data")
        manifest = build_manifest("test.txt", b"raw", "a" * 64, None, compressed)
        frame = build_manifest_frame(manifest, "a" * 12, total=5)

        assert frame.verify_crc() is True

    def test_manifest_frame_payload_roundtrip(self):
        compressed = _make_compressed("data")
        manifest = build_manifest("test.txt", b"raw", "a" * 64, None, compressed)
        frame = build_manifest_frame(manifest, "a" * 12, total=5)

        decoded = FileManifest.decode_payload(frame.payload)
        assert decoded == manifest


# ===========================================================================
# build_all_frames
# ===========================================================================


class TestBuildAllFrames:
    def test_small_file(self):
        text = "Hello, EDA World!"
        raw, sha256, md5, file_id = _make_real_payload(text)

        manifest, chunks = build_all_frames(
            "test.txt", raw, sha256, md5, max_chars=1200
        )

        # chunks[0] 是 manifest，其余是 data
        assert chunks[0].index == MANIFEST_INDEX
        assert all(c.index >= 1 for c in chunks[1:])

        # manifest 的 file_id 一致
        for c in chunks:
            assert c.file_id == file_id

        # total 一致
        data_chunks = chunks[1:]
        expected_total = len(data_chunks)
        for c in chunks:
            assert c.total == expected_total

    def test_multi_chunk_file(self):
        # 使用低重复性文本确保压缩后仍有较大体积
        import random
        random.seed(42)
        lines = [f"cmd_{i}: param_{random.randint(0, 99999)} value_{random.random()}\n" for i in range(500)]
        text = "".join(lines)
        raw, sha256, md5, file_id = _make_real_payload(text)

        manifest, chunks = build_all_frames(
            "test.txt", raw, sha256, md5, max_chars=80
        )

        # 应有多帧（manifest + 至少 3 个 data 帧）
        assert len(chunks) > 4

        # 所有 CRC 通过
        for c in chunks:
            assert c.verify_crc() is True

    def test_manifest_matches_original(self):
        text = "测试数据 EDA commands\n" * 50
        raw, sha256, md5, file_id = _make_real_payload(text)

        manifest, chunks = build_all_frames(
            "commands.txt", raw, sha256, md5, max_chars=200
        )

        assert manifest.filename == "commands.txt"
        assert manifest.original_bytes == len(raw)
        assert manifest.sha256 == sha256
        assert manifest.md5 == md5

    def test_chunks_decode_roundtrip(self):
        """每个 Chunk 的 encode() → decode() 应对称。"""
        text = "Roundtrip test data.\n" * 30
        raw, sha256, md5, file_id = _make_real_payload(text)

        manifest, chunks = build_all_frames(
            "test.txt", raw, sha256, md5, max_chars=100
        )

        for chunk in chunks:
            decoded = Chunk.decode(chunk.encode())
            assert decoded == chunk

    def test_all_frames_consistent_total(self):
        text = "consistency check\n" * 80
        raw, sha256, md5, file_id = _make_real_payload(text)

        _, chunks = build_all_frames("t.txt", raw, sha256, md5, max_chars=50)

        data_total = len(chunks) - 1  # 减去 manifest
        for c in chunks:
            assert c.total == data_total

    def test_all_frames_sequential_data_indices(self):
        text = "sequential\n" * 60
        raw, sha256, md5, file_id = _make_real_payload(text)

        _, chunks = build_all_frames("t.txt", raw, sha256, md5, max_chars=50)

        data_chunks = chunks[1:]
        for i, c in enumerate(data_chunks):
            assert c.index == i + 1
