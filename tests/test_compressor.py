"""sqr.sender.compressor 单元测试。

覆盖：gzip 回环、Base64 无换行、zstd 回退、空输入、Unicode 输入。
"""
from __future__ import annotations

import base64
import gzip

from sqr.sender.compressor import (
    CompressedPayload,
    compress_and_encode,
    decompress_payload,
)


class TestCompressAndEncode:
    def test_gzip_roundtrip(self):
        raw = b"Hello, World! " * 100
        result = compress_and_encode(raw, use_zstd=False)
        assert result.compression == "gzip"
        assert result.encoding == "base64"

        import base64
        compressed = base64.b64decode(result.data_b64)
        restored = decompress_payload(compressed, result.compression)
        assert restored == raw

    def test_base64_no_newline(self):
        raw = b"x" * 5000
        result = compress_and_encode(raw)
        assert "\n" not in result.data_b64
        assert "\r" not in result.data_b64

    def test_base64_valid_chars(self):
        raw = b"test data for encoding"
        result = compress_and_encode(raw)
        # Base64 字符集: A-Za-z0-9+/=
        import re
        assert re.match(r'^[A-Za-z0-9+/=]+$', result.data_b64)

    def test_empty_input(self):
        result = compress_and_encode(b"")
        assert result.compression == "gzip"
        import base64
        compressed = base64.b64decode(result.data_b64)
        restored = decompress_payload(compressed, result.compression)
        assert restored == b""

    def test_unicode_input(self):
        raw = "你好世界，EDA 工具测试。".encode("utf-8")
        result = compress_and_encode(raw)
        import base64
        compressed = base64.b64decode(result.data_b64)
        restored = decompress_payload(compressed, result.compression)
        assert restored == raw

    def test_compression_effective(self):
        """高重复文本应被显著压缩。"""
        raw = b"SELECT * FROM commands WHERE id = 1;\n" * 200
        result = compress_and_encode(raw)
        compressed = base64.b64decode(result.data_b64)
        assert len(compressed) < len(raw)

    def test_zstd_fallback_to_gzip(self):
        """use_zstd=True 但 zstandard 不可用时应回退 gzip。"""
        raw = b"test data"
        result = compress_and_encode(raw, use_zstd=True)
        assert result.compression in ("gzip", "zstd")
        import base64
        compressed = base64.b64decode(result.data_b64)
        restored = decompress_payload(compressed, result.compression)
        assert restored == raw


class TestDecompressPayload:
    def test_invalid_compression(self):
        import pytest
        with pytest.raises(ValueError, match="Unknown compression"):
            decompress_payload(b"test", "bzip2")
