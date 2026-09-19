"""词条加载与语言切换（详细设计 §7.1）。

词条文件：i18n/{lang}.json（扁平 key，点分层），两文件 key 集合必须一致。
"""

import json
import logging
from collections.abc import Callable
from pathlib import Path

_logger = logging.getLogger(__name__)

_current = "zh_CN"
_dict: dict[str, str] = {}
_listeners: list[Callable[[], None]] = []

_LOCALES_DIR = Path(__file__).parent
SUPPORTED_LANGS = ("zh_CN", "en_US")


def _load(lang: str) -> dict[str, str]:
    path = _LOCALES_DIR / f"{lang}.json"
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    return {str(k): str(v) for k, v in data.items()}


def init(lang: str) -> None:
    """启动时调用，加载 i18n/{lang}.json；未知语言回退 zh_CN。"""
    global _current, _dict
    _current = lang if lang in SUPPORTED_LANGS else "zh_CN"
    if lang != _current:
        _logger.warning("未知语言 %r，回退 zh_CN", lang)
    _dict = _load(_current)


def current_language() -> str:
    return _current


def tr(key: str, **kw: object) -> str:
    """查词条并 format；key 缺失 -> 返回 key 本身并记日志。"""
    if not _dict:
        init(_current)
    text = _dict.get(key)
    if text is None:
        _logger.warning("词条缺失: %s", key)
        return key
    if kw:
        try:
            return text.format(**kw)
        except (KeyError, IndexError, ValueError) as exc:
            _logger.warning("词条格式化失败 %s: %s", key, exc)
            return text
    return text


def set_language(lang: str) -> None:
    """重载词条 + 依次通知 listeners（各界面 retranslate）。"""
    if lang == _current:
        return
    init(lang)
    for cb in list(_listeners):
        cb()


def on_language_changed(cb: Callable[[], None]) -> None:
    """注册刷新回调。"""
    _listeners.append(cb)


def _reset_for_test() -> None:
    """测试辅助：清空监听器。"""
    _listeners.clear()


__all__ = [
    "SUPPORTED_LANGS",
    "current_language",
    "init",
    "on_language_changed",
    "set_language",
    "tr",
]
