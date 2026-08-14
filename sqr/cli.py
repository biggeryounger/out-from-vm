#!/usr/bin/env python3
"""SQR 命令行入口：send / receive。

用法:
    python -m sqr.cli send <FILE> [OPTIONS]
    python -m sqr.cli receive --region x,y,w,h --output <PATH> [OPTIONS]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List

from sqr.protocol import compute_file_id, compute_md5, compute_sha256
from sqr.sender.chunker import build_all_frames
from sqr.sender.qr_render import QRMatrix, generate_matrix, matrices_to_html_grid


def _parse_region(s: str):
    from sqr.receiver.capturer import CaptureRegion
    return CaptureRegion.from_string(s)


def cmd_send(args: argparse.Namespace) -> int:
    """发送端：压缩 → 分片 → QR → 全屏播放。"""
    file_path = Path(args.file)

    if not file_path.exists():
        print(f"Error: file not found: {file_path}", file=sys.stderr)
        return 1

    raw = file_path.read_bytes()

    try:
        raw.decode("utf-8")
    except UnicodeDecodeError:
        print(f"Error: {file_path} is not valid UTF-8", file=sys.stderr)
        return 1

    sha256_hex = compute_sha256(raw)
    md5_hex = compute_md5(raw)
    file_id = compute_file_id(sha256_hex)
    filename = file_path.name

    print(f"File:     {filename}")
    print(f"Bytes:    {len(raw)}")
    print(f"SHA-256:  {sha256_hex}")
    print(f"MD5:      {md5_hex}")
    print(f"File ID:  {file_id}")

    manifest, chunks = build_all_frames(
        filename, raw, sha256_hex, md5_hex,
        max_chars=args.max_payload,
        use_zstd=args.zstd,
    )

    data_count = len(chunks) - 1
    print(f"Chunks:   {data_count} data + 1 manifest = {len(chunks)} total")
    print(f"Interval: {args.interval}s/frame")

    if args.output_dir:
        from sqr.sender.qr_render import matrix_to_ppm
        out_dir = Path(args.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        for chunk in chunks:
            qr = generate_matrix(
                chunk.encode(),
                error_correction=args.error_correction,
            )
            ppm_data = matrix_to_ppm(qr, module_size=args.module_size)
            ppm_path = out_dir / f"frame_{chunk.index:04d}.ppm"
            ppm_path.write_bytes(ppm_data)
        print(f"PPM frames saved to: {out_dir}")

    matrices: List[QRMatrix] = []
    for chunk in chunks:
        qr = generate_matrix(
            chunk.encode(),
            error_correction=args.error_correction,
        )
        matrices.append(qr)

    if args.html_grid:
        html = matrices_to_html_grid(
            matrices,
            cols=args.grid_cols,
            rows_per_page=args.page_rows,
            page_interval_ms=int(args.page_interval * 1000),
            file_id=file_id,
            filename=filename,
            layout="grid",
        )
        html_path = Path(args.html_grid)
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text(html, encoding="utf-8")
        print(f"HTML grid saved to: {html_path} ({len(matrices)} frames)")
        return 0

    if args.html_cycle:
        html = matrices_to_html_grid(
            matrices,
            page_interval_ms=int(args.interval * 1000),
            file_id=file_id,
            filename=filename,
            layout="cycle",
        )
        html_path = Path(args.html_cycle)
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text(html, encoding="utf-8")
        print(f"HTML cycle saved to: {html_path} ({len(matrices)} frames, Auto: ON)")
        print("Open this file in a browser to start the QR transfer.")
        return 0

    if args.renderer == "terminal":
        from sqr.sender.qr_render import matrix_to_unicode
        import time
        print("\n" + "=" * 60)
        print(f"Terminal QR display (interval={args.interval}s)")
        print("Press Ctrl+C to stop.\n")
        try:
            for matrix in matrices:
                print(matrix_to_unicode(matrix))
                time.sleep(args.interval)
        except KeyboardInterrupt:
            pass
        return 0

    html = matrices_to_html_grid(
        matrices,
        page_interval_ms=int(args.interval * 1000),
        file_id=file_id,
        filename=filename,
        layout="cycle",
    )
    html_path = Path("sqr_sender.html")
    html_path.write_text(html, encoding="utf-8")
    print(f"HTML cycle saved to: {html_path} ({len(matrices)} frames, Auto: ON)")
    print("Open this file in a browser to start the QR transfer.")
    return 0


def cmd_receive(args: argparse.Namespace) -> int:
    """接收端：截图 → 解码 → 校验 → 保存。"""
    from sqr.receiver.capturer import CaptureRegion
    from sqr.receiver.runner import run_receiver

    if args.select or not args.region:
        try:
            from sqr.receiver.region_selector import select_region
        except ImportError as exc:
            print(f"错误：{exc}\n", file=sys.stderr)
            print("改用命令行指定： python3 -m sqr.cli receive --region x,y,w,h")
            return 1
        print("请拖拽框选 VMware 窗口中的 QR 码区域...")
        region = select_region()
        if region is None:
            print("已取消。")
            return 1
        print(f"已选区域: {region.left},{region.top},{region.width},{region.height}")
    else:
        region = _parse_region(args.region)

    output_path = Path(args.output)

    print(f"Region:    {region.left},{region.top},{region.width},{region.height}")
    print(f"Output:    {output_path}")
    print(f"Interval:  {args.interval}s")

    if args.expected_md5:
        print(f"Expect MD5:  {args.expected_md5}")
    if args.expected_bytes:
        print(f"Expect bytes: {args.expected_bytes}")

    print("\nStarting capture... (Ctrl+C to abort)\n")

    def on_progress(progress):
        pct = progress.percent
        bar_len = 30
        filled = int(bar_len * pct / 100)
        bar = "█" * filled + "░" * (bar_len - filled)
        print(
            f"\r  [{bar}] {progress.received_count}/{progress.total} "
            f"({pct:.0f}%)  rejected={progress.rejected_count}",
            end="", flush=True,
        )

    def on_complete(result, path):
        print()
        print(f"\n  Result:    {'SUCCESS' if result.success else 'FAILED'}")
        print(f"  Bytes:     {result.actual_bytes}")
        print(f"  SHA-256:   {result.actual_sha256}")
        print(f"  MD5:       {result.actual_md5}")
        print(f"  UTF-8:     {'OK' if result.utf8_valid else 'FAIL'}")
        if not result.success:
            print(f"  Errors:    {result.message}")
        else:
            print(f"  Saved to:  {path}")

    try:
        result = run_receiver(
            region=region,
            output_path=output_path,
            interval_ms=int(args.interval * 1000),
            expected_sha256=args.expected_sha256,
            expected_md5=args.expected_md5,
            expected_bytes=args.expected_bytes,
            on_progress=on_progress,
            on_complete=on_complete,
        )
    except KeyboardInterrupt:
        print("\n\nAborted by user.")
        return 1
    except TimeoutError as e:
        print(f"\n\nTimeout: {e}", file=sys.stderr)
        return 1

    return 0 if result.success else 2


def cmd_gui(args: argparse.Namespace) -> int:
    """接收端 GUI 启动器：控制面板 + 按钮触发框选 + 后台接收。"""
    try:
        from sqr.receiver.app import launch
    except ImportError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1
    return launch()


def cmd_decode(args: argparse.Namespace) -> int:
    """接收端（image 批量模式）：从多个二维码 image 文件解码还原内容。"""
    from sqr.receiver.image_decoder import run_receiver_from_images

    image_paths: list[Path] = []

    if args.image:
        for f in args.image:
            p = Path(f)
            if not p.exists():
                print(f"错误：image 文件不存在: {f}", file=sys.stderr)
                return 1
            image_paths.append(p)

    if args.images:
        d = Path(args.images)
        if not d.is_dir():
            print(f"错误：不是目录: {args.images}", file=sys.stderr)
            return 1
        exts = {".ppm", ".png", ".jpg", ".jpeg"}
        for child in sorted(d.iterdir()):
            if child.suffix.lower() in exts:
                image_paths.append(child)

    if not image_paths:
        print(
            "错误：未提供任何 image（用 --image <file> 或 --images <dir>）",
            file=sys.stderr,
        )
        return 1

    output_path = Path(args.output)

    print(f"Images:   {len(image_paths)} file(s)")
    print(f"Output:   {output_path}")
    if args.expected_sha256:
        print(f"Expect SHA-256: {args.expected_sha256}")
    if args.expected_md5:
        print(f"Expect MD5:     {args.expected_md5}")
    if args.expected_bytes:
        print(f"Expect bytes:   {args.expected_bytes}")

    print("\nDecoding... (Ctrl+C to abort)\n")

    def on_progress(progress):
        total = progress.total if progress.total else 0
        received = progress.received_count
        pct = progress.percent
        bar_len = 30
        filled = int(bar_len * pct / 100)
        bar = "█" * filled + "░" * (bar_len - filled)
        print(
            f"\r  [{bar}] {received}/{total} ({pct:.0f}%)",
            end="", flush=True,
        )

    def on_complete(result, path):
        print()
        print(f"\n  Result:    {'SUCCESS' if result.success else 'FAILED'}")
        if result.actual_bytes:
            print(f"  Bytes:     {result.actual_bytes}")
        if result.actual_sha256:
            print(f"  SHA-256:   {result.actual_sha256}")
        if result.actual_md5:
            print(f"  MD5:       {result.actual_md5}")
        print(f"  UTF-8:     {'OK' if result.utf8_valid else 'FAIL'}")
        if not result.success:
            print(f"  Errors:    {result.message}")
        else:
            print(f"  Saved to:  {path}")

    try:
        result = run_receiver_from_images(
            image_paths,
            output_path,
            expected_sha256=args.expected_sha256,
            expected_md5=args.expected_md5,
            expected_bytes=args.expected_bytes,
            on_progress=on_progress,
            on_complete=on_complete,
        )
    except KeyboardInterrupt:
        print("\n\nAborted by user.")
        return 1

    return 0 if result.success else 2


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="sqr",
        description="Screen QR Transfer — isolated network file transfer via QR codes",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # send
    send_parser = subparsers.add_parser("send", help="Send file via QR codes")
    send_parser.add_argument("file", help="UTF-8 text file to send")
    send_parser.add_argument("--interval", type=float, default=1.2,
                            help="Seconds per frame (default: 1.2)")
    send_parser.add_argument("--error-correction", default="M",
                            choices=["L", "M", "Q", "H"],
                            help="QR error correction level (default: M)")
    send_parser.add_argument("--max-payload", type=int, default=1200,
                            help="Max chars per QR payload (default: 1200)")
    send_parser.add_argument("--zstd", action="store_true",
                            help="Use zstd compression (default: gzip)")
    send_parser.add_argument("--output-dir", default=None,
                            help="Save QR PPM frames to this dir (debug)")
    send_parser.add_argument("--no-manifest", action="store_true",
                            help="Do not generate manifest frame")
    send_parser.add_argument("--renderer", default="html",
                            choices=["html", "terminal"],
                            help="QR display: html=cycle HTML (default), terminal=unicode print")
    send_parser.add_argument("--module-size", type=int, default=10,
                            help="Pixels per QR module (default: 10, PPM debug only)")
    send_parser.add_argument("--html-cycle", default=None,
                            help="Write fullscreen cycle HTML (1 QR/frame auto-loop) to PATH and exit")
    send_parser.add_argument("--html-grid", default=None,
                            help="Write static HTML grid (paginated) to PATH and exit. "
                                 "Auto-cycle default OFF; use Prev/Next buttons or toggle Auto.")
    send_parser.add_argument("--grid-cols", type=int, default=4,
                            help="QR columns per page in HTML grid (default: 4)")
    send_parser.add_argument("--page-rows", type=int, default=4,
                            help="QR rows per page in HTML grid (default: 4)")
    send_parser.add_argument("--page-interval", type=float, default=3.0,
                            help="Auto-cycle page interval seconds (default: 3.0)")
    send_parser.set_defaults(func=cmd_send)

    # receive
    recv_parser = subparsers.add_parser("receive", help="Receive file via screen capture")
    recv_parser.add_argument("--region", default=None,
                            help="Capture region as x,y,w,h (omit to use GUI selector)")
    recv_parser.add_argument("--select", action="store_true",
                            help="Show GUI region selector (default if --region omitted)")
    recv_parser.add_argument("--output", default="sqr_output.txt",
                            help="Output file path (default: sqr_output.txt)")
    recv_parser.add_argument("--interval", type=float, default=0.5,
                            help="Capture interval seconds (default: 0.5)")
    recv_parser.add_argument("--expected-sha256", default=None,
                            help="Expected SHA-256 (overrides manifest)")
    recv_parser.add_argument("--expected-md5", default=None,
                            help="Expected MD5 (overrides manifest)")
    recv_parser.add_argument("--expected-bytes", type=int, default=None,
                            help="Expected byte count (overrides manifest)")
    recv_parser.set_defaults(func=cmd_receive)

    # gui
    gui_parser = subparsers.add_parser(
        "gui", help="Launch receiver GUI (control panel + region selector)"
    )
    gui_parser.set_defaults(func=cmd_gui)

    # decode
    decode_parser = subparsers.add_parser(
        "decode",
        help="Decode QR images to file (batch mode: from image files, no screen capture)",
    )
    decode_parser.add_argument("--image", action="append", default=None,
                               help="Single image file (PPM/PNG/JPG); repeatable")
    decode_parser.add_argument("--images", default=None,
                               help="Directory to scan for QR images (.ppm/.png/.jpg)")
    decode_parser.add_argument("--output", default="sqr_decoded.txt",
                               help="Output file path (default: sqr_decoded.txt)")
    decode_parser.add_argument("--expected-sha256", default=None,
                               help="Expected SHA-256 (overrides manifest)")
    decode_parser.add_argument("--expected-md5", default=None,
                               help="Expected MD5 (overrides manifest)")
    decode_parser.add_argument("--expected-bytes", type=int, default=None,
                               help="Expected byte count (overrides manifest)")
    decode_parser.set_defaults(func=cmd_decode)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
