---
name: multi-phase-plan-orchestrator
description: >-
  通用多阶段计划编排：负责选择 Phase、读取计划、管理进度和阶段切换。
  在用户要求运行、继续或恢复任意分阶段执行计划时使用；单个 Phase 内的 designer/executor/reviewer 循环交给 single-phase-execution-loop。
---

# 多阶段计划编排器

本 skill 定义**多阶段计划的外层状态机**，不绑定单一主题。它负责定位活动、选择当前 Phase、
核对进度和在当前 Phase 完成收尾后推进到下一阶段；当前阶段记录由内层循环维护。

## 与单阶段循环的关系

- 本 skill 是“外层编排器”，负责选择当前 Phase、核对整体进度和阶段切换。
- 每个 Phase 内部的 designer -> executor -> reviewer、阶段级授权、FAIL 分流和重试规则，统一交给 `single-phase-execution-loop`。
- 内层是当前阶段 retry、风险登记、完成记录及 Phase 帧收尾的唯一负责方；外层不重复计数、解释或关闭同一帧。

## 适用场景

- 大型、多阶段、需逐阶段交付的计划
- 每阶段有明确目标、范围和验收标准
- 需要进度可恢复、可审计（进度文件 + 评审 YAML）

不适用：单文件小改、无分阶段计划的局部 refactor、无需 review 门禁的一次性改动。

## 任务绑定（启动前必读）

编排器从以下配置驱动：优先使用用户明确绑定；未指定时按文末“活动实例的发现与登记”
读取项目侧材料，只在与当前任务匹配的活动唯一时继续。零个候选时补齐计划绑定，
多个候选时请用户选择；不使用方法论仓库预设的活动默认值。

| 配置项 | 含义 | 如何确定 |
| --- | --- | --- |
| `execution_plan` | 分阶段执行方案（含各阶段目标、步骤、验收、全局约束） | 用户指定路径，或唯一匹配的项目活动绑定 |
| `progress_tracker` | 进度跟踪文件（阶段状态、重试、基线） | 用户指定路径，或唯一匹配的项目活动绑定 |
| `commit_prefix` | 用户批准 commit 时的 scope 前缀 | 默认 `refactor(<scope>)` |
| `global_constraints` | 跨阶段硬约束（来自执行方案中的约束章节） | 从 `execution_plan` 摘录，交给内层单阶段循环 |
| `max_retries` | 每阶段最大纠正轮次（首次执行不计） | 默认 3；可被 `progress_tracker` 覆盖；计数及末次评审以角色契约 §3 为准 |

启动时必须：

1. 读取 `progress_tracker` → 确定当前阶段 N 与 retry 计数
2. 读取 `execution_plan` 中阶段 N 的完整章节 + 全局约束章节
3. 按「编排后端适配」识别当前接口并校验对应的 Cursor 或 Codex 角色配置
4. 向用户报告：活动名称、当前阶段、当前工作分支、未完成项（中文）
5. 默认沿用当前工作分支执行各阶段；仅当用户明确要求时才创建新分支
6. 按 `<skill 根>/campaign-work-stack/references/activation-and-recovery.md`「各编排身份的接线」multi-phase 行执行：`stack.py stacks` 探测 → **已存在**则 `stack.py ensure --campaign <活动标识>` 幂等接线（只回显、不新建、不改 `activation`），随后 `stack.py show` 查看全栈；**不存在**则按六维信号评估并 `stack.py propose` 打印申请卡，**未获用户批准不得创建、不得声称已启用**；被拒则把新问题写进各 Phase 的 `remaining_risks` / `issues`，并在阶段收口处重提一次（同一轮内不重复申请）。
   本身份覆盖项：栈绑**总目标**（campaign）而非阶段或对话窗口，因此跨阶段、跨窗口续用同一个栈，**不得**为新一轮另起一个。
   复用当前阶段的活动帧；后续阶段的 `queued` 帧保留，不要求提前收口。
   只有当前阶段尚未完成收尾、前置阻塞未解决或活动归属不明时，才停止切换并核对，不得静默抢占其他活动帧。

若用户发起**新的重构活动**，须先具备或创建对应的 `execution_plan` 与 `progress_tracker`，并在对话中声明绑定（或新增「活动实例」条目后再启动）。

## 实现取向（继承当前任务要求）

组装当前阶段输入时读取 `project-context-brief/references/task-contract.md`，外层与内层复用同一要求：

- 在已确认用途、质量要求及风险边界内选择合适实现；不为缩小 diff 牺牲已要求的保障，也不追加未要求的工程目标。
- 熟悉度只影响信息与探索需求，不决定生产级或原型级质量；未指定时沿用项目约束及当前验收，关键缺口才询问。
- 涉及目标、质量、成本、风险的实质取舍时说明影响并请用户确认；边界内已有依据的实现选择不重复索取批准。
- 项目硬约束和批准方案保持有效；冲突时停止相关动作并澄清，不能用上下文摘要或“只要可用”覆盖。

## 阶段执行委托

当前阶段 N 的内部闭环由 `single-phase-execution-loop` 负责。主代理在进入阶段执行前，应把以下信息交给内层循环：

- 活动标识、当前 Phase 编号与阶段标题
- 当前阶段完整章节
- `global_constraints`
- 当前用途、质量/风险要求、明确暂缓项及其来源（复用计划和上下文，不另填表）
- 当前工作分支名（仅用于追踪上下文）
- 当前 retry 计数与 `max_retries`
- 上一轮 reviewer YAML（如有）

主代理不得在外层重复定义 designer/executor/reviewer 的 prompt 细节；这些细节以 `single-phase-execution-loop` 为准。
内层返回后，外层按共享交接约定核对阶段位置、结论与证据范围、剩余阻塞及下一步权限，
并执行下方“阶段结果决策”；交接建议不能绕过阶段收尾或自动扩大下一阶段授权。

子代理统一继承主窗口模型，角色配置与调用参数均不指定具体模型；权限和角色契约按当前编排后端读取；不得把 Cursor 配置传给 Codex，也不得把 Codex 配置当作 Cursor frontmatter。

## 编排后端适配

先检查当前可调用工具的参数，不按产品名称猜测后端：

### Cursor `Subagent` 后端

- 读取 `.cursor/agents/<role>.md` frontmatter。
- frontmatter 省略 `model`，调用时也不传具体模型；保留 `readonly`、`is_background` 参数。
- 后端无法继承主窗口模型时把当前 Phase 标记为 `BLOCKED`。

### Codex named-agent 后端

- 读取 `.codex/config.toml` 的 `agents.<role>.config_file` 与对应 TOML。
- 通过接口提供的代理名调用，让 Codex 加载 sandbox、approval 和 developer instructions；角色 TOML 省略 `model`，模型继承父会话。
- 调用结果无法确认命中注册角色时把当前 Phase 标记为 `BLOCKED`。

### Codex collaboration 后端

适用于只暴露 `spawn_agent(task_name, message, fork_turns)`、没有 per-call `model` 或 named-agent 参数的当前协作接口。

1. 运行：

```bash
# <skill 根> = 装着所有 skill 的那一层：仓库 skills/、全局 ~/.codex/skills/、项目 .agents/skills/
python3 <skill 根>/single-phase-execution-loop/scripts/check_codex_backend.py \
  --repo-root <repo-root>
```

2. 只有输出 `status=ready` 时才能委托。校验器要求 Designer、Executor、Reviewer 的 Codex 配置均省略 `model` 并保留各自权限与角色契约；模型由后端继承主窗口，不依赖 CLI 全局默认模型探测。
3. 读取 `.codex/agents/<role>.toml` 的 `developer_instructions`，把它作为 `role_contract` 传入 `spawn_agent` prompt；不得读取 `.cursor/agents`。
4. prompt 额外声明：
   - `orchestration_backend: codex_collaboration`
   - `runtime_model_policy: backend_managed_inheritance`
   - `role: designer|executor|reviewer`
5. Designer/Reviewer 是只读角色。调用前记录工作区基线，调用后复核；发生新增写入时 Reviewer 判定当前 Phase FAIL，主代理不得把变更当作有效产物。
6. `spawn_agent` 返回的 task name 只用于编排追踪，不等同于 `.codex/config.toml` 的 named-agent 选择。

任何后端能力与上述契约不匹配时停止，不得退回主代理自行执行 Designer、Executor 或 Reviewer 职责。

当用户要求使用本 skill 运行、继续或恢复某个多阶段计划时，视为同时授予当前 Phase 内 `designer`、`executor`、`reviewer` 三类项目级 subagent 的阶段级调用权限。主代理进入 `single-phase-execution-loop` 时必须在子代理 prompt 中写明：

```text
invocation_context: 用户已授权 multi-phase-plan-orchestrator 执行当前 Phase；该 Phase 按 single-phase-execution-loop 自动委托 designer/executor/reviewer。
phase_authorization: 当前 Phase 已获阶段级授权，主代理只负责编排、分流和记录，不替代子代理执行职责。
```

如果任一子代理无法被调用，主代理必须停止当前 Phase 并向用户报告原因，不得自行代替 Executor 实施或代替 Reviewer 判定 PASS。

## 阶段结果决策

| 结论 | 动作 |
| --- | --- |
| 当前 Phase PASS 且内层收尾完成 | 核对内层返回的 `review_id`、证据、阶段 `done` 记录；有栈时核对其校验及 Phase 帧关闭结果，无栈时核对阶段记录完整性；不重复写入或 `pop`，再按原授权进入 N+1 |
| Reviewer PASS 但内层收尾未完成 | 留在当前阶段，交内层从收尾记录恢复；不得提前进入 N+1 |
| 当前 Phase FAIL 且仍可重试 | 交内层按 FAIL 分流继续；retry 与失败记录只由内层更新，外层不再加一次 |
| 当前 Phase 最后一轮评审仍 FAIL 且达到 `max_retries` | 停止；不因切换路线刷新额度，不截断已启动末轮的评审 |
| 内层因连续无进展或探索预算耗尽暂停 | 保留停止原因和原位置，交还用户；不自行重启内层或推进依赖该结果的阶段 |
| 当前 Phase BLOCKED / NEEDS_CONFIRMATION | 停止；向用户报告待确认项，不推进阶段 |

在上述 FAIL、达到 `max_retries` 或 BLOCKED 的分支中，复用内层已生成的 `explain-task-failure` 说明；
只有失败发生在外层（如活动绑定/后端前置检查失败）或内层未提供解释时，才补一次。
按 `campaign-work-stack/references/output-contract.md` 分级展示，区分证据与未验证项；
日常例子仅在帮助理解或用户要求时提供，不得改变阶段状态或自动重跑昂贵任务。

有栈时，由问题所属的阶段负责方登记并处置阻塞项与阶段范围外问题，外层复用记录；
仅在外层新发现、内层未登记的问题才由外层登记。无栈时保存到已有进度/阶段报告中，包含处置和恢复条件。
**不得让阻塞只存在于对话里**——对话会被压缩、换模型或跨天丢弃。
接线细节以 `<skill 根>/campaign-work-stack/references/activation-and-recovery.md`「各编排身份的接线」为准，三角色字段契约与 FAIL 五类分流以 `single-phase-execution-loop/references/role-contract.md` 为准，本 Skill 不重复定义。

最后一个 Phase PASS、或整个计划被中止时，已有栈仍运行 `stack.py retro`，按输出约定汇报
「放弃的方案 / 明确搁置 / 用户方向切换」；无新增变化可简报，有变化说明原因和去向。多阶段计划跨越数天，
中途被否决的路线若不显式复盘，下一轮极可能原样重走。无栈时从阶段记录回顾，不运行栈命令或伪造栈历史。

**不得跳过阶段。除非用户明确要求，否则不得 commit。**

## 恢复执行

当用户说「继续重构」「继续 <活动名>」或 "continue refactor" 时：

1. 解析任务绑定（用户指定，或唯一匹配的项目侧活动）
2. 读取 `progress_tracker` → 第一个未完成阶段
3. 向用户报告当前状态（中文）
4. 当前阶段收尾未完成时交回内层恢复；已完成且原多阶段授权仍有效时按序继续。
   用户暂停、预算/重试门禁或新审批要求仍须停止，并给出准确恢复条件；不为普通阶段切换另加确认门禁。

## PR / Commit 约定

用户按阶段批准 commit 后，消息格式：

```text
<commit_prefix>: phase-N-<short-name>
```

示例：`refactor(monorepo): phase-2-migrate-web`

---

## 活动实例的发现与登记

**本方法论仓库不保存任何业务活动台账**：活动实例（campaign 与其计划/进度文档的对应关系）是项目侧状态，
住在使用本 skill 的项目里，不随 skill 分发；本仓库只描述**怎么发现与登记**，不描述任何一个具体活动。

- **发现**：读项目侧 `workstacks/_activities.md`（仓库根相对路径）。**该文件可能不存在** ——
  新项目还没登记过任何活动时它就是缺失的，**这不是错误，也不得据此判定编排不可用**。
  缺失时按发现规则从既有材料推导：`execution_plan` / `progress_tracker` 取项目计划与进度文档
  （常见落点 `scratch/workbench/<campaign>/execution-plan.md` 与 `progress.md`，项目也可自定义位置）
  头部的自我声明；`commit_prefix` 取该计划的提交前缀约定；`global_constraints` 取其「全局硬约束」章节。
- **登记**：每个活动一节，至少含 `活动标识`、`execution_plan`、`progress_tracker`、`commit_prefix`、
  `global_constraints` 来源五项，阶段序列可选；新增活动时在该文件追加一节，并在 `progress_tracker` 头部回指对应 `execution_plan` 与本 skill。
- **禁止**：把已完成的一次性计划或进度日志长期留在项目 `docs/`（那里只放阶段性稳定总结），
  也不要把任何活动实例写回本仓库的文件。
