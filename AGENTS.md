# AGENTS.md — sqr 项目协作约定

> 本文件是任何在本仓库工作的 Agent（Claude / Codex / 其他）的入口约定。
> 开始任何任务前，先完整阅读本文档。

---

## 1. 项目简介

**sqr（Screen QR Transfer）** 是一个通过屏幕二维码序列实现**内网 → 外网单向文件传输**的工具。

### 1.1 解决的问题

内网机器**无网络、无 USB、无共享目录、无剪贴板**，唯一对外通道是"外网可以看见内网屏幕"。sqr 把屏幕当作单向光学通道：内网循环播放二维码，外网截图解码还原文件。

### 1.2 架构

```
内网发送端（零安装）                外网接收端
┌──────────────────────┐          ┌──────────────────────┐
│ 文件 → gzip/b64      │  屏幕 QR │ mss 截图 → pyzbar     │
│ → 分片 + CRC32       │ ───────→ │ → 去重/排序/校验       │
│ → QR matrix 渲染      │          │ → b64 解码 → gunzip    │
│ (tkinter/PPM/Unicode) │          │ → SHA-256/MD5 校验     │
└──────────────────────┘          └──────────────────────┘
纯 stdlib + vendor qrcode          pyzbar + mss + Pillow
```

### 1.3 关键技术决策

1. **去 Pillow 化**：发送端用 PIL stub 绕过 qrcode 对 PIL 的导入依赖，实现纯 stdlib + vendor 零安装。
2. **SQ1 协议**：`SQ1|<file_id>|<index>|<total>|<crc32:08x>|<payload>`，index=0 为 manifest 帧（含文件名/SHA-256/MD5/总字节）。
3. **三种 QR 渲染器**：tkinter Canvas（屏幕）、PPM P6（测试/调试）、Unicode half-blocks（终端后备）。
4. **线程安全组装器**：`ChunkAssembler` 用 `threading.Lock` 保护，支持接收端循环并发写入。

### 1.4 当前状态

- **Phase 1–6 全部完成**（协议核心 / vendor / 接收端管线 / 屏幕 I/O / 打包 / GUI 区域选择器）。
- 测试：`92 passed`。
- 发送端打包产物：`dist/sqr-sender-src.zip`（~45KB，解压后 `./send.sh <file>`；send.sh 启动前自检 Python/tkinter/vendor，缺失时友好报错而非 traceback）。
- 详细进度见 `claude-progress.md`「当前已验证状态」+「待办清单」，完整设计见 `implementation-plan.md`，原始方案见 `screen-qr-transfer.md`。

### 1.5 运行入口

```bash
# 一次性环境准备（安装依赖 + 跑测试 + 进入启动菜单）
./init.sh
# 启动菜单子命令（都先走 install + verify 再 exec）：
#   ./init.sh receive [...]         # 接收端 GUI 框选模式（默认行为）
#   ./init.sh send <file> [...]     # 发送端（<file> 是位置参数，不是 --file）
#   ./init.sh gui                   # 接收端控制面板（sqr.receiver.app）
#   ./init.sh help                  # 快速路径，直接打印 sqr CLI help
#   ./init.sh test [pytest args...] # 快速路径，只跑测试（跳过 install/launch），参数透传给 pytest
#   ./init.sh install               # 快速路径，全自动安装接收端环境（.venv + pip + libzbar），装完退出
# 或 RUN_START_COMMAND=1 ./init.sh 直接执行 START_CMD

# 直接调 sqr.cli（跳过 install/verify）：
python3 -m sqr.cli send <file>                    # 发送端（内网）
python3 -m sqr.cli receive --output out.txt       # 接收端（外网，默认 GUI 框选）
python3 -m sqr.cli gui                            # 接收端控制面板

# 解压打包产物用：
unzip dist/sqr-sender-src.zip && ./sqr-sender/send.sh <file>

# 测试（per-session 轻量验证，跳过 pip install）
python3 -m pytest tests/ -q
```

> macOS 首次运行需先 `brew install zbar`（pyzbar 后端），不在 `init.sh` 职责内。

---

## 2. 开工流程

**写代码前先按顺序做这些事：**

1. **确认目录**：`pwd` 确认在仓库根目录 `out-from-vm/`。
2. **读取会话日志**：读 `claude-progress.md`，了解「当前已验证状态」「待办清单」、最近一轮的 Session 记录、blocker、下一步建议。
3. **读取功能清单**：读 `feature_list.json`，确认 `in_progress_id` 为 `null`（上一轮应已归位）；从中选一个 `not_started` 或 `blocked` 的 feature 作为本轮目标。
4. **读取设计**：若改动涉及协议/架构，读 `implementation-plan.md` 对应章节。
5. **查看最近提交**：`git log --oneline -10`，了解最近变更。
6. **运行验证基线**：`python3 -m pytest tests/ -q` 必须全绿，确认仓库处于干净可工作状态。
7. **锁定目标**：把选中的 feature 在 `feature_list.json` 中改 `status: "in_progress"` 并设顶层 `in_progress_id`；在 `claude-progress.md` 「会话记录」开新 Session 条目记下"本轮目标"。

> ⚠️ **同一时间只能有一个 feature 处于 `in_progress`**（见 `feature_list.json` 顶部 `_comment`）。
>
> ⚠️ 若第 6 步失败：**不要开始新功能**。先修复回归，或在 `claude-progress.md` 当前 Session 条目记录失败现象后再继续。

---

## 3. 工作规则

1. **一次只做一个功能**——本次会话只推进一个待办项，不并行多 features。
2. **不要因为"代码已经写了"就把功能标记为完成**——必须跑完验证（见 §5 完成定义）。
3. **不扩大范围**——除非为消除当前 blocker 的窄范围修复，否则不要扩散到其他功能。
4. **不悄悄改弱验证规则**——禁止放宽 CRC32、放宽 SHA-256、跳过失败用例、把 `assert` 改成警告、删除失败测试。任何验证规则的变更必须在 `claude-progress.md` 当前 Session 条目显式记录理由。
5. **优先依赖仓库里的持久化文件，而不是聊天记录**——`claude-progress.md` / `implementation-plan.md` / `screen-qr-transfer.md` 是事实来源，会话记忆不是。

---

## 4. 必需文件

本仓库的事实来源文件：

| 文件 | 角色 | 当前状态 |
|------|------|---------|
| `claude-progress.md` | **项目状态单一事实来源**：当前已验证状态 + 待办清单 + 会话日志 | ✅ 已存在，每轮会话必须更新 |
| `implementation-plan.md` | 完整实施设计文档（v2，1334 行） | ✅ 只读参考 |
| `screen-qr-transfer.md` | 原始方案文档 | ✅ 只读参考 |
| `conftest.py` | pytest 配置，保证 `sqr` 包可从项目根导入 | ✅ 已存在 |
| `feature_list.json` | **机器可读的功能清单（功能状态单一事实来源）**：每个 feature 有 id / priority / area / status / verification / evidence | ✅ 已存在，状态变更时更新 |
| `init.sh` | 统一启动与验证入口（安装依赖 + 跑测试 + 打印启动命令） | ✅ 已存在，fresh setup / CI 用 |


> 若决定引入 `feature_list.json` / `init.sh` / `session-handoff.md`，请先在 `claude-progress.md` 当前 Session 条目登记决定。

---

## 5. 完成定义

**一个功能只有在以下条件全部满足时才算完成：**

1. ✅ **目标行为已经实现**——按 `implementation-plan.md` 对应章节的接口契约。
2. ✅ **要求的验证真的跑过**——`python3 -m pytest tests/ -q` 全绿，且本次改动涉及的测试文件单独跑也全绿。
3. ✅ **证据记录在 `claude-progress.md`**——更新「当前已验证状态」「待办清单」「测试覆盖」相关字段，并在当前 Session 条目写明日期与变更点。
4. ✅ **仓库仍然能按标准启动路径重新开始工作**——下一轮会话 `pwd` + 读 `claude-progress.md` + `pytest tests/ -q` 即可恢复完整上下文。

任何一项未满足，功能状态必须保持「未完成」。

---

## 6. 结束会话前

**按顺序执行收尾清单：**

1. **更新 `claude-progress.md`**——把当前 Session 条目填完（已完成 / 验证 / 提交 / 文件 / 风险 / 下一步），并按需刷新顶部「当前已验证状态」「待办清单」「测试覆盖」。
2. **更新 `feature_list.json`**——把本轮 feature 的 `status` 从 `in_progress` 改为 `passing`（验证通过）或 `not_started` / `blocked`（未完成）；填写 `evidence` 字段；**把顶层 `in_progress_id` 归位为 `null`**。
3. **记录未解决的风险或 blocker**——在 `claude-progress.md` 当前 Session 条目下显式标注，不留模糊。
4. **跑一次完整验证**——`python3 -m pytest tests/ -q`，确认全绿。
5. **提交**——在工作处于安全状态（编译/测试/启动三通）后，用清晰的提交信息提交。提交信息应说明"做了什么 + 为什么 + 验证结果"，例如：
   > `feat(receiver): add GUI region selector (Phase 6) — 92 tests pass`
6. **保证下一轮可直接重启**——下一轮 Agent 执行 §2「开工流程」时，`in_progress_id` 应为 `null`，可立即接手。

---

## 附：快速参考

| 命令 | 用途 |
|------|------|
| `pwd` | 确认在 `out-from-vm/` 根目录 |
| `./init.sh` | 一次性环境准备 + 打印启动菜单（fresh setup / CI） |
| `./init.sh receive` | 安装 + 验证 + 启动接收端（默认 GUI 框选） |
| `./init.sh send <file>` | 安装 + 验证 + 启动发送端（`<file>` 位置参数） |
| `./init.sh gui` | 安装 + 验证 + 启动接收端控制面板 |
| `./init.sh help` | 快速路径，直接打印 sqr CLI help（跳过 install/verify） |
| `./init.sh test [args]` | 快速路径，只跑测试（跳过 install/launch，参数透传给 pytest） |
| `./init.sh install` | 快速路径，全自动安装接收端环境（.venv + pip + OS 检测装 libzbar），装完退出 |
| `python3 -m pytest tests/ -q` | 全量验证（应 92 passed；per-session 轻量复测） |
| `python3 -m pytest tests/test_<name>.py -q` | 单文件验证 |
| `git log --oneline -10` | 查看最近提交 |
| `git status` | 查看工作区状态 |
| `python3 -m sqr.cli send <file>` | 发送端启动（直接调，跳过 init.sh） |
| `python3 -m sqr.cli receive --output <path>` | 接收端启动（GUI 框选，直接调） |
