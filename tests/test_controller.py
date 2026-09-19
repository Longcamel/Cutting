"""controller 模块测试（doc/tasks/controller.md，详细设计 §4.2）。

假 solver + 假 io（经 sys.modules 注入），不依赖真实 excel/pdf 模块。
"""

import sys
import threading
import time
import types

import pytest
from PySide6.QtCore import QCoreApplication

from app.controller import AppController
from core.models import CuttingPattern, Part, Solution, StockSpec
from core.solver_base import ProgressCB, SolverBase
from core.validator import Issue
from fileio.settings import SettingsStore

STOCK = StockSpec(length=6000, kerf=3)
PARTS = [Part(name="a", length=1000, qty=6)]


def _valid_solution() -> Solution:
    # 每根 3 件 × 1000 + 3 切口 × 3 = 3009，余 2991；2 根共 6 件
    return Solution(patterns=[CuttingPattern(counts={0: 3}, bars=2, remainder=2991)])


class _FakeSolver(SolverBase):
    def __init__(self, sol: Solution | None = None):
        self._sol = sol if sol is not None else _valid_solution()

    def solve(
        self,
        parts: list[Part],
        stock: StockSpec,
        on_progress: ProgressCB | None = None,
        cancel: threading.Event | None = None,
    ) -> Solution:
        if on_progress:
            on_progress(50)
        return self._sol


def _make_controller(tmp_path, solver: SolverBase) -> AppController:
    settings = SettingsStore(tmp_path / "settings.json")
    settings.load()
    return AppController(settings, make_solver=lambda _mode: solver)


def _pump(ms: int = 50) -> None:
    """等待后台线程并派发跨线程信号到主线程回调。"""
    end = time.monotonic() + ms / 1000
    while time.monotonic() < end:
        QCoreApplication.processEvents()
        time.sleep(0.005)


def _wait_worker(ctrl: AppController) -> None:
    w = ctrl._worker
    assert w is not None, "worker 未创建"
    w.wait(5000)


def test_validate_fail_stops_solve(qapp, tmp_path) -> None:
    called: list[str] = []
    ctrl = _make_controller(tmp_path, _FakeSolver())
    ctrl.set_parts([])  # 空料单 → E001
    errors: list[Issue] = []
    ctrl.start_solve(
        "fast",
        lambda v: called.append("progress"),
        lambda sol: called.append("done"),
        lambda issues: errors.extend(issues),
    )
    assert called == []  # 未启动后台计算
    assert any(i.code == "E001" for i in errors)
    assert ctrl.solution is None


def test_full_flow_success(qapp, tmp_path) -> None:
    ctrl = _make_controller(tmp_path, _FakeSolver())
    ctrl.set_parts(PARTS)
    ctrl.set_stock(STOCK)
    progress: list[int] = []
    done: list[Solution] = []
    errors: list[Issue] = []
    ctrl.start_solve("fast", progress.append, done.append, errors.extend)
    _wait_worker(ctrl)
    _pump()
    assert errors == []
    assert progress == [50]
    assert len(done) == 1
    assert ctrl.solution is not None
    assert ctrl.solution.stats is not None
    assert ctrl.solution.stats.bars_used == 2


def test_self_check_fail_reports_e005(qapp, tmp_path) -> None:
    bad = Solution(patterns=[CuttingPattern(counts={0: 99}, bars=1, remainder=0)])
    ctrl = _make_controller(tmp_path, _FakeSolver(bad))
    ctrl.set_parts(PARTS)
    done: list[Solution] = []
    errors: list[Issue] = []
    ctrl.start_solve("fast", lambda v: None, done.append, errors.extend)
    _wait_worker(ctrl)
    _pump()
    assert done == []
    assert any(i.code == "E005" for i in errors)
    assert ctrl.solution is None


class _CrashSolver(SolverBase):
    def solve(self, parts, stock, on_progress=None, cancel=None) -> Solution:
        raise RuntimeError("boom")


def test_solver_crash_reports_e009(qapp, tmp_path) -> None:
    ctrl = _make_controller(tmp_path, _CrashSolver())
    ctrl.set_parts(PARTS)
    errors: list[Issue] = []
    ctrl.start_solve("fast", lambda v: None, lambda s: None, errors.extend)
    _wait_worker(ctrl)
    _pump()
    assert any(i.code == "E009" for i in errors)


class _SlowCancelSolver(SolverBase):
    def __init__(self) -> None:
        self.cancel_seen: threading.Event | None = None

    def solve(self, parts, stock, on_progress=None, cancel=None) -> Solution:
        self.cancel_seen = cancel
        assert cancel is not None
        while not cancel.is_set():
            time.sleep(0.002)
        return _valid_solution()


def test_cancel_solve(qapp, tmp_path) -> None:
    solver = _SlowCancelSolver()
    ctrl = _make_controller(tmp_path, solver)
    ctrl.set_parts(PARTS)
    ctrl.start_solve("fast", lambda v: None, lambda s: None, lambda e: None)
    time.sleep(0.05)  # 确保已进入循环
    ctrl.cancel_solve()
    _wait_worker(ctrl)
    assert solver.cancel_seen is not None and solver.cancel_seen.is_set()


def test_export_without_solution_e006(tmp_path) -> None:
    ctrl = _make_controller(tmp_path, _FakeSolver())
    assert ctrl.export_excel(str(tmp_path / "a.xlsx")) == "E006"
    assert ctrl.export_pdf(str(tmp_path / "a.pdf")) == "E006"


def _install_fake_io(monkeypatch, excel_mod=None, pdf_mod=None) -> None:
    if excel_mod is not None:
        monkeypatch.setitem(sys.modules, "fileio.excel_exporter", excel_mod)
    if pdf_mod is not None:
        monkeypatch.setitem(sys.modules, "fileio.pdf_reporter", pdf_mod)


def test_export_excel_success(qapp, tmp_path, monkeypatch) -> None:
    calls: list[tuple[object, ...]] = []
    mod = types.ModuleType("fileio.excel_exporter")
    setattr(mod, "save_report", lambda *a, **kw: calls.append(a))
    _install_fake_io(monkeypatch, excel_mod=mod)

    ctrl = _make_controller(tmp_path, _FakeSolver())
    ctrl.set_parts(PARTS)
    ctrl.start_solve("fast", lambda v: None, lambda s: None, lambda e: None)
    _wait_worker(ctrl)
    _pump()
    assert ctrl.export_excel(str(tmp_path / "a.xlsx")) is None
    assert len(calls) == 1


def test_export_excel_io_error_e007(qapp, tmp_path, monkeypatch) -> None:
    mod = types.ModuleType("fileio.excel_exporter")

    def _raise(*a, **kw):
        raise PermissionError("locked")

    setattr(mod, "save_report", _raise)
    _install_fake_io(monkeypatch, excel_mod=mod)

    ctrl = _make_controller(tmp_path, _FakeSolver())
    ctrl.set_parts(PARTS)
    ctrl.start_solve("fast", lambda v: None, lambda s: None, lambda e: None)
    _wait_worker(ctrl)
    _pump()
    assert ctrl.export_excel(str(tmp_path / "a.xlsx")) == "E007"


def test_export_pdf_success(qapp, tmp_path, monkeypatch) -> None:
    calls: list[tuple[object, ...]] = []
    mod = types.ModuleType("fileio.pdf_reporter")
    setattr(mod, "build_pdf", lambda *a: calls.append(a))
    _install_fake_io(monkeypatch, pdf_mod=mod)

    ctrl = _make_controller(tmp_path, _FakeSolver())
    ctrl.set_parts(PARTS)
    ctrl.start_solve("fast", lambda v: None, lambda s: None, lambda e: None)
    _wait_worker(ctrl)
    _pump()
    assert ctrl.export_pdf(str(tmp_path / "a.pdf")) is None
    assert len(calls) == 1


def test_set_stock_persists_settings(tmp_path) -> None:
    path = tmp_path / "s.json"
    settings = SettingsStore(path)
    settings.load()
    ctrl = AppController(settings, make_solver=lambda m: _FakeSolver())
    ctrl.set_stock(StockSpec(length=9000, kerf=5, material="Q235", company="ACME", project="P1"))
    settings2 = SettingsStore(path)
    settings2.load()
    assert settings2.data["stock_length"] == 9000
    assert settings2.data["kerf"] == 5
    assert settings2.data["company"] == "ACME"


def test_import_excel_e004_on_garbage(tmp_path, monkeypatch) -> None:
    mod = types.ModuleType("fileio.excel_importer")

    def _raise(path):
        raise ValueError("bad zip")

    setattr(mod, "load_parts", _raise)
    monkeypatch.setitem(sys.modules, "fileio.excel_importer", mod)
    ctrl = _make_controller(tmp_path, _FakeSolver())
    count, issues = ctrl.import_excel("x.xlsx")
    assert count == 0
    assert any(i.code == "E004" for i in issues)


def test_import_excel_replaces_parts(tmp_path, monkeypatch) -> None:
    mod = types.ModuleType("fileio.excel_importer")
    setattr(mod, "load_parts", lambda path: (PARTS, []))
    monkeypatch.setitem(sys.modules, "fileio.excel_importer", mod)
    ctrl = _make_controller(tmp_path, _FakeSolver())
    count, issues = ctrl.import_excel("x.xlsx")
    assert count == 1 and issues == []
    assert ctrl.parts == PARTS


def test_no_ui_import() -> None:
    import app.controller as c

    assert not any(name.startswith("ui") for name in vars(c))


@pytest.mark.parametrize("mode", ["fast", "exact"])
def test_make_solver_receives_mode(qapp, tmp_path, mode) -> None:
    seen: list[str] = []
    settings = SettingsStore(tmp_path / "s.json")
    settings.load()

    def make(m: str) -> SolverBase:
        seen.append(m)
        return _FakeSolver()

    ctrl = AppController(settings, make)
    ctrl.set_parts(PARTS)
    ctrl.start_solve(mode, lambda v: None, lambda s: None, lambda e: None)
    _wait_worker(ctrl)
    _pump()
    assert seen == [mode]
