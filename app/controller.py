"""流程编排（详细设计 §4.2）：无界面对象也可测，依赖全部经构造注入。

不 import 任何 ui 模块；io 模块延迟导入，测试可经 sys.modules 注入假实现。
"""

import importlib
import logging
import re
from collections.abc import Callable
from typing import Any

from app.worker import SolverWorker
from core import statistics
from core.models import CuttingPattern, Part, Solution, StockSpec
from core.solver_base import SolverBase
from core.validator import Issue, check_solution, validate_input
from fileio.settings import SettingsStore

_logger = logging.getLogger(__name__)

_CODE_RE = re.compile(r"^E\d{3}$")

ProgressFn = Callable[[int], None]
DoneFn = Callable[[Solution], None]
ErrorFn = Callable[[list[Issue]], None]
# render_bar(painter, pattern, scale) —— 由 ui.cutting_view.render_to_painter 注入
RenderBarFn = Callable[[Any, CuttingPattern, float], None]

_ERR_WORKER_UNKNOWN = "E009"  # D4：求解器未预期异常（设计 §9 表外新增兜底码）


def _to_int(v: object, default: int, minimum: int = 1) -> int:
    """宽松地把 settings 值转 int，异常/小于 minimum 回退默认。"""
    try:
        n = int(str(v))
    except (TypeError, ValueError):
        return default
    return n if n >= minimum else default


def _noop_render_bar(_painter: Any, _pattern: CuttingPattern, _scale: float) -> None:
    """render_bar 空实现：纯文本 PDF 或测试用。"""


class AppController:
    """持有当前会话状态，方法即用户动作。"""

    def __init__(self, settings: SettingsStore, make_solver: Callable[[str], SolverBase]):
        self._settings = settings
        self._make_solver = make_solver
        self.parts: list[Part] = []
        self.stock = self._restore_stock(settings)
        self.solution: Solution | None = None
        self._worker: SolverWorker | None = None

    @staticmethod
    def _restore_stock(settings: SettingsStore) -> StockSpec:
        """启动时从 settings 回填参数（F4.2）；数据异常回退默认。"""
        d = settings.data
        return StockSpec(
            length=_to_int(d.get("stock_length"), 6000),
            kerf=_to_int(d.get("kerf"), 3, minimum=0),
            material=str(d.get("material") or ""),
            company=str(d.get("company") or ""),
            project=str(d.get("project") or ""),
        )

    # ---- 求解模式（持久化）----
    @property
    def mode(self) -> str:
        """当前求解模式 fast/exact，来自 settings。"""
        m = str(self._settings.data.get("mode") or "fast")
        return m if m in ("fast", "exact") else "fast"

    @mode.setter
    def mode(self, value: str) -> None:
        if value not in ("fast", "exact"):
            return
        self._settings.data["mode"] = value
        self._settings.save()

    # ---- 输入 ----
    def import_excel(self, path: str) -> tuple[int, list[Issue]]:
        """调 excel_importer；成功则替换 self.parts。返回(导入条数, 问题列表)。"""
        excel_importer = importlib.import_module("fileio.excel_importer")  # 延迟导入，便于测试注入

        try:
            parts, issues = excel_importer.load_parts(path)
        except Exception as e:  # noqa: BLE001 —— 任何解析异常归 E004
            _logger.warning("excel import failed: %s", e)
            return 0, [Issue("E004", detail=str(e))]
        self.parts = list(parts)
        return len(parts), issues

    def set_parts(self, parts: list[Part]) -> None:
        self.parts = list(parts)

    def set_stock(self, stock: StockSpec) -> None:
        """更新参数并立即 settings.save()（F4.2）。"""
        self.stock = stock
        d = self._settings.data
        d["stock_length"] = stock.length
        d["kerf"] = stock.kerf
        d["material"] = stock.material
        d["company"] = stock.company
        d["project"] = stock.project
        self._settings.save()

    # ---- 计算（异步）----
    def start_solve(self, mode: str, on_progress: ProgressFn,
                    on_done: DoneFn, on_error: ErrorFn) -> None:
        """1) 校验失败 → on_error(issues) 并停止
        2) make_solver(mode) + SolverWorker 接线三个回调
        3) on_done 内 check_solution 自检 → 失败报 E005；
           通过则 statistics.compute 填充 stats，赋给 self.solution"""
        issues = validate_input(self.parts, self.stock)
        if issues:
            on_error(issues)
            return
        self.cancel_solve()
        worker = SolverWorker(self._make_solver(mode), self.parts, self.stock)
        worker.progress.connect(on_progress)
        worker.failed.connect(
            lambda msg: on_error([
                Issue(msg if _CODE_RE.match(msg) else _ERR_WORKER_UNKNOWN, detail=msg)
            ])
        )

        def _done(sol: Solution | None) -> None:
            if sol is None:  # 用户取消：求解器返回 None，静默结束
                return
            bad = check_solution(sol, self.parts, self.stock)
            if bad:
                _logger.error("solution self-check failed: %s", bad)
                on_error([Issue("E005", detail="; ".join(b.detail for b in bad))])
                return
            sol.stats = statistics.compute(sol, self.parts, self.stock)
            self.solution = sol
            on_done(sol)

        worker.finished_ok.connect(_done)
        self._worker = worker
        worker.start()

    def cancel_solve(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()

    # ---- 导出（同步，需已有 solution，否则返回 E006）----
    def export_excel(self, path: str) -> str | None:
        """返回 None=成功，否则错误码（E006/E007）。"""
        if self.solution is None:
            return "E006"
        excel_exporter = importlib.import_module("fileio.excel_exporter")

        try:
            excel_exporter.save_report(
                path, self.solution, self.parts, self.stock, self._lang())
        except Exception as e:  # noqa: BLE001 —— io 异常归 E007
            _logger.warning("excel export failed: %s", e)
            return "E007"
        return None

    def export_pdf(self, path: str, render_bar: RenderBarFn | None = None) -> str | None:
        """返回 None=成功，否则错误码（E006/E007）。render_bar 由 ui 注入。"""
        if self.solution is None:
            return "E006"
        pdf_reporter = importlib.import_module("fileio.pdf_reporter")

        try:
            pdf_reporter.build_pdf(
                path, self.solution, self.parts, self.stock, self._lang(),
                render_bar or _noop_render_bar)
        except Exception as e:  # noqa: BLE001
            _logger.warning("pdf export failed: %s", e)
            return "E007"
        return None

    # ---- 内部 ----
    def _lang(self) -> str:
        return str(self._settings.data.get("language", "zh_CN"))


__all__ = ["AppController"]
