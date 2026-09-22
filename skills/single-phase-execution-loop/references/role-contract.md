# 三角色字段契约与 FAIL 分流（唯一真源）

## §1 真源声明

本文件是 **Designer / Executor / Reviewer 三角色的输入输出字段契约**与 **FAIL 分流规则**的**唯一真源**。

- `single-phase-execution-loop/SKILL.md` 的标准循环只保留「调用条件 / 决策」骨架，字段清单一律引用本文件。
- `guided-goal-orchestrator/SKILL.md` 在受控模式下复用本文件，**只覆盖**「设计缺口分流」一项
  （阶段方案是用户批准的**不可变快照**，Designer 无权改动，故设计缺口必须停止并回计划模式，
  不得由 Designer 自行重设计）；覆盖表与「禁止把授权强度参数化」的理由就地写在该 SKILL.md 内。
- 两处若出现字段定义冲突，**以本文件为准**，并修正引用侧。

> 注：下文 §2 / §3 是从 `single-phase-execution-loop/SKILL.md` 逐字搬运的原文，其中「见「推进栈接线」」
> 指的是接线规则的真源 `work-queue-stack/references/activation-and-recovery.md`「各编排身份的接线」，
> 以及 `single-phase-execution-loop/SKILL.md` 的同名覆盖项小节。

## §2 三角色字段契约

### Designer（Step 0）

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

### Executor（Step 1）

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

### Reviewer（Step 2）

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

## §3 FAIL 分流规则（核心）

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

> 受控目标模式（`guided-goal-orchestrator/SKILL.md`）**覆盖**第 2 条：设计缺口 → 停止 →
> 标 `plan_change_requested` → 回计划模式，不得由 Designer 自行重设计。覆盖项与理由就地写在该 SKILL.md 内。

### 失败后的通俗解释

Reviewer `FAIL`、阶段 `blocked`、达到 `max_retries`，或不可恢复的验收命令失败后，调用 `explain-task-failure` 生成面向用户的说明，再决定是否进入下一轮。该说明必须包含失败原因、已通过/未通过部分、影响范围、术语翻译和一个对应的日常例子；不得替代 Reviewer YAML、改变 retry 计数或把 FAIL 改写成 PASS。

若仍可重试，先给用户展示简短解释，再把 Reviewer 的技术 `fix_instructions` 传给 Executor；若达到最大重试或 blocked，则停止自动推进，并把解释中的 blocker、证据和下一步交还用户。

## §4 规范标题锚块（`doctor.py` 第 13 组消费）

下面这个 HTML 注释块是**机器可读的字段名全集**：`doctor.py` 第 13 组解析它，并断言
`templates/codex-agents/*.toml` 与 `templates/cursor-agents/*.md` 六个角色模板里对应角色的字段名全部在位，
且 codex 模板的字段枚举与本锚块**双向一致**。模板是运行时快照（渲染进项目后必须脱离本仓库独立生效），
语义真源在本文件与 §2；改任一侧都会让第 13 组变红。

<!-- role-headings-canonical
designer: design_status problem_understanding entrypoints_and_flow impact_surface root_cause_or_design_boundary options recommended_design executor_instructions validation_strategy reviewer_focus open_questions
executor: implementation_summary changed_surface validation remaining_risks
reviewer: review_id review_subject verdict checks issues fix_instructions residual_risks
-->
