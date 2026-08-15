"""QR 矩阵生成 + 三种渲染器（Canvas / PPM / Terminal）。

不依赖 Pillow。通过 sqr.vendor 的 PIL stub 使 qrcode 导入成功，
但只访问 qr.modules（纯布尔矩阵），从不调用 make_image()。
"""
import math
from typing import List, NamedTuple

# vendor bootstrap 必须在 import qrcode 之前
import sqr.vendor  # noqa: F401
import qrcode
from qrcode.constants import ERROR_CORRECT_L, ERROR_CORRECT_M, ERROR_CORRECT_Q, ERROR_CORRECT_H


_EC_MAP = {
    "L": ERROR_CORRECT_L,
    "M": ERROR_CORRECT_M,
    "Q": ERROR_CORRECT_Q,
    "H": ERROR_CORRECT_H,
}


class QRMatrix(NamedTuple):
    """QR 矩阵 + 元数据。"""

    matrix: List[List[bool]]    # True = 黑块
    version: int                # QR version (1-40)
    module_count: int           # version * 4 + 17
    quiet_zone: int             # 静区 modules


def generate_matrix(
    data: str,
    error_correction: str = "M",
    quiet_zone: int = 4,
) -> QRMatrix:
    """生成 QR 矩阵（不经过任何图像库）。

    Args:
        data: QR 内容字符串（如 Chunk.encode() 的结果）。
        error_correction: "M" | "Q" | "L" | "H"
        quiet_zone: 静区 modules 数（≥4）。

    Raises:
        ValueError: error_correction 不合法或数据超出 QR 容量。
    """
    ec = _EC_MAP.get(error_correction.upper())
    if ec is None:
        raise ValueError(
            f"Invalid error_correction: {error_correction!r}. "
            f"Must be one of {list(_EC_MAP.keys())}"
        )

    qr = qrcode.QRCode(
        error_correction=ec,
        box_size=1,
        border=quiet_zone,
    )
    qr.add_data(data)
    qr.make(fit=True)

    return QRMatrix(
        matrix=[list(row) for row in qr.modules],
        version=qr.version,
        module_count=len(qr.modules),
        quiet_zone=quiet_zone,
    )


# ---------------------------------------------------------------------------
# 渲染器 A：tkinter Canvas（屏幕显示，主用途）
# ---------------------------------------------------------------------------


def draw_matrix_on_canvas(
    canvas,
    qr_matrix: QRMatrix,
    module_size: int = 10,
    bg_color: str = "white",
    fg_color: str = "black",
) -> int:
    """在 tkinter Canvas 上直接绘制 QR。

    Args:
        canvas: tkinter.Canvas 实例。
        qr_matrix: QR 矩阵。
        module_size: 每个 module 的像素边长。
        bg_color: 背景色。
        fg_color: 前景（黑块）色。

    Returns:
        绘制后的图像总像素尺寸（正方形边长）。
    """
    total_modules = qr_matrix.module_count + 2 * qr_matrix.quiet_zone
    pixel_size = total_modules * module_size

    canvas.delete("all")
    canvas.create_rectangle(
        0, 0, pixel_size, pixel_size,
        fill=bg_color, outline="",
    )

    for r in range(qr_matrix.module_count):
        row = qr_matrix.matrix[r]
        for c in range(qr_matrix.module_count):
            if row[c]:
                x = (c + qr_matrix.quiet_zone) * module_size
                y = (r + qr_matrix.quiet_zone) * module_size
                canvas.create_rectangle(
                    x, y, x + module_size, y + module_size,
                    fill=fg_color, outline="",
                )

    return pixel_size


# ---------------------------------------------------------------------------
# 渲染器 B：PPM 字节导出（调试 / 集成测试）
# ---------------------------------------------------------------------------


def matrix_to_ppm(
    qr_matrix: QRMatrix,
    module_size: int = 10,
) -> bytes:
    """生成 PPM (P6) 二进制图像字节。

    纯 stdlib 实现，不依赖任何图像库。
    PPM 可被 Pillow (Image.open) 直接读取。

    Args:
        qr_matrix: QR 矩阵。
        module_size: 每个 module 的像素边长。

    Returns:
        PPM P6 格式的字节串。
    """
    n = qr_matrix.module_count
    qz = qr_matrix.quiet_zone
    total = n + 2 * qz
    size = total * module_size

    header = f"P6\n{size} {size}\n255\n".encode("ascii")
    white = b"\xff\xff\xff"
    black = b"\x00\x00\x00"

    pixels = bytearray()
    for img_row in range(size):
        qr_r = img_row // module_size - qz
        in_matrix_r = 0 <= qr_r < n
        row = qr_matrix.matrix[qr_r] if in_matrix_r else None

        for img_col in range(size):
            qr_c = img_col // module_size - qz
            if in_matrix_r and 0 <= qr_c < n and row[qr_c]:
                pixels.extend(black)
            else:
                pixels.extend(white)

    return header + bytes(pixels)


# ---------------------------------------------------------------------------
# 渲染器 C：终端 Unicode（降级显示）
# ---------------------------------------------------------------------------


def matrix_to_unicode(qr_matrix: QRMatrix) -> str:
    """用 Unicode 半块字符渲染 QR（终端降级方案）。

    每个字符表示 2 行 module，大幅压缩高度。
    字符映射: ▀(上黑下白) ▄(上白下黑) █(全黑) ' '(全白)

    Returns:
        多行字符串，可直接 print()。
    """
    n = qr_matrix.module_count
    qz = qr_matrix.quiet_zone
    total = n + 2 * qz

    grid = [[False] * total for _ in range(total)]
    for r in range(n):
        for c in range(n):
            grid[r + qz][c + qz] = qr_matrix.matrix[r][c]

    lines: List[str] = []
    for r in range(0, total, 2):
        line: List[str] = []
        for c in range(total):
            top = grid[r][c]
            bottom = grid[r + 1][c] if r + 1 < total else False
            if top and bottom:
                line.append("\u2588")
            elif top:
                line.append("\u2580")
            elif bottom:
                line.append("\u2584")
            else:
                line.append(" ")
        lines.append("".join(line))

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 渲染器 D：HTML 网格（SVG + 分页 + Prev/Next/Auto 按钮）
# ---------------------------------------------------------------------------


_GRID_CSS = """<style>
body { margin: 0; background: #fff; font-family: -apple-system, sans-serif; }
.info-bar { padding: 8px 12px; background: #222; color: #fff; font-family: monospace; font-size: 13px; }
.qr-page { padding: 12px; }
.qr-grid { display: grid; gap: 18px; }
.qr-cell { background: #fff; padding: 10px; border: 1px solid #ddd; text-align: center; }
.qr-svg { width: 100%; height: auto; max-width: 320px; display: block; margin: 0 auto; }
.qr-label { font-size: 12px; margin-top: 6px; color: #333; font-family: monospace; }
.controls { position: fixed; bottom: 0; left: 0; right: 0; background: #f0f0f0; padding: 10px;
            display: flex; justify-content: center; gap: 14px; align-items: center; border-top: 1px solid #ccc; }
.controls button { padding: 6px 14px; cursor: pointer; font-size: 14px; }
#page-indicator { font-family: monospace; min-width: 110px; text-align: center; }
#player-stage { position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
                background: #000; display: none; align-items: center; justify-content: center;
                z-index: 5; }
#player-stage .qr-svg { width: 90vmin; height: 90vmin; display: block; }
</style>"""

_CYCLE_CSS = """<style>
html, body { margin: 0; padding: 0; height: 100%; background: #000; overflow: hidden;
              font-family: -apple-system, sans-serif; }
.info-bar { position: fixed; top: 0; left: 0; right: 0; z-index: 10;
            padding: 6px 12px; background: #222; color: #fff;
            font-family: monospace; font-size: 13px; }
.qr-page { height: 100vh; display: flex; align-items: center; justify-content: center; }
.qr-cell { background: #fff; padding: 1vmin; }
.qr-svg { width: 90vmin; height: 90vmin; display: block; }
.qr-label { display: none; }
.controls { position: fixed; bottom: 0; left: 0; right: 0; background: #f0f0f0;
            padding: 8px; display: flex; justify-content: center; gap: 14px;
            align-items: center; border-top: 1px solid #ccc; z-index: 10; }
.controls button { padding: 6px 14px; cursor: pointer; font-size: 14px; }
#page-indicator { font-family: monospace; min-width: 110px; text-align: center; }
</style>"""

_GRID_JS_TEMPLATE = """<script>
(function () {
    var pages = document.querySelectorAll('.qr-page');
    var cells = document.querySelectorAll('.qr-cell');
    var totalPages = pages.length;
    var totalFrames = cells.length;
    var currentPage = 0;
    var currentFrame = 0;
    var playMode = "__PLAY_MODE__";
    var autoCycle = __AUTO_CYCLE__;
    var intervalMs = __INTERVAL_MS__;
    var timer = null;
    var indicator = document.getElementById('page-indicator');
    var autoBtn = document.getElementById('auto-btn');
    var stage = document.getElementById('player-stage');

    function showPage(idx) {
        for (var i = 0; i < pages.length; i++) {
            pages[i].style.display = (i === idx) ? '' : 'none';
        }
        currentPage = idx;
        if (indicator) {
            indicator.textContent = 'Page ' + (idx + 1) + ' / ' + totalPages;
        }
    }

    function showFrame(idx) {
        currentFrame = idx;
        if (stage && cells[idx]) {
            var svg = cells[idx].querySelector('.qr-svg');
            if (svg) {
                stage.innerHTML = '';
                stage.appendChild(svg.cloneNode(true));
            }
        }
        if (indicator) {
            indicator.textContent = 'Frame ' + (idx + 1) + ' / ' + totalFrames;
        }
    }

    function enterPlayer() {
        for (var i = 0; i < pages.length; i++) { pages[i].style.display = 'none'; }
        if (stage) { stage.style.display = 'flex'; }
        showFrame(currentFrame);
    }

    function exitPlayer() {
        if (stage) { stage.style.display = 'none'; stage.innerHTML = ''; }
        showPage(currentPage);
    }

    function gotoNextFrame() { if (totalFrames > 1) showFrame((currentFrame + 1) % totalFrames); }
    function gotoPrevFrame() { if (totalFrames > 1) showFrame((currentFrame - 1 + totalFrames) % totalFrames); }
    function gotoNextPage() { if (totalPages > 1) showPage((currentPage + 1) % totalPages); }
    function gotoPrevPage() { if (totalPages > 1) showPage((currentPage - 1 + totalPages) % totalPages); }

    function startAuto() {
        if (timer) { clearInterval(timer); }
        timer = setInterval(playMode === 'frame' ? gotoNextFrame : gotoNextPage, intervalMs);
    }
    function stopAuto() { if (timer) { clearInterval(timer); timer = null; } }

    function toggleAuto() {
        autoCycle = !autoCycle;
        if (autoBtn) { autoBtn.textContent = autoCycle ? 'Auto: ON' : 'Auto: OFF'; }
        if (autoCycle) {
            if (playMode === 'frame') { enterPlayer(); }
            startAuto();
        } else {
            stopAuto();
            if (playMode === 'frame') { exitPlayer(); }
        }
    }

    document.getElementById('prev-btn').addEventListener('click', function () {
        if (playMode === 'frame' && autoCycle) { gotoPrevFrame(); startAuto(); }
        else { gotoPrevPage(); }
    });
    document.getElementById('next-btn').addEventListener('click', function () {
        if (playMode === 'frame' && autoCycle) { gotoNextFrame(); startAuto(); }
        else { gotoNextPage(); }
    });
    if (autoBtn) { autoBtn.addEventListener('click', toggleAuto); }

    showPage(0);
    if (autoCycle) {
        if (playMode === 'frame') { enterPlayer(); }
        startAuto();
    }
})();
</script>"""


_ZIP_JS = """<script>
(function () {
    var zipBtn = document.getElementById('save-zip-btn');
    if (!zipBtn) return;

    var CRC_TABLE = (function () {
        var t = new Array(256);
        for (var n = 0; n < 256; n++) {
            var c = n;
            for (var k = 0; k < 8; k++) {
                c = (c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1);
            }
            t[n] = c >>> 0;
        }
        return t;
    })();

    function crc32(bytes) {
        var c = 0xFFFFFFFF;
        for (var i = 0; i < bytes.length; i++) {
            c = CRC_TABLE[(c ^ bytes[i]) & 0xFF] ^ (c >>> 8);
        }
        return (c ^ 0xFFFFFFFF) >>> 0;
    }

    function u16(n) { return String.fromCharCode(n & 0xFF, (n >>> 8) & 0xFF); }
    function u32(n) { return String.fromCharCode(n & 0xFF, (n >>> 8) & 0xFF, (n >>> 16) & 0xFF, (n >>> 24) & 0xFF); }
    function pad(n, len) { var s = String(n); while (s.length < len) s = '0' + s; return s; }

    function bytesToBinStr(bytes) {
        var out = '';
        for (var i = 0; i < bytes.length; i++) out += String.fromCharCode(bytes[i]);
        return out;
    }

    function buildZip(files) {
        var locals = [];
        var centrals = [];
        var offset = 0;
        for (var i = 0; i < files.length; i++) {
            var nameBytes = '';
            for (var j = 0; j < files[i].name.length; j++) {
                nameBytes += String.fromCharCode(files[i].name.charCodeAt(j) & 0xFF);
            }
            var dataBin = bytesToBinStr(files[i].data);
            var crc = crc32(files[i].data);
            var size = files[i].data.length;

            locals.push(u32(0x04034b50) + u16(20) + u16(0) + u16(0) + u16(0) + u16(0)
                + u32(crc) + u32(size) + u32(size)
                + u16(files[i].name.length) + u16(0) + nameBytes);
            locals.push(dataBin);

            centrals.push(u32(0x02014b50) + u16(20) + u16(20) + u16(0) + u16(0) + u16(0) + u16(0)
                + u32(crc) + u32(size) + u32(size)
                + u16(files[i].name.length) + u16(0) + u16(0) + u16(0) + u16(0) + u32(0) + u32(offset) + nameBytes);

            offset += 30 + files[i].name.length + size;
        }
        var centralBlob = centrals.join('');
        var centralOffset = offset;

        var eocd = u32(0x06054b50) + u16(0) + u16(0)
            + u16(files.length) + u16(files.length)
            + u32(centralBlob.length) + u32(centralOffset) + u16(0);

        return locals.join('') + centralBlob + eocd;
    }

    function svgToPng(svgEl, pxPerModule, cb) {
        var modules = 33;
        var vb = svgEl.getAttribute('viewBox');
        if (vb) {
            var parts = vb.split(/\\s+/);
            modules = parseInt(parts[2], 10) || 33;
        }
        var px = modules * pxPerModule;
        var svgStr = new XMLSerializer().serializeToString(svgEl);
        var url = URL.createObjectURL(new Blob([svgStr], { type: 'image/svg+xml;charset=utf-8' }));
        var img = new Image();
        img.onload = function () {
            try {
                var canvas = document.createElement('canvas');
                canvas.width = px; canvas.height = px;
                var ctx = canvas.getContext('2d');
                ctx.fillStyle = '#ffffff';
                ctx.fillRect(0, 0, px, px);
                ctx.drawImage(img, 0, 0, px, px);
                var b64 = canvas.toDataURL('image/png').split(',')[1];
                var bin = atob(b64);
                var bytes = new Uint8Array(bin.length);
                for (var i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
                cb(bytes);
            } catch (e) {
                cb(null);
            } finally {
                URL.revokeObjectURL(url);
            }
        };
        img.onerror = function () { URL.revokeObjectURL(url); cb(null); };
        img.src = url;
    }

    zipBtn.addEventListener('click', function () {
        var svgs = document.querySelectorAll('.qr-cell .qr-svg');
        if (!svgs.length) { alert('No QR frames to save.'); return; }
        var total = svgs.length;
        var padLen = String(total).length;
        var results = new Array(total);
        var done = 0;
        var failed = 0;
        var origText = zipBtn.textContent;
        zipBtn.disabled = true;

        for (var i = 0; i < total; i++) {
            (function (idx, el) {
                svgToPng(el, 10, function (bytes) {
                    if (bytes) {
                        results[idx] = { name: 'qr_' + pad(idx, padLen) + '.png', data: bytes };
                    } else { failed++; }
                    done++;
                    zipBtn.textContent = 'Zipping ' + done + '/' + total;
                    if (done === total) {
                        if (failed) {
                            zipBtn.disabled = false;
                            zipBtn.textContent = origText;
                            alert('Failed to render ' + failed + ' frame(s).');
                            return;
                        }
                        var files = results.filter(Boolean);
                        var zipStr = buildZip(files);
                        var zipBytes = new Uint8Array(zipStr.length);
                        for (var n = 0; n < zipStr.length; n++) zipBytes[n] = zipStr.charCodeAt(n) & 0xFF;
                        var blob = new Blob([zipBytes], { type: 'application/zip' });
                        var a = document.createElement('a');
                        a.href = URL.createObjectURL(blob);
                        a.download = 'qr_frames.zip';
                        document.body.appendChild(a);
                        a.click();
                        document.body.removeChild(a);
                        setTimeout(function () { URL.revokeObjectURL(a.href); }, 2000);
                        zipBtn.disabled = false;
                        zipBtn.textContent = origText;
                    }
                });
            })(i, svgs[i]);
        }
    });
})();
</script>"""


def _matrix_to_svg(matrix: QRMatrix) -> str:
    n = matrix.module_count
    qz = matrix.quiet_zone
    total = n + 2 * qz
    parts = [
        '<svg viewBox="0 0 %d %d" xmlns="http://www.w3.org/2000/svg" '
        'class="qr-svg" shape-rendering="crispEdges">' % (total, total),
        '<rect width="%d" height="%d" fill="#ffffff"/>' % (total, total),
    ]
    for r in range(n):
        row = matrix.matrix[r]
        for c in range(n):
            if row[c]:
                parts.append(
                    '<rect x="%d" y="%d" width="1" height="1" fill="#000000"/>'
                    % (c + qz, r + qz)
                )
    parts.append('</svg>')
    return "".join(parts)


def _build_grid_js(
    auto_cycle: bool, page_interval_ms: int, play_mode: str = "page"
) -> str:
    return (
        _GRID_JS_TEMPLATE
        .replace("__PLAY_MODE__", play_mode)
        .replace("__AUTO_CYCLE__", "true" if auto_cycle else "false")
        .replace("__INTERVAL_MS__", str(page_interval_ms))
    )


def matrices_to_html_grid(
    matrices: List[QRMatrix],
    cols: int = 4,
    rows_per_page: int = 4,
    page_interval_ms: int = 3000,
    auto_cycle: bool = False,
    file_id: str = "",
    filename: str = "",
    layout: str = "grid",
) -> str:
    """将全部 QR 矩阵渲染成单文件静态 HTML（SVG 网格 + 自动分页 + 按钮翻页）。

    Args:
        matrices: 全部帧的 QR 矩阵（index 0 = manifest，其余为 data）。
        cols: 每页网格列数。
        rows_per_page: 每页网格行数（每页 = cols * rows_per_page 个 QR）。
        page_interval_ms: Auto 轮播时翻页间隔（毫秒）。
        auto_cycle: 是否自动轮播（默认 False，手动 Prev/Next）。
        file_id: 显示在信息栏的 file_id。
        filename: 显示在信息栏的文件名。
        layout: "grid"（网格，默认）或 "cycle"（全屏单 QR 自动循环）。
            grid: Auto OFF = 多张 QR 分页概览（Prev/Next 翻页）；
                  Auto ON = 进入全屏播放舞台，逐张 QR 轮播。
            cycle: 强制 cols=1/rows_per_page=1/auto_cycle=True，每页 1 张，
                   翻页即逐张。

    Returns:
        完整 HTML 文档字符串，可直接 .write_text() 落盘。

    Raises:
        ValueError: matrices 为空，cols / rows_per_page < 1，或 layout 非法。
    """
    if not matrices:
        raise ValueError("matrices must not be empty")
    if layout not in ("grid", "cycle"):
        raise ValueError(
            "layout must be 'grid' or 'cycle', got %r" % layout
        )

    if layout == "cycle":
        cols = 1
        rows_per_page = 1
        auto_cycle = True

    if cols < 1:
        raise ValueError("cols must be >= 1, got %d" % cols)
    if rows_per_page < 1:
        raise ValueError("rows_per_page must be >= 1, got %d" % rows_per_page)

    total = len(matrices)
    total_data = max(0, total - 1)
    per_page = cols * rows_per_page
    num_pages = math.ceil(total / per_page)

    pages_html: List[str] = []
    for page_idx in range(num_pages):
        start = page_idx * per_page
        end = min(start + per_page, total)
        cells: List[str] = []
        for i in range(start, end):
            matrix = matrices[i]
            label = "MANIFEST" if i == 0 else "DATA %d/%d" % (i, total_data)
            cells.append(
                '<div class="qr-cell">'
                + _matrix_to_svg(matrix)
                + '<div class="qr-label">' + label + '</div>'
                + '</div>'
            )
        pages_html.append(
            '<section class="qr-page" id="page-%d">' % (page_idx + 1)
            + '<div class="qr-grid" style="grid-template-columns: repeat(%d, 1fr);">' % cols
            + "".join(cells)
            + '</div>'
            + '</section>'
        )

    auto_label = "Auto: ON" if auto_cycle else "Auto: OFF"
    info_bar = (
        '<div class="info-bar">'
        'file_id: ' + (file_id or "-") + ' | '
        + (filename or "-") + ' | '
        + '%d frames | %d page(s)' % (total, num_pages)
        + '</div>'
    )
    controls = (
        '<div class="controls">'
        '<button id="prev-btn">&#9664; Prev</button>'
        '<span id="page-indicator">Page 1 / %d</span>' % num_pages
        + '<button id="next-btn">Next &#9654;</button>'
        + '<button id="auto-btn">' + auto_label + '</button>'
        + '<button id="save-zip-btn">Save ZIP</button>'
        + '</div>'
    )

    play_mode = "frame" if layout == "grid" else "page"
    stage_html = '<div id="player-stage"></div>\n' if layout == "grid" else ""

    body = (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        + "<title>SQR %s - %s</title>\n" % (
            "Cycle" if layout == "cycle" else "Grid",
            filename or "transfer",
        )
        + (_CYCLE_CSS if layout == "cycle" else _GRID_CSS)
        + "\n</head>\n<body>\n"
        + info_bar + "\n"
        + controls + "\n"
        + stage_html
        + "\n".join(pages_html) + "\n"
        + _build_grid_js(auto_cycle, page_interval_ms, play_mode) + "\n"
        + _ZIP_JS + "\n"
        + "</body>\n</html>\n"
    )
    return body
