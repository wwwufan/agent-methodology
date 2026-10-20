## design_status

READY

## problem_understanding

返回 number-tools / Phase 2 / F-002；design_id 为 `number-tools-phase-2`，retry 为 0/2。`plan.md` 明确授权连续执行两阶段及三角色委托；`progress.md` 记录 Phase 1 done。实际分支为 main。

目标：实现批量裁剪，保留顺序和重复项，不修改输入；合法空输入返回空列表，逆序上下界即使输入为空也抛出 ValueError。结论适用于本项目当前源码和所读两个阶段测试，不代表实施或评审完成。

## entrypoints_and_flow

入口为 `utils.clamp_many(values, lower, upper)`，目前直接抛 NotImplementedError。现有 `clamp` 已实现逆界检查及单值裁剪，区间内与端点返回原值。建议数据流：先检查上下界，再按输入顺序逐项调用 `clamp`，收集为新列表。

## impact_surface

主要改动仅 `utils.py` 的 `clamp_many`；可在 `test_phase2.py` 补充本阶段边界测试。保留 `clamp` 与 Phase 1 测试行为，不涉及架构、配置、外部服务或其他目录。

## root_cause_or_design_boundary

当前缺口是批量入口尚未实现。单纯逐项调用 `clamp` 会遗漏空列表的逆界校验，因此必须在遍历前显式检查 `lower > upper`。

无需新增输入转换、数值类型策略或通用校验框架。

## options

- 推荐：前置逆界检查，然后以列表推导逐项调用 `clamp`。复用既有语义，代码简短；每个元素重复一次逆界检查，当前用途可接受。
- 备选：前置检查后内联裁剪逻辑。减少重复检查，但复制单值语义，增加后续行为分歧风险，无必要。

## recommended_design

采用推荐方案。逆界时抛 ValueError，错误信息可沿用现有 `clamp`；合法边界下生成新列表，无排序、去重或原地赋值。

此方案满足标准库、轻量函数与接口保留要求，并复用 Phase 1 的端点、等界及原值保留语义，无需扩大工程范围。

## executor_instructions

1. 仅实施本阶段批量函数，保留函数签名和 Phase 1 逻辑。
2. 必须先校验逆界，不能先因输入为空而返回。
3. 按原顺序逐项处理，保留重复项，返回新列表，不修改输入或转换数字。
4. 测试可补充非空逆界、相等上下界和端点原值保留，属于既定语义覆盖，不扩展产品功能。
5. 只在当前项目实施；不联网、发布、创建 Goal、提交或切换分支，不自行维护推进栈、阶段状态或重试计数。已有未追踪文件均予保留。
6. 由主代理依现有授权调度 Executor；READY 只表示设计就绪。

## validation_strategy

在项目目录运行：

```bash
python3 -B -m unittest test_phase1 test_phase2 -v
```

核对混合值顺序及重复项、输入不变、合法空列表、空与非空逆界、等界及 Phase 1 回归。当前 Designer 未运行验收，不提供实施通过结论。

## reviewer_focus

- 逆界校验是否位于遍历和空输入返回之前。
- 是否复用单值裁剪语义，保持端点与区间内原值。
- 是否返回新列表且不排序、去重或修改输入。
- 是否保留接口、范围与全局约束，并独立重跑完整验收。
- 不以未要求的通用类型支持或性能扩展缺失判 FAIL。

## open_questions

无影响当前设计的未决问题。下一步为主代理在既有 Phase 2 授权下调度 Executor，随后独立 Reviewer 复核；本角色未修改文件或关闭阶段帧。
