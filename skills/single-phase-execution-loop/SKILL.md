---
name: single-phase-execution-loop
description: 面向单个阶段（单步计划）的执行循环：按 designer → executor → reviewer 推进，并根据 FAIL 类型分流到 executor 重试、designer 重设计或证据驱动探索。适用于用户要求“单阶段闭环/门禁复核/失败重试”的场景。
---

# 单阶段执行循环（Designer/Executor/Reviewer）

用于把“一个阶段”稳定跑完：设计、实现、复核、失败分流、重试、收敛。

## 与多阶段编排的关系

- 本 skill 只负责“单个阶段内”的闭环执行。
- 若任务是多阶段（Phase 1/2/3...）推进，外层请使用 `multi-phase-plan-orchestrator`，由它选择当前阶段；本 skill 负责把该阶段跑到 PASS。

## 适用场景

- 用户明确要求“编排模式”“分阶段推进”“调 designer/executor/reviewer subagent”。
- 阶段有明确验收标准（自动化命令 + 手工验收项）。
- 需要 FAIL 后可追踪、可重试、可分流（实现偏差 vs 设计缺口 vs 认知缺口）。

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

字段契约（必须输入 / 必须输出清单）见 `references/role-contract.md` §2「Designer（Step 0）」——唯一真源，本 Skill 不重复定义。

决策：

- `READY` -> 可进入 Executor
- `NEEDS_CONFIRMATION/BLOCKED` -> 停止并回到用户确认，不可进入 Executor

### Step 1: Executor

调用条件：Designer 返回 `READY`，且当前阶段需要实施、修复或验收取证。

字段契约（必须输入 / 必须输出清单）见 `references/role-contract.md` §2「Executor（Step 1）」——唯一真源，本 Skill 不重复定义。

### Step 2: Reviewer

调用条件：Executor 返回实施或取证结果，且需要门禁复核。

字段契约（必须输入清单 + 必须输出的 Reviewer YAML 七字段，原样）见 `references/role-contract.md` §2「Reviewer（Step 2）」——唯一真源，本 Skill 不重复定义。

## 推进栈接线（work-queue-stack）

接线规则（通用接线动作表、`verify` 门禁与 `retro` 语义、栈帧与 Phase 的对应关系）的唯一真源是 `<skill 根>/work-queue-stack/references/activation-and-recovery.md`「各编排身份的接线」，本 Skill 不重复定义。栈脚本 `S=<skill 根>/work-queue-stack/scripts/stack.py`（`<skill 根>` = 装着所有 skill 的那一层：仓库 `skills/`、全局 `~/.codex/skills/`、项目 `.agents/skills/`），`--campaign` 用当前活动标识。

本身份（单阶段编排）覆盖项——强度不低于真源，逐条就地可读：

- **只接线不创建**：栈存在才 `capture` / `pop` / `verify`；不存在**不得** `ensure`、也不得用首次 `push` 建栈，改为写进 Executor 的 `remaining_risks` 与 Reviewer 的 `issues` / `residual_risks`，并按真源评估后 `propose` 打印申请卡，**由用户批准**才启用。「启用」与「接线」是两件事：启用**只由用户声明或批准**，接线只看栈是否存在。
- **`verify` fail-closed 门禁在 PASS 前**：`verify` 必须 `exit 0`，否则不得写 `progress_tracker`、不得进入下一阶段。
- **一个 Phase 一帧**；Phase 内的返工重试**不另立子帧**（retry 计数真源是 `progress_tracker`）。
- **范围外的新问题** `push --parent <Phase 帧>` 成子帧；范围内的实现偏差走 FAIL 分流规则 1，由 Executor 在当前 Phase 内修掉。
- **收工 `retro`**：原样转达「放弃的方案」「明确搁置」「用户方向切换」三段，不得改写成一句概述。
- 栈绑总目标（campaign），跨阶段跨窗口续用同一个，不另起。

三角色字段契约（必须输入 / 必须输出）的唯一真源是 `references/role-contract.md` §2，本 Skill 不重复定义；`guided-goal-orchestrator` 只**覆盖**「设计缺口分流」一项，覆盖表与理由就地写在 `guided-goal-orchestrator/SKILL.md`。

FAIL 五类分流规则的语义在 `references/role-contract.md` §3，本 Skill 不重复定义。

失败后的通俗解释（`explain-task-failure` 的调用义务与禁止事项）在 `references/role-contract.md` §3「失败后的通俗解释」，本 Skill 不重复定义。

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
