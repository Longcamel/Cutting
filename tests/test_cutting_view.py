"""ui/cutting_view 单元测试（offscreen Qt）。"""

from __future__ import annotations

import pytest
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication, QGraphicsRectItem, QGraphicsSimpleTextItem

from core.models import CuttingPattern, Part, Solution, StockSpec
from i18n.translator import _reset_for_test, set_language
from ui import cutting_view
from ui.cutting_view import (
    PALETTE,
    CuttingView,
    content_height,
    render_to_painter,
)

_STOCK = StockSpec(length=6000, kerf=3)
_PARTS = [Part(1500, 3, "A"), Part(1000, 1, "B")]


@pytest.fixture(autouse=True)
def _lang():
    _reset_for_test()
    set_language("zh_CN")
    yield
    _reset_for_test()


def _solution() -> Solution:
    return Solution(
        patterns=[
            CuttingPattern(counts={0: 3, 1: 1}, remainder=1494, bars=2),
            CuttingPattern(counts={1: 2}, remainder=3994, bars=1),
        ]
    )


@pytest.fixture
def view(qtbot):
    v = CuttingView()
    v.resize(700, 300)
    qtbot.addWidget(v)
    return v


def test_scene_rows_and_remainder(view: CuttingView) -> None:
    view.show_solution(_solution(), _PARTS, _STOCK)
    rects = [it for it in view._scene.items() if isinstance(it, QGraphicsRectItem)]
    # 行1: 3+1段+余料=5；行2: 2段+余料=3
    assert len(rects) == 8
    gray = QColor("#D9D9D9")
    rem = [r for r in rects if r.brush().color() == gray]
    assert len(rem) == 2  # 两行都有余料段
    # 余料 tooltip 带「余料」字样
    assert any("余料" in r.toolTip() for r in rem)


def test_palette_consistency(view: CuttingView) -> None:
    view.show_solution(_solution(), _PARTS, _STOCK)
    rects = [it for it in view._scene.items() if isinstance(it, QGraphicsRectItem)]
    c0 = QColor(PALETTE[0 % len(PALETTE)])
    c1 = QColor(PALETTE[1 % len(PALETTE)])
    same0 = [r for r in rects if r.brush().color() == c0]
    same1 = [r for r in rects if r.brush().color() == c1]
    assert len(same0) == 3 and len(same1) == 3  # A×3；B×1+×2


def test_bars_label_and_ruler(view: CuttingView) -> None:
    view.show_solution(_solution(), _PARTS, _STOCK)
    texts = [it.text() for it in view._scene.items() if isinstance(it, QGraphicsSimpleTextItem)]
    assert "×2 根" in texts and "×1 根" in texts
    assert "0" in texts and "3000" in texts and "6000" in texts


def test_clear_on_none(view: CuttingView) -> None:
    view.show_solution(_solution(), _PARTS, _STOCK)
    view.show_solution(None, _PARTS, _STOCK)
    assert len(view._scene.items()) == 0


def test_render_to_painter_matches_layout() -> None:
    sol = _solution()
    h = content_height(sol)
    img = QImage(600, h + 10, QImage.Format.Format_ARGB32)
    img.fill(0xFFFFFFFF)
    p = QPainter(img)
    drawn = render_to_painter(p, sol, _PARTS, _STOCK, 600)
    p.end()
    assert drawn > 0
    # 与 content_height 相差不超过一行
    assert abs(drawn - h) <= 34
    # 图上有非白色像素（确实画了东西）
    colors = {img.pixelColor(x, y).name() for x in (8, 100, 300) for y in (30, 40, 60)}
    assert colors - {"#ffffff"}


def test_retranslate_keeps_content(view: CuttingView) -> None:
    view.show_solution(_solution(), _PARTS, _STOCK)
    set_language("en_US")
    view.retranslate()
    texts = [it.text() for it in view._scene.items() if isinstance(it, QGraphicsSimpleTextItem)]
    assert "×2 bars" in texts


def test_large_solution_perf(qtbot) -> None:
    import time

    pats = [CuttingPattern(counts={0: 3, 1: 1}, remainder=1494, bars=10) for _ in range(120)]
    sol = Solution(patterns=pats)
    v = CuttingView()
    v.resize(700, 300)
    qtbot.addWidget(v)
    t0 = time.perf_counter()
    v.show_solution(sol, _PARTS, _STOCK)
    assert time.perf_counter() - t0 < 1.0
    rects = [it for it in v._scene.items() if isinstance(it, QGraphicsRectItem)]
    assert len(rects) == 120 * 5


def test_render_bar_draws_at_exact_scale(qapp: QApplication) -> None:
    """render_bar：给定 px_per_mm 精确缩放，复用整行布局，返回正高度。"""
    parts = [Part(1000, 3, "A"), Part(500, 2, "B")]
    stock = StockSpec(6000, 3)
    pat = CuttingPattern(counts={0: 2, 1: 1}, bars=2, remainder=3497)
    img = QImage(1400, 200, QImage.Format.Format_ARGB32)
    img.fill(QColor("white"))
    painter = QPainter(img)
    h = cutting_view.render_bar(painter, pat, parts, stock, 0.2)
    painter.end()
    assert h > 0
    # 条体区域应有非白像素（证明确实按布局画出）
    assert any(img.pixelColor(x, 40) != QColor("white") for x in range(60, 1300, 20))
