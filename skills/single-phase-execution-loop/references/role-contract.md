# 三角色字段契约与 FAIL 分流（唯一真源）

## §1 真源声明

本文件是 **Designer / Executor / Reviewer 三角色的输入输出字段契约**与 **FAIL 分流规则**的**唯一真源**。

- `single-phase-execution-loop/SKILL.md` 的标准循环只保留「调用条件 / 决策」骨架，字段清单一律引用本文件。
- `guided-goal-orchestrator/SKILL.md` 在受控模式下复用本文件，在 FAIL 分流中覆盖「设计缺口」一项
  （阶段方案是用户批准的**不可变快照**，Designer 无权改动，故设计缺口必须停止并回计划模式，
  不得由 Designer 自行重设计）；阶段完成与用户批准仍按受控 Skill 自己的收尾流程，不套用普通阶段的 `done`。
- 两处若出现字段定义冲突，**以本文件为准**，并修正引用侧。

> 注：下文 §2 / §3 的「见「推进栈接线」」
> 指的是接线规则的真源 `campaign-work-stack/references/activation-and-recovery.md`「各编排身份的接线」，
> 以及 `single-phase-execution-loop/SKILL.md` 的同名覆盖项小节。

## §2 三角色字段契约

`phase_authorization` 必须注明实际授权来源及当前阶段边界：普通流程为单/多阶段执行授权；
受控流程为用户批准当前阶段方案及创建该阶段 Goal，不把受控调用误写成普通自动编排授权。

### 三角色共同输入与返回语义

组装角色输入、消费角色报告时，主代理读取 `project-context-brief/references/task-contract.md`，
按其中的最小输入与交接语义复用既有材料；这不是强制调用上下文 Skill，也不新增独立任务表单。
三角色收到同一份当前任务要求及可读取的来源，尤其包括用途、必须满足的质量/风险约束、
明确暂缓项、当前成功判据和授权边界。后续角色不能只继承上一角色的方案而丢失原要求。
角色可先定向读取补齐可查事实；确实影响下一步的未知才阻断，不要求理解所有项目知识。

- Designer 在 `recommended_design` 说明方案如何匹配当前质量要求；建议与必须完成项分开，
  不按熟悉度或未来可能性追加工程目标。确认涉及质量/成本/风险的实质取舍后才改变方案。
- Executor 按相同要求实施并在 `validation` 给证据，不擅自增减范围或标准。
- Reviewer 的 `checks` 对照原要求，而不只核对 Designer 的建议；FAIL 的 `issues` 需指出违反的要求、
  影响及证据。纯可选的未来能力缺失不构成 FAIL；必要风险和关键未验证项仍阻断通过。
- 质量要求缺失时先复用适用项目约束和已有验收；冲突或关键取舍待确认时返回对应停止状态，
  不能由角色自行决定提高/降低标准，受控快照变更仍走人工审批。

最小交接信息放进既有字段，不增加输出标题或 Reviewer YAML 字段：
Designer 用 `problem_understanding` / `executor_instructions` / `open_questions`，
Executor 用 `implementation_summary` / `validation` / `remaining_risks`，
Reviewer 用 `review_subject` / `checks` / `issues` / `fix_instructions` / `residual_risks`。
主代理保留原任务/阶段/帧绑定，核对证据适用范围、剩余阻塞与下一步权限后再调度；
报告中的“可继续”建议不替代授权，Reviewer PASS 仍按相应编排的收尾门禁处理。

### Designer（Step 0）

必须输入：

- `phase_authorization`：当前阶段的实际授权（见本节说明）
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

- `phase_authorization`：当前阶段的实际授权（见本节说明）
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
- `remaining_risks`（逐条返回；由主代理按有栈/无栈路径登记处置，见「推进栈接线」；角色不直接写栈或进度）

### Reviewer（Step 2）

必须输入：

- `phase_authorization`：当前阶段的实际授权（见本节说明）
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

Reviewer 返回的 `residual_risks` 与 `issues` 由主代理逐条处置：有栈时登记/复用 capture，
无栈时保存在阶段记录；`verdict: FAIL` 的归因和证据也一并留存。Reviewer 保持只读，
不自行改栈、retry 或阶段状态；内外层不重复记录同一来源的问题。

## §3 FAIL 分流规则（核心）

Reviewer 为 `FAIL` 时，主代理按类型分流：

### 纠正轮次与恢复

当前阶段的 FAIL 分流及 retry 记录只由阶段负责方处理一次（普通流程为内层单阶段，受控流程为受控编排）。
`retry` 表示 **Reviewer FAIL 后已启动的阶段纠正轮次**，不再只计代码修复。
首次执行及评审是第 0 轮；`max_retries` 默认 3，明确配置优先，即默认最多首次执行加三轮纠正。

- 收到 FAIL，先核对授权、预算、暂停及无进展门禁。允许继续且 `retry < max_retries` 时，
  在启动纠正前把 `retry + 1` 写入原阶段记录，关联来源 `review_id`、所选路线及本轮证据。
- 一轮从该 FAIL 的纠正启动到下一次 Reviewer 结论；期间修复、重设计、取证、
  探索及返回均属于同一轮，切换路线或多次调用角色不再加 retry。每个实验另计自己的预算。
- `retry == max_retries` 时，**已启动的最后一轮仍可实施、取证并完成评审**；
  其他停止门禁仍有效。该轮 PASS 可正常收尾；仍 FAIL 则停止，不启动下一轮。
  不在角色调用前仅因数字达到上限就取消尚未结束的最后一轮。
- 收到 FAIL 但因审批、外部条件或用户暂停尚不能启动纠正时，只记录停止原因，不先消耗一轮。
  独立探索或首次评审之前的探索不凭空创建阶段 retry。
- 恢复时读取原进度、来源 FAIL、角色报告及本轮是否已启动/评审结束；同一轮续跑不重复计数。
  普通模式用 `progress_tracker` 及报告，受控模式用原台账及报告；不新增计数文件、栈 schema 或 Reviewer 字段。
- 旧记录保留原值和证据；有可靠历史才补充口径说明。无法确定已启动轮次时先核对并确认继续额度，
  不清零、不伪造历史，也不通过换角色、换帧、换窗口、诊断或计划版本变化自动刷新上限。
  用户批准额外额度时记录新上限及依据，累计值仍保留。

运行或恢复纠正循环时同时读取 `exploration-loop/references/budget-and-progress.md`，
按其中规则识别有效进展并处理默认连续两轮无进展暂停；新证据不自动恢复已耗尽的预算或重试额度。
该暂停不自动等同于平台 Goal 的 `blocked`。

### 路由（计数统一按上节，不在分支内重复增加）

1. **实现偏差 / 修复可直接编码**
   - 现象：校验缺口、边界 case 漏测、逻辑遗漏、配置约束未落实、回归 bug
   - 动作：调用 **executor**，并传入 `fix_instructions`

2. **设计缺口 / 方案不成立 / 影响面遗漏**
   - 现象：当前方案本身矛盾、边界定义错误、全局约束冲突、需重选技术路径
   - 动作：返回 **designer** 重新设计（带上 reviewer 问题）

3. **证据缺失（代码基本通过但验收证据不全）**
   - 现象：自动化通过，但缺 staging 手工验收、缺运行记录、缺外部依赖验证证据
   - 动作：调用 **executor** 执行“验收取证任务”（可不改代码），补齐证据后再 reviewer

4. **认知缺口 / 未知根因 / 需实测选路**
   - 现象：继续修复或重设计只能猜测；同时存在多个可能根因；可行性或技术路线必须通过实验区分
   - 动作：暂停原实现路线，调用 `exploration-loop` 运行“假设 → 最小区分实验 → 证据 → 决策”；
     若由 FAIL 发起，该探索属于已计数的本轮纠正，实验和返回不额外增加阶段 `retry`
   - 栈动作：已有栈时 `capture --disposition blocks`，建探索子帧并激活；没有栈时不因探索自动创建
   - 返回：证据指向实现偏差 → Executor；推翻设计 → Designer；需价值、成本或风险取舍 → 用户；预算耗尽仍无结论 → `parked` / blocked
   - 受控目标模式下，探索结论若要求改动已批准快照，仍必须停止并回计划模式，不得由 Designer 自行改写

5. **达到最大重试**
   - 条件：本轮 Reviewer 仍为 FAIL，且 `retry >= max_retries`；不是“最后一轮刚启动就停止”
   - 动作：停止循环，向用户报告阻塞项与建议
   - 记录：在项目问题台账立项，保存真实 issue 指针、失败证据及恢复条件，不用占位编号冒充已立项。
     有栈时按依赖顺序收口阻塞帧并留 issue 指针；无栈时写入既有阶段记录，不运行栈命令。
     无法完成立项时明确报告并保留已有记录，不能宣称已升级完成。**阻塞项不得只留在对话里**。

> 受控目标模式（`guided-goal-orchestrator/SKILL.md`）**覆盖**第 2 条：设计缺口 → 停止 →
> 标 `plan_change_requested` → 回计划模式，不得由 Designer 自行重设计。覆盖项与理由就地写在该 SKILL.md 内。

### 失败后的通俗解释

Reviewer `FAIL`、阶段 `blocked`、无进展暂停、重试耗尽仍失败，或不可恢复的验收命令失败后，
调用 `explain-task-failure` 生成说明，再决定是否进入下一轮。按
`campaign-work-stack/references/output-contract.md` 分级展示，保留原因、通过/未通过部分、
影响、证据、剩余额度和下一步；术语与日常例子按理解需要提供。
不得替代 Reviewer YAML、改变 retry 计数或把 FAIL 改写成 PASS。

若仍可重试，先展示简短解释，再传递技术 `fix_instructions`；
若重试耗尽仍失败、无进展暂停或 blocked，则停止相关自动尝试，交还 blocker、证据和恢复条件。

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
