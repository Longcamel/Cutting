
## D3（M2 settings）
`io` 包与 Python 标准库内置 `io` 模块冲突（stdlib 内置优先，`from io.settings import` 必失败）。
设计 §6.4 的 `io/` 包重命名为 `fileio/`（settings/excel_importer/excel_exporter/pdf_reporter 均归入）。
## D4（M2 controller）
worker.failed 信号优先携带 `e.code`（TooManyKindsError → "E008" 经错误码表直达词条）；
未带 code 的异常在 controller 归为 **E009 求解器内部错误**（补充错误码，err.E009 词条已加 zh/en）。

## D5（M2 controller 测试注入）
fileio 的 excel/pdf 子模块在 M3 才实现。controller 用 `importlib.import_module("fileio.xxx")`
延迟导入；测试经 `monkeypatch.setitem(sys.modules, ...)` 注入假模块即可生效
（`from fileio import xxx` 对 sys.modules 里的假模块会因父包无属性而失败）。
## D6（M2 controller 收尾）
1. i18n 词条 err.E006/E007 原文案（计算已取消/求解超时）与设计 §9 错误码表冲突，
   以 §9 为准修正为「无计算结果，无法导出」/「文件读写失败」。
2. controller._done 增加 `sol is None` 守卫：取消时求解器返回 None，静默结束（不弹错）。
3. controller.__init__ 启动即从 settings.data 回填 stock（stock_length/kerf/material/company/project）。
## D7（M2 input_panel 接口契约）
1. 信号：progressChanged(int) / solveRequested() / solveFinished(object) / solveFailed(list) /
   issuesFound(list)。录入行级错误与 E008 走 issuesFound；求解失败走 solveFailed；弹窗由 main_window 统一处理
   （面板内禁止阻塞式 QMessageBox，offscreen 测试会挂死）。
2. collect() 返回 (parts, stock) 2 元组；任一字段非法 → 该行红底高亮 + emit issuesFound，
   返回 ([], None)。E002 按字段粒度计 Issue；row=可见行序（跳全空行）；空名称允许（匿名零件）；
   collect 成功即回写 controller.set_parts/set_stock（含 settings 持久化）。
3. 参数区用 textChanged（非 editingFinished）即时回写 controller 并持久化，setText 也触发。
4. 表格初始 0 行数据，行尾常驻「＋」加行按钮（span）；delete_row 发 removeRequested 由面板转 table.delete_row。
   粘贴/批量追加发 addRequested → _append_rows（先清旧高亮）。行高亮清除必须用默认 QBrush()（NoBrush），
   Qt6 下 NoBrush.color() 仍返回有效黑色，测试断言应判 style()==NoBrush。
5. E008（exact 模式种类>25）只在点击计算时检查并发 issuesFound，不做阻塞弹窗；切 exact 时仅改 controller.mode。
## D8（M2 result_panel 契约）
1. 接口：show_solution(sol, parts, stock, exact_mode=False)。面板纯展示，无求解/持久化逻辑。
2. 统计行：sol.exact → 追加「✔最优」；exact_mode 且非 exact（超时最好解）→ 追加「（当前最好，非最优）」；
   快速模式解不加任何标注。
3. sol.stats 为 None 时用 statistics.compute(sol, parts, stock) 现算（求解器可不预填 stats）。
4. 方案表「切割明细」超长截断显示「…」，tooltip 保留全量；匿名零件显示 #序号。
   核对表差额≠0 行整行橙底（QBrush 实色，勿用透明色）。
5. retranslate() 按缓存的 sol/parts/stock 重绘，语言切换不丢内容；大表格刷新用 setUpdatesEnabled 包裹。
## D9（M2 cutting_view 契约）
1. 接口：show_solution(sol, parts, stock)（任务单未含 parts，但段内要显示零件名称，与
   result_panel 对齐）；show_solution(None,...) 清空。
2. 屏幕渲染与 render_to_painter 共用 _row_segments 布局函数（依赖倒置供 pdf_reporter 注入），
   render_to_painter 返回实际总高（可能因按比例收缩 < content_height，差值≤一行）。
3. PALETTE 20 色按 part_idx 循环；余料固定浅灰 #D9D9D9，tooltip「余料 N mm」。
   段宽=max(1, 长×px_per_mm)；段内文字逐级省略（名称+长度→长度→无）。
4. 顶部刻度尺 0/L/2/L；行高28、间距6、左右边距8；右侧「×N 根」用 result.bars_suffix 词条。
5. retranslate() 按缓存参数重绘；不注册 on_language_changed（由 main_window 统一调）。
## D10（M2 dialogs 契约）
1. format_issue 行号显示 1 基（Issue.row 为 0 基）；模板缺参自动补通用 kwargs
   （row/detail/max_len/kinds/max），调用方可用 **extra 传领域参数（如 E003 的 length/stock），
   未用 kwargs 被 str.format 忽略。
2. EXACT_MAX_KINDS=25 在 dialogs 复制定义（与 input_panel 一致，E008 的 kinds 取 issue.detail）。
3. show_issues 用自制 QDialog+QPlainTextEdit(readonly) 实现可滚动多合一弹窗，
   不用阻塞式 QMessageBox.warning 以便测试 monkeypatch exec。
4. 新增词条 dlg.warning/dlg.info/dlg.ok（双语）。

## D12 PDF 中文字体与示意图位图（M4）
- assets/fonts/NotoSansSC.ttf（OFL 许可，assets/fonts/OFL.txt）内嵌注册；
  文件缺失/损坏时回退 reportlab CID 字体 STSong-Light（不内嵌，依赖阅读器），
  保证 exe 极端环境下仍可导出。
- 示意图：注入的 render_bar(painter, pattern, scale) 画到 QImage（3× 超采样，
  保证 ≥200px/mm 分辨率），逐行白边裁剪后按文档宽度等比嵌入 PNG。
- dev 依赖新增 types-reportlab（reportlab 官方无 stubs）。
