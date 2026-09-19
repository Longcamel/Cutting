# 模块：io/excel_exporter.py —— 方案导出

- 详细设计：§6.2 | 里程碑：M3 | 依赖：models、i18n | 测试：tests/test_excel.py

## 子任务
- [x] T1 实现 `save_report(path, sol, parts, stock, lang)`：Sheet1 参数统计（公司/项目/材料/原料长度/锯缝/日期 + 根数/利用率/零件总长/锯缝损耗/废料总长）
- [x] T2 Sheet2 切割方案：`切法# | 明细 | 余料 | 根数`，列宽自适应
- [x] T3 Sheet3 零件核对：`名称 | 长度 | 需求 | 实切 | 差额`
- [x] T4 文件写入异常 → 抛 E007（由 controller 捕获）
- [x] T5 测试：导出后重新打开校验三 Sheet 关键单元格数值与 Solution 一致
- [x] T6 `pytest tests/test_excel.py`（导出部分）通过

## 验收
- [x] Excel 打开无警告；数值与界面显示一致；中文表头随语言参数切换
