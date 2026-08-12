"""Vendor bootstrap：注入 sys.path 和 PIL stub。

在 import qrcode 之前执行。如果系统没有真实 PIL，安装一个最小 stub，
使 qrcode 的 import 链不崩溃。我们只访问 qr.modules，从不调用 make_image()，
所以 stub 的方法永远不会被实际执行。

用法：任何需要 import qrcode 的模块，先 import sqr.vendor。
"""
from __future__ import annotations

import os
import sys
import types

_VENDOR_DIR = os.path.dirname(os.path.abspath(__file__))
if _VENDOR_DIR not in sys.path:
    sys.path.insert(0, _VENDOR_DIR)

if "PIL" not in sys.modules:
    try:
        import PIL  # noqa: F401
    except ImportError:
        _pil = types.ModuleType("PIL")
        _pil.Image = type("Image", (), {
            "new": staticmethod(lambda *a, **k: None),
            "open": staticmethod(lambda *a, **k: None),
        })
        _pil.ImageDraw = type("ImageDraw", (), {
            "Draw": staticmethod(lambda *a, **k: None),
        })
        sys.modules["PIL"] = _pil
        sys.modules["PIL.Image"] = _pil.Image
        sys.modules["PIL.ImageDraw"] = _pil.ImageDraw
