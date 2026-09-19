"""translator 模块测试（doc/tasks/translator.md，详细设计 §7）。"""

import json
from pathlib import Path

import i18n
from i18n import translator

LOCALES = Path(__file__).parent.parent / "i18n"


def test_key_sets_identical() -> None:
    zh = json.loads((LOCALES / "zh_CN.json").read_text(encoding="utf-8"))
    en = json.loads((LOCALES / "en_US.json").read_text(encoding="utf-8"))
    assert set(zh) == set(en)
    assert len(zh) > 40  # 词条覆盖面兜底


def test_error_codes_all_present() -> None:
    # E008（精确模式种数上限）已随 v1.3 移除；现有错误码：E001-E007、E009、E010
    zh = json.loads((LOCALES / "zh_CN.json").read_text(encoding="utf-8"))
    for code in [*(f"err.E{i:03d}" for i in range(1, 8)), "err.E009", "err.E010"]:
        assert code in zh, code
    assert "err.E008" not in zh


def test_tr_format_and_missing_fallback() -> None:
    translator.init("zh_CN")
    expected = "精确模式计算超过 30 秒仍未求出结果，已自动结束任务；建议使用「快速模式」"
    assert translator.tr("err.E010") == expected
    assert translator.tr("no.such.key") == "no.such.key"  # 缺失降级返回 key


def test_tr_bad_placeholder_keeps_text(caplog) -> None:
    translator.init("zh_CN")
    # 占位符参数缺失时不抛异常，返回原文
    assert "数值非法" in translator.tr("err.E002")


def test_set_language_notifies_listeners() -> None:
    translator.init("zh_CN")
    calls: list[str] = []
    translator._reset_for_test()
    i18n.on_language_changed(lambda: calls.append(translator.current_language()))
    i18n.set_language("en_US")
    assert calls == ["en_US"]
    assert translator.tr("app.title") == "1D Cutting Optimizer"
    i18n.set_language("en_US")  # 重复设置不触发
    assert calls == ["en_US"]
    i18n.set_language("zh_CN")
    assert translator.tr("app.title") == "一维下料优化"
    translator._reset_for_test()


def test_unknown_lang_fallback() -> None:
    translator.init("fr_FR")
    assert translator.current_language() == "zh_CN"
    translator.init("zh_CN")
