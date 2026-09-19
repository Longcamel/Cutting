"""validator 模块测试（doc/tasks/validator.md，对齐详细设计 §3.1）。"""

from core.models import CuttingPattern, Part, Solution, StockSpec
from core.validator import Issue, check_solution, validate_input

STOCK = StockSpec(length=6000, kerf=3)
PARTS = [Part(length=2000, qty=5), Part(length=1500, qty=3, name="长管")]


def _codes(issues: list[Issue]) -> list[str]:
    return [i.code for i in issues]


def test_valid_input_passes() -> None:
    assert validate_input(PARTS, STOCK) == []


def test_r1_empty_parts() -> None:
    issues = validate_input([], STOCK)
    assert _codes(issues) == ["E001"]


def test_r2_bad_part_and_row() -> None:
    parts = [Part(length=2000, qty=5), Part(length=0, qty=1), Part(length=100, qty=0)]
    issues = validate_input(parts, STOCK)
    assert _codes(issues) == ["E002", "E002"]
    assert [i.row for i in issues] == [1, 2]


def test_r3_bad_stock() -> None:
    assert _codes(validate_input(PARTS, StockSpec(length=0, kerf=3))) == ["E002"]
    assert _codes(validate_input(PARTS, StockSpec(length=6000, kerf=-1))) == ["E002"]


def test_r4_part_too_long() -> None:
    parts = [Part(length=6001, qty=1)]  # 超过原料
    issues = validate_input(parts, STOCK)
    assert _codes(issues) == ["E003"] and issues[0].row == 0


def test_r4_kerf_boundary() -> None:
    # length+kerf==stock.length 允许；length+kerf>stock.length 且 length<stock.length 拒绝
    assert validate_input([Part(length=5997, qty=1)], STOCK) == []
    assert _codes(validate_input([Part(length=5998, qty=1)], STOCK)) == ["E003"]
    assert validate_input([Part(length=6000, qty=1)], STOCK) == []  # 恰等原料长允许


def test_r5_name_length_boundary() -> None:
    assert validate_input([Part(length=100, qty=1, name="x" * 50)], STOCK) == []
    assert _codes(validate_input([Part(length=100, qty=1, name="x" * 51)], STOCK)) == ["E002"]


def _good_sol() -> Solution:
    # 需求：2000×5、1500×3，原料6000/锯缝3。
    # A: 2×2000+1×1500=5500+3切口×3，余料491，×2根 → 0:4, 1:2
    # B: 2×2000=4000+2切口×3，余料1994，×1根 → 0:2（注意3×2000+2×3=6006超界，不可行）
    # C: 3×1500=4500+3切口×3，余料1491，×1根 → 1:3
    a = CuttingPattern(counts={0: 2, 1: 1}, bars=2, remainder=491)
    b = CuttingPattern(counts={0: 2}, bars=1, remainder=1994)
    c = CuttingPattern(counts={1: 3}, bars=1, remainder=1491)
    return Solution(patterns=[a, b, c])  # 实切 0:6≥5, 1:5≥3


def test_check_solution_ok() -> None:
    assert check_solution(_good_sol(), PARTS, STOCK) == []


def test_check_c1_overflow() -> None:
    bad = CuttingPattern(counts={0: 3, 1: 1}, bars=1, remainder=0)  # 7500>6000
    issues = check_solution(Solution(patterns=[bad]), PARTS, STOCK)
    assert "E005" in _codes(issues)


def test_check_c2_underproduction() -> None:
    sol = _good_sol()
    sol.patterns[0].bars = 1  # 零件0 实切 2+2=4<5；零件1 实切 1+3=4≥3
    issues = check_solution(sol, PARTS, STOCK)
    assert any(i.code == "E005" and i.row == 0 and "C2" in i.detail for i in issues)
    assert not any("C2" in i.detail and i.row == 1 for i in issues)


def test_check_c3_illegal() -> None:
    sol = Solution(
        patterns=[
            CuttingPattern(counts={}, bars=1),
            CuttingPattern(counts={0: 1}, bars=0),
            CuttingPattern(counts={9: 1}, bars=1),
            CuttingPattern(counts={0: 0}, bars=1),
        ]
    )
    issues = check_solution(sol, PARTS, STOCK)
    assert _codes(issues).count("E005") >= 4
