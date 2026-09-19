"""多语言包（详细设计 §7）。"""

from .translator import init, on_language_changed, set_language, tr

__all__ = ["init", "on_language_changed", "set_language", "tr"]
