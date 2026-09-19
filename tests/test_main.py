"""main 入口单元测试（offscreen Qt）。"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

import main as main_mod
from core.exact_solver import ExactSolver
from core.heuristic_solver import HeuristicSolver


def test_make_solver_fast() -> None:
    assert isinstance(main_mod.make_solver("fast"), HeuristicSolver)


def test_make_solver_exact() -> None:
    assert isinstance(main_mod.make_solver("exact"), ExactSolver)


def test_excepthook_writes_log_and_suppresses_dialog(
    qapp: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(main_mod, "_log_dir", lambda: tmp_path)
    from PySide6.QtWidgets import QMessageBox

    called: list[str] = []

    def _fake_critical(*a: object, **k: object) -> None:
        called.append("x")

    monkeypatch.setattr(QMessageBox, "critical", _fake_critical)
    main_mod._install_excepthook()
    try:
        raise ValueError("boom")
    except ValueError as e:
        sys.excepthook(type(e), e, e.__traceback__)
    log = tmp_path / "error.log"
    assert log.exists()
    assert "boom" in log.read_text(encoding="utf-8")
    assert called  # 弹窗被调用


def test_main_wiring(qapp: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """main() 装配：SettingsStore.load → translator.init → Controller → MainWindow。"""
    from fileio.settings import SettingsStore

    settings = SettingsStore(tmp_path / "settings.json")
    settings.load()
    monkeypatch.setattr(main_mod, "SettingsStore", lambda: settings)
    monkeypatch.setattr(main_mod, "_install_excepthook", lambda: None)

    shown: list[str] = []

    class _FakeWin:
        def __init__(self, controller: Any, settings_: Any) -> None:
            assert controller is not None and settings_ is settings

        def show(self) -> None:
            shown.append("x")

    import ui.main_window as mw_mod

    monkeypatch.setattr(mw_mod, "MainWindow", _FakeWin)
    monkeypatch.setattr(type(qapp), "exec", lambda self: 0)
    with pytest.raises(SystemExit) as ei:
        main_mod.main()
    assert ei.value.code == 0
    assert shown


def test_exact_solver_default_ctor() -> None:
    ExactSolver()  # cancel 可选，默认 None
