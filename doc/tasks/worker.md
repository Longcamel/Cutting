# 模块：app/worker.py —— 后台求解线程

- 详细设计：§4.1 | 里程碑：M2 | 依赖：core 全部 | 测试：tests/test_worker.py

## 子任务
- [x] T1 创建 `app/__init__.py` 和 `app/worker.py`：`SolverWorker(QThread)`，三个信号 `progress(int)`、`finished_ok(object)`、`failed(str)`
- [x] T2 实现 `run()`：调 solver.solve（传入 cancel 事件），异常→failed(str(e))
- [x] T3 实现 `cancel()`：置位取消事件
- [x] T4 测试（需 QApplication）：假 solver 立即返回固定 Solution → finished_ok 收到；运行中 cancel → 正常结束不抛异常
- [x] T5 `pytest tests/test_worker.py` 通过

## 验收
- [x] worker 不 import 任何 ui 模块；信号链路通畅；pytest 绿
