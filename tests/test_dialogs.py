"""ui/dialogs 单元测试（offscreen Qt）。"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QDialog, QMessageBox

from core.validator import Issue
from i18n.translator import _reset_for_test, set_language
from ui import dialogs


@pytest.fixture(autouse=True)
def _zh() -> None:
    _reset_for_test()
    set_language("zh_CN")


def test_format_issue_row_one_based() -> None:
    text = dialogs.format_issue(Issue("E002", row=0))
    assert "第 1 行" in text
    text = dialogs.format_issue(Issue("E002", row=4))
    assert "第 5 行" in text
    assert "max_len" not in text  # 模板参数已替换


def test_format_issue_e008_uses_detail_and_max() -> None:
    text = dialogs.format_issue(Issue("E008", detail="30"))
    assert "30" in text and "25" in text


def test_format_issue_extra_kwargs() -> None:
    text = dialogs.format_issue(Issue("E003", row=1), length=7000, stock=6000)
    assert "7000" in text and "6000" in text
    set_language("en_US")
    text_en = dialogs.format_issue(Issue("E003", row=1), length=7000, stock=6000)
    assert "7000" in text_en and "6000" in text_en


def test_show_issues_scrollable_dialog(
    monkeypatch: pytest.MonkeyPatch, qtbot: object
) -> None:
    captured: dict[str, object] = {}
    orig = dialogs._scroll_dialog

    def spy(parent: object, title: str, text: str) -> QDialog:
        captured["title"] = title
        captured["text"] = text
        dlg = orig(parent, title, text)  # type: ignore[arg-type]
        captured["dlg"] = dlg
        return dlg

    monkeypatch.setattr(dialogs, "_scroll_dialog", spy)
    monkeypatch.setattr(QDialog, "exec", lambda self: 1)
    issues = [Issue("E002", row=i) for i in range(20)]
    dialogs.show_issues(None, issues)
    text = str(captured["text"])
    assert text.count("\n") == 19  # 20 条合并一窗
    assert "第 20 行" in text


def test_show_issues_empty_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        QDialog,
        "exec",
        lambda self: pytest.fail("不应弹窗"),
    )
    dialogs.show_issues(None, [])


def test_show_info_calls_messagebox(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, str] = {}

    def fake(parent: object, title: str, text: str) -> int:
        seen["title"] = title
        seen["text"] = text
        return 0

    monkeypatch.setattr(QMessageBox, "information", staticmethod(fake))
    dialogs.show_info(None, "result.empty")
    assert "暂无计算结果" in seen["text"]


def test_ask_file_open_and_save(monkeypatch: pytest.MonkeyPatch) -> None:
    from PySide6.QtWidgets import QFileDialog

    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: ("in.xlsx", ""))
    )
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: ("out.pdf", ""))
    )
    assert dialogs.ask_file(None, "open", "*.xlsx") == "in.xlsx"
    assert dialogs.ask_file(None, "save", "*.pdf") == "out.pdf"
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: ("", "")))
    assert dialogs.ask_file(None, "open", "*.xlsx") is None
