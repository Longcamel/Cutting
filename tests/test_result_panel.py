"""ui/result_panel 单元测试（offscreen Qt）。"""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QTableWidget, QTableWidgetItem

from core.models import CuttingPattern, Part, Solution, StockSpec
from i18n.translator import _reset_for_test, set_language, tr
from ui.result_panel import ResultPanel


def _cell(t: QTableWidget, r: int, c: int) -> QTableWidgetItem:
    it = t.item(r, c)
    assert it is not None, f"({r},{c}) 无单元格"
    return it


def _header(t: QTableWidget, c: int) -> QTableWidgetItem:
    it = t.horizontalHeaderItem(c)
    assert it is not None, f"列头 {c} 不存在"
    return it

_STOCK = StockSpec(length=6000, kerf=3)
_PARTS = [Part(length=1500, qty=4, name="A"), Part(length=1000, qty=3, name="B")]


def _solution(exact: bool = False) -> Solution:
    # p1: A1500×3 + B1000×1（余 1494）；p2: A1500×1 + B1000×2（余 3497）
    sol = Solution(
        patterns=[
            CuttingPattern(counts={0: 3, 1: 1}, remainder=1494, bars=1),
            CuttingPattern(counts={0: 1, 1: 2}, remainder=3497, bars=1),
        ],
        exact=exact,
    )
    return sol


@pytest.fixture
def panel(qtbot) -> ResultPanel:
    _reset_for_test()
    set_language("zh_CN")
    w = ResultPanel()
    qtbot.addWidget(w)
    return w


def test_empty_shows_placeholder(panel: ResultPanel) -> None:
    panel.show_solution(None, [], _STOCK)
    assert panel.lbl_stats.text() == tr("result.empty")
    assert panel.tbl_patterns.rowCount() == 0
    assert panel.tbl_check.rowCount() == 0


def test_stats_line_exact_flag(panel: ResultPanel) -> None:
    panel.show_solution(_solution(exact=True), _PARTS, _STOCK, exact_mode=True)
    txt = panel.lbl_stats.text()
    assert "原料根数 2" in txt
    assert tr("result.optimal") in txt
    # 利用率 = (4*1500+3*1000) / (2*6000) = 9000/12000 = 75%
    assert "75.0" in txt


def test_stats_not_optimal_mark(panel: ResultPanel) -> None:
    panel.show_solution(_solution(exact=False), _PARTS, _STOCK, exact_mode=True)
    assert tr("result.not_optimal") in panel.lbl_stats.text()
    panel.show_solution(_solution(exact=False), _PARTS, _STOCK, exact_mode=False)
    txt = panel.lbl_stats.text()
    assert tr("result.not_optimal") not in txt
    assert tr("result.optimal") not in txt


def test_pattern_table_rows(panel: ResultPanel) -> None:
    panel.show_solution(_solution(), _PARTS, _STOCK)
    t = panel.tbl_patterns
    assert t.rowCount() == 2
    assert _cell(t, 0, 0).text() == "1"
    assert _cell(t, 0, 1).text() == "A 1500×3 + B 1000×1"
    assert _cell(t, 0, 2).text() == "1494"
    assert _cell(t, 1, 3).text() == "1"
    # tooltip 保留全量明细
    assert _cell(t, 0, 1).toolTip() == "A 1500×3 + B 1000×1"


def test_check_table_diff_highlight(panel: ResultPanel) -> None:
    sol = _solution()
    # 把需求改大 1 使差额≠0：A 需求 5，实切 4，diff=-1
    parts = [Part(length=1500, qty=5, name="A"), Part(length=1000, qty=3, name="B")]
    panel.show_solution(sol, parts, _STOCK)
    t = panel.tbl_check
    assert t.rowCount() == 2
    assert _cell(t, 0, 3).text() == "4" and _cell(t, 0, 4).text() == "-1"
    assert _cell(t, 0, 4).background().style() != Qt.BrushStyle.NoBrush
    assert _cell(t, 1, 4).text() == "0"
    assert _cell(t, 1, 4).background().style() == Qt.BrushStyle.NoBrush


def test_anonymous_part_shows_index(panel: ResultPanel) -> None:
    parts = [Part(length=1500, qty=1, name="")]
    sol = Solution(patterns=[CuttingPattern(counts={0: 1}, remainder=4497, bars=1)])
    panel.show_solution(sol, parts, _STOCK)
    assert _cell(panel.tbl_patterns, 0, 1).text() == "#1 1500×1"
    assert _cell(panel.tbl_check, 0, 0).text() == "#1"


def test_retranslate_keeps_content(panel: ResultPanel) -> None:
    panel.show_solution(_solution(exact=True), _PARTS, _STOCK, exact_mode=True)
    set_language("en_US")
    panel.retranslate()
    assert _header(panel.tbl_patterns, 1).text() == tr("result.col_detail")
    assert panel.tbl_patterns.rowCount() == 2  # 内容未丢
    assert "Bars 2" in panel.lbl_stats.text()
    _reset_for_test()
    set_language("zh_CN")


def test_large_solution_fast(qtbot) -> None:
    import time

    parts = [Part(length=700, qty=3000, name=f"P{i}") for i in range(30)]
    patterns = []
    for r in range(1000):  # 千行方案表
        counts = {(r + k) % 30: 2 for k in range(4)}
        patterns.append(CuttingPattern(counts=counts, remainder=100, bars=1))
    sol = Solution(patterns=patterns)
    w = ResultPanel()
    qtbot.addWidget(w)
    t0 = time.perf_counter()
    w.show_solution(sol, parts, _STOCK)
    QApplication.processEvents()
    elapsed = time.perf_counter() - t0
    assert w.tbl_patterns.rowCount() == 1000
    assert elapsed < 1.0, f"千行刷新 {elapsed:.2f}s"
