"""主窗口（详细设计 §5.1，M2）：布局、菜单、状态栏与全链路接线。

决策 D11：
- export_pdf 经 ui.cutting_view.render_bar 适配器注入 PDF 绘制（依赖倒置）；
- 语言动作用 QActionGroup(checkable) 单选；切换即 translator.set_language +
  全界面 retranslate + settings 记忆；
- 状态栏进度条仅求解中显示，取消按钮调 controller.cancel_solve；
- 菜单动作不 import io 模块，导入/导出全部委托 AppController（其内部延迟导入）。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QActionGroup, QCloseEvent

if TYPE_CHECKING:
    from PySide6.QtGui import QPainter
    from PySide6.QtPrintSupport import QPrinter

    from core.models import CuttingPattern
from PySide6.QtWidgets import (
    QMainWindow,
    QMenu,
    QProgressBar,
    QPushButton,
    QSplitter,
    QWidget,
)

from app.controller import AppController
from fileio.settings import SettingsStore
from i18n.translator import current_language, on_language_changed, set_language, tr
from ui import dialogs
from ui.cutting_view import CuttingView, render_bar
from ui.input_panel import InputPanel
from ui.result_panel import ResultPanel

_INPUT_WIDTH = 380
_START_SIZE = (1200, 800)


class MainWindow(QMainWindow):
    """主窗口：左输入、右上结果、右下示意图；菜单/状态栏统一接线。"""

    def __init__(
        self,
        controller: AppController,
        settings: SettingsStore,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._controller = controller
        self._settings = settings

        self.input_panel = InputPanel(controller)
        self.input_panel.setFixedWidth(_INPUT_WIDTH)
        self.result_panel = ResultPanel()
        self.cutting_view = CuttingView()

        right = QSplitter(Qt.Orientation.Vertical)
        right.addWidget(self.result_panel)
        right.addWidget(self.cutting_view)
        right.setStretchFactor(0, 0)
        right.setStretchFactor(1, 1)

        root = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(self.input_panel)
        root.addWidget(right)
        root.setStretchFactor(1, 1)
        self.setCentralWidget(root)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setMaximumWidth(220)
        self._progress.hide()
        self._btn_cancel = QPushButton()
        self._btn_cancel.hide()
        self._btn_cancel.clicked.connect(self._on_cancel)
        self.statusBar().addPermanentWidget(self._progress)
        self.statusBar().addPermanentWidget(self._btn_cancel)

        self._build_menus()
        self._wire()
        on_language_changed(self.retranslate)
        self.input_panel.restore_from_settings()
        self.retranslate()
        self.resize(*_START_SIZE)

    def _build_menus(self) -> None:
        """文件/语言/帮助三菜单；动作文本统一在 retranslate 中刷新。"""
        bar = self.menuBar()
        self._menu_file: QMenu = bar.addMenu("")
        self._act_import = self._menu_file.addAction("", self._on_import_excel)
        self._act_export_x = self._menu_file.addAction("", self._on_export_excel)
        self._act_export_p = self._menu_file.addAction("", self._on_export_pdf)
        self._act_print = self._menu_file.addAction("", self._on_print)
        self._menu_file.addSeparator()
        self._act_exit = self._menu_file.addAction("", self.close)

        self._menu_lang: QMenu = bar.addMenu("")
        group = QActionGroup(self)
        group.setExclusive(True)
        self._lang_actions: dict[str, QAction] = {}
        for lang in ("zh_CN", "en_US"):
            act = self._menu_lang.addAction("")
            act.setCheckable(True)
            group.addAction(act)
            act.triggered.connect(lambda _c=False, lg=lang: self._on_language(lg))
            self._lang_actions[lang] = act

        self._menu_help: QMenu = bar.addMenu("")
        self._act_template = self._menu_help.addAction("", self._on_template)
        self._act_about = self._menu_help.addAction("", self._on_about)

    def _wire(self) -> None:
        p = self.input_panel
        p.progressChanged.connect(self._on_progress)
        p.solveRequested.connect(self._on_solve_started)
        p.solveFinished.connect(self._on_solve_finished)
        p.solveFailed.connect(self._on_solve_failed)
        p.issuesFound.connect(self._on_issues_found)

    # ---- 文件/帮助 菜单 ----
    def _on_import_excel(self) -> None:
        path = dialogs.ask_file(self, "open", tr("filter.excel"), tr("menu.file.import_excel"))
        if not path:
            return
        count, issues = self._controller.import_excel(path)
        if count <= 0 and issues:
            dialogs.show_issues(self, issues)
            return
        self.input_panel.set_parts(self._controller.parts)
        if issues:
            dialogs.show_issues(self, issues)
        else:
            dialogs.show_info(self, "info.import_ok", count=count)

    def _on_export_excel(self) -> None:
        if self._controller.solution is None:
            dialogs.show_info(self, "err.E006")
            return
        path = dialogs.ask_file(self, "save", tr("filter.excel"), tr("menu.file.export_excel"))
        if not path:
            return
        err = self._controller.export_excel(path)
        self._report_export(err, path)

    def _on_export_pdf(self) -> None:
        if self._controller.solution is None:
            dialogs.show_info(self, "err.E006")
            return
        path = dialogs.ask_file(self, "save", tr("filter.pdf"), tr("menu.file.export_pdf"))
        if not path:
            return
        c = self._controller

        def _render(p: QPainter, pat: CuttingPattern, scale: float) -> None:
            render_bar(p, pat, c.parts, c.stock, scale)

        err = c.export_pdf(path, _render)
        self._report_export(err, path)

    def _report_export(self, err: str | None, path: str) -> None:
        if err:
            dialogs.show_info(self, "err.export_failed", reason=tr(f"err.{err}"))
        else:
            dialogs.show_info(self, "info.export_ok", path=path)

    def _on_print(self) -> None:
        if self._controller.solution is None:
            dialogs.show_info(self, "err.E006")
            return
        from PySide6.QtPrintSupport import QPrintDialog, QPrinter  # 延迟导入

        printer = QPrinter()
        if QPrintDialog(printer, self).exec() != QPrintDialog.DialogCode.Accepted:
            return
        self._print_to_printer(printer)

    def _print_to_printer(self, printer: QPrinter) -> None:
        """分页打印：每页以页宽渲染、按页高纵向偏移裁剪。"""
        from PySide6.QtGui import QPainter
        from PySide6.QtPrintSupport import QPrinter

        from ui.cutting_view import render_to_painter

        sol = self._controller.solution
        if sol is None:
            return
        painter = QPainter(printer)
        page_w = printer.pageRect(QPrinter.Unit.DevicePixel).width()
        page_h = printer.pageRect(QPrinter.Unit.DevicePixel).height()
        total = render_to_painter(
            painter, sol, self._controller.parts, self._controller.stock, page_w
        )
        page = 1
        while page * page_h < total:
            printer.newPage()
            painter.resetTransform()
            painter.translate(0, -page * page_h)
            render_to_painter(painter, sol, self._controller.parts, self._controller.stock, page_w)
            page += 1
        painter.end()

    def _on_template(self) -> None:
        path = dialogs.ask_file(self, "save", tr("filter.excel"), tr("menu.help.template"))
        if not path:
            return
        try:
            import fileio.excel_importer as imp

            imp.create_template(path, self._settings.data.get("language", "zh_CN"))
        except Exception as e:  # noqa: BLE001
            dialogs.show_info(self, "err.export_failed", reason=str(e))
        else:
            dialogs.show_info(self, "info.template_saved", path=path)

    def _on_about(self) -> None:
        dialogs.show_info(self, "info.about")

    # ---- 语言 ----
    def _on_language(self, lang: str) -> None:
        set_language(lang)  # 触发所有已注册 retranslate
        self._settings.data["language"] = lang
        self._settings.save()

    # ---- 求解/状态栏 ----
    def _on_solve_started(self) -> None:
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.show()
        self._btn_cancel.show()

    def _on_progress(self, pct: int) -> None:
        self._progress.setValue(max(0, min(100, pct)))

    def _on_solve_finished(self, _result: object) -> None:
        self._end_solve_ui()
        c = self._controller
        self.result_panel.show_solution(c.solution, c.parts, c.stock, c.mode == "exact")
        if c.solution is not None:
            self.cutting_view.show_solution(c.solution, c.parts, c.stock)

    def _on_solve_failed(self, _issues: list[object]) -> None:
        self._end_solve_ui()

    def _on_issues_found(self, _issues: list[object]) -> None:
        self._end_solve_ui()

    def _end_solve_ui(self) -> None:
        self._progress.hide()
        self._btn_cancel.hide()

    def _on_cancel(self) -> None:
        self._controller.cancel_solve()

    # ---- retranslate ----
    def retranslate(self) -> None:
        self.setWindowTitle(tr("app.title"))
        self._menu_file.setTitle(tr("menu.file"))
        self._act_import.setText(tr("menu.file.import_excel"))
        self._act_export_x.setText(tr("menu.file.export_excel"))
        self._act_export_p.setText(tr("menu.file.export_pdf"))
        self._act_print.setText(tr("menu.file.print"))
        self._act_exit.setText(tr("menu.file.exit"))
        self._menu_lang.setTitle(tr("menu.language"))
        self._lang_actions["zh_CN"].setText(tr("menu.language.zh_CN"))
        self._lang_actions["en_US"].setText(tr("menu.language.en_US"))
        self._menu_help.setTitle(tr("menu.help"))
        self._act_template.setText(tr("menu.help.template"))
        self._act_about.setText(tr("menu.help.about"))
        self._btn_cancel.setText(tr("btn.cancel"))
        # 同步单选状态
        cur = current_language()
        self._lang_actions.get(cur, self._lang_actions["zh_CN"]).setChecked(True)
        # 面板刷新（input_panel 自注册，其余手动）
        self.result_panel.retranslate()
        self.cutting_view.retranslate()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self._controller.cancel_solve()
        super().closeEvent(event)


__all__ = ["MainWindow"]
