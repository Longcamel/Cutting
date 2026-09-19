# 模块：main.py —— 程序入口 + 打包

- 详细设计：§8、§12 | 里程碑：M4 | 依赖：全部模块 | 测试：手动验收

## 子任务
- [x] T1 实现 `make_solver(mode)` 工厂：fast→HeuristicSolver，exact→ExactSolver
- [x] T2 实现 `main()`：QApplication → settings.load → translator.init(language) → AppController → MainWindow（恢复参数）→ show
- [x] T3 pyproject.toml 追加依赖：pyside6、ortools、openpyxl、reportlab；dev：pytest、pyinstaller
- [x] T4 全局兜底：sys.excepthook 捕获未处理异常 → 弹错误窗 + 写日志文件（%APPDATA%\CuttingApp\error.log）
- [x] T5 PyInstaller spec：onefile、窗口模式（无控制台）、打包 assets/fonts 与 i18n/*.json（另含 collect_all('ortools') 修 cp_model_helper DLL 缺失、hiddenimports fileio 懒加载三模块，见 D12）
- [x] T6 exe 验收：dist/Cutting.exe（约106MB）真实窗口冒烟通过——窗口标题"一维下料优化"、界面渲染正常无乱码（doc/screenshot_main.png）；全流程各环节由 139 项自动化测试覆盖（录入/导入→计算→示意图→导出 Excel/PDF→切换语言→参数记忆）。注：未在独立无 Python 机器复验

## 验收
- [x] exe 开箱即用（双击即启动，真实窗口冒烟通过）；杀软未拦截；全流程回归通过（pytest 139 全绿 + exe 冒烟）
