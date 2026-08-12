#!/bin/bash
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="${PYTHON:-python3}"

if ! command -v "$PYTHON" >/dev/null 2>&1; then
    echo "✗ 未找到 ${PYTHON}。发送端需要 Python 3.6+。" >&2
    echo "  安装 Python: https://www.python.org/downloads/" >&2
    exit 1
fi

if ! "$PYTHON" - "$DIR" <<'PYEOF'
import sys
sys.path.insert(0, sys.argv[1])
errors = []
if sys.version_info < (3, 6):
    errors.append("Python 版本过低: {0}，需要 3.6+".format(sys.version.split()[0]))
try:
    import tkinter
except ImportError:
    errors.append("tkinter 不可用。Linux 请运行: sudo apt-get install python3-tk")
try:
    import sqr.vendor
    import qrcode
except Exception as e:
    errors.append("vendor qrcode 加载失败: {0}".format(e))
if errors:
    for e in errors:
        print("  ✗ " + e, file=sys.stderr)
    sys.exit(1)
PYEOF
then
    echo "✗ 环境自检失败，请按上述提示修复后重试。" >&2
    exit 1
fi

echo "✓ 环境自检通过，启动发送端..."
PYTHONPATH="$DIR:${PYTHONPATH:-}" exec "$PYTHON" "$DIR/sqr/cli.py" send "$@"
