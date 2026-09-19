"""结果统计与方案表格（详细设计 §5.3，M2）。

三区：统计区（一行大字号）/ 方案汇总表 / 零件核对表。
契约（决策 D8）：show_solution(sol, parts, stock, exact_mode=False)。
exact_mode=True 且解非数学最优（超时）时统计行追加「（当前最好，非最优）」；
面板自身不含任何求解/持久化逻辑，只负责展示。
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core import statistics
from core.models import Part, Solution, StockSpec
from i18n.translator import tr

_DIFF_BG = QBrush(QColor(255, 190, 110))  # 核对表差额≠0 橙色高亮
_MAX_DETAIL_CHARS = 120  # 方案表「切割明细」过长时截断显示，tooltip 保留全量


def _disp_name(idx: int, name: str) -> str:
    """匿名零件显示为 #序号（与设计 §5.2 录入区允许空名称一致）。"""
    return name if name else f"#{idx + 1}"


class ResultPanel(QWidget):
    """结果展示区。show_solution 一次性刷新三区；retranslate 即时重绘。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._sol: Solution | None = None
        self._parts: list[Part] = []
        self._stock: StockSpec | None = None
        self._exact_mode = False

        self.lbl_stats = QLabel()
        font = self.lbl_stats.font()
        font.setPointSizeF(font.pointSizeF() * 1.4)
        font.setBold(True)
        self.lbl_stats.setFont(font)

        self.tbl_patterns = self._make_table(4)
        self.tbl_check = self._make_table(5)

        layout = QVBoxLayout(self)
        layout.addWidget(self.lbl_stats)
        layout.addWidget(self.tbl_patterns, stretch=3)
        layout.addWidget(self.tbl_check, stretch=2)
        self.retranslate()

    # ================= 对外接口 =================
    def show_solution(
        self,
        sol: Solution | None,
        parts: list[Part],
        stock: StockSpec,
        exact_mode: bool = False,
    ) -> None:
        """一次性刷新三区；sol 为 None/空 patterns 时显示占位提示。"""
        self._sol = sol
        self._parts = list(parts)
        self._stock = stock
        self._exact_mode = exact_mode
        self._render()

    def retranslate(self) -> None:
        """语言切换：重设表头并按缓存数据重绘（不丢内容）。"""
        self.tbl_patterns.setHorizontalHeaderLabels(
            [
                tr("result.col_pattern"),
                tr("result.col_detail"),
                tr("result.col_remainder"),
                tr("result.col_bars"),
            ]
        )
        self.tbl_check.setHorizontalHeaderLabels(
            [
                tr("result.check_name"),
                tr("result.check_length"),
                tr("result.check_demand"),
                tr("result.check_cut"),
                tr("result.check_diff"),
            ]
        )
        self._render()

    # ================= 内部 =================
    @staticmethod
    def _make_table(cols: int) -> QTableWidget:
        t = QTableWidget(0, cols)
        t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        t.verticalHeader().setVisible(False)
        t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        t.horizontalHeader().setStretchLastSection(True)
        return t

    def _render(self) -> None:
        sol = self._sol
        if sol is None or not sol.patterns or self._stock is None:
            self.lbl_stats.setText(tr("result.empty"))
            self.tbl_patterns.setRowCount(0)
            self.tbl_check.setRowCount(0)
            return
        stats = sol.stats or statistics.compute(sol, self._parts, self._stock)
        line = tr(
            "result.stats",
            bars=stats.bars_used,
            util=f"{stats.utilization:.1f}",
            part_len=stats.total_part_len,
            kerf_loss=stats.kerf_loss,
            waste=stats.waste_len,
        )
        if sol.exact:
            line += "  " + tr("result.optimal")
        elif self._exact_mode:
            line += "  " + tr("result.not_optimal")
        self.lbl_stats.setText(line)
        self._fill_patterns(sol)
        self._fill_check(sol)

    def _pattern_detail(self, counts: dict[int, int]) -> str:
        segs = []
        for idx in sorted(counts):
            p = self._parts[idx]
            segs.append(f"{_disp_name(idx, p.name)} {p.length}×{counts[idx]}")
        return " + ".join(segs)

    def _fill_patterns(self, sol: Solution) -> None:
        t = self.tbl_patterns
        t.setUpdatesEnabled(False)
        try:
            t.setRowCount(len(sol.patterns))
            for r, pat in enumerate(sol.patterns):
                detail = self._pattern_detail(pat.counts)
                shown = (
                    detail
                    if len(detail) <= _MAX_DETAIL_CHARS
                    else detail[: _MAX_DETAIL_CHARS - 1] + "…"
                )
                cells = (str(r + 1), shown, str(pat.remainder), str(pat.bars))
                for c, txt in enumerate(cells):
                    item = QTableWidgetItem(txt)
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    if c == 1:
                        item.setToolTip(detail)
                    t.setItem(r, c, item)
        finally:
            t.setUpdatesEnabled(True)

    def _fill_check(self, sol: Solution) -> None:
        t = self.tbl_check
        # 每种零件实切总数 = Σ counts[i]*bars
        cut = [0] * len(self._parts)
        for pat in sol.patterns:
            for idx, n in pat.counts.items():
                cut[idx] += n * pat.bars
        t.setUpdatesEnabled(False)
        try:
            t.setRowCount(len(self._parts))
            for r, p in enumerate(self._parts):
                diff = cut[r] - p.qty
                cells = (
                    _disp_name(r, p.name),
                    str(p.length),
                    str(p.qty),
                    str(cut[r]),
                    str(diff),
                )
                for c, txt in enumerate(cells):
                    item = QTableWidgetItem(txt)
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    if diff != 0:
                        item.setBackground(_DIFF_BG)
                    t.setItem(r, c, item)
        finally:
            t.setUpdatesEnabled(True)


__all__ = ["ResultPanel"]
