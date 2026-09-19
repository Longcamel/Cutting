"""heuristic_solver 模块测试（doc/tasks/heuristic_solver.md，基准阈值按 decisions.md D2 修正）。"""

import random
import threading
import time

from core.heuristic_solver import HeuristicSolver
from core.models import Part, StockSpec
from core.statistics import compute
from core.validator import check_solution

STOCK = StockSpec(length=6000, kerf=3)
BENCH_PARTS = [
    Part(name="立柱", length=2000, qty=5),
    Part(name="横梁", length=1500, qty=4),
    Part(name="短撑", length=800, qty=10),
]


def test_benchmark() -> None:
    sol = HeuristicSolver().solve(BENCH_PARTS, STOCK)
    assert check_solution(sol, BENCH_PARTS, STOCK) == []
    assert sol.stats is not None
    assert sol.stats.bars_used <= 6
    assert sol.stats.utilization >= 75.0  # D2：该数据集理论上限80%，原≥95%不可达
    assert sol.exact is False


def test_random_property() -> None:
    rng = random.Random(42)
    for _ in range(100):
        n = rng.randint(1, 15)
        parts = [Part(length=rng.randint(100, 5900), qty=rng.randint(1, 20)) for _ in range(n)]
        sol = HeuristicSolver().solve(parts, STOCK)
        assert check_solution(sol, parts, STOCK) == []
        st = compute(sol, parts, STOCK)
        assert st.utilization >= 0


def test_performance_1000_parts() -> None:
    rng = random.Random(7)
    parts = [Part(length=rng.randint(200, 5800), qty=rng.randint(5, 50)) for _ in range(100)]
    total = sum(p.qty for p in parts)
    assert total >= 1000
    t0 = time.monotonic()
    sol = HeuristicSolver().solve(parts, STOCK)
    assert time.monotonic() - t0 < 10
    assert check_solution(sol, parts, STOCK) == []


def test_cancel_returns_quickly() -> None:
    rng = random.Random(1)
    parts = [Part(length=rng.randint(200, 5800), qty=20) for _ in range(50)]
    cancel = threading.Event()
    cancel.set()  # 立即取消
    t0 = time.monotonic()
    sol = HeuristicSolver().solve(parts, STOCK, cancel=cancel)
    assert time.monotonic() - t0 < 1
    # 取消时允许返回空 Solution（SolverBase 契约）；非空解则必须合法
    if sol.patterns:
        assert check_solution(sol, parts, STOCK) == []


def test_progress_monotonic_and_reaches_100() -> None:
    seen: list[int] = []
    HeuristicSolver().solve(BENCH_PARTS, STOCK, on_progress=seen.append)
    assert seen and seen[-1] == 100
    assert all(a <= b for a, b in zip(seen, seen[1:]))
    assert all(0 <= v <= 100 for v in seen)


def test_empty_parts() -> None:
    sol = HeuristicSolver().solve([], STOCK)
    assert sol.patterns == []
    assert sol.exact is False


def test_consolidate_empties_worst_bin() -> None:
    # 直接构造欠载bins（BFD 本身往往已最优，难以自然触发合并路径）：
    # [5000] + [500×2] → 后者可并入前者 → 1 根
    from core.heuristic_solver import _Bin, _consolidate

    lengths = [5000, 500]
    bins = [_Bin(counts={0: 1}, consumed=5000), _Bin(counts={1: 2}, consumed=1000)]
    merged = _consolidate(bins, lengths, 6000, 0, None)
    assert len(merged) == 1
    assert merged[0].counts == {0: 1, 1: 2}


def test_consolidate_keeps_when_no_fit() -> None:
    # [5000] + [1500]：1500 塞不进 1000 空间 → 保持 2 根
    from core.heuristic_solver import _Bin, _consolidate

    lengths = [5000, 1500]
    bins = [_Bin(counts={0: 1}, consumed=5000), _Bin(counts={1: 1}, consumed=1500)]
    merged = _consolidate(bins, lengths, 6000, 0, None)
    assert len(merged) == 2


def test_fit_units_impossible_returns_none() -> None:
    from core.heuristic_solver import _fit_units_into_spaces

    assert _fit_units_into_spaces([0], [10], [5000], 3) is None  # 空间不足
    assert _fit_units_into_spaces([], [], [100], 3) == []  # 空单位 trivially 成功
