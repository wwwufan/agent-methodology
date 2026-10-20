## implementation_summary

number-tools / Phase 2 / F-002，main，retry 0/2：已按 READY 设计实现批量裁剪。先检查逆界，再逐项复用 `clamp`，返回新列表，保留顺序、重复项和原数值，不修改输入。Phase 1 实现未变。

已核对项目约束、完整设计、角色契约及实际 executor 配置；未修改进度或关闭阶段。

## changed_surface

仅修改项目中的：

- `utils.py`：实现 `clamp_many`。
- `test_phase2.py`：补充新列表、非空逆界、等界、端点和区间内原值保留测试。

## validation

实际执行：

```bash
python3 -B -m unittest test_phase1 test_phase2 -v
```

关键输出：`Ran 11 tests in 0.001s`，`OK`，退出码 0。覆盖当前项目两阶段测试，包括空输入逆界及 Phase 1 回归。

## remaining_risks

- 尚未独立 Reviewer 复核；本报告仅证明实施与本次测试结果，不代替评审结论。
- 建议主代理依现有授权调度 Reviewer；无新增权限需求。
