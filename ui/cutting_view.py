"""切割示意图自绘控件（详细设计 §5.4，M2）。

契约（决策 D9）：
- show_solution(sol, parts, stock) —— 段内要显示零件名称，故签名含 parts
  （任务单原文未含，与 result_panel 保持一致）；
- render_to_painter(painter, sol, parts, stock, width_px) -> int 总高，
  供 pdf_reporter 注入复用，屏幕图与 PDF 图走同一 _row_segments 布局函数。
"""

from __future__ import annotations

from collections.abc import Iterator

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFontMetrics, QPainter, QPen, QResizeEvent
from PySide6.QtWidgets import (
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QWidget,
)

from core.models import CuttingPattern, Part, Solution, StockSpec
from i18n.translator import tr

# 20 色调色板，按 part_idx 循环（§5.4）
PALETTE: tuple[str, ...] = (
    "#5B8FF9",
    "#61DDAA",
    "#65789B",
    "#F6BD16",
    "#7262FD",
    "#78D3F8",
    "#9661BC",
    "#F6903D",
    "#008685",
    "#F08BB4",
    "#5AD8A6",
    "#5D7092",
    "#F4664A",
    "#6DC8EC",
    "#945FB9",
    "#FF9D4D",
    "#269A99",
    "#FF99C3",
    "#5B8FF9",
    "#BDD2FD",
)
REMAINDER_COLOR = QColor("#D9D9D9")  # 余料浅灰

ROW_H = 28
ROW_GAP = 6
RULER_H = 22  # 顶部 mm 刻度尺高度
MARGIN = 8
LABEL_W = 64  # 右侧「×N 根」标签宽
_MIN_SEG_PX = 1


def _seg_color(part_idx: int) -> QColor:
    return QColor(PALETTE[part_idx % len(PALETTE)])


def _part_label(parts: list[Part], idx: int) -> str:
    name = parts[idx].name if idx < len(parts) else ""
    return name if name else f"#{idx + 1}"


def _row_segments(
    pat: CuttingPattern, parts: list[Part], stock: StockSpec, px_per_mm: float
) -> Iterator[tuple[float, float, int]]:
    """展开一行的段为 (x, width, part_idx)；part_idx=-1 表示余料。"""
    x = 0.0
    for idx in sorted(pat.counts):
        for _ in range(pat.counts[idx]):
            length = parts[idx].length if idx < len(parts) else 0
            w = max(_MIN_SEG_PX, length * px_per_mm)
            yield x, w, idx
            x += w + max(0.0, stock.kerf * px_per_mm)
    if pat.remainder > 0:
        yield x, max(_MIN_SEG_PX, pat.remainder * px_per_mm), -1


def _fit_text(fm: QFontMetrics, full: str, length: int, width: float) -> str:
    """逐级省略：名称+长度 → 仅长度 → 空。"""
    if width >= fm.horizontalAdvance(full) + 6:
        return full
    short = str(length)
    if width >= fm.horizontalAdvance(short) + 6:
        return short
    return ""


def content_height(sol: Solution) -> int:
    """给定方案的行布局总高（含刻度尺与边距）。"""
    rows = len(sol.patterns)
    return RULER_H + MARGIN + rows * (ROW_H + ROW_GAP) + MARGIN


def render_to_painter(
    painter: QPainter,
    sol: Solution,
    parts: list[Part],
    stock: StockSpec,
    width_px: float,
) -> int:
    """把整页示意图画到任意 QPainter（屏幕/PDF 共用），返回绘制总高。"""
    bar_w = max(1.0, width_px - 2 * MARGIN - LABEL_W)
    px_per_mm = bar_w / max(1, stock.length)
    fm = QFontMetrics(painter.font())

    # 顶部刻度尺：0 / L/2 / L
    painter.setPen(QPen(QColor("#888888")))
    half = f"{stock.length // 2}"
    for xoff, text, anchor in (
        (0.0, "0", Qt.AlignmentFlag.AlignLeft),
        (bar_w / 2, half, Qt.AlignmentFlag.AlignHCenter),
        (bar_w, str(stock.length), Qt.AlignmentFlag.AlignRight),
    ):
        rect = QRectF(MARGIN + xoff - 40, 0, 80, RULER_H)
        painter.drawText(rect, int(anchor | Qt.AlignmentFlag.AlignVCenter), text)

    y = float(RULER_H)
    for i, pat in enumerate(sol.patterns):
        # 行标题
        painter.setPen(QPen(QColor("#333333")))
        painter.drawText(
            QRectF(0, y - 14, MARGIN + bar_w, 14),
            int(Qt.AlignmentFlag.AlignLeft),
            f"#{i + 1}",
        )
        for x, w, idx in _row_segments(pat, parts, stock, px_per_mm):
            rect = QRectF(MARGIN + x, y, w, ROW_H)
            painter.setPen(QPen(QColor("#FFFFFF")))
            painter.setBrush(QBrush(REMAINDER_COLOR) if idx < 0 else QBrush(_seg_color(idx)))
            painter.drawRect(rect)
            if idx < 0:
                tip_full = f"{tr('result.remainder')} {pat.remainder}"
                painter.setPen(QPen(QColor("#666666")))
                text = _fit_text(fm, tip_full, pat.remainder, w)
            else:
                label = _part_label(parts, idx)
                length = parts[idx].length if idx < len(parts) else 0
                painter.setPen(QPen(QColor("#FFFFFF")) if idx >= 0 else painter.pen())
                text = _fit_text(fm, f"{label} {length}", length, w)
            if text:
                painter.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), text)
        # 右侧「×N 根」
        painter.setPen(QPen(QColor("#333333")))
        painter.drawText(
            QRectF(MARGIN + bar_w + 4, y, LABEL_W, ROW_H),
            int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
            tr("result.bars_suffix", n=pat.bars),
        )
        y += ROW_H + ROW_GAP
    return int(y + MARGIN)


class CuttingView(QGraphicsView):
    """切割示意图控件（QGraphicsView 视口机制，大方案只绘可见区）。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        self._sol: Solution | None = None
        self._parts: list[Part] = []
        self._stock: StockSpec | None = None

    def show_solution(
        self, sol: Solution | None, parts: list[Part], stock: StockSpec | None
    ) -> None:
        """重绘整图；sol=None 时清空。"""
        self._sol, self._parts, self._stock = sol, parts, stock
        self._redraw()

    def retranslate(self) -> None:
        self._redraw()

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self._sol is not None:
            self._redraw()

    def _redraw(self) -> None:
        self._scene.clear()
        if self._sol is None or self._stock is None:
            return
        width = max(200, self.viewport().width() - 4)
        self._draw_scene(self._sol, self._parts, self._stock, float(width))
        self._scene.setSceneRect(0, 0, width, content_height(self._sol))

    def _draw_scene(
        self, sol: Solution, parts: list[Part], stock: StockSpec, width_px: float
    ) -> None:
        """与 render_to_painter 共用 _row_segments 几何，保证屏幕/PDF 一致。"""
        bar_w = max(1.0, width_px - 2 * MARGIN - LABEL_W)
        px_per_mm = bar_w / max(1, stock.length)
        fm = QFontMetrics(self.font())

        ruler = ((0.0, "0"), (bar_w / 2, str(stock.length // 2)), (bar_w, str(stock.length)))
        for xoff, text in ruler:
            item = QGraphicsSimpleTextItem(text)
            item.setBrush(QBrush(QColor("#888888")))
            tw = item.boundingRect().width()
            item.setPos(MARGIN + xoff - tw * (xoff / bar_w if bar_w else 0), 0)
            self._scene.addItem(item)

        y = float(RULER_H)
        for i, pat in enumerate(sol.patterns):
            title = QGraphicsSimpleTextItem(f"#{i + 1}")
            title.setBrush(QBrush(QColor("#333333")))
            title.setPos(0, y - 14)
            self._scene.addItem(title)
            for x, w, idx in _row_segments(pat, parts, stock, px_per_mm):
                seg = QGraphicsRectItem(MARGIN + x, y, w, ROW_H)
                if idx < 0:
                    seg.setBrush(QBrush(REMAINDER_COLOR))
                    full = f"{tr('result.remainder')} {pat.remainder}"
                    seg.setToolTip(full)
                    text = _fit_text(fm, full, pat.remainder, w)
                    tcolor = QColor("#666666")
                else:
                    seg.setBrush(QBrush(_seg_color(idx)))
                    label = _part_label(parts, idx)
                    length = parts[idx].length if idx < len(parts) else 0
                    full = f"{label} {length}"
                    seg.setToolTip(full)
                    text = _fit_text(fm, full, length, w)
                    tcolor = QColor("#FFFFFF")
                seg.setPen(QPen(QColor("#FFFFFF")))
                self._scene.addItem(seg)
                if text:
                    t = QGraphicsSimpleTextItem(text)
                    t.setBrush(QBrush(tcolor))
                    tw = t.boundingRect().width()
                    th = t.boundingRect().height()
                    t.setPos(
                        MARGIN + x + (w - tw) / 2,
                        y + (ROW_H - th) / 2,
                    )
                    self._scene.addItem(t)
            lbl = QGraphicsSimpleTextItem(tr("result.bars_suffix", n=pat.bars))
            lbl.setBrush(QBrush(QColor("#333333")))
            lbl.setPos(MARGIN + bar_w + 4, y + (ROW_H - lbl.boundingRect().height()) / 2)
            self._scene.addItem(lbl)
            y += ROW_H + ROW_GAP


__all__ = ["CuttingView", "PALETTE", "content_height", "render_bar", "render_to_painter"]


def render_bar(
    painter: QPainter,
    pattern: CuttingPattern,
    parts: list[Part],
    stock: StockSpec,
    px_per_mm: float,
) -> int:
    """单条切法画到 painter 当前原点（决策 D11：PDF 注入契约）。

    按给定 px_per_mm 精确缩放，复用 render_to_painter 的整行布局
    （含行标题、刻度尺、「×N 根」标签），返回绘制高度，纵向排版由调用方控制。
    """
    sol = Solution(patterns=[pattern])
    width_px = stock.length * px_per_mm + 2 * MARGIN + LABEL_W
    return render_to_painter(painter, sol, parts, stock, width_px)
