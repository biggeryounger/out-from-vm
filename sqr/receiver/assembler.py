"""分片收集器：校验、去重、排序、拼接。

线程安全：内部用 threading.Lock 保护。capturer 线程调 add()，
主线程调 get_progress() / assemble()。
"""
from __future__ import annotations

import base64
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from sqr.protocol import (
    Chunk,
    CrcMismatchError,
    FileManifest,
    FrameType,
    IndexConflictError,
    MANIFEST_INDEX,
    ProtocolError,
    compute_crc32,
)


@dataclass
class AssemblyProgress:
    """当前采集进度（只读视图）。"""

    file_id: Optional[str] = None
    total: Optional[int] = None
    manifest: Optional[FileManifest] = None
    received_indices: Set[int] = field(default_factory=set)
    conflicts: Dict[int, List[str]] = field(default_factory=dict)
    rejected_count: int = 0

    @property
    def missing_indices(self) -> Set[int]:
        if self.total is None:
            return set()
        return set(range(1, self.total + 1)) - self.received_indices

    @property
    def is_complete(self) -> bool:
        if self.total is None or self.manifest is None:
            return False
        return len(self.received_indices) == self.total

    @property
    def received_count(self) -> int:
        return len(self.received_indices)

    @property
    def percent(self) -> float:
        if self.total is None or self.total == 0:
            return 0.0
        return (self.received_count / self.total) * 100


class ChunkAssembler:
    """分片收集器。

    用法:
        assembler = ChunkAssembler()
        for raw_string in decoded_qr_strings:
            assembler.add_raw(raw_string)
            if assembler.get_progress().is_complete:
                break
        compressed_bytes = assembler.assemble()
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._progress = AssemblyProgress()
        self._chunks: Dict[int, Chunk] = {}

    def add_raw(self, raw: str) -> bool:
        """解析原始字符串并尝试加入。

        Returns:
            True = 新有效分片已加入；False = 重复 / 损坏 / 拒绝。
        """
        try:
            chunk = Chunk.decode(raw)
        except ProtocolError:
            with self._lock:
                self._progress.rejected_count += 1
            return False
        return self.add_chunk(chunk)

    def add_chunk(self, chunk: Chunk) -> bool:
        """已解析的 Chunk 加入。

        Returns:
            True = 新有效分片已加入。
        """
        with self._lock:
            return self._add_chunk_unlocked(chunk)

    def _add_chunk_unlocked(self, chunk: Chunk) -> bool:
        """内部方法（调用者需持锁）。"""

        if not chunk.verify_crc():
            self._progress.rejected_count += 1
            return False

        if chunk.frame_type == FrameType.MANIFEST:
            return self._handle_manifest(chunk)
        else:
            return self._handle_data(chunk)

    def _handle_manifest(self, chunk: Chunk) -> bool:
        """处理 manifest 帧（index=0）。"""
        try:
            manifest = FileManifest.decode_payload(chunk.payload)
        except ProtocolError:
            self._progress.rejected_count += 1
            return False

        if self._progress.file_id is not None and chunk.file_id != self._progress.file_id:
            self._progress.rejected_count += 1
            return False

        self._progress.file_id = chunk.file_id
        self._progress.total = chunk.total
        self._progress.manifest = manifest
        return True

    def _handle_data(self, chunk: Chunk) -> bool:
        """处理数据帧（index >= 1）。"""
        if self._progress.file_id is not None:
            if chunk.file_id != self._progress.file_id:
                self._progress.rejected_count += 1
                return False
        else:
            self._progress.file_id = chunk.file_id

        if self._progress.total is not None:
            if chunk.total != self._progress.total:
                self._progress.rejected_count += 1
                return False
        else:
            self._progress.total = chunk.total

        if chunk.index < 1 or chunk.index > chunk.total:
            self._progress.rejected_count += 1
            return False

        if chunk.index in self._chunks:
            existing = self._chunks[chunk.index]
            if existing.crc32 == chunk.crc32:
                return False
            else:
                conflict_key = f"{chunk.crc32:08x} vs {existing.crc32:08x}"
                self._progress.conflicts.setdefault(chunk.index, []).append(conflict_key)
                return False

        self._chunks[chunk.index] = chunk
        self._progress.received_indices.add(chunk.index)
        return True

    def get_progress(self) -> AssemblyProgress:
        """获取当前进度快照（线程安全）。"""
        with self._lock:
            return AssemblyProgress(
                file_id=self._progress.file_id,
                total=self._progress.total,
                manifest=self._progress.manifest,
                received_indices=set(self._progress.received_indices),
                conflicts=dict(self._progress.conflicts),
                rejected_count=self._progress.rejected_count,
            )

    def assemble(self) -> bytes:
        """拼接全部 payload → Base64 解码 → 返回压缩字节。

        仅在 is_complete=True 时调用。

        Raises:
            ProtocolError: 分片不完整。
            ValueError: Base64 解码失败。
        """
        with self._lock:
            progress = self.get_progress_unlocked()

            if not progress.is_complete:
                missing = progress.missing_indices
                raise ProtocolError(
                    f"Cannot assemble: missing {len(missing)} chunks: "
                    f"{sorted(missing)[:10]}..."
                )

            chunks_sorted = sorted(
                [self._chunks[i] for i in range(1, progress.total + 1)],
                key=lambda c: c.index,
            )

        combined_b64 = "".join(c.payload for c in chunks_sorted)
        return base64.b64decode(combined_b64)

    def get_progress_unlocked(self) -> AssemblyProgress:
        """获取进度快照（调用者需持锁）。"""
        return AssemblyProgress(
            file_id=self._progress.file_id,
            total=self._progress.total,
            manifest=self._progress.manifest,
            received_indices=set(self._progress.received_indices),
            conflicts=dict(self._progress.conflicts),
            rejected_count=self._progress.rejected_count,
        )

    def reset(self) -> None:
        """清空当前会话，准备接收新 file_id。"""
        with self._lock:
            self._progress = AssemblyProgress()
            self._chunks.clear()
