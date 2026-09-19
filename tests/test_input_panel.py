"""ui/input_panel 单元测试（offscreen Qt）。"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QTableWidgetItem

from app.controller import AppController
from core.models import Part, Solution, StockSpec
from core.solver_base import ProgressCB, SolverBase
from fileio.settings import SettingsStore
from i18n.translator import _reset_for_test, set_language
from ui.input_panel import InputPanel


class _FakeSolver(SolverBase):
    def solve(
        self,
        parts: list[Part],
        stock: StockSpec,
        on_progress: ProgressCB | None = None,
        cancel: threading.Event | None = None,
    ) -> Solution:
        return Solution(patterns=[])


def _controller(tmp_path: Path, **over) -> AppController:
    st = SettingsStore(tmp_path / "settings.json")
    st.data.update(over)
    return AppController(st, lambda mode: _FakeSolver())


@pytest.fixture
def panel(qtbot, tmp_path):
    ctl = _controller(
        tmp_path,
        stock_length=9000,
        kerf=4,
        material="Q235",
        company="ACME",
        project="P1",
        mode="fast",
    )
    w = InputPanel(ctl)
    qtbot.addWidget(w)
    yield w, ctl
    _reset_for_test()
    set_language("zh_CN")


def _fill_row(panel: InputPanel, row: int, name: str, length: str, qty: str) -> None:
    t = panel.table
    while t._data_rows <= row:
        t.add_row()
    t.setItem(row, 0, QTableWidgetItem(name))
    t.setItem(row, 1, QTableWidgetItem(length))
    t.setItem(row, 2, QTableWidgetItem(qty))


# ---- 参数区 ----
def test_params_restored_from_controller(panel):
    w, ctl = panel
    assert w.spin_stock.value() == 9000
    assert w.spin_kerf.value() == 4
    assert w.edit_material.text() == "Q235"
    assert w.edit_company.text() == "ACME"
    assert w.edit_project.text() == "P1"
    assert w.radio_fast.isChecked()


def test_param_change_pushes_back_and_persists(panel):
    w, ctl = panel
    w.spin_stock.setValue(7000)
    w.spin_kerf.setValue(0)
    w.edit_material.setText("SUS304")
    assert ctl.stock.length == 7000
    assert ctl.stock.kerf == 0
    assert ctl.stock.material == "SUS304"
    assert ctl._settings.data["stock_length"] == 7000
    assert ctl._settings.data["kerf"] == 0


def test_mode_switch_persists(panel):
    w, ctl = panel
    w.radio_exact.setChecked(True)
    assert ctl.mode == "exact"
    assert ctl._settings.data["mode"] == "exact"


# ---- 表格行操作 ----
def test_add_and_delete_row(panel):
    w, _ = panel
    t = w.table
    base = t.rowCount()  # 首数据行 + 加行
    t.add_row()
    t.add_row()
    assert t.rowCount() == base + 2
    t.delete_row(0)
    assert t.rowCount() == base + 1


def test_add_requested_appends_rows(panel):
    w, _ = panel
    w.table.addRequested.emit([("轴", "100", "2"), ("", "50", "1")])
    assert w.table.item(0, 0).text() == "轴"
    assert w.table.item(1, 1).text() == "50"


def test_paste_multi_row(panel):
    w, _ = panel
    QApplication.clipboard().setText("轴\t100\t2\n管\t60\t5\n")
    w.table.setCurrentCell(0, 0)
    w.table._paste_clipboard()
    t = w.table
    assert t.item(0, 0).text() == "轴"
    assert t.item(0, 1).text() == "100"
    assert t.item(0, 2).text() == "2"
    assert t.item(1, 0).text() == "管"
    assert t.item(1, 2).text() == "5"


# ---- collect ----
def test_collect_valid(panel):
    w, ctl = panel
    _fill_row(w, 0, "轴", "1500", "3")
    parts, stock = w.collect()
    assert parts[0].length == 1500 and parts[0].qty == 3 and parts[0].name == "轴"
    assert stock.length == 9000 and stock.kerf == 4
    assert ctl.parts == parts


def test_collect_skips_empty_rows(panel):
    w, _ = panel
    _fill_row(w, 0, "", "", "")  # 全空行应跳过，无错误
    parts, _ = w.collect()
    assert parts == []


def test_collect_invalid_highlights_and_emits(panel, qtbot):
    w, _ = panel
    _fill_row(w, 0, "x" * 60, "abc", "0")  # 名称超长+长度非法+数量非法
    with qtbot.waitSignal(w.issuesFound, timeout=1000) as blk:
        parts, _ = w.collect()
    assert parts == []
    codes = [i.code for i in blk.args[0]]
    assert codes.count("E002") == 3
    for c in range(3):
        item = w.table.item(0, c)
        assert item is not None and item.background().color().isValid()
    w.table.addRequested.emit([("a", "10", "1")])  # 新增行应清除高亮
    for r in range(2):
        for c in range(3):
            it = w.table.item(r, c)
            assert it is not None and it.background().style() == Qt.BrushStyle.NoBrush


# ---- 模式/求解 ----
def test_exact_mode_over_25_kinds_proceeds(panel, qtbot, monkeypatch):
    # 上限拦截已解除：>25 种精确模式直接开始求解，不再弹 E008
    w, ctl = panel
    w.radio_exact.setChecked(True)
    for i in range(26):
        w.table.add_row()
        _fill_row(w, i, f"p{i}", "100", "1")
    called = {}

    def fake_start(mode, on_progress, on_done, on_error):
        called["mode"] = mode

    monkeypatch.setattr(ctl, "start_solve", fake_start)
    with qtbot.waitSignal(w.solveRequested, timeout=1000):
        w._on_calc_clicked()
    assert called["mode"] == "exact"


def test_calc_click_starts_solve_and_toggles(panel, qtbot, monkeypatch):
    w, ctl = panel
    _fill_row(w, 0, "轴", "100", "1")
    called = {}

    def fake_start(mode, on_progress, on_done, on_error):
        called["mode"] = mode

    monkeypatch.setattr(ctl, "start_solve", fake_start)
    with qtbot.waitSignal(w.solveRequested, timeout=1000):
        w.btn_calc.click()
    assert called["mode"] == "fast"
    assert w._solving is True
    assert w.btn_calc.text() != ""  # 已切为「正在计算」文案
    assert not w.btn_calc.isEnabled()  # 求解中按钮禁用，取消走状态栏取消按钮


def test_invalid_input_blocks_solve(panel, qtbot):
    w, ctl = panel
    _fill_row(w, 0, "", "-5", "1")
    with qtbot.waitSignal(w.issuesFound, timeout=1000):
        w.btn_calc.click()
    assert w._solving is False


def test_language_switch_retranslates(panel):
    w, _ = panel
    old = w.btn_calc.text()
    set_language("en_US")
    QApplication.processEvents()
    assert w.btn_calc.text() != old
    assert w.table.horizontalHeaderItem(1).text() == "Length mm"
