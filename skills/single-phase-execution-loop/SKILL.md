---
name: single-phase-execution-loop
description: 面向单个阶段（单步计划）的执行循环：按 designer → executor → reviewer 推进，并根据 FAIL 类型分流到 executor 重试、designer 重设计或证据驱动探索。适用于用户要求“单阶段闭环/门禁复核/失败重试”的场景。
---

# 单阶段执行循环（Designer/Executor/Reviewer）

用于把“一个阶段”稳定跑完：设计、实现、复核、失败分流、重试、收敛。

## 与多阶段编排的关系

- 本 skill 只负责“单个阶段内”的闭环执行。
- 若任务是多阶段（Phase 1/2/3...）推进，外层请使用 `multi-phase-plan-orchestrator`，由它选择当前阶段；本 skill 负责把该阶段跑到 PASS。
- 本 Skill 的主代理是当前阶段记录、retry 和 Phase 帧收尾的唯一负责方，外层只消费结果，不重复写入。
  独立调用时收尾后交还用户；受控目标流程只复用角色/FAIL 契约，阶段状态及人工批准由 `guided-goal-orchestrator` 自己管理。

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

按 `references/role-contract.md` §2 的共同输入约定核对当前任务要求，将同一质量/风险边界、
成功判据及来源传给三个角色。已有计划足够就复用，不强制新建上下文包或额外调用 Skill。
接收上下文或探索交接后，先核对原阶段、证据适用范围、剩余阻塞和权限，再恢复具体步骤；
输入齐全不替代本 Skill 的阶段授权与门禁。

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

每次进入 Phase 时由主代理识别后端并完成一次完整校验；已有外层完成的有效校验则复用，
独立调用时由本 Skill 的主代理完成；角色调用前再确认配置未变化：

三个角色的配置均省略 `model`；调用时也不传具体模型，统一由后端继承当前主窗口（父会话）的模型。不要把 CLI 全局默认模型当作主窗口当前模型，也不要把当前模型名写回角色配置。

1. Cursor `Subagent`：读取 frontmatter，保留只读和前后台参数；省略调用的 `model`，使用父会话继承。
2. Codex named-agent：按 `.codex/config.toml` 注册名调用，确认注册配置可解析且角色 TOML 未指定 `model`。
3. Codex collaboration：运行 `check_codex_backend.py`，检查角色配置、模型继承策略与权限；把对应 TOML 的 `developer_instructions` 作为 `role_contract` 传入 prompt。
4. 若角色配置或调用参数覆盖了模型，或后端无法继承主窗口模型，当前 Phase 直接 `BLOCKED`。不得用 CLI 模型探测结果替代父会话模型。

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

## 推进栈接线（campaign-work-stack）

接线规则（通用接线动作表、`verify` 门禁与 `retro` 语义、栈帧与 Phase 的对应关系）的唯一真源是 `<skill 根>/campaign-work-stack/references/activation-and-recovery.md`「各编排身份的接线」，本 Skill 不重复定义。栈脚本 `S=<skill 根>/campaign-work-stack/scripts/stack.py`（`<skill 根>` = 装着所有 skill 的那一层：仓库 `skills/`、全局 `~/.codex/skills/`、项目 `.agents/skills/`），`--campaign` 用当前活动标识。

本身份（单阶段编排）覆盖项——强度不低于真源，逐条就地可读：

- **只接线不创建**：栈存在才 `capture` / `pop` / `verify`；不存在**不得** `ensure`、也不得用首次 `push` 建栈，改为写进 Executor 的 `remaining_risks` 与 Reviewer 的 `issues` / `residual_risks`，并按真源评估后 `propose` 打印申请卡，**由用户批准**才启用。「启用」与「接线」是两件事：启用**只由用户声明或批准**，接线只看栈是否存在。
- **有栈才执行栈门禁**：`verify` 必须 `exit 0`，否则不得标记阶段成功或进入下一阶段；仍应记录失败与恢复条件。无栈走真源的“有栈与无栈的适用边界”，核对已有阶段记录，不因栈缺失阻塞完成。
- **已有栈时一个 Phase 一帧**：先复用，缺失才压帧；Phase 内返工重试不另立子帧（retry 计数真源是 `progress_tracker`）。
- **独立阻塞与探索问题**按真源建子帧；非阻塞事项保持 `queued`，登记范围外事项不授予实施权限。范围内实现偏差由 Executor 在当前 Phase 内修掉。
- **有栈时收工 `retro`**：按 `campaign-work-stack/references/output-contract.md` 汇报放弃、搁置与改道；
  无新增变化可简报，有变化须说明影响与去向；无栈使用阶段记录，不假称已有栈复盘。
- 栈绑总目标（campaign），跨阶段跨窗口续用同一个，不另起。

三角色字段契约（必须输入 / 必须输出）的唯一真源是 `references/role-contract.md` §2，本 Skill 不重复定义；
受控模式的设计缺口分流及人工批准收尾规则就地定义在 `guided-goal-orchestrator/SKILL.md`，不能套用下面的普通 PASS 收尾。

FAIL 五类分流、统一纠正轮次及恢复规则在 `references/role-contract.md` §3。
每次开始/恢复循环读取该节及其引用的预算/有效进展约定；默认三次纠正，最后一轮完成评审后才判断耗尽，
不得在分支或角色切换时重复计数；无进展暂停也不能靠路由切换绕过。

失败后的通俗解释（`explain-task-failure` 的调用义务与禁止事项）在 `references/role-contract.md` §3「失败后的通俗解释」，本 Skill 不重复定义。

## PASS 推进规则

Reviewer `PASS` 后，由本 Skill 的主代理按顺序执行一次：

1. 核对该阶段的验收证据、角色输出及风险处置，确保没有未解决的当前阶段阻塞。
2. **已有栈**：先 `verify`，必须 `exit 0`；未处置登记先 `resolve`，阻塞子帧先处理。
   通过后 `pop` 当前 Phase 帧，`--note` 写 `review_id`、结论、证据与残余风险去向，检查返回码并再 `verify`；
   任一步失败都保留实际状态与恢复信息，不标记成功（`pop` 不是事务回滚，报错不代表尚未写盘）。
   **未启用栈**：不执行栈命令，检查阶段记录完整且问题已有明确处置。
3. 前述步骤成功后，才将 `progress_tracker` 的当前阶段标记为 `done`，写入时间戳、`review_id`、
   证据路径和栈收尾结果（无栈则明确“不适用”，不伪造 PASS）。
4. 返回该阶段结果和收尾证据。独立调用到此停止；有多阶段外层时交其选择下一阶段，
   外层不重复 `pop` 或更新该阶段的 retry / 完成记录。

若收尾中断，恢复时先读 `progress_tracker`、Reviewer 原文和已有帧终态/`close_note`。
只有确认是同一阶段、同一次已通过评审且栈收尾成功，才补尚未写完的进度记录；
已关闭帧不重复 `pop`，证据不匹配则停止核对，不重跑实现来掩盖收尾失败。

## 输出与记录规范

用户展示遵循 `campaign-work-stack/references/output-contract.md`；简报不减少下列记录义务。

每轮都要沉淀：

- 子代理输出原文（尤其 reviewer YAML；可另附要点，不用摘要替换原文）
- 自动化命令与关键输出
- 手工验收记录路径（建议在 `scratch/runtime/<campaign>-phaseN-manual/`）

返回结果沿用 `project-context-brief/references/task-contract.md` 的最小交接语义，
包含具体返回位置、已解锁步骤与未解决部分；在已有阶段报告中表达，不创建第二份进度真源。

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
