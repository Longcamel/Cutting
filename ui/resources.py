"""界面静态资源（图标）解析。

打包（PyInstaller onefile）后资源在 sys._MEIPASS 下；
源码运行时回退到项目根 assets/icons。与 fileio.pdf_reporter 的
字体解析策略一致（详细设计 §8 T5）。
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QIcon

ICONS_DIR_NAME = Path("assets") / "icons"


def icon_path(name: str) -> Path:
    """返回图标文件路径：优先 PyInstaller 解包目录，其次项目根。"""
    bundled = Path(getattr(sys, "_MEIPASS", "")) / ICONS_DIR_NAME / name
    if bundled.is_file():
        return bundled
    return Path(__file__).resolve().parent.parent / ICONS_DIR_NAME / name


def load_icon(name: str) -> QIcon:
    """加载图标；文件缺失时返回空 QIcon（不崩溃，保持默认）。"""
    path = icon_path(name)
    return QIcon(str(path)) if path.is_file() else QIcon()
