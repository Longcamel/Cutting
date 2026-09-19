"""参数与零件录入面板（详细设计 §5.2）。

布局：参数区（原料长度/锯缝/材料/公司/项目）+ 零件表格 + 求解模式 + 开始计算按钮。
职责边界：只做控件读写与行级格式校验（E002）；领域校验交 controller.start_solve。

表格结构：数据列 名称/长度/数量 三列，第 4 列为窄行删除按钮列（表头为空，
视觉上仍是三数据列）；末行为跨列的「＋」加行按钮行。
"""

import logging

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor, QKeyEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.controller import AppController
from core.models import Part, StockSpec
from core.validator import MAX_NAME_LEN, Issue
from i18n import on_language_changed, tr

_logger = logging.getLogger(__name__)

_ERR_BG = QColor("#FFC7CE")  # 错误行红底高亮
_CLEAR_BG = QBrush()  # 默认 NoBrush，用于清除错误高亮
_EMPTY = ""


class _PartsTable(QTableWidget):
    """数据行（名称/长度/数量 + 行删除按钮）+ 末行「＋」加行 + Ctrl+V 粘贴。"""

    addRequested = Signal(list)  # list[tuple[name,length,qty]]，粘贴多行时一次发出
    removeRequested = Signal(int)  # 数据行行号

    COLS = 4
    COL_DEL = 3

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(0, self.COLS, parent)
        hh = self.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.setColumnWidth(self.COL_DEL, 30)
        self.verticalHeader().setVisible(False)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._data_rows = 0
        self._add_btn = QPushButton("＋")
        self._add_btn.setFlat(True)
        self._add_btn.clicked.connect(lambda: self.add_row(focus=True))
        self._refresh_add_row()

    # ---------- 行模型 ----------
    def _cell_text(self, r: int, c: int) -> str:
        item = self.item(r, c)
        return item.text().strip() if item is not None else _EMPTY

    def iter_data_rows(self) -> list[tuple[str, str, str]]:
        return [
            (self._cell_text(r, 0), self._cell_text(r, 1), self._cell_text(r, 2))
            for r in range(self._data_rows)
        ]

    def add_row(
        self, name: str = _EMPTY, length: str = _EMPTY, qty: str = _EMPTY, focus: bool = False
    ) -> None:
        r = self._data_rows
        self.insertRow(r)
        for c, text in enumerate((name, length, qty)):
            self.setItem(r, c, QTableWidgetItem(text))
        btn = QPushButton("✕")
        btn.setFixedWidth(24)
        btn.setFlat(True)
        btn.clicked.connect(self._on_del_clicked)
        self.setCellWidget(r, self.COL_DEL, btn)
        self._data_rows += 1
        self._refresh_add_row()
        if focus:
            self.setCurrentCell(r, 1)

    def delete_row(self, trow: int) -> None:
        if 0 <= trow < self._data_rows:
            self.removeRow(trow)
            self._data_rows -= 1
            self._refresh_add_row()

    def clear_data_rows(self) -> None:
        while self._data_rows:
            self.delete_row(0)

    # ---------- 「＋」加行按钮行（始终位于末尾） ----------
    def _refresh_add_row(self) -> None:
        if self.rowCount() > self._data_rows:  # 旧加行行存在则删除
            self.removeRow(self._data_rows)
        r = self._data_rows
        self.insertRow(r)
        self.setSpan(r, 0, 1, self.COLS)
        self.setCellWidget(r, 0, self._add_btn)

    def _on_del_clicked(self) -> None:
        btn = self.sender()
        for r in range(self._data_rows):
            if self.cellWidget(r, self.COL_DEL) is btn:
                self.removeRequested.emit(r)
                return

    # ---------- Ctrl+V 粘贴多行（Excel 格式：行 \n / 列 \t） ----------
    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_V and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self._paste_clipboard()
            return
        super().keyPressEvent(event)

    def _paste_clipboard(self) -> None:
        text = QApplication.clipboard().text()
        if not text:
            return
        rows: list[tuple[str, str, str]] = []
        for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
            if not line.strip():
                continue
            cells = (line.split("\t") + [_EMPTY, _EMPTY, _EMPTY])[:3]
            rows.append((cells[0].strip(), cells[1].strip(), cells[2].strip()))
        if rows:
            self.addRequested.emit(rows)

    # ---------- 国际化 ----------
    def retranslate(self) -> None:
        self.setHorizontalHeaderLabels(
            [tr("input.col_name"), tr("input.col_length"), tr("input.col_qty"), _EMPTY]
        )
        self._add_btn.setText("＋ " + tr("input.add_row"))


class InputPanel(QWidget):
    """左侧面板。controller 注入；进度/结果经信号抛给 MainWindow。"""

    progressChanged = Signal(int)
    solveRequested = Signal()  # 求解已开始（按钮已切取消态）
    solveFinished = Signal(object)  # Solution
    solveFailed = Signal(list)  # 求解器/领域错误 list[Issue]
    issuesFound = Signal(
        list
    )  # 录入行级错误或 E008 list[Issue]（Qt Signal 不支持参数化，文档见上）

    def __init__(self, controller: AppController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._controller = controller
        self._solving = False
        self._build_ui()
        self._wire()
        self.restore_from_settings()
        self.retranslate()
        on_language_changed(self.retranslate)

    # ================= UI 构建 =================
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        self.grp_params = QGroupBox()
        form = QFormLayout(self.grp_params)
        self.spin_stock = QSpinBox()
        self.spin_stock.setRange(1, 1000000)
        self.spin_kerf = QSpinBox()
        self.spin_kerf.setRange(0, 100)
        self.edit_material = QLineEdit()
        self.edit_material.setMaxLength(30)
        self.edit_company = QLineEdit()
        self.edit_company.setMaxLength(50)
        self.edit_project = QLineEdit()
        self.edit_project.setMaxLength(50)
        self.lbl_stock = QLabel()
        self.lbl_kerf = QLabel()
        self.lbl_material = QLabel()
        self.lbl_company = QLabel()
        self.lbl_project = QLabel()
        form.addRow(self.lbl_stock, self.spin_stock)
        form.addRow(self.lbl_kerf, self.spin_kerf)
        form.addRow(self.lbl_material, self.edit_material)
        form.addRow(self.lbl_company, self.edit_company)
        form.addRow(self.lbl_project, self.edit_project)
        root.addWidget(self.grp_params)

        self.grp_parts = QGroupBox()
        pv = QVBoxLayout(self.grp_parts)
        self.table = _PartsTable(self)
        pv.addWidget(self.table)
        root.addWidget(self.grp_parts, stretch=1)

        self.grp_mode = QGroupBox()
        mh = QHBoxLayout(self.grp_mode)
        self.radio_fast = QRadioButton()
        self.radio_exact = QRadioButton()
        mh.addWidget(self.radio_fast)
        mh.addWidget(self.radio_exact)
        mh.addStretch(1)
        root.addWidget(self.grp_mode)

        self.btn_calc = QPushButton()
        root.addWidget(self.btn_calc)

    def _wire(self) -> None:
        self.btn_calc.clicked.connect(self._on_calc_clicked)
        self.radio_fast.toggled.connect(self._on_fast_toggled)
        self.radio_exact.toggled.connect(self._on_exact_toggled)
        self.spin_stock.valueChanged.connect(self._push_stock)
        self.spin_kerf.valueChanged.connect(self._push_stock)
        for w in (self.edit_material, self.edit_company, self.edit_project):
            w.textChanged.connect(self._push_stock)
        self.table.addRequested.connect(self._append_rows)
        self.table.removeRequested.connect(self.table.delete_row)

    def _append_rows(self, rows: list[tuple[str, str, str]]) -> None:
        """粘贴等多行追加（空三格行跳过）；新数据到来时清除旧的错误高亮。"""
        self._clear_highlights()
        for name, length, qty in rows:
            self.table.add_row(name, length, qty)

    # ================= 设置回填 / 写回（T7） =================
    def restore_from_settings(self) -> None:
        """启动时从 controller.stock（已含 settings 回填）恢复参数与模式。"""
        s = self._controller.stock
        widgets = (
            self.spin_stock,
            self.spin_kerf,
            self.edit_material,
            self.edit_company,
            self.edit_project,
        )
        for w in widgets:
            w.blockSignals(True)
        self.spin_stock.setValue(s.length)
        self.spin_kerf.setValue(s.kerf)
        self.edit_material.setText(s.material)
        self.edit_company.setText(s.company)
        self.edit_project.setText(s.project)
        for w in widgets:
            w.blockSignals(False)
        (self.radio_exact if self._controller.mode == "exact" else self.radio_fast).setChecked(True)

    def _push_stock(self) -> None:
        """参数变更即写回并持久化。"""
        self._controller.set_stock(
            StockSpec(
                length=self.spin_stock.value(),
                kerf=self.spin_kerf.value(),
                material=self.edit_material.text().strip(),
                company=self.edit_company.text().strip(),
                project=self.edit_project.text().strip(),
            )
        )

    # ================= 收集与行校验（T3） =================
    def collect(self) -> tuple[list[Part], StockSpec | None]:
        """收集零件与参数。

        非法行红底高亮并 emit issuesFound(E002,row)，返回 ([], None)；
        全空行忽略；空名称允许；row 下标按可见行序（跳全空行）计。
        """
        parts: list[Part] = []
        issues: list[Issue] = []
        self._clear_highlights()
        visible = -1  # 可见行序（跳全空行）
        for trow, (name, len_txt, qty_txt) in enumerate(self.table.iter_data_rows()):
            if not (name or len_txt or qty_txt):
                continue  # 全空行忽略
            visible += 1
            length = self._parse_int(len_txt)
            qty = self._parse_int(qty_txt)
            row_issues: list[Issue] = []  # 每个非法字段一条 E002
            if len(name) > MAX_NAME_LEN:
                row_issues.append(Issue("E002", row=visible, detail="name too long"))
            if length is None or length < 1:
                row_issues.append(Issue("E002", row=visible, detail=f"length={len_txt!r}"))
            if qty is None or qty < 1:
                row_issues.append(Issue("E002", row=visible, detail=f"qty={qty_txt!r}"))
            if row_issues:
                issues.extend(row_issues)
                self._highlight_row(trow)
                continue
            assert length is not None and qty is not None
            parts.append(Part(length=length, qty=qty, name=name))
        if issues:
            self.issuesFound.emit(issues)
            return [], None
        stock = StockSpec(
            length=self.spin_stock.value(),
            kerf=self.spin_kerf.value(),
            material=self.edit_material.text().strip(),
            company=self.edit_company.text().strip(),
            project=self.edit_project.text().strip(),
        )
        self._controller.set_parts(parts)
        self._controller.set_stock(stock)
        return parts, stock

    @staticmethod
    def _parse_int(text: str) -> int | None:
        try:
            return int(text.strip())
        except ValueError:
            return None

    def _highlight_row(self, trow: int) -> None:
        for c in range(3):
            item = self.table.item(trow, c)
            if item is None:
                item = QTableWidgetItem(_EMPTY)
                self.table.setItem(trow, c, item)
            item.setBackground(_ERR_BG)

    def _clear_highlights(self) -> None:
        for r in range(self.table.rowCount()):
            for c in range(3):
                item = self.table.item(r, c)
                if item is not None:
                    item.setBackground(_CLEAR_BG)

    # ================= 求解控制（T5） =================
    def _on_calc_clicked(self) -> None:
        if self._solving:
            self._controller.cancel_solve()
            self._set_solving(False)
            return
        parts, stock = self.collect()
        if stock is None:  # 行级错误已高亮并发 issuesFound
            return
        if self.radio_exact.isChecked() and len(parts) > 25:
            issue = Issue("E008", detail=str(len(parts)))
            self.issuesFound.emit([issue])  # 弹窗提示由 main_window 统一处理，避免阻塞
            return
        self._set_solving(True)
        self.solveRequested.emit()
        self._controller.start_solve(
            self._controller.mode,
            on_progress=self.progressChanged.emit,
            on_done=self._on_done,
            on_error=self._on_error,
        )

    def _on_done(self, solution: object) -> None:
        self._set_solving(False)
        self.solveFinished.emit(solution)

    def _on_error(self, issues: list[Issue]) -> None:
        self._set_solving(False)
        self.solveFailed.emit(issues)

    def _set_solving(self, solving: bool) -> None:
        self._solving = solving
        self.btn_calc.setText(tr("btn.cancel") if solving else tr("btn.calculate"))
        self.grp_params.setEnabled(not solving)
        self.grp_parts.setEnabled(not solving)
        self.grp_mode.setEnabled(not solving)

    # ================= 模式（T4） =================
    def _on_fast_toggled(self, checked: bool) -> None:
        if checked:
            self._controller.mode = "fast"

    def _on_exact_toggled(self, checked: bool) -> None:
        if checked:
            self._controller.mode = "exact"

    # ================= 对外接口 =================
    def set_parts(self, parts: list[Part]) -> None:
        """Excel 导入等外部填充零件表；末尾留一个空行便于继续录入。"""
        self.table.clear_data_rows()
        for p in parts:
            self.table.add_row(p.name, str(p.length), str(p.qty))
        self.table.add_row()

    def set_solving(self, solving: bool) -> None:
        """外部（MainWindow）强制复位按钮态。"""
        self._set_solving(solving)

    # ================= 国际化（T6） =================
    def retranslate(self) -> None:
        self.grp_params.setTitle(tr("input.group_params"))
        self.grp_parts.setTitle(tr("input.parts_table"))
        self.grp_mode.setTitle(tr("input.mode"))
        self.lbl_stock.setText(tr("input.stock_length"))
        self.lbl_kerf.setText(tr("input.kerf"))
        self.lbl_material.setText(tr("input.material"))
        self.lbl_company.setText(tr("input.company"))
        self.lbl_project.setText(tr("input.project"))
        self.radio_fast.setText(tr("input.mode.fast"))
        self.radio_exact.setText(tr("input.mode.exact"))
        self.table.retranslate()
        self.btn_calc.setText(tr("btn.cancel") if self._solving else tr("btn.calculate"))


__all__ = ["InputPanel"]
