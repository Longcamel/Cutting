# 模块：core/heuristic_solver.py —— 快速模式求解器

- 详细设计：§3.3 | 里程碑：M1 | 依赖：models、validator、statistics | 测试：tests/test_heuristic.py

## 子任务
- [x] T1 实现 `expand(parts)` 展开零件实例，及单棒填充：BFD 初始 + 背包 DP 填满余料（含 kerf）
- [x] T2 实现 `solve(parts, stock, on_progress, cancel)`：5s 预算内多策略重跑取优、相同切法合并为 CuttingPattern、进度回调、cancel 检查
- [x] T3 基准用例测试：6000/锯缝3，[立柱2000×5, 横梁1500×4, 短撑800×10] → ≤6 根、check_solution 过、利用率 ≥75%（原95%数学不可达，见 decisions.md D2）
- [x] T4 随机性质测试：100 组随机输入，全部 `check_solution` 通过
- [x] T5 性能测试：随机 1000 根 < 10s；cancel 置位后 1s 内返回
- [x] T6 `pytest tests/test_heuristic.py` 全部通过

## 验收
- [x] 满足 M1 验收基准；返回 Solution.exact=False；pytest 绿
