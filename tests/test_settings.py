"""settings 模块测试（doc/tasks/settings.md，详细设计 §6.4）。"""

import json
from pathlib import Path

import pytest

from fileio.settings import DEFAULTS, SettingsStore


def test_load_missing_file_returns_defaults(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path / "no" / "settings.json")
    assert store.load() == DEFAULTS
    assert store.data == DEFAULTS


def test_save_and_reload_roundtrip(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path / "settings.json")
    store.load()
    store.data.update({"stock_length": 9000, "kerf": 5, "material": "钢管", "language": "en_US"})
    store.save()
    store2 = SettingsStore(tmp_path / "settings.json")
    cfg = store2.load()
    assert cfg["stock_length"] == 9000 and cfg["kerf"] == 5
    assert cfg["material"] == "钢管" and cfg["language"] == "en_US"


def test_corrupt_json_falls_back(tmp_path: Path) -> None:
    p = tmp_path / "settings.json"
    p.write_text("{not valid json!!!", encoding="utf-8")
    store = SettingsStore(p)
    assert store.load() == DEFAULTS


def test_unknown_keys_ignored(tmp_path: Path) -> None:
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"kerf": 7, "hacker_key": True}), encoding="utf-8")
    store = SettingsStore(p)
    cfg = store.load()
    assert cfg["kerf"] == 7 and "hacker_key" not in cfg


def test_atomic_save_no_tmp_left(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path / "settings.json")
    store.save()
    assert list(tmp_path.iterdir()) == [tmp_path / "settings.json"]


def test_default_path_uses_appdata(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path))
    store = SettingsStore()
    assert store.path == tmp_path / "CuttingApp" / "settings.json"
