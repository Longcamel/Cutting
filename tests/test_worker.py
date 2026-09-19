"""worker 模块测试（doc/tasks/worker.md，详细设计 §4.1）。"""

import threading
import time

import pytest
from PySide6.QtCore import Qt

from app.worker import SolverWorker
from core.models import Part, Solution, StockSpec
from core.solver_base import ProgressCB, SolverBase

_DIRECT = Qt.ConnectionType.DirectConnection  # 跨线程同步派发，测试无需事件循环

STOCK = StockSpec(length=6000, kerf=3)
PARTS = [Part(name="a", length=1500, qty=4)]


class _InstantSolver(SolverBase):
    """立即返回固定 Solution 的假求解器。"""

    def solve(
        self,
        parts: list[Part],
        stock: StockSpec,
        on_progress: ProgressCB | None = None,
        cancel: threading.Event | None = None,
    ) -> Solution:
        if on_progress:
            on_progress(50)
        return Solution(patterns=[])


class _SlowSolver(SolverBase):
    """慢速求解器：轮询 cancel，置位后立即返回。"""

    def __init__(self) -> None:
        self.iterations = 0

    def solve(
        self,
        parts: list[Part],
        stock: StockSpec,
        on_progress: ProgressCB | None = None,
        cancel: threading.Event | None = None,
    ) -> Solution:
        while not (cancel and cancel.is_set()):
            self.iterations += 1
            time.sleep(0.005)
        return Solution(patterns=[])


class _CrashSolver(SolverBase):
    def solve(
        self,
        parts: list[Part],
        stock: StockSpec,
        on_progress: ProgressCB | None = None,
        cancel: threading.Event | None = None,
    ) -> Solution:
        raise RuntimeError("boom")


def _wait(worker: SolverWorker, timeout: float = 5.0) -> None:
    assert worker.wait(int(timeout * 1000)), "worker 未在超时内结束"


def test_finished_ok_and_progress(qapp: object) -> None:
    worker = SolverWorker(_InstantSolver(), PARTS, STOCK)
    got: dict[str, object] = {}
    worker.finished_ok.connect(lambda sol: got.__setitem__("sol", sol), _DIRECT)
    worker.progress.connect(lambda v: got.__setitem__("progress", v), _DIRECT)
    worker.start()
    _wait(worker)
    # 直接连接（同线程）时信号已同步派发
    assert isinstance(got["sol"], Solution)
    assert got["progress"] == 50


def test_failed_signal_on_exception(qapp: object) -> None:
    worker = SolverWorker(_CrashSolver(), PARTS, STOCK)
    got: list[str] = []
    worker.failed.connect(got.append, _DIRECT)
    worker.start()
    _wait(worker)
    assert got == ["boom"]


def test_cancel_stops_solve(qapp: object) -> None:
    solver = _SlowSolver()
    worker = SolverWorker(solver, PARTS, STOCK)
    worker.start()
    time.sleep(0.05)
    assert worker.isRunning()
    worker.cancel()
    _wait(worker)
    assert solver.iterations > 0  # 确实循环过，靠 cancel 退出


def test_no_ui_import() -> None:
    import app.worker as w

    assert not any(name.startswith("ui") for name in vars(w)), "worker 不得 import ui 模块"


@pytest.mark.parametrize("parent", [None])
def test_construct_with_parent(qapp: object, parent: object) -> None:
    worker = SolverWorker(_InstantSolver(), PARTS, STOCK, parent=parent)
    assert worker is not None
