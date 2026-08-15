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
- **Git 仓库**：独立 git repo（remote `origin` → `https://github.com/biggeryounger/out-from-vm.git`，分支 `main`，首次提交 `ed65481`，72 files / 11927 insertions）
- **标准启动路径**：
  - 发送端：`python3 -m sqr.cli send <file-or-directory>`（默认写 cycle HTML 到 `sqr_sender.html`，浏览器打开即播）
  - 接收端（屏幕）：`python3 -m sqr.cli receive --output <path>`（文件时为输出文件；目录包时为输出父目录）
  - 接收端（image 批量）：`python3 -m sqr.cli decode --images <dir> --output <path>`（扫描目录 PPM/PNG/JPG 批量解码；自动写文件或安全还原目录）
  - 打包产物：`dist/sqr-sender-src.zip`（约 58 KB，解压后 `./send.sh <file-or-directory>`）
- **标准验证路径**：`python3 -m pytest tests/ -q`（当前基线 **176 passed**）
- **Phase 完成情况**：Phase 1–6 **全部完成**
  - P1 协议核心（`sqr/protocol.py` / `sqr/sender/compressor.py` / `sqr/sender/chunker.py`）
  - P2 vendor + QR 渲染（`sqr/vendor/qrcode/` + `sqr/sender/qr_render.py`，PIL stub 实现 zero-install）
  - P3 接收端管线 + 端到端验证（`sqr/receiver/{decoder,assembler,verifier}.py` + `tests/test_roundtrip.py`）
  - P4 屏幕 I/O（`sqr/receiver/{capturer,runner}.py` / `sqr/cli.py`；~~`sqr/sender/player.py`~~ 已于 t7 删除，tkinter 弹窗改为 cycle HTML）
  - P5 打包与启动器（`build/bundle_sender.py` + `launcher/`）
  - P6 GUI 区域选择器（`sqr/receiver/region_selector.py`）
  - 各 Phase 详细设计见 `implementation-plan.md` §4 + §14
- **测试覆盖**（当前 176 项）：

  | 测试文件 | 数量 | 覆盖范围 |
  |---|---|---|
  | `test_protocol.py` | ~30 | Chunk/Manifest 序列化、CRC32、异常路径 |
  | `test_compressor.py` | ~15 | gzip/zstd 压缩、Base64 编解码、边界值 |
  | `test_chunker.py` | ~18 | 分片、manifest 帧、build_all_frames |
  | `test_qr_render.py` | 53 | matrix 生成、PPM 导出、Unicode 渲染、vendor 加载、**HTML 网格/分页（t6 +22）、cycle 全屏布局（t7 +7）、grid Auto 逐张播放舞台（t8 +5）** |
  | `test_decoder.py` | 12 | **decode_qr_multi 多码解码 + decode_qr 向后兼容（t6 新增）** |
  | `test_image_decoder.py` | 8 | **run_receiver_from_images：round-trip + 顺序无关 + manifest/数据帧缺失 + 回调（t9 新增）** |
  | `test_roundtrip.py` | 10 | 文件→QR→解码→校验 端到端（3 fixture） |
  | `test_sender_bundle_compat.py` | 5 | Python 3.6 语法、无新式 typing 运行时依赖、启动器无 tkinter、优先内网 Python 3.9 |
  | `test_bundle.py` | 13 | 目录确定性封装、安全解包、正则筛选、Unicode/二进制/空目录、路径穿越/篡改拒绝 |
  | `test_directory_roundtrip.py` | 3 | 目录→SQ1 QR image→解码→安全还原端到端、正则筛选 round-trip、损坏整包不发布 |
  | `test_receiver_app.py` | 2 | GUI 目录包保存父目录选择、取消不改输出路径（无 Tk 窗口 helper 测试） |
  | `test_bundle_symlinks.py` | 3 | 内部软链接文件/目录跳过且不泄漏目标、根目录软链接拒绝、正则不纳入软链接 |

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
| HTML 网格 + 分页 + 多码解码 | `t6-html-grid-mode` | passing | 15 | 方案 B：静态 HTML 网格（SVG）+ 自动分页 + Prev/Next/Auto（Auto 默认关）+ 接收端 decode_qr_multi — 133 passed |
| HTML 循环播放 + 移除 tkinter | `t7-html-cycle-replace-tkinter` | passing | 15 | cycle 布局（全屏单 QR 自动循环，Auto:ON）+ 默认 send 写 sqr_sender.html + 彻底删除 player.py — 133 passed |
| grid Auto 改逐张全屏播放 | `t8-grid-auto-per-frame` | passing | 15 | grid 模式 Auto ON → 进 player-stage 全屏单张逐帧轮播（原为整页翻）；Auto OFF 回 grid 多张概览；cycle 零回归（playMode=page）— 138 passed |
| 接收端 image 批量解码 | `t9-decode-from-images` | passing | 15 | `sqr decode --images <dir> [--image <f>...] --output <path>` 扫描二维码 image 批量 pyzbar 解码 → 组装 → 还原；复用 assembler/verifier 不动 runner.py — 146 passed |
| 目录信息包传输 | `t11-directory-bundle-transfer` | passing | 15 | 保留指定根目录、嵌套结构、普通/二进制/空文件和空目录；整包 + 逐文件 SHA-256；安全临时解包后原子发布 — 166 passed |
| 目录文件名正则筛选 | `t12-directory-filename-regex-filter` | passing | 15 | 可重复 `--include-regex`；basename `re.search`、多个 OR，只保留匹配文件及必要祖先目录 — 171 passed |
| GUI 目录包保存目录 | `t13-gui-directory-output-picker` | passing | 10 | 输出区提供“选择文件…”/“选择目录…”；目录包选父目录，完成后显示实际根目录 — 173 passed |
| 目录内部软链接排除 | `t14-skip-internal-symlinks` | passing | 10 | 内部软链接文件/目录不跟随并跳过，显示计数；根目录软链接仍拒绝 — 176 passed |

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

### Session 004 — 架构文档 + 首次提交推送 GitHub

- **日期**：2026-08-12
- **本轮目标**：为整个 sqr 项目编写架构文档（顶层 + 各模块 ARCHITECTURE.md），然后做首次 git 提交并推送到 GitHub。
- **已完成**：
  1. **读取全部 11 个模块源文件**（protocol.py / cli.py / sender/{compressor,chunker,qr_render,player}.py / receiver/{capturer,decoder,assembler,verifier,runner,region_selector,app}.py / vendor/__init__.py）+ implementation-plan.md §1-3，为写文档建立事实基础。（注：派出的两个 explore agent `bg_ca4acf07`/`bg_3eefb200` 均卡死无输出，已 cancel，改为直接读文件。）
  2. **写 4 份架构文档**：
     - `ARCHITECTURE.md`（项目根）：整体架构图 + 分层设计 + SQ1 协议详解 + 关键技术决策（去 Pillow 化 / 循环播放 / 线程安全 / GUI 线程模型）+ 依赖矩阵 + 目录结构 + 入口点 + 模块文档导航。
     - `sqr/sender/ARCHITECTURE.md`：发送端管线 compressor→chunker→qr_render→player，完整函数签名 + 数据流 + 三种渲染器对比。
     - `sqr/receiver/ARCHITECTURE.md`：接收端管线 capturer→decoder→assembler→verifier→runner + GUI 边界（region_selector/app），线程安全模型，完整函数签名。
     - `sqr/vendor/ARCHITECTURE.md`：PIL stub 机制 + sys.path bootstrap 顺序约束 + vendor 边界（勿改规则）。
  3. **Git 初始化**：`git init -b main`（out-from-vm/ 成为独立 git repo，嵌套在父级 test_project/ gitee 仓库内）；写 `.gitignore`（排除 `.venv/` / `__pycache__/` / `dist/sqr-sender/` staging 目录 / `.omo/`）；`git remote add origin https://github.com/biggeryounger/out-from-vm.git`（用户提前建好的空 PUBLIC 仓库）。
  4. **首次提交 + 推送**：`git add -A`（72 files）→ `git commit`（commit `ed65481`，"Initial commit: sqr (Screen QR Transfer)"）→ `gh auth setup-git` → `git push -u origin main`。**Session 001/002/003 的全部工作 + 本次架构文档全部包含在此首次提交中**。
- **运行过的验证**：
  - `python3 -m pytest tests/ -q` → **92 passed in 2.04s**（确认文档变更未影响代码，基线钉死）。
  - `git push -u origin main` → `* [new branch] main -> main`（推送成功，GitHub 远端可见）。
  - `glob **/ARCHITECTURE.md` → 4 个文件确认就位（根 + sender/receiver/vendor）。
- **已记录证据**：无新增证据文件；本次是文档 + git 基建，`feature_list.json` 不涉及（`in_progress_id` 保持 `null`，无 sqr feature 状态变更）。
- **提交记录**：✅ **已提交并推送** —— commit `ed65481` on `main`，remote `origin` → `https://github.com/biggeryounger/out-from-vm.git`。Session 001/002/003 未提交的工作一并归入此首次提交。
- **更新过的文件或工件**：
  - `ARCHITECTURE.md`（新建，项目根顶层架构文档）
  - `sqr/sender/ARCHITECTURE.md`（新建）
  - `sqr/receiver/ARCHITECTURE.md`（新建）
  - `sqr/vendor/ARCHITECTURE.md`（新建）
  - `.gitignore`（新建）
  - `claude-progress.md`（本 Session 004 条目 + 顶部「当前已验证状态」加 Git 仓库信息）
- **已知风险或未解决问题**：
  1. **架构文档基于当前代码快照**：文档里的函数签名是本轮读取时的状态，后续代码演进需同步更新对应 ARCHITECTURE.md（建议纳入 AGENTS.md 工作流，但本轮不改 AGENTS.md）。
  2. **out-from-vm 嵌套 git repo**：out-from-vm/ 现在是独立 git repo，与父级 test_project/ 的 gitee 仓库形成嵌套；父级仓库的 .gitignore 应排除 out-from-vm/ 否则 git 会当作 submodule 或忽略其内部变更。
- **下一步最佳动作**：
  1. 推进 `feature_list.json` 待办：`t1` 真实屏幕 e2e（需 VMware）或 `t2` PyInstaller 打包（无环境依赖，可立即开工）。
  2. 后续代码变更时同步更新对应模块的 ARCHITECTURE.md。

### Session 005 — HTML 网格渲染器 + 分页 + 接收端多码解码（t6-html-grid-mode）

- **日期**：2026-08-12
- **本轮目标**：新增 HTML 网格呈现模式（方案 B）：发送端把所有 QR chunk 渲染成静态 HTML 网格（inline SVG），自动分页 + Prev/Next/Auto 按钮（Auto 默认关）；接收端支持一帧多码解码（pyzbar 多码 + opencv detectAndDecodeMulti 回退）。消除频闪模式的不稳定性，并支持大文件分页。SQ1 协议不变。
- **背景决策**：用户在方案评估中选定 B（网格静态）；分页要求本期完成；Auto 轮播默认关（手动 Next）。频闪模式的"错乱"风险原本已由 CRC32 + SHA-256 + 循环补采兜底，网格模式从根上消除页内频闪。
- **已完成**：
  1. TDD：先写测试（test_qr_render.py 加 `TestMatricesToHtmlGrid` 22 项；新建 test_decoder.py 12 项），确认红（ImportError），再实现转绿。
  2. `sqr/sender/qr_render.py`：加 `matrices_to_html_grid()`（渲染器 D）+ 私有助手 `_matrix_to_svg()` / `_build_grid_js()`。每个 QRMatrix → inline SVG（viewBox 含 quiet zone），CSS grid 排列，按 `cols×rows_per_page` 自动分页（`<section class="qr-page">`），Prev/Next/Auto 按钮 + 页码指示；Auto 默认关（`var autoCycle = false;` + 按钮 `Auto: OFF`）。
  3. `sqr/receiver/decoder.py`：加 `decode_qr_multi()`（pyzbar 多码 + opencv `detectAndDecodeMulti` 回退）+ `_decode_multi_pyzbar()` / `_decode_multi_opencv()`。**保留** `decode_qr` 单码路径不变（零回归）。
  4. `sqr/receiver/runner.py`：主循环 `decode_qr(img)` → `decode_qr_multi(img)`，遍历 list 逐个 `add_raw`；`progress.is_complete` 双层 break（内层 for + 外层 while）。
  5. `sqr/cli.py`：send 加 4 个标志 `--html-grid <path>` / `--grid-cols` / `--page-rows` / `--page-interval`；`cmd_send` 在 matrices 构建后插入 HTML 网格分支（生成 .html 写盘后 return 0，不启 tkinter player）。
- **运行过的验证**：
  - `python3 -m pytest tests/ -q` → **126 passed in 2.64s**（基线 92 + 新增 34：test_qr_render 41 项含 +22 网格/分页，test_decoder 12 项多码）。
  - `python3 -m pytest tests/test_qr_render.py -q` → 41 passed；`tests/test_decoder.py -q` → 12 passed（AGENTS.md §5 改动文件单独跑全绿）。
  - 烟雾测试（实跑 CLI）：`sample_mid.txt`（5293B → 3 frames → 3 SVG / 1 页）；`/tmp/big.txt`（51KB 随机 sha256 → 35 frames → 35 SVG / 3 页 ceil(35/16)，Auto: OFF / autoCycle=false / Prev/Next 按钮齐备）。
- **已记录证据**：无新增证据文件；验证结果见本 Session「运行过的验证」+ feature_list.json `t6-html-grid-mode.evidence`。
- **提交记录**：本轮工作**尚未提交**（按 AGENTS.md §3，需用户显式批准）。
- **更新过的文件或工件**：
  - `sqr/sender/qr_render.py`（渲染器 D + 助手，~150 行新增）
  - `sqr/receiver/decoder.py`（decode_qr_multi + 2 助手，~50 行新增）
  - `sqr/receiver/runner.py`（主循环改多码，import 改）
  - `sqr/cli.py`（4 个 CLI 标志 + HTML 网格分支）
  - `tests/test_qr_render.py`（TestMatricesToHtmlGrid 22 项 + import）
  - `tests/test_decoder.py`（新建，12 项）
  - `feature_list.json`（t6 in_progress → passing，in_progress_id 归位 null）
  - `claude-progress.md`（本 Session 005 + 待办清单 + 当前已验证状态）
- **已知风险或未解决问题**：
  1. **真实屏幕 round-trip 未做**：接收端多码解码靠单元测试（mock pyzbar）证明逻辑正确，但未在真实"网格 HTML 浏览器全屏 + mss 截图 + pyzbar 多码"物理链路上验证（依赖 t1 的 VMware 环境）。网格 QR 间距是否足够 pyzbar 分离，需真实环境确认。
  2. **网格密度 vs 可解码性**：默认 4×4=16/页，每个 QR 在屏幕上的物理尺寸取决于屏幕分辨率。若 QR 太小截屏后 pyzbar 可能解码失败——用户需用 `--grid-cols`/`--page-rows` 调小每页密度。已知约束，非 bug。
  3. **opencv detectAndDecodeMulti 版本依赖**：需 opencv-python ≥4.3；旧版本走 except 返回 []（pyzbar 路径仍可用）。
  4. **--no-player 与 --html-grid 冲突**：同时传时 --no-player 在 line 76 早退，HTML 不会生成。--html-grid 单独用即可（自带 return 0）。未做冲突保护（用户错误，非关键）。
- **下一步最佳动作**：
  1. 按需提交本次所有改动（需用户批准）。
  2. 若有 VMware 环境：把 t6 网格 HTML 放进真实屏幕 round-trip 验证（同时推进 t1）。
  3. 同步更新 `sqr/sender/ARCHITECTURE.md`（加渲染器 D）+ `sqr/receiver/ARCHITECTURE.md`（加 decode_qr_multi）——Session 004 立的规矩"代码演进同步更新 ARCHITECTURE.md"。

### Session 006 — HTML 循环播放模式 + 移除 tkinter（t7-html-cycle-replace-tkinter）

- **日期**：2026-08-12
- **本轮目标**：在 t6 网格 HTML 基础上，新增 `layout="cycle"` 全屏单 QR 自动循环布局；默认 `send <file>` 行为从「tkinter 弹窗循环播放」改为「写 cycle HTML 到 `sqr_sender.html`」；彻底删除 `sqr/sender/player.py`（tkinter player）+ cli.py 中所有 tkinter 引用 + `--renderer tkinter` / `--no-player` 标志。不自动开浏览器。
- **背景决策**：用户选定方案 A（完全删除 tkinter，非保留兼容）；只写文件不自动开浏览器（内网环境浏览器未必可用，用户自行打开）。cycle 布局复用 t6 的 `matrices_to_html_grid()`，新增 `layout` 参数 + 全屏 CSS 变体（`vmin` 单位）。
- **已完成**：
  1. TDD：`tests/test_qr_render.py` 加 `TestCycleLayout`（7 项：one_qr_per_page / auto_on_by_default / forces_single_col_single_row / fullscreen_css_marker / interval_applied / invalid_layout_raises / svg_count_preserved），确认红（`TypeError: unexpected keyword argument 'layout'`），再实现转绿。
  2. `sqr/sender/qr_render.py`：加 `_CYCLE_CSS`（全屏 black bg + `90vmin` QR + `100vh` 页面 flex 居中）+ `matrices_to_html_grid()` 新增 `layout` 参数（`"grid"` 默认 / `"cycle"`）。cycle 时强制 `cols=1` / `rows_per_page=1` / `auto_cycle=True` 并切换到 `_CYCLE_CSS`；非法 layout 值 `ValueError`。
  3. `sqr/cli.py`：删除 `from sqr.sender.player import QRPlayer` + tkinter player 分支；删除 `--no-player` 标志；`--renderer` choices 从 `["auto","tkinter","terminal"]` 改为 `["html","terminal"]`（default `"html"`）；新增 `--html-cycle <path>` 标志；默认行为（无特殊标志）→ 写 cycle HTML 到 `sqr_sender.html`。`matrices_to_html_grid` 提升为顶层 import。
  4. 删除 `sqr/sender/player.py`（tkinter 全屏播放器，132 行）。
- **运行过的验证**：
  - `python3 -m pytest tests/ -q` → **133 passed in 2.69s**（126 基线 + cycle 新增 7）。
  - `python3 -m pytest tests/test_qr_render.py -q` → **48 passed**（41 + 7 cycle；AGENTS.md §5 改动文件单独跑全绿）。
  - 烟雾测试：`python3 -m sqr.cli send tests/fixtures/sample_mid.txt` → `sqr_sender.html`（3 frames），7 项断言全 PASS（vmin CSS / Auto: ON / autoCycle=true / SQR Cycle title / 3 qr-page / 3 SVG / 0 tkinter refs）。
  - `grep QRPlayer sqr/` → 仅剩 `qr_render.py` 中 `draw_matrix_on_canvas` 的 docstring 提及 tkinter.Canvas（该函数不 import tkinter，接受 canvas 参数；player.py 删除后已成死代码，本轮不改——scope discipline）。
- **已记录证据**：无新增证据文件；验证结果见本 Session「运行过的验证」+ feature_list.json `t7-html-cycle-replace-tkinter.evidence`。
- **提交记录**：本轮工作**尚未提交**（按 AGENTS.md §3，需用户显式批准）。t6 + t7 两轮工作均待提交。
- **更新过的文件或工件**：
  - `sqr/sender/qr_render.py`（`_CYCLE_CSS` + `layout` 参数 + cycle 强制逻辑，~30 行新增）
  - `sqr/cli.py`（删除 tkinter 分支 + `--no-player`；`--renderer` 改 choices/default；新增 `--html-cycle`；默认 cycle HTML 分支；import 提升）
  - `sqr/sender/player.py`（**删除**，-132 行）
  - `tests/test_qr_render.py`（`TestCycleLayout` 7 项）
  - `feature_list.json`（t7 in_progress → passing，in_progress_id 归位 null）
  - `claude-progress.md`（本 Session 006 + 待办清单 + 当前已验证状态）
- **已知风险或未解决问题**：
  1. **`draw_matrix_on_canvas` 成死代码**：`qr_render.py` 的渲染器 A（tkinter Canvas 绘制）在 player.py 删除后无调用方。函数本身不 import tkinter（接受 canvas 参数），不影响零依赖目标。后续可清理，但非本轮 scope。
  2. **真实屏幕 round-trip 未做**：cycle HTML 的全屏单 QR 循环未在真实「浏览器全屏 + mss 截图 + pyzbar」物理链路上验证（依赖 t1 的 VMware 环境）。与 t6 同类风险。
  3. **文档未同步**：`sqr/sender/ARCHITECTURE.md` 仍引用 player.py / QRPlayer / tkinter 全屏播放（Session 005 遗留 + 本轮新增的 layout 参数未记录）。需后续更新。
  4. **send.sh 自检**：`launcher/send.sh` 的自检逻辑（Phase 5 打包产物）可能仍假设 tkinter 可用——需在下一轮打包验证时确认。
- **下一步最佳动作**：
  1. 按需提交 t6 + t7 两轮改动（需用户批准）。
  2. 同步更新 `sqr/sender/ARCHITECTURE.md`（删 player.py 章节 + 加 layout 参数 + 更新默认行为为 cycle HTML）。
  3. 清理 `draw_matrix_on_canvas` 死代码（可选，低优先级）。
  4. 若有 VMware 环境：把 cycle HTML 放进真实屏幕 round-trip 验证。

### Session 007 — grid Auto 改逐张全屏播放（t8-grid-auto-per-frame）

- **日期**：2026-08-13
- **本轮目标**：修改发送端 grid 模式（`--html-grid`）的 Auto 行为：从"整页翻页"（一次切 cols×rows 张 QR）改为"逐张全屏播放"（Auto ON 进全屏舞台，一次 1 张 QR 逐帧轮播）。Auto OFF 回 grid 多张概览翻页（原行为）。cycle 模式零回归。
- **背景决策**：用户反馈 grid 模式 Auto 整页翻（默认 16 张/页一起换）对接收端解码不友好；澄清后确认 Auto ON 时屏幕一次只显示 1 张 QR 全屏大图（类似 cycle），逐张切换。
- **已完成**：
  1. `sqr/sender/qr_render.py`：
     - `_GRID_CSS` 加 `#player-stage` 样式（全屏 fixed，`display:none` 默认，flex 居中，`.qr-svg` 90vmin）。
     - `_GRID_JS_TEMPLATE` 重写支持 frame/page 双模式：新增 `playMode` 变量（grid=`"frame"` / cycle=`"page"`）；frame 模式 Auto ON 时 `enterPlayer()` 隐藏所有 page + 显示 stage、`showFrame(idx)` 克隆当前 cell 的 SVG 进 stage、`setInterval(gotoNextFrame)` 逐帧；Auto OFF `exitPlayer()` 回 grid 翻页。frame 模式手动 Prev/Next：Auto ON 时切帧 + 重启定时器，Auto OFF 时翻页。
     - `_build_grid_js()` 加 `play_mode` 参数（默认 `"page"`）。
     - `matrices_to_html_grid()`：grid 模式生成 `<div id="player-stage"></div>` + `play_mode="frame"`；cycle 模式不生成 stage + `play_mode="page"`（保持原翻页逻辑，每页 1 张即逐张）。
     - docstring 更新 grid/cycle 的 Auto 行为说明。
  2. `tests/test_qr_render.py`：`TestMatricesToHtmlGrid` 加 3 项（grid_has_player_stage / grid_play_mode_frame / grid_stage_hidden_by_default_css）；`TestCycleLayout` 加 2 项（cycle_no_player_stage / cycle_play_mode_page）。共 +5。
- **运行过的验证**：
  - `python3 -m pytest tests/test_qr_render.py -q` → **53 passed**（48 + 5 新增；AGENTS.md §5 改动文件单独跑全绿）。
  - `python3 -m pytest tests/ -q` → **138 passed in 2.72s**（133 基线 + 5 新增）。
  - 烟雾测试（实跑 `matrices_to_html_grid`）：10 frames cols=4 rows=4 → 含 player-stage + `playMode="frame"` + Auto:OFF + 1 页 10 SVG；`auto_cycle=True` → `playMode="frame"` + Auto:ON + `var autoCycle = true` + `enterPlayer()` 初始化；`layout="cycle"` → 无 player-stage + `playMode="page"` + Auto:ON + 10 页。
  - CLI 端到端：`send sample_mid.txt --html-grid /tmp/test_grid.html` → player-stage + `playMode="frame"` + Auto:OFF + 3 SVG/1 页；默认 `send` → cycle HTML 无 player-stage + `playMode="page"` + Auto:ON。
- **已记录证据**：无新增证据文件；验证结果见本 Session「运行过的验证」。
- **提交记录**：本轮工作**尚未提交**（按 AGENTS.md §3，需用户显式批准）。
- **更新过的文件或工件**：
  - `sqr/sender/qr_render.py`（`_GRID_CSS` +stage / `_GRID_JS_TEMPLATE` 重写 frame-page 双模式 / `_build_grid_js` +play_mode / `matrices_to_html_grid` 条件生成 stage + play_mode / docstring）
  - `tests/test_qr_render.py`（+5 断言：grid 3 + cycle 2）
  - `claude-progress.md`（本 Session 007 + 顶部基线 133→138 + 测试覆盖表 test_qr_render 48→53 + 待办清单加 t8 行）
- **已知风险或未解决问题**：
  1. **真实屏幕 round-trip 未做**：grid Auto 逐张全屏播放未在真实「浏览器全屏 + mss 截图 + pyzbar」物理链路验证（依赖 t1 的 VMware 环境）。与 t6/t7 同类风险。
  2. **player-stage 克隆 SVG 方式**：`showFrame` 用 `cloneNode(true)` 克隆 cell 的 SVG 进 stage，DOM 重复但视觉等效。QR 传输场景帧数有限（百级），无性能问题。
  3. **文档未同步**：`sqr/sender/ARCHITECTURE.md` 仍引用 player.py（Session 006 遗留），且未记录 player-stage / playMode 双模式。需后续统一更新。
- **下一步最佳动作**：
  1. 按需提交本轮改动（需用户批准）。
  2. 同步更新 `sqr/sender/ARCHITECTURE.md`（Session 006 + 007 合并更新：删 player.py + 加 layout/playMode/player-stage）。
  3. 若有 VMware 环境：把 grid Auto 逐张 HTML 放进真实屏幕 round-trip 验证。

### Session 008 — 接收端 image 批量解码（t9-decode-from-images）

- **日期**：2026-08-14
- **本轮目标**：接收端增加"从多个二维码 image 文件批量解码还原"能力。数据源从 mss 屏幕截图换成 image 文件列表（PPM/PNG/JPG），后续组装校验链路复用现有组件。接续 Session 007 后的 `/tmp/e2e_t001.py` image round-trip 验证，正式化为 CLI 子命令。
- **已完成**：
  1. `sqr/receiver/image_decoder.py`（新建）：`run_receiver_from_images(image_paths, output_path, expected_*, on_progress, on_complete)`。数据源换成 image 文件列表，复用 `ChunkAssembler` / `decompress_payload` / `verify_restored_file`，**不动 runner.py（零回归）**。每 image 优先 `decode_qr_multi`（兼容网格同屏多 QR），空回退 `decode_qr` 单码。manifest 缺失 / 数据帧未收齐 → 构造失败 `VerificationResult`（不抛异常）。私有助手 `_decode_image_file()` / `_fail_result()`。
  2. `sqr/cli.py`：加 `cmd_decode()` + `decode` 子命令。参数：`--image <file>`（action=append，可多次）+ `--images <dir>`（扫描 .ppm/.png/.jpg/.jpeg）+ `--output` + `--expected-sha256/md5/bytes`。`on_progress` 进度条 + `on_complete` 结果打印，风格对齐 `cmd_receive`。错误路径（目录不存在 / 无 image 参数 / 文件不存在）友好报错 exit 1。
  3. `tests/test_image_decoder.py`（新建，8 项）：round-trip small + round-trip mid + 顺序无关 + progress 回调 + manifest 缺失 + 数据帧缺失 + 空列表 + on_complete 回调。
- **运行过的验证**：
  - `python3 -m pytest tests/test_image_decoder.py -q` → **8 passed**（TDD：先红 ModuleNotFoundError → 实现转绿）。
  - `python3 -m pytest tests/ -q` → **146 passed in 4.47s**（138 基线 + 8 新增）。
  - CLI 端到端（`--images` 目录模式）：`decode --images /tmp/qr_frames_t001 --output received_cli.md --expected-sha256 d9c923... --expected-md5 68e7af... --expected-bytes 72641` → 进度条 0→100% → **SUCCESS** / 72641 bytes / SHA-256 ✓ / MD5 ✓ / UTF-8 OK；`diff` **IDENTICAL** / 系统 md5 `68e7affbd41c72bb81ed881fdd32be2b` 匹配。
  - `--image` append 路径：2 帧 → incomplete FAILED（missing 18 frames，参数收集正确）。
  - 错误路径：目录不存在 → exit 1；无 image 参数 → exit 1。
- **已记录证据**：无新增证据文件；验证结果见本 Session「运行过的验证」+ feature_list.json `t9-decode-from-images.evidence`。
- **提交记录**：本轮工作**尚未提交**（按 AGENTS.md §3，需用户显式批准）。
- **更新过的文件或工件**：
  - `sqr/receiver/image_decoder.py`（新建，~110 行）
  - `sqr/cli.py`（`cmd_decode()` + `decode` subparser）
  - `tests/test_image_decoder.py`（新建，8 项）
  - `feature_list.json`（t9 in_progress → passing，in_progress_id 归位 null）
  - `claude-progress.md`（本 Session 008 + 顶部基线 138→146 + 测试覆盖表加 test_image_decoder + 标准启动路径加 decode + 待办清单加 t9 行）
- **已知风险或未解决问题**：
  1. **真实屏幕 round-trip 未做**：image round-trip 证明接收端核心解码链路对 72KB 文件可靠，但仍非真实屏幕 mss 截图（依赖 t1 VMware 环境）。与 t6/t7/t8 同类风险。
  2. **CLI `--image` append 路径未单元测试覆盖**：函数层 `run_receiver_from_images` 的 path list 已被 8 项测试覆盖；CLI 层 `action="append"` 参数收集靠手动端到端验证（2 帧 incomplete 测试通过）。
  3. **大批量 image 性能未测**：当前 t001_60k = 20 张秒级完成；数百张 image 的 I/O + 解码耗时未压测。
  4. **GUI 未集成**：`sqr.receiver.app`（控制面板）未加"上传 image"按钮调用 `run_receiver_from_images`；app.py 本身仍未被 feature_list.json 收录（Session 001 遗留）。
- **下一步最佳动作**：
  1. 按需提交本轮改动（需用户批准）。
  2. 可选：GUI `app.py` 加"上传 image"按钮调用 `run_receiver_from_images`（同时把 app.py 正式登记进 feature_list.json）。
  3. 可选：`decode` 支持 glob 模式（`--image "frames/*.ppm"`）。
  4. 同步更新 `sqr/receiver/ARCHITECTURE.md`（加 image_decoder 模块说明）。

### Session 009 — GUI 加 image 批量解码按钮 + app.py 正式登记

- **日期**：2026-08-14
- **本轮目标**：接收端 GUI 控制面板（`sqr/receiver/app.py`）加"从 image 文件批量解码"按钮，触发 `run_receiver_from_images`（t9 的 GUI 入口）；同时把 app.py 正式登记进 feature_list.json（消除 Session 001 遗留风险 #5）。
- **已完成**：
  1. `sqr/receiver/app.py`：
     - `_build_ui` 加**步骤③ section**（row 13-16）："选择 image 文件…" / "选择目录…" / "开始解码" 三按钮 + 已选文件数显示。日志区 row 号 13-15 → 17-19。
     - 加 `_on_select_image_files`（filedialog.askopenfilenames 多选 .ppm/.png/.jpg）/ `_on_select_image_dir`（askdirectory + 扫描扩展名）/ `_on_start_decode`（校验非空 + 后台线程）事件方法。
     - 加 `_run_decode` 后台线程方法（调 `run_receiver_from_images`，进度/完成/异常事件经 `queue.Queue` 传主线程，复用现有 `_drain_queue` 轮询机制）。
     - `_set_controls_busy` 加步骤③三按钮的 disable/enable。
     - `__init__` 加 `self.image_paths: list[Path]` 状态。
  2. `feature_list.json`：加 `p7-gui-control-panel`（passing），app.py 正式收录（消除 Session 001 遗留风险 #5）；t9 notes 补 GUI 入口说明。
- **运行过的验证**：
  - `.venv/bin/python -c "import sqr.receiver.app"` → **import OK**（app.py 无单元测试，靠 import 检查语法/导入）。
  - `python3 -m pytest tests/ -q` → **146 passed**（未破坏其他；GUI 改动不影响测试层）。
  - GUI 启动（tmux sqr-gui）：`.venv/bin/python -m sqr.cli gui` → 无 traceback，进程运行，窗口弹出。
- **已记录证据**：无新增证据文件；验证结果见本 Session「运行过的验证」+ feature_list.json `p7-gui-control-panel.evidence`。
- **提交记录**：本轮工作**尚未提交**（按 AGENTS.md §3，需用户显式批准）。
- **更新过的文件或工件**：
  - `sqr/receiver/app.py`（步骤③ UI + 3 事件方法 + _run_decode + _set_controls_busy + image_paths 状态，~70 行新增）
  - `feature_list.json`（加 p7-gui-control-panel passing + t9 notes 补 GUI）
  - `claude-progress.md`（本 Session 009 + 待办清单加 p7 行）
- **已知风险或未解决问题**：
  1. **GUI 无自动化测试**：tkinter 需手动验证（与 p4-screen-io / p6-gui-region-selector 同类，均"手动验证，无独立自动化测试"）。
  2. **image 解码无停止按钮**：场景快（t001_60k 秒级），未加 stop_event 支持；数百张大图未压测（如需可扩展 run_receiver_from_images 加 stop_event）。
  3. **GUI 解码时输出路径默认 sqr_output.txt**：用户需手动改成 .md 或对应扩展名（沿用现有 output_var 默认值，未特判）。
- **下一步最佳动作**：
  1. 用户手动测试 GUI image 按钮：选 `/tmp/qr_frames_t001` 目录 → 开始解码 → 验证还原。
  2. 按需提交本轮改动（需用户批准）。

### Session 010 — 发送端 HTML 加 Save ZIP 按钮（纯 JS 零依赖导出 QR PNG zip）

- **日期**：2026-08-14
- **本轮目标**：发送端静态 HTML（`matrices_to_html_grid` 产物）加 "Save ZIP" 按钮，点击把全部 QR 帧 SVG 光栅化为 PNG 打包成 zip 下载，打通"发送端 HTML → image zip → 接收端 image 批量解码"链路。
- **已完成**：
  1. `sqr/sender/qr_render.py`：加 `_ZIP_JS` 常量（独立 `<script>` 块，纯 JS 零依赖）：
     - CRC32 查表实现（IEEE 802.3，与 Python `binascii.crc32` 一致）
     - `svgToPng()`：SVG DOM → serializeToString → Blob URL → Image.onload → canvas 光栅化（pxPerModule=10，version 3 QR → 370px）→ toDataURL('image/png') → Uint8Array
     - `buildZip()`：STORE 无压缩格式（local file header + central directory + EOCD），手写 u16/u32 LE 编码
     - save-zip 按钮事件：遍历 `.qr-cell .qr-svg` 批量异步转 PNG → 计数器收齐 → 打包 zip → `<a download="qr_frames.zip">` 触发下载；过程显示 "Zipping N/M" 进度
     - **JS 源码无 `<svg` 字面量**（保护 `test_svg_count_equals_matrices` 计数断言）
  2. `matrices_to_html_grid` controls 加 `<button id="save-zip-btn">Save ZIP</button>`（grid + cycle 两种布局共用）
  3. body 拼接追加 `_ZIP_JS`（在 `_build_grid_js` 后、`</body>` 前）
  4. `tests/test_qr_render.py`：加 4 测试（`test_has_save_zip_button` / `test_zip_js_embedded` / `test_zip_js_no_extra_svg_literal` / `test_cycle_has_save_zip_button`）
- **运行过的验证**：
  - `import sqr.sender.qr_render` → **import OK**
  - `pytest tests/test_qr_render.py -q` → **57 passed**
  - `pytest tests/ -q` → **150 passed**（原 146 + 4 新测试）
  - **Playwright 端到端**（纯 JS zip 浏览器首次验证）：
    1. 生成 5 帧 cycle HTML（`/tmp/test_savezip.html`，5 个 SQ1 帧）
    2. 临时 http.server + Playwright navigate + click `#save-zip-btn`
    3. `page.waitForEvent('download')` 捕获 → `download.saveAs('/tmp/qr_frames_download.zip')`
    4. Python 校验：`zipfile.testzip()` → None（CRC 全过）；5 个文件 `qr_0.png…qr_4.png`（各 370×370px）
    5. 每个 PNG `pyzbar.decode` → 全部成功 → 还原 SQ1 帧 `match: True`
- **已记录证据**：`/tmp/qr_frames_download.zip`（Playwright 下载产物，端到端验证用，可复现）。
- **提交记录**：本轮工作**尚未提交**（按 AGENTS.md §3，需用户显式批准）。
- **更新过的文件或工件**：
  - `sqr/sender/qr_render.py`（`_ZIP_JS` ~120 行 + controls +1 按钮 + body +1 拼接）
  - `tests/test_qr_render.py`（+4 测试）
  - `claude-progress.md`（本 Session 010 + 待办清单加 t10 行）
  - `feature_list.json`（加 `t10-save-zip-from-html` passing）
- **已知风险或未解决问题**：
  1. **SVG→PNG 依赖现代浏览器**：canvas + Image.onload + Blob URL + toDataURL，极旧浏览器可能不支持；但项目已假设现代浏览器（CSS grid/flex/vmin）。canvas taint 风险已规避（SVG 纯 rect 无 foreignObject，blob URL 同源）。
  2. **pxPerModule=10 硬编码**：version 3 QR → 370px 已验证 pyzbar 可读；更大 version（高容量文件分片多）未跨 version 压测，理论上 pxPerModule=10 对所有 version 足够（pyzbar 扫光栅 QR 不依赖绝对像素，只看对比度）。
  3. **下载文件名固定 `qr_frames.zip`**：未含 file_id，多个文件并发下载可能撞名（单用户场景无影响）。
- **下一步最佳动作**：
  1. 用户手动浏览器测试：打开真实 sqr_sender.html → 点 Save ZIP → 用接收端 GUI 步骤③ 或 CLI `decode` 解码验证。
  2. 按需提交本轮改动（需用户批准）。

### Session 011 — 重新打包内网发送端

- **日期**：2026-08-15
- **本轮目标**：生成可带入内网使用的 Tier 1 完整发送端压缩包，并从解压后的包内实际启动验证。
- **已完成**：
  1. 移除 `send.sh` / `send.bat` 中过时的 tkinter 自检；当前发送端使用浏览器 HTML 播放，不再需要 tkinter。
  2. 更新包内 `README.txt`：说明默认生成 `sqr_sender.html`、浏览器打开播放、Save ZIP 导出 PNG，并更新当前 CLI 参数。
  3. 重新生成 `dist/sqr-sender-src.zip`：约 54 KB，37 files，vendor qrcode 24 个 Python 文件。
  4. 根据内网报错修复 Python 3.6 兼容性：用 `typing.NamedTuple` 替代 Python 3.7+ `dataclasses`，移除 `future annotations`，把新式 union/容器标注改为 `typing` 形式，并移除 Python 3.7 才支持的 `add_subparsers(required=True)`。
  5. 新增并扩展 `tests/test_sender_bundle_compat.py` 5 项回归测试，防止再引入旧 Python 不支持的语法/typing 特性或 tkinter 依赖。
  6. 根据内网环境将 `send.sh` 设为优先使用 `/opt/devtoolset/python3.9.12/bin/python3`；该路径不存在时回退 `python3`，仍可用 `PYTHON=/path/to/python3` 手动覆盖。
  7. 递归检查 vendor 24 个 Python 文件，移除 `typing.Literal` 与 PEP 585 内建容器标注等旧 Python 不兼容项。
- **运行过的验证**：
  - `.venv/bin/python -m pytest tests/test_sender_bundle_compat.py -q` → **5 passed**。
  - `.venv/bin/python -m pytest tests/ -q` → **155 passed**。
  - 从 zip 解压到临时目录后 `./send.sh --help` → 环境自检通过，CLI help 正常。
  - 解压包内 `./send.sh sample_small.txt --html-cycle sample_sender.html` → 成功生成 2 帧 HTML，确认 `SQR Cycle` / `Auto: ON` / `Save ZIP` 存在。
- **更新过的文件或工件**：`launcher/send.sh`、`launcher/send.bat`、`build/bundle_sender.py`、`sqr/protocol.py`、`sqr/cli.py`、`sqr/sender/{compressor,chunker,qr_render}.py`、`sqr/vendor/__init__.py`、`tests/test_sender_bundle_compat.py`、`dist/sqr-sender-src.zip`、`feature_list.json`、`claude-progress.md`。
- **已知风险**：Windows `send.bat` 在 macOS 上无法实跑，但与已验证的 shell 启动链路使用同一 Python/vendor 入口。这是源码包，内网机器仍需 Python 3.6+ 和现代浏览器；无 Python 环境需完成 t2 PyInstaller 打包。
- **提交记录**：本轮改动将通过 `codex/sender-python39-bundle` 分支发布。

### Session 012 — 目录信息包传输（t11-directory-bundle-transfer）

- **日期**：2026-08-15
- **本轮目标**：实现 M1 目录信息包传输：发送端接受目录，保留指定根目录名、相对目录结构、普通文件内容、空文件和空目录；接收端在整包与逐文件校验通过后安全还原。
- **启动基线**：系统 `python3` 缺 pytest；改用仓库 `.venv/bin/python`，全量 **155 passed in 4.66s**。工作区原有未跟踪 `sqr_output.txt` / `sqr_sender.html`，保持不动。
- **已完成**：
  1. 新增 `sqr/bundle/{builder,extractor}.py`：确定性 ZIP_STORED 信息包，`.sqr-bundle.json` 记录根目录、规范化路径、文件大小与逐文件 SHA-256；保留 Unicode、二进制/空文件及空目录。
  2. 初版在打包阶段拒绝符号链接和特殊文件；后续 t14 将内部软链接改为不跟随并跳过，根目录软链接和其他特殊文件仍拒绝。绝对内网路径不会写入信息包。
  3. 新增 `sqr/receiver/restorer.py`，屏幕接收与 image 解码共用同一恢复边界；整包 SHA-256/MD5/字节数通过后，目录包手工安全解包到 `.sqr-partial-*`，逐文件校验通过后原子发布。
  4. 解包拒绝绝对路径、`..`、反斜杠、盘符、NUL、重复路径、清单外成员和超限展开；目标根目录已存在时默认失败且不覆盖。
  5. `sqr.cli send` 位置参数扩展为 UTF-8 文件或目录；目录包接收时 `--output` 表示输出父目录。单文件行为保持不变。
  6. 更新顶层、发送端和接收端架构文档；更新 Tier 1 README 并重建 `dist/sqr-sender-src.zip`（约 58KB）。
- **运行过的验证**：
  - `.venv/bin/python -m pytest tests/test_bundle.py tests/test_directory_roundtrip.py -q` → **11 passed**。
  - 兼容回归组合（image decoder / roundtrip / protocol / sender bundle compat）→ **57 passed**。
  - `.venv/bin/python -m pytest tests/ -q` → **166 passed in 4.95s**。
  - CLI：2 文件/3 目录/53338 文件字节 → 54530B bundle → 3 PPM 帧 → `decode` SUCCESS → `restored/source`；`diff -r` identical。
  - 重建后 `./dist/sqr-sender/send.sh <directory> --html-cycle ...` 实跑成功，生成 3 帧 Auto:ON HTML。
- **更新过的文件或工件**：`sqr/bundle/`、`sqr/receiver/restorer.py`、`sqr/{cli.py,receiver/{runner,image_decoder,verifier}.py}`、3 份 ARCHITECTURE.md、`tests/{test_bundle,test_directory_roundtrip,test_sender_bundle_compat}.py`、`build/bundle_sender.py`、`dist/sqr-sender-src.zip`、`feature_list.json`、本文件。
- **已知风险或后续范围**：M1 仍将完整 bundle/Base64/QR matrices 放在内存中；真正的大目录需要 `t5`/M2 的磁盘持久化、断点续收、分卷和 HTML 延迟加载。软链接由 t14 排除，不还原；权限、owner/ACL/xattr 不在 M1 支持范围。真实屏幕目录 round-trip 仍依赖 `t1` 的 VMware 环境。
- **提交记录**：本轮以 `feat(bundle): transfer directory trees safely via SQ1 — 166 tests pass` 提交。
- **下一步最佳动作**：有 VMware 环境时做真实屏幕目录 round-trip；否则推进 `t5-large-file-transfer` 的持久化/分卷设计。

### Session 013 — 目录文件名正则筛选（t12-directory-filename-regex-filter）

- **日期**：2026-08-15
- **本轮目标**：发送目录时通过可重复的 `--include-regex` 筛选同步文件；正则对 basename 执行 `re.search`，多个表达式按 OR，保留匹配文件所需的祖先目录。
- **启动基线**：`.venv/bin/python -m pytest tests/ -q` → **166 passed in 4.93s**；`in_progress_id` 原为 null；原有未跟踪 `sqr_output.txt` / `sqr_sender.html` 保持不动。
- **已完成**：
  1. `build_directory_bundle(source, include_regexes=...)` 编译 Python 正则并对文件 basename 执行 `re.search`；多个表达式按 OR。
  2. 启用筛选时不保留无关目录，只保留 bundle 根目录和匹配文件所需祖先目录；未传筛选时仍完整保留空目录，零回归。
  3. CLI `send` 新增可重复 `--include-regex PATTERN`；单文件误用时友好报错，非法正则返回明确错误；输出显示实际文件/目录/字节数与 Filters。
  4. 更新 bundle/发送端架构说明和 Tier 1 README，重建 `dist/sqr-sender-src.zip`（约 59KB）。
- **运行过的验证**：
  - `test_bundle.py` → **13 passed**；`test_directory_roundtrip.py` → **3 passed**。
  - `.venv/bin/python -m pytest tests/ -q` → **171 passed in 5.07s**。
  - CLI `--include-regex '\\.txt$'` → 3 PPM → decode SUCCESS；恢复结果仅有 `hello.txt` 与 `nested/data.txt`，无关空目录未传输。
  - 非法 `--include-regex '['` → exit 1 + 友好错误。
  - 重建后的 `dist/sqr-sender/send.sh ... --include-regex '^hello'` → 仅 1 文件/1 目录，生成 2 帧 HTML。
- **更新过的文件或工件**：`sqr/bundle/builder.py`、`sqr/cli.py`、`tests/{test_bundle,test_directory_roundtrip}.py`、`build/bundle_sender.py`、`dist/sqr-sender-src.zip`、顶层/发送端 ARCHITECTURE.md、`feature_list.json`、本文件。
- **已知边界**：筛选只匹配 basename，不匹配相对路径；默认大小写敏感，可用 `(?i)`；当前只有 include，没有 exclude。正则只影响普通文件；t14 起内部软链接跳过，其他特殊文件仍拒绝。
- **提交记录**：本轮以 `feat(bundle): filter directory files by regex — 171 tests pass` 提交。

### Session 014 — GUI 目录包保存父目录选择器（t13-gui-directory-output-picker）

- **日期**：2026-08-15
- **本轮目标**：补齐接收端 GUI 的目录还原入口：输出区域增加“选择目录”按钮，明确普通文件路径与目录包父目录的不同语义，并在成功事件中展示实际还原根目录。
- **启动基线**：`.venv/bin/python -m pytest tests/ -q` → **171 passed in 5.17s**；原有未跟踪 `sqr_output.txt` / `sqr_sender.html` 保持不动。
- **已完成**：
  1. GUI 输出区由单一“浏览…”改为独立“选择文件…”和“选择目录…”按钮，标签改为“输出路径”。
  2. 新增说明“普通文件：填写目标文件；目录包：选择保存父目录”，subtitle 同步说明可还原完整目录结构。
  3. `_browse_output_directory()` 用 `askdirectory` 写入 `output_var` 并记录父目录语义；接收进行中两个输出选择按钮会一起禁用。
  4. 完成事件继续使用后端 `restorer` 回传的实际路径，因此目录包弹窗显示 `<所选父目录>/<原根目录名>`。
  5. 新增 `tests/test_receiver_app.py` 两项无窗口 helper 测试；接收端架构文档同步更新。
- **运行过的验证**：
  - `.venv/bin/python -m pytest tests/test_receiver_app.py -q` → **2 passed**。
  - `.venv/bin/python -c 'import sqr.receiver.app'` → import OK。
  - `.venv/bin/python -m pytest tests/ -q` → **173 passed in 5.20s**。
- **视觉核验说明**：按 computer-use 技能启动新 GUI，但本机已有多个相同 Python bundle 的旧 Tk 进程，界面工具只能聚焦旧实例；未把旧界面截图作为新版本证据，也未关闭可能属于用户的旧窗口。新进程已停止。
- **更新过的文件**：`sqr/receiver/app.py`、`sqr/receiver/ARCHITECTURE.md`、`tests/test_receiver_app.py`、`feature_list.json`、本文件。
- **提交记录**：本轮以 `feat(gui): choose parent directory for bundle restore — 173 tests pass` 提交。

### Session 015 — 目录内部软链接排除（t14-skip-internal-symlinks）

- **日期**：2026-08-15
- **本轮目标**：目录扫描遇到内部软链接文件/目录时从信息包排除，不跟随、不失败；根目录本身为软链接仍拒绝，并显示跳过数量。
- **启动基线**：工作区测试文件存在用户侧 mode 100644→100755 变更及 `tests/user_case/dir_case/` 测试产物，内容未变；全部保持不动。`.venv/bin/python -m pytest tests/ -q` → **173 passed in 5.11s**。
- **已完成**：
  1. `build_directory_bundle` 遍历 `dir_names` 时移除软链接目录，遍历文件时跳过软链接文件；两者都不读取、不跟随，并累计 `skipped_symlink_count`。
  2. `BundleBuildResult` 增加跳过计数；CLI 在存在软链接时打印 `Symlinks: skipped N`。
  3. 所选根目录本身为软链接继续拒绝；FIFO/socket/device 等非软链接特殊文件继续拒绝。
  4. 新增独立 `tests/test_bundle_symlinks.py`，避免覆盖用户当前对原测试文件的权限调整；旧 `test_bundle.py` 冲突断言仅更新为新策略。
  5. 更新架构与包内 README，重建 `dist/sqr-sender-src.zip`（约 59KB）。
- **运行过的验证**：
  - `tests/test_bundle_symlinks.py` → **3 passed**；bundle + directory roundtrip 组合 → **19 passed**。
  - `.venv/bin/python -m pytest tests/ -q` → **176 passed in 5.02s**。
  - CLI 实测：1 软链接文件 + 1 软链接目录 + 1 普通 `.tcl` → `Symlinks: skipped 2`，生成 2 帧；decode SUCCESS 后仅有 `real-dir/keep.tcl`。
  - 重建后的 `dist/sqr-sender/send.sh` 在同一含软链接目录上运行成功并显示 skipped 2。
- **更新过的文件或工件**：`sqr/bundle/builder.py`、`sqr/cli.py`、`tests/test_bundle_symlinks.py`、`tests/test_bundle.py`（仅断言更新，用户 chmod 保留）、顶层/发送端 ARCHITECTURE.md、`build/bundle_sender.py`、`dist/sqr-sender-src.zip`、`feature_list.json`、本文件。
- **提交记录**：本轮以 `fix(bundle): skip internal symlinks safely — 176 tests pass` 提交；不包含用户测试产物与测试文件权限变更。
