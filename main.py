"""程序入口（详细设计 §8）。

启动流程：QApplication → SettingsStore.load → translator.init(language)
→ AppController(settings, make_solver) → MainWindow → show → exec。
sys.excepthook 兜底：任何未处理异常写日志文件并弹错误窗（详细设计 §11 T4）。
"""

from __future__ import annotations

import logging
import sys
import traceback
from pathlib import Path
from types import TracebackType

from app.controller import AppController
from core.exact_solver import ExactSolver
from core.heuristic_solver import HeuristicSolver
from core.solver_base import SolverBase
from fileio.settings import SettingsStore
from i18n import translator

_logger = logging.getLogger("cutting")


def make_solver(mode: str) -> SolverBase:
    """按模式工厂：fast→启发式，exact→CP-SAT 精确解。"""
    return HeuristicSolver() if mode == "fast" else ExactSolver()


def _log_dir() -> Path:
    """与 settings 相同的用户目录（打包后可写）。"""
    import os

    appdata = os.environ.get("APPDATA")
    base = Path(appdata) if appdata else Path.home()
    return base / "CuttingApp"


def _install_excepthook() -> None:
    """全局异常兜底：写 error.log + 弹窗。任何环节失败都不再抛异常。"""

    def hook(exc_type: type[BaseException], exc: BaseException, tb: TracebackType | None) -> None:
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        log = _log_dir() / "error.log"
        try:
            log.parent.mkdir(parents=True, exist_ok=True)
            with log.open("a", encoding="utf-8") as f:
                f.write(text + "\n")
        except OSError:
            log = Path("error.log")
        _logger.error("unhandled exception:\n%s", text)
        try:
            from PySide6.QtWidgets import QMessageBox  # noqa: PLC0415

            QMessageBox.critical(None, "Cutting", translator.tr("err.unexpected", log=str(log)))
        except Exception:  # noqa: BLE001
            pass

    sys.excepthook = hook


def main() -> None:
    from PySide6.QtWidgets import QApplication  # noqa: PLC0415 —— 惰性，便于无界面导入

    app = QApplication.instance() or QApplication(sys.argv)
    settings = SettingsStore()
    cfg = settings.load()
    translator.init(str(cfg.get("language", "zh_CN")))
    _install_excepthook()

    controller = AppController(settings, make_solver)

    from ui.main_window import MainWindow  # noqa: PLC0415

    win = MainWindow(controller, settings)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
