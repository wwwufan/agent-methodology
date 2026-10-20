# 推进栈的启用与恢复路由

判断「该不该有栈、该用哪个栈、怎么恢复、指针怎么管」时读本文件。
栈本体怎么用（schema、命令语义、硬不变量、推进树、四段回看）看 `../SKILL.md`，本文件不复述。

## 为什么启用栈是用户的决策

任务栈的价值是把「待办 + 衍生问题 + 决策」外化成文件，避免**解决完一个问题就忘了后面还有什么**。
但启用栈是有代价的：每轮要 `show`/`verify`、关帧要 `pop` 四段回看、收工要 `retro`；
用户展示按 [output-contract.md](output-contract.md) 分级，不能因此省略记录或校验。
为一个一次性小活套上这套仪式，既浪费注意力，也会把该 campaign 的复盘数据污染成噪音。

所以「该不该有栈」**不能由编排身份自动决定**：受控目标模式也可能只跑一个很小的阶段，
「你在哪个模式里」并不等于「这件事有多复杂」。用模式去预判粒度，正是
`orchestration-strength-guide.md` 反对的那种预判（该指南的立场是**粒度不可预判、只能自适应**）。

更关键的是副作用不可逆：`ensure` 一跑就落下目录与两个文件，而**新建的空栈 `verify` 是 PASS 的**
——没有任何机械信号会告诉你「这个栈本来不该存在」。因此启用栈是**用户的决策**，
本文件的职责是把该决策所需的材料结构化地摆到用户面前，而不是替他决定。

这条不靠自觉，靠脚本：新建栈时 `--activation` 缺省或传 legacy 值，`ensure` 直接 `exit 2`
且**不产生任何目录与文件**。

## 存放位置与 Git 口径

```text
workstacks/                        ← 项目内、纳入 Git
├── .gitignore                     ← */history/ 与 _current.json 不入库
├── _current.json                  ← 单栈指针（全局唯一）
└── <campaign>/
    ├── active-work-stack.json     ← 真源
    ├── active-work-stack.md       ← 脚本渲染的视图，勿手改
    ├── goal-ledger.md             ← 总目标台账（与栈同目录，一对一绑定）
    ├── phases/                    ← 阶段快照（不可变输入）
    └── history/                   ← 迁移备份，不入库
```

为什么不住在 `scratch/`：`scratch/*` 被 gitignore，且 `clean-scratch-intermediates` 只保留 `workbench`
的空目录骨架、清空其内容——跑一次就会把栈、台账与阶段快照一起删掉；`git clean -ndx` 也实测报
`Would remove scratch/workbench/<campaign>/`。而栈被契约定为「推进状态**唯一真源**」、
台账是阶段状态与门禁结论的真源，二者都不能住在一条命令就能抹掉、且抹掉后不会报警的目录里。

**提交节奏**：栈与台账在**每轮收口时**合成一个独立的 `chore(stack):` 提交，或按用户主动要求提交；
**永不与其他改动混提**。理由：栈是高频写入的状态文件，每关一帧就脏一次，混提会让「零夹带」核验失效。
同时**禁止在多个分支或多个窗口同时推进同一个栈**——JSON 合并冲突无法手工解。

## 启用规则：三个入口，全部收敛到 `ensure`

| 入口 | 动作 | `activation` |
| --- | --- | --- |
| **用户主动声明**需要任务栈 | 直接 `ensure --activation user_declared --title <核心任务名>` | `user_declared` |
| **栈已存在**（指针命中或语义命中） | 幂等接线：`ensure` → `show` → `verify`，**零提问** | 不改写 |
| 两者都不满足 | 评估复杂度 → `propose` 打印申请卡 → **用户批准才** `ensure --activation user_approved_on_proposal` | `user_approved_on_proposal` |

**任何编排身份都不得自动创建栈**，包括受控目标模式（`guided-goal-orchestrator`）与
多阶段编排（`multi-phase-plan-orchestrator`）。`auto_orchestration` 是 legacy 值：
只接受、不再新发（新建栈传它 `exit 2`），`verify` 见到给软警告，不改写历史。

### 复杂度信号表（机械可判，与编排强度指南共用同一套六维信号）

**命中 ≥2 条即建议启用**：

1. 同一总目标下待办 ≥ 2 项
2. 预计跨会话 / 跨天 / 上下文可能被压缩
3. 需要用户 ≥2 次决策（路线、口径、是否 push…）
4. 探索 / 取证性任务，推进中大概率衍生新问题
5. 有需逐条自检的完成判据（门禁 / 验收）
6. 涉及多文件或多模块改动

**反向信号**（命中即不建议启用，即便身处受控模式）：单步问答；只读查询；单一文件小改；
一句话可写清完成判据；用户已明确说不要栈。

### 申请卡（`propose`，只读）

```bash
S=<本 skill 目录>/scripts/stack.py   # <本 skill 目录> = campaign-work-stack 的 skill 根目录
python3 $S propose --campaign <id> \
  --signal "同一总目标下待办 ≥2 项" --signal "预计跨会话、上下文可能被压缩" \
  --negative "单一文件小改" --cost "<不启用的具体代价>"
```

`propose` **不创建任何目录、不写任何文件**；命中数与结论由脚本算，理由不由代理临场编话术。
申请卡必须含「**为什么需要栈**」与「**不用的代价**」两栏——用户是在为注意力成本付账，
只说「建议启用」等于让他盲签。栈已存在时它会直接说「无需申请，直接接线」。

### 用户拒绝时

1. 写进当轮交付摘要；若该 campaign 有台账，同时写进台账决策记录
2. **同一轮内不得重复申请**，只在下一个自然边界（阶段收口、交付前）重提一次
3. **没栈时不得宣称「已登记」**——改为把新问题写进 Executor 的 `remaining_risks`
   与 Reviewer 的 `issues` / `residual_risks`，并在交付摘要中逐条列出

## 恢复规则：由语义识别该用哪个栈

会话开始、上下文被压缩、换模型、跨天或跨窗口回来时，**按顺序**执行：

1. `stacks` 读全局清单 + `workstacks/_current.json` 指针
2. 指针有效（指向的栈存在、`status=open`）且与当前对话主题一致 → **直接接线，零提问**
3. 否则用**语义**匹配当前对话主题，素材 = 核心任务名 `title` + `campaign_id` + 台账总目标 + 最近帧标题
4. **命中唯一** → `use --campaign <id>` 绑定 → `ensure`（幂等接线）→ `show` + `verify`
5. **命中多个或零个** → **不得猜**，把候选列给用户选

恢复后必须**原样转达**推进树与位置指针两段，不得改写成一句概述；
**不得仅凭对话历史推断进度**——对话记忆会被压缩、被换模型、被跨天丢弃，那正是栈要消灭的失败模式。

## 单对话单栈单指针

- 一个对话**只允许绑定一个栈**；全局只有一个指针 `workstacks/_current.json`（**排除多 active 等复杂情况**）
- 切换栈是**显式动作**：`use --campaign <id>`，必须用户确认；脚本会打印「从 A 切到 B」并写进目标栈的
  `event_log`（`pointer_switched`），`retro` 可查
- 被切走的栈**保持原状**，其未关闭帧不会丢；回去再 `use` 即可
- 指针**不入库**：否则每次切换都脏 Git，多窗口还会互相覆盖。克隆后没有指针是正常的，按恢复规则重新识别
- 已全部收口（`closed`）的栈**不得**设为当前栈（`use` 会 `exit 2`）；要复用它先 `push` 新帧说明返工原因

## 多栈边界判据

| 情形 | 判定 |
| --- | --- |
| 共享同一成功标准 / 同一台账 | **同一栈，用帧**（不开新栈） |
| 目标不同、验收不同、可独立收口 | **新栈** |
| 为「换一轮对话 / 换一个阶段 Goal / 换一天」 | **禁止**开新栈 |

同一时刻可以有多个 `open` 栈，但**只有一个是指针所指的当前栈**。
每个栈内部仍是单栈顶 DFS：最多一个 `active` 帧、`depth ≤ 4`、子帧关闭后自动恢复父帧。
「同时并行推两件事」在栈内表达不出来，只能串行排 `queued` 或开子帧——这是刻意的，
因为「唯一栈顶」正是 `verify` 能机械回答「你现在在哪」的前提。

## 生命周期：代理不参与清理

- **代理不得删除任何栈**，也不得删帧或并帧凑数；清理无需代理参与
- 终态**派生而不存储**：全部帧终态 ⇒ `closed`，否则 `open`（存标志位就多一个可能失真、需额外校验的字段）
- 最后一帧 `pop` 后自动释放与该 campaign 和实际栈路径均匹配的 `_current.json`；只移除便利指针，
  不删除栈或历史，不影响其他栈的指针。后续还有 `queued` 帧时不释放。
- `stacks` 默认先列 `open`、`closed` 折叠但可查——**不清理 ≠ 看不见**，`retro` 的复盘价值必须保留
- 孤儿空栈（0 帧）会在清单里被标出，供用户自行判断是否废弃

## 命令速查

```bash
S=<本 skill 目录>/scripts/stack.py   # <本 skill 目录> = campaign-work-stack 的 skill 根目录
python3 $S stacks                                       # 只读：全局清单 + 当前指针
python3 $S propose --campaign <id> --signal … --cost …   # 只读：启用申请卡
python3 $S ensure  --campaign <id> --activation user_declared|user_approved_on_proposal --title <核心任务名>
python3 $S use     --campaign <id>                      # 设为当前栈（切换留痕）
python3 $S retitle --campaign <id> --title <核心任务名>   # 改核心任务名，campaign_id 不变
python3 $S migrate --campaign <id>                      # 从旧 scratch/workbench/ 搬迁（栈 + 台账 + phases/）
python3 $S show|survey|verify|retro --campaign <id>      # 见 ../SKILL.md
```

## 各编排身份的接线

| 身份 | 启动 / 恢复时做什么 |
| --- | --- |
| `guided-goal-orchestrator`（受控目标模式） | 先 `stacks` 探测：**已存在 → `ensure` 接线，不提问**；不存在 → `propose` 申请，未获批准不得创建、不得声称已启用；拒绝 → 写进 `remaining_risks` 并在自然边界重提。**栈绑总目标、与 `goal-ledger.md` 一对一**（从该 Skill 绝对约束 9 迁入的理由：受控模式下阶段之间的收尾工作——回写问题清单、更新台账、决定 push——恰恰发生在 Goal 释放之后，此时栈是唯一的状态载体，这正是它必须绑 campaign 而不能绑 Goal 的原因） |
| `multi-phase-plan-orchestrator`（多阶段编排） | 同上；复用当前 Phase 帧，后续阶段的 `queued` 帧正常保留；当前阶段尚未收口、前置阻塞未解决或活动归属不明时不得切换，不能仅因存在排队帧就停止 |
| `single-phase-execution-loop`（单阶段编排） | **只接线不创建**：栈存在才 `capture`/`pop`/`verify`；不存在**不得创建**，改为写 `remaining_risks`/`issues` 并按本文件评估后 `propose` 申请 |
| 直接做 / 普通对话 | 不启用；除非用户显式声明，或 `propose` 获批准 |

### 有栈与无栈的适用边界

下表中的栈动作**只在当前 campaign 已有且绑定正确的栈时执行**。未启用栈时：

- 不调用 `capture` / `push` / `resolve` / `verify` / `pop` / `retro`，不为通过门禁临时建栈。
- 主代理把角色输出、风险/问题、处置结果、验收证据和恢复条件保存到既有阶段记录
  （普通编排为 `progress_tracker` 及其引用的报告；受控编排为 `goal-ledger.md` 及评审包）。
- 收尾前检查上述记录完整、当前阶段没有未解决的阻塞、验收证据齐全；缺失则停止收尾。
  “未启用栈”不等于“没有风险”，也不能声称栈校验已通过。
- 原重试上限、阶段授权、人工审批和 Reviewer 门禁不变。有栈但文件损坏、绑定错误或校验失败时，
  必须报错，**不能伪装成无栈路径**绕过门禁。

### 状态写入的唯一责任方

上下文、诊断和探索返回的最小信息以 `project-context-brief/references/task-contract.md` 为准；
栈仅用现有 `origin` / `pointers` / `close_note` 保留位置与报告指针，不复制正文、不新增交接 schema。
恢复父帧只恢复推进位置；原阶段的成功判据、风险约束与继续权限仍由阶段负责方核对。

这里的责任方均指运行相应流程的**主代理**；Designer / Executor / Reviewer 返回报告，
不自行改推进栈、阶段状态或重试计数。每个问题按来源记录去重，内外层复用同一处置记录。

| 执行方式 | 当前阶段记录、retry、风险登记及 Phase 帧收尾 | 外层职责 |
| --- | --- | --- |
| 独立单阶段 | `single-phase-execution-loop` 的主代理 | 无外层；收尾后交还用户 |
| 多阶段中的单阶段 | 仍由内层 `single-phase-execution-loop` 的主代理负责 | `multi-phase-plan-orchestrator` 核对结果并选择下一阶段，不重复计数、登记或 `pop` |
| 受控目标编排 | `guided-goal-orchestrator` 的主代理负责台账及栈；复用角色/FAIL 契约，不执行普通单阶段的 `done` 收尾 | Reviewer PASS 仅进入 `awaiting_user_approval`；用户批准后才完成阶段并关闭 Phase 帧 |

`verify` 检查状态结构，不证明业务完成或用户批准。Phase 帧已有终态时，恢复流程先核对同一次评审、
证据和收尾记录，并重新 `verify`，只补尚未完成的记录步骤；不重复 `pop`，也不把任意 `pop` 失败当成幂等成功。
`pop` 非事务操作，失败后可能已有写盘；必须读取实际状态，成功收尾需同时检查返回码与出栈后的 `verify`。

### 通用接线动作表（仅适用于已启用栈）

| 时点 | 机械动作 | 强度 |
| --- | --- | --- |
| Executor 返回 `remaining_risks` | 阶段负责方逐条 `capture --found-in <Phase 帧> --disposition blocks\|spawns\|note`，已有同源记录则复用并补充证据 | 必须 |
| Reviewer 返回 `residual_risks` / `issues` | 阶段负责方逐条登记/复用；FAIL 归因写进记录，不由只读 Reviewer 写栈 | 必须 |
| 最后一轮评审仍 FAIL 且达到 `max_retries` | 阶段负责方登记阻塞并在项目问题台账立项；记录真实 issue 指针后按依赖顺序收口对应帧，外层不重复；不把流程停止直接等同平台 Goal blocked | 必须 |
| **阶段成功收尾前** | **`verify` 必须 `exit 0`**，且当前阶段阻塞已解决；否则不得标记成功或进入下一阶段，仍可记录失败与恢复条件 | **fail-closed 门禁** |
| 阶段成功收尾时 | 由唯一负责方 `pop` 当前 Phase 帧；普通流程在 Reviewer PASS 后，受控流程在用户批准后；记录评审/批准与证据指针 | 必须 |
| 帧的标题/判据写错、或验收口径变了 | `amend --frame <未关闭帧>`（改动自动留痕 `event_log`）；**终态帧不可改写**，要纠正就新压一帧说明返工 | 必须 |
| 全部 Phase 收工 / 计划中止 / 交付前 | `retro`（只读）→ 按输出约定汇报放弃、搁置和改道；无新增可简报，有变化须说明 | 必须 |
| **任何时点** | **不得 `ensure` / 首次 `push` 创建栈**（只接线不创建；确有需要走 `propose` 申请，用户批准才建） | **禁止** |

### `verify` 门禁与 `retro` 语义（已有栈时）

`verify` 失败意味着存在未处置的衍生登记（`pending`），或 `blocks`/`spawns` 未落到某个帧或指针。
这是**门禁而不是提醒**：先 `resolve` 干净再推进；不得跳过 `verify` 绕过。

`retro` 同理不是可选项：收工报告只讲「完成 N 个 Phase」会丢掉最贵的信息——哪些方案被放弃、
哪些被搁置、用户中途改了几次道。这三段来自只追加的 `event_log`，**推进时没留痕就复盘不出来**，
所以每一次改道与放弃都必须在发生的当时落进栈（`activate` / `pop --terminal wontfix|parked` + `--note`），
不允许事后补记。

### 栈帧与 Phase / 阶段的对应关系（已有栈时）

- **一个 Phase 一帧**：阶段负责方先按 campaign / Phase 绑定复用已有帧；确实没有时才
  `push --title "Phase N <阶段名>" --criteria <该阶段验收标准>`。外层不得再次压同一 Phase 帧。
- Phase 内的**返工重试不另立子帧**——retry 计数的真源是 `progress_tracker`，重复登记只会制造两份状态。
- 范围内的实现偏差走 FAIL 分流规则 1，由 Executor 在当前 Phase 内修掉。
- 阻塞当前阶段的独立问题可建子帧；认知缺口按 `exploration-loop` 建探索子帧，
  即使知识问题在阶段范围内，也不等同于给每次返工建帧。
- 不阻塞当前阶段的问题登记为 `queued` 后续工作，不激活、不当场展开。
  范围外事项的登记不等于实施授权；解决它需要超出原授权时，先交用户批准。
- 判定「范围内/范围外」的依据是 `execution_plan` 的当前阶段章节与 `global_constraints`；
  拿不准时按**范围外**处理（先登记，宁可多登不可漏登）。

注：上文「FAIL 分流规则 1」= `single-phase-execution-loop/references/role-contract.md` §3 的第 1 类
（实现偏差 / 修复可直接编码 → 交 Executor；retry 由该节统一计纠正轮次，分支内不再额外 +1）。

## 禁止行为

- 不得因编排身份自动 `ensure` 建栈；不得在未获用户声明或批准时创建栈
- 不得用 `push`、手写 JSON 或改 `--campaign` 绕过「创建只有 `ensure` 一个门」
- 不得在语义匹配命中多个或零个时**猜**一个栈；必须列候选让用户选
- 不得同时推进两个栈；不得未经用户确认切换指针
- 不得删除任何栈、不得把 `closed` 的栈设为当前栈
- 不得把栈与台账的提交与其他改动混提；不得在多分支 / 多窗口同时推进同一个栈
- 不得仅凭对话历史推断进度；恢复后不得省略推进树与位置指针
