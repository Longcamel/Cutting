"""ui/main_window 单元测试（offscreen Qt）。

覆盖（§5.6）：布局比例、菜单结构、状态栏进度显隐、语言切换、
PDF 导出注入 render_bar、无结果导出提示 E006、取消按钮。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from app.controller import AppController
from core.models import Part, Solution, StockSpec
from core.solver_base import ProgressCB, SolverBase
from fileio.settings import SettingsStore
from i18n.translator import _reset_for_test, current_language, set_language, tr
from ui import dialogs
from ui import main_window as main_window_mod
from ui.main_window import MainWindow

_PARTS = [Part(1500, 3, "A")]
_STOCK = StockSpec(length=6000, kerf=3)


class _DummySolver(SolverBase):
    def solve(
        self,
        parts: list[Part],
        stock: StockSpec,
        on_progress: ProgressCB | None = None,
        cancel: object = None,
    ) -> Solution:
        return Solution()


def _make_window(tmp_path: Path) -> MainWindow:
    store = SettingsStore(tmp_path / "settings.json")
    ctrl = AppController(store, lambda _mode: _DummySolver())
    return MainWindow(ctrl, store)


@pytest.fixture
def win(qapp: QApplication, tmp_path: Path) -> MainWindow:  # noqa: ARG001
    _reset_for_test()
    set_language("zh_CN")
    return _make_window(tmp_path)


def test_layout_and_menus(win: MainWindow) -> None:
    assert win.input_panel is not None
    assert win.result_panel is not None
    assert win.cutting_view is not None
    menus = [a.text() for a in win.menuBar().actions()]
    assert menus == [tr("menu.file"), tr("menu.language"), tr("menu.help")]
    acts = list(win._lang_actions.values())
    assert all(a.isCheckable() for a in acts)
    groups = {a.actionGroup() for a in acts}
    assert len(groups) == 1
    assert next(iter(groups)).isExclusive()
    assert win._progress.isHidden()
    assert win._btn_cancel.isHidden()


def test_solve_progress_flow(win: MainWindow) -> None:
    p = win.input_panel
    p.solveRequested.emit()
    assert not win._progress.isHidden()
    p.progressChanged.emit(42)
    assert win._progress.value() == 42
    win._controller.solution = Solution()
    p.solveFinished.emit(object())
    assert win._progress.isHidden()
    p.solveFailed.emit([])
    assert win._progress.isHidden()


def test_language_switch(win: MainWindow) -> None:
    win._lang_actions["en_US"].trigger()
    assert current_language() == "en_US"
    assert win._settings.data["language"] == "en_US"
    assert win._lang_actions["en_US"].isChecked()
    assert not win._lang_actions["zh_CN"].isChecked()
    assert win.windowTitle() == tr("app.title")
    win._lang_actions["zh_CN"].trigger()
    assert current_language() == "zh_CN"


def test_export_pdf_injects_render_bar(win: MainWindow, monkeypatch: pytest.MonkeyPatch) -> None:
    win._controller.solution = Solution()
    monkeypatch.setattr(dialogs, "ask_file", lambda *a, **k: "out.pdf")
    shown: list[str] = []
    monkeypatch.setattr(dialogs, "show_info", lambda _p, key, **kw: shown.append(key))
    captured: dict[str, object] = {}

    def fake_export(path: str, renderer: object = None) -> str | None:
        captured["path"] = path
        captured["renderer"] = renderer
        return None

    monkeypatch.setattr(win._controller, "export_pdf", fake_export)
    win._act_export_p.trigger()
    assert captured["path"] == "out.pdf"
    assert callable(captured["renderer"])
    assert shown == ["info.export_ok"]

    # renderer 委托 render_bar（注入 parts/stock）
    spy: list[tuple[object, ...]] = []

    def spy_render(p: object, pat: object, parts: object, stock: object, scale: float) -> None:
        spy.append((p, pat, parts, stock, scale))

    monkeypatch.setattr(main_window_mod, "render_bar", spy_render)
    renderer = captured["renderer"]
    assert callable(renderer)
    renderer(object(), object(), 1.0)
    assert spy and spy[0][2] == win._controller.parts and spy[0][3] == win._controller.stock


def test_export_without_solution_shows_e006(
    win: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    shown: list[str] = []
    monkeypatch.setattr(dialogs, "show_info", lambda _p, key, **kw: shown.append(key))
    win._act_export_x.trigger()
    win._act_export_p.trigger()
    assert shown == ["err.E006", "err.E006"]


def test_cancel_button(win: MainWindow, monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[bool] = []
    monkeypatch.setattr(win._controller, "cancel_solve", lambda: called.append(True))
    win.input_panel.solveRequested.emit()
    win._btn_cancel.click()
    assert called == [True]


def test_corner_link_buttons(win: MainWindow, monkeypatch: pytest.MonkeyPatch) -> None:
    """菜单栏右上角 GitHub/文档站图标按钮：图标非空、tooltip 随语言、点击跳转。"""
    from PySide6.QtGui import QDesktopServices

    assert not win._btn_github.icon().isNull()
    assert not win._btn_web.icon().isNull()
    assert win._btn_github.toolTip() == "GitHub 项目主页"
    assert win._btn_web.toolTip() == "项目文档网站"

    opened: list[str] = []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: opened.append(url.toString()))
    win._btn_github.click()
    win._btn_web.click()
    assert opened == [
        "https://github.com/Longcamel/Cutting",
        "https://longcamel.github.io/Cutting/",
    ]
