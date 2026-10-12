---
name: campaign-work-stack
description: >-
  用文件化推进栈管理一个总目标（campaign）下的多个待办：衍生新问题先登记再决定，
  survey 统一呈现「当前推进栈 + 长期待办池」；并负责推进栈的启用与恢复路由（评估申请、语义识栈、
  维护「一个对话一个栈」唯一指针），栈绑总目标、跨轮跨窗口续用。
  当用户问「还剩什么 / 我们做到哪了 / 别丢了 / 接下来做什么 / 用哪个栈 / 要不要建栈」、
  提到「工作计划 / 下一步做什么 / 问题清单」、要求「复盘 / 回看弯路 / 为什么改了主意 / 修订判据」、
  需要把需求分解成任务树、会话可能被压缩/换模型/跨天中断需要交接，或任何编排 skill 启动恢复时使用。
  不用于单步问答；不替代 guided-goal-orchestrator 的阶段门禁编排，
  也不替代 single-phase-execution-loop 的三角色循环。
---

# 总目标推进栈

## 要解决的失败模式

推进一个总目标时常同时有多个待办（例如 ①②③）。推进 ① 时会衍生出新问题；一旦当场展开，思路被带走，
① 做完时 ②③ 与衍生项全都只存在于对话记忆里。而对话记忆会被压缩、被换模型、被跨天丢弃
——于是「解决完一个问题，就完全忘了之后该怎么办」。

本 Skill 把推进状态外化成文件，并把三条纪律做成**脚本的机械动作**，而不是依赖自觉：

| 纪律 | 由谁强制 |
| --- | --- |
| 新工作开始前先摊开已有推进栈 | `show`；且 `push` / `activate` / `pop` 都会自动附带全栈输出 |
| 衍生问题先登记、再决定，不当场展开 | `capture`；`verify` 把未处置登记判为**硬违规** |
| 关掉一帧时必须回看剩余与下一步 | `pop` **自动打印**四段回看，无法跳过 |

## 绑定对象与启用策略

**一个 campaign 一个栈；栈与总目标台账 `workstacks/<campaign>/goal-ledger.md` 一对一绑定（同目录）。**

绑定对象**不是**轮次、**不是**对话窗口、**不是**阶段 Goal：

| 候选绑定 | 为什么不用 |
| --- | --- |
| 阶段 Goal | Goal 是独占、串行、不可暂停资源，一阶段一个、收口即释放。而阶段之间的收尾工作（回写问题清单、更新台账、决定 push）恰恰发生在 **Goal 释放之后** —— 绑 Goal 会在最该留状态的时候把栈丢掉 |
| phase | 装不下跨阶段的帧（如「把编排契约改动 commit」），也装不下不属于任何阶段的工具自建帧 |
| 轮次 / 对话窗口 | 一轮的边界只存在于用户脑子里，跨窗口即断；绑上去等于每换一次窗口丢一次状态 —— 那正是本 Skill 要消灭的失败模式 |
| **campaign（总目标）** | 唯一能横跨多 Goal、多 phase、多会话、跨天的稳定标识，且与台账同目录同名 → **采用** |

所以**栈跨轮续用**：同一总目标下的第二轮、第三轮继续往同一个栈压帧，`retro` 复盘的是整个
campaign 的弯路而不是单轮。文中「一轮」指**你一次连续推进的意图**（`survey` 选事 → 推到收口），
它是叙述单位、**不是**栈的容器边界；schema 里没有 round 层，也刻意不加。

### 启用与恢复路由

**栈不按编排身份自动启用。**「你在哪个模式里」不等于「这件事有多复杂」——受控目标模式也可能只跑一个
很小的阶段；而 `ensure` 一跑就落下目录与两个文件，且**新建的空栈 `verify` 是 PASS 的**，
没有任何机械信号会告诉你「这个栈本来不该存在」。所以启用是**用户的决策**，本 Skill 的职责是把决策材料
结构化地摆到用户面前。三个入口全部收敛到 `ensure`：

| 入口 | 动作 | `activation` |
| --- | --- | --- |
| **用户主动声明**需要任务栈 | `ensure --activation user_declared --title <核心任务名>` | `user_declared` |
| **栈已存在**（指针命中或语义命中） | 幂等接线：`ensure` → `show` → `verify`，**零提问** | 不改写 |
| 两者都不满足 | 六维信号评估（命中 ≥2 即建议）→ `propose` 打印申请卡 → **用户批准才** `ensure --activation user_approved_on_proposal` | `user_approved_on_proposal` |

**任何编排身份都不得自动创建栈**，包括受控目标模式与多阶段编排。这条不靠自觉：新建栈时
`--activation` 缺省、或传 legacy 值 `auto_orchestration`，`ensure` 直接 `exit 2` 且**不产生任何目录与文件**。
`auto_orchestration` 只作为历史值被接受（`verify` 见到给软警告，不改写历史）。

`ensure` 对**已存在**的栈是幂等的：只补 `bound_ledger`、回显栈顶，**不新建、不改 `activation`、不动任何帧**，
所以「接线」这一步任何身份都可以无条件调用，不会因为重复调用而制造出第二个栈。
**「启用」与「接线」是两件事，别混**：启用 = 创建栈（唯一入口 `ensure`，受上表约束）；
接线 = 栈已存在时 `capture` 衍生、`pop` 关帧、`verify` 门禁（只要栈存在就做，与谁启用无关）。

**恢复**（会话被压缩、换模型、跨天或跨窗口回来）按顺序：① `stacks` 读全局清单 +
`workstacks/_current.json` 指针 → ② 指针有效（栈存在、`status=open`）且与当前对话主题一致则
**直接接线、零提问** → ③ 否则用**语义**匹配，素材 = 核心任务名 `title` + `campaign_id` +
台账总目标 + 最近帧标题 → ④ **命中唯一**才 `use --campaign <id>` 绑定并 `ensure` 接线 →
⑤ **命中多个或零个不得猜**，列候选由用户选。

**一个对话只允许一个栈**，全局只有一个指针 `_current.json`（**不入库**：否则每次切换都脏 Git、
多窗口还会互相覆盖）。切换栈是显式动作，须用户确认，脚本打印「从 A 切到 B」并写 `pointer_switched` 事件；
已全部收口（`closed`）的栈不得设为当前栈。多栈边界：**共享同一成功标准/台账 → 同一栈用帧**；
目标不同、验收不同、可独立收口 → 新栈；**禁止**为「换一轮对话 / 换一个阶段 Goal / 换一天」开新栈。
生命周期：**代理不得删除任何栈**；终态**派生而不存储**（全部帧终态 ⇒ `closed`）。

复杂度信号表、申请卡格式、用户拒绝时的留痕规则、各编排身份的接线动作见
[references/activation-and-recovery.md](references/activation-and-recovery.md)
——**开始一项新工作前、或需要判断「该不该有栈 / 该用哪个栈」时读**。

## 真源边界（不得造平行真源）

| 内容 | 真源 | 本 Skill 的角色 |
| --- | --- | --- |
| 跨轮次缺陷、根因、完成标准 | `docs/operations/issues.md` | 只存 `ISS-0xx` 指针 |
| 阶段状态、Goal 绑定、门禁结论 | `workstacks/<campaign>/goal-ledger.md` | **栈与它一对一绑定**（`bound_ledger`，同目录），但只存指针、不复制正文 |
| 长期计划与验收标准 | `docs/operations/next-work-plan.md` | `survey` 只读抽索引 |
| **推进栈（campaign 级）：待办、衍生、回看** | **`active-work-stack.json`** | **唯一真源** |

栈文件只存「推进状态 + 指针」，**不复制**上述文件的正文。被判定为跨轮次缺陷的衍生项，
动作是升级到 `issues.md` 立项，栈里改为 `escalated` 并留 `ISS-0xx` 指针。

「选下一件事」与「把选定的事推到底」都在本 Skill 内：`survey` 负责选（读长期池给菜单），
栈负责推（`push` → `pop` 不丢帧）。原 `next-work-plan` skill 的职责已被 `survey` 吸收并删除，
但它读取的两个长期真源文档**原样保留**——`survey` 只抽索引，不把正文搬进栈。
阶段内 Designer → Executor → Reviewer 仍走 `single-phase-execution-loop`。当前帧因可行性、未知根因或
候选技术路线缺少证据而无法可靠继续时，以 `exploration-loop` 作为该帧或阻塞子帧的临时执行协议。
本 Skill 只保存推进状态与指针，不介入角色委托，也不代替用户做阶段批准或跨阶段推进决策。

## 命令

真源 `active-work-stack.json` 与派生视图 `active-work-stack.md`（脚本渲染，**勿手改**）位于
**`workstacks/<campaign>/`**，并**纳入 Git**。

为什么不住在 `scratch/`：`scratch/*` 被 gitignore，且 `clean-scratch-intermediates` 的
`KEEP_EMPTY_DIRECTORIES` 只保留 `workbench` 的空目录骨架、清空其内容——跑一次那个「清理可重建
中间内容」的 skill 就会把栈、台账与阶段快照一起删掉；`git clean -ndx` 也实测报
`Would remove scratch/workbench/<campaign>/`。而本 Skill 的真源边界表把栈定为「推进状态**唯一真源**」，
真源不能住在一条命令就能抹掉、且抹掉后不会报警的目录里。

总目标台账 `goal-ledger.md` 与阶段快照 `phases/` 已随栈一起迁入 `workstacks/<campaign>/`，与栈**同目录**
（`bound_ledger` 因此是同目录相对路径）；`verify` 的绑定检查按仓库根解析，仍然 fail-closed。
旧位置的栈必须先 `migrate` 搬迁（`migrate` 连台账与 `phases/` 一起搬，并在台账头部**追加**一条迁移说明，
**不改写任何历史条目里的旧路径**）：**未搬迁时任何命令都 `exit 2` 拒绝**，
防止在新位置另起一个空栈造成分叉（帧进新栈、真栈一帧未动，而两边 `verify` 都 PASS）。

所有写操作走脚本（只用标准库）：

```bash
# <本 skill 目录> = 装着本 SKILL.md 的 skill 根目录（仓库 skills/、全局 ~/.codex/skills/、项目 .agents/skills/ 之一）
S=<本 skill 目录>/scripts/stack.py
python3 $S stacks                                        # 只读：全局栈清单 + 当前指针（多栈视图）
python3 $S propose  --campaign <id> --signal … [--negative …] [--cost …]
                                          # 只读：打印「启用申请卡」，不创建任何文件
python3 $S ensure   --campaign <id> --activation user_declared|user_approved_on_proposal [--title <核心任务名>]
                                          # 幂等启用+绑定台账；**新建栈时 --activation 必填且不得为 legacy**
python3 $S use      --campaign <id>       # 设为当前栈（单对话单栈单指针，切换留痕）
python3 $S retitle  --campaign <id> --title <核心任务名>   # 改核心任务名，campaign_id 不变
python3 $S survey   --campaign <id> [--commands]   # 先看当前栈，再看长期池（只读）
python3 $S show     --campaign <id>          # 回显全栈
python3 $S push     --campaign <id> --title … [--goal …] [--criteria …]… [--parent F-00x] [--activate]
                                          # 压一帧；**栈不存在时 exit 2，不会静默新建**
python3 $S activate --campaign <id> --frame F-00x
python3 $S capture  --campaign <id> --text … [--found-in F-00x] [--disposition blocks|spawns|note]
python3 $S resolve  --campaign <id> --capture C-00x --disposition … [--frame F-00y | --pointer ISS-0zz]
python3 $S pop      --campaign <id> --frame F-00x --terminal done|parked|escalated|wontfix --note …
python3 $S amend    --campaign <id> --frame F-00x [--title …] [--goal …] [--origin …] [--criteria …]… [--pointers '{…}']
python3 $S retro    --campaign <id> [--tail 20]   # 弯路复盘（只读）
python3 $S verify   --campaign <id>          # 硬违规 exit 1
python3 $S render   --campaign <id> [--check]
python3 $S migrate  --campaign <id>          # 把旧位置 scratch/workbench/<id>/ 的栈（及台账与 phases/）迁到 workstacks/<id>/
```

每条命令都可用 `--path <active-work-stack.json>` 替代 `--campaign`，用于把栈放在
`workstacks/` 之外（例如临时验证栈）。`--path` 必须指向 **`.json` 栈文件本身**，
不是它所在的目录；误传目录时脚本会自动补成 `<目录>/active-work-stack.json` 并在 stderr 提示。
跨仓库时用 `--repo-root` 指定根目录。

**创建栈只有一个门：`ensure`。** `push` 在栈文件不存在时 `exit 2`，并用 `difflib` 给出
「你是不是想找 `<近似 campaign>`？」的提示。理由：静默新建会造成**栈分叉**——`--campaign` 打错一个字母，
帧就压进了另一个目录的空栈，真栈一帧未动，而 `verify` 对那个新栈照样 PASS，没人会发现
（v2 时期 `push` 就是这样建栈的，实测 `ui-image-system-recogntion` 少一个 `i` 即分叉）。
`survey` 是唯一容忍无栈的命令（它本来就是「先看有什么可做」的选单，只打印提示、不创建）。

Schema、状态机、不变量清单与排错见 [references/stack-schema.md](references/stack-schema.md)
（需要手工核对 JSON、扩展字段或排查 `verify` 失败时读）。

该用多强的编排（直接做 / 只用栈 / 单阶段门禁 / 多阶段自动 / 多阶段受控）见
[references/orchestration-strength-guide.md](references/orchestration-strength-guide.md)
——`survey` 选出大事后、决定编排强度时读。核心立场是**粒度不可预判、只能自适应**：
总是先上栈（免费无损），只在出现指南信号表里的具体信号时才升级编排强度；
升级路径单向便宜（栈 → 单阶段 → 多阶段），降级很贵（Goal 与不可变快照退不回去）。

## 推进树与位置指针

`show`（以及 `push` / `activate` / `pop` 的自动附带输出）会先打印一棵**推进树**，
再打印**位置指针**。回答用户「我们做到哪了 / 还剩什么 / 现在在哪个子任务」时，
**原样转达这两段**，不要改写成一句概述。

```text
├─ [F-001] ✓ done          写 skill
├─ [F-002] ○ 待办          ISS-021 回写
│  └─ [F-010] ● 正在做     子任务　◀━━ 当前位置
└─ [F-003] ○ 待办          补台账

当前位置：F-010 · 子任务（depth 1）
推进路径：F-002 ISS-021 回写 ▸ F-010 子任务
会自动恢复：F-002 · ISS-021 回写（当前帧关闭后回到它，不用你记）
进度：已关闭 1/4 帧（25%）｜未关闭 3｜当前 depth 1｜栈深上限 4
```

- 树里**包含已关闭帧**（`✓ done` / `⏸ parked` / `↑ escalated` / `✗ wontfix`），
  整轮做过什么一目了然，不会因为关闭就从视野里消失。
- `◀━━ 当前位置` 标出唯一 `active` 帧；`推进路径` 是从根帧到它的完整链路，
  等价于 DFS 调用栈——**这一段就是「现在推进到哪一个子任务」的权威答案**。
- `会自动恢复` 指出关掉当前帧后会回到哪个被打断的祖先帧，无需人工记忆。
- 终端对齐按东亚全角宽度计算（`_dwidth`），中文标题不会错位。

## 五个强制时点

### 1. 开工前 · 先摊开再压栈

每轮开始或用户选定要做的事时：先跑 **`survey`**——它会先回显当前栈（含推进树与位置指针），
再列出长期池菜单，并标出哪些池条目**已经在栈里**（防止重复压栈）。
只有当前栈里的未关闭帧确认收口或显式 `parked` 后，才从长期池挑新的大事压进来。
该 campaign 还没有栈时，先按「启用与恢复路由」走：用户已声明 → `ensure --activation user_declared`；
否则 `propose` 打印申请卡，**用户批准后才 `ensure`**，再压第一帧。
栈文件已存在但只需看栈时，用 `show` 即可，并**把全栈原样回显给用户**，再压新帧。
新帧压栈后其余未关闭帧保持 `queued`，并明确告知用户「这些是挂起，不是丢弃」。

### 2. 执行中 · 发现即登记，登记后才决定

每发现一个新问题，**先 `capture`，再决定处置**：

| disposition | 含义 | 后续动作 |
| --- | --- | --- |
| `blocks` | 不解决就无法完成当前帧 | `push --parent <栈顶> --activate` 建子帧；关掉子帧后父帧自动恢复 |
| `spawns` | 是真问题但不阻塞当前帧 | `push` 成 `queued` 帧，**不当场展开** |
| `note` | 不是独立问题 | `resolve --pointer` 写明归属（例如「是 ISS-007 的新证据」） |

拿不准就先用默认 `pending` 登记，但 **`pending` 会让 `verify` 失败**，收工前必须 `resolve`。
**禁止未登记就顺手展开一个新问题**——这正是「推进第一个问题时被带走」的成因；只有 `blocks` 允许打断当前帧。

#### 认知型阻塞的帧级路由

任务栈是状态容器，不把 campaign 全局标记为「探索项目」。每次阻塞按当前帧分流：

| 当前情况 | 执行协议 | 栈动作 |
| --- | --- | --- |
| 方案明确，只是实现偏差 | 普通执行或 `single-phase-execution-loop` | 留在当前帧 |
| 可行性、根因或技术路线缺证据 | `exploration-loop` | `capture blocks` → 探索子帧 `--activate` |
| 需要成本、风险或“够好”的判断 | 用户决策 | 保留当前帧与选项，不以实验代替价值判断 |
| 缺权限、数据或外部系统 | blocked / escalated | 登记阻塞证据与恢复条件 |

探索子帧只回答一个知识问题；关闭后由栈自动恢复父执行帧。
探索循环不构成新建栈或扩大原任务授权的理由；没有栈时仍按本 Skill 的启用规则走 `propose`。

### 3. 收工时 · pop 自动回看四段

`pop` 会打印下列四段。原样转达给用户，**不要省略第 3、4 段**：

1. **本帧结论**：做了什么、完成判据逐条自检、证据指针
2. **本帧衍生**：这一帧期间 `capture` 的全部条目及其去向（立帧 / 升级 ISS / 仅记录）
3. **栈剩余**：还有哪些帧、各自深度与状态
4. **下一步**：建议推进哪一帧，以及需要用户发送的准确指令

### 4. 中断恢复

会话被压缩、换模型或隔天回来时：**先 `show` + `verify`**，找到 `active` 帧，报告它的完成判据
与已达成部分，再请用户确认继续还是换帧。**不得仅凭对话历史推断进度**。

### 5. 换轮 / 交付前 · `retro` 复盘弯路

一段推进收工、准备交付、或用户问「我们走了哪些弯路」时跑 **`retro`**（只读，不改栈）：
它按 `wontfix` / `parked` / `escalated` / `done` 分组列出终态帧及其 `close_note`，
并统计**用户方向切换次数**、DFS 自动抢占次数、衍生问题去向分布、栈深峰值与帧修订次数。

原样转达「放弃的方案」「明确搁置」「用户方向切换」三段，**不要只报完成率**：
放弃和改道才是下一轮最该避免的重复成本。`retro` 的数据来自 `event_log`（只追加的时间线），
因此**推进过程中不许事后补记**——没有留痕的历史，复盘时会如实声明不完整，不假装拥有。

修订未关闭帧用 **`amend`**（标题写错了、判据要改、来源要补）：改动自动写进 `event_log`，
`retro` 能看到「这一帧改过几次、改了什么」。**终态帧不可修订**（exit 2）——
`done`/`parked`/`escalated`/`wontfix` 是历史；要纠正已关闭帧的结论，新压一帧说明返工原因，
让返工留在树里可查，而不是把旧帧改写成「其实早就对了」。

## 硬不变量（`verify` 机械检查）

- 未关闭帧中最多一个 `active`；`suspended` 必须是 `active` 的祖先（挂起来路可追）
- 帧只能以 `done` / `parked` / `escalated` / `wontfix` 四种终态离栈，且必须带 `close_note`
  并写入 `pop_log`——**`queued` 帧不得静默消失**
- `capture` 不得停留 `pending`；`blocks` / `spawns` 必须已落到某个帧或指针
- `parent` / `spawned` 指针存在，`depth` 与父帧自洽，栈深 ≤ 4
- **绑定自洽**：`activation` 取值合法；`bound_ledger` 指向的台账必须存在（不存在 = 绑定已断，硬违规），
  且台账正文的 `campaign_id` 必须与栈一致（不一致 = 硬违规）；台账缺失或解析不到 `campaign_id` 时只给软警告并
  **如实声明未校验**，不假装绑过
- **单栈指针**：`workstacks/_current.json` 指向的栈必须存在；指向已 `closed` 的栈 = **硬违规**（指针失效），
  指向别的 campaign = 软警告（一个对话只允许一个栈，切换用 `use`，不要手改指针文件）
- `event_log` 存在且 `seq` 为连续的 1..N（缺号即判违规：事件只允许追加，不许删改），
  `kind` / `actor` 取值合法；由 v1 迁移来的栈只给软警告并声明历史不完整
- Markdown 视图必须与 JSON 真源一致（`render --check`）

## 禁止行为

- 不手改 `active-work-stack.json` 或 `.md` 视图；一切变更走脚本，否则 `verify` 与 `render --check` 失去意义
- 不把栈绑到轮次、对话窗口或阶段 Goal 上；换窗口 / 换阶段 / 开新一轮都**续用同一个 campaign 栈**，不得另起一个
- 不在未获用户声明或批准时创建栈：**任何身份都不得自动 `ensure` 建栈**（含受控目标模式与多阶段编排）；
  认为确有需要时先 `propose` 打印申请卡，由用户批准。被拒后同一轮不得重复申请，且**没栈时不得宣称「已登记」**
- 不删除任何栈，也不把 `closed` 的栈设为当前栈；不在多分支 / 多窗口同时推进同一个栈
- 不把栈与台账的提交和其他改动混提：收口时合成一个独立的 `chore(stack):` 提交，或按用户主动要求提交
- 不用 `push`、手写 JSON 或改 `--campaign` 绕过「创建只有 `ensure` 一个门」；`push` 报 exit 2 并提示近似 id 时，
  正确动作是**核对 campaign 拼写**，不是换一个 id 让它建出新栈
- 不把 `issues.md` / 台账的正文复制进栈文件
- 不因「栈快满了」而删帧或并帧凑数；应 `parked` 并写明理由
- 不在未 `show` 的情况下宣称「还剩 N 件事」
- 不把 `pop` 的四段回看压缩成一句「做完了」
- 不用 `amend` 抹掉返工痕迹（例如把判据改宽好让已做的活儿「刚好达标」）；判据变更要能自证理由
- 不在收工时跳过 `retro`，也不把复盘只汇报成「完成 N 帧」而略过放弃、搁置与改道
