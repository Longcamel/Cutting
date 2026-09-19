# 模块：app/controller.py —— 流程编排

- 详细设计：§4.2 | 里程碑：M2 | 依赖：core 全部、worker、io/settings、io/excel_importer、io/excel_exporter、io/pdf_reporter | 测试：tests/test_controller.py

## 子任务
- [x] T1 实现构造与状态：`AppController(settings, make_solver)`，持有 parts/stock/solution
- [x] T2 实现 `set_parts()` / `set_stock()`（后者立即 settings.save()）
- [x] T3 实现 `import_excel(path)`：调 excel_importer，成功替换 parts，返回 (条数, issues)
- [x] T4 实现 `start_solve(mode, on_progress, on_done, on_error)`：校验→worker 后台求解→on_done 内 check_solution 自检（失败报 E005）→statistics 填充
- [x] T5 实现 `cancel_solve()`
- [x] T6 实现 `export_excel(path)` / `export_pdf(path)`：无 solution 返回 E006；io 异常返回 E007
- [x] T7 测试：注入假 solver + 假 io，验证全流程编排、校验失败分支、E006 分支（不启动 QApplication 的部分单独测）
- [x] T8 `pytest tests/test_controller.py` 通过

## 验收
- [x] controller 不 import ui；所有依赖经构造注入可替换；pytest 绿
