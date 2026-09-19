"""fileio/pdf_reporter 单元测试（offscreen Qt + reportlab）。"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from core.models import CuttingPattern, Part, Solution, Statistics, StockSpec
from fileio.pdf_reporter import _labels, _register_font, build_pdf

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


def _render_stub(painter: Any, pattern: CuttingPattern, scale: float) -> None:
    painter.fillRect(QRectF(8, 22, 1500, 28), QColor("#5B8FF9"))
    painter.drawText(QRectF(8, 50, 400, 20), 0, f"scale={scale:.3f}")


def _assert_pdf(path: Path, min_size: int = 1500) -> bytes:
    data = path.read_bytes()
    assert data.startswith(b"%PDF")
    assert b"%%EOF" in data[-1024:]
    assert len(data) > min_size
    return data


@pytest.mark.usefixtures("_qapp")
def test_build_pdf_with_render(tmp_path: Path) -> None:
    out = tmp_path / "r.pdf"
    build_pdf(str(out), _solution(), _PARTS, _STOCK, "zh_CN", _render_stub)
    _assert_pdf(out, min_size=5000)


@pytest.mark.usefixtures("_qapp")
def test_build_pdf_no_render(tmp_path: Path) -> None:
    out = tmp_path / "r2.pdf"
    build_pdf(str(out), _solution(), _PARTS, _STOCK, "zh_CN", None)
    _assert_pdf(out)


@pytest.mark.usefixtures("_qapp")
def test_build_pdf_en(tmp_path: Path) -> None:
    out = tmp_path / "r3.pdf"
    build_pdf(str(out), _solution(), _PARTS, _STOCK, "en_US", _render_stub)
    _assert_pdf(out)


def test_font_registered() -> None:
    assert _register_font() == "NotoSC"  # assets/fonts/NotoSansSC.ttf 已内嵌


def test_labels_both_langs() -> None:
    zh, en = _labels("zh_CN"), _labels("en_US")
    assert zh["report.title"] != en["report.title"]
    assert set(zh) == set(en)


@pytest.mark.usefixtures("_qapp")
def test_build_pdf_bad_path(tmp_path: Path) -> None:
    with pytest.raises(OSError):
        build_pdf(
            str(tmp_path / "no_dir" / "r.pdf"), _solution(), _PARTS, _STOCK, "zh_CN", _render_stub
        )
