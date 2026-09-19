"""求解器接口（详细设计 §3.2）。"""

import threading
from abc import ABC, abstractmethod
from collections.abc import Callable

from .models import Part, Solution, StockSpec

ProgressCB = Callable[[int], None]  # 0~100 百分比


class SolverBase(ABC):
    @abstractmethod
    def solve(
        self,
        parts: list[Part],
        stock: StockSpec,
        on_progress: ProgressCB | None = None,
        cancel: threading.Event | None = None,
    ) -> Solution:
        """cancel.is_set() 时应尽快返回当前最好解（或空 Solution）。

        实现方须在主要循环定期检查 cancel 并回报进度。
        """


__all__ = ["ProgressCB", "SolverBase"]
