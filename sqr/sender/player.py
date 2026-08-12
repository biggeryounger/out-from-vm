"""tkinter 全屏循环播放 QR 帧。

使用 Canvas 直接渲染，不依赖 Pillow / PhotoImage。
"""
from __future__ import annotations

import sys
import tkinter as tk
from typing import List, Optional

from sqr.sender.qr_render import QRMatrix, draw_matrix_on_canvas


class QRPlayer:
    """全屏循环播放 QR 帧的 tkinter 窗口。

    使用 Canvas 直接渲染，不依赖 Pillow / PhotoImage。
    帧序: manifest → data_1 → data_2 → ... → data_N → manifest → ...
    """

    def __init__(
        self,
        matrices: List[QRMatrix],
        file_id: str,
        total: int,
        filename: str,
        module_size: int = 10,
        interval_ms: int = 1200,
        title: str = "SQR Sender",
    ) -> None:
        self._matrices = matrices
        self._file_id = file_id
        self._total = total
        self._filename = filename
        self._module_size = module_size
        self._interval_ms = interval_ms
        self._title = title
        self._current = 0
        self._root: Optional[tk.Tk] = None
        self._canvas: Optional[tk.Canvas] = None
        self._info_label: Optional[tk.Label] = None
        self._running = False

    def run(self) -> None:
        """启动 tkinter mainloop（阻塞直到 ESC 或窗口关闭）。"""
        self._root = tk.Tk()
        self._root.title(self._title)
        self._root.attributes("-fullscreen", True)
        self._root.configure(bg="white")
        self._root.bind("<Escape>", self._on_quit)
        self._root.bind("<q>", self._on_quit)

        self._canvas = tk.Canvas(
            self._root, bg="white", highlightthickness=0
        )
        self._canvas.pack(fill="both", expand=True)

        self._info_label = tk.Label(
            self._root,
            text="",
            font=("Courier", 16),
            bg="white",
            fg="black",
            anchor="w",
        )
        self._info_label.pack(side="bottom", fill="x")

        self._running = True
        self._show_frame()
        self._root.mainloop()

    def stop(self) -> None:
        """从外部线程请求停止。"""
        self._running = False
        if self._root:
            self._root.after(0, self._root.quit)

    def _show_frame(self) -> None:
        """渲染当前帧 + 调度下一帧。"""
        if not self._running or self._root is None:
            return

        matrix = self._matrices[self._current]
        pixel_size = draw_matrix_on_canvas(
            self._canvas, matrix, self._module_size
        )

        screen_w = self._root.winfo_screenwidth()
        screen_h = self._root.winfo_screenheight()
        self._canvas.config(
            scrollregion=(0, 0, pixel_size, pixel_size)
        )

        index = self._current
        frame_label = "MANIFEST" if index == 0 else f"DATA {index}/{self._total}"
        self._info_label.config(
            text=(
                f"  {frame_label}  |  "
                f"file_id={self._file_id}  |  "
                f"{self._filename}  |  "
                f"{pixel_size}x{pixel_size}px  |  "
                f"ESC to quit"
            )
        )

        self._current = (self._current + 1) % len(self._matrices)
        self._root.after(self._interval_ms, self._show_frame)

    def _on_quit(self, event=None) -> None:
        self._running = False
        if self._root:
            self._root.quit()


def run_player_from_matrices(
    matrices: List[QRMatrix],
    file_id: str,
    total: int,
    filename: str,
    module_size: int = 10,
    interval_ms: int = 1200,
) -> None:
    """便捷函数：创建并运行 QRPlayer。"""
    player = QRPlayer(
        matrices=matrices,
        file_id=file_id,
        total=total,
        filename=filename,
        module_size=module_size,
        interval_ms=interval_ms,
    )
    player.run()
