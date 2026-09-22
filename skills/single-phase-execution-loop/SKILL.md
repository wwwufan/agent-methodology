---
name: single-phase-execution-loop
description: 面向单个阶段（单步计划）的执行循环：按 designer → executor → reviewer 推进，并根据 FAIL 类型分流到 executor 重试或 designer 重设计。适用于用户要求“单阶段闭环/门禁复核/失败重试”的场景。
---

# 单阶段执行循环（Designer/Executor/Reviewer）

用于把“一个阶段”稳定跑完：设计、实现、复核、失败分流、重试、收敛。

## 与多阶段编排的关系

- 本 skill 只负责“单个阶段内”的闭环执行。
- 若任务是多阶段（Phase 1/2/3...）推进，外层请使用 `multi-phase-plan-orchestrator`，由它选择当前阶段；本 skill 负责把该阶段跑到 PASS。

## 适用场景

- 用户明确要求“编排模式”“分阶段推进”“调 designer/executor/reviewer subagent”。
- 阶段有明确验收标准（自动化命令 + 手工验收项）。
- 需要 FAIL 后可追踪、可重试、可分流（实现问题 vs 设计问题）。

不适用：一次性小改、无需 reviewer 门禁的简单任务。

## 输入前置

每次开始一个阶段前，主代理必须掌握：

1. `execution_plan`（当前阶段目标、范围、验收）
2. `progress_tracker`（阶段状态、retry 次数、max_retries）
3. `global_constraints`（跨阶段硬约束）
4. 当前阶段 `N` 的上一轮结果（若有）

## 阶段级授权

- 用户明确要求使用本 skill 执行某个 Phase 时，视为授予该 Phase 内 designer -> executor -> reviewer 循环的阶段级授权。
- 阶段级授权生效后，主代理可按标准循环连续调度子代理，不再要求每一步单独向用户索取授权。
- 阶段级授权必须写入每个子代理 prompt 的 `invocation_context` 或 `phase_authorization`，明确说明当前调用来自 `single-phase-execution-loop`。
- 若 Designer 返回 `NEEDS_CONFIRMATION` / `BLOCKED`，或 Reviewer 达到 `max_retries` 仍失败，必须停止并回到用户。
- 主代理不得因子代理调用失败而静默降级为自行设计、实现或复核；必须向用户报告阻塞原因。

## 子代理绑定

- Designer：项目角色 `designer`
- Executor：项目角色 `executor`
- Reviewer：项目角色 `reviewer`

配置真源由当前后端决定：Cursor 只读 `.cursor/agents/`；Codex 只读 `.codex/config.toml` 和 `.codex/agents/`。禁止跨后端复制或混用配置。

### 模型绑定前置检查

每次进入 Phase 时由外层编排器识别后端并完成一次完整校验；角色调用前再确认配置未变化：

1. Cursor `Subagent`：读取 frontmatter，并在调用中显式传入模型和运行参数。
2. Codex named-agent：按 `.codex/config.toml` 注册名调用，确认注册配置可解析。
3. Codex collaboration：运行 `check_codex_backend.py`；仅在三个角色模型均与活动模型一致时允许后端托管继承，并把对应 TOML 的 `developer_instructions` 作为 `role_contract` 传入 prompt。
4. 配置模型、活动模型、可用模型或工具能力任一不满足时，当前 Phase 直接 `BLOCKED`。

不要在 Skill 中复制易过期的具体模型速查值；模型真源始终是当前后端配置。

职责分离：

- 主代理：组装当前阶段上下文、确认阶段级授权、执行 FAIL 分流、维护 retry 与证据路径
- Designer：只读分析调用链、影响面、方案取舍、测试策略和 reviewer 关注点
- Executor：阶段内实施或取证、运行验收、如实报告风险
- Reviewer：只读复核 Designer 方案与 Executor 结果，重跑验收，输出 PASS / FAIL 与修复指令

Codex collaboration 后端无法强制每个子代理使用独立 sandbox。主代理必须用工作区基线补偿：Designer/Reviewer 调用前后比较工作区状态；只读角色发生写入即视为角色契约违规并停止当前循环。

主代理不得替代 Executor 修改代码、不得替代 Reviewer 宣告 PASS，也不得把 Designer / Executor / Reviewer 的职责合并到主代理自身执行。

## 标准循环

### Step 0: Designer

调用条件：阶段级授权已生效，且当前阶段尚未完成设计。

必须输入：

- `phase_authorization`：用户已授权本 Phase 进入单阶段循环
- `design_id`：`<campaign>-phase-N`
- 当前阶段目标/范围/验收标准
- 当前上下文与历史失败信息
- 阶段涉及的模块、目录或边界提示
- 全局约束

必须输出：

- `design_status`：`READY` | `NEEDS_CONFIRMATION` | `BLOCKED`
- `recommended_design`
- `executor_instructions`
- `validation_strategy`
- `reviewer_focus`

决策：

- `READY` -> 可进入 Executor
- `NEEDS_CONFIRMATION/BLOCKED` -> 停止并回到用户确认，不可进入 Executor

### Step 1: Executor

调用条件：Designer 返回 `READY`，且当前阶段需要实施、修复或验收取证。

必须输入：

- `phase_authorization`：用户已授权本 Phase 进入单阶段循环
- `campaign` 活动标识
- 当前阶段完整执行章节
- Designer 输出（完整）
- 全局约束
- 当前工作分支名（仅用于追踪上下文；不自动新建阶段分支）
- 若 `retry > 0`，附上上一轮 reviewer `fix_instructions`

必须输出：

- `implementation_summary`
- `changed_surface`
- `validation`（命令与关键输出）
- `remaining_risks`（**每条都必须 `capture` 进推进栈**，见「推进栈接线」；不得只留在对话里）

### Step 2: Reviewer

调用条件：Executor 返回实施或取证结果，且需要门禁复核。

必须输入：

- `phase_authorization`：用户已授权本 Phase 进入单阶段循环
- 当前阶段验收标准（仅该阶段）
- Designer 输出（完整）
- Executor 输出（完整）
- 指令：只读复核、重跑验收命令、不得修改文件、不得自动修复
- 检查实现是否遵守 Designer 推荐方案、是否覆盖影响面、是否违背全局约束

必须输出 YAML：

```yaml
review_id: <campaign>-phase-N[-retry-k]
review_subject: <阶段说明>
verdict: PASS | FAIL
checks:
  - name: <check>
    status: pass | fail | skipped
    output: "<证据>"
issues: []
fix_instructions: []
residual_risks: []
```

Reviewer 返回的 `residual_risks` 与 `issues` 同样必须逐条 `capture`；`verdict: FAIL` 时把归因写进
`capture --text`，使「这一轮为什么没过」在栈里可查，而不是只存在于本次对话。

## 推进栈接线（work-queue-stack）

本循环产生的每一个**阶段范围外的新问题**都必须落进推进栈——但**单阶段编排只接线、不创建栈**：

- 栈**已存在**（用户主动声明需要任务栈，或用户批准了 `propose` 申请卡）→ 按下表**接线**：
  `capture` 衍生、`pop` 关帧、`verify` 门禁。
- 栈**不存在** → **不得**运行 `ensure`，也不得用首次 `push` 把栈创建出来。改为把新问题写进
  Executor 的 `remaining_risks` 与 Reviewer 的 `issues`/`residual_risks`，并在交付摘要中逐条列出；
  若判断确有跨会话丢失风险，按 `work-queue-stack/references/activation-and-recovery.md` 的六维信号评估后
  运行 `propose` 打印申请卡，**由用户批准**才启用（`ensure` 对新建栈强制要求非 legacy 的 `--activation`，
  绕过不了）。

「启用」与「接线」是两件事：启用**只由用户声明或批准**（见 `work-queue-stack` 的「启用与恢复路由」），
接线只看栈是否存在。栈脚本 `S=<skill 根>/work-queue-stack/scripts/stack.py`
（`<skill 根>` = 装着所有 skill 的那一层：仓库 `skills/`、全局 `~/.codex/skills/`、项目 `.agents/skills/`），
`--campaign` 用当前活动标识；栈绑总目标（campaign），跨阶段跨窗口续用同一个，不另起。

| 时点 | 机械动作 | 强度 |
| --- | --- | --- |
| Executor 返回 `remaining_risks` | 逐条 `capture --found-in <Phase 帧> --disposition blocks\|spawns\|note` | 必须 |
| Reviewer 返回 `residual_risks` / `issues` | 逐条 `capture`；FAIL 归因写进 `--text` | 必须 |
| 达到 `max_retries` 转 blocked | `capture` → `pop --terminal escalated`，并在 `docs/operations/issues.md` 立项 | 必须 |
| **PASS 推进前** | **`verify` 必须 `exit 0`**，否则不得写 `progress_tracker`、不得进入下一阶段 | **fail-closed 门禁** |
| PASS 推进时 | `pop` 当前 Phase 帧，`--note` 写 Reviewer 结论与证据路径 | 必须 |
| 帧的标题/判据写错、或验收口径变了 | `amend --frame <未关闭帧>`（改动自动留痕 `event_log`）；**终态帧不可改写**，要纠正就新压一帧说明返工 | 必须 |
| 全部 Phase 收工 / 计划中止 / 交付前 | `retro`（只读）→ 原样转达「放弃的方案」「明确搁置」「用户方向切换」三段 | 必须 |
| **任何时点** | **不得 `ensure` / 首次 `push` 创建栈**（只接线不创建；确有需要走 `propose` 申请，用户批准才建） | **禁止** |

`verify` 失败意味着存在未处置的衍生登记（`pending`），或 `blocks`/`spawns` 未落到某个帧或指针。
这是**门禁而不是提醒**：先 `resolve` 干净再推进；不得跳过 `verify` 绕过。

`retro` 同理不是可选项：收工报告只讲「完成 N 个 Phase」会丢掉最贵的信息——哪些方案被放弃、
哪些被搁置、用户中途改了几次道。这三段来自只追加的 `event_log`，**推进时没留痕就复盘不出来**，
所以每一次改道与放弃都必须在发生的当时落进栈（`activate` / `pop --terminal wontfix|parked` + `--note`），
不允许事后补记。

### 栈帧与 Phase 的对应关系（避免栈被噪音淹没）

- **一个 Phase 一帧**：`push --title "Phase N <阶段名>" --criteria <该阶段验收标准>`。
- Phase 内的**返工重试不另立子帧**——retry 计数的真源是 `progress_tracker`，重复登记只会制造两份状态。
- 只有**阶段范围外的新问题**才 `push --parent <Phase 帧>` 成子帧；范围内的实现偏差走 FAIL 分流规则 1，
  由 Executor 在当前 Phase 内修掉。
- 判定「范围内/范围外」的依据是 `execution_plan` 的当前阶段章节与 `global_constraints`；
  拿不准时按**范围外**处理（先登记，宁可多登不可漏登）。

### 本 Skill 是三角色字段契约的真源

Designer / Executor / Reviewer 的**输入输出字段定义以本 Skill 为准**。
`guided-goal-orchestrator` 在受控模式下复用这些字段契约，只**覆盖** FAIL 分流策略
（因其阶段方案是用户批准的不可变快照，设计缺口必须停止回计划模式，不得由 Designer 自行重设计）。
两处若出现字段定义冲突，以本 Skill 为准，并修正受控编排侧的引用。

## FAIL 分流规则（核心）

Reviewer 为 `FAIL` 时，主代理按类型分流：

1. **实现偏差 / 修复可直接编码**
   - 现象：校验缺口、边界 case 漏测、逻辑遗漏、配置约束未落实、回归 bug
   - 动作：`retry + 1`，调用 **executor**，并传入 `fix_instructions`

2. **设计缺口 / 方案不成立 / 影响面遗漏**
   - 现象：当前方案本身矛盾、边界定义错误、全局约束冲突、需重选技术路径
   - 动作：返回 **designer** 重新设计（带上 reviewer 问题）

3. **证据缺失（代码基本通过但验收证据不全）**
   - 现象：自动化通过，但缺 staging 手工验收、缺运行记录、缺外部依赖验证证据
   - 动作：调用 **executor** 执行“验收取证任务”（可不改代码），补齐证据后再 reviewer

4. **达到最大重试**
   - 条件：`retry >= max_retries`
   - 动作：停止循环，向用户报告阻塞项与建议
   - 栈动作：`capture` 后 `pop --terminal escalated --pointers '{"issues":["ISS-0xx"]}'`，
     并在 `docs/operations/issues.md` 立项。**阻塞项不得只留在对话里**——对话会被压缩、换模型或跨天丢弃。

### 失败后的通俗解释

Reviewer `FAIL`、阶段 `blocked`、达到 `max_retries`，或不可恢复的验收命令失败后，调用 `explain-task-failure` 生成面向用户的说明，再决定是否进入下一轮。该说明必须包含失败原因、已通过/未通过部分、影响范围、术语翻译和一个对应的日常例子；不得替代 Reviewer YAML、改变 retry 计数或把 FAIL 改写成 PASS。

若仍可重试，先给用户展示简短解释，再把 Reviewer 的技术 `fix_instructions` 传给 Executor；若达到最大重试或 blocked，则停止自动推进，并把解释中的 blocker、证据和下一步交还用户。

## PASS 推进规则

- Reviewer `PASS`：
  - **先过栈门禁**：`python3 $S verify --campaign <活动标识>` 必须 `exit 0`；
    失败则先把未处置衍生 `resolve` 干净，**不得跳过**
  - 当前阶段标记 `done`
  - `pop` 当前 Phase 帧，`--note` 写 Reviewer 结论、关键证据路径与残余风险去向
  - 写入 `progress_tracker`（时间戳 + 结论 + 关键证据）
  - 进入下一阶段前，交回外层 `multi-phase-plan-orchestrator` 选择下一 Phase

## 输出与记录规范

每轮都要沉淀：

- 子代理输出原文要点（尤其 reviewer YAML）
- 自动化命令与关键输出
- 手工验收记录路径（建议在 `scratch/runtime/<campaign>-phaseN-manual/`）

稳定结论进 `docs/`，过程证据留 `scratch/`。

## 快速命令模板

### 启动单阶段循环

```text
使用 single-phase-execution-loop 跑 <campaign> Phase <N> <阶段名>，直到 PASS 或 BLOCKED
```

### 从实现失败继续

```text
使用 single-phase-execution-loop 继续 <campaign> Phase <N>，按 reviewer fix_instructions 修复
```

### 从设计失败重开

```text
使用 single-phase-execution-loop 重新设计 <campaign> Phase <N>：<设计问题摘要>
```

### 补手工验收证据

```text
使用 single-phase-execution-loop 为 <campaign> Phase <N> 补齐手工验收记录（<验收项列表>）
```
