# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec：onefile、windowed（无控制台），打包字体与 i18n 资源（main.md T5）。"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_all

datas = [
    (str(p), "i18n") for p in Path("i18n").glob("*.json")
] + [(str(p), "assets/fonts") for p in Path("assets/fonts").glob("*")]

# ortools 的 cp_model_helper 依赖原生 DLL，PyInstaller 默认收集不全 → collect_all
datas_o, binaries_o, hiddenimports_o = collect_all("ortools")

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries_o,
    datas=datas + datas_o,
    hiddenimports=["fileio.excel_importer", "fileio.excel_exporter", "fileio.pdf_reporter"]
    + ["PIL.Image", "PIL.PngImagePlugin"]  # Excel示意图：openpyxl 惰性依赖 PIL
    + list(hiddenimports_o),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "pytest_cov", "pytestqt", "mypy", "ruff"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Cutting",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
