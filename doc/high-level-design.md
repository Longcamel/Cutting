# 一维下料优化软件 —— 概要设计文档

| 项目 | 内容 |
|---|---|
| 文档版本 | v1.0 |
| 创建日期 | 2026-09-19 |
| 依据文档 | doc/proposal.md v1.0（+ 双语需求补充） |
| 状态 | 已确认，待详细设计/编码 |

---

## 1. 设计目标与原则

1. **三层分离**：算法 / GUI / 导入导出互不渗透，对应需求文档"可维护性"要求。
2. **单向依赖**：上层可依赖下层，下层不知道上层存在 → 算法可脱离界面单独测试（支撑 M1 里程碑"命令行验证"）。
3. **界面不冻结**：优化计算在后台线程执行，界面随时可响应、可取消。
4. **集中式多语言**：所有界面与报表文字走统一翻译模块，运行时切换中英文。

### 本期确认的范围裁剪（与需求文档的差异说明）

| 事项 | 结论 | 对设计的影响 |
|---|---|---|
| 工程文件保存/打开 | **不做**，用 Excel 导入代替 | 无工程文件模块，数据只存在于界面表格和 Excel 之间 |
| 计算历史记录 | **不做**，用户自管导出文件 | 无数据库模块，软件零持久化负担（仅参数记忆） |
| 界面语言 | **中文 + English，可切换** | 新增 i18n 多语言模块（见 §3.5） |

---

## 2. 总体架构

```
┌─────────────────────────── 表现层 (ui) ───────────────────────────┐
│  MainWindow                                                       │
│   ├── InputPanel      参数设置 + 零件清单表格（手工录入）          │
│   ├── ResultPanel     利用率统计 + 方案汇总表 + 零件核对表         │
│   ├── CuttingView     切割示意图自绘控件（按比例条形图）           │
│   └── Dialogs         中文/英文错误提示弹窗                        │
└──────┬───────────────────────▲────────────────────────────────────┘
       │ 调用/传数据             │ 信号(进度/完成/取消)
       ▼                        │
┌─────────────────────────── 调度层 (app) ──────────────────────────┐
│  AppController    编排：校验→求解→自检→展示→导出                  │
│  SolverWorker     后台线程包装，转发进度信号，支持取消            │
└──────┬───────────────────────────────────────────┬───────────────┘
       │                                            │
       ▼                                            ▼
┌────────────── 核心层 (core) ──────────────┐  ┌──────── 导入导出层 (io) ────────┐
│ models        数据模型（纯数据，无逻辑）   │  │ excel_importer  Excel导入+模板   │
│ validator     输入校验 + 结果合法性自检    │  │ excel_exporter  方案导出.xlsx    │
│ solver (接口)  求解器抽象基类              │  │ pdf_reporter    PDF报告生成      │
│  ├─ HeuristicSolver  快速模式(默认)        │  │ settings        参数记忆(JSON)   │
│  └─ ExactSolver      精确模式(OR-Tools)    │  └───────────────┬────────────────┘
│ statistics    利用率/废料统计计算          │                  │
└───────────────────────────────────────────┘                  │
       ▲                                                       │
       │              ┌──────────── 支撑层 ────────────┐       │
       └──────────────┤ i18n  多语言翻译(zh_CN/en_US)  ├───────┘
                      └────────────────────────────────┘
        io 层与 core 层只通过 models 交换数据，互不直接依赖
```

**依赖规则**（强制）：
- `ui` → `app` → `core` / `io` / `i18n`
- `core` 不依赖 `ui`、`io`（只用标准库 + OR-Tools）
- `io` 不依赖 `ui`；读写报表文字经 `i18n` 取词
- 任何两层之间只通过 `core.models` 中的数据对象传数据

---

## 3. 模块设计

### 3.1 表现层 `ui/`

| 模块 | 职责 | 对应需求 |
|---|---|---|
| `main_window.py` | 主窗口布局、菜单（语言切换/导出/帮助）、协调各面板 | F4 |
| `input_panel.py` | 原料长度/锯缝/材料名输入框；零件清单表格（增删改行）；求解模式选择（快速/精确）；"开始计算"按钮 | F1.1, F1.3 |
| `result_panel.py` | 统计区（原料根数、利用率%、废料等）；方案汇总表；零件需求 vs 实切核对表 | F2.2, F3.2 |
| `cutting_view.py` | 自绘控件：每行一种切法，按比例色块=零件段（标注长度）+ 灰色余料段，右侧"×N 根" | F3.1 |
| `dialogs.py` | 统一错误/警告弹窗（超长零件、导入错误行等） | F1.4, F4.3 |

### 3.2 调度层 `app/`

| 模块 | 职责 |
|---|---|
| `controller.py` | 串联主流程：收集输入 → validator 校验 → 选求解器 → 后台求解 → 结果自检 → 刷新界面；处理导出请求 |
| `worker.py` | QThread 包装求解过程：进度信号、完成信号、取消标志（精确模式耗时长必须可取消） |

**主流程时序**：

```
用户点击[开始计算]
  → InputPanel 读取零件清单+参数
  → Validator 校验输入(失败→Dialogs 提示，终止)
  → Controller 按模式选 HeuristicSolver / ExactSolver
  → SolverWorker 后台线程执行（界面显示进度/取消按钮）
  → Validator 自检结果合法性(F2.4：总长不超原料、数量不少切)
  → Statistics 计算利用率
  → ResultPanel + CuttingView 刷新展示
```

### 3.3 核心层 `core/`

| 模块 | 职责 | 关键接口（示意） |
|---|---|---|
| `models.py` | 纯数据对象 | `Part(length:int, qty:int)`；`StockSpec(length:int, kerf:int, material:str)`；`CuttingPattern(counts:dict, remainder:int, bars:int)`；`Solution(patterns:list, stats:Statistics)` |
| `validator.py` | 输入校验（正值、零件+锯缝≤原料）；结果合法性自检 | `validate_input(parts, stock) -> list[str]`、`check_solution(sol, parts, stock) -> bool` |
| `solver_base.py` | 求解器抽象接口 + 进度/取消回调协议 | `solve(parts, stock, on_progress, cancel_flag) -> Solution` |
| `heuristic_solver.py` | 快速模式：改进 FFD（按长度降序最佳适配）+ 模式合并局部搜索；千级零件 <10s | 实现 `solve()` |
| `exact_solver.py` | 精确模式：OR-Tools CP-SAT 列生成/装箱模型；超时返回当前最优 | 实现 `solve()`，支持 `cancel_flag` |
| `statistics.py` | 利用率、废料总长、根数等统计 | `compute(solution, stock) -> Statistics` |

**双模式策略**：两求解器实现同一接口，Controller 按用户选择注入，互相可替换；
结果都必须过 `check_solution` 自检后才允许展示（F2.4 兜底）。

### 3.4 导入导出层 `io/`

| 模块 | 职责 | 对应需求 |
|---|---|---|
| `excel_importer.py` | 读 .xlsx（列：长度/数量）→ `list[Part]`；逐行校验，报告错误行号；生成空白模板 | F1.2 |
| `excel_exporter.py` | `Solution` → .xlsx：方案汇总表 + 零件核对表 | F3.3 |
| `pdf_reporter.py` | `Solution` + 示意图渲染 → PDF 报告（参数、利用率、图形、明细）；内置中文字体 | F3.4 |
| `settings.py` | 参数记忆：原料长度/锯缝/材料名/语言 → JSON 存用户目录，启动时恢复 | F4.2 |

### 3.5 支撑层 `i18n/`

| 模块 | 职责 |
|---|---|
| `translator.py` | 全局取词函数 `tr(key)`；运行时切换语言并通知界面刷新 |
| `zh_CN.json` / `en_US.json` | 全部界面文字、按钮、报错、报表词条，以 key-value 集中管理 |

**规则**：代码中禁止硬编码显示文字，一律 `tr("msg.overlong_part")` 取词；
PDF/Excel 报表文字跟随当前界面语言。

---

## 4. 模块关系与数据流

### 4.1 数据流（一次完整计算）

```
Excel文件 ──excel_importer──► list[Part] ──► InputPanel表格
手工录入 ────────────────────► InputPanel表格
                                      │
InputPanel: list[Part] + StockSpec    ▼
        ──► validator.validate_input ──► [错误] ──► Dialogs
                                      │ 通过
                          controller ─▼─► HeuristicSolver / ExactSolver
                                      │    (worker 线程, 进度/取消)
                                      ▼
                    Solution ──► validator.check_solution (F2.4 自检)
                                      │
              ┌───────────────────────┼───────────────────┐
              ▼                       ▼                   ▼
        CuttingView 示意图      ResultPanel 表格      导出请求
                                                      ├─ excel_exporter → .xlsx
                                                      └─ pdf_reporter   → .pdf
settings: 每次参数变更自动保存 ──► 下次启动恢复
```

### 4.2 关键交互关系

| 关系 | 说明 |
|---|---|
| ui ↔ worker | 仅信号通信（progress/finished/cancel），不共享可变数据，避免线程问题 |
| controller → solver | 依赖注入：按模式传入不同求解器实例，controller 不感知算法细节 |
| io → core | 只读 models 数据对象做序列化，不调用求解逻辑 |
| 全局 → i18n | ui 与 io 的每个显示字符串都经 `tr()`，切换语言=重载词条+界面重绘 |

---

## 5. 目录结构

```
D:\Desktop\Cutting\
├── pyproject.toml
├── main.py                     # 入口：创建 QApplication、加载设置与语言、显示 MainWindow
├── src/
│   ├── app/
│   │   ├── controller.py
│   │   └── worker.py
│   ├── core/
│   │   ├── models.py
│   │   ├── validator.py
│   │   ├── solver_base.py
│   │   ├── heuristic_solver.py
│   │   ├── exact_solver.py
│   │   └── statistics.py
│   ├── ui/
│   │   ├── main_window.py
│   │   ├── input_panel.py
│   │   ├── result_panel.py
│   │   ├── cutting_view.py
│   │   └── dialogs.py
│   ├── io/
│   │   ├── excel_importer.py
│   │   ├── excel_exporter.py
│   │   ├── pdf_reporter.py
│   │   └── settings.py
│   └── i18n/
│       ├── translator.py
│       ├── zh_CN.json
│       └── en_US.json
├── assets/
│   ├── fonts/                  # 内嵌中文字体（PDF用）
│   └── template.xlsx           # Excel导入模板
├── tests/
│   ├── test_heuristic.py       # 算法正确性/合法性/性能(千级<10s)
│   ├── test_validator.py
│   └── test_io.py
└── doc/
    ├── proposal.md
    └── high-level-design.md
```

---

## 6. 关键技术决策

| 决策点 | 方案 | 理由 |
|---|---|---|
| 线程模型 | 求解在 QThread worker，GUI 主线程只收信号 | 精确模式耗时长，界面必须可取消不冻结 |
| 求解器可替换 | 统一 `solve()` 接口 + 依赖注入 | 快速/精确双模式（F2.3），未来可加新算法 |
| 结果可信 | 求解后强制 `check_solution` 自检，失败则报错不展示 | F2.4 可靠性兜底，防算法 bug 导致车间错切 |
| 多语言 | 词条外置 JSON + `tr()` 取词 + 运行时切换 | 中英文需求；新增语言只需加一个词条文件 |
| 持久化 | 仅 settings JSON（参数+语言），无数据库 | 已确认不做工程文件与历史记录 |
| PDF 中文 | reportlab + 打包内嵌字体 | 规避用户机器缺字体风险 |
| 测试策略 | 算法层纯 Python 可无界面单测（pytest），支撑 M1 命令行验证 | 核心层零 GUI 依赖 |

---

## 7. 需求追踪表

| 需求编号 | 实现模块 |
|---|---|
| F1.1 手工录入 | ui/input_panel |
| F1.2 Excel导入 | io/excel_importer → ui/input_panel |
| F1.3 参数设置 | ui/input_panel + io/settings |
| F1.4 数据校验 | core/validator + ui/dialogs |
| F2.1 一键优化 | app/controller + core/*solver |
| F2.2 利用率统计 | core/statistics → ui/result_panel |
| F2.3 双模式 | core/solver_base + heuristic/exact + app/worker(取消) |
| F2.4 合法性保证 | core/validator.check_solution |
| F3.1 切割示意图 | ui/cutting_view |
| F3.2 方案表格 | ui/result_panel |
| F3.3 导出Excel | io/excel_exporter |
| F3.4 导出/打印PDF | io/pdf_reporter |
| F4.1 打包exe | PyInstaller（构建脚本，M4） |
| F4.2 参数记忆 | io/settings |
| F4.3 中文错误提示 | ui/dialogs + i18n |
| F4.4 中英文切换(新增) | i18n 模块 + ui/main_window 语言菜单 |

---

## 8. 风险与对策（设计层面）

| 风险 | 对策 |
|---|---|
| 精确模式极端规模超时 | worker 支持取消 + 超时返回当前最优解并标注"非最优" |
| 界面自绘示意图在大方案数时卡顿 | CuttingView 按需绘制可见区域（QGraphicsView 视口机制） |
| 双语切换后界面布局溢出 | 界面统一用布局管理器，禁固定像素；词条长度自测 |
| 层间依赖腐化 | 目录即边界 + code review 检查 import 方向；core 禁 import PySide6 |
