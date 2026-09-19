# 模块：i18n/translator.py —— 多语言

- 详细设计：§7 | 里程碑：M2 | 依赖：无 | 测试：tests/test_i18n.py

## 子任务
- [x] T1 创建 `i18n/__init__.py`、`i18n/translator.py`、`i18n/zh_CN.json`、`i18n/en_US.json`
- [x] T2 词条骨架：错误码 err.E001–E008 + app.title + menu.* + input.* + btn.* + report.*（先占位，随各模块开发补充；文案含 {row} 占位符）
- [x] T3 实现 `init(lang)` / `tr(key, **kw)`（缺失 key 返回 key 并记日志）/ `set_language(lang)` / `on_language_changed(cb)`
- [x] T4 测试：两 JSON key 集合完全相等；tr 格式化与缺失降级；set_language 通知全部 listener
- [x] T5 `pytest tests/test_i18n.py` 通过

## 验收
- [x] 任何界面/报表文字无硬编码（抽查）；切换语言无需重启；pytest 绿
