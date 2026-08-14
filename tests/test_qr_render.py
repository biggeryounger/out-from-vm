"""sqr.sender.qr_render 单元测试。

覆盖：QR 矩阵生成、PPM 格式正确性、矩阵维度、Unicode 渲染。
不依赖 Pillow（使用 PIL stub）。
"""
from __future__ import annotations

from typing import List

import pytest

from sqr.sender.qr_render import (
    QRMatrix,
    generate_matrix,
    matrices_to_html_grid,
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


class TestMatricesToHtmlGrid:
    def _make_matrices(self, n: int) -> List[QRMatrix]:
        total_data = max(0, n - 1)
        return [
            generate_matrix(
                f"SQ1|abc123def456|{i}|{total_data}|0a1b2c3d|payload_content_{i}"
            )
            for i in range(n)
        ]

    def test_returns_nonempty_str(self):
        html = matrices_to_html_grid(self._make_matrices(3))
        assert isinstance(html, str)
        assert len(html) > 0

    def test_has_html_skeleton(self):
        html = matrices_to_html_grid(self._make_matrices(2))
        lower = html.lower()
        assert "<html" in lower
        assert "</html>" in lower
        assert "<svg" in lower

    def test_svg_count_equals_matrices(self):
        for n in (1, 3, 5, 17):
            html = matrices_to_html_grid(self._make_matrices(n))
            assert html.count("<svg") == n, f"n={n} should yield {n} SVGs"

    def test_single_page_when_fits(self):
        html = matrices_to_html_grid(self._make_matrices(5), cols=4, rows_per_page=4)
        assert html.count('class="qr-page"') == 1

    def test_multi_page_when_overflows(self):
        html = matrices_to_html_grid(self._make_matrices(20), cols=4, rows_per_page=4)
        assert html.count('class="qr-page"') == 2

    @pytest.mark.parametrize("n,cols,rows,expected_pages", [
        (1, 4, 4, 1),
        (16, 4, 4, 1),
        (17, 4, 4, 2),
        (32, 4, 4, 2),
        (33, 4, 4, 3),
        (10, 5, 2, 1),
        (11, 5, 2, 2),
    ], ids=["single", "exactly-full", "one-over", "exactly-two",
            "over-two", "custom-fit", "custom-overflow"])
    def test_page_count(self, n, cols, rows, expected_pages):
        html = matrices_to_html_grid(
            self._make_matrices(n), cols=cols, rows_per_page=rows
        )
        assert html.count('class="qr-page"') == expected_pages

    def test_has_prev_next_auto_buttons(self):
        html = matrices_to_html_grid(self._make_matrices(3))
        assert "Prev" in html
        assert "Next" in html
        assert "Auto" in html

    def test_labels_manifest_and_data(self):
        html = matrices_to_html_grid(self._make_matrices(5))
        assert "MANIFEST" in html
        assert "DATA" in html

    def test_auto_default_off(self):
        html = matrices_to_html_grid(self._make_matrices(3))
        assert "Auto: OFF" in html

    def test_auto_explicit_on(self):
        html = matrices_to_html_grid(self._make_matrices(3), auto_cycle=True)
        assert "Auto: ON" in html

    def test_svg_viewbox_includes_quiet_zone(self):
        m = generate_matrix("test", quiet_zone=4)
        total = m.module_count + 2 * m.quiet_zone
        html = matrices_to_html_grid([m])
        assert f'viewBox="0 0 {total} {total}"' in html

    def test_file_id_and_filename_embedded(self):
        html = matrices_to_html_grid(
            self._make_matrices(3),
            file_id="deadbeef00ff",
            filename="report.txt",
        )
        assert "deadbeef00ff" in html
        assert "report.txt" in html

    def test_page_interval_embedded(self):
        html = matrices_to_html_grid(
            self._make_matrices(20),
            page_interval_ms=1500,
        )
        assert "1500" in html

    def test_empty_matrices_raises(self):
        with pytest.raises(ValueError):
            matrices_to_html_grid([])

    def test_invalid_cols_raises(self):
        with pytest.raises(ValueError):
            matrices_to_html_grid(self._make_matrices(3), cols=0)

    def test_invalid_rows_raises(self):
        with pytest.raises(ValueError):
            matrices_to_html_grid(self._make_matrices(3), rows_per_page=0)

    def test_grid_has_player_stage(self):
        """grid 模式生成全屏播放舞台元素（Auto ON 时逐张播放的容器）。"""
        html = matrices_to_html_grid(self._make_matrices(5))
        assert 'id="player-stage"' in html

    def test_grid_play_mode_frame(self):
        """grid 模式 JS 注入 playMode='frame'（Auto 操作单帧而非翻页）。"""
        html = matrices_to_html_grid(self._make_matrices(5))
        assert 'playMode = "frame"' in html

    def test_grid_stage_hidden_by_default_css(self):
        """player-stage 默认 display:none（仅 Auto ON 时 JS 改 flex 显示）。"""
        html = matrices_to_html_grid(self._make_matrices(3))
        assert "#player-stage" in html
        assert "display: none" in html

    def test_has_save_zip_button(self):
        """controls 含 Save ZIP 按钮（点按后导出全部 QR PNG 打包 zip）。"""
        html = matrices_to_html_grid(self._make_matrices(3))
        assert 'id="save-zip-btn"' in html
        assert "Save ZIP" in html

    def test_zip_js_embedded(self):
        """HTML 注入纯 JS zip 打包逻辑（STORE 无压缩 + CRC32，零依赖）。"""
        html = matrices_to_html_grid(self._make_matrices(3))
        assert "buildZip" in html
        assert "application/zip" in html
        assert "crc32" in html

    def test_zip_js_no_extra_svg_literal(self):
        """_ZIP_JS 源码不含 <svg 字面量，保证 svg 计数断言不被破坏。"""
        html = matrices_to_html_grid(self._make_matrices(5))
        assert html.count("<svg") == 5


class TestCycleLayout:
    """layout='cycle' 全屏单 QR 自动循环布局。"""

    def _make_matrices(self, n: int) -> List[QRMatrix]:
        total_data = max(0, n - 1)
        return [
            generate_matrix(
                f"SQ1|abc123def456|{i}|{total_data}|0a1b2c3d|payload_content_{i}"
            )
            for i in range(n)
        ]

    def test_one_qr_per_page(self):
        """cycle 布局：每个 QR 独占一页（N 矩阵 = N 页）。"""
        for n in (1, 3, 7):
            html = matrices_to_html_grid(self._make_matrices(n), layout="cycle")
            assert html.count('class="qr-page"') == n, (
                f"cycle: n={n} should yield {n} pages (1 QR/page)"
            )

    def test_auto_on_by_default(self):
        """cycle 布局：Auto 默认 ON（自动循环）。"""
        html = matrices_to_html_grid(self._make_matrices(3), layout="cycle")
        assert "Auto: ON" in html
        assert "var autoCycle = true" in html

    def test_forces_single_col_single_row(self):
        """cycle 布局：忽略传入的 cols/rows_per_page，强制 1×1。"""
        html = matrices_to_html_grid(
            self._make_matrices(3), layout="cycle", cols=4, rows_per_page=4
        )
        assert html.count('class="qr-page"') == 3

    def test_fullscreen_css_marker(self):
        """cycle 布局：使用全屏 CSS（vmin 标记）。"""
        html = matrices_to_html_grid(self._make_matrices(2), layout="cycle")
        assert "vmin" in html

    def test_interval_applied(self):
        """cycle 布局：page_interval_ms 透传到 JS。"""
        html = matrices_to_html_grid(
            self._make_matrices(3), layout="cycle", page_interval_ms=1200
        )
        assert "1200" in html

    def test_invalid_layout_raises(self):
        """非法 layout 值应 ValueError。"""
        with pytest.raises(ValueError, match="layout"):
            matrices_to_html_grid(self._make_matrices(2), layout="unknown")

    def test_svg_count_preserved(self):
        """cycle 布局：SVG 总数仍等于矩阵数。"""
        html = matrices_to_html_grid(self._make_matrices(5), layout="cycle")
        assert html.count("<svg") == 5

    def test_cycle_no_player_stage(self):
        """cycle 布局：不生成 player-stage（每页 1 张，翻页即逐张，无需舞台）。"""
        html = matrices_to_html_grid(self._make_matrices(3), layout="cycle")
        assert 'id="player-stage"' not in html

    def test_cycle_play_mode_page(self):
        """cycle 布局：JS 注入 playMode='page'（保持原翻页逻辑）。"""
        html = matrices_to_html_grid(self._make_matrices(3), layout="cycle")
        assert 'playMode = "page"' in html

    def test_cycle_has_save_zip_button(self):
        """cycle 布局也含 Save ZIP 按钮（两种布局均可导出 PNG zip）。"""
        html = matrices_to_html_grid(self._make_matrices(3), layout="cycle")
        assert 'id="save-zip-btn"' in html
        assert "Save ZIP" in html
