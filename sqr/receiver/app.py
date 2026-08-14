"""外网接收端启动器 GUI。

启动时显示一个普通控制面板窗口（不全屏），用户按按钮触发跨屏框选，
再按"开始接收"在后台线程跑截图→解码→校验流水线。

线程模型：
- 截图主循环在后台 daemon 线程中运行（tkinter 非线程安全，后台线程
  绝不直接触碰 widget）；
- 进度 / 完成 / 异常事件丢进 queue.Queue；
- 主线程通过 root.after() 每 100ms 轮询队列，更新 UI。
"""
from __future__ import annotations

import os
import queue
import threading
from pathlib import Path
from typing import Any, Optional

from sqr.receiver.capturer import CaptureRegion


# 后台线程向主线程传递的事件类型
_EV_PROGRESS = "progress"
_EV_COMPLETE = "complete"
_EV_ERROR = "error"
_EV_LOG = "log"


class ReceiverApp:
    """接收端启动器主窗口。"""

    def __init__(self) -> None:
        self._check_tkinter()
        import tkinter as tk
        from tkinter import filedialog, messagebox, ttk

        self._tk = tk
        self._ttk = ttk
        self._filedialog = filedialog
        self._messagebox = messagebox

        self.root = tk.Tk()
        self.root.title("SQR 屏幕二维码接收器")
        self.root.resizable(False, False)
        self.root.configure(bg="#f5f5f5")

        # 运行期状态
        self.region: Optional[CaptureRegion] = None
        self._worker: Optional[threading.Thread] = None
        self._stop_event: Optional[threading.Event] = None
        self._event_q: "queue.Queue[tuple]" = queue.Queue()
        self._capturing = False
        self.image_paths: list[Path] = []

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(100, self._drain_queue)

    # ------------------------------------------------------------
    # UI 构建
    # ------------------------------------------------------------
    def _build_ui(self) -> None:
        tk = self._tk
        ttk = self._ttk

        pad = {"padx": 12, "pady": 6}

        # ---- 标题 ----
        title = tk.Label(
            self.root,
            text="SQR 屏幕二维码接收器",
            font=("Helvetica", 18, "bold"),
            bg="#f5f5f5",
            fg="#222222",
        )
        title.grid(row=0, column=0, columnspan=3, **pad, sticky="ew")

        subtitle = tk.Label(
            self.root,
            text="从屏幕上的 QR 码序列还原文件（支持多屏 / 双屏框选）",
            font=("Helvetica", 11),
            bg="#f5f5f5",
            fg="#666666",
        )
        subtitle.grid(row=1, column=0, columnspan=3, padx=12, pady=(0, 8), sticky="ew")

        ttk.Separator(self.root, orient="horizontal").grid(
            row=2, column=0, columnspan=3, sticky="ew", padx=8
        )

        # ---- 基本参数 ----
        tk.Label(self.root, text="输出文件:", bg="#f5f5f5").grid(
            row=3, column=0, sticky="w", **pad
        )
        self.output_var = tk.StringVar(value="sqr_output.txt")
        ttk.Entry(self.root, textvariable=self.output_var, width=36).grid(
            row=3, column=1, sticky="ew", padx=(0, 4)
        )
        ttk.Button(self.root, text="浏览…", width=8, command=self._browse_output).grid(
            row=3, column=2, sticky="w"
        )

        tk.Label(self.root, text="截图间隔(秒):", bg="#f5f5f5").grid(
            row=4, column=0, sticky="w", **pad
        )
        self.interval_var = tk.StringVar(value="0.5")
        ttk.Entry(self.root, textvariable=self.interval_var, width=10).grid(
            row=4, column=1, sticky="w"
        )

        ttk.Separator(self.root, orient="horizontal").grid(
            row=5, column=0, columnspan=3, sticky="ew", padx=8, pady=(8, 0)
        )

        # ---- 步骤 1：框选 ----
        step1 = tk.Label(
            self.root,
            text="① 框选截图区域",
            font=("Helvetica", 12, "bold"),
            bg="#f5f5f5",
            fg="#222222",
        )
        step1.grid(row=6, column=0, columnspan=3, sticky="w", padx=12, pady=(8, 0))

        self.select_btn = ttk.Button(
            self.root,
            text="框选截图区域（覆盖所有屏幕）",
            command=self._on_select_region,
        )
        self.select_btn.grid(row=7, column=0, columnspan=3, sticky="ew", padx=12, pady=4)

        self.region_var = tk.StringVar(value="未选择")
        self.region_label = tk.Label(
            self.root,
            textvariable=self.region_var,
            font=("Courier", 11),
            bg="#f5f5f5",
            fg="#888888",
        )
        self.region_label.grid(row=8, column=0, columnspan=3, sticky="w", padx=12)

        # ---- 步骤 2：接收 ----
        step2 = tk.Label(
            self.root,
            text="② 开始接收",
            font=("Helvetica", 12, "bold"),
            bg="#f5f5f5",
            fg="#222222",
        )
        step2.grid(row=9, column=0, columnspan=3, sticky="w", padx=12, pady=(10, 0))

        btn_frame = tk.Frame(self.root, bg="#f5f5f5")
        btn_frame.grid(row=10, column=0, columnspan=3, sticky="ew", padx=12, pady=4)

        self.start_btn = ttk.Button(
            btn_frame, text="开始接收", command=self._on_start, width=14
        )
        self.start_btn.pack(side="left", padx=(0, 8))

        self.stop_btn = ttk.Button(
            btn_frame, text="停止", command=self._on_stop, width=10, state="disabled"
        )
        self.stop_btn.pack(side="left")

        # 进度条
        self.progress = ttk.Progressbar(
            self.root, orient="horizontal", length=440, mode="determinate"
        )
        self.progress.grid(row=11, column=0, columnspan=3, sticky="ew", padx=12, pady=(6, 0))

        self.progress_var = tk.StringVar(value="状态: 等待开始")
        tk.Label(
            self.root,
            textvariable=self.progress_var,
            font=("Helvetica", 10),
            bg="#f5f5f5",
            fg="#444444",
        ).grid(row=12, column=0, columnspan=3, sticky="w", padx=12, pady=(2, 0))

        # ---- 步骤 3：从 image 文件批量解码 ----
        ttk.Separator(self.root, orient="horizontal").grid(
            row=13, column=0, columnspan=3, sticky="ew", padx=8, pady=(8, 0)
        )
        step3 = tk.Label(
            self.root,
            text="③ 从 image 文件批量解码（无需屏幕截图）",
            font=("Helvetica", 12, "bold"),
            bg="#f5f5f5",
            fg="#222222",
        )
        step3.grid(row=14, column=0, columnspan=3, sticky="w", padx=12, pady=(6, 0))

        img_btn_frame = tk.Frame(self.root, bg="#f5f5f5")
        img_btn_frame.grid(row=15, column=0, columnspan=3, sticky="ew", padx=12, pady=4)

        self.img_files_btn = ttk.Button(
            img_btn_frame, text="选择 image 文件…",
            command=self._on_select_image_files,
        )
        self.img_files_btn.pack(side="left", padx=(0, 8))

        self.img_dir_btn = ttk.Button(
            img_btn_frame, text="选择目录…",
            command=self._on_select_image_dir,
        )
        self.img_dir_btn.pack(side="left", padx=(0, 8))

        self.decode_btn = ttk.Button(
            img_btn_frame, text="开始解码", width=12,
            command=self._on_start_decode,
        )
        self.decode_btn.pack(side="left")

        self.images_var = tk.StringVar(value="未选择 image 文件")
        tk.Label(
            self.root,
            textvariable=self.images_var,
            font=("Courier", 10),
            bg="#f5f5f5",
            fg="#888888",
        ).grid(row=16, column=0, columnspan=3, sticky="w", padx=12)

        # ---- 日志 ----
        ttk.Separator(self.root, orient="horizontal").grid(
            row=17, column=0, columnspan=3, sticky="ew", padx=8, pady=(8, 0)
        )
        tk.Label(
            self.root, text="日志", font=("Helvetica", 10, "bold"), bg="#f5f5f5"
        ).grid(row=18, column=0, columnspan=3, sticky="w", padx=12, pady=(6, 0))

        self.log_text = tk.Text(
            self.root,
            height=8,
            width=64,
            font=("Courier", 10),
            bg="#1e1e1e",
            fg="#d4d4d4",
            state="disabled",
            wrap="word",
        )
        self.log_text.grid(row=19, column=0, columnspan=3, sticky="ew", padx=12, pady=4)

        self.root.grid_columnconfigure(1, weight=1)

    # ------------------------------------------------------------
    # 事件：框选
    # ------------------------------------------------------------
    def _on_select_region(self) -> None:
        if self._capturing:
            self._messagebox.showwarning("提示", "接收进行中，请先停止。")
            return

        # 暂存当前窗口，框选结束后恢复
        try:
            self.root.withdraw()
        except Exception:
            pass

        try:
            from sqr.receiver.region_selector import RegionSelector

            selector = RegionSelector(master=self.root)
            region = selector.select()
        except ImportError as exc:
            self._messagebox.showerror("缺少 tkinter", str(exc))
            region = None
        except Exception as exc:
            self._messagebox.showerror("框选失败", str(exc))
            region = None
        finally:
            try:
                self.root.deiconify()
                self.root.lift()
                self.root.focus_force()
            except Exception:
                pass

        if region is None:
            self._log("框选已取消")
            return

        self.region = region
        self.region_var.set(
            f"已选 {region.width}x{region.height} @ ({region.left},{region.top})"
        )
        self.region_label.config(fg="#007a33")
        self._log(f"选区: {region.left},{region.top},{region.width},{region.height}")

    # ------------------------------------------------------------
    # 事件：开始 / 停止
    # ------------------------------------------------------------
    def _on_start(self) -> None:
        if self._capturing:
            return
        if self.region is None:
            self._messagebox.showwarning("提示", "请先框选截图区域。")
            return

        try:
            interval = float(self.interval_var.get())
            if interval <= 0:
                raise ValueError
        except ValueError:
            self._messagebox.showerror("参数错误", "截图间隔必须是正数。")
            return

        output_str = self.output_var.get().strip()
        if not output_str:
            self._messagebox.showerror("参数错误", "请填写输出文件路径。")
            return
        output_path = Path(output_str).expanduser()

        self._capturing = True
        self._set_controls_busy(True)
        self.progress["value"] = 0
        self.progress_var.set("状态: 接收中…")

        self._stop_event = threading.Event()
        self._worker = threading.Thread(
            target=self._run_capture,
            args=(self.region, output_path, interval, self._stop_event),
            daemon=True,
        )
        self._worker.start()
        self._log(f"开始接收 → {output_path}")

    def _on_stop(self) -> None:
        if not self._capturing or self._stop_event is None:
            return
        self._stop_event.set()
        self.progress_var.set("状态: 正在停止…")
        self._log("用户请求停止")

    # ------------------------------------------------------------
    # 事件：image 批量解码
    # ------------------------------------------------------------
    def _on_select_image_files(self) -> None:
        if self._capturing:
            self._messagebox.showwarning("提示", "接收进行中，请先停止。")
            return
        paths = self._filedialog.askopenfilenames(
            title="选择 QR image 文件",
            filetypes=[
                ("QR 图片", "*.ppm *.png *.jpg *.jpeg"),
                ("所有文件", "*.*"),
            ],
        )
        if not paths:
            return
        self.image_paths = [Path(p) for p in paths]
        self.images_var.set(f"已选 {len(self.image_paths)} 个文件")
        self._log(f"已选 image 文件: {len(self.image_paths)} 个")

    def _on_select_image_dir(self) -> None:
        if self._capturing:
            self._messagebox.showwarning("提示", "接收进行中，请先停止。")
            return
        d = self._filedialog.askdirectory(title="选择含 QR image 的目录")
        if not d:
            return
        exts = {".ppm", ".png", ".jpg", ".jpeg"}
        self.image_paths = sorted(
            p for p in Path(d).iterdir() if p.suffix.lower() in exts
        )
        self.images_var.set(f"已选 {len(self.image_paths)} 个文件（来自目录）")
        self._log(f"目录扫描: {len(self.image_paths)} 个 image 文件")

    def _on_start_decode(self) -> None:
        if self._capturing:
            return
        if not self.image_paths:
            self._messagebox.showwarning("提示", "请先选择 image 文件或目录。")
            return
        output_str = self.output_var.get().strip()
        if not output_str:
            self._messagebox.showerror("参数错误", "请填写输出文件路径。")
            return
        output_path = Path(output_str).expanduser()

        self._capturing = True
        self._set_controls_busy(True)
        self.progress["value"] = 0
        self.progress_var.set("状态: 解码中…")

        self._worker = threading.Thread(
            target=self._run_decode,
            args=(list(self.image_paths), output_path),
            daemon=True,
        )
        self._worker.start()
        self._log(f"开始解码 {len(self.image_paths)} 个 image → {output_path}")

    # ------------------------------------------------------------
    # 后台线程：截图主循环
    # ------------------------------------------------------------
    def _run_capture(
        self,
        region: CaptureRegion,
        output_path: Path,
        interval: float,
        stop_event: threading.Event,
    ) -> None:
        from sqr.receiver.runner import run_receiver

        def on_progress(progress):
            self._event_q.put((_EV_PROGRESS, progress))

        def on_complete(result, path):
            self._event_q.put((_EV_COMPLETE, result, path))

        try:
            run_receiver(
                region=region,
                output_path=output_path,
                interval_ms=int(interval * 1000),
                on_progress=on_progress,
                on_complete=on_complete,
                stop_event=stop_event,
            )
        except Exception as exc:
            self._event_q.put((_EV_ERROR, str(exc)))

    def _run_decode(self, image_paths: list, output_path: Path) -> None:
        from sqr.receiver.image_decoder import run_receiver_from_images

        def on_progress(progress):
            self._event_q.put((_EV_PROGRESS, progress))

        def on_complete(result, path):
            self._event_q.put((_EV_COMPLETE, result, path))

        try:
            run_receiver_from_images(
                image_paths,
                output_path,
                on_progress=on_progress,
                on_complete=on_complete,
            )
        except Exception as exc:
            self._event_q.put((_EV_ERROR, str(exc)))

    # ------------------------------------------------------------
    # 主线程：轮询事件队列
    # ------------------------------------------------------------
    def _drain_queue(self) -> None:
        try:
            while True:
                ev = self._event_q.get_nowait()
                self._handle_event(ev)
        except queue.Empty:
            pass
        self.root.after(100, self._drain_queue)

    def _handle_event(self, ev: tuple) -> None:
        kind = ev[0]
        if kind == _EV_PROGRESS:
            self._on_progress_event(ev[1])
        elif kind == _EV_COMPLETE:
            self._on_complete_event(ev[1], ev[2])
        elif kind == _EV_ERROR:
            self._on_error_event(ev[1])
        elif kind == _EV_LOG:
            self._log(ev[1])

    def _on_progress_event(self, progress: Any) -> None:
        pct = progress.percent
        self.progress["value"] = pct
        self.progress_var.set(
            f"状态: {progress.received_count}/{progress.total} "
            f"({pct:.0f}%)  拒绝={progress.rejected_count}"
        )

    def _on_complete_event(self, result: Any, path: Any) -> None:
        self._capturing = False
        self._set_controls_busy(False)
        if result.success:
            self.progress["value"] = 100
            self.progress_var.set("状态: 接收完成 ✓")
            self._log(
                f"完成 ✓ 字节={result.actual_bytes} sha256={result.actual_sha256} "
                f"md5={result.actual_md5}"
            )
            self._log(f"已保存 → {path}")
            self._messagebox.showinfo(
                "接收成功",
                f"已保存到:\n{path}\n\n字节: {result.actual_bytes}\nSHA-256:\n{result.actual_sha256}",
            )
        else:
            self.progress_var.set("状态: 校验失败")
            self._log(f"失败: {result.message}")
            self._messagebox.showerror("校验失败", result.message)

    def _on_error_event(self, message: str) -> None:
        self._capturing = False
        self._set_controls_busy(False)
        self.progress_var.set("状态: 出错")
        self._log(f"错误: {message}")
        self._messagebox.showerror("接收出错", message)

    # ------------------------------------------------------------
    # UI helpers
    # ------------------------------------------------------------
    def _set_controls_busy(self, busy: bool) -> None:
        state_main = "disabled" if busy else "normal"
        self.select_btn.config(state=state_main)
        self.start_btn.config(state=state_main)
        self.stop_btn.config(state="normal" if busy else "disabled")
        self.img_files_btn.config(state=state_main)
        self.img_dir_btn.config(state=state_main)
        self.decode_btn.config(state=state_main)

    def _browse_output(self) -> None:
        path = self._filedialog.asksaveasfilename(
            title="选择输出文件",
            defaultextension=".txt",
            filetypes=[
                ("文本文件", "*.txt"),
                ("所有文件", "*.*"),
            ],
        )
        if path:
            self.output_var.set(path)

    def _log(self, message: str) -> None:
        import time

        stamp = time.strftime("%H:%M:%S")
        self.log_text.config(state="normal")
        self.log_text.insert("end", f"[{stamp}] {message}\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def _on_close(self) -> None:
        if self._capturing and self._stop_event is not None:
            self._stop_event.set()
        try:
            self.root.destroy()
        except Exception:
            pass

    @staticmethod
    def _check_tkinter() -> None:
        try:
            import tkinter  # noqa: F401
        except ImportError as exc:
            import sys
            raise ImportError(
                f"GUI 需要 tkinter，但当前 Python ({sys.version.split()[0]}) 缺少 _tkinter。\n"
                f"安装方式：\n"
                f"  macOS:   brew install python-tk@{sys.version_info.major}.{sys.version_info.minor}\n"
                f"  Ubuntu:  sudo apt install python3-tk"
            ) from exc


def launch() -> int:
    """启动接收端 GUI，返回退出码。"""
    app = ReceiverApp()
    app.root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(launch())
