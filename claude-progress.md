# 进度日志

这是一个通用的仓库内会话进度日志。`claude-progress.md` 只是课程沿用的历史
文件名，并不要求使用 Claude Code。只要仓库里的指令明确要求，Codex 或其他
coding agent 都可以在开工时读取、交接前更新；agent 不会自动维护这个文件。

本文件是项目**会话级**事实来源：当前已验证状态快照 + 待办清单速览 + 会话日志。
**功能级**权威状态以 `feature_list.json` 为准（本文件「待办清单」是它的速览视图）。
完整设计见 `implementation-plan.md`，原始方案见 `screen-qr-transfer.md`。

---

## 当前已验证状态

- **仓库根目录**：`/Users/e2uninova-m4/Desktop/test_project/out-from-vm`
- **标准启动路径**：
  - 发送端：`python3 -m sqr.cli send --file <path>`
  - 接收端：`python3 -m sqr.cli receive --output <path>`（默认 GUI 框选）
  - 打包产物：`dist/sqr-sender-src.zip`（44 KB，解压后 `./send.sh <file>`）
- **标准验证路径**：`python3 -m pytest tests/ -q`（基线应为 **92 passed**）
- **Phase 完成情况**：Phase 1–6 **全部完成**
  - P1 协议核心（`sqr/protocol.py` / `sqr/sender/compressor.py` / `sqr/sender/chunker.py`）
  - P2 vendor + QR 渲染（`sqr/vendor/qrcode/` + `sqr/sender/qr_render.py`，PIL stub 实现 zero-install）
  - P3 接收端管线 + 端到端验证（`sqr/receiver/{decoder,assembler,verifier}.py` + `tests/test_roundtrip.py`）
  - P4 屏幕 I/O（`sqr/sender/player.py` / `sqr/receiver/{capturer,runner}.py` / `sqr/cli.py`）
  - P5 打包与启动器（`build/bundle_sender.py` + `launcher/`）
  - P6 GUI 区域选择器（`sqr/receiver/region_selector.py`）
  - 各 Phase 详细设计见 `implementation-plan.md` §4 + §14
- **测试覆盖**（基线 92 项）：

  | 测试文件 | 数量 | 覆盖范围 |
  |---|---|---|
  | `test_protocol.py` | ~30 | Chunk/Manifest 序列化、CRC32、异常路径 |
  | `test_compressor.py` | ~15 | gzip/zstd 压缩、Base64 编解码、边界值 |
  | `test_chunker.py` | ~18 | 分片、manifest 帧、build_all_frames |
  | `test_qr_render.py` | 19 | matrix 生成、PPM 导出、Unicode 渲染、vendor 加载 |
  | `test_roundtrip.py` | 10 | 文件→QR→解码→校验 端到端（3 fixture） |

- **当前最高优先级未完成功能**：**真实屏幕端到端验证**（VMware + 物理 QR 播放/截屏环境下跑完整 round-trip，校验 MD5 `fd3b2ff5b10c902575332e8bbdd616f9` 与字节数 29816）。
- **当前 blocker**：**环境 blocker，非代码 blocker**——需要可用的 VMware + 内网发送端屏幕 + 外网截图三件套；代码层面无 blocker。

---

## 待办清单

> 本表是 `feature_list.json` 中 `status != passing` 的 feature 的人眼速览视图。**权威状态、verification 步骤、evidence 以 `feature_list.json` 为准**。

| 项目 | 对应 feature_id | 状态 | 优先级 | 说明 |
|---|---|---|---|---|
| 真实屏幕端到端验证 | `t1-real-screen-e2e` | blocked | 10 | 需 VMware + 实际 QR 播放/截屏环境；项目验收（`screen-qr-transfer.md` §10）最后一公里 |
| Tier 2 PyInstaller 打包 | `t2-packaging-tier2` | not_started | 20 | `implementation-plan.md` §13.3 已规划，发送端单文件可执行程序 |
| opencv 解码后备 | `t3-opencv-decoder-fallback` | not_started | 30 | `sqr/receiver/decoder.py` 中 pyzbar 失败时的后备路径 |
| zstd 压缩 | `t4-zstd-compression` | not_started | 40 | `sqr/sender/compressor.py` 支持 zstd 但默认 gzip |
| 大文件传输 | `t5-large-file-transfer` | not_started | 40 | 目前 fixture 最大 ~10KB QR 序列 |

---

## 会话记录

### Session 001 — 基线建立

- **日期**：2026-08-11
- **本轮目标**：初始化 Agent 协作约定文档（`AGENTS.md` + `claude-progress.md`），建立 `claude-progress.md` 作为项目状态单一事实来源。
- **已完成**：
  1. 读 `implementation-plan.md` / `screen-qr-transfer.md` / `conftest.py` 摸清现状。
  2. 写 `AGENTS.md`：项目简介、开工流程、工作规则、必需文件、完成定义、结束会话前清单、快速参考表。
  3. 建 `claude-progress.md`：当前已验证状态 + 待办清单 + 会话记录。
  4. 把原 `PROCESS.md` 独有内容（Phase 完成状态、测试覆盖表、待办清单）迁入本文件后，**删除 `PROCESS.md`**，避免双事实来源。
  5. 建 `feature_list.json`（11 个 feature：6 passing / 1 blocked / 4 not_started，`in_progress_id: null`）；`AGENTS.md` §2/§4/§6 同步加入 feature 锁定/解锁流程。
  6. 写 `init.sh`（统一启动与验证入口）并**实跑通过**——确认基线 `92 passed in 2.05s`。`AGENTS.md` §1.5/§4/快速参考同步加入 init.sh。
  7. 给 `init.sh` 加子命令路由：`./init.sh { receive | send <file> | gui | help }`，全部实跑通过。**顺手修了 `AGENTS.md` §1.5 的错误**——send 实际是位置参数 `<file>`（cli.py:213），不是 `--file <path>`。
  8. **新发现**：仓库存在 `sqr/receiver/app.py`（15 KB）+ `gui` 子命令（cli.py:254-258），但**未在 PROCESS.md / implementation-plan.md / feature_list.json 中记录**。这块工作（接收端控制面板 GUI）下轮需要决定：补登进 feature_list.json 还是不认。
- **运行过的验证**：
  - `./init.sh` 实跑通过：`92 passed in 2.05s`（基线钉死，本轮真实复测）。
  - pip 安装：`Requirement already satisfied`（环境已齐）。
  - bash -n init.sh 语法检查通过。
- **已记录证据**：
  - 项目状态总览 → 本文件「当前已验证状态」+「待办清单」
  - Agent 入口约定 → `AGENTS.md`
  - 完整设计 → `implementation-plan.md`
  - 原始方案 → `screen-qr-transfer.md`
- **提交记录**：本轮工作**尚未提交**（按 `AGENTS.md` §3 工作规则，需用户显式批准才提交）。
- **更新过的文件或工件**：
  - `AGENTS.md`（新建内容，原文件 0 行）
  - `claude-progress.md`（新建）
  - `PROCESS.md`（**删除**）
  - `feature_list.json`（新建，11 个 feature）
  - `init.sh`（新建，可执行；本轮加子命令路由 receive/send/gui/help）
- **已知风险或未解决问题**：
  1. **`AGENTS.md` §4 标准模板剩余项**：仅 `session-handoff.md` 仍未采用（会话交接写在本文件「会话记录」）；如需引入再登记。
  2. **真实屏幕端到端验证**未做，是项目验收最后一公里（`feature_list.json` 中 `t1-real-screen-e2e` 处于 `blocked`）。
  3. **P4 / P6 仅手动验证**：`p4-screen-io` 和 `p6-gui-region-selector` 在 `feature_list.json` 标为 `passing` 但 evidence 注明"手动验证，无独立自动化测试"；下轮做 `t1` 时会顺带补强。
  4. **init.sh 未在干净环境验证**：本轮 `.venv` 与 libzbar 都已就位，未模拟"无 venv / 无 libzbar"场景；首次跑到陌生机器时可能需要补 `brew install zbar`。
  5. **`sqr/receiver/app.py` + `gui` 子命令未被 feature_list.json 收录**：仓库存在但 PROCESS.md（已删）/ implementation-plan.md / feature_list.json 都没记录这块工作。下轮开工前需要决定补登（建议加 `p7-gui-control-panel`）或维持未记录状态。
- **下一步最佳动作**（按优先级）：
  1. **开工第一件事**：跑 `python3 -m pytest tests/ -q`，复测 92 passed 基线。
  2. 若有 VMware 环境：推进"真实屏幕端到端验证"，更新本文件「待办清单」。
  3. 若无 VMware 环境：推进 Tier 2 PyInstaller 打包（`implementation-plan.md` §13.3）。
  4. 任何新功能开工前，先在本文档开 Session 002 条目，写明"本轮目标"。

### Session 002 — init.sh 加 test 子命令（一键启动测试）

- **日期**：2026-08-12
- **本轮目标**：为 `init.sh` 新增 `test` 子命令，实现"一键启动测试"——跳过 `pip install` 和启动步骤，直接跑 pytest，额外参数透传。
- **已完成**：
  1. `init.sh` 加 `test` 快速路径（模式参照 `help` 快速路径）：`./init.sh test [...]` → `shift` 掉子命令 → `exec python3 -m pytest "$@"`，参数透传给 pytest。
  2. **配套重构**：把 `.venv` 检测块从"help 快速路径之后"提前到"所有快速路径之前"，确保 `test`/`help` 快速路径也能复用 venv（原位置下 help 不需要 venv 所以无影响，但 test 需要 venv 里的包）。
  3. `init.sh` 顶部用法注释 + `case` 的 Usage 错误提示同步加 `test` 行。
  4. `AGENTS.md` §1.5 子命令列表 + 附录「快速参考」表同步加 `./init.sh test`。
- **运行过的验证**：
  - `bash -n init.sh` 语法检查通过。
  - `./init.sh test` 实跑：检测到 .venv，跳过 install/launch，直接跑 pytest → **92 passed in 1.96s**（基线钉死）。
  - `./init.sh test tests/test_protocol.py -q` 参数透传验证 → **34 passed**（确认指定文件 + `-q` 正确透传给 pytest）。
- **已记录证据**：无新增证据文件；本次是工具/基建改动，`feature_list.json` 不涉及（`in_progress_id` 保持 `null`，无 sqr feature 状态变更）。
- **提交记录**：本次工作**尚未提交**（按 `AGENTS.md` §3 工作规则，需用户显式批准）。
- **更新过的文件或工件**：
  - `init.sh`（加 test 快速路径 + .venv 检测前置 + 顶部注释 + Usage 提示）
  - `AGENTS.md`（§1.5 子命令列表 + 附录「快速参考」表）
  - `claude-progress.md`（本 Session 002 条目）
- **已知风险或未解决问题**：
  1. **无 .venv 场景未实测**：本次只验证了 `.venv` 存在场景；无 `.venv` 时 test 快速路径会回退到系统 `python3`，未在无 venv 环境实测（逻辑上与原主流水线一致）。
  2. **test 快速路径跳过 pip install**：若环境依赖缺失会直接 `ModuleNotFoundError`；这是设计取舍（频繁测试不重复装依赖），用户应先跑一次完整 `./init.sh` 装好依赖后再用 `./init.sh test`。
- **下一步最佳动作**：
  1. 按需提交本次 `init.sh` + `AGENTS.md` + `claude-progress.md` 改动（需用户批准）。
  2. 推进 `feature_list.json` 待办：`t1` 真实屏幕 e2e（需 VMware）或 `t2` PyInstaller 打包（无环境依赖，可立即开工）。

### Session 003 — init.sh install 子命令 + 发送端部署包自检

- **日期**：2026-08-12
- **本轮目标**：让 `init.sh` 支持接收端一键全自动安装（.venv + pip + 系统级 libzbar），并增强内网发送端部署包（send.sh/send.bat）的启动前环境自检。
- **已完成**：
  1. `init.sh` 新增 `install` 快速路径（装完退出，不启动）：[1/4] 创建/复用 .venv → [2/4] `pip install --upgrade pip` + requirements-test.txt → [3/4] 检测 pyzbar 能否导入，失败则调 `install_libzbar` 按 OS 分发（macOS brew / Debian apt-get / Fedora dnf / Alpine apk，Linux 需 sudo）→ [4/4] 验证 pyzbar+mss+PIL 全部可导入。
  2. `init.sh` 新增 `install_libzbar()` 函数：`uname -s` 分发到对应包管理器，不支持的平台打印手动安装指引。
  3. `launcher/send.sh` 重写：加 `set -euo pipefail` + 启动前自检（Python 存在 + 版本≥3.6 + tkinter 可 import + vendor qrcode 可 import），任一失败友好报错 exit 1，不进 cli.py。自检脚本用 `.format()` 兼容老版本 Python（不用 f-string，避免老 Python SyntaxError）。
  4. `launcher/send.bat` 重写：Windows 版三段 `python -c` 自检（版本/tkinter/vendor）。
  5. **修了一个 bash 变量边界 bug**：`$PYTHON` 后紧跟中文句号「。」，macOS bash 3.2 把 UTF-8 后续字节吞进变量名导致 `PYTHON\xxx: unbound variable`；改用 `${PYTHON}` 显式界定修复。
  6. `build/bundle_sender.py` 重新打包确认：`dist/sqr-sender-src.zip` 44KB→45KB（带新 send.sh 自检代码），vendor 24 个 py 文件。
  7. `AGENTS.md` 同步：§1.4 打包产物描述（+自检说明）+ §1.5 子命令列表加 install + 附录快速参考表加 install。
- **运行过的验证**：
  - `bash -n init.sh` + `bash -n launcher/send.sh` 语法检查通过。
  - `./init.sh install` 实跑（macOS 幂等）：.venv 复用 → pip 升级 26.1.2→26.2.1 + 依赖 already satisfied → libzbar 已就位跳过 → 验证 "receiver deps OK" + "接收端环境就绪"。
  - `PYTHON=/nonexistent/python ./launcher/send.sh --help` → exit 1 + 友好消息「✗ 未找到 /nonexistent/python。发送端需要 Python 3.6+。」（Python 缺失分支）。
  - `./dist/sqr-sender/send.sh --help` → 「✓ 环境自检通过」+ cli `send --help` 正常打印 usage（打包产物完整自检+exec）。
  - `python3 build/bundle_sender.py` → 打包成功，45KB。
- **已记录证据**：无新增证据文件；本次是工具/基建增强，`feature_list.json` 不涉及（`in_progress_id` 保持 `null`）。
- **提交记录**：本次工作**尚未提交**（按 `AGENTS.md` §3，需用户显式批准）。
- **更新过的文件或工件**：
  - `init.sh`（install 快速路径 + install_libzbar 函数）
  - `launcher/send.sh`（启动前自检 + set -euo pipefail + ${PYTHON} 边界修复）
  - `launcher/send.bat`（启动前自检 Windows 版）
  - `dist/sqr-sender-src.zip`（重新打包，45KB）+ `dist/sqr-sender/`（staging 目录）
  - `AGENTS.md`（§1.4 + §1.5 + 附录快速参考表）
  - `claude-progress.md`（本 Session 003 条目）
- **已知风险或未解决问题**：
  1. **send.bat 未实跑验证**：macOS 无法跑 Windows 批处理，仅逻辑审查（结构同 send.sh，`python -c` 三段检测）。
  2. **install 的 Linux libzbar 分支未实跑**：macOS 测时 libzbar 已装（跳过自动安装）；apt-get/dnf/apk + sudo 分支仅逻辑审查。
  3. **pip 被 install 子命令升级**：`./init.sh install` 会 `pip install --upgrade pip`，本次把 .venv 的 pip 从 26.1.2 升到 26.2.1（全自动的预期行为，但改变了 venv 状态）。
  4. **install 自动创建 .venv 改变项目运行方式**：此前 .venv 需手动创建，现在 install 自动建；已有 .venv 的环境幂等复用不受影响。
- **下一步最佳动作**：
  1. 按需提交本次所有改动（init.sh + launcher/ + AGENTS.md + claude-progress.md + dist/）。
  2. 推进 `feature_list.json` 待办：`t1` 真实屏幕 e2e（需 VMware）或 `t2` PyInstaller 打包。
