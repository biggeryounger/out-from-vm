"""Compatibility checks for the zero-install sender source bundle."""

import ast
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SENDER_SOURCES = [PROJECT_ROOT / "sqr" / "protocol.py", PROJECT_ROOT / "sqr" / "cli.py"]
SENDER_SOURCES.extend((PROJECT_ROOT / "sqr" / "sender").rglob("*.py"))
SENDER_SOURCES.extend((PROJECT_ROOT / "sqr" / "bundle").rglob("*.py"))
SENDER_SOURCES.extend((PROJECT_ROOT / "sqr" / "vendor").rglob("*.py"))


def test_sender_sources_use_python36_grammar():
    for path in SENDER_SOURCES:
        ast.parse(
            path.read_text(encoding="utf-8"),
            filename=str(path),
            feature_version=(3, 6),
        )


def test_sender_sources_do_not_require_dataclasses_or_future_annotations():
    for path in SENDER_SOURCES:
        source = path.read_text(encoding="utf-8")
        assert "from dataclasses import" not in source, path
        assert "from __future__ import annotations" not in source, path


def test_sender_sources_do_not_use_new_typing_runtime_features():
    pep585 = re.compile(r"\b(?:list|dict|tuple|set|type)\[")
    for path in SENDER_SOURCES:
        source = path.read_text(encoding="utf-8")
        assert "Literal" not in source, path
        assert not pep585.search(source), path


def test_launchers_do_not_require_tkinter():
    for name in ("send.sh", "send.bat"):
        source = (PROJECT_ROOT / "launcher" / name).read_text(encoding="utf-8")
        assert "tkinter" not in source, name


def test_shell_launcher_prefers_internal_python39():
    source = (PROJECT_ROOT / "launcher" / "send.sh").read_text(encoding="utf-8")
    assert "/opt/devtoolset/python3.9.12/bin/python3" in source
    assert '[ -x "$PREFERRED_PYTHON" ]' in source
