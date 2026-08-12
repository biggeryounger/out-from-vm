#!/usr/bin/env python3
"""打包发送端为可分发的 zip（Tier 1：源码 + vendor）。

在外网构建机上运行，产出 dist/sqr-sender-src.zip。
内网解压后运行 send.sh 即可，无需 pip install。

用法:
    python3 build/bundle_sender.py
"""
from __future__ import annotations

import os
import shutil
import zipfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = PROJECT_ROOT / "dist"
BUNDLE_NAME = "sqr-sender"


def main() -> int:
    DIST_DIR.mkdir(exist_ok=True)

    stage_dir = DIST_DIR / BUNDLE_NAME
    if stage_dir.exists():
        shutil.rmtree(stage_dir)
    stage_dir.mkdir(parents=True)

    print(f"[1/4] Staging sender bundle to {stage_dir}...")

    # Copy sqr package (excluding receiver — sender doesn't need it)
    sqr_src = PROJECT_ROOT / "sqr"
    sqr_dst = stage_dir / "sqr"
    shutil.copytree(sqr_src, sqr_dst,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "receiver"))

    # Copy launcher
    launcher_src = PROJECT_ROOT / "launcher"
    if launcher_src.exists():
        shutil.copy(launcher_src / "send.sh", stage_dir / "send.sh")
        os.chmod(stage_dir / "send.sh", 0o755)
        shutil.copy(launcher_src / "send.bat", stage_dir / "send.bat")

    # Write README
    readme = stage_dir / "README.txt"
    readme.write_text(_README_TEXT, encoding="utf-8")

    print("[2/4] Verifying vendor qrcode...")
    vendor_init = sqr_dst / "vendor" / "__init__.py"
    if not vendor_init.exists():
        print("[error] sqr/vendor/__init__.py not found!")
        return 1

    qrcode_dir = sqr_dst / "vendor" / "qrcode"
    if not qrcode_dir.exists():
        print("[error] sqr/vendor/qrcode/ not found! Run vendor_qrcode.py first.")
        return 1
    py_count = len(list(qrcode_dir.rglob("*.py")))
    print(f"  vendor/qrcode: {py_count} Python files")

    print("[3/4] Creating zip...")
    zip_path = DIST_DIR / f"{BUNDLE_NAME}-src.zip"
    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(stage_dir):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for file in files:
                if file.endswith(".pyc"):
                    continue
                filepath = Path(root) / file
                arcname = filepath.relative_to(stage_dir.parent)
                zf.write(filepath, arcname)

    zip_size_kb = zip_path.stat().st_size / 1024
    print(f"  {zip_path.name}: {zip_size_kb:.0f} KB")

    print("[4/4] Done.")
    print(f"\n  Bundle: {zip_path}")
    print(f"  Usage:  unzip {zip_path.name} && cd {BUNDLE_NAME} && ./send.sh <file>")
    return 0


_README_TEXT = """\
SQR Sender — Screen QR Transfer (Zero-Install)
==============================================

Requirements:
  - Python 3.6+
  - tkinter (included with most Python installations)

Usage (Linux/macOS):
  ./send.sh <file.txt>

Usage (Windows):
  send.bat <file.txt>

Options:
  --interval 1.2          Seconds per QR frame
  --error-correction M    QR error correction: L/M/Q/H
  --max-payload 1200      Max chars per QR payload
  --output-dir <dir>      Save PPM frames (debug)
  --renderer terminal     Use terminal instead of fullscreen window
  --no-player             Only generate frames, don't display

All dependencies are bundled in sqr/vendor/. No pip install needed.
"""


if __name__ == "__main__":
    raise SystemExit(main())
