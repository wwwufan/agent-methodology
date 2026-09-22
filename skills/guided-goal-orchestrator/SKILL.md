---
name: guided-goal-orchestrator
description: >-
  以人工路线审批、阶段审批和一阶段一 Goal 的方式编排 Codex 大目标；维护总目标台账，
  在单个阶段 Goal 内自动运行 Designer、Executor、Reviewer 闭环，并在阶段之间强制等待用户决定。
  仅当用户显式点名 guided-goal-orchestrator、受控目标编排、人工门禁目标模式，或明确要求按该流程启动、继续、恢复时使用。
---

# 受控目标编排

把大型总目标拆成由用户掌握路线和阶段边界、由 Codex 在单个阶段内自动闭环的可恢复流程。

## 绝对约束

1. 总目标、执行路线、阶段顺序、阶段边界和最终阶段批准权归用户。
2. 一个 Codex Goal 只绑定一个阶段；不得把总目标或多个阶段创建成同一个 Goal。
3. Designer → Executor → Reviewer 循环只在当前阶段 Goal 内运行，不得跨 Goal、跨阶段或自动启动下一阶段。
4. Reviewer `PASS` 只表示内部门禁通过；阶段必须进入 `awaiting_user_approval`，只有用户明确批准后才能标记 `approved`。
5. 需要切换计划模式或默认执行模式时立即停止，用明确提示要求用户切换；不得声称 Skill 能自行切换客户端模式。
6. 只允许显式调用本 Skill。不得因任务看起来较大而自动进入受控目标流程。
7. 除非用户明确要求，否则不得创建分支、commit、push 或 PR。
8. 阶段进入 `awaiting_user_approval` 前，若该 campaign 存在推进栈
   （`workstacks/<campaign>/active-work-stack.json`），`stack.py verify` 必须返回 `exit 0`；
   存在未处置衍生登记时不得交付评审包。
9. 启动与恢复本 Skill 时按 `work-queue-stack/references/activation-and-recovery.md`「各编排身份的接线」guided 行执行：先 `stack.py stacks` 探测该 campaign 有没有推进栈，**已存在** → `stack.py ensure --campaign <campaign_id>`（幂等接线，**零提问**）；**不存在** → 按六维信号评估复杂度并 `stack.py propose` 打印申请卡，**未获用户批准不得创建、不得声称已启用**；被拒则把新问题写进 Executor 的 `remaining_risks` 与 Reviewer 的 `issues`/`residual_risks`，在当轮交付摘要留痕，并只在下一个自然边界（阶段收口、交付前）重提一次。
   本身份覆盖项：栈绑**总目标**、与 `workstacks/<campaign_id>/goal-ledger.md` 一对一，跨阶段跨窗口续用；**不得**为某个阶段、某次对话或某一轮另起一个栈（「阶段间收尾发生在 Goal 释放之后、栈是唯一状态载体」的理由句已迁入真源的身份表 guided 行）。

## 总目标台账

首次使用时读取 [台账与提示模板](references/ledger-template.md)，在 **`workstacks/<campaign>/`** 维护
（**纳入 Git**；与推进栈同目录，二者一对一绑定，因此栈的 `verify` 能机械校验绑定未断）：

```text
goal-ledger.md
phases/
└── phase-<N>-v<M>.md
```

`goal-ledger.md` 是状态真源，批准后的阶段快照是当前阶段 Goal 的不可变输入。每个 Goal 必须绑定：

- `campaign_id` 与 `total_goal_version`
- `phase_id` 与 `phase_version`
- 阶段快照路径与文件 SHA-256
- 当前阶段目标、范围、非范围、验收标准和前置阶段

每个阶段还必须声明 `execution_mode`：

- `goal`：由当前任务创建单阶段 Goal，并在 Goal 内完成实现闭环。
- `external`：由外部任务执行；当前任务只登记状态，不读取或干预外部执行。
- `review_only`：外部交付完成后创建独立审核 Goal，只允许影响核对、验收取证和复核，不得擅自修改交付物。

创建 Goal 前、调用每个角色前、处理用户中途引导后都重新读取台账并校验绑定。任一字段或 SHA-256 不一致时停止执行，将阶段标记为 `binding_mismatch`，要求用户切换到计划模式重新确认。

总目标或路线变化时递增 `total_goal_version`；阶段内容变化时创建新的 `phase-<N>-v<M+1>.md`，不得覆盖已批准快照。已批准完成的阶段保持不可变；若新路线使其失效，新增补偿阶段，不改写历史。

### 外部阶段

外部阶段允许在未读取外部任务内容时以 `external_in_progress` 登记，此时 `snapshot`、`sha256` 和 `goal_id` 必须为空。不得为仍在执行的外部阶段创建 Goal。

用户明确声明外部任务完成后，将状态改为 `external_ready_for_import`，并要求切换到计划模式。默认只在计划模式中导入外部任务的批准计划、变更、验证和证据，讨论并批准审核方案；随后生成不可变审核快照，把 `execution_mode` 切换为 `review_only`，再按单阶段规则创建审核 Goal。

如果用户已经掌握交付证据，并明确选择“由用户直接批准该外部阶段”，可以不创建 `review_only` Goal。此时只在台账决策记录中保存精简证据摘要、用户批准原文和批准时间，将外部阶段直接标记为 `approved`。不得把推定完成、Codex 自行判断或 Reviewer 之外的内部结论当成用户直接批准；该例外也不得自动解锁或执行下一阶段。

采用 `review_only` Goal 时，Designer 负责影响核对，Executor 只负责验收取证，Reviewer 负责独立复核。发现缺陷时不得在审核 Goal 中自动修复；停止并由用户决定退回外部任务或另建受控修复阶段。

## 工作流

### 1. 讨论总目标与路线

如果当前不在计划模式，停止并显示：

```text
需要切换模式：请切换到计划模式，然后回复“继续受控目标规划”。
原因：需要与你讨论总目标、路线、阶段边界和验收标准；本 Skill 不会自行切换模式。
```

在计划模式中完成只读探索并与用户确认：总目标、成功标准、全局约束、非范围、路线选择、阶段顺序、每阶段验收和依赖。只输出决策完整的计划，不修改文件、不创建 Goal。

用户确认全局计划后停止并要求切换到默认模式。仅在用户回复“落盘总目标台账”或等价明确指令后创建台账和阶段快照；此时仍不得创建阶段 Goal。

### 2. 讨论当前阶段方案

从台账选择第一个非 `approved` 阶段，校验所有前置阶段均为 `approved`。若当前不在计划模式，停止并要求用户切换。

在计划模式中只讨论当前阶段：可行方案、影响面、实现边界、接口和数据流、失败模式、测试与验收。不得重新决定总路线；发现阶段方案需要改变路线或阶段边界时，返回总目标规划并等待用户批准。

用户确认阶段方案后，生成新的不可变阶段快照内容。要求用户切换到默认模式并明确回复：

```text
批准 <phase_id> 方案，落盘快照并创建该阶段 Goal。
```

没有这条或等价的明确授权，不得写入快照、不得调用 `create_goal`、不得委托子代理。

### 3. 创建单阶段 Goal

在默认模式中落盘快照、计算 SHA-256、更新台账为 `approved_for_goal`，再调用 `get_goal` 确认没有未完成 Goal。若存在其他 Goal，停止并要求用户先处理，不得替换。

创建 Goal 时，目标正文必须包含完整绑定信息，并把完成条件限定为：当前阶段完成 Designer → Executor → Reviewer 内部门禁、交付用户评审包并进入 `awaiting_user_approval`。不得包含“进入下一阶段”或整个 campaign 的完成条件。

将工具返回的 Goal 标识（若提供）和绑定信息写回台账，然后把阶段标记为 `goal_active`。

`execution_mode=external` 的阶段禁止进入本步骤；只有完成导入并切换为 `review_only` 后才允许创建审核 Goal。

### 4. 在 Goal 内运行三角色闭环

创建当前阶段 Goal 的明确授权只覆盖该 Goal 内的 Designer、Executor、Reviewer。Codex 环境读取 `.codex/config.toml` 和 `.codex/agents/*.toml`；配置缺失或角色不可调用时停止，不得由主代理替代。

循环顺序：

1. Designer 只读核对用户批准的阶段方案、影响面和验证策略；不得改变路线。返回 `NEEDS_CONFIRMATION` 或 `BLOCKED` 时停止。
2. Executor 按批准快照实施并运行验收；发现需要改变路线、阶段边界或验收语义时停止。
3. Reviewer 独立只读复核并返回 `PASS` 或 `FAIL`。
4. `FAIL` 属于实现偏差或证据缺失时，在当前 Goal 内交给 Executor 修复；属于设计缺口时停止并要求回到计划模式。默认最多重试 3 次。

#### 角色字段契约以 `single-phase-execution-loop/references/role-contract.md` 为准（避免两份定义漂移）

三角色的**输入输出字段定义**以 `single-phase-execution-loop/references/role-contract.md` §2 为唯一真源，本 Skill 不重复定义、也不在此枚举字段名（枚举即第二真源，必然漂移）；冲突时以该文件为准，并修正本 Skill 的引用。

本 Skill 只**覆盖**受控模式特有的更强约束：

| 覆盖项 | 受控模式（本 Skill） | 单阶段循环默认 |
| --- | --- | --- |
| 设计缺口时的 FAIL 分流 | **停止 → 标 `plan_change_requested` → 回计划模式** | 回 Designer 重设计 |
| 理由 | 阶段方案是用户批准的**不可变快照**，Designer 无权改动 | 阶段方案内 Designer 有权调整实现设计 |

**禁止把授权强度参数化**：不得把上述差异下沉成 `single-phase-execution-loop` 的一个开关参数。
受控模式的门禁语义必须就地可读、自解释；参数传错就等于悄悄放宽了用户保留的批准权。

#### 推进栈接线

接线规则（通用接线动作表、`verify` 门禁与 `retro` 语义、栈帧与阶段的对应关系）以 `<skill 根>/work-queue-stack/references/activation-and-recovery.md`「各编排身份的接线」为唯一真源，本 Skill 不重复定义分流与门禁细节；本身份覆盖项：Executor 的 `remaining_risks`、Reviewer 的 `residual_risks` / `issues` 必须逐条 `capture` 进推进栈，且 `awaiting_user_approval` 前的 `verify` `exit 0` 门禁（绝对约束 8）不得降级。

每次委托前执行绑定校验，并在子代理上下文中写明 `campaign_id`、阶段绑定、当前 Goal 授权和“不得跨阶段”。

### 5. 内部 PASS 与用户最终门禁

Reviewer `PASS` 后：

1. 生成用户评审包：实现摘要、文件链接、验证证据、Reviewer 结论、残余风险和与总目标的对应关系。
2. 将阶段状态更新为 `awaiting_user_approval`。
3. 将当前阶段 Goal 标记完成；其含义仅是“已交付评审候选”，不是阶段已获用户批准。
4. 停止执行，等待用户明确回复批准或驳回；不得规划或创建下一阶段 Goal。

用户批准后把阶段标记为 `approved`，记录批准时间和用户原文，然后停止并要求切换到计划模式讨论下一阶段。用户驳回时标记 `changes_requested`，记录意见，递增阶段版本，并要求切换到计划模式；不得在旧 Goal 中继续扩展范围。

## 单 Goal 独占时的新问题分流

Codex 的 Goal 是**独占、串行、不可暂停**的资源：存在未完成 Goal 时 `create_goal` 直接失败，
`update_goal` 只能置 `complete` 或 `blocked`。因此阶段内冒出的新问题**不可能**靠
「再开一个 Goal」并行解决。

正确做法是先 `capture` 进当轮推进栈（零成本、不需要 Goal），再按范围三分流：

| 情况 | 动作 | 需要新 Goal |
| --- | --- | --- |
| 在当前阶段**已批准快照范围内** | 当前 Goal 内交 Executor 修（FAIL 分流：实现偏差） | 不需要 |
| **超范围 / 改路线 / 改阶段边界 / 改验收语义** | 立即停止 → 标 `plan_change_requested` → 要求切计划模式 → **当前 Goal 先收口** → 才为新阶段开 Goal | 需要，必须串行 |
| **跨轮次缺陷** | `pop --terminal escalated` + `docs/operations/issues.md` 立项 → 成为未来阶段（必要时新增补偿阶段） | 需要，排队等释放 |

**红线**：不得为了给新问题腾出 Goal 位置而把当前 Goal 标 `blocked`。`blocked` 的语义是
「同一阻塞条件连续三轮无法推进且确实需要用户输入或外部状态变化」，滥用它会污染状态、
让真正的阻塞失去信号价值。

推进栈在此的作用是**单 Goal 串行约束的缓冲区**：排队期间发现的问题有地方待着，不会丢，
也不会诱使编排违反「一阶段一 Goal」。

## 中途引导

- 补充信息不改变阶段快照：记录为执行注记，可在当前 Goal 内继续。
- 改变实现但仍符合批准方案：先让 Designer 判断是否仍在边界内；确认后继续。
- 改变阶段目标、范围、验收、路线或阶段顺序：立即停止，标记 `plan_change_requested`，要求切换计划模式并生成新版本快照。
- 用户说暂停或停止：立即停止自动循环，保留台账和证据，不自行恢复。

## 恢复与输出

恢复时先按 `work-queue-stack/references/activation-and-recovery.md`「恢复规则：由语义识别该用哪个栈」定位并接线栈（`stacks` 探测 → 指针有效且与当前总目标一致则直接接线；指针无效或缺失则语义匹配，**命中唯一**才 `use` 绑定，命中多个或零个时列候选由用户选、**不得猜**），本 Skill 不重复定义探测与匹配细节。随后读取台账、阶段快照、当前 Goal 状态和最后一份角色输出，然后决定继续当前 Goal、等待用户批准或要求切换模式。不得仅凭聊天历史推断状态。

每次停下都显示：总目标版本、当前阶段及版本、阶段状态、Goal 绑定、最近门禁结论、下一项只能由谁执行（用户或 Codex），以及需要用户发送的准确指令。
此外，若该 campaign 存在推进栈，必须原样附上 `stack.py show` 的**推进树与位置指针**两段，
不得改写成一句概述。

总目标收口（最后一个阶段获用户批准）时，还要附 `stack.py retro` 的
「放弃的方案 / 明确搁置 / 用户方向切换」三段：受控模式下阶段快照不可变，
被否决的路线与中途改道**只存在于推进栈里**，不复盘就等于把它们交给下一轮重新踩一遍。

## 禁止行为

- 不调用 `multi-phase-plan-orchestrator` 自动跨阶段推进。
- 不在计划模式中修改台账、创建 Goal 或执行阶段实现。
- 不把 Reviewer PASS 当作用户批准。
- 不在旧阶段快照上静默修改内容或遗漏版本递增。
- 不因 Goal 即将耗尽、执行困难或自动续跑而放宽阶段边界。
