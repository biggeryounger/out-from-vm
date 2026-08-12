"""QR 矩阵生成 + 三种渲染器（Canvas / PPM / Terminal）。

不依赖 Pillow。通过 sqr.vendor 的 PIL stub 使 qrcode 导入成功，
但只访问 qr.modules（纯布尔矩阵），从不调用 make_image()。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

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


@dataclass(frozen=True)
class QRMatrix:
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
