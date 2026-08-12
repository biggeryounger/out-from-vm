#!/usr/bin/env bash
#
# init.sh — sqr 项目统一启动与验证入口
#
# 一条命令完成：打印目录 → 安装依赖 → 跑测试 → 启动指定模式。
# 用法：
#   ./init.sh                       # 安装 + 验证 + 打印所有启动命令
#   ./init.sh receive [...]         # 安装 + 验证 + 启动接收端（参数透传给 sqr.cli）
#   ./init.sh send <file> [...]     # 安装 + 验证 + 启动发送端（file 是位置参数）
#   ./init.sh gui                   # 安装 + 验证 + 启动接收端控制面板
#   ./init.sh help                  # 直接打印 sqr CLI help（跳过 install/verify）
#   ./init.sh test [pytest args...] # 快速路径，只跑测试（跳过 install/launch），参数透传给 pytest
#   RUN_START_COMMAND=1 ./init.sh   # 不带子命令时执行 START_CMD
#
# 顶部三个变量按项目实际情况改：
#   INSTALL_CMD — 依赖安装命令
#   VERIFY_CMD  — 基础验证命令（应为 AGENTS.md §1.5 的"标准验证路径"）
#   START_CMD   — 不带子命令 + RUN_START_COMMAND=1 时的默认启动命令
#
# macOS 系统前置（不在本脚本职责内）：brew install zbar  # pyzbar 后端

set -euo pipefail

# === Configuration (edit these) ===
INSTALL_CMD="python3 -m pip install -r requirements-test.txt"
VERIFY_CMD="python3 -m pytest tests/ -q"
START_CMD="python3 -m sqr.cli --help"

install_libzbar() {
    case "$(uname -s)" in
        Darwin)
            if command -v brew >/dev/null 2>&1; then
                echo "  macOS: brew install zbar"
                brew install zbar
            else
                echo "  ✗ Homebrew 未安装。请先装 brew: https://brew.sh" >&2
                echo "    然后运行: brew install zbar" >&2
                return 1
            fi
            ;;
        Linux)
            if command -v apt-get >/dev/null 2>&1; then
                echo "  Debian/Ubuntu: sudo apt-get install -y libzbar0"
                sudo apt-get install -y libzbar0
            elif command -v dnf >/dev/null 2>&1; then
                echo "  Fedora/RHEL: sudo dnf install -y zbar"
                sudo dnf install -y zbar
            elif command -v apk >/dev/null 2>&1; then
                echo "  Alpine: sudo apk add zbar"
                sudo apk add zbar
            else
                echo "  ✗ 未知包管理器，请手动装 libzbar:" >&2
                echo "    Debian/Ubuntu: sudo apt-get install libzbar0" >&2
                echo "    Fedora/RHEL:   sudo dnf install zbar" >&2
                echo "    Alpine:        sudo apk add zbar" >&2
                return 1
            fi
            ;;
        *)
            echo "  ✗ 不支持的 OS: $(uname -s)，请手动安装 libzbar。" >&2
            return 1
            ;;
    esac
}

# === Prefer .venv if present (所有路径统一前置，确保快速路径也能用 venv) ===
if [[ -x ".venv/bin/python" ]]; then
    export PATH="$PWD/.venv/bin:$PATH"
    echo "(detected .venv, prepended to PATH)"
fi

# === 快速路径：./init.sh help 直接打印 CLI help，跳过 install/verify ===
if [[ "${1:-}" == "help" || "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    exec python3 -m sqr.cli --help
fi

# === 快速路径：./init.sh test [...] 只跑测试（跳过 install/launch），参数透传给 pytest ===
if [[ "${1:-}" == "test" ]]; then
    shift
    echo "=== Running tests only (skipping install/launch) ==="
    echo "  python3 -m pytest $*"
    echo ""
    exec python3 -m pytest "$@"
fi

echo ""

# === 快速路径：./init.sh install 全自动安装接收端环境（.venv + pip + libzbar），装完退出 ===
if [[ "${1:-}" == "install" ]]; then
    echo "=== Installing receiver environment (full auto) ==="
    echo ""
    echo "--- [1/4] Virtual environment ---"
    if [[ -x ".venv/bin/python" ]]; then
        echo "  .venv 已存在，复用。"
    else
        echo "  创建 .venv..."
        python3 -m venv .venv
        echo "  .venv 创建完成。"
    fi
    export PATH="$PWD/.venv/bin:$PATH"
    echo ""
    echo "--- [2/4] Python packages (pip install) ---"
    python3 -m pip install --upgrade pip
    python3 -m pip install -r requirements-test.txt
    echo ""
    echo "--- [3/4] System dependency: libzbar (pyzbar backend) ---"
    if python3 -c "from pyzbar.pyzbar import decode" 2>/dev/null; then
        echo "  pyzbar 已可导入，libzbar 已就位。"
    else
        echo "  pyzbar 导入失败，尝试安装 libzbar..."
        install_libzbar || { echo "  libzbar 安装失败，请按提示手动安装后重跑 ./init.sh install" >&2; exit 1; }
    fi
    echo ""
    echo "--- [4/4] Verification ---"
    if python3 -c "from pyzbar.pyzbar import decode; import mss; import PIL; print('receiver deps OK')" 2>/dev/null; then
        echo "  ✓ 接收端环境就绪。"
    else
        echo "  ✗ pyzbar 仍无法导入，libzbar 可能未装好。" >&2
        echo "    手动尝试: brew install zbar (macOS) / apt-get install libzbar0 (Debian)" >&2
        exit 1
    fi
    echo ""
    echo "=== install 完成。运行 ./init.sh 进行验证 + 打印启动菜单。 ==="
    exit 0
fi

# === [1/4] Print working directory ===
echo "=== [1/4] Working directory ==="
pwd
expected_root="out-from-vm"
if [[ "$(basename "$PWD")" != "$expected_root" ]]; then
    echo "⚠️  Expected to run from .../$expected_root/ root, got $(basename "$PWD")"
fi
echo ""

# === [2/4] Install dependencies ===
echo "=== [2/4] Installing dependencies ==="
echo "  $INSTALL_CMD"
$INSTALL_CMD
echo ""

# === [3/4] Run verification ===
echo "=== [3/4] Running verification ==="
echo "  $VERIFY_CMD"
$VERIFY_CMD
echo ""

# === [4/4] Launch ===
echo "=== [4/4] Launch ==="
SUBCOMMAND="${1:-}"

case "$SUBCOMMAND" in
    "")
        # 无子命令：打印所有启动命令（默认行为）
        echo "  Sender (内网):       python3 -m sqr.cli send <file> [options]"
        echo "  Receiver (外网):     python3 -m sqr.cli receive [--output <path>]"
        echo "  Receiver 控制面板:   python3 -m sqr.cli gui"
        echo "  Default start:       $START_CMD"
        echo ""
        echo "提示：也可以直接用  ./init.sh receive | send <file> | gui  启动对应模式。"
        if [[ "${RUN_START_COMMAND:-0}" == "1" ]]; then
            echo ""
            echo "RUN_START_COMMAND=1, executing: $START_CMD"
            exec $START_CMD
        fi
        echo ""
        echo "✓ init.sh completed successfully."
        ;;
    receive|send|gui)
        # 透传：shift 掉子命令，剩下参数全部交给 sqr.cli
        shift
        echo "  Launching: python3 -m sqr.cli $SUBCOMMAND $*"
        echo ""
        exec python3 -m sqr.cli "$SUBCOMMAND" "$@"
        ;;
    *)
        echo "✗ Unknown subcommand: $SUBCOMMAND" >&2
        echo "" >&2
        echo "Usage:" >&2
        echo "  ./init.sh                    # 安装 + 验证 + 打印命令" >&2
        echo "  ./init.sh receive [...]      # 安装 + 验证 + 启动接收端（参数透传）" >&2
        echo "  ./init.sh send <file> [...]  # 安装 + 验证 + 启动发送端" >&2
        echo "  ./init.sh gui                # 安装 + 验证 + 启动接收端控制面板" >&2
        echo "  ./init.sh help               # 打印 sqr CLI help（快速路径）" >&2
        echo "  ./init.sh test [pytest args] # 只跑测试（快速路径，跳过 install/launch）" >&2
        exit 1
        ;;
esac
