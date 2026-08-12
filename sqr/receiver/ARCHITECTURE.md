# sqr/receiver/ 架构

> 外网接收端：从屏幕截图序列还原出原始文件。重依赖（pyzbar + libzbar + mss + Pillow），但外网可联网安装。

## 端到端数据流

```
屏幕（内网发送端在循环播放 QR 序列）
    │
    ▼  ScreenCapturer.capture()              ← capturer.py
    │     mss.grab(region) → PIL.Image(RGB)
    ▼
    decode_qr(img)                           ← decoder.py
    │     pyzbar.decode(img) ─失败回退─► cv2.QRCodeDetector
    │     返回 SQ1|file_id|idx|total|crc32|payload 字符串（或 None）
    ▼
    ChunkAssembler.add_raw(decoded_str)      ← assembler.py
    │     Chunk.decode → verify_crc → 去/重冲突检测 → 存入 _chunks[index]
    │     manifest 帧(index=0) → 解出 FileManifest（file_id/total/sha256/...）
    │     ★ 线程安全：threading.Lock 保护所有写操作
    ▼
    循环截图直到 is_complete (received == total)
    │
    ▼  assembler.assemble()                  ← assembler.py
    │     按 index 排序 → 拼接 payload → base64.b64decode → 压缩字节
    ▼
    decompress_payload(compressed, manifest.compression)  ← sender.compressor.py
    │     gzip.decompress 或 zstandard
    ▼  restored bytes
    │
    ▼  verify_restored_file(restored, manifest, ...)  ← verifier.py
    │     校验 字节数 / SHA-256 / MD5 / UTF-8（全检查不短路）
    │     CLI --expected-* 优先于 manifest
    ▼
    VerificationResult
    │  success → output_path.write_bytes(restored)
    ▼
    on_complete 回调（更新进度条/日志/弹窗）
```

主循环在 **`runner.run_receiver`**（`runner.py:18`）里，`cli.cmd_receive` 和 `app.ReceiverApp._run_capture` 都调它。

## 文件

### `capturer.py` — 固定区域截图（64 行）

| 符号 | 签名 | 说明 |
|---|---|---|
| `CaptureRegion` | `@dataclass(frozen)`: left, top, width, height | 屏幕坐标区域 |
| `CaptureRegion.as_mss_dict` | `() -> dict` | 转成 mss.grab 参数 |
| `CaptureRegion.from_string` | `(cls, s: str) -> CaptureRegion` *(classmethod)* | 解析 `"x,y,w,h"` |
| `ScreenCapturer` | 类 | 延迟 import mss，线程安全 |
| `ScreenCapturer.capture` | `() -> PIL.Image` | mss.grab → `Image.frombytes("RGB", ..., "raw", "BGRX")` |
| `ScreenCapturer.close` | `() -> None` | 关闭 mss 句柄 |

### `decoder.py` — QR 解码（81 行）

| 符号 | 签名 | 说明 |
|---|---|---|
| `decode_qr` | `(image) -> Optional[str]` | **首选 pyzbar**，失败回退 opencv。返回 QR 内容字符串或 None |
| `decode_qr_from_file` | `(path) -> Optional[str]` | 从图像文件（PPM/PNG/...）解码，先 `PIL.Image.open` |
| `_decode_with_pyzbar` | `(image) -> Optional[str]` | pyzbar.pyzbar.decode，取 `results[0].data` |
| `_decode_with_opencv` | `(image) -> Optional[str]` | cv2.QRCodeDetector 回退方案（pyzbar 不可用 / 失败时）|

> opencv 回退是 `feature_list.json` 的 `t3-opencv-decoder-fallback`，代码已存在但缺测试覆盖。

### `assembler.py` — 分片收集器（215 行，**核心**）

线程安全的分片去重/校验/排序/拼接。`capturer` 线程调 `add_raw/add_chunk`，主线程调 `get_progress/assemble`。

| 符号 | 签名 | 说明 |
|---|---|---|
| `AssemblyProgress` | `@dataclass`: file_id, total, manifest, received_indices(Set), conflicts(Dict), rejected_count | 只读进度视图 |
| `AssemblyProgress.missing_indices` | property `-> Set[int]` | `set(range(1,total+1)) - received_indices` |
| `AssemblyProgress.is_complete` | property `-> bool` | `total 和 manifest 都已知 且 received == total` |
| `AssemblyProgress.percent` | property `-> float` | `received_count / total * 100` |
| `ChunkAssembler` | 类 | 核心收集器，`__init__` 创建 `_lock = threading.Lock()` |
| `ChunkAssembler.add_raw` | `(raw: str) -> bool` | 解析+加入。True=新有效帧，False=重复/损坏/拒绝 |
| `ChunkAssembler.add_chunk` | `(chunk: Chunk) -> bool` | 加锁调 `_add_chunk_unlocked` |
| `ChunkAssembler.get_progress` | `() -> AssemblyProgress` | 加锁返回**深拷贝**快照（set/dict 都复制，调用方可任意用）|
| `ChunkAssembler.assemble` | `() -> bytes` | 加锁校验完整 → 排序 → 拼接 → `base64.b64decode` → 返回压缩字节 |
| `ChunkAssembler.reset` | `() -> None` | 清空，准备接新 file_id |

**CRC/冲突处理逻辑**（`_add_chunk_unlocked` / `_handle_data`）：
- `verify_crc()` 失败 → `rejected_count++`，丢弃
- 同 index 同 CRC → 静默丢弃（重复帧，返回 False）
- 同 index 不同 CRC → 记入 `conflicts[index]`，丢弃（疑似传输损坏或 file_id 碰撞）
- `file_id` / `total` 与已收到的 manifest 不一致 → 拒绝

### `verifier.py` — 最终完整性校验（100 行）

| 符号 | 签名 | 说明 |
|---|---|---|
| `VerificationResult` | `@dataclass(frozen)`: success, byte_count_match, sha256_match, md5_match, utf8_valid, actual_bytes, actual_sha256, actual_md5, message | 每项检查结果 |
| `verify_restored_file` | `(data: bytes, manifest: FileManifest, expected_sha256=None, expected_md5=None, expected_bytes=None) -> VerificationResult` | 全量校验，**不短路** |

校验顺序：字节数 → SHA-256 → MD5（若 manifest 或 CLI 提供）→ UTF-8 严格解码。`expected_*` 参数（CLI `--expected-*`）优先于 manifest 值，用于「接收方预先知道期望哈希」的场景。

### `runner.py` — 接收端主循环（99 行）

| 符号 | 签名 | 说明 |
|---|---|---|
| `run_receiver` | `(region, output_path, interval_ms=500, expected_sha256/md5/bytes=None, on_progress=None, on_complete=None, timeout_sec=None, stop_event=None) -> VerificationResult` | **接收端唯一主循环** |

循环逻辑（`runner.py:49`）：
```
while True:
    if stop_event.is_set(): break        # GUI 停止按钮
    if 超时: raise TimeoutError
    img = capturer.capture()             # 截图失败则 sleep 重试
    decoded = decode_qr(img)
    if decoded 且 assembler.add_raw(decoded) 是新帧:
        on_progress(progress)            # 更新进度条
        if progress.is_complete: break
    sleep(interval_ms)
# 循环退出后：
compressed = assembler.assemble()
restored = decompress_payload(compressed, manifest.compression)
result = verify_restored_file(restored, manifest, ...)
if result.success: output_path.write_bytes(restored)
on_complete(result, output_path)
return result
```

`stop_event`（`threading.Event`）让 GUI 的「停止」按钮能中断主循环。

### `region_selector.py` — 跨屏拖拽框选（428 行）

GUI 全屏区域选择器，**支持多显示器/双屏**。

| 符号 | 说明 |
|---|---|
| `_check_tkinter()` | tkinter 缺失时抛带安装指引的 ImportError |
| `_MonitorOverlay` | 单个物理显示器的全屏覆盖层：暗化背景 + 拖拽框选 + 聚光灯（选区内显示亮版）+ 坐标换算到虚拟桌面绝对坐标 |
| `RegionSelector` | 跨屏选择器主类 |
| `RegionSelector.__init__` | `(master=None)` —— master=None 时自建 Tk root；非 None 时**嵌入已有 root**（GUI app 共用）|
| `RegionSelector.select` | `() -> Optional[CaptureRegion]` | 截虚拟桌面 → 枚举显示器 → 每屏建 overlay → mainloop。返回选区或 None（取消）|
| `select_region()` | `() -> Optional[CaptureRegion]` | 便捷封装（自建 root）|

**多屏关键设计**：截整个虚拟桌面（`mss.monitors[0]`）为每个物理屏（`monitors[1:]`）建覆盖层；拖拽坐标用 `_local_to_abs`（`mon.left + lx`）换算成虚拟桌面绝对坐标，保证选区在副屏时 `capturer` 也能抓到正确区域。

### `app.py` — 接收端控制面板 GUI（439 行）

普通窗口（非全屏）的控制面板，按钮触发框选和后台接收。

| 符号 | 说明 |
|---|---|
| `ReceiverApp` | 主窗口类：输出文件/截图间隔/框选按钮/开始停止/进度条/日志区 |
| `ReceiverApp._on_select_region` | 嵌入 `RegionSelector(master=self.root)` 复用 Tk root |
| `ReceiverApp._on_start` / `_on_stop` | 启停后台 daemon 线程 |
| `ReceiverApp._run_capture` | 后台线程：调 `run_receiver`，把事件丢进 `queue.Queue` |
| `ReceiverApp._drain_queue` | 主线程 `root.after(100ms)` 轮询队列更新 UI |
| `launch()` | `() -> int` 启动 GUI，返回退出码 |

**线程模型（重要）**：tkinter 非线程安全，后台线程**绝不直接触碰 widget**。事件类型 `_EV_PROGRESS` / `_EV_COMPLETE` / `_EV_ERROR` / `_EV_LOG` 通过 `queue.Queue` 传递，主线程轮询消费。

## GUI 职责边界（region_selector vs app.py）

| 组件 | 职责 | 窗口形态 |
|---|---|---|
| `region_selector.RegionSelector` | **一次性**全屏框选，返回 `CaptureRegion` 后立即销毁 | 全屏覆盖层（每屏一个），选完即退 |
| `app.ReceiverApp` | **常驻**控制面板，编排框选+接收+进度+日志 | 普通窗口，mainloop 直到关闭 |

`app` 通过 `RegionSelector(master=self.root)` 嵌入复用 Tk root（避免多 mainloop 冲突），框选时 `root.withdraw()` 隐藏面板，框选完 `root.deiconify()` 恢复。

## 依赖

| 依赖 | 性质 | 用在哪 |
|---|---|---|
| `pyzbar` (+ 系统 libzbar) | C 绑定 | `decoder.py` 主解码 |
| `opencv-python` (cv2) | 可选 | `decoder.py` 回退解码 |
| `mss` | C 扩展 | `capturer.py` 截图 + `region_selector.py` 框选背景 |
| `Pillow` | C 扩展 | `capturer.py` Image + `region_selector.py` 暗化/裁剪 + `decoder.py` 开图 |
| `tkinter` | stdlib | `region_selector.py` + `app.py` GUI |
| `sqr.protocol` | 共用层 | `assembler.py` Chunk/FileManifest |
| `sqr.sender.compressor` | 跨层调用 | `runner.py` 调 `decompress_payload`（解压逻辑成对放在 compressor.py）|

## 上游调用方

- `sqr/cli.py:cmd_receive` —— CLI 入口，直接调 `run_receiver`，进度通过 `on_progress` 回调打印进度条
- `sqr/cli.py:cmd_gui` → `app.launch()` —— GUI 入口，控制面板 + 后台线程
