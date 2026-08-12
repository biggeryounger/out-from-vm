"""sqr.sender.qr_render 单元测试。

覆盖：QR 矩阵生成、PPM 格式正确性、矩阵维度、Unicode 渲染。
不依赖 Pillow（使用 PIL stub）。
"""
from __future__ import annotations

import pytest

from sqr.sender.qr_render import (
    QRMatrix,
    generate_matrix,
    matrix_to_ppm,
    matrix_to_unicode,
)


class TestGenerateMatrix:
    def test_basic_generation(self):
        qr = generate_matrix("hello world")
        assert isinstance(qr, QRMatrix)
        assert qr.version >= 1
        assert qr.module_count == qr.version * 4 + 17
        assert len(qr.matrix) == qr.module_count
        assert all(len(row) == qr.module_count for row in qr.matrix)

    def test_matrix_is_bool(self):
        qr = generate_matrix("test")
        for row in qr.matrix:
            for cell in row:
                assert isinstance(cell, bool)

    def test_quiet_zone_default(self):
        qr = generate_matrix("test")
        assert qr.quiet_zone == 4

    def test_custom_quiet_zone(self):
        qr = generate_matrix("test", quiet_zone=8)
        assert qr.quiet_zone == 8

    def test_error_correction_levels(self):
        for ec in ("L", "M", "Q", "H"):
            qr = generate_matrix("test data", error_correction=ec)
            assert qr.version >= 1

    def test_invalid_error_correction(self):
        with pytest.raises(ValueError, match="error_correction"):
            generate_matrix("test", error_correction="X")

    def test_larger_data_higher_version(self):
        small = generate_matrix("a")
        large = generate_matrix("a" * 500)
        assert large.version >= small.version

    def test_protocol_frame_encoding(self):
        """模拟真实协议帧内容。"""
        frame = "SQ1|abcdef012345|1|10|0a1b2c3d|" + "X" * 200
        qr = generate_matrix(frame)
        assert qr.module_count > 0


class TestMatrixToPpm:
    def test_ppm_header_format(self):
        qr = generate_matrix("test")
        ppm = matrix_to_ppm(qr, module_size=5)
        # PPM P6 header: "P6\n<w> <h>\n255\n" + pixel data
        first_nl = ppm.index(b"\n")
        second_nl = ppm.index(b"\n", first_nl + 1)
        third_nl = ppm.index(b"\n", second_nl + 1)
        header = ppm[:third_nl + 1].decode("ascii")
        assert header.startswith("P6\n")
        assert "255" in header

    def test_ppm_dimensions(self):
        qr = generate_matrix("test", quiet_zone=4)
        module_size = 10
        ppm = matrix_to_ppm(qr, module_size=module_size)
        total_modules = qr.module_count + 2 * qr.quiet_zone
        expected_size = total_modules * module_size
        header_line = ppm.split(b"\n", 2)[1].decode("ascii")
        assert f"{expected_size} {expected_size}" == header_line

    def test_ppm_pixel_data_size(self):
        qr = generate_matrix("test", quiet_zone=4)
        module_size = 5
        ppm = matrix_to_ppm(qr, module_size=module_size)
        total_modules = qr.module_count + 2 * qr.quiet_zone
        expected_pixels = (total_modules * module_size) ** 2 * 3
        header_size = len(f"P6\n{total_modules * module_size} {total_modules * module_size}\n255\n")
        assert len(ppm) - header_size == expected_pixels

    def test_ppm_has_black_and_white(self):
        qr = generate_matrix("hello world")
        ppm = matrix_to_ppm(qr, module_size=2)
        has_black = b"\x00\x00\x00" in ppm
        has_white = b"\xff\xff\xff" in ppm
        assert has_black, "PPM should contain black pixels"
        assert has_white, "PPM should contain white pixels"

    def test_ppm_module_size_1(self):
        """module_size=1 时 PPM 应等于 QR 矩阵的像素级表示。"""
        qr = generate_matrix("X", quiet_zone=0)
        ppm = matrix_to_ppm(qr, module_size=1)
        size = qr.module_count
        header = f"P6\n{size} {size}\n255\n".encode("ascii")
        pixels = ppm[len(header):]
        for r in range(size):
            for c in range(size):
                idx = (r * size + c) * 3
                pixel = pixels[idx:idx + 3]
                if qr.matrix[r][c]:
                    assert pixel == b"\x00\x00\x00", f"({r},{c}) should be black"
                else:
                    assert pixel == b"\xff\xff\xff", f"({r},{c}) should be white"


class TestMatrixToUnicode:
    def test_returns_string(self):
        qr = generate_matrix("test")
        result = matrix_to_unicode(qr)
        assert isinstance(result, str)

    def test_has_block_characters(self):
        qr = generate_matrix("hello world")
        result = matrix_to_unicode(qr)
        block_chars = {"\u2588", "\u2580", "\u2584", " "}
        used_chars = set(result.replace("\n", ""))
        assert used_chars.issubset(block_chars)

    def test_line_count(self):
        qr = generate_matrix("test", quiet_zone=4)
        result = matrix_to_unicode(qr)
        total = qr.module_count + 2 * qr.quiet_zone
        expected_lines = (total + 1) // 2
        actual_lines = result.count("\n") + 1
        assert actual_lines == expected_lines

    def test_nonempty_output(self):
        qr = generate_matrix("hello world this is a test")
        result = matrix_to_unicode(qr)
        assert len(result) > 0
        assert any(c != " " and c != "\n" for c in result)


class TestQRMatrixProperties:
    def test_frozen(self):
        qr = generate_matrix("test")
        with pytest.raises(AttributeError):
            qr.version = 99

    def test_finder_pattern_present(self):
        """QR 码的左上角应有 Finder Pattern（7×7 黑色边框区域）。"""
        qr = generate_matrix("test", quiet_zone=0)
        m = qr.matrix
        assert m[0][0] is True
        assert m[6][6] is True or m[0][6] is True
