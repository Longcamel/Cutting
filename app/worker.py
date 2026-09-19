"""后台求解线程（详细设计 §4.1）：与 GUI 只经信号通信，不 import 任何 ui 模块。"""

import threading

from PySide6.QtCore import QThread, Signal

from core.models import Part, Solution, StockSpec
from core.solver_base import SolverBase


class SolverWorker(QThread):
    """在后台线程运行 solver.solve，经 Qt 信号回报进度/结果/错误。"""

    progress = Signal(int)  # 0~100
    finished_ok = Signal(object)  # Solution
    failed = Signal(str)  # i18n 错误 key 或错误码

    def __init__(
        self,
        solver: SolverBase,
        parts: list[Part],
        stock: StockSpec,
        parent: object = None,
    ) -> None:
        super().__init__(parent)  # type: ignore[arg-type]
        self._solver = solver
        self._parts = list(parts)  # 输入副本
        self._stock = stock
        self._cancel = threading.Event()

    def run(self) -> None:
        try:
            sol: Solution = self._solver.solve(
                self._parts,
                self._stock,
                on_progress=self.progress.emit,
                cancel=self._cancel,
            )
            self.finished_ok.emit(sol)
        except Exception as e:  # noqa: BLE001 —— 线程内任何异常都转信号
            self.failed.emit(str(getattr(e, "code", None) or e))

    def cancel(self) -> None:
        self._cancel.set()


__all__ = ["SolverWorker"]
