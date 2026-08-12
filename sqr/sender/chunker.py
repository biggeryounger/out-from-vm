"""分片 + CRC32 + 协议头组装。

将压缩编码后的 Base64 payload 按固定长度切片，
为每片生成 Chunk 对象（含 CRC32），并构建 manifest 帧。
"""
from __future__ import annotations

import math
from typing import List, Tuple

from sqr.protocol import (
    Chunk,
    FileManifest,
    MANIFEST_INDEX,
    compute_crc32,
    compute_file_id,
)
from sqr.sender.compressor import CompressedPayload, compress_and_encode


def build_manifest(
    filename: str,
    raw_bytes: bytes,
    sha256_hex: str,
    md5_hex: str | None,
    compressed: CompressedPayload,
) -> FileManifest:
    """构建文件元数据。"""
    return FileManifest(
        schema_version=1,
        filename=filename,
        original_bytes=len(raw_bytes),
        sha256=sha256_hex,
        md5=md5_hex,
        compression=compressed.compression,
        encoding=compressed.encoding,
    )


def chunk_payload(
    compressed: CompressedPayload,
    file_id: str,
    max_chars: int = 1200,
) -> List[Chunk]:
    """将 Base64 payload 按固定长度切片，组装数据帧。

    Args:
        compressed: 压缩编码结果。
        file_id: 12 hex chars 文件标识。
        max_chars: 单帧 payload 最大字符数。

    Returns:
        数据帧列表（index 1..N），不含 manifest。
    """
    text = compressed.data_b64

    if not text:
        # 空文件 → 单个空 payload 数据帧
        return [
            Chunk(
                file_id=file_id,
                index=1,
                total=1,
                crc32=compute_crc32(""),
                payload="",
            )
        ]

    total = math.ceil(len(text) / max_chars)
    chunks: List[Chunk] = []

    for i in range(total):
        start = i * max_chars
        end = start + max_chars
        payload = text[start:end]
        chunks.append(
            Chunk(
                file_id=file_id,
                index=i + 1,
                total=total,
                crc32=compute_crc32(payload),
                payload=payload,
            )
        )

    return chunks


def build_manifest_frame(
    manifest: FileManifest,
    file_id: str,
    total: int,
) -> Chunk:
    """构建 manifest 帧（index=0）。

    Args:
        manifest: 文件元数据。
        file_id: 12 hex chars 文件标识。
        total: 数据帧总数。
    """
    payload = manifest.encode_payload()
    return Chunk(
        file_id=file_id,
        index=MANIFEST_INDEX,
        total=total,
        crc32=compute_crc32(payload),
        payload=payload,
    )


def build_all_frames(
    filename: str,
    raw_bytes: bytes,
    sha256_hex: str,
    md5_hex: str | None,
    max_chars: int = 1200,
    use_zstd: bool = False,
) -> Tuple[FileManifest, List[Chunk]]:
    """一站式：文件字节 → (manifest, [manifest_frame, data_1, ..., data_N])。

    Args:
        filename: 原始文件名。
        raw_bytes: 原始文件字节。
        sha256_hex: 原始文件 SHA-256 (64 hex)。
        md5_hex: 原始文件 MD5 (32 hex)，可为 None。
        max_chars: 单帧 payload 最大字符数。
        use_zstd: 是否优先使用 zstd。

    Returns:
        (FileManifest, Chunk 列表)
        Chunk 列表第 0 个是 manifest 帧，其余是数据帧。
    """
    file_id = compute_file_id(sha256_hex)
    compressed = compress_and_encode(raw_bytes, use_zstd=use_zstd)
    manifest = build_manifest(filename, raw_bytes, sha256_hex, md5_hex, compressed)
    data_chunks = chunk_payload(compressed, file_id, max_chars)
    manifest_frame = build_manifest_frame(manifest, file_id, len(data_chunks))

    all_chunks: List[Chunk] = [manifest_frame] + data_chunks
    return manifest, all_chunks
