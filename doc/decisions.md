# 决策记录（主 Agent 全程沉淀）

## D1 2026-09-19 models 结构以详细设计 §2 为准纠正

**背景**：首次实现 `core/models.py` 时按任务文件 models.md 的概述写了
`Part(name,length,quantity,idx)`、`CutSegment`、`CuttingPattern(segments/leftover)` 等字段，
与详细设计 §2 的权威定义冲突（Part 为 `length/qty/name` 无 idx；
CuttingPattern 用 `counts: dict[int,int]` + `bars` + `remainder`；无 CutSegment；
Statistics 含 `total_stock_len`、`waste_len`；Solution 有 `elapsed_s`）。

**裁决**：按 prompt §1 优先级，详细设计 > 任务文件。已将 models.py 重写为与 §2
逐字段一致；Issue 按 §3.1 定义在 `core/validator.py`（含 detail 字段）；
切口数不变式按 §2：余料>0→段数，余料=0→段数−1；允许多切（实切≥需求）。

**影响**：同步修订任务文件 models.md / validator.md / statistics.md 的字段描述，
避免后续误导。已完成的 models 门禁（pytest/mypy/ruff）在新结构下重跑通过后再勾选。
## D2 2026-09-19 M1 基准用例"利用率≥95%"不可达，阈值裁决为 ≥75%

**背景**：详细设计 §10 与任务文件要求基准用例（原料6000/锯缝3，零件
立柱2000×5、横梁1500×4、短撑800×10）"≤6 根、check_solution 通过、利用率 ≥95%"。

**矛盾**：零件总长 = 2000×5+1500×4+800×10 = 24000。按 §3.5 权威公式
utilization = 零件总长/(根数×6000)×100：4 根时原料总长=24000 恰好等于零件总长，
但锯缝损耗>0 必然超界（4 根不可行）；5 根时利用率上限 = 24000/30000 = 80%。
≥95% 需 ≤4.21 根，数学上不可达。详细设计与自身 §3.5 公式冲突。

**裁决**：保持 §3.5 利用率公式不变（接口冻结），将基准阈值修正为
**≤6 根且利用率 ≥75%**（5 根时 80% 留有 5% 余量；6 根时 66.7% 不合格，
故该阈值实际逼出 ≤5 根的好解）。同步修订 heuristic_solver.md 与
progress.md 中的 M1 出口标准描述。

**依据**：prompt §9 设计矛盾时主 Agent 裁决并记录。

## D11 main_window
- export_pdf 经具名 _render 适配器注入 render_bar（依赖倒置，满足 mypy strict）
- 语言菜单 QActionGroup 单选；retranslate 同步 checked；settings 记忆语言
- 状态栏进度条/取消按钮仅求解中显示；closeEvent 先 cancel_solve
- 菜单动作不 import io 模块（excel_importer 延迟导入+type ignore，M3 提供）
- 打印分页：render_to_painter 按页宽渲染、纵向偏移分页

## D12 PyInstaller 打包 ortools（2026-09-19）
- 现象：onefile exe 启动即崩，`ImportError: DLL load failed while importing cp_model_helper`（ortools 原生 DLL 未被收集）。
- 排查：console=True 构建后运行拿到 traceback；onefile 会生成子进程，taskkill 仅杀父进程会掩盖子进程崩溃，冒烟必须确认真实退出码（rc=1 暴露）。
- 决定：cutting.spec 用 `PyInstaller.utils.hooks.collect_all("ortools")` 收集 binaries/datas/hiddenimports；fileio 三个模块走 importlib 延迟导入，需列入 hiddenimports。
- ExactSolver 构造补默认值 `cancel=None`（§8 允许 `ExactSolver()` 无参构造）。

## D13 交付门禁 mypy 2.x 适配与测试层类型修复
- 问题：终门禁 `uv run mypy .` 报 80 错（全部在 tests/）。根因：mypy 2.3.1 对"部分注解函数"（如 `-> None` 但参数未注解）默认报 `no-untyped-def`，pyproject 的 tests 覆盖仅放宽了 `disallow_untyped_defs`。
- 决定：tests 覆盖追加 `disallow_incomplete_defs = false`（符合 prompt.md "ui/tests 层宽松" 意图，core/app/fileio/i18n 仍 strict）；新增 `tests/__init__.py` 使 `tests.*` override 正确匹配；其余 39 处为测试代码真实类型问题，逐条修复（Optional 收窄、monkeypatch 用 `setattr(raises=False)`、注解对齐基类签名），不放水配置。
- 结果：pytest 139 全绿、mypy 42 文件 0 错、ruff 0 错；exe 真实窗口冒烟通过（doc/screenshot_main.png）。
