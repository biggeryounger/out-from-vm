"""从多个二维码 image 文件批量解码 → 组装 → 还原。

数据源为 image 文件列表（PPM/PNG/JPG），后续组装校验链路与 run_receiver 一致。
复用 ChunkAssembler / decompress_payload / verify_restored_file，不动 runner.py。
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, List, Optional

from sqr.receiver.assembler import AssemblyProgress, ChunkAssembler
from sqr.receiver.decoder import decode_qr, decode_qr_multi
from sqr.receiver.verifier import VerificationResult, verify_restored_file
from sqr.sender.compressor import decompress_payload


def _fail_result(message: str) -> VerificationResult:
    return VerificationResult(
        success=False,
        byte_count_match=False,
        sha256_match=False,
        md5_match=False,
        utf8_valid=False,
        actual_bytes=0,
        actual_sha256="",
        actual_md5="",
        message=message,
    )


def _decode_image_file(path: Path) -> List[str]:
    """打开 image 文件，优先多码解码，空则回退单码。返回解码字符串列表。"""
    from PIL import Image

    img = Image.open(str(path))
    if img.mode != "RGB":
        img = img.convert("RGB")

    decoded = decode_qr_multi(img)
    if decoded:
        return decoded

    single = decode_qr(img)
    return [single] if single else []


def run_receiver_from_images(
    image_paths: List[Path],
    output_path: Path,
    expected_sha256: Optional[str] = None,
    expected_md5: Optional[str] = None,
    expected_bytes: Optional[int] = None,
    on_progress: Optional[Callable[[AssemblyProgress], None]] = None,
    on_complete: Optional[Callable[[VerificationResult, Path], None]] = None,
) -> VerificationResult:
    """从 image 文件列表批量解码还原文件。

    每个 image 优先多码解码（兼容网格同屏多 QR），空则回退单码。
    解码出的 SQ1 帧按 index 组装（顺序无关），收齐后 gunzip + 三重校验 + 写出。

    Args:
        image_paths: image 文件路径列表（PPM/PNG/JPG，顺序任意）。
        output_path: 还原文件写出路径（仅校验成功才写）。
        expected_sha256 / expected_md5 / expected_bytes: 可选覆盖校验值。
        on_progress: 每收到新分片时回调。
        on_complete: 处理结束时回调（无论成功失败）。

    Returns:
        VerificationResult（manifest 缺失 / 帧未收齐时 success=False）。
    """
    assembler = ChunkAssembler()

    for img_path in image_paths:
        decoded_list = _decode_image_file(img_path)

        completed = False
        for decoded in decoded_list:
            added = assembler.add_raw(decoded)
            if added:
                progress = assembler.get_progress()
                if on_progress:
                    on_progress(progress)
                if progress.is_complete:
                    completed = True
                    break
        if completed:
            break

    progress = assembler.get_progress()
    manifest = progress.manifest

    if manifest is None:
        result = _fail_result(
            "manifest frame missing: no SQ1 manifest (index=0) found in any image"
        )
    elif not progress.is_complete:
        missing = sorted(progress.missing_indices)
        result = _fail_result(
            "incomplete: missing %d data frame(s): %s" % (len(missing), missing)
        )
    else:
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
