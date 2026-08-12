# sqr/sender/ 架构

> 内网发送端：把一个 UTF-8 文本文件变成屏幕上循环播放的 QR 码序列。
> **零外部编译依赖** —— 仅需 Python 3.6+ stdlib + tkinter + vendor qrcode（PIL stub 兜底）。

## 端到端数据流

```
输入文件 (UTF-8 bytes)
    │
    ▼  cli.cmd_send
    │  compute_sha256 / compute_md5 / compute_file_id   ← sqr.protocol
    ▼
build_all_frames(filename, raw, sha256, md5, max_chars, use_zstd)   ← chunker.py
    │
    ├──► compress_and_encode(raw, use_zstd)             ← compressor.py
    │        raw bytes ─gzip/zstd─► compressed ─base64─► data_b64 (str)
    │
    ├──► build_manifest(filename, raw, sha256, md5, compressed)  → FileManifest
    │
    ├──► chunk_payload(compressed, file_id, max_chars)  → [Chunk(index=1..N)]
    │        data_b64 按 max_chars 切片，每片算 CRC32
    │
    └──► build_manifest_frame(manifest, file_id, total) → Chunk(index=0)
    │
    ▼  返回 (FileManifest, [manifest_frame, data_1, ..., data_N])
    │
    ▼  对每个 Chunk.encode() 调 generate_matrix()       ← qr_render.py
    │        SQ1|file_id|idx|total|crc32|payload ─qrcode─► QRMatrix(List[List[bool]])
    │
    ▼  List[QRMatrix]
    │
    ├─► --output-dir : matrix_to_ppm()      ← 渲染器B，保存 PPM 调试帧
    ├─► --renderer terminal : matrix_to_unicode()  ← 渲染器C，终端降级
    └─► 默认 : QRPlayer(matrices).run()      ← player.py
                tkinter 全屏 Canvas 循环播放 (manifest→data_1..N→manifest→...)
```

**帧序列设计**：manifest 帧（index=0）和所有数据帧（index=1..N）**混在同一个循环里反复播放**，让接收端无论从哪一帧开始截图都能逐步补齐（先收到 manifest 知道总量和校验信息，再收数据帧）。见 `player.QRPlayer._show_frame` 的 `self._current = (self._current + 1) % len(self._matrices)`。

## 文件

### `compressor.py` — 压缩 + Base64 编码（92 行）

| 符号 | 签名 | 说明 |
|---|---|---|
| `CompressedPayload` | `@dataclass(frozen)`: data_b64, compression, encoding | 压缩编码结果 |
| `compress_and_encode` | `(raw: bytes, use_zstd: bool=False) -> CompressedPayload` | gzip(9) 或 zstd(-19)；zstd 不可用自动回退 gzip；输出 Base64 ASCII（断言无换行）|
| `depress_payload`⚠️ | `(compressed: bytes, compression: str) -> bytes` | **接收端调用**（解压）。gzip.decompress 或 zstandard.ZstdDecompressor |
| `_try_zstd` | `(raw: bytes) -> Tuple[str, bytes]` | 尝试 zstd，ImportError 回退 gzip |

> ⚠️ `decompress_payload` 物理上在 `sqr/sender/compressor.py`，但语义属于接收端管线（`receiver/runner.py` 调用）。这是历史布局，压缩/解压成对放在一起便于对照。

### `chunker.py` — 分片 + CRC32 + manifest 组装（140 行）

| 符号 | 签名 | 说明 |
|---|---|---|
| `build_manifest` | `(filename, raw_bytes, sha256_hex, md5_hex, compressed) -> FileManifest` | 组装文件元数据 |
| `chunk_payload` | `(compressed, file_id, max_chars=1200) -> List[Chunk]` | Base64 payload 按 max_chars 切片 → 数据帧 index=1..N，每片算 CRC32 |
| `build_manifest_frame` | `(manifest, file_id, total) -> Chunk` | manifest 帧 index=0，payload 是 FileManifest 的 Base64-JSON |
| `build_all_frames` | `(filename, raw_bytes, sha256_hex, md5_hex, max_chars=1200, use_zstd=False) -> Tuple[FileManifest, List[Chunk]]` | **一站式入口**，cli.cmd_send 直接调它。返回 `[manifest_frame, data_1..N]` |

### `qr_render.py` — QR 矩阵生成 + 三种渲染器（205 行）

**依赖顺序约束**：第 12 行 `import sqr.vendor` 必须在 `import qrcode` 之前（见 [vendor/ARCHITECTURE.md](../vendor/ARCHITECTURE.md)）。

| 符号 | 签名 | 说明 |
|---|---|---|
| `QRMatrix` | `@dataclass(frozen)`: matrix, version, module_count, quiet_zone | QR 矩阵纯数据（`List[List[bool]]`，True=黑），不涉及任何图像库 |
| `generate_matrix` | `(data: str, error_correction="M", quiet_zone=4) -> QRMatrix` | 用 vendor qrcode 生成矩阵，只取 `qr.modules`，**从不调 make_image()** |
| `draw_matrix_on_canvas` | `(canvas, qr_matrix, module_size=10, bg_color, fg_color) -> int` | **渲染器 A**：在 tkinter Canvas 上画矩形，返回像素边长。主用途 |
| `matrix_to_ppm` | `(qr_matrix, module_size=10) -> bytes` | **渲染器 B**：PPM P6 二进制，纯 stdlib。可被 Pillow `Image.open` 读。用于 round-trip 测试 |
| `matrix_to_unicode` | `(qr_matrix) -> str` | **渲染器 C**：Unicode 半块字符（▀▄█ ），终端降级方案 |

### `player.py` — tkinter 全屏循环播放器（132 行）

| 符号 | 签名 | 说明 |
|---|---|---|
| `QRPlayer` | 类 | 全屏循环播放 QR 帧的 tkinter 窗口 |
| `QRPlayer.__init__` | `(matrices, file_id, total, filename, module_size=10, interval_ms=1200, title="SQR Sender")` | |
| `QRPlayer.run` | `() -> None` | 启动 tkinter mainloop（阻塞至 ESC/q 或窗口关闭）|
| `QRPlayer.stop` | `() -> None` | 从外部线程请求停止（`root.after(0, root.quit)`）|
| `run_player_from_matrices` | `(matrices, file_id, total, filename, module_size=10, interval_ms=1200) -> None` | 便捷封装 |

播放器底部有 info 栏显示当前帧类型（`MANIFEST` / `DATA i/N`）、file_id、文件名、像素尺寸。用 `draw_matrix_on_canvas` 直接渲染，**不经过 Pillow / PhotoImage**。

## 依赖

| 依赖 | 性质 | 用在哪 |
|---|---|---|
| `sqr.vendor` (+ qrcode) | 项目内置 | `qr_render.py` 生成矩阵 |
| `sqr.protocol` | 项目共用层 | `chunker.py` 用 `Chunk` / `FileManifest` / `compute_*` |
| `tkinter` | stdlib（需系统 tcl/tk） | `player.py` 全屏 Canvas |
| gzip / base64 / hashlib / binascii / math / json | stdlib | `compressor.py` / `chunker.py` |
| `zstandard` | **可选** C 扩展，不打包 | `--zstd` 时尝试，无则回退 gzip |

**发送端无 pyzbar / mss / Pillow / libzbar 依赖** —— 这些全在接收端。

## 上游调用方

唯一入口：`sqr/cli.py` 的 `cmd_send()`（见 `sqr/cli.py:25`）。CLI 参数 → `build_all_frames` → `generate_matrix` → 渲染器选择。
