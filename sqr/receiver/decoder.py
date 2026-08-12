"""QR 解码：从图像或文件中解码 QR 字符串。

首选 pyzbar（ZBar 绑定），自动回退 opencv。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional


def decode_qr(image: Any) -> Optional[str]:
    """从 PIL Image / numpy array 解码 QR，返回原始字符串。

    Args:
        image: PIL.Image 对象或 numpy array。

    Returns:
        QR 内容字符串；未识别到 QR 返回 None。
    """
    result = _decode_with_pyzbar(image)
    if result is not None:
        return result

    result = _decode_with_opencv(image)
    return result


def decode_qr_from_file(path: str | Path) -> Optional[str]:
    """从图像文件解码 QR。

    Args:
        path: 图像文件路径（PPM / PNG / JPEG 等）。

    Returns:
        QR 内容字符串；未识别到 QR 返回 None。
    """
    from PIL import Image

    img = Image.open(str(path))
    if img.mode != "RGB":
        img = img.convert("RGB")
    return decode_qr(img)


def _decode_with_pyzbar(image: Any) -> Optional[str]:
    """使用 pyzbar (ZBar) 解码。"""
    try:
        from pyzbar.pyzbar import decode
    except ImportError:
        return None

    results = decode(image)
    if not results:
        return None

    data = results[0].data
    return data.decode("utf-8") if isinstance(data, bytes) else str(data)


def _decode_with_opencv(image: Any) -> Optional[str]:
    """使用 opencv-python QRCodeDetector 解码（回退方案）。"""
    try:
        import cv2
        import numpy as np
    except ImportError:
        return None

    if hasattr(image, "mode"):
        arr = np.array(image)
    else:
        arr = image

    if arr.ndim == 3 and arr.shape[2] == 3:
        arr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)

    detector = cv2.QRCodeDetector()
    data, points, straight_qrcode = detector.detectAndDecode(arr)

    if data:
        return data
    return None
