## implementation_summary

number-tools / Phase 1 / F-001，retry 0/2：已按 READY 设计实现 `clamp`，先检查逆序边界，再裁剪，否则返回原值。实际分支为 `main`。

## changed_surface

仅修改：

- `utils.py`：实现 `clamp`，未修改 `clamp_many`。
- `test_phase1.py`：补充端点与区间内原值身份、相等边界、不同值位置下逆序边界测试。

未改变接口、添加类型转换、写入进度或栈、创建 Goal、提交、联网或委托其他代理。

## validation

实际执行：

```bash
python3 -B -m unittest test_phase1 -v
```

结果：5 项测试全部成功，`Ran 5 tests in 0.000s`，`OK`，退出码 0。

证据仅覆盖 Phase 1；未读取或执行 Phase 2 测试。

## remaining_risks

无已知阶段内阻塞。NaN、非数值输入等未要求语义未扩展。仓库现有文件均未跟踪，未创建提交。

建议主代理依已有授权交 Reviewer 独立核验；本报告不宣告阶段 PASS，不关闭帧。
