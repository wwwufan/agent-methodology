# 推进栈 Schema 与状态机

需要手工核对 JSON、扩展字段或排查 `verify` 失败时读本文件。日常推进只看 `SKILL.md` 即可。

## 文件

```text
workstacks/                             ← v4：项目内、纳入 Git（原 scratch/workbench/<campaign>/）
├── .gitignore                 排除 */history/ 与 _current.json
├── config.json                布局配置（可选）；覆盖 workstack_root / plan_doc / issue_doc
├── _current.json              单栈指针（全局唯一）；**不入库**
└── <campaign>/
    ├── active-work-stack.json 真源；只由 scripts/stack.py 写
    ├── active-work-stack.md   派生视图；由 `render` 生成，手改会被 `render --check` 判失败
    ├── goal-ledger.md         总目标台账；**与栈同目录**，bound_ledger 一对一绑定
    ├── phases/                阶段快照（受控编排的不可变输入）
    └── history/               迁移备份（.v1.bak / .v2.bak）；不入库，版本历史由 Git 提供
```

## 布局配置（`workstacks/config.json`，可选）

栈与两个长期池的位置默认是 `workstacks/`、`docs/operations/next-work-plan.md`、`docs/operations/issues.md`；
项目可在 `<仓库根>/workstacks/config.json` 用三个**全部可选**的键覆盖：`workstack_root` / `plan_doc` / `issue_doc`，
值必须是仓库根相对路径字符串（例：`{"workstack_root": "stacks", "plan_doc": "docs/plan.md"}`）。
文件不存在 = 全默认且**零输出**，故加不加它对既有项目零影响；部分键缺失 = 缺的键取默认。
非法一律 `exit 2` 并点明是哪个键：根节点不是 JSON object、JSON 不可解析、未知键（拼错会静默不生效，
比报错更难查，故宁炸不默）、值非字符串或空串、绝对路径、含 `..` 段、解析后逃出仓库根、`workstack_root` 为 `.`。
配置位置**固定在 `workstacks/` 下**、不随 `workstack_root` 变，否则「先知道布局才能找到布局配置」成了自指循环。
已知限制：`find_repo_root` 的标记名用**默认** `workstacks`，故「唯一标记是自定义 `workstack_root`」的仓库
必须显式传 `--repo-root`。`doctor.py` 第 8 组读同一份文件：非法 = error、非默认值 = warn（它按默认路径检查，结论不覆盖自定义位置）。

## JSON 结构

```jsonc
{
  "schema_version": "work-queue-stack-v3",   // v1/v2 栈在首次写入时链式自动迁移，见文末
  "campaign_id": "ui-image-system-recognition",
  "title": "UI 图片多系统识别",              // 核心任务名（= 栈的名字）；语义恢复的匹配素材；缺省回落 campaign_id
                                            // `ensure --title` 设、`retitle` 改；campaign_id 不变 → 既有引用不受影响
                                            // 注意：**没有 status 字段**，open/closed 由帧状态派生（见「绑定字段」）

  // ── v3 新增：绑定字段（栈绑总目标，不绑轮次/窗口/阶段 Goal）──
  "bound_ledger": "workstacks/ui-image-system-recognition/goal-ledger.md",
                                            // 总目标台账的仓库根相对路径（与栈同目录）；台账不存在则 null
  "activation": "user_declared",             // user_declared | user_approved_on_proposal | pre-v3-unknown
                                            // | auto_orchestration（legacy，只接受不新发）

  "updated_at": "2026-09-18T12:38:05+08:00",

  "frames": [
    {
      "frame_id": "F-001",            // 全局唯一，脚本分配，不复用
      "depth": 0,                     // 0 = 根帧；子帧 = 父帧 depth + 1；上限 4
      "parent": null,                 // 父帧 frame_id 或 null
      "title": "① 修 ISS-022",
      "status": "active",             // 见状态机
      "goal": "让 pytest 能收集整个测试套件",
      "criteria": ["收集 0 error", "守卫测试就位"],   // 完成判据，收工时逐条自检
      "origin": "用户批准序列第 1 项",                 // 谁/哪一轮要求的，便于事后回溯
      "pointers": {"issues": ["ISS-022"], "commits": ["bcc5f6f"]},  // 只存指针，不存正文
      "spawned": ["F-004"],           // 本帧衍生出的子帧
      "created_at": "...", "closed_at": null, "close_note": null
    }
  ],

  "captures": [
    {
      "capture_id": "C-001",
      "at": "...",
      "text": "全量跑发现 51 项既存失败",   // 现象 + 发现位置，一行说清
      "found_in": "F-001",                  // 在哪一帧里发现的
      "disposition": "spawns",              // pending|blocks|spawns|note
      "frame_id": "F-004",                  // 已立帧时填
      "pointer": null                       // 未立帧时填归属，如 "ISS-007"
    }
  ],

  "pop_log": [
    {"at": "...", "frame_id": "F-004", "terminal": "done",
     "note": "...", "spawned": [], "remaining": ["F-001", "F-002", "F-003"]}
  ],

  "event_log": [                        // v2 新增：复盘真源，只追加、永不改写
    {"seq": 1, "at": "...", "kind": "pushed", "frame_id": "F-001", "detail": "① 修 ISS-022"},
    {"seq": 2, "at": "...", "kind": "suspended", "frame_id": "F-001", "actor": "dfs",
     "detail": "被新压入的子帧抢占"},
    {"seq": 3, "at": "...", "kind": "activated", "frame_id": "F-004", "actor": "dfs",
     "detail": "② 子任务"},
    {"seq": 4, "at": "...", "kind": "amended", "frame_id": "F-004",
     "detail": "criteria: 整组替换为 2 条"},
    {"seq": 5, "at": "...", "kind": "popped", "frame_id": "F-004", "terminal": "done"}
  ],

  "migrated_from": "work-queue-stack-v1" // 仅迁移过的栈才有；retro 会据此声明历史不完整
}
```

## 绑定字段（v3 新增）

栈的绑定对象是**总目标（campaign）**，用两个字段把这件事变成可机械校验的事实，而不是口头约定：

| 字段 | 取值 | 含义 |
| --- | --- | --- |
| `title` | 字符串 | **核心任务名 = 栈的名字**（用户看 `stacks` 清单时认它，不认 `campaign_id`）。`ensure --title` 设、`retitle` 改，`campaign_id` 不变所以既有引用不受影响；缺省回落 `campaign_id` |
| `bound_ledger` | 仓库根相对路径 / `null` | **与栈同目录**的 `goal-ledger.md`。`ensure` 在台账真实存在时才填；填了就必须存在，否则 `verify` 判**绑定已断**（硬违规） |
| `activation` | `user_declared` | 用户主动声明需要任务栈 |
| | `user_approved_on_proposal` | 代理 `propose` 打印申请卡、**用户批准后**才 `ensure` |
| | `pre-v3-unknown` | v3 之前创建，无从考证。**迁移时一律记这个值，不猜** —— 猜出来的绑定在复盘时比没有绑定更坏 |
| | `auto_orchestration` | **legacy**：v3 时期「编排身份自动启用」留下的历史值。只接受、不再新发（新建栈传它 `exit 2`）；`verify` 见到给软警告，不改写历史 |

**没有 `status` 字段**：栈的 `open` / `closed` 由帧状态**派生**（全部帧终态 ⇒ `closed`，否则 `open`）。
多存一个标志位就多一个可能失真、需要额外校验的字段，而派生值永远不会与帧矛盾。
`stacks` 清单里的 status 列即由此算出。

`activation` 记录的是**栈最初怎么来的**，`ensure` 重复调用不会改写它；确需改记必须显式带
`--set-activation`（且仅对 `pre-v3-unknown` 生效），改动会打印出来，不静默。

### 创建栈只有一个门：`ensure`

`push` 在栈文件不存在时 **`exit 2`**，不再 `allow_missing` 建栈。这是防**栈分叉**：

```text
$ stack.py push --campaign ui-image-system-recogntion --title …   # 少打一个 i
[exit 2] 栈不存在：…/workstacks/ui-image-system-recogntion/active-work-stack.json
`push` 不再静默新建栈（打错 `--campaign` 会造成栈分叉：帧进了空栈、真栈没动、verify 还 PASS）。
要启用一个新栈请**显式**运行：`stack.py ensure --campaign ui-image-system-recogntion --activation user_declared`
你是不是想找：`ui-image-system-recognition`？
```

近似提示由 `difflib.get_close_matches` 对 `workstacks/` 与旧 `scratch/workbench/` 下
**已有栈文件或台账**的目录名计算（两个根都扫，否则迁移后这道防分叉的防线会失灵），
因此不会把无关目录当候选。分叉的危险在于它**静默且自检通过**：新空栈的 `verify` 是 PASS 的，
只有「真栈帧数没变」这一个信号，而人不会去数。把创建收敛到 `ensure` 一个门之后，
「栈是怎么来的」必然对应一条显式动作与一个 `activation` 值。

**但防线必须装在创建门上**：`push` 的近似提示只是把人导向 `ensure`，若 `ensure` 自己不校验，
「打错一个字母」的补救建议恰好就是「去建那个错名字的栈」。实测
`ensure --campaign ui-image-system-recogntion --activation user_declared`（少一个 `i`）
确实建出了分叉空栈，因此新增 `_refuse_near_match_fork`：新建时与既有 campaign 相似度 ≥0.6 即 `exit 2`
并列出候选；确实要建名字相近的**不同**栈时显式带 `--force-new`。

`survey` 是唯一容忍栈缺失的命令（`exit 0`，只打印「还没有推进栈」）——它是选单，本就运行在建栈之前。

**为什么绑 campaign 而不绑 Goal / phase / 轮次**：Goal 独占串行、收口即释放，而阶段间收尾工作恰恰
发生在 Goal 释放之后；phase 装不下跨阶段帧与工具自建帧；轮次边界只存在于用户脑子里、跨窗口即断。
campaign 是唯一能横跨多 Goal / 多 phase / 多会话 / 跨天的稳定标识，且与台账同目录同名。
因此**栈跨轮续用**，schema 里没有 round 层，也刻意不加。

`pop_log` 是**防丢失的最后一道保险**：即使 `frames` 被误改，出栈日志仍能还原
「哪一帧在什么时候以什么终态关闭、当时栈里还剩什么」。

## event_log（v2 新增：弯路复盘的真源）

`frames` 只存**当前状态**，回答不了「我们中间改过几次主意、放弃过什么、在哪一帧上反复返工」。
`event_log` 是只追加的时间线，`retro` 命令只读它做复盘，不参与推进逻辑。

| `kind` | 何时写入 | 关键字段 |
| --- | --- | --- |
| `pushed` | `push` 成功 | `frame_id`、`parent`、`detail`=标题 |
| `activated` | 成为栈顶（`push --activate` / `activate` / 空栈自动） | `frame_id`、`actor` |
| `suspended` | 原栈顶被后代帧打断 | `frame_id`、`actor="dfs"` |
| `requeued` | 原栈顶因**用户改道**退回 `queued` | `frame_id`、`actor="user"` |
| `resumed` | 子帧关闭后自动恢复原栈顶 | `frame_id`、`actor="dfs"` |
| `captured` | `capture` 登记衍生问题 | `capture_id`、`frame_id`=发现处 |
| `resolved` | `resolve` 处置衍生登记 | `capture_id`、`disposition` |
| `popped` | `pop` 关帧 | `frame_id`、`terminal` |
| `amended` | `amend` 修订未关闭帧 | `frame_id`、`detail`=改了哪些字段 |

`actor` 只有三种，用于把「计划内深入」和「临时改主意」分开——这是 `retro` 最核心的判据：

- `dfs`：按任务树往下钻（压入子帧并抢占、恢复被打断的父帧）。**不算弯路。**
- `user`：用户驱动的切换（`activate` 到非后代帧）。**弯路信号。**
- `auto`：栈里没有 `active` 帧，压栈时自动成为栈顶。中性。

三条硬约束（`verify` 会查，违反即 exit 1）：

1. `seq` 必须是从 1 开始的**连续递增**整数。缺号说明有人删过事件，即使仍然递增也会被判违规。
2. `kind` 必须在上表内，`actor` 若存在必须在 `dfs|user|auto` 内。
3. 事件只允许追加：任何回填、重排、改写都会破坏 1 或 2。

`retro` 统计「用户方向切换」时按**改道次数**去重：一次改道会先记 `requeued` 再记
`activated(actor=user)`，只算 1 次；`push --activate` 记的是 `actor=dfs`，不会被误报成改道。

## amend 与 retro 的分工

| 命令 | 作用 | 是否写盘 |
| --- | --- | --- |
| `amend` | 修订**未关闭**帧的 `title`/`goal`/`origin`/`criteria`/`pointers`，改动写进 `event_log` | 是 |
| `retro` | 只读复盘：放弃的方案、明确搁置、升级为缺陷、用户改道次数、结构指标 | 否 |

`amend` 对**终态帧一律 exit 2**：`done`/`parked`/`escalated`/`wontfix` 是历史，不得改写。
要纠正已关闭帧的结论，正确做法是新压一帧说明返工原因，让这次返工留在树里可查。
`criteria` 是整组替换（不是追加），`pointers` 是与既有键合并。

## 状态机

```text
                 push（无 active 帧）
                        ↓
   ┌──────────────→  active  ←──────────────┐
   │                  │  │                  │
   │   子帧 activate   │  │  用户切换到非后代帧  │
   ↓                  ↓  ↓                  │
suspended ──子帧 pop 后自动恢复──┘  └──→ queued ──activate──┘
   （任何未关闭状态）
        │
        └── pop ──→ done | parked | escalated | wontfix   （终态，必须带 close_note）
```

| 状态 | 含义 | 是否未关闭 |
| --- | --- | --- |
| `active` | 栈顶，正在做；**最多一个** | 是 |
| `queued` | 已登记、等待；**挂起不是丢弃** | 是 |
| `suspended` | 曾是栈顶，被子帧打断；子帧 `pop` 后**自动恢复** | 是 |
| `done` | 完成，`close_note` 写清判据达成情况与证据 | 否 |
| `parked` | 明确搁置，`close_note` 必须写搁置理由与恢复条件 | 否 |
| `escalated` | 升级为 `issues.md` 条目，`pointers.issues` 必须有 `ISS-0xx` | 否 |
| `wontfix` | 决定不做，`close_note` 必须写理由 | 否 |

两种栈顶切换的区别（`activate` 会自动判别并打印）：

- 目标是当前栈顶的**后代** → 栈顶转 `suspended`，关掉子帧后自动恢复。这是正常的深度优先推进。
- 目标与栈顶**无祖先关系**（用户临时改主意）→ 栈顶退回 `queued`，**不会**自动恢复，
  脚本会显式告警。这类切换最容易造成遗忘，务必在收工回看时确认它还在栈里。

## disposition 语义

| 值 | 判定问题 | 必须的落点 |
| --- | --- | --- |
| `blocks` | 不解决它，当前帧就无法完成？ | `push --parent <栈顶> --activate` 建子帧，再 `resolve --frame` |
| `spawns` | 是真问题，但与当前帧无阻塞关系？ | `push`（默认 `queued`，**不当场展开**），再 `resolve --frame` |
| `note` | 不是独立问题，只是某处的新证据？ | `resolve --pointer ISS-0xx`（或文件路径） |
| `pending` | 还没想好 | 允许临时存在，但 `verify` 会判**硬违规**；收工前必须 `resolve` |

`pending` 被判失败是刻意设计：它是「发现了但还没决定」的状态，也正是最容易被遗忘的状态。
让它挡住 `verify`，遗忘就会在收工时被抓到，而不是在下一轮才发现。

## verify 的不变量与修复方式

| 违规 | 通常原因 | 修复 |
| --- | --- | --- |
| 同时有多个 `active` | 手工改过 JSON | 用 `activate` 指定唯一栈顶 |
| `suspended` 不是 `active` 的祖先 | 切换顺序被打乱 | `activate` 重新选定栈顶，让挂起链自洽 |
| 深度达上限 4 | 当前帧定义太粗，一层层往下拆 | 把中间层 `parked` 或重新拆帧 |
| `parent`/`spawned` 指向不存在的帧 | 手工删帧 | 补齐或改正指针；删帧必须走 `pop` |
| `depth` 与父帧不自洽 | 手工改过 `depth` | 用 `push --parent` 重建该帧 |
| 终态帧缺 `close_note` / `closed_at` / `pop_log` | 绕过 `pop` 直接改状态 | 只能用 `pop` 关帧 |
| `capture` 停留 `pending` | 登记后忘了处置 | `resolve` 到某个帧或指针 |
| `blocks`/`spawns` 无 `frame_id` 也无 `pointer` | `resolve` 时漏给落点 | 补 `--frame` 或 `--pointer` |
| 帧无 `criteria`（**软警告**） | `push` 时没写判据 | 补判据，否则收工无法客观自检 |
| 有未关闭帧却无 `active`（**软警告**） | 刚 `pop` 完还没选下一个 | `activate` 选一帧，或明确交给用户决定 |
| `event_log` 缺失或不是数组 | 手工改过 JSON / 旧 v1 文件 | 用 v1 文件走 `load` 自动迁移；不要手拼 v2 |
| `event_log` 的 `seq` 不连续 | 删过事件 | 事件日志只追加；缺号无法修复，只能新压一帧说明 |
| `event_log` 的 `kind`/`actor` 非法 | 手工加过事件 | 只通过 `stack.py` 的子命令产生事件 |
| 本栈由 v1 迁移而来（**软警告**） | 老栈升级 | 无需处理；`retro` 会声明迁移点之前的改道计数不完整 |
| `activation` 取值非法 | 手工改过 JSON | 只能是 `user_declared` / `user_approved_on_proposal` / `pre-v3-unknown` / `auto_orchestration`(legacy) |
| `activation` 是 legacy `auto_orchestration`（**软警告**） | v3 时期编排自动启用留下的老栈 | 无需处理，也不改写历史；新栈不会再产生这个值（`ensure` 对新建栈强制要求非 legacy 的 `--activation`） |
| 当前指针指向一个已 `closed` 的栈 | 旧版本或中断遗留的指针 | 新版最后一帧 `pop` 自动释放匹配 campaign 及栈路径的指针；旧遗留须核对后 `use` 指向实际在推进的栈，不为消除告警虚构新工作；要复用 closed 栈先 `push` 新帧说明返工原因 |
| 当前指针指向别的 campaign（**软警告**） | 一个对话里换了栈却没走 `use` | 一个对话只允许一个栈；切换用 `use`（会留痕 `pointer_switched`），不要手改 `_current.json` |
| `bound_ledger` 指向的台账不存在 | 台账被移动/删除，或栈被拷到别处 | 把栈与 `goal-ledger.md` 放回同一 campaign 目录，再 `ensure` 补绑 |
| 台账 `campaign_id` 与栈不一致 | 栈被拷进了别的 campaign 目录 | 栈绑的是总目标：确认归属后改正 `campaign_id`，或把栈移回原 campaign |
| `bound_ledger` 为空（**软警告**） | 仓库外临时栈，或台账尚未落盘 | 临时栈可接受；属某个 campaign 就 `ensure` 补绑 |
| 台账里解析不到 `campaign_id`（**软警告**） | 台账格式非常规 | 补齐台账的 `campaign_id` 行；在此之前绑定一致性**未校验**，脚本会如实声明 |
| 视图与真源不一致 | 手改了 `.md` | `render` 重新生成 |

软警告不阻断（`verify` 仍 exit 0），但必须在回看里向用户说明。

## 退出码

| 码 | 含义 |
| --- | --- |
| 0 | 成功（含 `verify` 无硬违规、`render --check` 一致） |
| 1 | `verify` 发现硬违规；或 `pop` 时本帧存在未处置衍生项 |
| 2 | 用法/环境错误：栈文件缺失或损坏、frame_id 不存在、状态迁移非法、深度超限、越序 `pop`、**`push` 时栈不存在**（创建只有 `ensure` 一个门） |

## 与其他产物的写法约定

- `campaign_id` 取当前项目任务台账里的 `campaign_id`，不使用方法论仓库预设的业务活动名；
  `verify` 会拿台账正文反查它，两者不一致即硬违规 —— 所以不要靠改目录名来「换 campaign」。
- 栈与台账属**过程与决策资产**，放 `workstacks/<campaign>/`（不进 `docs/`），**纳入 Git 提交**；
  `history/` 与 `_current.json` 由 `workstacks/.gitignore` 排除。
- 提交节奏：收口时合成一个独立的 `chore(stack):` 提交（只含 `workstacks/` 下的 json + md + 台账 + phases），
  **永不与其他改动混提**；**禁止在多个分支或多个窗口同时推进同一个栈**（JSON 合并冲突无法手工解）。
- 帧标题用用户能一眼认出的措辞（如 `① 修 ISS-022`），不要用内部术语。
- `pointers` 只放**可反查的标识**：`ISS-0xx`、commit 短哈希、文件路径、digest。
  需要长篇结论时写进 `issues.md` 或台账，栈里只留指针。

## 迁移（v1 → v2 → v3）

- `load()` 读到 `schema_version == "work-queue-stack-v1"` 时在**内存里**自动迁移：
  从 `frames[].created_at`、`pop_log[].at`、`captures[].at` 回填 `pushed`/`popped`/`captured`
  三类事件，按时间排序后重编 `seq`，并打上 `migrated_from`。
- 只读命令（`show` / `survey` / `verify` / `retro` / `render`）**不落盘**，因此不会偷偷改写老栈；
  第一次执行写命令（`push`/`activate`/`capture`/`resolve`/`pop`/`amend`）时才持久化为 v2。
- `activate` / `suspended` / `resolve` / `amend` 在 v1 时期没有留痕，**无法回填**。
  迁移过的栈 `retro` 会显式声明「用户方向切换计数只覆盖迁移点之后」，不假装拥有并不存在的历史。
- 迁移前请先备份（v1 时期栈文件在 `scratch/`、不进 Git）：`cp active-work-stack.json{,.v1.bak}`。

### v2 → v3

- `load()` 读到 `work-queue-stack-v2` 时补 `bound_ledger` / `activation` 两个顶层字段并升版本号；
  v1 栈走 `v1 → v2 → v3` 链式迁移，`migrated_from` 保留**最早**的来源版本（v1 栈仍记 v1）。
- `activation` 一律记 `pre-v3-unknown`；`bound_ledger` 留 `null`，由下一次 `ensure` 在台账存在时补绑。
- **迁移不改写 `event_log`**：既有事件的 `seq` 逐位不变（实测校验），复盘历史不受影响。
- 迁移由写命令触发落盘；`ensure` 是最自然的触发点，也是编排 skill 的启动动作。
- 备份同理：`cp active-work-stack.json{,.v2.bak}`。

### v3 → v4（栈搬出 `scratch/`、纳入 Git）

- **不是 schema 变更**：JSON 结构、`schema_version`（仍为 `work-queue-stack-v3`）、不变量与命令语义都不变，
  变的只有**栈住在哪**。所以没有 `migrate_v3_to_v4()` 这种数据迁移函数，只有一个搬文件的 `migrate` 子命令。
- 动因（实测）：`clean-scratch-intermediates` 只保 `workbench` 空骨架、清空内容，跑一次即删掉栈 + 台账 + 阶段快照；
  `git clean -ndx` 报 `Would remove scratch/workbench/<campaign>/`。栈却是「推进状态唯一真源」。
- `resolve_paths` 的根改为 `workstacks/`；旧位置有栈而新位置没有时 `_refuse_legacy_fork` 让**所有命令** `exit 2`
  并要求先 `migrate`——防止在新位置另起空栈造成分叉（两边 `verify` 都 PASS，没人会发现）。
- `verify` 的台账解析由「同目录硬推导」改为 `_resolve_ledger_path()`：同目录 → `bound_ledger`（仓库根相对）→
  旧 `scratch/workbench/<同名 campaign>/`。**不改这里，搬迁会把「绑定自洽」误判成「绑定已断」硬违规**。
  三处都找不到时仍返回 `bound_ledger` 那条路径，让 `verify` 如实报「绑定已断」，而不是降级成「未绑定」软警告。
- `_ledger_rel` 同步支持按同名 campaign 回退；`_existing_campaign_ids` 同时扫新旧两个根
  （否则迁移后「你是不是想找 …」的近似提示会失灵，而它是防分叉的那道防线）。
- `EVENT_KINDS` 新增 `migrated`；`migrate` 内部机械断言：帧数不变、原 `seq` 逐位不变、只追加一条事件。
- `history/` 不入库（`workstacks/.gitignore`）：栈已进 Git，版本历史由 Git 提供，`.bak` 是 gitignore 年代的保险。
- **台账搬迁（用户 2026-09-20 定案「搬」）**：`migrate` 是二段式 —— 先搬栈（json + md + `history/`），
  再 `_migrate_ledger_only` 把 `goal-ledger.md` 与 `phases/` 一起搬进 `workstacks/<campaign>/`，
  并在台账头部**追加**一条迁移说明（旧路径 → 新路径映射），**不改写任何历史条目里的旧路径**。
  搬完后 `bound_ledger` 是同目录路径，`_ledger_rel` / `_resolve_ledger_path` 的同目录推导重新成立；
  「台账仍暴露在 `scratch` 清理射程内」的风险随之消除（F-024 因此不必立新缺陷）。
- 同期新增命令：`propose`（只读申请卡）/ `stacks`（只读全局清单）/ `use`（写单栈指针、切换留痕）/
  `retitle`（改核心任务名）；`ensure` 增 `--title`，并把「新建栈必须显式声明启用方式」做成 `exit 2`
  ——缺省或 legacy 值都不落任何文件，让「编排身份不构成启用授权」变成机械事实而不是 prose。
  `EVENT_KINDS` 增 `proposed` / `pointer_switched` / `retitled` / `migrated`；`ACTIVATIONS` 增
  `user_approved_on_proposal`，`auto_orchestration` 移入 `LEGACY_ACTIVATIONS`（`verify` 软警告）。
- 实测（真栈 24 帧）：搬运 4 个文件、帧数 24 → 24、`event_log` 95 → 96；台账搬迁 2 项、
  `bound_ledger=workstacks/ui-image-system-recognition/goal-ledger.md`（同目录）、96 → 97 → 98；
  `retitle` → 「UI 图片多系统识别」；`use` 指针已设；`propose` 对已有栈提示无需申请、
  对全新 campaign 打印申请卡且**未创建任何目录**；`verify` [PASS]、`render --check` 一致；
  旧目录已无 `goal-ledger.md` / `phases/`；分叉守卫与近似提示各一组负向实测。
