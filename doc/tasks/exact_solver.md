# 模块：core/exact_solver.py —— 精确模式求解器（OR-Tools CP-SAT）

- 详细设计：§3.4 | 里程碑：M1 | 依赖：models、validator、statistics | 测试：tests/test_exact.py

## 子任务
- [x] T1 实现模式枚举：DFS 生成所有可行切割组合（含 kerf，零件种数 ≤25 时可行）
- [x] T2 CP-SAT 建模：变量 y_p=各模式使用根数；约束 Σ a_ip·y_p == 需求；目标 min Σ y_p；max_time=30s
- [x] T3 实现 solve()：种数>25 抛 E008；超时/cancel 返回当前最优可行解并置 exact 标志
- [x] T4 测试：小规模与手工枚举最优对比一致；>25 种触发 E008
- [x] T5 `pytest tests/test_exact.py` 通过

## 验收
- [x] 小规模达到数学最优；超时仍可返回合法解；pytest 绿
