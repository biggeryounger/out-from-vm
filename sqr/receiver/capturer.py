"""固定区域截图（mss）。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class CaptureRegion:
    """截图区域（屏幕坐标）。"""

    left: int
    top: int
    width: int
    height: int

    def as_mss_dict(self) -> dict:
        return {
            "left": self.left,
            "top": self.top,
            "width": self.width,
            "height": self.height,
        }

    @classmethod
    def from_string(cls, s: str) -> "CaptureRegion":
        """从 "x,y,w,h" 字符串解析。"""
        parts = s.strip().split(",")
        if len(parts) != 4:
            raise ValueError(f"Expected 'x,y,w,h', got {s!r}")
        left, top, width, height = (int(p.strip()) for p in parts)
        return cls(left=left, top=top, width=width, height=height)


class ScreenCapturer:
    """固定区域截图器（线程安全）。"""

    def __init__(self, region: CaptureRegion) -> None:
        self._region = region
        self._sct = None

    def _ensure_sct(self):
        if self._sct is None:
            import mss
            self._sct = mss.mss()
        return self._sct

    def capture(self):
        """截取指定区域，返回 PIL Image。

        Returns:
            PIL.Image 对象（RGB 模式）。
        """
        from PIL import Image

        sct = self._ensure_sct()
        raw = sct.grab(self._region.as_mss_dict())
        img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
        return img

    def close(self) -> None:
        if self._sct is not None:
            self._sct.close()
            self._sct = None
