# 模块：core/models.py —— 数据模型

- 详细设计：§2 | 里程碑：M1 | 依赖：无 | 测试：tests/test_models.py

## 子任务
- [x] T1 创建 `core/__init__.py` 和 `core/models.py`
- [x] T2 定义 frozen dataclass：`Part(length, qty, name="")`、`StockSpec(length, kerf, material="", company="", project="")`（以详细设计 §2 为准，无 idx；见 decisions.md D1）
- [x] T3 定义 `CuttingPattern(counts: dict[int,int], bars=1, remainder=0)`、`Statistics(bars_used, total_stock_len, total_part_len, kerf_loss, waste_len, utilization)`、`Solution(patterns, stats=None, exact=False, elapsed_s=0.0)`；切口数不变式：余料>0→段数，=0→段数−1
- [x] T4 编写 tests/test_models.py：默认值正确；frozen 实例修改字段抛异常
- [x] T5 `pytest tests/test_models.py` 通过

## 验收
- [x] `from core.models import *` 可用；字段与详细设计 §2 一致；pytest 绿（注：Issue 定义在 core/validator.py，见 §3.1）
