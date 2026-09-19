# 一维下料优化软件 —— 详细设计文档

| 项目 | 内容 |
|---|---|
| 文档版本 | v1.0 |
| 创建日期 | 2026-09-19 |
| 依据文档 | doc/proposal.md v1.0、doc/high-level-design.md v1.0 |
| 读者 | 开发者 |
| 状态 | 已确认，可编码 |

> 本期新增确认（相对概要设计）：Excel 导入模板为**三列**（名称[可空]、长度、数量）；
> PDF 报告支持**公司名 + 项目名**两个可选抬头字段。已反映在下文与需求追踪表中。

## 1. 设计约定

- 语言 Python 3.11+；长度单位统一 **毫米(int)**，数量 int；禁止浮点参与长度计算。
- 所有显示文字一律 `tr(key)` 取词，禁止硬编码中英文。
- 层间只传 `core.models` 数据对象；core 层不得 import PySide6 / openpyxl / reportlab。
- 每个模块提供独立的 `if __name__ == "__main__":` 演示或对应 pytest 用例，可单独测试。
- 命名：模块小写下划线；类大驼峰；i18n key 用点分层（如 `err.part_too_long`）。

---

## 2. core/models.py —— 数据模型（全系统唯一数据结构定义）

```python
from dataclasses import dataclass, field

@dataclass(frozen=True)
class Part:
    """一种零件需求"""
    length: int   # mm，>=1
    qty: int      # >=1
    name: str = ""  # 可空，Excel"名称"列，仅展示用

@dataclass(frozen=True)
class StockSpec:
    """原料与全局参数"""
    length: int          # mm，>=1
    kerf: int            # mm，>=0，锯缝损耗
    material: str = ""   # 材料名，报表标注
    company: str = ""    # 可空，PDF抬头
    project: str = ""    # 可空，PDF抬头

@dataclass
class CuttingPattern:
    """一种切法：一根原料上的切割组合 + 该切法使用根数"""
    counts: dict[int, int]  # {零件在parts列表中的下标: 每件根数}
    bars: int = 1           # 此切法消耗的原料根数
    remainder: int = 0      # 每根余料 mm（由求解器填入）

@dataclass
class Statistics:
    bars_used: int        # 原料总根数
    total_stock_len: int  # 原料总长 = bars_used * stock.length
    total_part_len: int   # 零件总长（不含锯缝）
    kerf_loss: int        # 锯缝损耗总长
    waste_len: int        # 余料总长 = total_stock_len - total_part_len - kerf_loss
    utilization: float    # 利用率% = total_part_len / total_stock_len * 100

@dataclass
class Solution:
    patterns: list[CuttingPattern]
    stats: Statistics | None = None
    exact: bool = False       # 是否数学最优（精确模式且未超时）
    elapsed_s: float = 0.0
```

**不变式**（求解器与自检共同维护）：
- 每个 pattern 消耗长度 = `Σ(length_i × n_i) + kerf × 切口数 ≤ stock.length`
- 切口数约定：余料 > 0 时 = 段数；余料 = 0 时 = 段数 − 1
- `Σ(各pattern中零件i总数 × bars) ≥ 需求qty`（允许>0多切，统计与核对表中标示）

---

## 3. core 层详细设计

### 3.1 core/validator.py —— 校验（纯函数，无状态）

```python
@dataclass
class Issue:
    code: str        # 见 §9 错误码表，如 "E003"
    row: int = -1    # 出错的零件下标/Excel行号，-1=全局
    detail: str = "" # 供日志，不直接显示

def validate_input(parts: list[Part], stock: StockSpec) -> list[Issue]:
    """计算前校验。返回空列表=通过。规则：
    R1 parts 非空 -> E001
    R2 每个 part.length>=1 且 part.qty>=1 -> E002（row=下标）
    R3 stock.length>=1 且 stock.kerf>=0 -> E002
    R4 每个零件可切出：part.length<=stock.length 且
       (part.length+kerf<=stock.length 或 part.length==stock.length) -> E003
    R5 part.name 长度<=50 -> E002"""

def check_solution(sol: Solution, parts: list[Part], stock: StockSpec) -> list[Issue]:
    """结果合法性自检（F2.4）。任一不满足返回非空：
    C1 每pattern消耗长度+锯缝 <= stock.length（按§2切口数约定）-> E005
    C2 每种零件实切总数 >= 需求 -> E005
    C3 每pattern counts 非空、bars>=1、下标合法 -> E005"""
```

### 3.2 core/solver_base.py —— 求解器接口

```python
import threading
from abc import ABC, abstractmethod
from typing import Callable

ProgressCB = Callable[[int], None]   # 0~100 百分比

class SolverBase(ABC):
    @abstractmethod
    def solve(self, parts: list[Part], stock: StockSpec,
              on_progress: ProgressCB | None = None,
              cancel: threading.Event | None = None) -> Solution:
        """cancel.is_set() 时应尽快返回当前最好解（或空Solution）。
        实现方须在主要循环定期检查 cancel 并回报进度。"""
```

### 3.3 core/heuristic_solver.py —— 快速模式（默认）

**算法：聚合 BFD + 背包填充 + 模式合并（时间预算内迭代）**

```
输入 parts(≤数千种/根), stock；输出 Solution（exact=False）
1. 预处理：按 length 降序排序；相同长度合并数量
2. 初始解（Best-Fit Decreasing）：
   对每种零件的每一根：放入"剩余容量能装下它的余料最小"的已开原料，
   无则开新原料。容量判断含锯缝：need = length + kerf（最后一段豁免见§2）
3. 背包填充：对每根余料>0的原料，用剩余零件在其余料空间内做
   01背包DP（容量=余料+kerf），把能塞的零件塞进去
4. 模式合并改进（循环直到时间预算 time_budget_s=5s 或 cancel）：
   a. 把所有原料按切法聚合为 patterns
   b. 取余料最大的两个 pattern，尝试将其原料合并重新切割
      （对两根原料的并集做有限枚举/背包），若总根数下降则接受
   c. 每轮 on_progress(已迭代比例)
5. 汇总 statistics，返回 Solution
```

- 复杂度：初始解 O(N log N)；合并轮次受预算控制。**性能目标：1000 根零件 <10s**（F2.3/性能需求）。
- 关键参数（模块级常量，可调）：`TIME_BUDGET_S = 5`

### 3.4 core/exact_solver.py —— 精确模式（OR-Tools CP-SAT）

```
适用限制：零件种数 n <= MAX_KINDS(默认25)；超出抛 E008，由UI提示改用快速模式
1. 模式枚举：递归生成所有可行切割组合 a=(x1..xn)，满足
   Σ li·xi + kerf·cuts(a) <= L 且 Σ xi >= 1（xi 上界 = min(d_i, L//li)）
2. CP-SAT 建模（整数规划）：
   变量 y_p >= 0 整数（每种模式用几根）
   min  Σ y_p
   s.t. Σ_p a_ip · y_p >= d_i   ∀i
3. 求解参数：max_time_in_seconds = 30；cancel 时 NumConflicts 中断，
   取当前最优可行解，exact=False
4. 把 y_p>0 的模式转成 CuttingPattern 列表，统计后返回
```

### 3.5 core/statistics.py —— 统计（纯函数）

```python
def compute(sol: Solution, parts: list[Part], stock: StockSpec) -> Statistics:
    """遍历patterns：bars_used=Σbars；
    total_part_len=Σ每段长度×根数×bars；
    kerf_loss=Σ切口数×kerf×bars（切口数按§2约定）；
    waste=stock总长−零件总长−kerf_loss；
    utilization=零件总长/原料总长×100（保留2位小数，由调用方格式化）"""
```

---

## 4. app 调度层详细设计

### 4.1 app/worker.py —— 后台求解线程

```python
class SolverWorker(QThread):
    progress = pyqtSignal(int)          # 0~100
    finished_ok = pyqtSignal(object)    # Solution
    failed = pyqtSignal(str)            # i18n错误key 或错误码

    def __init__(self, solver: SolverBase, parts, stock, parent=None):
        ...  # 仅保存输入副本，不持有UI对象
    def run(self):
        try:
            sol = self._solver.solve(self._parts, self._stock,
                                     on_progress=self.progress.emit,
                                     cancel=self._cancel)
            self.finished_ok.emit(sol)
        except Exception as e:
            self.failed.emit(str(e))
    def cancel(self): self._cancel.set()
```
- 与 GUI 只经信号通信；worker 不 import 任何 ui 模块 → 可用 dummy solver 独立测试。

### 4.2 app/controller.py —— 流程编排（无界面对象也可测）

```python
class AppController:
    """持有当前会话状态，方法即用户动作。依赖全部经构造注入。"""
    def __init__(self, settings: SettingsStore, make_solver: Callable[[str], SolverBase]):
        self.parts: list[Part] = []
        self.stock: StockSpec = StockSpec(6000, 3)
        self.solution: Solution | None = None
        self._worker: SolverWorker | None = None

    # ---- 输入 ----
    def import_excel(self, path: str) -> tuple[int, list[Issue]]:
        """调 excel_importer；成功则替换 self.parts。返回(导入条数, 问题列表)"""
    def set_parts(self, parts: list[Part]) -> None: ...
    def set_stock(self, stock: StockSpec) -> None:
        """更新参数并立即 settings.save()（F4.2）"""

    # ---- 计算（异步）----
    def start_solve(self, mode: str,  # "fast"|"exact"
                    on_progress, on_done, on_error) -> None:
        """1) validate_input，有问题→on_error(issues)并停止
           2) make_solver(mode)，构造 SolverWorker 接线三个回调
           3) on_done 内：check_solution 自检→失败报 E005；
              通过则 statistics.compute 填充 stats，赋给 self.solution"""
    def cancel_solve(self) -> None: ...

    # ---- 导出（同步，需已有 solution，否则返回 E006）----
    def export_excel(self, path: str) -> str | None: ...   # None=成功
    def export_pdf(self, path: str) -> str | None: ...
```

**主流程时序（与概要设计 §4.1 对应）**：UI 收集 → `set_parts/set_stock` →
`start_solve`（worker 后台）→ `on_done` 刷新 ResultPanel/CuttingView → 用户导出。

---

## 5. ui 表现层详细设计（PySide6）

> 所有 ui 类只做：展示、采集、调 controller。不含任何算法/文件格式逻辑。

### 5.1 ui/main_window.py
- 布局：左 `InputPanel`（固定宽 ~380px），右侧上下分：`ResultPanel`（上）+ `CuttingView`（下，可拉伸）。
- 菜单栏：
  - 文件 File：导入Excel… / 导出Excel… / 导出PDF… / 打印… / 退出
  - 语言 Language：中文 / English（单选，切换即 `translator.set_language()` + 全界面 retranslate + settings 记忆）
  - 帮助 Help：Excel模板下载 / 关于
- 状态栏：进度条（求解时显示）+ 取消按钮。

### 5.2 ui/input_panel.py
| 控件 | 类型 | 约束/默认 |
|---|---|---|
| 原料长度 | QSpinBox | 1–1 000 000 mm，默认 6000 |
| 锯缝损耗 | QSpinBox | 0–100 mm，默认 3 |
| 材料名称 | QLineEdit | ≤30 字，可空 |
| 公司名 | QLineEdit | ≤50 字，可空（PDF抬头） |
| 项目名/订单号 | QLineEdit | ≤50 字，可空（PDF抬头） |
| 零件表格 | QTableWidget | 3列：名称(可空)/长度mm(必填)/数量(必填)；行尾"＋"按钮加行、行右"✕"删行；支持Ctrl+V从Excel粘贴多行 |
| 求解模式 | QRadioButton ×2 | 快速(默认)/精确（选精确且种数>25时弹提示 E008） |
| 开始计算 | QPushButton | 点击→`collect()`→controller.start_solve；求解中变"取消" |

```python
def collect(self) -> tuple[list[Part], StockSpec]:
    """逐行读取表格；空名称允许；长度/数量列空或无法转int -> 构造 Issue(E002,row)。
    有任何 Issue 则返回空parts并高亮错误行（红底）。"""
```

### 5.3 ui/result_panel.py
- 统计区（一行大字号标签）：`原料根数 X | 利用率 95.3% | 零件总长 | 锯缝损耗 | 废料总长`；
  精确模式得到数学最优时追加"✔最优"，超时解标注"（当前最好，非最优）"。
- 方案汇总表（QTableWidget）：列 `切法# | 切割明细(名称+长度×n + …) | 余料mm | 使用根数`。
- 零件核对表：列 `名称 | 长度 | 需求 | 实切 | 差额`；差额≠0 的行橙色高亮。

### 5.4 ui/cutting_view.py —— 示意图自绘控件
- 基于 QGraphicsView/QGraphicsScene，利用视口机制只绘可见区（大方案不卡）。
- 每行一个切法：
  ```
  ┌─切法1──────────────────────────────────────────┐
  │ [名称A 2000][名称A 2000][名称B 1500][余料 497] │ ×12 根
  └─────────────────────────────────────────────────┘
  ```
- 比例：`px_per_mm = 可用宽度 / stock.length`；各段宽 = length×px_per_mm（最小 1px）。
- 配色：同一零件下标固定颜色（调色板 20 色循环 `PALETTE[idx % 20]`）；余料统一浅灰。
- 段内文字：`名称 + 长度`；放不下则只显示长度，再放不下省略（tooltip 显示完整）。
- 行高 28px，行间 6px；顶部绘制 mm 刻度尺（0 / L/2 / L）。
- 导出复用：`render_to_painter(painter, solution, width_px)` 供 pdf_reporter 调用，
  保证屏幕图与 PDF 图一致。

### 5.5 ui/dialogs.py
```python
def show_issues(parent, issues: list[Issue]) -> None:
    """按 tr('err.'+code) 取模板，含 row>=0 时格式化行号；多条合并为一个滚动弹窗"""
def show_info(parent, key: str, **kw) -> None
```

---

## 6. io 导入导出层详细设计

### 6.1 io/excel_importer.py —— Excel 导入 + 模板

**模板格式（assets/template.xlsx，表头即词条，随语言生成）**：

| 行 | A列 | B列 | C列 |
|---|---|---|---|
| 1 表头 | 名称（可空） | 长度(mm) | 数量 |
| 2+ 数据 | 文本 ≤50 字，可空 | 正整数 | 正整数 |

```python
def load_parts(path: str) -> tuple[list[Part], list[Issue]]:
    """openpyxl 只读模式逐行解析：
    - 跳过完全空行；B/C 列缺失或非正整数 -> Issue(E002, row=行号)
    - 名称缺列也兼容（两列模板）
    - 全部行都有错 -> Issue(E004)；有错行时仍返回成功解析的 parts，
      由UI决定"忽略错行继续"或"全部修正后重导"
def create_template(path: str, lang: str) -> None:  # 生成表头+1行示例"""
```
- 独立测试：临时 xlsx 构造正常/缺列/非数字/超长名称等用例。

### 6.2 io/excel_exporter.py —— 方案导出

```python
def save_report(path: str, sol: Solution, parts: list[Part],
                stock: StockSpec, lang: str) -> None
```
工作簿三 Sheet：
1. **参数统计**：公司/项目/材料/原料长度/锯缝/日期 + 原料根数/利用率/零件总长/锯缝损耗/废料总长
2. **切割方案**：`切法# | 明细(名称+长度×n) | 余料 | 根数`，列宽自适应
3. **零件核对**：`名称 | 长度 | 需求 | 实切 | 差额`

### 6.3 io/pdf_reporter.py —— PDF 报告

```python
def build_pdf(path: str, sol: Solution, parts: list[Part],
              stock: StockSpec, lang: str,
              render_bar: Callable[[Any, CuttingPattern, float], None]) -> None
    """render_bar 由 ui.cutting_view.render_to_painter 注入（依赖倒置，
    pdf_reporter 本身不 import PySide6，可传入空实现做纯文本测试）"""
```
- A4 纵向；reportlab platypus；`pdfmetrics.registerFont(TTFont(...))` 注册 assets/fonts 内嵌中文字体。
- 版面顺序：
  1. 抬头：公司名/项目名（非空才显示，居中大字）+ 材料/日期
  2. 参数与统计表（同 Excel Sheet1 内容）
  3. 切割示意图：每切法一条矢量横条（调 render_bar），图右侧"×N 根"；
     条宽超出页面按比例缩放
  4. 方案明细表 + 零件核对表
- 打印：main_window 调用 QPrinter 打印 PDF 临时文件（复用同一生成函数）。

### 6.4 io/settings.py —— 参数记忆

```python
class SettingsStore:
    """路径：%APPDATA%/CuttingApp/settings.json（打包后亦可写）"""
    def load(self) -> dict   # 缺文件/损坏 -> 返回默认值dict，不抛异常
    def save(self) -> None   # 写临时文件再 os.replace，防写坏
    # 字段与默认：
    # stock_length=6000, kerf=3, material="", company="", project="",
    # mode="fast", language="zh_CN"
```

---

## 7. i18n 多语言详细设计

### 7.1 i18n/translator.py
```python
_current = "zh_CN"
_dict: dict[str, str] = {}
_listeners: list[Callable[[], None]] = []

def init(lang: str) -> None            # 启动时调用，加载 i18n/{lang}.json
def tr(key: str, **kw) -> str          # 查词条并 format；key缺失 -> 返回 key 本身并记日志
def set_language(lang: str) -> None    # 重载词条 + 依次通知 listeners（各界面 retranslate）
def on_language_changed(cb) -> None    # 注册刷新回调
```

### 7.2 词条文件规范
- `zh_CN.json` / `en_US.json` **扁平 key**，点分层：
  - 界面：`app.title`、`menu.file`、`input.stock_length`、`btn.calculate`…
  - 错误：`err.E001`…`err.E008`（与 §9 错误码一一对应，文案含 `{row}` 占位）
  - 报表：`report.utilization`、`report.pattern_detail`…
- 规则：两文件 key 集合必须完全一致（有 pytest 保证）；新增文字必须先加双词条。

### 7.3 界面刷新
每个 ui 组件实现 `retranslate()`（重写所有 setText/setWindowTitle/表头），
构造时注册到 `on_language_changed`。切换语言不重启。

---

## 8. main.py —— 程序入口

```python
def main():
    app = QApplication(sys.argv)
    settings = SettingsStore(); cfg = settings.load()
    translator.init(cfg.get("language", "zh_CN"))
    controller = AppController(settings, make_solver)
    win = MainWindow(controller, settings)   # 恢复参数到界面
    win.show(); sys.exit(app.exec())

def make_solver(mode: str) -> SolverBase:
    return HeuristicSolver() if mode == "fast" else ExactSolver()
```

---

## 9. 错误码表（validator/各层统一使用，词条 key = `err.<code>`）

| 码 | 含义 | 触发处 |
|---|---|---|
| E001 | 零件清单为空 | validate_input R1 |
| E002 | 数值非法（非正整数/超长名称/参数越界） | validate_input R2/R3/R5、Excel导入、表格录入 |
| E003 | 零件长度超过原料，无法切出 | validate_input R4 |
| E004 | Excel 文件无法解析（损坏/无有效行） | excel_importer |
| E005 | 求解结果未通过合法性自检 | check_solution（兜底，正常不应出现） |
| E006 | 无计算结果，无法导出 | controller.export_* |
| E007 | 文件读写失败（占用/无权限） | io 各模块 |
| E008 | 零件种数超过精确模式上限(25)，请改用快速模式 | exact_solver / input_panel |

---

## 10. 独立测试方案（pytest，模块间零依赖可单独跑）

| 测试文件 | 被测模块 | 要点 |
|---|---|---|
| tests/test_models.py | models | 数据类默认值、不可变性 |
| tests/test_validator.py | validator | R1–R5/C1–C3 每条规则正反用例；构造非法解必须被 C1/C2 拦截 |
| tests/test_heuristic.py | heuristic_solver | ①手工可验小例（6000/锯缝3：2000×5+1500×4 → 期望4根）②随机性质测试：100组随机输入，`check_solution` 全过 ③性能：1000根<10s ④cancel 能在1s内返回 |
| tests/test_exact.py | exact_solver | 小规模与已知最优对比（如手工枚举结果）；>25种抛 E008；cancel 返回可行解 |
| tests/test_statistics.py | statistics | 手算用例核对利用率/锯缝损耗数值 |
| tests/test_excel.py | importer/exporter | 临时文件：三列/两列模板、坏行定位、E004；导出后重新打开校验三 Sheet 内容 |
| tests/test_settings.py | settings | 损坏 JSON 回退默认；保存后重读一致 |
| tests/test_i18n.py | translator | 两词条文件 key 集合相等；tr 缺失 key 降级；切换语言生效 |
| tests/test_controller.py | controller | 注入假 solver（立即返回固定 Solution），验证 校验→求解→自检→统计 编排与 E006 分支；不启动 QApplication（controller 不依赖界面） |
| tests/test_worker.py | worker | 需 QApplication：假 solver + cancel 信号链路 |
| tests/test_pdf.py | pdf_reporter | 注入空 render_bar，生成 PDF 不报错且文件非空 |

**验收基准用例**（M1 通过标准）：原料 6000、锯缝 3，
零件 `[("立柱",2000,5),("横梁",1500,4),("短撑",800,10)]`，
期望 ≤6 根原料、check_solution 通过、利用率 ≥ 95%。

---

## 11. 需求追踪表（详细设计 → 需求）

| 需求 | 落点（详细设计章节） |
|---|---|
| F1.1 手工录入 | §5.2 零件表格 + collect() |
| F1.2 Excel导入 | §6.1（三列模板、错行定位、模板下载） |
| F1.3 参数设置 | §5.2 参数控件（含公司/项目名） |
| F1.4 数据校验 | §3.1 validate_input + §5.5 弹窗 |
| F2.1 一键优化 | §4.2 start_solve + §3.3/§3.4 |
| F2.2 利用率统计 | §3.5 statistics + §5.3 统计区 |
| F2.3 双模式+可取消 | §3.2 接口/cancel、§4.1 worker、§3.4 超时 |
| F2.4 合法性保证 | §3.1 check_solution 强制自检 |
| F3.1 切割示意图 | §5.4（含 PDF 复用渲染） |
| F3.2 方案表格 | §5.3 汇总表+核对表 |
| F3.3 导出Excel | §6.2 |
| F3.4 导出/打印PDF | §6.3（公司/项目抬头） |
| F4.1 打包exe | M4：PyInstaller spec（assets/fonts、template.xlsx 一并打包） |
| F4.2 参数记忆 | §6.4 |
| F4.3 中文错误提示 | §7.2 词条 err.* + §5.5 |
| F4.4 中英文切换 | §7 全模块（运行时切换） |
| 新增：零件名称列 | §2 Part.name、§5.2、§6.1/6.2、§5.4 |
| 新增：PDF 公司/项目抬头 | §2 StockSpec.company/project、§5.2、§6.3 |

---

## 12. 依赖清单（pyproject.toml 追加）

```
pyside6          # GUI
ortools          # 精确模式 CP-SAT
openpyxl         # Excel 读写
reportlab        # PDF
# dev: pytest, pyinstaller
```

## 13. 实施顺序建议（对应里程碑）

1. **M1**：models → validator → statistics → heuristic_solver →（可后做 exact_solver）→ pytest 全绿
2. **M2**：i18n → worker → controller → ui 全部 → 界面联调
3. **M3**：excel_importer/exporter + 模板
4. **M4**：pdf_reporter + settings + PyInstaller 打包验证
