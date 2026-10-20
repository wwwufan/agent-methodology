## design_status

READY。返回 number-tools / Phase 1 / F-001；design_id：number-tools-phase-1；retry：0/2。已确认阶段级委托授权，实际分支为 main（尚无提交）。本报告仅为只读设计，不替代实施授权；未修改文件、运行测试或读取其他测试目录。

## problem_understanding

依据完整读取的 AGENTS.md、plan.md、utils.py、test_phase1.py、progress.md 和 `.codex/agents/designer.toml`：

当前 `clamp` 无条件抛出 `NotImplementedError`。Phase 1 要求实现单值裁剪：低于下界返回下界，高于上界返回上界，否则返回原值；相等边界合法，逆序边界抛出 `ValueError`。

仅使用标准库、函数式实现、保留接口，不增加类型转换，不实现 `clamp_many`，不联网、发布、创建 Goal 或提交 Git。

## entrypoints_and_flow

`test_phase1.py` 从 `utils` 导入 `clamp`，直接调用并验证结果或异常。

建议流程：先检查上下界是否合法，再比较值与下界、上界，最后返回区间内原值。没有文件、外部服务或其他状态流。

## impact_surface

必要代码变更仅限 `utils.py` 的 `clamp` 函数体。可在 `test_phase1.py` 补充本阶段边界测试；保留 `clamp_many` 原状，不调整接口或引入共享架构。

## root_cause_or_design_boundary

根因是功能尚未实现，而非已有裁剪算法的局部错误。应直接完成函数契约。

边界合法性检查必须先于裁剪，避免逆序边界因值的位置不同而错误返回结果。现有要求没有规定 NaN、非数值输入或额外类型校验，不扩展其语义。

progress.md 的 BLOCKED 是先前调度工具不可用的记录，不构成本设计的业务缺口；状态恢复由主代理处理。

## options

1. 显式条件分支：先验证边界，再分别处理低于下界、高于上界、区间内值。与计划逐项对应，易验证原值返回语义。
2. 验证边界后使用嵌套 `min`/`max`：更短，但相等值的对象选择和比较过程不如显式分支直观。

## recommended_design

采用显式条件分支。它满足当前轻量数值工具的全部硬约束，不引入依赖、转换或抽象，也便于检查“否则原值”和相等边界语义。

时间、额外空间复杂度均为常数；无需新增辅助函数。

## executor_instructions

- 保留 `clamp(value, lower, upper)` 签名。
- 首先检测 `lower > upper`，成立则抛 `ValueError`；异常文案未被契约限定。
- 值低于下界时返回调用者提供的下界，高于上界时返回上界，否则返回传入原值。
- 不修改 `clamp_many`，不增加类型转换或额外数据类型限制。
- 保留现有测试；可补充恰等下界、恰等上界，以及相等边界下值低于或等于边界的情况。
- 只在本项目执行，遵守标准库、无联网、无发布、无 Goal、无 commit 等约束。
- 将结果与验证证据返回主代理，不自行修改阶段状态或关闭帧。

## validation_strategy

必需验收命令：

```bash
python3 -B -m unittest test_phase1 -v
```

现有测试覆盖区间外两侧、区间内、逆序边界和相等边界。建议补充上述端点组合，确认严格比较及原值返回路径。执行后核对变更范围，确保没有 Phase 2 实现。

## reviewer_focus

- 是否先校验逆序边界，且抛出正确异常类型。
- 相等边界是否始终合法。
- 区间内及恰好落在端点的值是否走原值返回路径。
- 是否保持函数接口、数字原样处理和无副作用。
- `clamp_many` 是否完全未改。
- 必需验收是否实际通过，变更是否严格限于本阶段。

## open_questions

无影响当前决定的未决问题。下一步可由主代理基于已有 Phase 1 授权委托 Executor 实施，再委托 Reviewer 独立核验；本报告不代替这两个角色。
