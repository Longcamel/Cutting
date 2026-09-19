# 模块：ui/cutting_view.py —— 切割示意图控件

- 详细设计：§5.4 | 里程碑：M2 | 依赖：models | 测试：手动联调 + tests/test_pdf.py 间接覆盖

## 子任务
- [x] T1 基于 QGraphicsView/Scene：单根横条绘制，比例 `px_per_mm=可用宽度/stock.length`，段宽=max(1px, length×比例)
- [x] T2 配色：PALETTE 20 色按 part_idx 循环；余料浅灰；段内文字"名称+长度"，放不下逐级省略，tooltip 显示完整
- [x] T3 多行布局：每行一切法 + 右侧"×N 根"；行高 28px 间距 6px；顶部 mm 刻度尺（0 / L/2 / L）
- [x] T4 实现 `show_solution(sol, stock)` 重绘；视口只绘可见区（QGraphicsView 自带）
- [x] T5 实现 `render_to_painter(painter, sol, stock, width_px)` 供 pdf_reporter 复用（不依赖窗口显示）
- [x] T6 性能验证：100+ 切法滚动流畅

## 验收
- [x] 图形与方案表格数据一致；屏幕图与 PDF 图一致；大方案不卡
