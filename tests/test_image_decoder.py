"""sqr.receiver.image_decoder 单元测试。

验证 run_receiver_from_images：从多个二维码 image 文件批量解码 → 组装 → 还原。
复用发送端 PPM 生成（纯 stdlib）+ 接收端 pyzbar 解码链路。
"""
from __future__ import annotations

import random
from pathlib import Path

import pytest

from sqr.protocol import compute_md5, compute_sha256
from sqr.receiver.image_decoder import run_receiver_from_images
from sqr.sender.chunker import build_all_frames
from sqr.sender.qr_render import generate_matrix, matrix_to_ppm

FIXTURES = Path(__file__).parent / "fixtures"


def _make_ppm_set(
    source: Path, frames_dir: Path, max_chars: int = 100, module_size: int = 10
):
    """生成完整 PPM 帧集落盘，返回 (raw_bytes, manifest, sorted_path_list)。"""
    raw = source.read_bytes()
    sha = compute_sha256(raw)
    md5 = compute_md5(raw)
    manifest, chunks = build_all_frames(
        source.name, raw, sha, md5, max_chars=max_chars
    )
    frames_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for chunk in chunks:
        qr = generate_matrix(chunk.encode())
        ppm = matrix_to_ppm(qr, module_size=module_size)
        p = frames_dir / f"frame_{chunk.index:04d}.ppm"
        p.write_bytes(ppm)
        paths.append(p)
    return raw, manifest, paths


class TestRunReceiverFromImages:
    def test_roundtrip_small(self, tmp_path):
        raw, manifest, paths = _make_ppm_set(
            FIXTURES / "sample_small.txt", tmp_path / "frames"
        )
        out = tmp_path / "out.txt"

        result = run_receiver_from_images(
            paths, out,
            expected_sha256=compute_sha256(raw),
            expected_md5=compute_md5(raw),
            expected_bytes=len(raw),
        )

        assert result.success, f"Verification failed: {result.message}"
        assert out.exists()
        assert out.read_bytes() == raw

    def test_roundtrip_mid(self, tmp_path):
        raw, manifest, paths = _make_ppm_set(
            FIXTURES / "sample_mid.txt", tmp_path / "frames", max_chars=80
        )
        out = tmp_path / "out.txt"

        result = run_receiver_from_images(paths, out)

        assert result.success, f"Verification failed: {result.message}"
        assert out.read_bytes() == raw

    def test_order_independent(self, tmp_path):
        """image 输入顺序无关：add_raw 按 SQ1 帧 index 组装。"""
        raw, manifest, paths = _make_ppm_set(
            FIXTURES / "sample_mid.txt", tmp_path / "frames", max_chars=80
        )
        shuffled = paths.copy()
        random.seed(42)
        random.shuffle(shuffled)
        out = tmp_path / "out.txt"

        result = run_receiver_from_images(shuffled, out)

        assert result.success
        assert out.read_bytes() == raw

    def test_progress_callback_invoked(self, tmp_path):
        raw, manifest, paths = _make_ppm_set(
            FIXTURES / "sample_mid.txt", tmp_path / "frames", max_chars=80
        )
        progresses = []
        run_receiver_from_images(
            paths, tmp_path / "out.txt", on_progress=progresses.append
        )
        assert len(progresses) > 0
        assert progresses[-1].is_complete

    def test_missing_manifest_frame(self, tmp_path):
        """缺 manifest 帧（index=0）：无法 assemble，返回失败 result。"""
        raw, manifest, paths = _make_ppm_set(
            FIXTURES / "sample_mid.txt", tmp_path / "frames", max_chars=80
        )
        data_only = [p for p in paths if "frame_0000" not in p.name]
        out = tmp_path / "out.txt"

        result = run_receiver_from_images(data_only, out)

        assert not result.success
        assert "manifest" in result.message.lower()
        assert not out.exists()

    def test_missing_data_frame(self, tmp_path):
        """缺一个数据帧：未收齐，返回失败 result。"""
        raw, manifest, paths = _make_ppm_set(
            FIXTURES / "sample_mid.txt", tmp_path / "frames", max_chars=80
        )
        incomplete = [p for p in paths if "frame_0001" not in p.name]
        out = tmp_path / "out.txt"

        result = run_receiver_from_images(incomplete, out)

        assert not result.success
        assert not out.exists()

    def test_empty_image_list(self, tmp_path):
        """空 image 列表：返回失败 result，不抛异常。"""
        out = tmp_path / "out.txt"
        result = run_receiver_from_images([], out)
        assert not result.success
        assert not out.exists()

    def test_on_complete_callback(self, tmp_path):
        raw, manifest, paths = _make_ppm_set(
            FIXTURES / "sample_small.txt", tmp_path / "frames"
        )
        captured = []
        run_receiver_from_images(
            paths, tmp_path / "out.txt",
            on_complete=lambda r, p: captured.append((r, p)),
        )
        assert len(captured) == 1
        result, path = captured[0]
        assert result.success
        assert path.read_bytes() == raw
