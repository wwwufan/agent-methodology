# 推进栈的启用与恢复路由

判断「该不该有栈、该用哪个栈、怎么恢复、指针怎么管」时读本文件。
栈本体怎么用（schema、命令语义、硬不变量、推进树、四段回看）看 `../SKILL.md`，本文件不复述。

## 为什么启用栈是用户的决策

任务栈的价值是把「待办 + 衍生问题 + 决策」外化成文件，避免**解决完一个问题就忘了后面还有什么**。
但启用栈是有代价的：每轮要 `show`/`verify`、关帧要 `pop` 四段回看、收工要 `retro`。
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
S=<本 skill 目录>/scripts/stack.py   # <本 skill 目录> = work-queue-stack 的 skill 根目录
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
- `stacks` 默认先列 `open`、`closed` 折叠但可查——**不清理 ≠ 看不见**，`retro` 的复盘价值必须保留
- 孤儿空栈（0 帧）会在清单里被标出，供用户自行判断是否废弃

## 命令速查

```bash
S=<本 skill 目录>/scripts/stack.py   # <本 skill 目录> = work-queue-stack 的 skill 根目录
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
| `guided-goal-orchestrator`（受控目标模式） | 先 `stacks` 探测：**已存在 → `ensure` 接线，不提问**；不存在 → `propose` 申请，未获批准不得创建、不得声称已启用；拒绝 → 写进 `remaining_risks` 并在自然边界重提 |
| `multi-phase-plan-orchestrator`（多阶段编排） | 同上；且若存在**未关闭帧**，先报告并请示收口或 `parked`，不得在未收口的栈上直接开新阶段 |
| `single-phase-execution-loop`（单阶段编排） | **只接线不创建**：栈存在才 `capture`/`pop`/`verify`；不存在**不得创建**，改为写 `remaining_risks`/`issues` 并按本文件评估后 `propose` 申请 |
| 直接做 / 普通对话 | 不启用；除非用户显式声明，或 `propose` 获批准 |

## 禁止行为

- 不得因编排身份自动 `ensure` 建栈；不得在未获用户声明或批准时创建栈
- 不得用 `push`、手写 JSON 或改 `--campaign` 绕过「创建只有 `ensure` 一个门」
- 不得在语义匹配命中多个或零个时**猜**一个栈；必须列候选让用户选
- 不得同时推进两个栈；不得未经用户确认切换指针
- 不得删除任何栈、不得把 `closed` 的栈设为当前栈
- 不得把栈与台账的提交与其他改动混提；不得在多分支 / 多窗口同时推进同一个栈
- 不得仅凭对话历史推断进度；恢复后不得省略推进树与位置指针
