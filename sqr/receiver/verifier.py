"""最终完整性校验：字节 / SHA-256 / MD5 / UTF-8。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqr.protocol import FileManifest, compute_md5, compute_sha256


@dataclass(frozen=True)
class VerificationResult:
    """校验结果。"""

    success: bool
    byte_count_match: bool
    sha256_match: bool
    md5_match: bool
    utf8_valid: bool
    actual_bytes: int
    actual_sha256: str
    actual_md5: str
    message: str


def verify_restored_file(
    data: bytes,
    manifest: FileManifest,
    expected_sha256: Optional[str] = None,
    expected_md5: Optional[str] = None,
    expected_bytes: Optional[int] = None,
) -> VerificationResult:
    """全量校验恢复后的文件。

    校验顺序（全部检查，不短路）：
    1. 字节数
    2. SHA-256
    3. MD5（如果 manifest 或 CLI 提供了 expected）
    4. UTF-8 严格模式解码

    Args:
        data: 恢复后的原始字节。
        manifest: 从 manifest 帧解析的文件元数据。
        expected_sha256: CLI 传入的覆盖值（优先于 manifest）。
        expected_md5: CLI 传入的覆盖值。
        expected_bytes: CLI 传入的覆盖值。

    Returns:
        VerificationResult 包含每项检查的通过/失败状态。
    """
    actual_bytes = len(data)
    actual_sha256 = compute_sha256(data)
    actual_md5 = compute_md5(data)

    ref_bytes = expected_bytes if expected_bytes is not None else manifest.original_bytes
    ref_sha256 = expected_sha256 if expected_sha256 is not None else manifest.sha256
    ref_md5 = expected_md5 if expected_md5 is not None else manifest.md5

    byte_count_match = actual_bytes == ref_bytes
    sha256_match = actual_sha256 == ref_sha256

    md5_match = True
    if ref_md5 is not None:
        md5_match = actual_md5 == ref_md5

    utf8_valid = True
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        utf8_valid = False

    failures: list[str] = []
    if not byte_count_match:
        failures.append(
            f"bytes: expected {ref_bytes}, got {actual_bytes}"
        )
    if not sha256_match:
        failures.append(
            f"sha256: expected {ref_sha256}, got {actual_sha256}"
        )
    if not md5_match:
        failures.append(
            f"md5: expected {ref_md5}, got {actual_md5}"
        )
    if not utf8_valid:
        failures.append("utf-8 decode failed")

    success = len(failures) == 0
    message = "All checks passed" if success else "; ".join(failures)

    return VerificationResult(
        success=success,
        byte_count_match=byte_count_match,
        sha256_match=sha256_match,
        md5_match=md5_match,
        utf8_valid=utf8_valid,
        actual_bytes=actual_bytes,
        actual_sha256=actual_sha256,
        actual_md5=actual_md5,
        message=message,
    )
