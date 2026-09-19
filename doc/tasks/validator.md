# 模块：core/validator.py —— 校验

- 详细设计：§3.1 | 里程碑：M1 | 依赖：models | 测试：tests/test_validator.py

## 子任务
- [ ] T1 实现 `validate_input(parts, stock) -> list[Issue]`：R1 清单空(E001)、R2 非正整数(E002)、R3 参数越界(E002)、R4 零件超长(E003,row=idx)、R5 名称>50字(E002,row=idx)
- [ ] T2 实现 `check_solution(sol, parts, stock) -> bool`：C1 各棒 Σ长度+切口×kerf ≤ stock.length；C2 各零件实切总数==需求（按 part_idx 核对）；C3 段数、余料非负
- [ ] T3 编写测试：R1–R5 每条正反用例；构造3种非法解必须被 C1/C2/C3 分别拦截
- [ ] T4 `pytest tests/test_validator.py` 通过

## 验收
- [ ] 错误码与详细设计 §9 一致；合法输入返回空列表；pytest 绿
