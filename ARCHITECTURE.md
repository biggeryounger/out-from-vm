# sqr 架构文档

> **Screen QR Transfer** —— 通过屏幕二维码序列实现**内网 → 外网单向文件传输**的工具。
>
> 内网机器无网络、无 USB、无共享目录、无剪贴板，唯一对外通道是「外网能看见内网屏幕」。sqr 把屏幕当作单向光学通道：内网循环播放二维码，外网截图解码还原文件。

## 架构总览

```
内网发送端（零安装）                         外网接收端
┌────────────────────────────┐            ┌────────────────────────────┐
│ 文件 / 目录                │  屏幕 QR   │ mss 截图 → pyzbar 解码      │
│  ↓ 目录先封装 sqrbundle    │ ◀────────│  ↓                          │
│  ↓ gzip + base64           │  光学单向 │ SQ1 帧解析 → 去重/校验       │
│  ↓ 分片 + CRC32            │  通道     │  ↓                          │
│  ↓ manifest 帧(index=0)    │           │ base64 解码 → gunzip         │
│  ↓ QR matrix → HTML        │           │  ↓ 文件写出 / 目录安全还原    │
│ (纯 stdlib + vendor qrcode) │           │ SHA-256/MD5/逐文件校验       │
└────────────────────────────┘            └────────────────────────────┘
   仅需 Python 3.6+ + 浏览器                 pyzbar + libzbar + mss + Pillow
```

**单向性**：数据只能从内网流向外网（屏幕被看见），外网无法回传。这是物理隔离决定的，不是软件限制。

## 分层设计

```
                    ┌──────────────────────────────────────┐
                    │  sqr/cli.py  (入口编排: send/receive/gui) │
                    └──────────┬───────────────────────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        ▼                      ▼                      ▼
┌───────────────┐     ┌─────────────────┐    ┌─────────────────┐
│ sqr/sender/   │     │ sqr/receiver/   │    │ sqr/vendor/     │
│ 发送端管线     │     │ 接收端管线       │    │ 零安装基础设施    │
│ (compressor →  │     │ (capturer →     │    │ (PIL stub +     │
│  chunker →     │     │  decoder →      │    │  vendored qrcode)│
│  qr_render →   │     │  assembler →    │    │ 仅 sender 用    │
│  player)       │     │  verifier)      │    └─────────────────┘
└───────┬───────┘     └────────┬────────┘
        │                      │
        └──────────┬───────────┘
                   ▼
          ┌─────────────────┐
          │ sqr/protocol.py │
          │ SQ1 协议（共用） │
          │ Chunk / Manifest│
          │ CRC32 / SHA / MD5│
          └─────────────────┘
```

| 层 | 职责 | 谁依赖它 |
|---|---|---|
| `sqr/protocol.py` | SQ1 帧编解码、文件元数据、校验函数。纯 stdlib | sender + receiver 共用 |
| `sqr/bundle/` | 目录确定性封装、逐文件 SHA-256 清单、安全解包与原子提交 | sender + receiver 共用 |
| `sqr/sender/` | 文件 → QR 帧序列 → 屏幕播放 | 仅 `cli.cmd_send` 调用 |
| `sqr/receiver/` | 截图 → 解码 → 组装 → 校验 → 还原 | `cli.cmd_receive` + `cli.cmd_gui` |
| `sqr/vendor/` | PIL stub + vendored qrcode，让发送端零安装 | 仅 `sender/qr_render.py` 用 |
| `sqr/cli.py` | argparse 入口，编排 send / receive / gui 三个子命令 | 用户/启动器入口 |

详细架构见各模块文档：
- [sqr/sender/ARCHITECTURE.md](sqr/sender/ARCHITECTURE.md) —— 发送端管线
- [sqr/receiver/ARCHITECTURE.md](sqr/receiver/ARCHITECTURE.md) —— 接收端管线 + GUI
- [sqr/vendor/ARCHITECTURE.md](sqr/vendor/ARCHITECTURE.md) —— PIL stub + vendor 机制

## SQ1 协议

帧是 QR 码的内容字符串，格式：

```
SQ1|<file_id>|<index>|<total>|<crc32:08x>|<payload>
```

| 字段 | 含义 |
|---|---|
| `SQ1` | 协议版本（固定）|
| `file_id` | SHA-256 前 12 字符，文件标识 |
| `index` | 帧序号。**0 = manifest 帧**，1..N = 数据帧 |
| `total` | 数据帧总数（不含 manifest）|
| `crc32` | payload 的 CRC32，8 位 hex（`%08x`）|
| `payload` | Base64 ASCII 内容 |

**解析安全性**：`Chunk.decode` 用 `split("|", maxsplit=5)` 最多分 6 段，payload 中的 `|` 不会被误切。

### 两种帧

| 帧 | index | payload 内容 | 作用 |
|---|---|---|---|
| **manifest** | 0 | `FileManifest` 的 Base64-JSON（短键名 `v/fn/n/s/m/c/e`）| 携带文件名/原始字节数/SHA-256/MD5/压缩方式 |
| **data** | 1..N | 压缩+Base64 后的文件内容切片 | 实际文件数据 |

**为什么 manifest 混在循环里**：接收端从任意帧开始截图都能工作——先收到某数据帧知道 file_id/total，收到 manifest 帧拿到校验信息，逐步补齐所有 index。这让单向传输无需两端时间同步。

### 协议核心类型（`sqr/protocol.py`）

| 符号 | 说明 |
|---|---|
| `Chunk` | `@dataclass(frozen)`: file_id, index, total, crc32, payload + `encode()/decode()/verify_crc()/frame_type` |
| `FileManifest` | `@dataclass(frozen)`: schema_version, filename, original_bytes, sha256, md5, compression, encoding + `encode_payload()/decode_payload()` |
| `compute_file_id(sha256_hex)` | 取 SHA-256 前 12 字符 |
| `compute_crc32(data)` | `binascii.crc32 & 0xFFFFFFFF` |
| `compute_sha256(data)` / `compute_md5(data)` | hashlib |
| 异常 | `ProtocolError` / `CrcMismatchError` / `IndexConflictError` |

## 关键技术决策

### 0. 目录信息包复用 SQ1

发送目录时，`sqr.bundle.builder` 先生成确定性 ZIP_STORED 信息包。包内
`.sqr-bundle.json` 记录根目录、全部相对路径、空目录、文件大小与逐文件
SHA-256；随后仍走原有 gzip/zstd、Base64、SQ1 分片和 QR 渲染。接收端先校验
整包 SHA-256，再由 `sqr.bundle.extractor` 拒绝绝对路径、`..`、反斜杠、盘符、
重复路径及清单外成员，解包到 `.sqr-partial-*`，全部逐文件校验通过后原子发布
根目录。符号链接与特殊文件在发送端直接拒绝。

可重复的 `send --include-regex <pattern>` 在目录扫描阶段用 Python `re.search`
匹配文件 basename；多个 pattern 按 OR。启用筛选后，只把匹配文件及其必要祖先
目录写入 bundle，避免把无关空目录或兄弟目录带到外网。

### 1. 去 Pillow 化（发送端零安装的关键）

Pillow 有 C 扩展，内网无法 pip install。发送端用两层手段绕过：
- **vendor qrcode**：纯 Python 的 qrcode 库直接拷进 `sqr/vendor/qrcode/`
- **PIL stub**（`sqr/vendor/__init__.py`）：注入假 `PIL` 模块到 `sys.modules`，让 qrcode 的 PIL 导入链通过，但发送端只取 `qr.modules`（纯布尔矩阵），从不调 `make_image()`

详见 [sqr/vendor/ARCHITECTURE.md](sqr/vendor/ARCHITECTURE.md)。

### 2. 循环播放 + 渐进补齐

manifest 帧和数据帧混在**同一个循环**里反复播放（`player.QRPlayer`）。接收端循环截图，靠 CRC32 去重、靠 index 补齐缺失帧，直到 `is_complete`。无需两端时间同步，丢失的帧下一轮自然会再播。

### 3. 线程安全组装器

`ChunkAssembler` 用 `threading.Lock` 保护所有写操作（`capturer` 线程 add，主线程 get_progress/assemble）。`get_progress` 返回深拷贝快照，调用方可任意使用无锁风险。

### 4. GUI 线程模型

tkinter 非线程安全。`app.ReceiverApp` 把截图主循环放后台 daemon 线程，事件通过 `queue.Queue` 传递，主线程 `root.after(100ms)` 轮询更新 UI。后台线程绝不直接触碰 widget。

## 依赖矩阵

| 依赖 | 发送端（内网） | 接收端（外网） | 性质 | 来源 |
|---|:-:|:-:|---|---|
| `qrcode` | ✅ | — | 纯 Python | **vendor 到项目内** |
| `Pillow` | ❌ stub 兜底 | ✅ | C 扩展 | 接收端 pip |
| `pyzbar` | — | ✅ | C 绑定 | 接收端 pip |
| `libzbar` | — | ✅ | 原生 C 库 | brew / apt（`init.sh install` 自动）|
| `mss` | — | ✅ | C 扩展 | 接收端 pip |
| `opencv-python` | — | 可选 | 回退解码 | 接收端 pip（可选）|
| `zstandard` | 可选 | 可选 | C 扩展 | 不打包，无则回退 gzip |
| `tkinter` | ✅ | ✅(GUI) | stdlib | Python 自带 |
| stdlib(gzip/base64/hashlib/binascii/json) | ✅ | ✅ | 内置 | — |

**发送端外部编译依赖 = 0**。接收端用 `./init.sh install` 一键全自动安装（.venv + pip + libzbar）。

## 目录结构

```
out-from-vm/
├── sqr/
│   ├── __init__.py
│   ├── cli.py                  # argparse 入口: send / receive / gui
│   ├── protocol.py             # SQ1 协议（共用层）
│   ├── bundle/                 # 目录信息包 builder + 安全 extractor
│   ├── sender/                 # 发送端（详见 sender/ARCHITECTURE.md）
│   │   ├── ARCHITECTURE.md
│   │   ├── compressor.py       # 压缩 + base64（含解压，接收端跨层调用）
│   │   ├── chunker.py          # 分片 + CRC + manifest 组装
│   │   ├── qr_render.py        # QR matrix + 3 种渲染器（Canvas/PPM/Unicode）
│   │   └── player.py           # tkinter 全屏循环播放
│   ├── receiver/               # 接收端（详见 receiver/ARCHITECTURE.md）
│   │   ├── ARCHITECTURE.md
│   │   ├── capturer.py         # mss 固定区域截图
│   │   ├── decoder.py          # pyzbar 解码 + opencv 回退
│   │   ├── assembler.py        # 线程安全分片收集器（核心）
│   │   ├── verifier.py         # 字节/SHA/MD5/UTF-8 全量校验
│   │   ├── runner.py           # 接收端主循环
│   │   ├── region_selector.py  # 跨屏拖拽框选 GUI
│   │   └── app.py              # 接收端控制面板 GUI
│   └── vendor/                 # 零安装基础设施（详见 vendor/ARCHITECTURE.md）
│       ├── ARCHITECTURE.md
│       ├── __init__.py         # PIL stub + sys.path bootstrap
│       └── qrcode/             # vendored 第三方库（24 .py，勿改）
├── tests/                      # pytest（基线 92 passed）
├── launcher/                   # send.sh / send.bat（启动器，含自检）
├── build/                      # bundle_sender.py（Tier 1 打包）
├── dist/                       # 打包产物（sqr-sender-src.zip 发布包）
├── init.sh                     # 统一入口: install / test / receive / send / gui
├── conftest.py                 # pytest 配置
├── requirements-*.txt          # 依赖声明（receiver/test/build）
├── AGENTS.md                   # Agent 协作约定
├── claude-progress.md          # 会话级状态日志
├── feature_list.json           # 功能级状态（机器可读）
├── implementation-plan.md      # 完整实施设计（只读参考）
└── screen-qr-transfer.md       # 原始方案文档（只读参考）
```

## 入口点

| 命令 | 作用 |
|---|---|
| `./init.sh install` | 全自动安装接收端环境（.venv + pip + libzbar），装完退出 |
| `./init.sh` | 安装依赖 + 跑测试 + 打印启动菜单 |
| `./init.sh send <file>` | 安装+验证+启动发送端 |
| `./init.sh receive` | 安装+验证+启动接收端（默认 GUI 框选）|
| `./init.sh gui` | 接收端控制面板 |
| `./init.sh test [args]` | 只跑测试（参数透传给 pytest）|
| `python3 -m sqr.cli send <file-or-directory>` | 直接调发送端（跳过 init.sh）|
| `python3 -m sqr.cli receive --output <path>` | 直接调接收端 |

**发送端内网部署**：解压 `dist/sqr-sender-src.zip` → `./send.sh <file>`（send.sh 启动前自检 Python/tkinter/vendor，缺失友好报错）。

## 测试与打包

- **测试**：`python3 -m pytest tests/ -q`，基线 **92 passed**。覆盖 protocol / compressor / chunker / qr_render / roundtrip（PPM-based 端到端）。
- **打包**（Tier 1）：`python3 build/bundle_sender.py` → `dist/sqr-sender-src.zip`（~45KB，源码 + vendor，解压即用）。Tier 2 PyInstaller 单文件可执行程序见 `feature_list.json` 的 `t2`。

## 相关文档

| 文档 | 角色 |
|---|---|
| 本文件 | 顶层架构导航 |
| [sqr/sender/ARCHITECTURE.md](sqr/sender/ARCHITECTURE.md) | 发送端模块架构 |
| [sqr/receiver/ARCHITECTURE.md](sqr/receiver/ARCHITECTURE.md) | 接收端模块架构 |
| [sqr/vendor/ARCHITECTURE.md](sqr/vendor/ARCHITECTURE.md) | vendor / PIL stub 架构 |
| `AGENTS.md` | Agent 协作约定（开工流程、工作规则、完成定义）|
| `implementation-plan.md` | 完整实施设计文档（v2，1334 行，只读参考）|
| `screen-qr-transfer.md` | 原始方案文档（只读参考）|
| `claude-progress.md` | 会话级状态日志（当前已验证状态 + 待办 + Session 记录）|
| `feature_list.json` | 功能级状态（机器可读，11 个 feature）|
