# sqr/vendor/ 架构

> 发送端「零安装」能力的核心。让 `import qrcode` 在无 Pillow 的内网机器上不崩溃。

## 职责

vendor 解决一个问题：[`qrcode`](./qrcode/) 库在 `import` 时会触发 `from PIL import Image, ImageDraw`（导入链：`qrcode.image.base` → `styles.moduledrawers.__init__` → `moduledrawers.pil` → PIL）。内网机器没有 Pillow、也无法 `pip install`（Pillow 含 C 扩展，需编译工具链或预编译 wheel）。

vendor 的解法分两步：
1. **vendor qrcode 源码**：把纯 Python 的 `qrcode` 库直接拷进 `sqr/vendor/qrcode/`，随项目分发，无需安装。
2. **PIL stub**：在 `sqr/vendor/__init__.py` 注入一个假的 `PIL` 模块到 `sys.modules`，让 qrcode 的导入链通过，但 PIL 函数永远不会被真正调用。

## 文件

### `__init__.py` — bootstrap + PIL stub（33 行）

**必须在 `import qrcode` 之前执行**（`qr_render.py` 第 12 行 `import sqr.vendor` 在 `import qrcode` 之前）。

做两件事：

```python
# 1. 把 vendor 目录注入 sys.path，使 import qrcode 能找到 sqr/vendor/qrcode/
_VENDOR_DIR = os.path.dirname(os.path.abspath(__file__))
if _VENDOR_DIR not in sys.path:
    sys.path.insert(0, _VENDOR_DIR)

# 2. 若真实 PIL 不存在，注入 stub
if "PIL" not in sys.modules:
    try:
        import PIL  # 真实 Pillow 存在则跳过
    except ImportError:
        # 构造最小 stub：Image.new / Image.open / ImageDraw.Draw 都是空 lambda
        _pil = types.ModuleType("PIL")
        ...
        sys.modules["PIL"] = _pil
        sys.modules["PIL.Image"] = _pil.Image
        sys.modules["PIL.ImageDraw"] = _pil.ImageDraw
```

**为什么 stub 的空函数安全**：发送端只访问 `qr.modules`（`List[List[bool]]` 纯布尔矩阵，见 `qr_render.generate_matrix`），从不调用 `qr.make_image()`（那才会真正触发 PIL 绘图）。stub 方法被定义但永不执行。

### `qrcode/` — vendored 第三方库（24 个 .py）

纯 Python 的 [qrcode](https://github.com/lincolnloop/python-qrcode/) 源码原样拷入。**不应手动修改**——升级时重新 vendor。发送端实际只用到核心编码逻辑（`main.py` / `util.py` / `constants.py` / `LUT.py`），`image/` 和 `styles/` 仅因导入链被加载（由 PIL stub 兜住）。

## 与其它模块的关系

| 方向 | 关系 |
|---|---|
| 上游（谁用 vendor） | `sqr/sender/qr_render.py` —— `import sqr.vendor` 然后 `import qrcode` |
| 下游（vendor 用谁） | 仅 stdlib（`os` / `sys` / `types`）+ 自带的 `qrcode/` |

## 注意事项

- **顺序约束**：任何 `import qrcode` 之前必须有 `import sqr.vendor`，否则导入链崩溃。目前只有 `qr_render.py` 依赖 qrcode。
- **接收端不需要 vendor**：接收端（`sqr/receiver/`）用真实 Pillow 处理截图，用 pyzbar 解码，与 vendor 无关。`bundle_sender.py` 打包发送端时会**排除 receiver 目录**。
- stub 是**幂等**的：有真实 Pillow 时 stub 不激活，qrcode 正常用 Pillow；无 Pillow 时 stub 兜底。
