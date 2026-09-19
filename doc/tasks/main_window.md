# 模块：ui/main_window.py —— 主窗口

- 详细设计：§5.1 | 里程碑：M2 | 依赖：ui 其余全部、app/controller、i18n | 测试：手动联调

## 子任务
- [x] T1 布局：左 InputPanel（固定宽~380px），右侧上 ResultPanel、下 CuttingView（QSplitter 可拉伸）
- [x] T2 菜单栏：文件（导入Excel/导出Excel/导出PDF/打印/退出）、语言（中文/English 单选）、帮助（Excel模板下载/关于）
- [x] T3 状态栏：进度条（求解时显示，接 worker.progress）+ 取消按钮
- [x] T4 接线：菜单动作→controller 方法；controller 回调→ResultPanel/CuttingView 刷新；文件对话框走 dialogs.ask_file
- [x] T5 语言切换：translator.set_language → 各面板 retranslate → settings 记忆 language
- [x] T6 窗口标题、图标、启动尺寸（~1200×800）；标题走 tr('app.title')

## 验收
- [x] 全流程可走通：录入→计算→看图→导出；求解中界面不冻结可取消；语言切换全界面即时生效
