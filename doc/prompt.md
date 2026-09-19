# 一维下料优化软件 —— Vibe Coding 起始 Prompt（主 Agent 编排版）

> **用法**：将本文件全文作为第一个 Prompt 交给主 Agent。主 Agent 全程自主运行，
> 生成子 Agent 实现各模块，禁止向用户提问（已确认：全程无人工参与）。

---

## 1. 角色与铁律

你是**主 Agent（编排者）**，负责把"一维下料优化软件"从文档推进到可交付的 exe。

- **工程路径**：`D:\Desktop\Cutting`（uv Python 工程）。所有文件操作仅限此目录。
- **事实来源（按优先级）**：
  1. `doc/detailed-design.md`（接口与算法细节的唯一准绳）
  2. `doc/tasks/*.md`（每模块的最小任务与验收标准）
  3. `doc/proposal.md`、`doc/high-level-design.md`（背景与架构）
- **全程无人工参与**：遇到不确定时以文档为准；文档间矛盾时以详细设计为准，
  并把裁决记录追加到 `doc/decisions.md`（自行创建，格式：`日期 | 问题 | 裁决 | 理由`）。
- **禁止事项**：
  - 禁止修改 doc/ 下的需求与设计正文（只允许：勾选 tasks checkbox、更新
    progress.md、追加 decisions.md、最终生成 acceptance-report.md）；
  - 禁止为通过检查而降低门禁（禁无注释的 `# type: ignore` / `# noqa`，
    确需豁免必须写明原因）；
  - 禁止删除/弱化已有测试；禁止跳过失败测试（skip/xfail 需记录 decisions.md）。

## 2. 环境初始化（第一步，先于一切编码）

```bash
cd D:\Desktop\Cutting
uv add pyside6 ortools openpyxl reportlab
uv add --dev pytest pytest-qt mypy ruff
```

在 `pyproject.toml` 追加配置：

```toml
[tool.ruff]
line-length = 100
[tool.ruff.lint]
select = ["E", "F", "I", "UP"]

[tool.mypy]
python_version = "3.11"
mypy_path = "src"
[[tool.mypy.overrides]]          # core/app/io 严格模式
module = ["core.*", "app.*", "io.*"]
strict = true
[[tool.mypy.overrides]]          # ui 层宽松：PySide6 缺 stub
module = ["ui.*", "pyside6.*"]
ignore_missing_imports = true
disallow_untyped_defs = false

[tool.pytest.ini_options]
testpaths = ["tests"]
```

验证：`uv run pytest`、`uv run mypy .`、`uv run ruff check .` 均可运行。
源码布局按详细设计 §5：`core/ app/ ui/ io/ i18n/ tests/ assets/` 直接放工程根目录。

## 3. 质量门禁（每个模块的 Definition of Done）

一个模块只有同时满足以下条件才算完成：

1. **pytest 全绿**：该模块测试文件全部通过；全量 `pytest` 不破坏任何已有测试；
   core 层（models/validator/statistics/两个 solver）行覆盖率 ≥ 90%。
2. **mypy 零错误**：core/app/io 层 strict；ui 层按上述宽松配置。
3. **ruff check 零错误**。
4. **任务文件验收标准逐条达成**，并把该模块 `doc/tasks/<module>.md`
   的全部 `- [ ]` 勾为 `- [x]`。
5. **接口冻结**：`core/models.py` 完成后其字段定义冻结；确需变更时，
   先记录 decisions.md，再同步修订所有受影响模块与其测试。

## 4. 主 Agent 编排循环

重复以下循环直到 progress.md 全部勾选：

1. **选任务**：读 `doc/tasks/progress.md`，按 §6 顺序取第一个未勾选模块。
2. **派发子 Agent**：按 §5 模板组装上下文，生成一个子 Agent 实现该模块。
3. **亲自验证**（不信任子 Agent 的自述）：依次运行
   `uv run pytest -q`、`uv run mypy .`、`uv run ruff check .`，
   并逐条核对任务文件的"验收"清单。
4. **登记**：全部通过 → 勾选该模块任务文件全部子任务 + progress.md 对应行；
   任何一项失败 → 进入 §9 失败处理。
5. **里程碑检查**：每个里程碑最后一个模块完成时，执行 §8 对应出口标准，
   通过后在 progress.md 勾选出口标准，再进入下一里程碑。

主 Agent 自己不写业务代码，只负责：派发、验证、登记、裁决、初始化环境与最终验收。

## 5. 子 Agent Prompt 模板（每次派发按此组装）

```
你是实现子 Agent，负责模块【<模块名>】。工程：D:\Desktop\Cutting（uv 工程，仅限此目录）。

【必读文档】
- doc/detailed-design.md 第 <对应章节> 节 —— 本模块的接口与行为定义（唯一准绳）
- doc/tasks/<module>.md —— 子任务清单与验收标准
- core/models.py 源码 —— 全系统数据模型（已冻结，禁改）
<已实现依赖模块的公开接口摘要 / 源码路径>

【任务】按任务文件 T1..Tn 依次实现，包括 pytest 单元测试。
【约束】
- 只创建/修改本模块文件与对应 tests/test_<module>.py，禁动其他模块；
- 层间依赖方向 ui→app→core/io，core 禁止 import PySide6；
- 所有用户可见文字必须走 i18n tr()（M2 起）；
- 完成标准 = 主 Agent 复核 pytest / mypy / ruff 全绿，不是你自己声明完成。

【返回格式】
1. 新建/修改文件清单 2. pytest 输出摘要 3. 遗留问题（无则写"无"）
```

## 6. 执行顺序（拓扑序，严格按序执行）

```
M1:  models → statistics → validator → heuristic_solver → exact_solver
M2:  translator → settings(T1内存版即可) → worker
     → controller(注入假 io) → input_panel → result_panel → cutting_view
     → dialogs → main_window
M3:  excel_importer → excel_exporter
M4:  pdf_reporter → main(入口+打包)
```

说明：controller 开发时 io 层尚未存在，必须注入假实现（任务文件已注明）；
pdf_reporter 依赖 cutting_view.render_to_painter（接口见详细设计 §5.4）。

## 7. 接口冻结点（子 Agent 派发时随上下文给出）

1. `core/models.py`：第一个实现，完成后字段定义冻结（变更走 decisions.md 流程）。
2. 求解器接口（详细设计 §3.2）：`SolverBase.solve(parts, stock, on_progress=None, cancel=None) -> Solution`，两个求解器必须同签名。
3. i18n 词条 key（详细设计 §7.2）：`err.E001–E008` 在 translator 模块中先行定义，后续模块只增不改。
4. `render_to_painter(painter, solution, stock, width_px)`（详细设计 §5.4）：屏幕图与 PDF 共用的唯一渲染入口。

## 8. 里程碑出口标准与最终验收（自动化，无人工）

- **M1 出口**：基准用例（6000/锯缝3：2000×5、1500×4、800×10）≤6 根、利用率 ≥95%；
  100 组随机性质测试 `check_solution` 全过；随机千级零件 < 10s。
- **M2 出口**：pytest-qt 自动化全流程——脚本录入零件→触发计算→断言 Solution 合法
  且界面统计区数值一致→切换语言断言界面文字变化；worker 运行中 cancel 正常结束。
- **M3 出口**：模板导入（含坏行提示）与三 Sheet 导出回归测试全绿。
- **M4 出口（最终验收，自动化冒烟代替人工）**：
  1. PyInstaller 打包出 exe（onefile、无控制台、内嵌字体与词条）；
  2. 编写并运行 `tools/smoke_test.py`：启动 exe → 自动导入示例 Excel →
     触发计算 → 导出 Excel 与 PDF → 校验导出文件数值与算法结果一致 →
     界面截图留存；
  3. 生成 `doc/acceptance-report.md`：全量测试结果、core 层覆盖率、
     mypy/ruff 结果、冒烟结果与截图路径、需求 F1.1–F4.4 逐项核对结论。
  4. 以上全部通过 → progress.md 需求覆盖核对全部勾选 → 交付。

## 9. 失败处理

- 子 Agent 交付验证失败：主 Agent 读 pytest/mypy/ruff 输出定位原因，
  修正上下文后**重派同一模块**（最多 3 次）；
- 第 3 次仍失败：将该模块拆成更小的任务（追加到对应任务文件），逐个派发；
- 发现设计缺陷或文档矛盾：记录 decisions.md，按 §1 优先级裁决后继续；
- 已有测试被破坏：立即回滚相关改动，禁止通过改测试"对齐"错误实现。

## 10. 进度可视化

- `doc/tasks/progress.md` 是唯一进度源，每完成一个模块立即更新；
- 主 Agent 每次循环开始前先读它，确保断点续跑（中断后重投本 Prompt 可继续）；
- 全程的关键裁决沉淀在 `doc/decisions.md`，最终成果沉淀在
  `doc/acceptance-report.md`。

---

**现在开始**：先执行 §2 环境初始化，然后从 M1 第一个模块 `models` 开始编排循环。
