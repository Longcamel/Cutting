# 模块：io/pdf_reporter.py —— PDF 报告

- 详细设计：§6.3 | 里程碑：M4 | 依赖：models、i18n、cutting_view.render_to_painter（注入） | 测试：tests/test_pdf.py

## 子任务
- [ ] T1 注册 assets/fonts 内嵌中文字体（pdfmetrics + TTFont），A4 纵向 platypus 文档骨架
- [ ] T2 抬头：公司名/项目名（非空才显示，居中大字）+ 材料/日期
- [ ] T3 参数与统计表（同 Excel Sheet1 内容，词条随 lang）
- [ ] T4 切割示意图：每切法一条矢量横条（调注入的 render_bar），右侧"×N 根"；超宽按比例缩放
- [ ] T5 方案明细表 + 零件核对表
- [ ] T6 实现 `build_pdf(path, sol, parts, stock, lang, render_bar)`；写文件异常 → E007
- [ ] T7 测试：注入空 render_bar，生成 PDF 成功且文件非空；中英文各生成一份
- [ ] T8 `pytest tests/test_pdf.py` 通过

## 验收
- [ ] PDF 中文正常显示无方块；图与屏幕示意图一致；无公司/项目名时版面不空洞
