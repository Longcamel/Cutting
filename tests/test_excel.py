"""fileio/excel_importer 测试：临时 xlsx 覆盖正常/两列/坏行/非数字/超长/E004/E007/模板。"""

from pathlib import Path

import pytest
from openpyxl import Workbook

from fileio.excel_importer import create_template, load_parts


def _make_xlsx(path: Path, rows: list[list[object]]) -> Path:
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    for r in rows:
        ws.append(r)
    wb.save(path)
    return path


def test_load_parts_ok(tmp_path: Path) -> None:
    p = _make_xlsx(
        tmp_path / "ok.xlsx",
        [
            ["名称", "长度mm", "数量"],
            ["管件A", 1200, 5],
            [None, 800, 3],  # 名称可空
            [None, None, None],  # 完全空行跳过
            ["", "  ", None],  # 空白字符串视为空行跳过
            ["管件B", "1500", 2.0],  # 数字字符串/整数值浮点兼容
        ],
    )
    parts, issues = load_parts(str(p))
    assert issues == []
    assert [(x.name, x.length, x.qty) for x in parts] == [
        ("管件A", 1200, 5),
        ("", 800, 3),
        ("管件B", 1500, 2),
    ]


def test_two_column_template(tmp_path: Path) -> None:
    p = _make_xlsx(
        tmp_path / "two.xlsx",
        [
            ["长度mm", "数量"],
            [1200, 5],
            [800, 3],
        ],
    )
    parts, issues = load_parts(str(p))
    assert issues == []
    assert [(x.length, x.qty, x.name) for x in parts] == [(1200, 5, ""), (800, 3, "")]


def test_bad_row_excel_row_number(tmp_path: Path) -> None:
    p = _make_xlsx(
        tmp_path / "bad.xlsx",
        [
            ["名称", "长度mm", "数量"],
            ["ok", 1200, 5],
            ["bad", "abc", 2],  # Excel 第3行
            ["bad2", 1200, 0],  # Excel 第4行，数量非正
            ["ok2", 900, 1],
        ],
    )
    parts, issues = load_parts(str(p))
    assert len(parts) == 2
    assert [i.code for i in issues] == ["E002", "E002"]
    # Issue.row = Excel行号-1，format_issue 显示时 +1 = 实际行号
    assert [i.row for i in issues] == [2, 3]


def test_name_too_long(tmp_path: Path) -> None:
    p = _make_xlsx(tmp_path / "long.xlsx", [["名称", "长度mm", "数量"], ["x" * 51, 100, 1]])
    parts, issues = load_parts(str(p))
    assert parts == []
    assert issues[0].code == "E002"
    assert issues[-1].code == "E004"  # 全部行无效


def test_all_invalid_e004(tmp_path: Path) -> None:
    p = _make_xlsx(
        tmp_path / "allbad.xlsx",
        [["名称", "长度mm", "数量"], ["a", -1, 2], ["b", 100, "x"]],
    )
    parts, issues = load_parts(str(p))
    assert parts == []
    assert any(i.code == "E002" for i in issues)
    assert issues[-1].code == "E004"


def test_empty_file_e004(tmp_path: Path) -> None:
    p = _make_xlsx(tmp_path / "empty.xlsx", [])
    parts, issues = load_parts(str(p))
    assert parts == []
    assert [i.code for i in issues] == ["E004"]


def test_corrupt_file_e004(tmp_path: Path) -> None:
    p = tmp_path / "corrupt.xlsx"
    p.write_bytes(b"not a real xlsx")
    parts, issues = load_parts(str(p))
    assert parts == []
    assert [i.code for i in issues] == ["E004"]


def test_e007_file_occupied(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = _make_xlsx(tmp_path / "ok.xlsx", [["名称", "长度mm", "数量"], ["a", 100, 1]])

    def _raise(*a: object, **k: object) -> None:
        raise PermissionError("file locked")

    monkeypatch.setattr("fileio.excel_importer.load_workbook", _raise)
    parts, issues = load_parts(str(p))
    assert parts == []
    assert [i.code for i in issues] == ["E007"]


def test_e007_file_not_found(tmp_path: Path) -> None:
    parts, issues = load_parts(str(tmp_path / "missing.xlsx"))
    assert parts == []
    assert [i.code for i in issues] == ["E007"]


@pytest.mark.parametrize(
    ("lang", "headers"),
    [("zh_CN", ["名称", "长度mm", "数量"]), ("en_US", ["Name", "Length mm", "Qty"])],
)
def test_create_template_roundtrip(tmp_path: Path, lang: str, headers: list[str]) -> None:
    p = tmp_path / f"tpl_{lang}.xlsx"
    create_template(str(p), lang)
    wb = Workbook()
    del wb
    from openpyxl import load_workbook

    ws = load_workbook(str(p), read_only=True).active
    assert ws is not None
    rows = list(ws.iter_rows(values_only=True))
    assert list(rows[0]) == headers
    assert len(rows) == 2  # 表头 + 1 行示例
    # 模板可直接被 load_parts 使用（表头跳过、示例行可解析）
    parts, issues = load_parts(str(p))
    assert issues == []
    assert len(parts) == 1


def test_create_template_unknown_lang_fallback(tmp_path: Path) -> None:
    p = tmp_path / "tpl_xx.xlsx"
    create_template(str(p), "fr_FR")
    from openpyxl import load_workbook

    ws = load_workbook(str(p), read_only=True).active
    assert ws is not None
    rows = list(ws.iter_rows(values_only=True))
    assert list(rows[0]) == ["名称", "长度mm", "数量"]


# ============ excel_exporter ============

import json  # noqa: E402
from typing import cast  # noqa: E402

from core.models import CuttingPattern, Part, Solution, Statistics, StockSpec  # noqa: E402
from fileio.excel_exporter import save_report  # noqa: E402


def _sample_solution() -> tuple[Solution, list[Part], StockSpec]:
    parts = [Part(name="P1", length=1200, qty=6), Part(name="", length=800, qty=2)]
    sol = Solution(
        patterns=[CuttingPattern(counts={0: 3, 1: 1}, bars=2, remainder=400)],
        stats=Statistics(
            bars_used=2,
            total_stock_len=12000,
            total_part_len=8800,
            kerf_loss=12,
            waste_len=800,
            utilization=73.33,
        ),
        exact=True,
    )
    stock = StockSpec(length=6000, kerf=3, material="Q235", company="ACME", project="P9")
    return sol, parts, stock


def _zh(key: str) -> str:
    return str(json.loads(Path("i18n/zh_CN.json").read_text(encoding="utf-8"))[key])


def _en(key: str) -> str:
    return str(json.loads(Path("i18n/en_US.json").read_text(encoding="utf-8"))[key])


def _sheet_rows(path: Path) -> list[list[list[object]]]:
    from openpyxl import load_workbook

    wb = load_workbook(str(path), read_only=True)
    out = []
    for ws in wb.worksheets:
        out.append(cast("list[list[object]]", [list(r) for r in ws.iter_rows(values_only=True)]))
    return out


def test_save_report_three_sheets_content(tmp_path: Path) -> None:
    sol, parts, stock = _sample_solution()
    p = tmp_path / "report.xlsx"
    save_report(str(p), sol, parts, stock, "zh_CN")
    s1, s2, s3 = _sheet_rows(p)
    # Sheet1 参数统计
    flat = [str(c) for row in s1 for c in row if c is not None]
    assert _zh("report.title") in flat
    assert _zh("report.company") in flat and "ACME" in flat
    assert _zh("report.material") in flat and "Q235" in flat
    assert 6000 in [c for row in s1 for c in row]
    summary = _zh("result.stats").format(
        bars=2, util="73.3", part_len=8800, kerf_loss=12, waste=800
    )
    assert summary in flat
    # Sheet2 切割方案
    assert list(s2[0]) == [
        _zh("result.col_pattern"),
        _zh("result.col_detail"),
        _zh("result.col_remainder"),
        _zh("result.col_bars"),
    ]
    assert s2[1] == [1, "P1 1200×3 + #2 800×1", 400, 2]
    # Sheet3 零件核对：需求 vs 实切
    assert list(s3[0]) == [
        _zh("result.check_name"),
        _zh("result.check_length"),
        _zh("result.check_demand"),
        _zh("result.check_cut"),
        _zh("result.check_diff"),
    ]
    assert s3[1] == ["P1", 1200, 6, 6, 0]
    assert s3[2] == ["#2", 800, 2, 2, 0]


def test_save_report_en_headers(tmp_path: Path) -> None:
    sol, parts, stock = _sample_solution()
    p = tmp_path / "report_en.xlsx"
    save_report(str(p), sol, parts, stock, "en_US")
    s1, s2, _s3 = _sheet_rows(p)
    assert _en("report.title") in [c for row in s1 for c in row]
    assert s2[0][0] == _en("result.col_pattern")


def test_save_report_e007_bad_path(tmp_path: Path) -> None:
    sol, parts, stock = _sample_solution()
    with pytest.raises(OSError):
        save_report(str(tmp_path / "no_such_dir" / "r.xlsx"), sol, parts, stock, "zh_CN")
