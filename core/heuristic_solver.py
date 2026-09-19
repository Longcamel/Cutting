"""快速模式求解器（详细设计 §3.3）：聚合 BFD + 背包填充 + 模式合并改进。

约定：
- 每根原料的"有效容量" = stock.length + kerf（末段豁免一个锯缝，§2 不变式）。
- 装箱中某根的消耗 = Σ(段长 + kerf)，须 ≤ 有效容量。
- 收口时按 §2 切口数规则计算 remainder。
"""

import threading
import time
from dataclasses import dataclass, field

from .models import CuttingPattern, Part, Solution, StockSpec
from .solver_base import ProgressCB, SolverBase
from .statistics import compute

TIME_BUDGET_S = 5  # 时间预算（模块级常量，可调）


def expand(parts: list[Part]) -> list[int]:
    """展开零件实例：返回按下标引用、按长度降序排列的零件下标列表。"""
    order = sorted(range(len(parts)), key=lambda i: -parts[i].length)
    units: list[int] = []
    for i in order:
        units.extend([i] * parts[i].qty)
    return units


@dataclass
class _Bin:
    """一根原料的装箱状态。"""

    counts: dict[int, int] = field(default_factory=dict)
    consumed: int = 0  # Σ(段长 + kerf)


def _total_len(counts: dict[int, int], lengths: list[int]) -> int:
    return sum(lengths[i] * n for i, n in counts.items())


def _remainder(counts: dict[int, int], lengths: list[int], stock: StockSpec) -> int:
    """按 §2 切口数规则计算余料。调用前须保证切法可行。"""
    n = sum(counts.values())
    total = _total_len(counts, lengths)
    rem_min_cuts = stock.length - total - stock.kerf * max(n - 1, 0)
    if rem_min_cuts == 0:
        return 0  # 恰好满棒：切口数 = 段数 − 1
    return stock.length - total - stock.kerf * n  # 余料>0：切口数 = 段数


def _bfd(units: list[int], lengths: list[int], eff_cap: int, kerf: int) -> list[_Bin]:
    """Best-Fit Decreasing 初始解。"""
    bins: list[_Bin] = []
    for u in units:
        need = lengths[u] + kerf
        best: _Bin | None = None
        best_left = eff_cap + 1
        for b in bins:
            left = eff_cap - b.consumed - need
            if 0 <= left < best_left:
                best, best_left = b, left
        if best is None:
            best = _Bin()
            bins.append(best)
        best.counts[u] = best.counts.get(u, 0) + 1
        best.consumed += need
    return bins


def _consolidate(
    bins: list[_Bin],
    lengths: list[int],
    eff_cap: int,
    kerf: int,
    cancel: threading.Event | None,
) -> list[_Bin]:
    """背包填充：尝试把利用率最低的根清空分配到其他根的余料空间（有界背包DP）。"""
    improved = True
    while improved:
        if cancel is not None and cancel.is_set():
            break
        improved = False
        bins.sort(key=lambda b: b.consumed)
        if len(bins) < 2:
            break
        victim = bins[0]
        victim_units = [i for i, n in victim.counts.items() for _ in range(n)]
        # 目标空间（其余各根剩余有效容量）
        spaces = [eff_cap - b.consumed for b in bins[1:]]
        # 贪心+有限枚举：尝试把 victim 的每段塞进某个根
        assignment = _fit_units_into_spaces(victim_units, spaces, lengths, kerf)
        if assignment is not None:
            for bi, u in assignment:
                bins[bi + 1].counts[u] = bins[bi + 1].counts.get(u, 0) + 1
                bins[bi + 1].consumed += lengths[u] + kerf
            bins.pop(0)
            improved = True
    return bins


def _fit_units_into_spaces(
    units: list[int], spaces: list[int], lengths: list[int], kerf: int
) -> list[tuple[int, int]] | None:
    """尝试把 units 全部放入 spaces（每个单位占 length+kerf）。

    贪心按单位长度降序，放入剩余空间最小的可行根；全部放下返回 (space_idx, unit) 列表。
    """
    remain = list(spaces)
    result: list[tuple[int, int]] = []
    for u in sorted(units, key=lambda i: -lengths[i]):
        need = lengths[u] + kerf
        best = -1
        best_left = max(remain, default=-1) + 1
        for si, r in enumerate(remain):
            left = r - need
            if 0 <= left < best_left:
                best, best_left = si, left
        if best < 0:
            return None
        remain[best] -= need
        result.append((best, u))
    return result


def _merge_patterns(
    bins: list[_Bin],
    lengths: list[int],
    eff_cap: int,
    kerf: int,
    deadline: float,
    on_progress: ProgressCB | None,
    cancel: threading.Event | None,
    budget_s: float,
) -> list[_Bin]:
    """模式合并改进：取余料最大两根重切，若总根数下降或总余料下降则接受。"""
    start = time.monotonic()
    rounds = 0
    while time.monotonic() < deadline:
        if cancel is not None and cancel.is_set():
            break
        rounds += 1
        if len(bins) < 2:
            break
        # 余料最大的两根
        order = sorted(range(len(bins)), key=lambda bi: -(eff_cap - bins[bi].consumed))
        i, j = order[0], order[1]
        units = [idx for bi in (i, j) for idx, n in bins[bi].counts.items() for _ in range(n)]
        units.sort(key=lambda idx: -lengths[idx])
        old_waste = (eff_cap - bins[i].consumed) + (eff_cap - bins[j].consumed)
        repacked = _bfd(units, lengths, eff_cap, kerf)
        new_waste = sum(eff_cap - b.consumed for b in repacked)
        if len(repacked) < 2 or new_waste < old_waste:
            for bi in sorted((i, j), reverse=True):
                bins.pop(bi)
            bins.extend(repacked)
        else:
            break  # 局部最优
        if on_progress is not None:
            elapsed = time.monotonic() - start
            on_progress(min(50 + int(50 * elapsed / max(budget_s, 1e-6)), 99))
    return bins


def _aggregate(bins: list[_Bin], lengths: list[int], stock: StockSpec) -> list[CuttingPattern]:
    """相同切法合并为 CuttingPattern。"""
    merged: dict[tuple[tuple[int, int], ...], CuttingPattern] = {}
    for b in bins:
        key = tuple(sorted(b.counts.items()))
        if key in merged:
            merged[key].bars += 1
        else:
            merged[key] = CuttingPattern(
                counts=dict(b.counts), bars=1, remainder=_remainder(b.counts, lengths, stock)
            )
    # 余料升序展示更直观
    return sorted(merged.values(), key=lambda p: p.remainder)


class HeuristicSolver(SolverBase):
    """快速模式求解器。exact 恒为 False。"""

    def solve(
        self,
        parts: list[Part],
        stock: StockSpec,
        on_progress: ProgressCB | None = None,
        cancel: threading.Event | None = None,
    ) -> Solution:
        t0 = time.monotonic()
        if not parts:
            return Solution(patterns=[], exact=False)
        if cancel is not None and cancel.is_set():
            return Solution(patterns=[], exact=False)
        lengths = [p.length for p in parts]
        eff_cap = stock.length + stock.kerf
        units = expand(parts)
        if on_progress is not None:
            on_progress(5)
        bins = _bfd(units, lengths, eff_cap, stock.kerf)
        if on_progress is not None:
            on_progress(20)
        bins = _consolidate(bins, lengths, eff_cap, stock.kerf, cancel)
        if on_progress is not None:
            on_progress(50)
        deadline = t0 + TIME_BUDGET_S
        bins = _merge_patterns(
            bins, lengths, eff_cap, stock.kerf, deadline, on_progress, cancel, TIME_BUDGET_S
        )
        patterns = _aggregate(bins, lengths, stock)
        sol = Solution(patterns=patterns, exact=False, elapsed_s=time.monotonic() - t0)
        sol.stats = compute(sol, parts, stock)
        if on_progress is not None:
            on_progress(100)
        return sol


__all__ = ["HeuristicSolver", "TIME_BUDGET_S", "expand"]
