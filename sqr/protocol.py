"""SQ1 协议：分片帧编解码、文件元数据、校验函数。

纯 stdlib，发送端和接收端共用。
"""
import base64
import binascii
import hashlib
import json
from enum import IntEnum
from typing import Any, Dict, NamedTuple, Optional, Union

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

PROTOCOL_VERSION: str = "SQ1"
FIELD_SEPARATOR: str = "|"
DEFAULT_MAX_PAYLOAD_CHARS: int = 1200
DEFAULT_ERROR_CORRECTION: str = "M"
DEFAULT_QUIET_ZONE_MODULES: int = 4
MANIFEST_INDEX: int = 0

# 预期帧字段数: version | file_id | index | total | crc32 | payload
_EXPECTED_FIELD_COUNT: int = 6


# ---------------------------------------------------------------------------
# 枚举
# ---------------------------------------------------------------------------


class FrameType(IntEnum):
    """帧类型。"""

    MANIFEST = 0
    DATA = 1


# ---------------------------------------------------------------------------
# 异常
# ---------------------------------------------------------------------------


class ProtocolError(Exception):
    """协议解析错误（格式 / 版本 / 字段）。"""


class CrcMismatchError(ProtocolError):
    """CRC32 校验失败。"""


class IndexConflictError(ProtocolError):
    """同一 index 出现不同内容。"""


# ---------------------------------------------------------------------------
# 纯函数
# ---------------------------------------------------------------------------


def compute_file_id(sha256_hex: str) -> str:
    """取 SHA-256 hex 的前 12 字符作为 file_id。"""
    return sha256_hex[:12]


def compute_crc32(data: Union[bytes, str]) -> int:
    """计算 CRC32，返回 unsigned 32-bit int。

    Args:
        data: 字节串或 ASCII 字符串。
    """
    if isinstance(data, str):
        data = data.encode("ascii")
    return binascii.crc32(data) & 0xFFFFFFFF


def compute_sha256(data: bytes) -> str:
    """计算 SHA-256，返回 64 位 hex 字符串。"""
    return hashlib.sha256(data).hexdigest()


def compute_md5(data: bytes) -> str:
    """计算 MD5，返回 32 位 hex 字符串。"""
    return hashlib.md5(data).hexdigest()


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------


class Chunk(NamedTuple):
    """单个分片帧（manifest 或 data）。

    编码格式: SQ1|<file_id>|<index>|<total>|<crc32:08x>|<payload>
    """

    file_id: str       # 12 hex chars
    index: int         # 0=manifest, 1..N=data
    total: int         # 数据帧总数（不含 manifest）
    crc32: int         # payload 的 CRC32（unsigned 32-bit）
    payload: str       # Base64 ASCII 内容

    def encode(self) -> str:
        """序列化为 QR 内容字符串。"""
        return (
            f"{PROTOCOL_VERSION}{FIELD_SEPARATOR}"
            f"{self.file_id}{FIELD_SEPARATOR}"
            f"{self.index}{FIELD_SEPARATOR}"
            f"{self.total}{FIELD_SEPARATOR}"
            f"{self.crc32:08x}{FIELD_SEPARATOR}"
            f"{self.payload}"
        )

    @classmethod
    def decode(cls, raw: str) -> "Chunk":
        """从 QR 解码字符串解析为 Chunk。

        Raises:
            ProtocolError: 版本不匹配、字段数不对、类型转换失败。
        """
        # maxsplit=5 确保最多分成 6 段，payload 中的 | 不会被误切
        parts = raw.split(FIELD_SEPARATOR, _EXPECTED_FIELD_COUNT - 1)
        if len(parts) != _EXPECTED_FIELD_COUNT:
            raise ProtocolError(
                f"Expected {_EXPECTED_FIELD_COUNT} fields, got {len(parts)}"
            )

        version, file_id, index_str, total_str, crc32_str, payload = parts

        if version != PROTOCOL_VERSION:
            raise ProtocolError(f"Unknown protocol version: {version!r}")

        try:
            index = int(index_str)
        except ValueError as exc:
            raise ProtocolError(f"Invalid index: {index_str!r}") from exc

        try:
            total = int(total_str)
        except ValueError as exc:
            raise ProtocolError(f"Invalid total: {total_str!r}") from exc

        try:
            crc32 = int(crc32_str, 16)
        except ValueError as exc:
            raise ProtocolError(f"Invalid crc32: {crc32_str!r}") from exc

        return cls(
            file_id=file_id,
            index=index,
            total=total,
            crc32=crc32,
            payload=payload,
        )

    def verify_crc(self) -> bool:
        """校验 payload 的 CRC32 是否与声明值一致。"""
        return compute_crc32(self.payload) == self.crc32

    @property
    def frame_type(self) -> FrameType:
        """帧类型（manifest 或 data）。"""
        if self.index == MANIFEST_INDEX:
            return FrameType.MANIFEST
        return FrameType.DATA


class FileManifest(NamedTuple):
    """文件元数据，编码进 manifest 帧的 payload。

    JSON 字段使用短键名以减少体积：
        v  → schema_version
        fn → filename
        n  → original_bytes
        s  → sha256
        m  → md5 (nullable)
        c  → compression
        e  → encoding
    """

    schema_version: int     # 固定 1
    filename: str
    original_bytes: int
    sha256: str             # 64 hex chars
    md5: Optional[str]      # 32 hex chars，可为 None
    compression: str        # "gzip" | "zstd"
    encoding: str           # "base64"

    def encode_payload(self) -> str:
        """JSON → Base64（无换行），作为 manifest 帧的 payload。"""
        data: Dict[str, Any] = {
            "v": self.schema_version,
            "fn": self.filename,
            "n": self.original_bytes,
            "s": self.sha256,
            "m": self.md5,
            "c": self.compression,
            "e": self.encoding,
        }
        json_bytes = json.dumps(
            data,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return base64.b64encode(json_bytes).decode("ascii")

    @classmethod
    def decode_payload(cls, payload: str) -> "FileManifest":
        """Base64 → JSON → FileManifest。

        Raises:
            ProtocolError: JSON 解析失败或字段缺失。
        """
        try:
            json_bytes = base64.b64decode(payload)
            data = json.loads(json_bytes)
        except (ValueError, json.JSONDecodeError) as exc:
            raise ProtocolError(f"Invalid manifest payload: {exc}") from exc

        required = {"v", "fn", "n", "s", "c", "e"}
        missing = required - set(data)
        if missing:
            raise ProtocolError(f"Manifest missing fields: {missing}")

        return cls(
            schema_version=data["v"],
            filename=data["fn"],
            original_bytes=data["n"],
            sha256=data["s"],
            md5=data.get("m"),
            compression=data["c"],
            encoding=data["e"],
        )
