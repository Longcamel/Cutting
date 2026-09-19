# 一维下料软件 —— 总体进度

> 规则：模块的全部子任务勾选且验收标准达成后，才勾选本表对应模块。
> 依据：doc/proposal.md、doc/detailed-design.md

## M1 核心算法（pytest 全绿）

- [x] [models](models.md) —— 数据模型（按详细设计 §2 修正，7 测试）
- [x] [validator](validator.md) —— 输入校验 + 结果自检（10 测试；core 累计 22 测试 100% 覆盖）
- [x] [statistics](statistics.md) —— 利用率统计（切口数不变式，4 测试；core 累计覆盖率 100%）
- [x] [heuristic_solver](heuristic_solver.md) —— 快速模式（基准：≤6根、利用率≥75%（D2修正）、千级<10s；9测试）
- [x] [exact_solver](exact_solver.md) —— 精确模式（CP-SAT，≤25种）

**M1 出口标准**：[x] 基准用例通过；100 组随机性质测试全过 check_solution

## M2 界面与调度

- [x] [translator](translator.md) —— 中英文切换
- [x] [worker](worker.md) —— 后台求解线程
- [x] [controller](controller.md) —— 流程编排（注：excel/pdf/settings 可先用假实现）
- [x] [input_panel](input_panel.md) —— 参数+零件录入
- [x] [result_panel](result_panel.md) —— 统计+方案表格
- [x] [cutting_view](cutting_view.md) —— 切割示意图
- [x] [dialogs](dialogs.md) —— 弹窗工具
- [x] [main_window](main_window.md) —— 主窗口集成

**M2 出口标准**：[x] 界面全流程走通（手工录入→计算→示意图/表格），求解不卡界面可取消，语言即时切换

## M3 Excel 导入导出

- [x] [excel_importer](excel_importer.md) —— 三列模板导入 + 模板下载
- [x] [excel_exporter](excel_exporter.md) —— 三 Sheet 方案导出

**M3 出口标准**：[x] 模板导入（含坏行提示）与导出回归通过

## M4 报告、记忆与打包

- [x] [pdf_reporter](pdf_reporter.md) —— PDF 报告（公司/项目抬头）+ 打印
- [x] [settings](settings.md) —— 参数记忆
- [x] [main](main.md) —— 入口 + PyInstaller 打包 exe（5 测试；exe 真实窗口冒烟通过）

**M4 出口标准**：[x] exe 验收通过（本机真实窗口冒烟 + 139 测试回归；注：未在独立无 Python 机器复验）

---

## 需求覆盖核对（全部模块完成后逐项验收）

- [x] F1.1 手工录入 / F1.2 Excel导入 / F1.3 参数设置 / F1.4 数据校验
- [x] F2.1 一键优化 / F2.2 利用率 / F2.3 双模式+取消 / F2.4 合法性自检
- [x] F3.1 示意图 / F3.2 方案表格 / F3.3 导出Excel / F3.4 导出打印PDF
- [x] F4.1 打包exe / F4.2 参数记忆 / F4.3 中文错误提示 / F4.4 中英文切换

（核对依据：17 个测试模块 139 用例逐项覆盖 + dist/Cutting.exe 真实窗口冒烟 doc/screenshot_main.png）
