# 模块：io/settings.py —— 参数记忆

- 详细设计：§6.4 | 里程碑：M4（controller 开发时先用内存假实现） | 依赖：无 | 测试：tests/test_settings.py

## 子任务
- [x] T1 实现 `SettingsStore`：路径 `%APPDATA%/CuttingApp/settings.json`；字段 stock_length=6000, kerf=3, material="", company="", project="", mode="fast", language="zh_CN"
- [x] T2 `load()`：文件缺失/JSON 损坏 → 返回默认值 dict，不抛异常
- [x] T3 `save()`：写临时文件再 os.replace（原子写防写坏）
- [x] T4 测试：损坏 JSON 回退默认；保存后重读一致；临时目录隔离
- [x] T5 `pytest tests/test_settings.py` 通过

## 验收
- [x] 重启软件参数保留；配置文件损坏不影响启动；pytest 绿
