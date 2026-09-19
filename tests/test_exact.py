"""exact_solver 模块测试（doc/tasks/exact_solver.md，详细设计 §3.4）。"""

import threading
import time

import pytest

from core.exact_solver import ExactSolver, ExactTimeoutError, enumerate_patterns
from core.models import Part, StockSpec
from core.validator import check_solution

STOCK = StockSpec(length=6000, kerf=3)


def test_known_optimum_3_bars() -> None:
    # 2000×5 + 1500×4：总长16000 → ≥3根；A=2×2000+1×1500 ×2 + B=1×2000+2×1500 → 3根可行
    parts = [Part(length=2000, qty=5), Part(length=1500, qty=4)]
    sol = ExactSolver().solve(parts, STOCK)
    assert sol.exact is True
    assert sol.stats is not None and sol.stats.bars_used == 3
    assert check_solution(sol, parts, STOCK) == []


def test_enumerate_patterns_feasible() -> None:
    lengths, demand = [2000, 1500], [5, 4]
    pats = enumerate_patterns(lengths, demand, STOCK)
    assert pats  # 非空
    for p in pats:
        n_seg = sum(p)
        total = sum(lengths[i] * p[i] for i in range(2))
        assert total > 0
        # 含锯缝可行性：末段豁免
        assert total + (n_seg - 1) * STOCK.kerf <= STOCK.length
        # 不超需求上界
        assert all(p[i] <= min(demand[i], STOCK.length // lengths[i]) for i in range(2))


def test_over_25_kinds_no_longer_blocked() -> None:
    # 上限拦截已解除：26 种（原 MAX_KINDS+1）也可正常精确求解
    # 大截面钢材场景：每棒至多装2件，组合数可控（小件×25种会子集爆炸，属设计适用边界）
    parts = [Part(length=2000 + 10 * i, qty=1) for i in range(26)]
    sol = ExactSolver().solve(parts, STOCK)
    assert sol.patterns  # 可解
    assert check_solution(sol, parts, STOCK) == []


def test_no_feasible_solution_raises_e010() -> None:
    # 零件全部长于原料 → 无任何可行切割组合 → 结束并报 E010
    parts = [Part(length=9000, qty=2)]
    with pytest.raises(ExactTimeoutError) as ei:
        ExactSolver().solve(parts, STOCK)
    assert ei.value.code == "E010"


def test_enumeration_phase_timeout_raises_e010(monkeypatch) -> None:
    # 小件×40种 → 枚举组合爆炸，枚举阶段即耗尽时限 → 同样报 E010（30s 承诺覆盖枚举期）
    import core.exact_solver as es

    monkeypatch.setattr(es, "MAX_TIME_S", 0.5)
    parts = [Part(length=233 + 7 * i, qty=3) for i in range(40)]
    t0 = time.monotonic()
    with pytest.raises(ExactTimeoutError) as ei:
        es.ExactSolver().solve(parts, STOCK)
    assert ei.value.code == "E010"
    assert time.monotonic() - t0 < 5  # 必须在时限附近结束，不能卡死


def test_cancel_preset_returns_quickly() -> None:
    cancel = threading.Event()
    cancel.set()
    parts = [Part(length=2000, qty=5), Part(length=1500, qty=4)]
    sol = ExactSolver().solve(parts, STOCK, cancel=cancel)
    assert sol.exact is False  # 取消不得标称最优
    if sol.patterns:
        assert check_solution(sol, parts, STOCK) == []


def test_empty_parts() -> None:
    sol = ExactSolver().solve([], STOCK)
    assert sol.patterns == []


def test_progress_monotonic() -> None:
    seen: list[int] = []
    parts = [Part(length=2000, qty=5), Part(length=1500, qty=4)]
    ExactSolver().solve(parts, STOCK, on_progress=seen.append)
    assert seen and seen[-1] == 100
    assert all(a <= b for a, b in zip(seen, seen[1:]))


def test_kerf_zero_case() -> None:
    # kerf=0：1000×6 → 1根（余料0，切口=段数-1 不报错）
    parts = [Part(length=1000, qty=6)]
    sol = ExactSolver().solve(parts, StockSpec(length=6000, kerf=0))
    assert sol.stats is not None and sol.stats.bars_used == 1
    assert check_solution(sol, parts, StockSpec(length=6000, kerf=0)) == []
