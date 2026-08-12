"""端到端 round-trip 测试：file → compress → chunk → QR matrix → PPM → decode → assemble → verify。

★ 核心里程碑测试 —— 证明协议层 + QR 生成/解码正确。

发送端 PPM 生成纯 stdlib（不依赖 Pillow）；
接收端读 PPM 用 Pillow + pyzbar 解码（构建机/外网可用）。
"""
from __future__ import annotations

import gzip
import os
from pathlib import Path

import pytest

from sqr.protocol import (
    Chunk,
    compute_file_id,
    compute_md5,
    compute_sha256,
)
from sqr.sender.chunker import build_all_frames
from sqr.sender.compressor import decompress_payload
from sqr.sender.qr_render import generate_matrix, matrix_to_ppm
from sqr.receiver.assembler import ChunkAssembler
from sqr.receiver.decoder import decode_qr_from_file
from sqr.receiver.verifier import verify_restored_file


FIXTURES_DIR = Path(__file__).parent / "fixtures"

FIXTURE_FILES = [
    "sample_small.txt",
    "sample_mid.txt",
    "sample_repetitive.txt",
]


@pytest.fixture(scope="module")
def tmp_frames_dir(tmp_path_factory):
    return tmp_path_factory.mktemp("qr_frames")


def _run_roundtrip(
    source_path: Path,
    frames_dir: Path,
    max_chars: int = 1200,
    module_size: int = 10,
    error_correction: str = "M",
):
    """完整端到端流程，返回 (raw_bytes, manifest, verification_result)。"""
    raw = source_path.read_bytes()
    sha256_hex = compute_sha256(raw)
    md5_hex = compute_md5(raw)
    filename = source_path.name

    # === 发送端 ===
    manifest, chunks = build_all_frames(
        filename, raw, sha256_hex, md5_hex,
        max_chars=max_chars,
    )

    # 生成 QR matrix → PPM 文件（纯 stdlib）
    ppm_files: list[Path] = []
    for chunk in chunks:
        qr = generate_matrix(
            chunk.encode(),
            error_correction=error_correction,
        )
        ppm_data = matrix_to_ppm(qr, module_size=module_size)
        ppm_path = frames_dir / f"{source_path.stem}_frame_{chunk.index:04d}.ppm"
        ppm_path.write_bytes(ppm_data)
        ppm_files.append(ppm_path)

    # === 接收端 ===
    assembler = ChunkAssembler()

    for ppm_path in ppm_files:
        decoded_str = decode_qr_from_file(ppm_path)
        assert decoded_str is not None, f"Failed to decode QR from {ppm_path}"
        assembler.add_raw(decoded_str)

    progress = assembler.get_progress()
    assert progress.is_complete, (
        f"Missing chunks: {sorted(progress.missing_indices)}"
    )

    compressed = assembler.assemble()
    restored = decompress_payload(compressed, manifest.compression)

    result = verify_restored_file(
        restored,
        assembler.get_progress().manifest,
        expected_sha256=sha256_hex,
        expected_md5=md5_hex,
        expected_bytes=len(raw),
    )

    return raw, restored, manifest, result


class TestRoundtrip:
    """端到端：file → PPM → decode → verify。"""

    def test_small_file(self, tmp_frames_dir):
        source = FIXTURES_DIR / "sample_small.txt"
        raw, restored, manifest, result = _run_roundtrip(
            source, tmp_frames_dir, max_chars=1200, module_size=10,
        )

        assert result.success, f"Verification failed: {result.message}"
        assert restored == raw

    def test_mid_file(self, tmp_frames_dir):
        source = FIXTURES_DIR / "sample_mid.txt"
        raw, restored, manifest, result = _run_roundtrip(
            source, tmp_frames_dir, max_chars=100, module_size=10,
        )

        assert result.success, f"Verification failed: {result.message}"
        assert restored == raw

    def test_repetitive_file(self, tmp_frames_dir):
        source = FIXTURES_DIR / "sample_repetitive.txt"
        raw, restored, manifest, result = _run_roundtrip(
            source, tmp_frames_dir, max_chars=1200, module_size=10,
        )

        assert result.success, f"Verification failed: {result.message}"
        assert restored == raw

    def test_md5_exact_match(self, tmp_frames_dir):
        source = FIXTURES_DIR / "sample_mid.txt"
        raw, restored, manifest, result = _run_roundtrip(
            source, tmp_frames_dir, max_chars=100, module_size=10,
        )

        assert result.md5_match
        expected_md5 = compute_md5(raw)
        assert result.actual_md5 == expected_md5

    def test_error_correction_q(self, tmp_frames_dir):
        source = FIXTURES_DIR / "sample_small.txt"
        raw, restored, manifest, result = _run_roundtrip(
            source, tmp_frames_dir,
            max_chars=1200, module_size=10, error_correction="Q",
        )

        assert result.success, f"Verification failed: {result.message}"

    def test_small_module_size(self, tmp_frames_dir):
        """module_size=5 仍可解码。"""
        source = FIXTURES_DIR / "sample_small.txt"
        raw, restored, manifest, result = _run_roundtrip(
            source, tmp_frames_dir,
            max_chars=1200, module_size=5,
        )

        assert result.success, f"Verification failed: {result.message}"


class TestRoundtripDataIntegrity:
    """验证传输数据的逐字节完整性。"""

    @pytest.mark.parametrize("filename", FIXTURE_FILES)
    def test_byte_for_byte_match(self, filename, tmp_frames_dir):
        source = FIXTURES_DIR / filename
        raw = source.read_bytes()

        sha256_hex = compute_sha256(raw)
        md5_hex = compute_md5(raw)

        manifest, chunks = build_all_frames(
            source.name, raw, sha256_hex, md5_hex, max_chars=500,
        )

        frames_dir = tmp_frames_dir / Path(filename).stem
        frames_dir.mkdir(exist_ok=True)

        assembler = ChunkAssembler()
        for chunk in chunks:
            qr = generate_matrix(chunk.encode())
            ppm_data = matrix_to_ppm(qr, module_size=10)
            ppm_path = frames_dir / f"frame_{chunk.index:04d}.ppm"
            ppm_path.write_bytes(ppm_data)

            decoded = decode_qr_from_file(ppm_path)
            assert decoded is not None
            assembler.add_raw(decoded)

        assert assembler.get_progress().is_complete
        compressed = assembler.assemble()
        restored = decompress_payload(compressed, manifest.compression)

        assert restored == raw
        assert len(restored) == len(raw)

    def test_chunk_count_matches(self, tmp_frames_dir):
        """发送端生成的数据帧数应与接收端收集的一致。"""
        source = FIXTURES_DIR / "sample_mid.txt"
        raw = source.read_bytes()
        sha256 = compute_sha256(raw)
        md5 = compute_md5(raw)

        _, chunks = build_all_frames(source.name, raw, sha256, md5, max_chars=80)

        data_chunk_count = len(chunks) - 1  # 去掉 manifest

        frames_dir = tmp_frames_dir / "count_test"
        frames_dir.mkdir(exist_ok=True)
        assembler = ChunkAssembler()
        for chunk in chunks:
            qr = generate_matrix(chunk.encode())
            ppm_data = matrix_to_ppm(qr, module_size=10)
            ppm_path = frames_dir / f"f_{chunk.index:04d}.ppm"
            ppm_path.write_bytes(ppm_data)
            decoded = decode_qr_from_file(ppm_path)
            assembler.add_raw(decoded)

        progress = assembler.get_progress()
        assert progress.total == data_chunk_count
        assert progress.received_count == data_chunk_count
