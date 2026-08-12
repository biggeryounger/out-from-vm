# 屏幕二维码单向传输 — 实施设计文档（v2：零安装可迁移）

> 基于 `screen-qr-transfer.md` 细化。
> **v2 核心变更**：发送端去 Pillow 化、vendor qrcode + PIL stub、PyInstaller 打包，实现传入内网零安装即用。
> 遵循 workspace Python 风格：`@dataclass`、绝对导入、snake_case、PascalCase、4-space 缩进、全类型注解。

---

## 1. 概述与可迁移性目标

### 1.1 核心约束

内网机器**无网络、无包管理器、可能无 Python 环境**。发送端代码和全部依赖必须随项目一起传入，解压即用。

### 1.2 可迁移性策略（三层方案）

| 层级 | 方案 | 适用场景 | 体积 |
|------|------|---------|------|
| **Tier 1 — 源码 + vendor** | 纯 Python 源码 + vendor 目录（qrcode 纯 Python）+ PIL stub | 内网有 Python 3.6+（任何来源） | ~300 KB |
| **Tier 2 — PyInstaller** | 单目录/单文件可执行程序，内含 Python 解释器 + Tcl/Tk + 全部依赖 | 内网无 Python | ~15–25 MB |
| **Tier 3 — python-build-standalone** | 完整 Python 发行版 + 项目代码打包为 tar/zip | 内网需完整 Python 环境 + 可执行其他脚本 | ~40 MB |

**本方案默认同时支持 Tier 1 + Tier 2。** Tier 3 作为文档备选。

### 1.3 技术路线总览

```
┌─────────────────────── 发送端（内网）──────────────────────┐
│  纯 stdlib + vendor/qrcode（纯 Python）+ PIL stub          │
│  ┌─────────────────────────────────────────────────────┐  │
│  │ gzip/zlib → base64 → 分片+CRC32 → QR matrix         │  │
│  │ → tkinter Canvas 渲染 / PPM 导出 / 终端 Unicode     │  │
│  └─────────────────────────────────────────────────────┘  │
│  零编译依赖 · 零安装 · 仅需 Python 3.6+ + tkinter          │
│  或 PyInstaller 可执行程序（连 Python 也内嵌）              │
└───────────────────────────────────────────────────────────┘

┌─────────────────────── 接收端（外网）──────────────────────┐
│  PyInstaller onefile（内嵌 Python + pyzbar + libzbar + mss）│
│  或源码 + pip install（外网可联网安装）                      │
│  ┌─────────────────────────────────────────────────────┐  │
│  │ mss 截图 → pyzbar 解码 → 校验/去重/排序              │  │
│  │ → base64 解码 → gunzip → SHA-256/MD5 校验            │  │
│  └─────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────┘
```

---

## 2. 关键技术决策：去 Pillow 化

### 2.1 为什么去掉 Pillow

Pillow 有 C 扩展（`_imaging.c`），需要编译工具链或预编译 wheel。内网无法 `pip install`，也难以保证平台匹配的 wheel 可用。

### 2.2 验证结论（已实测）

| 问题 | 结论 |
|------|------|
| `qrcode` 库是否纯 Python？ | ✅ 核心编码逻辑（`main.py`、`util.py`、`constants.py`）纯 Python |
| `qrcode` 导入时是否会触发 PIL import？ | ⚠️ 会。导入链：`qrcode.image.base` → `styles.moduledrawers.__init__` → `moduledrawers.pil` → `from PIL import Image, ImageDraw` |
| 能否只访问 QR matrix 不触发 PIL？ | ❌ 不能直接避免。导入 `qrcode` 包就触发 PIL import |
| **解决方案** | ✅ 在 vendor 中提供 PIL stub 模块，注入 `sys.modules['PIL']`，使 import 链通过但 PIL 函数永不被调用 |

### 2.3 PIL Stub 设计

```python
# sqr/vendor/__init__.py
"""Vendor bootstrap：注入 sys.path 和 PIL stub。

在 import qrcode 之前执行。如果系统没有真实 PIL，安装一个最小 stub，
使 qrcode 的 import 链不崩溃。我们只访问 qr.modules，从不调用 make_image()，
所以 stub 的方法永远不会被实际执行。
"""
import sys
import os
import types

# 1. 注入 vendor 目录到 sys.path
_VENDOR_DIR = os.path.dirname(os.path.abspath(__file__))
if _VENDOR_DIR not in sys.path:
    sys.path.insert(0, _VENDOR_DIR)

# 2. 如果真实 PIL 不存在，安装 stub
if 'PIL' not in sys.modules:
    try:
        import PIL  # noqa: F401
    except ImportError:
        _pil = types.ModuleType("PIL")
        _pil.Image = type("Image", (), {"new": staticmethod(lambda *a, **k: None)})
        _pil.ImageDraw = type("ImageDraw", (), {"Draw": staticmethod(lambda *a, **k: None)})
        sys.modules["PIL"] = _pil
        sys.modules["PIL.Image"] = _pil.Image
        sys.modules["PIL.ImageDraw"] = _pil.ImageDraw
```

**效果**：
- 有真实 Pillow → stub 不激活，qrcode 正常工作。
- 无 Pillow → stub 让 `from PIL import Image, ImageDraw` 返回空类，qrcode 导入成功。只要不调用 `make_image()`，一切正常。

### 2.4 QR 矩阵访问（不经过 Pillow）

```python
import qrcode  # vendor __init__ 已确保 PIL stub 就位

qr = qrcode.QRCode(
    error_correction=qrcode.constants.ERROR_CORRECT_M,
    box_size=10,
    border=4,
)
qr.add_data(text)
qr.make(fit=True)

matrix = qr.modules        # List[List[bool]]，True=黑块
version = qr.version       # int (1-40)
size = len(matrix)         # version*4+17
```

**`qr.modules` 是纯数据**（`List[List[bool]]`），不涉及任何图像库。

---

## 3. 技术选型

### 3.1 语言与版本

**Python 3.6+**（Tier 1 源码模式）。

理由：
- 消除 Pillow 后发送端仅需 stdlib + 纯 Python vendor，3.6+ 即可。
- Tk 8.6（Python 3.6+ 自带）原生支持 PNG/PPM 加载。
- `@dataclass` 需 3.7+，可用 `@dataclass` 或退化为普通类。

### 3.2 依赖矩阵

| 依赖 | 发送端（内网） | 接收端（外网） | 性质 | 打包方式 |
|------|:-:|:-:|------|------|
| `qrcode` | ✅ | — | **纯 Python** | **vendor 到项目内** |
| `Pillow` | ❌ 已消除 | ✅ | C 扩展 | 接收端 pip / PyInstaller |
| `pyzbar` | — | ✅ | C 绑定 (libzbar) | 接收端 pip / PyInstaller |
| `libzbar` | — | ✅ | 原生 C 库 | brew / apt / PyInstaller hook |
| `mss` | — | ✅ | C 扩展 | 接收端 pip / PyInstaller |
| `zstandard` | 可选 | 可选 | C 扩展 | 不打包，无则回退 gzip |
| `tkinter` | ✅ stdlib | — | Tcl/Tk 绑定 | Python 自带 / PyInstaller 内嵌 |
| stdlib (gzip/base64/hashlib/binascii) | ✅ | ✅ | 内置 | — |

**发送端外部编译依赖 = 0。**

### 3.3 QR 渲染方式（替代 Pillow）

| 渲染器 | 用途 | 依赖 | 实现 |
|--------|------|------|------|
| **tkinter Canvas** | 屏幕全屏显示（主用途） | tkinter (stdlib) | 直接在 Canvas 上画矩形 |
| **PPM 导出** | 调试 / 集成测试 | stdlib (bytes) | 纯 Python 生成 PPM (P6) 字节 |
| **终端 Unicode** | 无 tkinter 时的降级显示 | stdlib | 用 `▀▄█ ` 半块字符渲染 |

---

## 4. 目录结构

```
out-from-vm/
├── screen-qr-transfer.md          # 原始方案文档（只读参考）
├── implementation-plan.md         # 本文档
│
├── sqr/                           # 项目包根
│   ├── __init__.py
│   │
│   ├── protocol.py                # 共享：Chunk/Manifest 编解码、校验、异常（纯 stdlib）
│   │
│   ├── sender/                    # 内网发送端（纯 stdlib + vendor）
│   │   ├── __init__.py
│   │   ├── compressor.py          # gzip/zlib 压缩 + Base64 编码
│   │   ├── chunker.py             # 分片 + CRC32 + 协议头组装
│   │   ├── qr_render.py           # QR matrix 生成 + 3 种渲染器 (Canvas/PPM/Terminal)
│   │   └── player.py              # tkinter 全屏循环播放器
│   │
│   ├── receiver/                  # 外网接收端（可 pip install）
│   │   ├── __init__.py
│   │   ├── capturer.py            # mss 固定区域截图
│   │   ├── decoder.py             # pyzbar 解码（带 opencv 适配层）
│   │   ├── assembler.py           # 分片校验/去重/排序/拼接
│   │   └── verifier.py            # 字节/SHA-256/MD5/UTF-8 校验
│   │
│   ├── vendor/                    # ★ 零安装核心：vendored 纯 Python 依赖
│   │   ├── __init__.py            # sys.path 注入 + PIL stub
│   │   └── qrcode/                # vendored qrcode 库（MIT，纯 Python）
│   │       ├── __init__.py
│   │       ├── main.py
│   │       ├── constants.py
│   │       ├── util.py
│   │       ├── exceptions.py
│   │       └── image/
│   │           ├── __init__.py
│   │           ├── base.py
│   │           └── ...            # PIL 依赖文件存在但不会被调用
│   │
│   └── cli.py                     # 命令行入口：send / receive
│
├── build/                         # 打包脚本（在外网构建机上运行）
│   ├── vendor_qrcode.py           # 下载 qrcode 源码到 vendor/（一次性）
│   ├── bundle_sender.py           # 打包发送端为 zip / PyInstaller
│   ├── bundle_receiver.py         # PyInstaller 打包接收端
│   ├── sender.spec                # PyInstaller spec（发送端）
│   └── receiver.spec              # PyInstaller spec（接收端）
│
├── dist/                          # 构建产物（.gitignore 忽略）
│   ├── sqr-sender-src.zip         # Tier 1：源码 + vendor
│   ├── sqr-sender/                # Tier 2：PyInstaller 目录
│   │   └── sqr-sender             # 可执行程序
│   └── sqr-receiver               # Tier 2：PyInstaller onefile
│
├── launcher/                      # 启动脚本
│   ├── send.sh                    # Linux/macOS 发送端启动
│   ├── send.bat                   # Windows 发送端启动
│   └── send_pyinstaller.sh        # PyInstaller 可执行程序启动
│
├── tests/                         # 测试（不走屏幕）
│   ├── __init__.py
│   ├── test_protocol.py
│   ├── test_chunker.py
│   ├── test_compressor.py
│   ├── test_assembler.py
│   ├── test_verifier.py
│   ├── test_qr_render.py          # ★ 新增：PPM 生成 + matrix 正确性
│   ├── test_roundtrip.py          # ★ 核心：file → PPM → decode → verify
│   └── fixtures/
│       ├── sample_small.txt
│       ├── sample_mid.txt
│       └── sample_repetitive.txt
│
├── requirements-build.txt         # 构建机依赖（PyInstaller 等）
├── requirements-receiver.txt      # 接收端依赖（pyzbar/mss/Pillow）
└── requirements-test.txt          # 测试依赖（pytest + 接收端依赖）
```

### 设计原则

- **`sqr/vendor/` 是零安装的关键**：所有外部纯 Python 依赖打包在此，`vendor/__init__.py` 在导入时注入 `sys.path` 和 PIL stub。
- **发送端永远不 import 接收端依赖**：`sender/` 下所有模块只用 stdlib + `sqr.vendor`。
- **`protocol.py` 是唯一共享模块**：两端通过它通信，纯 stdlib。
- **`build/` 只在外网构建机运行**：产出的 `dist/` 产物可传入内网。

---

## 5. 协议规范细化（SQ1）

### 5.1 帧格式

在原始方案 `SQ1|<file_id>|<index>|<total>|<payload_crc32>|<payload>` 基础上，引入 **manifest 帧（index=0）**，用于自动传输文件元数据。

```
┌──────────────────────────────────────────────────────────┐
│  Manifest 帧（index = 0，每轮播放的首帧）                   │
│  SQ1|<file_id>|0|<total>|<manifest_crc32>|<manifest_b64> │
│                                                          │
│  manifest_b64 = Base64(JSON)                             │
│  JSON = {                                                │
│    "v": 1,                  # manifest schema 版本       │
│    "fn": "filename.txt",    # 原始文件名                   │
│    "n": 29816,              # 原始字节数                   │
│    "s": "<sha256_hex>",     # 原始文件 SHA-256            │
│    "m": "<md5_hex>",        # 原始文件 MD5（可为 null）    │
│    "c": "gzip",             # 压缩算法 gzip|zstd          │
│    "e": "base64"            # 编码算法 base64             │
│  }                                                       │
├──────────────────────────────────────────────────────────┤
│  Data 帧（index = 1..total）                              │
│  SQ1|<file_id>|<index>|<total>|<payload_crc32>|<payload> │
│                                                          │
│  payload = Base64(compressed_data_chunk)                 │
└──────────────────────────────────────────────────────────┘
```

### 5.2 字段规则

| 字段 | 类型 | 规则 |
|------|------|------|
| `SQ1` | const | 协议版本标识，必须精确匹配 |
| `file_id` | str | 12 hex chars（原始文件 SHA-256 前 12 位），同一次传输所有帧一致 |
| `index` | int | manifest=0，data=1..total |
| `total` | int | **仅数据帧数量**（不含 manifest） |
| `*_crc32` | hex str | CRC32 的 8 位零填充十六进制（如 `0a1b2c3d`） |
| `payload` / `manifest_b64` | str | Base64 ASCII，无换行 |

### 5.3 接收端拒绝条件（严格）

以下任一条件触发 → 丢弃该帧，等待重传，不中断采集：

1. 协议版本 ≠ `SQ1`
2. `file_id` 与已建立会话不匹配（且当前已有活跃会话）
3. `index` 越界（`< 0` 或 `> total`）
4. `total` 与已建立会话不一致
5. CRC32 计算值 ≠ 帧内声明值
6. 同一 `index` 出现 payload 不同但 CRC32 都通过的分片（记录冲突，保留首个，标记警告）

### 5.4 与原始方案的兼容性

- 原始方案的 `index` 从 1 开始，`total` 为数据帧总数 → **完全保留**。
- manifest 帧（index=0）是**纯增量扩展**：不支持 manifest 的旧接收端会因 `index=0 < 1` 拒绝它，不影响数据帧采集。
- 不使用 manifest 时，元数据通过 CLI `--expected-*` 参数传入，行为与原始方案一致。

---

## 6. 共享模块设计：`sqr/protocol.py`

> 纯 stdlib，两端共用。

### 6.1 数据结构

```python
from dataclasses import dataclass
from enum import IntEnum
import binascii
import hashlib
import json
import base64


PROTOCOL_VERSION: str = "SQ1"
FIELD_SEPARATOR: str = "|"
DEFAULT_MAX_PAYLOAD_CHARS: int = 1200
DEFAULT_ERROR_CORRECTION: str = "M"
DEFAULT_QUIET_ZONE_MODULES: int = 4
MANIFEST_INDEX: int = 0


class FrameType(IntEnum):
    MANIFEST = 0
    DATA = 1


@dataclass(frozen=True)
class Chunk:
    """单个分片帧（manifest 或 data）。"""
    file_id: str            # 12 hex chars
    index: int              # 0=manifest, 1..N=data
    total: int              # 数据帧总数（不含 manifest）
    crc32: int              # payload 的 CRC32（unsigned 32-bit）
    payload: str            # Base64 ASCII 内容

    def encode(self) -> str:
        """序列化为 QR 内容字符串。

        返回: SQ1|<file_id>|<index>|<total>|<crc32:08x>|<payload>
        """
        ...

    @classmethod
    def decode(cls, raw: str) -> "Chunk":
        """从 QR 解码字符串解析为 Chunk。

        Raises:
            ProtocolError: 版本不匹配、字段数不对、类型转换失败。
        """
        ...

    def verify_crc(self) -> bool:
        """校验 payload 的 CRC32 是否与声明值一致。"""
        ...

    @property
    def frame_type(self) -> FrameType:
        return FrameType.MANIFEST if self.index == MANIFEST_INDEX else FrameType.DATA


@dataclass(frozen=True)
class FileManifest:
    """文件元数据，编码进 manifest 帧的 payload。"""
    schema_version: int         # 固定 1
    filename: str
    original_bytes: int
    sha256: str                 # 64 hex chars
    md5: str | None             # 32 hex chars，可为 None
    compression: str            # "gzip" | "zstd"
    encoding: str               # "base64"

    def encode_payload(self) -> str:
        """JSON → Base64（无换行），作为 manifest 帧的 payload。"""
        ...

    @classmethod
    def decode_payload(cls, payload: str) -> "FileManifest":
        """Base64 → JSON → FileManifest。"""
        ...
```

### 6.2 异常

```python
class ProtocolError(Exception):
    """协议解析错误（格式/版本/字段）。"""


class CrcMismatchError(ProtocolError):
    """CRC32 校验失败。"""


class IndexConflictError(ProtocolError):
    """同一 index 出现不同内容。"""
```

### 6.3 纯函数

```python
def compute_file_id(sha256_hex: str) -> str:
    """取 SHA-256 hex 的前 12 字符作为 file_id。"""
    return sha256_hex[:12]


def compute_crc32(data: bytes | str) -> int:
    """计算 CRC32，返回 unsigned 32-bit int。"""
    if isinstance(data, str):
        data = data.encode("ascii")
    return binascii.crc32(data) & 0xFFFFFFFF


def compute_sha256(data: bytes) -> str:
    """计算 SHA-256，返回 64 hex chars。"""
    return hashlib.sha256(data).hexdigest()


def compute_md5(data: bytes) -> str:
    """计算 MD5，返回 32 hex chars。"""
    return hashlib.md5(data).hexdigest()
```

---

## 7. 发送端模块设计

> 纯 stdlib + `sqr.vendor`（vendored qrcode + PIL stub）。零编译依赖。

### 7.1 `sqr/sender/compressor.py`

```python
import gzip
import base64
import zlib
from dataclasses import dataclass


@dataclass(frozen=True)
class CompressedPayload:
    """压缩 + 编码后的结果。"""
    data_b64: str          # Base64 ASCII 字符串（无换行）
    compression: str       # "gzip" | "zstd"
    encoding: str          # "base64"


def compress_and_encode(
    raw: bytes,
    use_zstd: bool = False,
) -> CompressedPayload:
    """压缩 → Base64 编码。

    Args:
        raw: 原始文件字节。
        use_zstd: True 时尝试 zstd -19，不可用则回退 gzip。
                  zstd 是 C 扩展，不在 vendor 中——仅当系统已安装时可用。

    Returns:
        CompressedPayload(data_b64, compression, encoding)
    """
    ...
```

**实现要点**：
- gzip：`gzip.compress(data, compresslevel=9)`（stdlib，始终可用）。
- zstd：`zstandard.ZstdCompressor(level=19).compress(data)`，包在 `try/except ImportError` 中回退 gzip。
- Base64：`base64.b64encode().decode("ascii")`，确认无 `\n`。

### 7.2 `sqr/sender/chunker.py`

```python
from sqr.protocol import Chunk, FileManifest, compute_file_id, compute_crc32
from sqr.sender.compressor import CompressedPayload


def build_manifest(
    filename: str,
    raw_bytes: bytes,
    sha256_hex: str,
    md5_hex: str | None,
    compressed: CompressedPayload,
) -> FileManifest:
    """构建文件元数据。"""
    ...


def chunk_payload(
    compressed: CompressedPayload,
    file_id: str,
    max_chars: int = 1200,
) -> list[Chunk]:
    """将 Base64 payload 按固定长度切片，组装数据帧。

    Returns:
        数据帧列表（index 1..N），不含 manifest。
    """
    ...


def build_manifest_frame(manifest: FileManifest, file_id: str, total: int) -> Chunk:
    """构建 manifest 帧（index=0）。"""
    ...


def build_all_frames(
    filename: str,
    raw_bytes: bytes,
    sha256_hex: str,
    md5_hex: str | None,
    max_chars: int = 1200,
    use_zstd: bool = False,
) -> tuple[FileManifest, list[Chunk]]:
    """一站式：文件字节 → (manifest, [manifest_frame, data_frame_1, ..., data_frame_N])。

    返回的 Chunk 列表第 0 个是 manifest 帧，其余是数据帧。
    """
    ...
```

**分片边界处理**：
- 空 Base64 字符串 → 1 个空 payload 数据帧（total=1）。
- 长度恰好整除 → 无尾部空片。
- total = ceil(len(payload_str) / max_chars)。

### 7.3 `sqr/sender/qr_render.py`（★ 核心变更：替代 qr_generator.py）

此模块**不依赖 Pillow**，直接从 `qr.modules` 矩阵渲染。

#### 7.3.1 QR Matrix 生成

```python
# 导入 vendor（触发 sys.path 注入 + PIL stub）
import sqr.vendor  # noqa: F401
import qrcode
from qrcode.constants import ERROR_CORRECT_M, ERROR_CORRECT_Q


@dataclass(frozen=True)
class QRMatrix:
    """QR 矩阵 + 元数据。"""
    matrix: list[list[bool]]    # True = 黑块
    version: int                # QR version (1-40)
    module_count: int           # version * 4 + 17
    quiet_zone: int             # 静区 modules


def generate_matrix(
    data: str,
    error_correction: str = "M",
    quiet_zone: int = 4,
) -> QRMatrix:
    """生成 QR 矩阵（不经过任何图像库）。

    Args:
        data: QR 内容字符串（如 Chunk.encode() 的结果）。
        error_correction: "M" | "Q" | "L" | "H"
        quiet_zone: 静区 modules 数（≥4）
    """
    ec_map = {"L": ..., "M": ERROR_CORRECT_M, "Q": ERROR_CORRECT_Q, "H": ...}
    qr = qrcode.QRCode(
        error_correction=ec_map[error_correction],
        box_size=1,     # 不生成图像，box_size 无意义
        border=quiet_zone,
    )
    qr.add_data(data)
    qr.make(fit=True)
    return QRMatrix(
        matrix=[list(row) for row in qr.modules],
        version=qr.version,
        module_count=len(qr.modules),
        quiet_zone=quiet_zone,
    )
```

#### 7.3.2 渲染器 A：tkinter Canvas（屏幕显示，主用途）

```python
def draw_matrix_on_canvas(
    canvas,                        # tkinter.Canvas
    qr_matrix: QRMatrix,
    module_size: int = 10,         # 每个 module 的像素边长
    bg_color: str = "white",
    fg_color: str = "black",
) -> int:
    """在 tkinter Canvas 上直接绘制 QR。

    返回绘制后的图像总像素尺寸（正方形边长）。
    不生成任何图像文件，不依赖 Pillow。
    """
    total_modules = qr_matrix.module_count + 2 * qr_matrix.quiet_zone
    pixel_size = total_modules * module_size

    # 白色背景
    canvas.create_rectangle(0, 0, pixel_size, pixel_size, fill=bg_color, outline="")

    # 只画黑块（白块由背景覆盖）
    for r in range(qr_matrix.module_count):
        for c in range(qr_matrix.module_count):
            if qr_matrix.matrix[r][c]:
                x = (c + qr_matrix.quiet_zone) * module_size
                y = (r + qr_matrix.quiet_zone) * module_size
                canvas.create_rectangle(
                    x, y, x + module_size, y + module_size,
                    fill=fg_color, outline="",
                )
    return pixel_size
```

#### 7.3.3 渲染器 B：PPM 字节导出（调试 / 集成测试）

```python
def matrix_to_ppm(
    qr_matrix: QRMatrix,
    module_size: int = 10,
) -> bytes:
    """生成 PPM (P6) 二进制图像字节。

    纯 stdlib 实现，不依赖任何图像库。
    PPM 可被 Pillow (Image.open)、tkinter.PhotoImage(file=) 直接读取。

    格式: "P6\\n<width> <height>\\n255\\n" + RGB pixel data
    """
    n = qr_matrix.module_count
    qz = qr_matrix.quiet_zone
    total = n + 2 * qz
    size = total * module_size

    header = f"P6\n{size} {size}\n255\n".encode("ascii")
    white = b"\xff\xff\xff"
    black = b"\x00\x00\x00"

    pixels = bytearray()
    for img_row in range(size):
        qr_r = img_row // module_size - qz
        in_matrix_r = 0 <= qr_r < n
        for img_col in range(size):
            qr_c = img_col // module_size - qz
            if in_matrix_r and 0 <= qr_c < n and qr_matrix.matrix[qr_r][qr_c]:
                pixels.extend(black)
            else:
                pixels.extend(white)

    return header + bytes(pixels)
```

#### 7.3.4 渲染器 C：终端 Unicode（降级显示）

```python
def matrix_to_unicode(qr_matrix: QRMatrix) -> str:
    """用 Unicode 半块字符渲染 QR（终端降级方案）。

    每个字符表示 2 行 module，大幅压缩高度。
    字符映射: ▀(上黑下白) ▄(上白下黑) █(全黑) ' '(全白)
    """
    n = qr_matrix.module_count
    qz = qr_matrix.quiet_zone
    total = n + 2 * qz

    # 构建含静区的完整网格
    grid = [[False] * total for _ in range(total)]
    for r in range(n):
        for c in range(n):
            grid[r + qz][c + qz] = qr_matrix.matrix[r][c]

    lines = []
    for r in range(0, total, 2):
        line = []
        for c in range(total):
            top = grid[r][c]
            bottom = grid[r + 1][c] if r + 1 < total else False
            if top and bottom:
                line.append("\u2588")   # █
            elif top:
                line.append("\u2580")   # ▀
            elif bottom:
                line.append("\u2584")   # ▄
            else:
                line.append(" ")
        lines.append("".join(line))
    return "\n".join(lines)
```

### 7.4 `sqr/sender/player.py`

```python
import tkinter as tk
from pathlib import Path

from sqr.sender.qr_render import QRMatrix, draw_matrix_on_canvas


class QRPlayer:
    """全屏循环播放 QR 帧的 tkinter 窗口。

    使用 Canvas 直接渲染，不依赖 Pillow / PhotoImage。
    """

    def __init__(
        self,
        matrices: list[QRMatrix],       # 按 index 排序（manifest 在前）
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
        self._current = 0
        self._root = None
        self._canvas = None
        self._info_label = None

    def run(self) -> None:
        """启动 tkinter mainloop（阻塞）。"""
        self._root = tk.Tk()
        self._root.title(self._title)
        self._root.attributes("-fullscreen", True)
        self._root.bind("<Escape>", lambda e: self._root.quit())

        self._canvas = tk.Canvas(self._root, bg="white", highlightthickness=0)
        self._canvas.pack(fill="both", expand=True)

        self._info_label = tk.Label(
            self._root, text="", font=("Courier", 16),
            bg="white", fg="black", anchor="w",
        )
        self._info_label.pack(side="bottom", fill="x")

        self._show_frame()
        self._root.mainloop()

    def _show_frame(self) -> None:
        """渲染当前帧 + 调度下一帧。"""
        self._canvas.delete("all")
        matrix = self._matrices[self._current]
        pixel_size = draw_matrix_on_canvas(
            self._canvas, matrix, self._module_size
        )

        # 更新信息栏
        index = self._current  # 0=manifest, 1..N=data
        self._info_label.config(
            text=f"  file_id={self._file_id}  |  {index}/{self._total}  |  {self._filename}"
        )

        # 前进
        self._current = (self._current + 1) % len(self._matrices)
        self._root.after(self._interval_ms, self._show_frame)
```

---

## 8. 接收端模块设计

> 外网运行，可使用 pip 安装依赖或 PyInstaller 打包。

### 8.1 `sqr/receiver/capturer.py`

```python
from dataclasses import dataclass
import mss


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


class ScreenCapturer:
    """固定区域截图器（线程安全）。"""

    def __init__(self, region: CaptureRegion) -> None:
        self._region = region
        self._sct = mss.mss()

    def capture(self):
        """截取指定区域，返回 PIL Image。"""
        ...

    def close(self) -> None:
        self._sct.close()
```

### 8.2 `sqr/receiver/decoder.py`

```python
from typing import Protocol


def decode_qr(image) -> str | None:
    """从图像解码 QR，返回原始字符串。

    优先 pyzbar，自动回退 opencv。
    """
    ...


def decode_qr_from_file(path) -> str | None:
    """从图像文件解码 QR（测试用）。"""
    ...
```

**实现**：
- 首选 `pyzbar.decode(image)` → 取 `decoded[0].data.decode("utf-8")`。
- 回退 `cv2.QRCodeDetector().detectAndDecode(np.array(image))`。

### 8.3 `sqr/receiver/assembler.py`

```python
from dataclasses import dataclass, field
import threading
from sqr.protocol import Chunk, FileManifest, FrameType, ProtocolError


@dataclass
class AssemblyProgress:
    """当前采集进度（只读视图）。"""
    file_id: str | None = None
    total: int | None = None
    manifest: FileManifest | None = None
    received_indices: set[int] = field(default_factory=set)
    missing_indices: set[int] = field(default_factory=set)
    conflicts: dict[int, list[str]] = field(default_factory=dict)

    @property
    def is_complete(self) -> bool:
        ...

    @property
    def received_count(self) -> int:
        ...

    @property
    def percent(self) -> float:
        ...


class ChunkAssembler:
    """分片收集器：校验、去重、排序、拼接。

    线程安全：内部用 threading.Lock。capturer 线程调 add()，
    主线程调 get_progress() / assemble()。
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._progress = AssemblyProgress()
        self._chunks: dict[int, Chunk] = {}

    def add_raw(self, raw: str) -> bool:
        """解析原始字符串并尝试加入。返回是否为新有效分片。"""
        ...

    def add_chunk(self, chunk: Chunk) -> bool:
        """已解析的 Chunk 加入。"""
        ...

    def get_progress(self) -> AssemblyProgress:
        """获取当前进度快照。"""
        ...

    def assemble(self) -> bytes:
        """拼接 → Base64 解码 → 返回压缩字节。仅在 is_complete 时调用。"""
        ...

    def reset(self) -> None:
        """清空当前会话。"""
        ...
```

### 8.4 `sqr/receiver/verifier.py`

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class VerificationResult:
    success: bool
    byte_count_match: bool
    sha256_match: bool
    md5_match: bool
    utf8_valid: bool
    actual_bytes: int
    actual_sha256: str
    actual_md5: str
    message: str


def verify_restored_file(
    data: bytes,
    manifest: FileManifest,
    expected_sha256: str | None = None,
    expected_md5: str | None = None,
    expected_bytes: int | None = None,
) -> VerificationResult:
    """全量校验恢复后的文件。校验顺序：字节 → SHA-256 → MD5 → UTF-8。"""
    ...
```

### 8.5 接收端主循环

```python
def run_receiver(
    region: CaptureRegion,
    output_path: Path,
    interval_ms: int = 500,
    expected_sha256: str | None = None,
    expected_md5: str | None = None,
    expected_bytes: int | None = None,
    on_progress=None,
    on_complete=None,
) -> VerificationResult:
    """接收端主循环。截图 → 解码 → assembler → verify。"""
    ...
```

---

## 9. CLI 设计

```bash
# 发送端（内网）
python -m sqr.cli send <FILE> [OPTIONS]
# 或 PyInstaller 可执行程序
./sqr-sender <FILE> [OPTIONS]

# 接收端（外网）
python -m sqr.cli receive [OPTIONS]
# 或 PyInstaller 可执行程序
./sqr-receive [OPTIONS]
```

### 9.1 send 子命令

| 参数 | 默认 | 说明 |
|------|------|------|
| `<FILE>` | （必填） | 待传输 UTF-8 文本文件 |
| `--interval` | 1.2 | 帧停留秒数 |
| `--error-correction` | M | QR 纠错等级 M/Q/L/H |
| `--max-payload` | 1200 | 单帧 payload 最大字符数 |
| `--zstd` | False | 使用 zstd（默认 gzip） |
| `--output-dir` | None | 保存 QR PPM 的目录（调试用） |
| `--no-manifest` | False | 不生成 manifest 帧 |
| `--renderer` | auto | 渲染器：auto/tkinter/terminal |
| `--module-size` | 10 | 每个 QR module 的像素边长 |

### 9.2 receive 子命令

| 参数 | 默认 | 说明 |
|------|------|------|
| `--region` | （必填） | 截图区域 `x,y,w,h` |
| `--output` | sqr_output.txt | 输出文件路径 |
| `--interval` | 0.5 | 截图间隔秒数 |
| `--expected-sha256` | None | 期望 SHA-256（覆盖 manifest） |
| `--expected-md5` | None | 期望 MD5 |
| `--expected-bytes` | None | 期望字节数 |

---

## 10. 错误处理矩阵

| 场景 | 发送端行为 | 接收端行为 |
|------|-----------|-----------|
| 源文件不是 UTF-8 | 拒绝发送，报错退出 | — |
| zstd 库不可用 | 自动回退 gzip，控制台警告 | — |
| PIL 不存在 | stub 生效，正常工作 | — |
| tkinter 不存在 | 回退终端 Unicode 渲染，警告 | — |
| QR 数据超过单码容量 | 降低 max_payload 重试 | — |
| 截图无 QR | — | 忽略，等下一帧 |
| QR 解码失败 | — | 忽略，不中断 |
| 协议版本不匹配 | — | 丢弃，控制台警告 |
| file_id 混入异会话帧 | — | 忽略（会话隔离） |
| CRC32 不匹配 | — | 丢弃，等重传 |
| 同 index 不同内容 | — | 记录冲突，保留首个 |
| 解压失败 | — | 报错，不猜测，要求重传 |
| SHA-256 不匹配 | — | 报错，不保存，要求重传 |

---

## 11. 测试策略

### 11.1 单元测试（不走屏幕，发送端无需 Pillow）

| 测试文件 | 覆盖目标 | 关键用例 |
|---------|---------|---------|
| `test_protocol.py` | Chunk encode/decode 对称性 | 正常帧、manifest 帧、版本错误、CRC 不匹配、index 越界 |
| `test_chunker.py` | 分片逻辑 | 空文件、整除、余 1、大文件 total 计算 |
| `test_compressor.py` | 压缩回环 | gzip 回环、Base64 无换行 |
| `test_qr_render.py` | ★ QR 矩阵 + PPM 生成 | matrix 尺寸正确、PPM 头部格式、matrix 对称性 |
| `test_assembler.py` | 收集器逻辑 | 乱序到达、重复帧忽略、CRC 拒绝、冲突检测 |
| `test_verifier.py` | 校验逻辑 | 全通过、字节不符、SHA 不符 |

### 11.2 集成测试（★ 核心：不走屏幕）

`test_roundtrip.py` — **纯 stdlib + vendor qrcode 生成 PPM，接收端用 Pillow 读 PPM**：

```python
def test_full_roundtrip_mid_file():
    """file → compress → chunk → QR matrix → PPM → 读PPM → decode → assemble → verify"""
    # 1. 发送端：生成所有 QR PPM（纯 stdlib，无 Pillow）
    manifest, chunks = build_all_frames("sample_mid.txt", raw_bytes, sha256, md5)
    ppm_files = []
    for chunk in chunks:
        qr = generate_matrix(chunk.encode())
        ppm_data = matrix_to_ppm(qr)
        path = tmp_dir / f"frame_{chunk.index:04d}.ppm"
        path.write_bytes(ppm_data)
        ppm_files.append(path)

    # 2. 接收端：用 Pillow 读 PPM，pyzbar 解码（此处需要 Pillow）
    assembler = ChunkAssembler()
    for path in sorted(ppm_files):
        decoded_str = decode_qr_from_file(path)
        assembler.add_raw(decoded_str)

    # 3. 校验
    assert assembler.get_progress().is_complete
    compressed = assembler.assemble()
    raw = gzip.decompress(compressed)
    result = verify_restored_file(raw, manifest)
    assert result.success
```

**关键点**：发送端 PPM 生成纯 stdlib（不依赖 Pillow）；接收端读 PPM 需要 Pillow（在外网/构建机可用）。此测试在构建机上运行，CI 可直接用。

### 11.3 屏幕层测试（手动）

需要实际 VMware 窗口，按方案 §5 调整参数。

---

## 12. 配置与默认值汇总

| 参数 | 默认值 | 可调范围 | 出处 |
|------|--------|---------|------|
| 压缩算法 | gzip -9 | gzip / zstd -19 | 方案 §6.3 |
| 文本编码 | Base64（无换行） | Base64 | 方案 §6.4 |
| 单帧 payload 上限 | 1200 chars | 800–1500 | 方案 §5 |
| QR 纠错等级 | M | M / Q | 方案 §5 |
| QR 静区 | 4 modules | ≥4 | 方案 §5 |
| QR module_size | 10 px/module | 保证 ≥700×700 | 方案 §5 |
| 帧停留时间（发送） | 1.2 秒 | 0.8–1.5 | 方案 §5 |
| 截图间隔（接收） | 0.5 秒 | 0.3–1.0 | 本文档 |
| file_id 长度 | 12 hex | 固定 | 方案 §4 |
| 渲染器 | auto (tkinter → terminal) | tkinter/terminal | 本文档 |

---

## 13. 打包与部署（★ 零安装核心）

### 13.1 一次性准备：vendor qrcode

```bash
# 在外网构建机上执行
python3 build/vendor_qrcode.py
# → 下载 qrcode 源码到 sqr/vendor/qrcode/
# → 验证 PIL stub 工作（import qrcode 无 Pillow 不报错）
```

`build/vendor_qrcode.py` 逻辑：
1. `pip download qrcode --no-deps --no-binary :all: -d /tmp/qr_src`
2. 解压到 `sqr/vendor/qrcode/`
3. 运行验证脚本：在无 Pillow 环境下 `import sqr.vendor; import qrcode; print("OK")`
4. 记录 vendored 版本号到 `sqr/vendor/QRCODE_VERSION`

### 13.2 Tier 1：源码 + vendor 打包

```bash
python3 build/bundle_sender.py --tier 1
# 产出: dist/sqr-sender-src.zip
```

`dist/sqr-sender-src.zip` 内容：
```
sqr-sender/
├── sqr/
│   ├── __init__.py
│   ├── protocol.py
│   ├── sender/
│   ├── vendor/
│   │   ├── __init__.py          # PIL stub + sys.path 注入
│   │   └── qrcode/              # vendored 纯 Python
│   └── cli.py
├── send.sh                      # 启动脚本
├── send.bat                     # Windows 启动脚本
└── README.txt                   # 使用说明
```

`send.sh` 内容：
```bash
#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$DIR/sqr/cli.py" send "$@"
```

**内网使用方式**（有 Python 3.6+）：
```bash
unzip sqr-sender-src.zip
cd sqr-sender
./send.sh all_tcl_commands_help.txt
```

### 13.3 Tier 2：PyInstaller 打包（内嵌 Python）

```bash
python3 build/bundle_sender.py --tier 2
# 或直接用 spec:
pyinstaller build/sender.spec --distpath dist/
```

`build/sender.spec` 关键配置：
```python
# PyInstaller spec for sender
a = Analysis(
    ['sqr/cli.py'],
    pathex=['.'],
    datas=[('sqr/vendor', 'sqr/vendor')],   # 打包 vendor 目录
    ...
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas,
          name='sqr-sender',
          console=True,     # 需要终端输出状态
          ...)
```

**注意**：
- PyInstaller 必须在与内网**相同 OS/arch** 的机器上构建（Linux→Linux, Windows→Windows）。
- tkinter + Tcl/Tk 会被 PyInstaller 自动内嵌。
- 产出 `dist/sqr-sender/`（onedir）或 `dist/sqr-sender`（onefile）。

**内网使用方式**（无 Python）：
```bash
tar xzf sqr-sender-linux.tar.gz
./sqr-sender/sqr-sender all_tcl_commands_help.txt
```

### 13.4 接收端打包

```bash
# 源码方式（外网机器 pip install）
pip install -r requirements-receiver.txt
python3 -m sqr.cli receive --region ...

# PyInstaller 方式（零安装）
pyinstaller build/receiver.spec --distpath dist/
./dist/sqr-receive --region ...
```

`requirements-receiver.txt`：
```
pyzbar>=0.1.9
mss>=9.0.1
Pillow>=10.0.0
```

### 13.5 打包验证清单

构建后自动执行以下验证：

| 验证项 | 方法 |
|--------|------|
| vendor qrcode 导入无 Pillow | `python3 -c "import sqr.vendor; import qrcode"` 在无 Pillow 环境 |
| PIL stub 不影响真实 Pillow | 有 Pillow 时 `import sqr.vendor; import PIL; PIL.__version__` |
| PPM 生成正确 | `test_qr_render.py` 通过 |
| 端到端 round-trip | `test_roundtrip.py` 通过 |
| tkinter Canvas 渲染 | 手动运行 player，目视检查 |
| PyInstaller 产物可执行 | 在干净环境（无 Python）运行 sender |

---

## 14. 分阶段实现计划

### Phase 1 — 协议核心（纯 stdlib，可独立测试）

| 步骤 | 产出 | 验证 |
|------|------|------|
| 1.1 | `sqr/protocol.py`：Chunk、FileManifest、异常、纯函数 | `test_protocol.py` 全绿 |
| 1.2 | `sqr/sender/compressor.py` | `test_compressor.py` 全绿 |
| 1.3 | `sqr/sender/chunker.py` | `test_chunker.py` 全绿 |

**里程碑**：`pytest tests/test_protocol.py tests/test_compressor.py tests/test_chunker.py` 通过。

### Phase 2 — Vendor 基础设施 + QR 渲染（★ 零安装核心）

| 步骤 | 产出 | 验证 |
|------|------|------|
| 2.1 | `build/vendor_qrcode.py` + `sqr/vendor/qrcode/` | `import qrcode` 无 Pillow 成功 |
| 2.2 | `sqr/vendor/__init__.py`：PIL stub | 有/无 Pillow 均正常 |
| 2.3 | `sqr/sender/qr_render.py`：matrix + Canvas + PPM + Terminal | `test_qr_render.py` 全绿 |

**里程碑**：在无 Pillow 环境下 `generate_matrix()` + `matrix_to_ppm()` 正常工作。

### Phase 3 — 接收端管线 + 端到端（不走屏幕）

| 步骤 | 产出 | 验证 |
|------|------|------|
| 3.1 | `sqr/receiver/decoder.py` | 从 PPM 文件解码 QR |
| 3.2 | `sqr/receiver/assembler.py` | `test_assembler.py` 全绿 |
| 3.3 | `sqr/receiver/verifier.py` | `test_verifier.py` 全绿 |
| 3.4 | `test_roundtrip.py` | **★ 端到端 round-trip 通过** |

**里程碑**：`test_roundtrip.py` 对 3 个 fixture 全部通过——证明协议层 + QR 生成/解码正确。

### Phase 4 — 屏幕层

| 步骤 | 产出 | 验证 |
|------|------|------|
| 4.1 | `sqr/sender/player.py` | 手动：全屏 Canvas 播放，ESC 退出 |
| 4.2 | `sqr/receiver/capturer.py` | 手动：截图保存，确认区域 |
| 4.3 | `sqr/cli.py` | `send --help` / `receive --help` 正常 |

### Phase 5 — 打包与部署（★ 零安装落地）

| 步骤 | 产出 | 验证 |
|------|------|------|
| 5.1 | `build/bundle_sender.py` (Tier 1) | `dist/sqr-sender-src.zip` 解压即用 |
| 5.2 | `build/sender.spec` + PyInstaller (Tier 2) | 干净环境运行成功 |
| 5.3 | `build/bundle_receiver.py` | `dist/sqr-receive` 可执行 |
| 5.4 | VMware 实际测试 | MD5 `fd3b2ff5b10c902575332e8bbdd616f9` 匹配 |

**里程碑**：方案 §10 验收标准全部满足。

---

## 15. 与原始方案的对应关系

| 方案章节 | 本文档对应 |
|---------|-----------|
| §3 数据流水线 | §7.1 compressor + §7.2 chunker + §8.3 assembler |
| §4 分片协议 | §5 协议规范 + §6 protocol.py |
| §5 二维码参数 | §7.3 qr_render + §12 配置表 |
| §6 内网发送端 | §7 全部 + §9.1 CLI send + §13 打包 |
| §7 外网接收端 | §8 全部 + §9.2 CLI receive |
| §8 完整性与恢复 | §5.3 拒绝条件 + §8.3 去重逻辑 + §10 错误矩阵 |
| §10 验收标准 | §8.4 verifier + §11 测试策略 |
| §11 安全边界 | 文档约定 + CLI 提示，不在代码层面强制 |

---

## 16. 风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| vendor qrcode 版本升级后 import 链变化 | PIL stub 失效 | `vendor_qrcode.py` 构建后自动验证导入；锁定 vendored 版本 |
| tkinter 在 headless Linux 上不可用 | 发送端无法显示 | 终端 Unicode 渲染器作为降级方案；PyInstaller 内嵌 Tcl/Tk |
| PyInstaller 跨平台构建 | 内网 OS 与构建机不同 | 文档明确：必须同 OS/arch 构建；提供 Docker 构建方案 |
| pyzbar/libzbar 在新 macOS 上签名问题 | 接收端解码失败 | decoder.py 适配层自动回退 opencv-python |
| VMware Retina 缩放导致截图模糊 | QR 识别失败 | 接收端截图后不缩放；region 坐标基于物理像素 |
| 会话混淆 | 拼接出错误数据 | assembler 严格按 file_id 隔离；manifest 校验 |
| 大文件（>100KB）帧数过多 | 传输耗时过长 | 文档定位为普通文本；后续可加 XOR 冗余帧 |

---

## 17. 打包与部署速查

### 外网构建机（一次性准备）

```bash
# 1. vendor qrcode（下载纯 Python 源码到项目内）
python3 build/vendor_qrcode.py

# 2. 验证无 Pillow 可用
python3 -c "import sqr.vendor; import qrcode; print('vendor OK')"

# 3. 打包发送端 Tier 1（源码 zip）
python3 build/bundle_sender.py --tier 1
# → dist/sqr-sender-src.zip

# 4. 打包发送端 Tier 2（PyInstaller，需与内网同 OS）
pip install pyinstaller
python3 build/bundle_sender.py --tier 2
# → dist/sqr-sender/

# 5. 打包接收端（PyInstaller）
brew install zbar           # macOS only
pip install -r requirements-receiver.txt
python3 build/bundle_receiver.py
# → dist/sqr-receive
```

### 内网部署

```bash
# 方式 A：有 Python 3.6+
unzip sqr-sender-src.zip
cd sqr-sender
./send.sh all_tcl_commands_help.txt --interval 1.2

# 方式 B：无 Python（PyInstaller 产物）
tar xzf sqr-sender-linux.tar.gz
./sqr-sender/sqr-sender all_tcl_commands_help.txt --interval 1.2
```

### 外网接收

```bash
# 方式 A：源码
pip install -r requirements-receiver.txt
python3 -m sqr.cli receive \
    --region 200,150,700,700 \
    --output all_tcl_commands_help_received.txt \
    --expected-md5 fd3b2ff5b10c902575332e8bbdd616f9 \
    --expected-bytes 29816

# 方式 B：PyInstaller 可执行程序
./dist/sqr-receive \
    --region 200,150,700,700 \
    --output all_tcl_commands_help_received.txt \
    --expected-md5 fd3b2ff5b10c902575332e8bbdd616f9
```
