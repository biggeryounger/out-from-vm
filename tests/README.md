# sqr 测试方案

> sqr 项目的验证测试体系总览。任何修改 `tests/` 或 sqr 源码的 Agent，开工前必读本文档。
> 当前基线：**92 passed**（`python3 -m pytest tests/ -q`）。

---

## 1. 测试目标

证明三件事：

1. **协议正确**：`SQ1` 协议帧的 encode / decode 严格对称，错误输入被显式拒绝。
2. **数据完整**：文件经过 `gzip → b64 → 分片 → QR → PPM → pyzbar 解码 → 组装 → gunzip` 全链路后，**逐字节相等**。
3. **校验不放宽**：CRC32（chunk 级）、SHA-256 + MD5（文件级）三重校验必须全部通过。

---

## 2. 运行入口

| 命令 | 用途 | 何时用 |
|------|------|--------|
| `python3 -m pytest tests/ -q` | **标准全量验证**（应 92 passed） | 每轮开工基线 / 收尾确认 |
| `python3 -m pytest tests/test_<name>.py -q` | 单文件验证 | 只改了某一层时 |
| `python3 -m pytest tests/test_roundtrip.py -q` | 只跑端到端 | 验证光学链路是否回归 |
| `./init.sh` | `pip install -r requirements-test.txt` + 全量测试 + 打印启动菜单 | 全新环境 / CI |

> macOS 首次运行需先 `brew install zbar`（pyzbar 后端），不在 `init.sh` 职责内。

### 配置文件

- **`conftest.py`**（项目根）：把仓库根加入 `sys.path`，保证 `sqr` 包可从根导入。仅 7 行，勿改动。
- **`requirements-test.txt`**（项目根）：测试专用依赖（pyzbar、Pillow、mss、pytest）。与发送端运行时零依赖解耦。

---

## 3. 测试分层（金字塔）

```
                       ┌────────────────────────────────┐
                       │   test_roundtrip.py   (E2E)    │  ← 核心里程碑
                       │   file → PPM → decode → verify │
                       └────────────────────────────────┘
                 ┌─────────────────────────────────────────┐
                 │  test_qr_render.py      (QR 渲染层)      │
                 │  test_chunker.py        (分片层)         │
                 │  test_compressor.py     (压缩/编码层)    │
                 └─────────────────────────────────────────┘
             ┌─────────────────────────────────────────────────┐
             │         test_protocol.py     (协议层)            │
             │   Chunk / FileManifest / 哈希函数                │
             └─────────────────────────────────────────────────┘
```

| 文件 | 行数 | 层级 | 职责 |
|------|------|------|------|
| `test_protocol.py` | 308 | 协议层 | Chunk / FileManifest encode-decode 对称性、错误拒绝、哈希纯函数 |
| `test_compressor.py` | 80 | 压缩层 | gzip 回环、Base64 无换行、zstd 回退、空/Unicode 输入 |
| `test_chunker.py` | 276 | 分片层 | 分片边界、CRC 正确性、manifest 帧、`build_all_frames` 端到端 |
| `test_qr_render.py` | 156 | 渲染层 | QR 矩阵、PPM P6、Unicode half-blocks（不依赖 Pillow） |
| `test_roundtrip.py` | 222 | **E2E** | ★ 核心里程碑：完整光学链路逐字节还原 |

---

## 4. 各层测试详情

### 4.1 `test_protocol.py` — 协议层（最重）

**纯函数**
- `compute_crc32`：空串 = 0、`binascii.crc32` 已知值、str 与 bytes 等价、返回值始终 unsigned 32-bit。
- `compute_sha256` / `compute_md5`：用 NIST 标准已知向量验证（如 `sha256(b"") == "e3b0c442..."`）。
- `compute_file_id`：取 SHA-256 前 12 字符、短哈希场景。

**Chunk encode / decode 对称性**
- 数据帧、manifest 帧（`index=MANIFEST_INDEX`）、空 payload 回环。
- **`maxsplit` 保护**：payload 含 `|` 不被误切（`"abc|def|ghi"` 完整保留）。

**错误拒绝**（每个用 `pytest.raises(ProtocolError, match=...)` 锁定错误信息）
- 错误版本号（`SQ2|...`）、字段过少、非数字 index/total、非 hex crc32、空字符串。

**CRC 校验**
- 正确 CRC → `verify_crc() is True`；故意错误（`0xDEADBEEF`）→ `False`；零值编码为 `00000000`。

**FileManifest**
- 带/不带 MD5 回环；Base64 字符合法；无 `\n`/`\r`；字段缺失拒绝；Unicode 文件名（`中文文件名.txt`）。

### 4.2 `test_compressor.py` — 压缩/编码层

- gzip 回环（`compress_and_encode` → `decompress_payload`）。
- Base64 输出**不含换行**、字符集合法（`^[A-Za-z0-9+/=]+$`）。
- 空输入、Unicode（中文）输入回环。
- 压缩有效性（高重复文本压缩后更小）。
- `use_zstd=True` 但 `zstandard` 不可用时回退 gzip。
- 未知压缩算法（如 `"bzip2"`）→ `ValueError`。

### 4.3 `test_chunker.py` — 分片层

**边界值穷举**
- 单分片、空 payload、整除（300/100=3）、余数（305/100=4）、**余数=1**（301/100=4，最后一帧 1 字符）。

**CRC 正确性**
- 每个分片的 `crc32` == `compute_crc32(payload)`，`verify_crc() is True`。

**一致性**
- `file_id` 传播到所有分片；索引从 1 连续递增；所有分片 `total` 一致；payload 拼接 == 原始 Base64。

**`build_all_frames` 端到端**
- manifest 在 index=0、数据帧 index ≥ 1、`total` 处处等于数据帧数、每帧 `encode()` → `decode()` 对称。

### 4.4 `test_qr_render.py` — QR 渲染层（不依赖 Pillow）

> 发送端用 PIL stub 绕过 qrcode 对 PIL 的导入依赖，纯 stdlib + vendor。本层测试不导入真实 Pillow。

**QR 矩阵**
- 维度公式 `module_count = version * 4 + 17`；单元为 `bool`；默认 quiet_zone=4，可自定义。
- 4 种纠错级别（L/M/Q/H）；非法级别 `ValueError`；大数据 → 高 version。
- 模拟真实协议帧 `"SQ1|abcdef012345|1|10|0a1b2c3d|..."` 能正常生成矩阵。

**PPM P6 格式**
- Header `"P6\n<w> <h>\n255\n"`；像素数据大小 = `(total_modules * module_size)² * 3`。
- 含黑白像素（`\x00\x00\x00` / `\xff\xff\xff`）。
- `module_size=1` 时像素逐位匹配矩阵（最强不变量）。

**Unicode half-blocks**
- 返回 `str`；只用 `█ ▀ ▄`（U+2588/2580/2584）和空格；行数 = `(total+1)//2`。

**结构**
- `QRMatrix` 是 frozen dataclass（赋值触发 `AttributeError`）；左上角存在 Finder Pattern。

### 4.5 `test_roundtrip.py` — 端到端（★ 核心里程碑）

**这是最有价值的测试——证明整个光学链路可用：**

```
file → gzip/b64 → 分片+CRC → QR matrix → PPM 文件
     → Pillow+pyzbar 解码 → ChunkAssembler 组装 → gunzip → SHA-256/MD5 校验
```

**Fixture 文件**（`tests/fixtures/`）
- `sample_small.txt` / `sample_mid.txt` / `sample_repetitive.txt`（小 / 中 / 高重复三种典型）。

**验证项**
- `restored == raw`（逐字节相等）+ `len(restored) == len(raw)`。
- SHA-256 + MD5 双校验通过。
- 不同 `max_chars`（100 / 500 / 1200，影响分片数）、不同 `error_correction`（M / Q）、不同 `module_size`（5 / 10）。
- `@pytest.mark.parametrize` 跨 fixture 矩阵测试。
- 发送端生成的数据帧数 == 接收端收集的数据帧数。

> **架构耦合点**：发送端 PPM 生成纯 stdlib，接收端解码用 Pillow + pyzbar，两者通过 **PPM 文件**作为接口契约对接。本测试同时验证了这条契约。

---

## 5. 关键设计原则

1. **Round-trip（回环）是核心范式**
   凡是有 encode 的地方，必有 decode 回原值。协议层、压缩层、manifest 层都有回环测试。

2. **三重校验，不放宽**
   - CRC32 — 每个 chunk 级，8 位 hex
   - SHA-256 — 文件级，64 位 hex（NIST 已知向量）
   - MD5 — 文件级，32 位 hex（冗余校验）

3. **发送端 / 接收端解耦验证**
   发送端 PPM 生成纯 stdlib，接收端解码用 Pillow + pyzbar，通过 PPM 文件接口对接。端到端测试同时验证两端契约。

4. **错误路径全覆盖**
   每个 decode 函数都有"非法输入"测试，用 `pytest.raises(match=...)` 锁定错误信息，避免静默失败。

5. **边界值穷举**
   单分片、整除、余数、余数=1、空 payload、空文件。

6. **真实数据驱动**
   端到端用 fixture 文件，不用合成字符串，确保压缩行为接近生产。

---

## 6. 红线（反测试行为，禁止）

任何一项验证规则的弱化都**必须在 `claude-progress.md` 当前 Session 条目显式记录理由**。禁止：

- ❌ 放宽 CRC32 校验
- ❌ 放宽 SHA-256 校验
- ❌ 跳过失败用例（`pytest.skip` / `-k "not ..."`）
- ❌ 把 `assert` 改成警告或日志
- ❌ 删除失败测试让 suite"变绿"
- ❌ 引入对 Pillow / pyzbar 的依赖到发送端测试（破坏零安装目标）

---

## 7. 新增测试指引

新增 feature 时，按层级补测试：

| 改动位置 | 应补测试 |
|----------|----------|
| `sqr/protocol.py`（协议格式） | `test_protocol.py`：encode/decode 对称 + 错误拒绝 |
| `sqr/sender/compressor.py` | `test_compressor.py`：回环 + 边界 |
| `sqr/sender/chunker.py` | `test_chunker.py`：分片边界 + CRC + 一致性 |
| `sqr/sender/qr_render.py` | `test_qr_render.py`：格式 + 维度公式 |
| `sqr/receiver/*`（组装/解码/校验） | `test_roundtrip.py`：必须能跑通完整链路 |
| 任何改动 | `python3 -m pytest tests/ -q` 全绿 |

**测试命名**：`TestXxx` 类组织同一模块的用例；方法名 `test_<场景>_<期望>`，如 `test_remainder_one_char`、`test_wrong_version_rejected`。

---

## 8. 与"完成定义"挂钩

按 `AGENTS.md` §5，一个 feature 算完成的必要条件之一：

> ✅ `python3 -m pytest tests/ -q` 全绿，**且本次改动涉及的测试文件单独跑也全绿**。

测试不仅是技术验证，还是项目流程上"feature 是否可交付"的硬门槛：

- **开工第 6 步**：先跑 `pytest tests/ -q` 建立绿色基线（若失败则先修回归，不开新功能）。
- **收尾第 4 步**：再跑一次确认全绿。
- **收尾第 5 步**：提交信息需带验证结果（如 `feat(receiver): ... — 92 tests pass`）。
