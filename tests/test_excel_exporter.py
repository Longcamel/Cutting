"""fileio/excel_exporter 单元测试（offscreen Qt + openpyxl/PIL）。"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import pytest
from openpyxl import load_workbook
from openpyxl.worksheet.worksheet import Worksheet
from PySide6.QtWidgets import QApplication

from core.models import CuttingPattern, Part, Solution, Statistics, StockSpec
from fileio.excel_exporter import save_report
from ui.cutting_view import render_bar

_STOCK = StockSpec(length=6000, kerf=3, material="Q235", company="ACME", project="P-01")
_PARTS = [Part(1500, 6, "A"), Part(1000, 2, "")]


@pytest.fixture(scope="module")
def _qapp() -> Iterator[QApplication]:
    app = QApplication.instance() or QApplication([])
    yield cast("QApplication", app)


def _solution() -> Solution:
    sol = Solution(
        patterns=[
            CuttingPattern(counts={0: 3, 1: 1}, remainder=1491, bars=2),
            CuttingPattern(counts={1: 2}, remainder=3994, bars=1),
        ],
        exact=True,
    )
    sol.stats = Statistics(
        bars_used=3,
        total_stock_len=18000,
        total_part_len=11000,
        kerf_loss=24,
        waste_len=6976,
        utilization=61.1,
    )
    return sol


def _render_adapter(painter: Any, pattern: CuttingPattern, scale: float) -> None:
    render_bar(painter, pattern, _PARTS, _STOCK, scale)


@pytest.mark.usefixtures("_qapp")
def test_save_report_with_diagrams(tmp_path: Path) -> None:
    out = tmp_path / "r.xlsx"
    save_report(str(out), _solution(), _PARTS, _STOCK, "zh_CN", render_bar=_render_adapter)
    wb = load_workbook(out)
    assert len(wb.sheetnames) == 4 and wb.sheetnames[-1] == "切割示意图"
    ws = cast(Worksheet, wb["切割示意图"])
    assert len(ws._images) == 2  # type: ignore[attr-defined]  # noqa: SLF001  # 每切法一张图
    assert ws.cell(row=1, column=1).value == "切法 1（×2 根）"


def test_save_report_no_render_compat(tmp_path: Path) -> None:
    out = tmp_path / "r2.xlsx"
    save_report(str(out), _solution(), _PARTS, _STOCK, "zh_CN")
    wb = load_workbook(out)
    assert len(wb.sheetnames) == 3


@pytest.mark.usefixtures("_qapp")
def test_save_report_diagrams_en(tmp_path: Path) -> None:
    out = tmp_path / "r3.xlsx"
    save_report(str(out), _solution(), _PARTS, _STOCK, "en_US", render_bar=_render_adapter)
    wb = load_workbook(out)
    assert "Cutting Diagrams" in wb.sheetnames
    ws = cast(Worksheet, wb["Cutting Diagrams"])
    assert len(ws._images) == 2  # type: ignore[attr-defined]  # noqa: SLF001
    assert ws.cell(row=1, column=1).value == "Pattern 1 (×2 bars)"


def test_render_fn_type_alias_importable() -> None:
    from fileio.excel_exporter import RenderBarFn  # noqa: F401
    assert RenderBarFn is not None  # 仅确认模块导入链无 PySide6 顶层依赖
