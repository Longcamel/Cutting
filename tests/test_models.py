"""models 模块测试（doc/tasks/models.md，对齐详细设计 §2）。"""

import pytest

from core.models import CuttingPattern, Part, Solution, Statistics, StockSpec


def test_part_defaults() -> None:
    p = Part(length=2000, qty=5)
    assert p.name == ""


def test_stock_defaults() -> None:
    s = StockSpec(length=6000, kerf=3)
    assert (s.material, s.company, s.project) == ("", "", "")


def test_pattern_defaults_and_mutability() -> None:
    p = CuttingPattern(counts={0: 2})
    assert p.bars == 1 and p.remainder == 0
    p.bars = 3  # 可变（求解器要增量填充）


def test_solution_defaults() -> None:
    s = Solution()
    assert s.patterns == [] and s.stats is None and s.exact is False
    assert s.elapsed_s == 0.0


def test_frozen_part() -> None:
    p = Part(length=2000, qty=5)
    with pytest.raises(AttributeError):
        p.length = 1  # type: ignore[misc]  # 验证 frozen 生效


def test_frozen_stock() -> None:
    s = StockSpec(length=6000, kerf=3)
    with pytest.raises(AttributeError):
        s.kerf = 5  # type: ignore[misc]  # 同上


def test_statistics_construct() -> None:
    st = Statistics(
        bars_used=1,
        total_stock_len=6000,
        total_part_len=5500,
        kerf_loss=9,
        waste_len=491,
        utilization=5500 / 6000 * 100,
    )
    assert st.utilization == pytest.approx(91.6666666667)
