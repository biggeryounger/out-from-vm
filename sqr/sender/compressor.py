"""压缩 + Base64 编码。

纯 stdlib（gzip + base64）。zstd 可用时自动启用，否则回退 gzip。
"""
import base64
import gzip
from typing import NamedTuple, Tuple


class CompressedPayload(NamedTuple):
    """压缩 + 编码后的结果。"""

    data_b64: str          # Base64 ASCII 字符串（无换行）
    compression: str       # "gzip" | "zstd"
    encoding: str          # "base64"


def compress_and_encode(
    raw: bytes,
    use_zstd: bool = False,
) -> CompressedPayload:
    """压缩 → Base64 编码。

    Args:
        raw: 原始文件字节。
        use_zstd: True 时尝试 zstd -19，不可用则回退 gzip。
                  zstandard 是 C 扩展，不在 vendor 中——仅当系统已安装时可用。

    Returns:
        CompressedPayload(data_b64, compression, encoding)
    """
    compression: str
    compressed: bytes

    if use_zstd:
        compression, compressed = _try_zstd(raw)
    else:
        compression = "gzip"
        compressed = gzip.compress(raw, compresslevel=9)

    data_b64 = base64.b64encode(compressed).decode("ascii")
    # 防御性检查：确保无换行
    assert "\n" not in data_b64, "Base64 output contains newline"

    return CompressedPayload(
        data_b64=data_b64,
        compression=compression,
        encoding="base64",
    )


def decompress_payload(
    compressed: bytes,
    compression: str,
) -> bytes:
    """解压已 Base64 解码的压缩数据。

    Args:
        compressed: 已 Base64 解码的压缩字节（来自 assembler.assemble()）。
        compression: "gzip" | "zstd"。
    """
    if compression == "gzip":
        return gzip.decompress(compressed)
    elif compression == "zstd":
        try:
            import zstandard
        except ImportError as exc:
            raise ValueError(
                "zstd compression was used but zstandard is not installed"
            ) from exc
        return zstandard.ZstdDecompressor().decompress(compressed)
    else:
        raise ValueError(f"Unknown compression: {compression!r}")


def _try_zstd(raw: bytes) -> Tuple[str, bytes]:
    """尝试 zstd 压缩，不可用时回退 gzip。

    Returns:
        (compression_name, compressed_bytes)
    """
    try:
        import zstandard
    except ImportError:
        # 回退 gzip
        return "gzip", gzip.compress(raw, compresslevel=9)

    return "zstd", zstandard.ZstdCompressor(level=19).compress(raw)
