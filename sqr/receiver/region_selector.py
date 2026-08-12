"""跨屏拖拽框选截图区域（支持多显示器 / 双屏）。

显示逻辑：
- 截取整个虚拟桌面（mss.monitors[0]，覆盖所有物理屏）；
- 为每个物理显示器创建一个无边框全屏 Toplevel 覆盖层，各自显示该屏
  对应区域的暗化截图；
- 用户在任意一台显示器上拖拽框选，选区实时显示尺寸；
- 松开鼠标后坐标自动换算为虚拟桌面绝对坐标（CaptureRegion），
  保证后续 capturer 能抓到正确区域，哪怕选区在副屏。

依赖：tkinter (stdlib) + Pillow + mss（接收端已有）。
tkinter 延迟导入——缺失时给出明确提示而非崩溃。
"""
from __future__ import annotations

from typing import Any, List, Optional, Tuple

from sqr.receiver.capturer import CaptureRegion


def _check_tkinter() -> None:
    """检查 tkinter 可用性，给出安装指引。"""
    try:
        import tkinter  # noqa: F401
    except ImportError as exc:
        import sys
        raise ImportError(
            f"GUI 框选需要 tkinter，但当前 Python ({sys.version.split()[0]}) 缺少 _tkinter。\n"
            f"安装方式：\n"
            f"  macOS:   brew install python-tk@{sys.version_info.major}.{sys.version_info.minor}\n"
            f"  Ubuntu:  sudo apt install python3-tk\n"
            f"  或者跳过 GUI：python3 -m sqr.cli receive --region x,y,w,h"
        ) from exc


class _MonitorOverlay:
    """单个物理显示器的全屏覆盖层。

    每个覆盖层只负责本屏范围内的拖拽；拖拽坐标通过 monitor 的绝对
    offset 换算成虚拟桌面绝对坐标，写入共享的 selector 状态。
    """

    def __init__(
        self,
        selector: "RegionSelector",
        root: Any,
        mon: dict,
        bright_full_img: Any,
    ) -> None:
        self.selector = selector
        self.mon = mon
        self.bright_full_img = bright_full_img

        import tkinter as tk
        from PIL import Image, ImageEnhance, ImageTk

        # 本屏区域在虚拟桌面全图中的像素偏移
        virt = selector.virtual_desktop
        self.crop_x = mon["left"] - virt["left"]
        self.crop_y = mon["top"] - virt["top"]

        # 裁出本屏亮版 → 暗版背景
        mon_bright = bright_full_img.crop(
            (
                self.crop_x,
                self.crop_y,
                self.crop_x + mon["width"],
                self.crop_y + mon["height"],
            )
        )
        self.mon_bright = mon_bright
        dark = ImageEnhance.Brightness(mon_bright).enhance(0.35)

        # 无边框全屏 Toplevel，定位到本屏绝对坐标
        self.top = tk.Toplevel(root)
        self.top.overrideredirect(True)
        self.top.geometry(f"{mon['width']}x{mon['height']}+{mon['left']}+{mon['top']}")
        self.top.attributes("-topmost", True)
        self.top.configure(bg="black")

        self.canvas = tk.Canvas(
            self.top,
            cursor="crosshair",
            highlightthickness=0,
            bg="black",
        )
        self.canvas.pack(fill="both", expand=True)

        self.dark_photo = ImageTk.PhotoImage(dark)
        self.canvas.create_image(0, 0, image=self.dark_photo, anchor="nw", tags="bg")

        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Button-2>", self.selector._on_cancel)
        self.canvas.bind("<Button-3>", self.selector._on_cancel)

        # macOS aqua 下 overrideredirect(True) 的无边框窗口拿不到键盘焦点，
        # 单纯 bind 在 Toplevel 上的 <Return>/<Escape> 不会触发。
        # 这里在所有层级都绑一遍作为兜底；真正可靠的确认/取消靠屏幕按钮。
        for widget in (self.top, self.canvas):
            widget.bind("<Escape>", self.selector._on_cancel)
            widget.bind("<Return>", self.selector._on_confirm)
            widget.bind("<KP_Enter>", self.selector._on_confirm)

        # macOS 下无边框窗口默认拿不到键盘焦点，强制聚焦
        try:
            self.top.focus_force()
        except Exception:
            pass

        # 本覆盖层内的拖拽状态
        self._start_x: int = 0
        self._start_y: int = 0
        self._rect_id: Optional[int] = None
        self._spotlight_id: Optional[int] = None
        self._spotlight_photo: Any = None

    # ---- 坐标换算 ----
    def _local_to_abs(self, lx: int, ly: int) -> Tuple[int, int]:
        """本窗口内像素 → 虚拟桌面绝对坐标。"""
        return (self.mon["left"] + lx, self.mon["top"] + ly)

    # ---- 鼠标事件 ----
    def _on_press(self, event: Any) -> None:
        self.selector.set_active_overlay(self)
        self._start_x = event.x
        self._start_y = event.y

        if self._rect_id is not None:
            self.canvas.delete(self._rect_id)
            self._rect_id = None
        if self._spotlight_id is not None:
            self.canvas.delete(self._spotlight_id)
            self._spotlight_id = None
            self._spotlight_photo = None

        self._rect_id = self.canvas.create_rectangle(
            event.x, event.y, event.x, event.y,
            outline="#00ff88", width=3,
        )

    def _on_drag(self, event: Any) -> None:
        if self._rect_id is None:
            return
        x1 = min(self._start_x, event.x)
        y1 = min(self._start_y, event.y)
        x2 = max(self._start_x, event.x)
        y2 = max(self._start_y, event.y)

        self.canvas.coords(self._rect_id, x1, y1, x2, y2)

        w = x2 - x1
        h = y2 - y1
        self.selector.update_size_label(w, h)

        self._update_spotlight(x1, y1, x2, y2)

    def _update_spotlight(self, x1: int, y1: int, x2: int, y2: int) -> None:
        """在选区内显示亮版截图（聚光灯效果）。"""
        if x2 - x1 < 2 or y2 - y1 < 2:
            return

        from PIL import ImageTk

        # 从本屏亮版裁出选区
        crop = self.mon_bright.crop((x1, y1, x2, y2))
        self._spotlight_photo = ImageTk.PhotoImage(crop)

        if self._spotlight_id is not None:
            self.canvas.delete(self._spotlight_id)

        self._spotlight_id = self.canvas.create_image(
            x1, y1, image=self._spotlight_photo, anchor="nw",
        )
        self.canvas.tag_lower(self._spotlight_id, self._rect_id)
        self.canvas.tag_lower("bg", self._spotlight_id)

    def _on_release(self, event: Any) -> None:
        if self._rect_id is None:
            return
        x1 = min(self._start_x, event.x)
        y1 = min(self._start_y, event.y)
        x2 = max(self._start_x, event.x)
        y2 = max(self._start_y, event.y)

        if x2 - x1 < 20 or y2 - y1 < 20:
            self.canvas.delete(self._rect_id)
            self._rect_id = None
            if self._spotlight_id is not None:
                self.canvas.delete(self._spotlight_id)
                self._spotlight_id = None
                self._spotlight_photo = None
            self.selector.update_size_label(0, 0, too_small=True)
            self.selector.clear_pending()
            return

        # 换算为虚拟桌面绝对坐标
        abs_x1, abs_y1 = self._local_to_abs(x1, y1)
        abs_x2, abs_y2 = self._local_to_abs(x2, y2)

        self.selector.set_pending_region(
            abs_x1, abs_y1, abs_x2 - abs_x1, abs_y2 - abs_y1,
        )

    def destroy(self) -> None:
        try:
            self.top.destroy()
        except Exception:
            pass


class RegionSelector:
    """跨屏全屏截图 + 拖拽框选区域选择器（支持双屏 / 多屏）。

    用法:
        selector = RegionSelector()
        region = selector.select()
        if region:
            print(f"Selected: {region}")

    也可嵌入已有 Tk root（GUI app 共用 root）:
        selector = RegionSelector(master=app_root)
        region = selector.select()
    """

    def __init__(self, master: Any = None) -> None:
        self._master = master
        self.region: Optional[CaptureRegion] = None

        self.virtual_desktop: dict = {"left": 0, "top": 0, "width": 0, "height": 0}
        self._overlays: List[_MonitorOverlay] = []
        self._active_overlay: Optional[_MonitorOverlay] = None
        self._pending_region: Optional[CaptureRegion] = None

        self._own_root = master is None
        self._root: Any = None
        self._title_label: Any = None
        self._size_label: Any = None
        self._confirm_btn: Any = None
        self._cancel_btn: Any = None
        self._bright_full_img: Any = None

    def select(self) -> Optional[CaptureRegion]:
        """显示全屏覆盖层，等待用户拖拽选区。

        Raises:
            ImportError: tkinter 不可用。

        Returns:
            CaptureRegion 或 None（用户按 ESC 取消）。
        """
        _check_tkinter()
        import tkinter as tk

        if self._own_root:
            self._root = tk.Tk()
            self._root.withdraw()  # 主屏覆盖改由 Toplevel 承担
        else:
            self._root = self._master

        # 截取整个虚拟桌面（所有屏合一）
        self._capture_virtual_desktop()

        monitors = self._enum_monitors()
        if not monitors:
            return None

        # 为每个物理屏创建覆盖层
        for mon in monitors:
            overlay = _MonitorOverlay(self, self._root, mon, self._bright_full_img)
            self._overlays.append(overlay)

        # 兜底：键盘也绑在 root 上（部分平台有效）
        self._root.bind("<Escape>", self._on_cancel)
        self._root.bind("<Return>", self._on_confirm)
        self._root.bind("<KP_Enter>", self._on_confirm)

        # 提示条 + 屏幕按钮挂在第一个（主）覆盖层上。
        # macOS 无边框窗口键盘焦点不可靠，因此确认/取消主要靠鼠标点按钮。
        primary = self._overlays[0]

        self._cancel_btn = tk.Button(
            primary.top,
            text="  ✗ 取消  ",
            command=self._on_cancel,
            font=("Helvetica", 14, "bold"),
            bg="#cc3333",
            fg="#ffffff",
            activebackground="#aa2222",
            activeforeground="#ffffff",
            padx=20,
            pady=10,
            relief="flat",
            cursor="hand2",
            bd=0,
        )
        self._cancel_btn.place(x=24, y=20, anchor="nw")

        self._confirm_btn = tk.Button(
            primary.top,
            text="  ✓ 确认  ",
            command=self._on_confirm,
            font=("Helvetica", 14, "bold"),
            bg="#1a8a3a",
            fg="#ffffff",
            activebackground="#157030",
            activeforeground="#ffffff",
            padx=20,
            pady=10,
            relief="flat",
            cursor="hand2",
            bd=0,
            state="disabled",
        )
        self._confirm_btn.place(relx=1.0, x=-24, y=20, anchor="ne")

        self._title_label = tk.Label(
            primary.top,
            text=(
                f"拖拽框选 QR 码区域（共 {len(monitors)} 屏，可在任意屏上选择）"
                f"  |  点按钮或 ENTER 确认  |  ESC 取消"
            ),
            font=("Helvetica", 15, "bold"),
            bg="#000000",
            fg="#00ff88",
            padx=20,
            pady=10,
        )
        self._title_label.place(relx=0.5, y=24, anchor="n")

        self._size_label = tk.Label(
            primary.top,
            text="",
            font=("Courier", 14),
            bg="#000000",
            fg="#ffffff",
            padx=10,
            pady=5,
        )
        self._size_label.place(relx=0.5, rely=0.97, anchor="s")

        self._root.mainloop()

        self._destroy_overlays()
        if self._own_root:
            try:
                self._root.destroy()
            except Exception:
                pass

        return self.region

    # ---- 截屏 ----
    def _capture_virtual_desktop(self) -> None:
        """截取整个虚拟桌面，保存亮版 PIL Image。"""
        import mss
        from PIL import Image

        with mss.mss() as sct:
            self.virtual_desktop = dict(sct.monitors[0])
            raw = sct.grab(self.virtual_desktop)

        self._bright_full_img = Image.frombytes(
            "RGB", raw.size, raw.bgra, "raw", "BGRX"
        )

    def _enum_monitors(self) -> List[dict]:
        """枚举所有物理显示器（跳过 monitors[0] 虚拟桌面聚合项）。"""
        import mss

        with mss.mss() as sct:
            return [dict(m) for m in sct.monitors[1:]]

    # ---- overlay 回调 ----
    def set_active_overlay(self, overlay: _MonitorOverlay) -> None:
        self._active_overlay = overlay

    def update_size_label(self, w: int, h: int, too_small: bool = False) -> None:
        if self._size_label is None:
            return
        if too_small:
            self._size_label.config(text="  区域太小，请重新拖拽  ")
        else:
            self._size_label.config(text=f"  {w} x {h} px  ")

    def set_pending_region(self, x: int, y: int, w: int, h: int) -> None:
        self._pending_region = CaptureRegion(left=x, top=y, width=w, height=h)
        if self._title_label is not None:
            self._title_label.config(
                text=(
                    f"已选 {w}x{h} @ ({x},{y})  |  "
                    f"点 ✓按钮 或 ENTER 确认  |  重新拖拽可修改"
                ),
                fg="#00ff00",
            )
        if self._confirm_btn is not None:
            self._confirm_btn.config(state="normal")

    def clear_pending(self) -> None:
        """选区无效（太小）时清空待确认状态并禁用确认按钮。"""
        self._pending_region = None
        if self._confirm_btn is not None:
            self._confirm_btn.config(state="disabled")

    def _on_confirm(self, event: Any = None) -> None:
        if self._pending_region is not None:
            self.region = self._pending_region
        self._root.quit()

    def _on_cancel(self, event: Any = None) -> None:
        self.region = None
        self._root.quit()

    def _destroy_overlays(self) -> None:
        for ov in self._overlays:
            ov.destroy()
        self._overlays.clear()


def select_region() -> Optional[CaptureRegion]:
    """便捷函数：弹出跨屏框选器，返回 CaptureRegion 或 None。

    Raises:
        ImportError: tkinter 不可用。
    """
    selector = RegionSelector()
    return selector.select()
