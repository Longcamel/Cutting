"""精确模式求解器（详细设计 §3.4）：模式枚举 + OR-Tools CP-SAT。

适用限制：模式枚举 + CP-SAT 总时限 MAX_TIME_S=30 秒（枚举/求解共用同一截止时间）；
时限内无任何可行解（超时）抛 ExactTimeoutError(E010)。
切口数按 §2 不变式；约束为 Σ a_ip·y_p >= d_i（允许多切）。
"""

import threading
import time

from ortools.sat.python import cp_model

from .models import CuttingPattern, Part, Solution, StockSpec
from .solver_base import ProgressCB, SolverBase
from .statistics import _cuts_per_bar, compute

MAX_TIME_S = 30.0  # 精确模式求解时限（秒）；超时未出可行解即结束并报 E010


class ExactTimeoutError(ValueError):
    """精确模式在时限内求不出可行解（通常是超时），对应错误码 E010。"""

    code = "E010"


class _EnumerationTimeout(Exception):
    """枚举超过截止时间（内部信号，solve 中转译为 ExactTimeoutError）。"""


class _EnumerationAborted(Exception):
    """枚举中收到取消（内部信号，截断返回已生成部分）。"""


def enumerate_patterns(
    lengths: list[int],
    demand: list[int],
    stock: StockSpec,
    deadline: float | None = None,
    cancel: threading.Event | None = None,
) -> list[list[int]]:
    """DFS 生成所有可行切割组合（含 kerf，末段豁免，§3.4 步骤1）。

    组合按"长度降序、下标非降"生成避免排列重复；xi 上界 min(d_i, L//li)。
    deadline（monotonic 秒）到期抛 _EnumerationTimeout；cancel 置位则截断返回部分结果。
    """
    n = len(lengths)
    eff_cap = stock.length + stock.kerf
    order = sorted(range(n), key=lambda i: -lengths[i])  # 先生成长件，剪枝更早
    unit = [lengths[i] + stock.kerf for i in order]
    ub = [min(demand[i], stock.length // lengths[i]) for i in order]
    patterns: list[list[int]] = []
    cur = [0] * n
    checks = 0  # 每 4096 个组合检查一次时限/取消，降低开销

    def dfs(pos: int, used: int) -> None:
        nonlocal checks
        if pos == n:
            return
        i = order[pos]
        max_x = min(ub[pos], (eff_cap - used) // unit[pos])
        for x in range(max_x, -1, -1):
            cur[i] = x
            if x > 0:
                patterns.append(cur.copy())
                checks += 1
                if checks & 0xFFF == 0:
                    if cancel is not None and cancel.is_set():
                        raise _EnumerationAborted
                    if deadline is not None and time.monotonic() > deadline:
                        raise _EnumerationTimeout
            dfs(pos + 1, used + x * unit[pos])
        cur[i] = 0

    try:
        dfs(0, 0)
    except _EnumerationAborted:
        pass
    return patterns


class _CancelCallback(cp_model.CpSolverSolutionCallback):
    """cancel 置位或找到首个解后仍在时限内 → 由求解器自行继续；cancel 时停止搜索。"""

    def __init__(self, cancel: threading.Event | None = None) -> None:
        super().__init__()
        self._cancel = cancel

    def on_solution_callback(self) -> None:
        if self._cancel is not None and self._cancel.is_set():
            self.StopSearch()


def _remainder_of(counts: dict[int, int], lengths: list[int], stock: StockSpec) -> int:
    n_seg = sum(counts.values())
    total = sum(lengths[i] * c for i, c in counts.items())
    rem = stock.length - total - _cuts_per_bar(counts, 0) * stock.kerf  # 先按余料=0试算
    if rem == 0:
        return 0
    # 余料>0 时切口数=段数（比上面多一个锯缝）
    rem = stock.length - total - n_seg * stock.kerf
    return max(rem, 0)


class ExactSolver(SolverBase):
    """CP-SAT 精确求解。数学最优时 exact=True；超时/取消取当前最好可行解 exact=False。"""

    def solve(
        self,
        parts: list[Part],
        stock: StockSpec,
        on_progress: ProgressCB | None = None,
        cancel: threading.Event | None = None,
    ) -> Solution:
        t0 = time.monotonic()
        if not parts:
            return Solution(patterns=[], exact=True, elapsed_s=0.0)

        lengths = [p.length for p in parts]
        demand = [p.qty for p in parts]
        if on_progress is not None:
            on_progress(5)
        deadline = t0 + MAX_TIME_S  # 枚举与求解共用同一截止时间
        try:
            pats = enumerate_patterns(lengths, demand, stock, deadline=deadline, cancel=cancel)
        except _EnumerationTimeout as e:
            # 枚举阶段即超时，无任何可行解 → E010
            raise ExactTimeoutError("精确模式在 30 秒内未求出可行解") from e
        if cancel is not None and cancel.is_set():
            return Solution(patterns=[], exact=False, elapsed_s=time.monotonic() - t0)
        if on_progress is not None:
            on_progress(30)

        model = cp_model.CpModel()
        total_lb = (sum(demand[i] * lengths[i] for i in range(len(parts)))) // stock.length
        ub_bars = sum(demand)  # 宽松上界：每件一根
        ys = [model.new_int_var(0, ub_bars, f"y_{p}") for p in range(len(pats))]
        for i in range(len(parts)):
            model.add(sum(pats[p][i] * ys[p] for p in range(len(pats))) >= demand[i])
        model.minimize(sum(ys))
        _ = total_lb  # 下界交由 CP-SAT 推导

        solver = cp_model.CpSolver()
        # 求解阶段只能用枚举剩余的时间，保证总时长不超过 MAX_TIME_S
        solver.parameters.max_time_in_seconds = max(0.1, deadline - time.monotonic())
        cb = _CancelCallback(cancel)
        status = solver.solve(model, cb)
        if on_progress is not None:
            on_progress(90)

        feasible = status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        sol = Solution(patterns=[], exact=False, elapsed_s=time.monotonic() - t0)
        if feasible:
            for p in range(len(pats)):
                v = int(solver.value(ys[p]))
                if v > 0:
                    counts = {i: c for i, c in enumerate(pats[p]) if c > 0}
                    sol.patterns.append(
                        CuttingPattern(
                            counts=counts,
                            bars=v,
                            remainder=_remainder_of(counts, lengths, stock),
                        )
                    )
            sol.stats = compute(sol, parts, stock)
            sol.exact = bool(status == cp_model.OPTIMAL) and not (
                cancel is not None and cancel.is_set()
            )
        elif cancel is None or not cancel.is_set():
            # 时限内无任何可行解（几乎总是 30 s 超时或问题过大）→ 结束任务并提示
            raise ExactTimeoutError("精确模式在 30 秒内未求出可行解")
        if on_progress is not None:
            on_progress(100)
        return sol


__all__ = ["ExactSolver", "ExactTimeoutError", "MAX_TIME_S", "enumerate_patterns"]
