"""PDF 报告生成（详细设计 §6.3，决策 D11）。

A4 纵向，reportlab platypus：
1. 抬头：公司/项目/材料/日期 + 统计摘要（与界面 result.stats 同串）
2. 零件核对表（名称/长度/需求/实切/差额）
3. 每种切法一张示意图位图 —— 由 main_window 注入的 render_bar 画到
   QImage 再嵌 PNG（fileio 不 import PySide6 于模块层，仅惰性局部 import）。

中文用 assets/fonts/NotoSansSC.ttf 内嵌字体；缺失时回退 CID 字体
STSong-Light（不内嵌，依赖阅读器）。
"""

from __future__ import annotations

import json
import logging
import shutil
import sys
import tempfile
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from core.models import CuttingPattern, Part, Solution, StockSpec

if TYPE_CHECKING:  # pragma: no cover
    pass

_logger = logging.getLogger(__name__)

_FONT_NAME = "NotoSC"
_FONT_CANDIDATES = ("NotoSansSC.ttf",)
_IMG_CONTENT_W = 1500  # 单条切法图内容区目标像素宽（px_per_mm 由此反推）
_IMG_MAX_H = 160  # 位图逻辑高度上限（实际绘制约 72，余量后裁剪白边）
_SUPERSAMPLE = 3
_CHECK_GRID = 0.4


class _RenderBarFn(Protocol):
    def __call__(self, painter: Any, pattern: CuttingPattern, scale: float) -> None: ...


def _labels(lang: str) -> dict[str, str]:
    path = Path(__file__).resolve().parent.parent / "i18n" / f"{lang}.json"
    raw: dict[str, object] = json.loads(path.read_text(encoding="utf-8"))
    return {k: str(v) for k, v in raw.items()}


def _t(labels: dict[str, str], key: str, **kw: object) -> str:
    s = labels.get(key, key)
    return s.format(**kw) if kw else s


def _disp_name(idx: int, name: str) -> str:
    return name if name else f"#{idx + 1}"


def _register_font() -> str:
    """注册中文字体，返回字体名；TTF 缺失时回退 CID 字体。"""
    if _FONT_NAME in pdfmetrics.getRegisteredFontNames():
        return _FONT_NAME
    roots = [
        Path(getattr(sys, "_MEIPASS", "")) / "assets" / "fonts",  # PyInstaller
        Path(__file__).resolve().parent.parent / "assets" / "fonts",
    ]
    from reportlab.pdfbase.ttfonts import TTFont

    for root in roots:
        for name in _FONT_CANDIDATES:
            fp = root / name
            if fp.is_file():
                pdfmetrics.registerFont(TTFont(_FONT_NAME, str(fp)))
                return _FONT_NAME
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont

    fallback = "STSong-Light"
    pdfmetrics.registerFont(UnicodeCIDFont(fallback))
    _logger.warning("内嵌中文字体缺失，回退 CID 字体 %s（不内嵌）", fallback)
    return fallback


def _bar_png(
    pattern: CuttingPattern, stock: StockSpec, render_bar: _RenderBarFn, tmp: str
) -> tuple[str, int, int]:
    """调注入的 render_bar 画到 QImage，裁剪白边后存 PNG，返回 (路径, 宽px, 高px)。"""
    from PySide6.QtGui import QColor, QImage, QPainter  # 惰性：fileio 模块层不依赖 PySide6

    scale = _IMG_CONTENT_W / max(1, stock.length)
    w = _IMG_CONTENT_W + 2 * 8 + 64 + 8  # 内容 + 2*MARGIN + LABEL_W + 余量
    img = QImage(w * _SUPERSAMPLE, _IMG_MAX_H * _SUPERSAMPLE, QImage.Format.Format_RGB32)
    img.fill(QColor("#FFFFFF"))
    painter = QPainter(img)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.scale(_SUPERSAMPLE, _SUPERSAMPLE)
        render_bar(painter, pattern, scale)
    finally:
        painter.end()

    img = _crop_white(img)
    px_w, px_h = img.width(), img.height()
    path = str(Path(tmp) / f"bar_{id(pattern)}.png")
    img.save(path, "PNG")
    return path, px_w, px_h


def _crop_white(img: Any) -> Any:
    """裁掉底部/右侧纯白像素行。"""
    import numpy as np

    w, h = img.width(), img.height()
    ptr = img.constBits()
    arr = np.frombuffer(ptr, dtype=np.uint8, count=h * w * 4).reshape(h, w, 4)
    rgb = arr[:, :, :3]
    nonwhite = (rgb != 255).any(axis=2)
    rows = np.nonzero(nonwhite.any(axis=1))[0]
    cols = np.nonzero(nonwhite.any(axis=0))[0]
    if rows.size == 0 or cols.size == 0:
        return img
    pad = 2 * _SUPERSAMPLE
    bottom = min(h, int(rows[-1]) + pad + 1)
    right = min(w, int(cols[-1]) + pad + 1)
    return img.copy(0, 0, right, bottom)


def _check_rows(sol: Solution, parts: list[Part]) -> list[list[str]]:
    return [
        [
            _disp_name(i, p.name),
            str(p.length),
            str(p.qty),
            str(_cut_of(sol, i)),
            str(_cut_of(sol, i) - p.qty),
        ]
        for i, p in enumerate(parts)
    ]


def _cut_of(sol: Solution, idx: int) -> int:
    return sum(pat.counts.get(idx, 0) * pat.bars for pat in sol.patterns)


def build_pdf(
    path: str,
    sol: Solution,
    parts: list[Part],
    stock: StockSpec,
    lang: str,
    render_bar: _RenderBarFn | None = None,
) -> None:
    """生成 A4 纵向 PDF 报告。写入异常原样上抛（controller 归 E007）。"""
    lb = _labels(lang)
    font = _register_font()
    title_style = ParagraphStyle("t", fontName=font, fontSize=15, spaceAfter=6)
    normal = ParagraphStyle("n", fontName=font, fontSize=9.5, leading=14)

    doc = SimpleDocTemplate(
        path,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        title=_t(lb, "report.title"),
    )
    story: list[Any] = [Paragraph(_t(lb, "report.title"), title_style)]

    meta = [
        [_t(lb, "report.company"), stock.company],
        [_t(lb, "report.project"), stock.project],
        [_t(lb, "report.material"), stock.material],
        [_t(lb, "report.stock_length"), str(stock.length)],
        [_t(lb, "report.kerf"), str(stock.kerf)],
        [_t(lb, "report.date"), date.today().isoformat()],
    ]
    meta_tbl = Table(meta, colWidths=[doc.width * 0.22, doc.width * 0.78])
    meta_tbl.setStyle(_table_style(font, header=False))
    story.append(meta_tbl)

    stats = sol.stats
    if stats is not None:
        story.append(Spacer(1, 4))
        story.append(
            Paragraph(
                _t(
                    lb,
                    "result.stats",
                    bars=stats.bars_used,
                    util=f"{stats.utilization:.1f}",
                    part_len=stats.total_part_len,
                    kerf_loss=stats.kerf_loss,
                    waste=stats.waste_len,
                ),
                normal,
            )
        )
    story.append(Spacer(1, 8))

    check_header = [
        _t(lb, "result.check_name"),
        _t(lb, "result.check_length"),
        _t(lb, "result.check_demand"),
        _t(lb, "result.check_cut"),
        _t(lb, "result.check_diff"),
    ]
    check_tbl = Table([check_header, *_check_rows(sol, parts)], repeatRows=1)
    check_tbl.setStyle(_table_style(font, header=True))
    story.append(check_tbl)
    story.append(Spacer(1, 10))

    tmp = tempfile.mkdtemp(prefix="cutting_pdf_")
    try:
        for i, pat in enumerate(sol.patterns):
            if render_bar is not None:
                png, px_w, px_h = _bar_png(pat, stock, render_bar, tmp)
                disp_w = doc.width
                disp_h = disp_w * px_h / px_w
                story.append(Image(png, width=disp_w, height=disp_h))
            else:
                story.append(Paragraph(f"#{i + 1}", normal))
            story.append(Spacer(1, 6))
        doc.build(story)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    _logger.info("PDF 已导出 %s (lang=%s)", path, lang)


def _table_style(font: str, header: bool) -> TableStyle:
    cmds: list[tuple[Any, ...]] = [
        ("FONTNAME", (0, 0), (-1, -1), font),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), _CHECK_GRID, colors.HexColor("#999999")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    if header:
        cmds.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F0F0F0")))
    return TableStyle(cmds)


__all__ = ["build_pdf"]
