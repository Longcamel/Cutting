"""弹窗工具（详细设计 §5.5，M2）。

决策 D10：
- format_issue 行号一律显示 1 基（Issue.row 为 0 基下标，row>=0 时显示 row+1）；
- 模板缺参时自动补通用 kwargs（row/detail/max_len/kinds/max），
  调用方可经 **extra 补充领域参数（如 length/stock）；未用的 kwargs 被 str.format 忽略。
- show_issues/show_info 内部调 QDialog.exec()，测试中 monkeypatch exec 拦截。
"""

from __future__ import annotations

from typing import Any, Literal

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.validator import MAX_NAME_LEN, Issue
from i18n.translator import tr

# 精确模式零件种类上限（与 ui.input_panel / core.exact_solver 保持一致）
EXACT_MAX_KINDS = 25


def format_issue(issue: Issue, **extra: Any) -> str:
    """单条 Issue → 用户可读文本（词条 err.<code>）。"""
    kwargs: dict[str, Any] = {
        "row": issue.row + 1 if issue.row >= 0 else "",
        "detail": issue.detail,
        "max_len": MAX_NAME_LEN,
        "kinds": issue.detail,
        "max": EXACT_MAX_KINDS,
    }
    kwargs.update(extra)
    return tr(f"err.{issue.code}", **kwargs)


def _scroll_dialog(parent: QWidget | None, title: str, text: str) -> QDialog:
    """只读可滚动文本弹窗（多条信息合并显示）。"""
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    dlg.resize(480, 320)
    lay = QVBoxLayout(dlg)
    edit = QPlainTextEdit(dlg)
    edit.setReadOnly(True)
    edit.setPlainText(text)
    lay.addWidget(edit)
    btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok, parent=dlg)
    btns.button(QDialogButtonBox.StandardButton.Ok).setText(tr("dlg.ok"))
    btns.accepted.connect(dlg.accept)
    lay.addWidget(btns)
    return dlg


def show_issues(parent: QWidget | None, issues: list[Issue], **extra: Any) -> None:
    """校验/求解错误弹窗：多条合并为一个可滚动弹窗。"""
    if not issues:
        return
    text = "\n".join(format_issue(i, **extra) for i in issues)
    _scroll_dialog(parent, tr("dlg.warning"), text).exec()


def show_info(parent: QWidget | None, key: str, **kw: Any) -> None:
    """信息弹窗，key 为 i18n 词条键。"""
    QMessageBox.information(parent, tr("dlg.info"), tr(key, **kw))


def ask_file(
    parent: QWidget | None,
    mode: Literal["open", "save"],
    filters: str,
    title: str = "",
) -> str | None:
    """打开/保存文件对话框封装（导入/导出共用）。返回 None 表示用户取消。"""
    if mode == "open":
        path, _ = QFileDialog.getOpenFileName(parent, title, "", filters)
    else:
        path, _ = QFileDialog.getSaveFileName(parent, title, "", filters)
    return path or None


__all__ = ["EXACT_MAX_KINDS", "ask_file", "format_issue", "show_info", "show_issues"]
