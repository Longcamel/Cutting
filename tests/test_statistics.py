"""statistics 模块测试（doc/tasks/statistics.md T2，手算用例，对齐详细设计 §3.5）。"""

import pytest

from core.models import CuttingPattern, Part, Solution, StockSpec
from core.statistics import compute

PARTS = [
    Part(name="短管", length=2000, qty=5),
    Part(name="长管", length=1500, qty=3),
]


def _sol() -> Solution:
    # 切法A：2×2000 + 1×1500 = 5500，余料=6000-5500-3×3=491（余料>0→3切口），1根
    a = CuttingPattern(counts={0: 2, 1: 1}, bars=1, remainder=491)
    # 切法B：3×2000 = 6000，余料=0（→3-1=2切口），2根
    b = CuttingPattern(counts={0: 3}, bars=2, remainder=0)
    return Solution(patterns=[a, b])


def test_hand_calc() -> None:
    stock = StockSpec(length=6000, kerf=3)
    st = compute(_sol(), PARTS, stock)
    assert st.bars_used == 3
    assert st.total_stock_len == 18000
    assert st.total_part_len == 5500 + 2 * 6000
    # A: 3×3×1=9；B: (3-1)×3×2=12
    assert st.kerf_loss == 9 + 12
    assert st.waste_len == 18000 - 17500 - 21
    assert st.utilization == pytest.approx(17500 / 18000 * 100)


def test_full_utilization() -> None:
    pat = CuttingPattern(counts={0: 3}, bars=5, remainder=0)
    st = compute(Solution(patterns=[pat]), PARTS, StockSpec(length=6000, kerf=3))
    assert st.bars_used == 5
    assert st.total_part_len == 30000
    assert st.kerf_loss == 5 * 2 * 3
    assert st.utilization == pytest.approx(100.0)


def test_empty_solution() -> None:
    st = compute(Solution(patterns=[]), PARTS, StockSpec(length=6000, kerf=3))
    assert st.bars_used == 0
    assert st.total_stock_len == 0
    assert st.utilization == 0.0


def test_cuts_rule_remainder_positive() -> None:
    # 1段且余料>0：切口=1（端头修边）
    pat = CuttingPattern(counts={0: 1}, bars=1, remainder=3997)
    st = compute(Solution(patterns=[pat]), PARTS, StockSpec(length=6000, kerf=3))
    assert st.kerf_loss == 3
