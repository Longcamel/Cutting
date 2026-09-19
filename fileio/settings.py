"""参数记忆（详细设计 §6.4）：%APPDATA%/CuttingApp/settings.json。

缺文件/损坏 → 返回默认值 dict，不抛异常；保存采用临时文件 + os.replace 原子写。
"""

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

_logger = logging.getLogger(__name__)

DEFAULTS: dict[str, Any] = {
    "stock_length": 6000,
    "kerf": 3,
    "material": "",
    "company": "",
    "project": "",
    "mode": "fast",
    "language": "zh_CN",
}


def _default_path() -> Path:
    appdata = os.environ.get("APPDATA")
    base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
    return base / "CuttingApp" / "settings.json"


class SettingsStore:
    """读写用户设置；self.data 为当前配置（load 后有效）。"""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path if path is not None else _default_path()
        self.data: dict[str, Any] = dict(DEFAULTS)

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> dict[str, Any]:
        """加载配置；缺文件/损坏 → 返回默认值 dict，不抛异常。"""
        self.data = dict(DEFAULTS)
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                for key, value in raw.items():
                    if key in DEFAULTS:
                        self.data[key] = value
        except FileNotFoundError:
            pass
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            _logger.warning("settings load failed (%s), use defaults", exc)
        return dict(self.data)

    def save(self) -> None:
        """原子写：写临时文件再 os.replace，防写坏。"""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self._path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(self.data, fh, ensure_ascii=False, indent=2)
            os.replace(tmp, self._path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise


__all__ = ["DEFAULTS", "SettingsStore"]
