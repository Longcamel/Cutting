# 模块：io/excel_importer.py —— Excel 导入 + 模板

- 详细设计：§6.1 | 里程碑：M3 | 依赖：models、i18n（模板表头） | 测试：tests/test_excel.py

## 子任务
- [x] T1 创建 `io/__init__.py` 和 `io/excel_importer.py`；实现 `load_parts(path)`：openpyxl 只读模式逐行解析三列（名称可空/长度/数量）
- [x] T2 兼容处理：跳过完全空行；B/C 缺失或非正整数 → Issue(E002,row=行号)；仅两列模板也兼容；全部行无效 → Issue(E004)
- [x] T3 错行策略：有错行时仍返回成功解析的 parts + issues（由 UI 决定继续或重导）
- [x] T4 实现 `create_template(path, lang)`：生成表头（随语言）+ 1 行示例
- [x] T5 测试：临时 xlsx 覆盖 正常三列/两列/坏行定位/非数字/超长名称/E004/文件占用(E007)
- [x] T6 `pytest tests/test_excel.py`（导入部分）通过

## 验收
- [x] 模板可直接打开使用；错误行号与 Excel 实际行号一致；pytest 绿
