"""接收端主循环：截图 → 解码 → assembler → verify。"""
from __future__ import annotations

import gzip
import threading
import time
from pathlib import Path
from typing import Callable, Optional, Any

from sqr.protocol import FileManifest
from sqr.receiver.assembler import AssemblyProgress, ChunkAssembler
from sqr.receiver.capturer import CaptureRegion, ScreenCapturer
from sqr.receiver.decoder import decode_qr
from sqr.receiver.verifier import VerificationResult, verify_restored_file
from sqr.sender.compressor import decompress_payload


def run_receiver(
    region: CaptureRegion,
    output_path: Path,
    interval_ms: int = 500,
    expected_sha256: Optional[str] = None,
    expected_md5: Optional[str] = None,
    expected_bytes: Optional[int] = None,
    on_progress: Optional[Callable[[AssemblyProgress], None]] = None,
    on_complete: Optional[Callable[[VerificationResult, Path], None]] = None,
    timeout_sec: Optional[float] = None,
    stop_event: Optional[Any] = None,
) -> VerificationResult:
    """接收端主循环。

    Args:
        region: 截图区域。
        output_path: 输出文件路径。
        interval_ms: 截图间隔毫秒。
        expected_sha256 / expected_md5 / expected_bytes: CLI 传入的覆盖值。
        on_progress: 每次收到新分片时回调。
        on_complete: 传输完成时回调。
        timeout_sec: 超时秒数，None 表示不超时。
        stop_event: 可选 threading.Event，被 set 时主循环退出（用于 GUI 停止）。

    Returns:
        VerificationResult。
    """
    capturer = ScreenCapturer(region)
    assembler = ChunkAssembler()
    start_time = time.time()

    while True:
        if stop_event is not None and stop_event.is_set():
            break
        if timeout_sec is not None and (time.time() - start_time) > timeout_sec:
            raise TimeoutError(
                f"Receiver timed out after {timeout_sec}s"
            )

        try:
            img = capturer.capture()
        except Exception:
            time.sleep(interval_ms / 1000)
            continue

        decoded = decode_qr(img)
        if decoded is not None:
            added = assembler.add_raw(decoded)
            if added:
                progress = assembler.get_progress()
                if on_progress:
                    on_progress(progress)

                if progress.is_complete:
                    break

        time.sleep(interval_ms / 1000)

    capturer.close()

    progress = assembler.get_progress()
    manifest = progress.manifest

    compressed = assembler.assemble()
    restored = decompress_payload(compressed, manifest.compression)

    result = verify_restored_file(
        restored,
        manifest,
        expected_sha256=expected_sha256,
        expected_md5=expected_md5,
        expected_bytes=expected_bytes,
    )

    if result.success:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(restored)

    if on_complete:
        on_complete(result, output_path)

    return result
