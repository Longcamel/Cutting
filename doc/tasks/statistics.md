# 模块：core/statistics.py —— 统计

- 详细设计：§3.5 | 里程碑：M1 | 依赖：models | 测试：tests/test_statistics.py

## 子任务
- [ ] T1 实现 `compute(sol, parts, stock) -> Statistics`：bars_used、total_part_len、kerf_loss（切口数按设计约定）、waste、utilization
- [ ] T2 编写测试：手算用例（6000/锯缝3：切2000+2000+1500 → 损耗9、余料497、利用率=5503/6000）
- [ ] T3 `pytest tests/test_statistics.py` 通过

## 验收
- [ ] 利用率=零件总长/原料总长；锯缝损耗单独列出；数值与手算一致
