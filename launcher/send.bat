@echo off
cd /d "%~dp0"

python -c "import sys; sys.exit(0 if sys.version_info >= (3,6) else 1)" 2>nul
if errorlevel 1 (
    echo [ERROR] Python 3.6+ not found. Install from https://www.python.org/downloads/
    exit /b 1
)

python -c "import tkinter" 2>nul
if errorlevel 1 (
    echo [ERROR] tkinter not available. Reinstall Python and enable tcl/tk option.
    exit /b 1
)

python -c "import sqr.vendor; import qrcode" 2>nul
if errorlevel 1 (
    echo [ERROR] vendor qrcode failed to load. Bundle may be corrupted.
    exit /b 1
)

python sqr\cli.py send %*
