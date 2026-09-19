# 模块：ui/dialogs.py —— 弹窗工具

- 详细设计：§5.5 | 里程碑：M2 | 依赖：models、i18n | 测试：手动联调

## 子任务
- [x] T1 实现 `show_issues(parent, issues)`：按 tr('err.'+code) 取模板，row>=0 时格式化行号；多条合并为一个可滚动弹窗
- [x] T2 实现 `show_info(parent, key, **kw)` 信息弹窗
- [x] T3 实现 `ask_file(parent, mode, filters)` 封装打开/保存文件对话框（导入/导出共用）

## 验收
- [x] 错误文案中英文随语言切换；含行号定位；多条错误一窗显示
