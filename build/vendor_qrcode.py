#!/usr/bin/env python3
"""下载 qrcode 纯 Python 源码到 sqr/vendor/qrcode/。

在外网构建机上运行一次即可。之后 vendor 目录随项目打包传入内网。

用法:
    python3 build/vendor_qrcode.py
"""
from __future__ import annotations

import os
import shutil
import sys
import subprocess


VENDOR_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "sqr", "vendor",
)
QRCODE_DIR = os.path.join(VENDOR_DIR, "qrcode")
VERSION_FILE = os.path.join(VENDOR_DIR, "QRCODE_VERSION")


def main() -> int:
    if os.path.exists(QRCODE_DIR):
        print(f"[skip] {QRCODE_DIR} already exists")
        return 0

    print("[1/4] Downloading qrcode source...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "download", "qrcode",
         "--no-deps", "--no-binary", ":all:",
         "-d", "/tmp/_sqr_qrcode_dl"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"[error] pip download failed:\n{result.stderr}")
        return 1

    import glob
    import tarfile
    sdist_files = glob.glob("/tmp/_sqr_qrcode_dl/qrcode-*.tar.gz")
    if not sdist_files:
        print("[error] No sdist found after pip download")
        return 1

    sdist_path = sdist_files[0]

    print("[2/4] Extracting...")
    extract_dir = "/tmp/_sqr_qrcode_extract"
    if os.path.exists(extract_dir):
        shutil.rmtree(extract_dir)
    with tarfile.open(sdist_path) as tar:
        tar.extractall(extract_dir)

    src_dirs = glob.glob(os.path.join(extract_dir, "qrcode-*"))
    if not src_dirs:
        print("[error] No extracted source directory found")
        return 1
    src_dir = src_dirs[0]

    print("[3/4] Copying qrcode package to vendor/...")
    src_pkg = os.path.join(src_dir, "qrcode")
    if not os.path.isdir(src_pkg):
        print(f"[error] qrcode package not found in {src_dir}")
        return 1

    shutil.copytree(src_pkg, QRCODE_DIR)

    for cache in [
        os.path.join(QRCODE_DIR, "__pycache__"),
        os.path.join(QRCODE_DIR, "tests"),
    ]:
        if os.path.exists(cache):
            shutil.rmtree(cache)

    version = os.path.basename(src_dir).replace("qrcode-", "")
    with open(VERSION_FILE, "w") as f:
        f.write(version + "\n")
    print(f"[ok] Vendored qrcode version: {version}")

    print("[4/4] Verifying import without Pillow...")
    verify_code = (
        "import sqr.vendor; import qrcode; "
        "qr = qrcode.QRCode(); "
        "qr.add_data('test'); qr.make(fit=True); "
        "print(f'matrix size: {len(qr.modules)}'); "
        "print('VERIFY OK')"
    )
    result = subprocess.run(
        [sys.executable, "-c", verify_code],
        capture_output=True, text=True,
        cwd=os.path.dirname(os.path.dirname(VENDOR_DIR)),
    )
    if result.returncode != 0:
        print(f"[error] Verification failed:\n{result.stderr}")
        return 1
    print(result.stdout.strip())

    shutil.rmtree("/tmp/_sqr_qrcode_dl", ignore_errors=True)
    shutil.rmtree(extract_dir, ignore_errors=True)
    print("[done] vendor_qrcode.py complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
