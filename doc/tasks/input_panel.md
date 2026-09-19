# 模块：ui/input_panel.py —— 参数与零件录入面板

- 详细设计：§5.2 | 里程碑：M2 | 依赖：models、i18n | 测试：手动联调 + tests/test_controller.py 间接覆盖

## 子任务
- [x] T1 创建 `ui/__init__.py` 和 `ui/input_panel.py`；参数控件区：原料长度 QSpinBox(1–1000000,默认6000)、锯缝 QSpinBox(0–100,默认3)、材料/公司名/项目名 QLineEdit(可空)
- [x] T2 零件表格 QTableWidget 3 列（名称[可空]/长度/数量）：行尾"＋"加行、行右"✕"删行、支持 Ctrl+V 从 Excel 粘贴多行
- [x] T3 实现 `collect() -> (parts, stock)`：空名称允许；非法值构造 Issue(E002,row) 并红底高亮错误行
- [x] T4 求解模式单选（快速默认/精确）：选精确且种数>25 弹 E008 提示
- [x] T5 "开始计算"按钮：点击→collect→controller.start_solve；求解中变"取消"→controller.cancel_solve
- [x] T6 实现 `retranslate()`：全部 setText/表头走 tr()；注册 on_language_changed
- [x] T7 实现参数回填（启动时从 settings 恢复）与变更即写回

## 验收
- [x] 手工录入/粘贴/增删行流畅；非法输入正确高亮并弹错；切换语言界面即时刷新
