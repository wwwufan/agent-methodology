# 总目标台账与模式切换模板

## 目录

- 台账模板
- 阶段快照模板
- Goal 绑定模板
- 模式切换提示

## 台账模板

```markdown
# <campaign_name> 总目标台账

## 总目标

- campaign_id：<stable-id>
- total_goal_version：1
- status：planning | route_approved | active | completed | paused
- goal_statement：<用户确认的总目标>
- success_criteria：<最终成功标准>
- global_constraints：<跨阶段约束>
- out_of_scope：<明确非范围>
- approved_route：<用户批准的路线摘要>
- approved_by_user_at：<时间或 ->

## 阶段

| phase_id | phase_version | execution_mode | title | prerequisite | snapshot | sha256 | status | goal_id | internal_review | user_approval |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| phase-1 | 1 | goal | <标题> | - | phases/phase-1-v1.md | <sha256> | draft | - | - | - |

## 决策记录

- <时间>：<用户原文或确认摘要>
```

阶段状态只允许：

```text
draft
planning
external_in_progress
external_ready_for_import
approved_for_goal
goal_active
binding_mismatch
plan_change_requested
internal_failed
awaiting_user_approval
changes_requested
approved
blocked
```

`execution_mode` 只允许：

```text
external
goal
review_only
```

外部执行尚未完成时使用 `execution_mode=external`、`status=external_in_progress`，并保持 `snapshot=-`、`sha256=-`、`goal_id=-`。默认在完成导入和审核方案确认后生成审核快照并切换为 `review_only`。如果用户基于已有交付证据明确选择直接人工批准，可以保持 `execution_mode=external`，记录精简证据摘要、批准原文和时间后直接进入 `approved`；不得因此自动启动下一阶段。

## 阶段快照模板

```markdown
# <phase_id> · <title>

- campaign_id：<stable-id>
- total_goal_version：<N>
- phase_id：<phase-N>
- phase_version：<M>
- prerequisite：<phase ids>

## 阶段目标

## 与总目标的对应关系

## 范围

## 非范围

## 当前用途、质量要求与风险边界

<!-- 必须满足 / 明确暂缓 / 可选建议，附批准依据；可引用已有约束，不按熟悉度自动填质量等级。 -->

## 用户批准的方案

## 接口与数据流

## 失败模式与停止条件

## 验收标准

## 验证命令与人工验收
```

对阶段快照文件字节计算 SHA-256。任何内容变化都必须新建更高 `phase_version`，重新计算 SHA-256 并再次获得用户批准。
此模板只用于新快照；旧快照已包含所需要求时直接复用，不为新增标题改写已批准文件。

## Goal 绑定模板

```text
仅执行受控目标 <campaign_id> 的 <phase_id>。
绑定：total_goal_version=<N>，phase_version=<M>，snapshot=<path>，sha256=<digest>。
完成条件：在本阶段边界内完成 Designer → Executor → Reviewer 闭环；Reviewer PASS 后生成用户评审包并进入 awaiting_user_approval。
禁止：改变总路线、扩大阶段范围、自动进入下一阶段、创建下一阶段 Goal、把 Reviewer PASS 当成用户批准。
```

## 模式切换提示

进入计划模式：

```text
需要切换模式：请切换到计划模式，然后回复“继续 <campaign_id> <phase_id> 方案讨论”。
原因：下一步需要改变或确认路线、阶段边界、方案或验收；当前不会继续执行或修改文件。
```

进入默认执行模式：

```text
需要切换模式：请切换到默认模式，然后回复“批准 <phase_id> 方案，落盘快照并创建该阶段 Goal”。
原因：计划已确认；下一步需要写入台账、创建单阶段 Goal 并执行实现。
```

等待用户评审：

```text
当前阶段已通过内部 Reviewer，状态为 awaiting_user_approval。请评审交付结果并明确回复“批准 <phase_id>”或“驳回 <phase_id>：<原因>”。在你批准前不会进入下一阶段。
```
