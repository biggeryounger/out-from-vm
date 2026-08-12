"""sqr.protocol 单元测试。

覆盖：Chunk encode/decode 对称性、错误拒绝、CRC 校验、
FileManifest encode/decode、纯函数。
"""
from __future__ import annotations

import pytest

from sqr.protocol import (
    PROTOCOL_VERSION,
    Chunk,
    FileManifest,
    FrameType,
    MANIFEST_INDEX,
    ProtocolError,
    compute_crc32,
    compute_file_id,
    compute_md5,
    compute_sha256,
)


# ===========================================================================
# 纯函数
# ===========================================================================


class TestComputeFileId:
    def test_takes_first_12_chars(self):
        sha256 = "a" * 64
        assert compute_file_id(sha256) == "a" * 12

    def test_short_hash(self):
        assert compute_file_id("abc123") == "abc123"


class TestComputeCrc32:
    def test_empty_string(self):
        assert compute_crc32("") == 0

    def test_empty_bytes(self):
        assert compute_crc32(b"") == 0

    def test_known_value(self):
        # CRC32 of "hello" via binascii（标准 zlib 多项式）
        import binascii
        expected = binascii.crc32(b"hello") & 0xFFFFFFFF
        assert compute_crc32("hello") == expected

    def test_str_and_bytes_match(self):
        assert compute_crc32("abc") == compute_crc32(b"abc")

    def test_unsigned(self):
        """确保返回值始终为 unsigned 32-bit。"""
        # 这个值在某些实现中会产生负数
        data = b"\x00" * 100
        result = compute_crc32(data)
        assert 0 <= result <= 0xFFFFFFFF


class TestComputeHashes:
    def test_sha256_known(self):
        assert (
            compute_sha256(b"")
            == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        )

    def test_md5_known(self):
        assert compute_md5(b"") == "d41d8cd98f00b204e9800998ecf8427e"


# ===========================================================================
# Chunk encode / decode
# ===========================================================================


class TestChunkEncodeDecode:
    def test_encode_format(self):
        chunk = Chunk(
            file_id="a1b2c3d4e5f6",
            index=3,
            total=10,
            crc32=0x0A1B2C3D,
            payload="SGVsbG8=",
        )
        encoded = chunk.encode()
        assert encoded == "SQ1|a1b2c3d4e5f6|3|10|0a1b2c3d|SGVsbG8="

    def test_roundtrip_data_frame(self):
        original = Chunk(
            file_id="abcdef012345",
            index=5,
            total=8,
            crc32=compute_crc32("test_payload"),
            payload="test_payload",
        )
        decoded = Chunk.decode(original.encode())
        assert decoded == original

    def test_roundtrip_manifest_frame(self):
        original = Chunk(
            file_id="abcdef012345",
            index=MANIFEST_INDEX,
            total=8,
            crc32=compute_crc32("manifest_data"),
            payload="manifest_data",
        )
        decoded = Chunk.decode(original.encode())
        assert decoded == original

    def test_roundtrip_empty_payload(self):
        original = Chunk(
            file_id="abcdef012345",
            index=1,
            total=1,
            crc32=0,
            payload="",
        )
        decoded = Chunk.decode(original.encode())
        assert decoded == original

    def test_payload_with_pipe_not_split(self):
        """payload 中的 | 不应被误切（maxsplit 保护）。"""
        payload_with_pipe = "abc|def|ghi"
        original = Chunk(
            file_id="abcdef012345",
            index=1,
            total=1,
            crc32=compute_crc32(payload_with_pipe),
            payload=payload_with_pipe,
        )
        decoded = Chunk.decode(original.encode())
        assert decoded.payload == payload_with_pipe


class TestChunkDecodeErrors:
    def test_wrong_version(self):
        raw = "SQ2|abcdef012345|1|1|00000000|payload"
        with pytest.raises(ProtocolError, match="version"):
            Chunk.decode(raw)

    def test_too_few_fields(self):
        raw = "SQ1|abcdef012345|1|1|00000000"
        with pytest.raises(ProtocolError, match="fields"):
            Chunk.decode(raw)

    def test_too_many_separators_maxsplit_protects(self):
        """6 个 | 时，payload 获取最后一个 | 之后的部分。"""
        # 这实际上还是 6 个字段，payload 含 |
        raw = "SQ1|abcdef012345|1|1|00000000|pay|load"
        chunk = Chunk.decode(raw)
        assert chunk.payload == "pay|load"

    def test_non_numeric_index(self):
        raw = "SQ1|abcdef012345|abc|1|00000000|payload"
        with pytest.raises(ProtocolError, match="index"):
            Chunk.decode(raw)

    def test_non_numeric_total(self):
        raw = "SQ1|abcdef012345|1|xyz|00000000|payload"
        with pytest.raises(ProtocolError, match="total"):
            Chunk.decode(raw)

    def test_non_hex_crc32(self):
        raw = "SQ1|abcdef012345|1|1|zzzzzzzz|payload"
        with pytest.raises(ProtocolError, match="crc32"):
            Chunk.decode(raw)

    def test_empty_string(self):
        with pytest.raises(ProtocolError):
            Chunk.decode("")


class TestChunkCrc:
    def test_verify_crc_correct(self):
        payload = "SGVsbG8gV29ybGQ="
        chunk = Chunk(
            file_id="abcdef012345",
            index=1,
            total=1,
            crc32=compute_crc32(payload),
            payload=payload,
        )
        assert chunk.verify_crc() is True

    def test_verify_crc_wrong(self):
        chunk = Chunk(
            file_id="abcdef012345",
            index=1,
            total=1,
            crc32=0xDEADBEEF,  # 故意错误
            payload="SGVsbG8=",
        )
        assert chunk.verify_crc() is False

    def test_crc_zero_padding(self):
        """CRC32=0 应编码为 00000000。"""
        chunk = Chunk(
            file_id="abcdef012345",
            index=1,
            total=1,
            crc32=0,
            payload="",
        )
        assert "00000000" in chunk.encode()


class TestChunkFrameType:
    def test_manifest_frame_type(self):
        chunk = Chunk(
            file_id="abcdef012345",
            index=MANIFEST_INDEX,
            total=5,
            crc32=0,
            payload="",
        )
        assert chunk.frame_type == FrameType.MANIFEST

    def test_data_frame_type(self):
        chunk = Chunk(
            file_id="abcdef012345",
            index=1,
            total=5,
            crc32=0,
            payload="",
        )
        assert chunk.frame_type == FrameType.DATA

    def test_data_frame_type_last(self):
        chunk = Chunk(
            file_id="abcdef012345",
            index=5,
            total=5,
            crc32=0,
            payload="",
        )
        assert chunk.frame_type == FrameType.DATA


# ===========================================================================
# FileManifest encode / decode
# ===========================================================================


class TestFileManifest:
    def _make_manifest(self, md5: str | None = None) -> FileManifest:
        return FileManifest(
            schema_version=1,
            filename="test.txt",
            original_bytes=29816,
            sha256="a" * 64,
            md5=md5,
            compression="gzip",
            encoding="base64",
        )

    def test_roundtrip_with_md5(self):
        manifest = self._make_manifest(md5="b" * 32)
        payload = manifest.encode_payload()
        decoded = FileManifest.decode_payload(payload)
        assert decoded == manifest

    def test_roundtrip_without_md5(self):
        manifest = self._make_manifest(md5=None)
        payload = manifest.encode_payload()
        decoded = FileManifest.decode_payload(payload)
        assert decoded == manifest
        assert decoded.md5 is None

    def test_encoded_payload_is_base64(self):
        manifest = self._make_manifest()
        payload = manifest.encode_payload()
        # Base64 字符集检查
        import re
        assert re.match(r'^[A-Za-z0-9+/=]+$', payload), "Payload is not valid Base64"

    def test_encoded_payload_no_newline(self):
        manifest = self._make_manifest()
        payload = manifest.encode_payload()
        assert "\n" not in payload
        assert "\r" not in payload

    def test_decode_invalid_base64(self):
        with pytest.raises(ProtocolError, match="Invalid manifest"):
            FileManifest.decode_payload("!!!not-base64!!!")

    def test_decode_missing_fields(self):
        import base64
        import json
        incomplete = base64.b64encode(
            json.dumps({"v": 1, "fn": "test"}).encode()
        ).decode("ascii")
        with pytest.raises(ProtocolError, match="missing"):
            FileManifest.decode_payload(incomplete)

    def test_unicode_filename(self):
        manifest = FileManifest(
            schema_version=1,
            filename="中文文件名.txt",
            original_bytes=100,
            sha256="c" * 64,
            md5=None,
            compression="gzip",
            encoding="base64",
        )
        decoded = FileManifest.decode_payload(manifest.encode_payload())
        assert decoded.filename == "中文文件名.txt"
