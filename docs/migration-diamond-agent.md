# 从 diamond-agent 迁出方法论 skill（过程真源）

本文是「把方法论 skill 从 diamond-agent 项目迁出为独立真源仓库」这件事的**过程真源**：
为什么迁、分几步、当前处于哪个中间态、哪些不一致是**故意留着**的、以及后续各阶段必须记得做的事。

阶段性状态与进度登记在项目侧的计划/进度文档里（不入本仓库）；本文只放跨阶段仍然成立的结论与待办。

---

## ① 动机与范围

**动机**：`campaign-work-stack`、`multi-phase-plan-orchestrator`、`single-phase-execution-loop`、
`guided-goal-orchestrator`、`explain-task-failure` 这 5 个 skill 描述的是「怎么推进一项复杂工作」，
与 diamond-agent 的业务毫无关系（实测：5 份 `SKILL.md` 正文里 `Diamond|diamond-agent|diamond_` 出现次数 = **0**，
唯一命中是 `__pycache__/*.pyc` 二进制里烙进的绝对路径）。把它们留在业务项目里，别的项目就无法复用，
且每次复用都要复制一份 —— 复制即分叉，分叉即失去真源。

**项目名耦合的真实分布**（实测）：不在 skill 正文里，而在角色配置里 ——
`.codex/agents/*.toml` 的身份句是「你是 Diamond Agent 项目的 X 子代理」，
`.cursor/agents/*.md` 的身份句已经是「你是**本项目**的 X 子代理」（两套模板的身份句本来就不同源）。
所以迁出只需要把身份句参数化，不需要改 skill 正文的语义。

**范围**：

| 类别 | 数量 | 处置 |
| --- | --- | --- |
| 方法论 skill | **5** | 迁出到本仓库，成为唯一真源 |
| 业务 skill | **12** | **不动**，继续留在 diamond-agent 的 `.agents/skills/` 下 |

计数口径见 ④。

**不在范围**：Cursor 是否支持全局 skill —— 用户已明确排除（2026-09-21 原话
「不需要考虑Cursor支持全局skill」），证据边界见 `discovery-probe.md` A4。

---

## ② Phase 分期表

| Phase | 一句话目标 | 关键产出 / 门禁 |
| --- | --- | --- |
| **0** | 用探针搞清 Codex / Cursor 的 skill 发现机制，选定挂载布局 | 选定「两端都挂」；结论与证据边界见 `discovery-probe.md` |
| **1** | 在暂存区搭出未来仓库的**完整内容**（不含 `.git`）：只搬不改 + 新建 3 个仓库级脚本、10 个模板、3 份文档 | 32 个文件 / 21 个目录；5 份 `SKILL.md` 与项目内当前版本逐字一致 |
| **2** | 改路径表述与脚本行为：`SKILL.md` 里的 `.agents/skills/…` 前缀改为相对表述、移动 `check_codex_backend.py`、给 `stack.py` 加配置发现、把 `survey` 两池皆空时的 `exit 1` 改为 `exit 0` + bootstrap 指引、把 diamond-agent 专属活动实例移出到项目侧 | 机械验收：**`doctor.py` 第 10 组 warn 归零**（判据已按裁决 **R14** 放宽：正则去掉 `/scripts/` 尾巴 + 扫描范围加 `references/`，命中由 3 处扩到 **6 处 / 5 文件** 后归零）。**本阶段已在暂存区实施完成**；`survey` 空池 `exit 0` 含「池文件存在但解析 0 条」的扩展解释（裁决 **R16**），`--structure-only` 未排期（裁决 **R17**） |
| **3** | 结构治理：抽公共角色契约、治理 skill 的 `description` 与 `references/` 结构 | `references/role-contract.md` |
| **4a** | promote 到最终仓库路径（`git init` + 首个提交），并用 `install.py --adopt-symlink` 接管个人根软链 | 门禁 **G2**（仓库最终路径与名字确认）、**G3**（等价性回归双采比对，`stack.py` 行为不变） |
| **4b** | 把项目侧实体目录**改为软链**（`install.py --project-link --replace-dir --backup-dir`），并更新项目 `AGENTS.md` 写明「两端只能是软链、禁止实体副本」 | 硬前置：`explain-task-failure/` 在项目里**未纳入 Git**（实测 `??`），替换前必须先提交或确认备份目录里有它 |

Phase 切分的机械判据（防范围蔓延）：

| 问题 | 归属 |
| --- | --- |
| 某个文件在**新仓库**里的位置 / 名字 | Phase 1 |
| 仓库级新工具（install / bootstrap / doctor）的接口与实现 | Phase 1 |
| 模板的完整内容 | Phase 1 |
| `stack.py` / `check_codex_backend.py` 的**任何行为改动** | Phase 2 |
| 5 份 `SKILL.md` 的**任何字符改动** | Phase 2（路径表述）/ Phase 3（结构治理） |
| `references/role-contract.md` | Phase 3 |

---

## ③ 暂存期不一致清单（**故意留着**，Phase 2 修）

Phase 1 的硬约束是「5 份 `SKILL.md` 逐字一致」，代价是暂存仓库里的 `SKILL.md` 仍带着
`.agents/skills/…` 前缀的路径与 diamond-agent 专属的活动实例 —— **这些引用在新仓库布局下全部失效**。
这不是疏漏，是明知故犯接受的中间态；但必须留痕，不能只存在于对话里。

跟踪机制：下表第 1~3 条由 `doctor.py` **第 10 组**机械跟踪。Phase 1 时该组判据刻意窄
（正则 `\.agents/skills/[A-Za-z0-9_-]+/scripts/`、只扫 `skills/*/SKILL.md`），恰好命中 **3 处**；
Phase 2 按裁决 **R14** 放宽为正则 `\.agents/skills/[A-Za-z0-9_-]+/`（去 `/scripts/` 尾巴）+ 扫描范围加
`skills/*/references/*.md`，于是同类失效引用从 3 处扩到 **6 处 / 5 文件**（新增 `activation-and-recovery.md:75,137`、
`orchestration-strength-guide.md:3`），全部修掉后第 10 组归零。第 4 条不被该判据命中，只由本清单跟踪。

| # | 文件:行号 | 失效内容 | 失效原因 | 修复 Phase |
| --- | --- | --- | --- | --- |
| 1 | `skills/campaign-work-stack/SKILL.md:128` | `S=.agents/skills/campaign-work-stack/scripts/stack.py` | 新仓库里该脚本位于 `skills/campaign-work-stack/scripts/stack.py`，没有 `.agents/` 前缀；挂载后经软链访问的路径也不是这个 | **2 · 已修**：改为自指占位符 `S=<本 skill 目录>/scripts/stack.py`（首次使用处带 1 行占位符定义） |
| 2 | `skills/single-phase-execution-loop/SKILL.md:163` | 同上形式的 `S=.agents/skills/campaign-work-stack/scripts/stack.py` | 同上（这是**跨 skill** 引用：spel 正文里用 wqs 的 `stack.py`） | **2 · 已修**：改为跨 skill 占位符 `S=<skill 根>/campaign-work-stack/scripts/stack.py` |
| 3 | `skills/multi-phase-plan-orchestrator/SKILL.md:101` | `python .agents/skills/multi-phase-plan-orchestrator/scripts/check_codex_backend.py` | 该脚本 Phase 2 已移到 `skills/single-phase-execution-loop/scripts/` 下，路径与文件名两处都变 | **2 · 已修**（与脚本移动**同批**）：改为 `python3 <skill 根>/single-phase-execution-loop/scripts/check_codex_backend.py` |
| 4 | `skills/multi-phase-plan-orchestrator/SKILL.md:175-185` | diamond-agent 专属活动实例（`ui-csd-visual-variants`、`ui-image-system-recognition` 的 `execution_plan` / `progress_tracker` / `commit_prefix` / 阶段序列，路径形如 `scratch/workbench/<campaign>/…`） | 这是**业务项目的活动台账**，不属跨项目复用的方法论；留在真源仓库会让每个新项目都看到两个与它无关的活动 | **2 · 已修**：168–EOF 整段替换为「活动实例的发现与登记」通用规则（指向项目侧 `workstacks/_activities.md`，并显式写明该文件**可能不存在、不是错误**）。**本仓库不创建该文件**（硬约束 2），活动台账由各业务项目自维护 |

第 4 条为什么不由 `doctor.py` 第 10 组跟踪：该组判据匹配 `.agents/skills/<slug>/` 项目侧前缀。
Phase 1 时它刻意窄（只匹配 `…/scripts/`、只扫 `SKILL.md`）；Phase 2 按裁决 **R14** 放宽（去 `/scripts/` 尾巴 + 扫
`skills/*/references/*.md`）后，`references/stack-schema.md`、`references/activation-and-recovery.md` 里大量
`scratch/workbench/…` 的提及**仍不被命中** —— 那是 v3→v4 迁移史的**合法叙述**（`stack.py` 的 `migrate` 命令就依赖
这套旧路径语义），不是缺陷。放宽判据**没有**产生永久黄噪音：本正则只匹配 `.agents/skills/<slug>/` 前缀，
与 `scratch/workbench/…` 的命中集合**零交集**（实测，见 `doctor.py` 第 10 组 detail 与 V6 复核）。

Phase 2 把第 1~3 条（放宽后含 references 共 **6 处 / 5 文件**）改成布局无关的占位符表述后，第 10 组命中数变为 0，warn 消失。
**于是「`doctor.py` 第 10 组 warn 归零」是 Phase 2 的一条机械验收项**（比"人工读一遍看路径改没改"强得多）。
Phase 1 不得为了让当下好看而把该项设成 OK 或跳过 —— 它的价值正是"现在黄、Phase 2 变绿"。

---

## ④ 口径注记：skill 计数的三种口径（引用时**必须**注明）

同一个项目在同一时刻可以合法地对应三个不同的数字，它们互不矛盾，但**混用就会显得自相矛盾**
（Phase 0 曾因此判 FAIL）。凡引用计数，必须注明口径。

| 数字 | 口径 | 怎么数出来的 |
| --- | --- | --- |
| **17** | `<project>/.agents/skills/` 下的**目录总数** | `ls -1d <project>/.agents/skills/*/ \| wc -l` = 17（实测） |
| **12** | **业务 skill** 数（不迁出的那部分） | 17 − 5 个方法论 skill = 12 |
| **15** | 本轮 Codex 会话注入的 skill 清单中，以项目根（`r5 = <project>/.agents/skills`）列出的**条数** | 17 − 1（`explain-task-failure` 因 A3 的去重/遮蔽经个人根 `r0` 出现）− 1（`guided-goal-orchestrator` 因 `allow_implicit_invocation: false` 不进隐式清单）= 15 |

关键区分：**17 是磁盘上的目录数，15 是注入清单里的条目数**。二者相差的 2 条不是"丢了"，
一条换了来源根、一条被 frontmatter 显式关掉了隐式调用。判读"某个 skill 不在清单里"时必须区分这两种成因
（详见 `discovery-probe.md` A3）。

本仓库自身的口径：`skills/` 下 **5** 个 skill；Phase 1 暂存区共 **32** 个文件 / **21** 个目录
（32 = 14 个逐字复制 + 18 个新建；21 含仓库根，其中 `skills/` 下 **12** 个目录）。

Phase 1 口径 32/21 为历史基线；Phase 3 后现状 = **33 文件 / 22 目录（含根）**，推导见 ⑦.12。

---

## ⑤ 后续阶段待办（**跨阶段记忆**，做完请回来划掉）

按 Phase 排序。这里的每一条都是"现在不做、以后一定会忘"的类型，所以写进仓库而不是写进对话。

### Phase 2

1. ✅ **已修** · **移动 `check_codex_backend.py`**：已从 `skills/multi-phase-plan-orchestrator/scripts/` 移到
   `skills/single-phase-execution-loop/scripts/`（旧目录已 `rmdir`），**并同批**改了 `multi-phase-plan-orchestrator/SKILL.md:101`
   的引用（③ 第 3 条）。Phase 2 还给它加了 `--codex-bin` 与零 traceback 的友好 JSON 报错（`status=not-ready`）。
2. ⏸ **未排期**（裁决 **R17**）· **给 `check_codex_backend.py` 加 `--structure-only`** 并把 `doctor.py` 第 6 组改为 subprocess 复用：
   **不纳入 Phase 2**（计划未列 = 未声明的范围扩张；且会使 doctor 依赖「外部脚本可执行 + 刚移位」两个同时变化的条件，失败模式叠加）。
   Phase 2 只做 移位 + `--codex-bin` + 友好报错。见下面「互指注释留痕」（该段同步改为「未排期」）。
3. ✅ **已修** · **改路径表述**（③ 第 1~3 条）→ 验收：`doctor.py` 第 10 组 warn **归零**（实测 `--no-global` 0 error / 0 warn）。
   注：范围按裁决 **R13** 更正为 **3 份 `SKILL.md`（4 处）+ 2 份 `references`（3 处）+ `stack.py:28` docstring + `stack-schema.md`**
   （原计划文本「4 份 SKILL.md」是笔误）。
4. ✅ **已修（仓库侧）** · **把 diamond-agent 专属活动实例移出**（③ 第 4 条）：mpo `SKILL.md` 168–EOF 整段替换为
   「活动实例的发现与登记」通用规则，指向项目侧 `workstacks/_activities.md`。**本仓库不创建该文件**（硬约束 2）；
   项目侧台账由各业务项目自维护，Phase 4b 落到 diamond-agent 时再按需建。
5. ✅ **已做** · **给 `stack.py` 加配置发现**：新增 `Layout` / `load_layout` / `layout_for_root`，发现 `<repo>/workstacks/config.json`
   （位置固定，不随 `workstack_root` 变）；schema 写进 `references/stack-schema.md`。diamond-agent 无 `config.json`，输出零变化（V1 实证）。
6. ✅ **已做** · **把 `survey` 两池皆空时的 `exit 1` 改为 `exit 0` + bootstrap 指引**；并按裁决 **R16** 扩展：
   「池文件**存在**但解析 0 条」也由 `exit 1` 改为 `exit 0`（保留既有 warn 行）。两种情形输出**可区分**：
   文件都缺失 → 给 bootstrap 指引；文件存在但 0 条 → 保留 warn 行。第 9 组文案已同步更新（去 `stack.py:1432` 行号、改述 exit 0）。
7. ✅ **关闭**（裁决 **R18**）· **`templates/workstacks/.gitignore` 无需为 `workstacks/config.json` 加例外**：
   实测该 `.gitignore` 只排除 `*/history/`、`_current.json`、`_current.json.tmp`，`config.json` 天然入库。
   **Phase 4a 仍须实测**（promote 后跑 `git status --ignored` 确认 `config.json` 不被忽略）。

### Phase 3

8. ✅ **已按 ⑦ 裁定收口** · 抽 `references/role-contract.md`（三角色公共契约）：契约唯一真源 =
   `skills/single-phase-execution-loop/references/role-contract.md`；6 个角色模板**保持运行时自包含**
   （不指针化），模板与真源之间的重复由 `doctor.py` 第 13 组机械看护。裁定与理由见 ⑦.11 决策 ④。
9. ✅ **已完成** · 治理 skill 的 `description` 与 `references/` 结构：`campaign-work-stack` 的 description
   由 13 行块体压到 8 行（其余 4 份本就 ≤8 行，未动）；`references/` 结构治理 = 新增
   `single-phase-execution-loop/references/`，并把三个编排 SKILL.md 里重复的接线规则收敛到
   `campaign-work-stack/references/activation-and-recovery.md`。保留词清单与「原位置 → 新位置」映射见 ⑦.9 / ⑦.10。
10. 若希望新项目也能用 `module-investigator`（第 4 个角色，AGENTS.md 规定它"只能由用户显式点名，
    不得自动委托"），加 `--with-investigator` 开关。Phase 1 **不 bootstrap 它**。

### Phase 4a / 4b

11. ✅ **已确认（G2 · 2026-09-21）** · 仓库最终路径与名字 = `~/client/agent-methodology`（独立 Git 仓库，首提交 `3be3060`）。
    `bootstrap_project.py` 的围栏注释行实测为 `# 本区块由 agent-methodology/scripts/bootstrap_project.py 管理。`（`:64`），
    与最终仓库名一致，**无需同步**；`FENCE_OPEN/CLOSE`（`:61-62`）亦已用该名。
12. ✅ **已执行（4a · 2026-09-22 PASS，用户 G3 确认 2026-09-24）** · 等价性回归在替换项目内实体副本**之前**完成：
    OLD 锚 `agent-methodology@3be3060` vs NEW `@17090b5`，5 个只读入口归一化后 `diff = 0`，Reviewer 18/18/0/0。
13. ✅ **已解除（G4 + 4a 追加验收 (i)(ii)(iii)）** · `explain-task-failure/` 未纳入 diamond-agent Git 的处置：
    不提交进项目 Git，改为备份到 `~/client/agent-methodology-backup/explain-task-failure-20260921/`（`cp -Rp` + 逐文件 shasum 2/2 OK），
    且两文件已入真源 Git（hash `8eb390d4…` / `ff4c30f0…` 逐字节吻合）；`install.py` 的 `conflict(real)` 输出里的这条风险提示保持有效。

### 互指注释留痕（§doctor 第 6 组与 `check_codex_backend.py` 的接缝）

`doctor.py` 第 6 组自实现了一份与 `check_codex_backend.py:load_role_configs` 语义对齐的静态结构检查
（越界校验 + 四个必填字段 + `sandbox_mode` 期望值），但**不比对活动模型、不 shell out 到 codex**
（那是编排期门禁，不是安装健康；且 doctor 不应依赖 codex CLI 存在）。这是唯一被接受的重复，
要求**双向可见**：

- 第一处注释已写进 `doctor.py` 第 6 组函数开头（Phase 1 已完成）。
- **第二处注释**原计划在 Phase 2 移动 `check_codex_backend.py` 时同批加 `--structure-only` 并把第 6 组改为 subprocess 复用。
  **该计划已按裁决 R17 调整为「未排期」**：Phase 2 只做了 移位 + `--codex-bin` + 友好报错，**没有**加 `--structure-only`，
  也**没有**改第 6 组。理由是「计划未列 = 未声明的范围扩张」，且会让 doctor 同时依赖「外部脚本可执行 + 刚移位」两个变化条件。
  因此 `doctor.py` 第 6 组与 `check_codex_backend.py:load_role_configs` 的**这份重复仍是「唯一被接受的重复」**，双向留痕照旧有效，
  只是收口动作（subprocess 复用 + 删自实现）**推迟到未来某个排期**，不再预告为 Phase 2 交付。

  ```text
  # check_codex_backend.py 侧（未排期）：将来若给它加 --structure-only，
  # 须回头把 doctor.py 第 6 组改为 subprocess 复用并删除那段自实现。Phase 2 未做此事（R17）。
  ```

### 项目侧既有缺陷（不属本仓库，登记不顺手改）

14. diamond-agent 的 `.cursor/agents/module-investigator.md` frontmatter 是 `model: gpt-5.6-sol[]`（实测原文），
    形态像占位符替换残留，可能导致该角色在 Cursor 侧调用异常。
    **不在本仓库范围**，建议登记为 diamond-agent 的 `docs/operations/issues.md` 条目，由该项目自行修复。
    它同时是「模板渲染必须校验无残留 `{{`」这条设计的现成反面证据 ——
    `bootstrap_project.py` 的残留占位符自检就是为了让这类缺陷机械化拦住（命中即 `exit 1`，一个文件都不写）。


---

## ⑥ Phase 2 契约增量（对 `phase1-design.md` 既有契约的修订）

> 为什么记在这里而不是直接改 `phase1-design.md`：本阶段硬约束规定 Executor 的全部写入只能落在暂存区 `repo/` 与
> `/tmp`，且不得修改 Designer 已返回的设计文档；`phase1-design.md` 两者都触碰。故按「文档与实现不得两套说法」的要求，
> 把 Phase 2 对 Phase 1 既有契约的**增量修订**集中记录在本过程真源里，与实现同源。下面每条注明它修订的是
> `phase1-design.md` 的哪一节。

| 契约 | 修订的 phase1-design 节 | Phase 2 增量（实现已落地） |
| --- | --- | --- |
| **install `--json` schema 加 `scope`** | §2.4 | 每行新增 `scope` 字段（`skill` / `root`）。**根级条目**（`missing-root`、创建目标根等）`name` 改为符号名 `"<target-root>"`（不再以 `/` 开头），真实路径放进 `path`。判据：`all(not r['name'].startswith('/') and 'scope' in r for r in results)` |
| **bootstrap 写盘事务性** | §3.5 | 写盘改为**全或无**：任一文件写失败（`OSError`）或围栏写入后复检不过，本次运行已写的文件**全部还原**（新建→`unlink`；`--force` 覆盖→从备份 `shutil.move` 回原位；围栏→用 `original_bytes` 覆盖/`unlink`）。退出码：复检失败 **1**、`OSError` **2**。FAIL 文案含「已回滚 N 个文件、磁盘状态与本次运行前一致」；回滚自身失败时逐个列出残留路径 |
| **围栏完整性第 2.5 步** | §3.6 | 在「解析 → **完整性** → 围栏外 `[agents.*]` → 比较/追加」顺序里，于比较/追加**之前**插入完整性检查。**不变量**：重写区间严格等于唯一一对 `OPEN`/`CLOSE` 之间（含标记行）。`OPEN`/`CLOSE` 各 0 处 = 全新文件的正常态，放行到第 5 步 EOF 追加；**部分缺失 / 多次出现 / 顺序颠倒** = 损坏态，`exit 1`「围栏标记不完整」，**绝不追加**（追加会造出第 2 个 OPEN，使下次 `--force` 跨越围栏外用户内容） |
| **bootstrap envelope 加 `warnings`** | §3.5（C2） | 输出 envelope 新增 `"warnings": []`，收 `probe_note` 与 `CURSOR_MODEL_WARNING`；`_fail` 路径也带该键。两个 Cursor 模型未全显式给出时才触发 `CURSOR_MODEL_WARNING`（全显式传参 → `warnings == []`）。**文案本体未改**（issue 6 属 Phase 3） |
| **bootstrap 删 `--codex-home`** | §3.x（C3） | 删除 `--codex-home` flag、`if args.codex_home:` 两行、`_common` 导入里的 `codex_home`。`--help | grep -c codex-home` = 0、`grep -c codex_home bootstrap_project.py` = 0 |
| **doctor 第 9 组新增 `9.2` 跨组件契约校验** | §4.2 | 用**内容锚点**（非行号）机械校验 `stack.py` 源码：断言 4 条池解析正则 `r"…"` 字面量、`def parse_work_plans` / `def parse_issue_index` / `def load_layout` 三个函数定义、以及布局键与默认值的 4 行字面量逐字存在；不成立 → **error**。`doctor.py:61/425` 与 `bootstrap:302` 的行号注释改为函数名锚点 |
| **doctor id 统一重编号 + 唯一性** | §4.2（issue 2/B2） | `main()` 收齐 rows 后**按组统一重编号**（`for i,r in enumerate(rows_of_group,1): r["id"]=f"{g}.{i}"`），删 `_group8`/`_group9` 里硬编码的 `2`/`None`；末尾加 id 唯一性断言（不成立 `exit 2`）。`.0` 形态的 id 示例随之改为 `.1`。注：契约行 id 依赖该组行数——健康池下字面为 `9.2`，无 `--project` 时第 9 组只 1 行则为 `9.1` |
| **doctor 第 10 组判据放宽** | §4.2 / §4.4（D3/R14） | 正则由 `\.agents/skills/[A-Za-z0-9_-]+/scripts/` 放宽为 `\.agents/skills/[A-Za-z0-9_-]+/`（去 `/scripts/` 尾巴），扫描范围由 `skills/*/SKILL.md` 加到 `skills/*/references/*.md`。命中由 3 处扩到 **6 处 / 5 文件**，全修后归零。**放宽是加强而非降低门禁**：不放宽则 B4「warn 归零」会在仍有 3 处失效引用时假 PASS。§4.4 补「为什么不是噪音」：本正则与 `scratch/workbench/…` 命中集合零交集 |
| **doctor 第 1 组 manifest 错误行去前缀** | §4.2（issue 3/C1） | `_group1` 的 manifest 错误行改为 `object=problem.split(":",1)[0]`、`message=problem.split(":",1)[1].strip()`，使 `message` 不再以 `object+":"` 开头（无 `1.x` 行满足 `message.startswith(object+":")`） |
| **doctor 第 8 组 config.json 感知** | §4.2（D4/R15） | `_group8` 中若 `<project>/workstacks/config.json` 存在：解析失败/非法 = **1 行 error**（文案与 `stack.py` 同源）；声明了非默认值 = **1 行 warn**「第 8/9 组按默认路径检查，结论不覆盖自定义位置（对齐留待 Phase 3）」；文件存在、合法、且全部取默认值 = **1 行 ok**「存在且全部取默认值（等价于没有该文件）」（裁决 R22：fail-visible 优于静默；ok 不是 warn，不影响 B4 与 diamond-agent 零变化）；**文件不存在 → 不加任何行**（保证 diamond-agent 输出零变化，不破坏 V1/等价性） |
| **doctor 路径与「未来工作」表述** | §4.2（耦合 #3/#4） | `doctor.py:222/224/499` 的旧路径改为新路径；`224-225` 注释改为「**未来工作（未排期）**」（对应 R17 的 `--structure-only`） |
| **stack.py 根解析四趟 + 配置发现** | §4.x（E1/E2/Q2/Q3） | `stack.py` 重构出唯一真源 `_markers_root(start)`（四趟：`.git` / `workstacks` / `AGENTS.md` / `.codex`）+ `find_repo_root(start)`（None 时 `die(2,…)`，文案含 4 个标记、`--repo-root` 提示、bootstrap 提示）；`--repo-root` 只覆盖**起点**，仍向上走到真根（语义未变成「权威根」）。新增 `Layout` / `load_layout` / `layout_for_root`，发现固定位置 `<repo>/workstacks/config.json`（不随 `workstack_root` 变，否则自指循环）；5 类非法（未知键 / 绝对路径 / `..` / 非 str / 非 object）各 `exit 2` 且文案含出错键 |
| **survey 空池 exit 0** | §4.x（E3/Q1③/R16） | 两池**文件都缺失** → 打印第一步 + 第二步标题 + 「⚠ 未解析到任何池条目，且两个池文件都不存在」+ bootstrap 指引 → **`return 0`**，且不打印第三步；池文件**存在但解析 0 条** → 保留既有 warn 行 → **`return 0`**。两种情形输出**可区分**，不合并成同一句话 |
| **check_codex_backend.py 移位 + 改造** | §4.x（E5/Q6） | 从 `skills/multi-phase-plan-orchestrator/scripts/` 移到 `skills/single-phase-execution-loop/scripts/`（旧目录 `rmdir`）；加 `--codex-bin`（default `"codex"`）；`main()->int` + `raise SystemExit(main())`；全部 `ValueError/FileNotFoundError/OSError/tomllib.TOMLDecodeError` 收敛为 stdout 上 JSON `{"status":"not-ready","reason_class":"role-config|model-binding|probe",…}` + `exit 1`，**零 traceback**；保留 `config_file` 越界校验（硬约束 7）；**不引入 `_common` 依赖**（保持自包含，第 2 组 `py_compile` 才成立） |
| **路径表述占位符约定** | §4.x（Q7） | 自指 = `<本 skill 目录>/scripts/stack.py`；跨 skill = `<skill 根>/<slug>/scripts/xxx.py`（`<skill 根>` = 仓库 `skills/` / 全局 `~/.codex/skills/` / 项目 `.agents/skills/`）。后缀 `<slug>/scripts/…` 在三种布局下都不变，故既布局无关又被 doctor 第 3 组校验。每个用到占位符的 `SKILL.md` 在首次使用处带 1 行占位符定义 |

**等价性保证（硬约束 6）**：以上所有 `stack.py` 改动对 diamond-agent 的输出**逐字不变**——diamond-agent 无
`workstacks/config.json`（配置发现走默认值）、池非空（survey 不触发 exit-0 分支）、根解析起点能命中 `.git`。
V1 等价性回归（新旧脚本紧邻双跑 + `<SELF>` 归一化）实测 `RESULT fail=0`，5 个命令 stdout/stderr/exit 全同。
---

## ⑦ Phase 3 契约增量（对既有契约的修订；**取代 ⑥ 之「13 项」记载**）

> 占位符约定（同 README.md）：<方法论仓库> = agent-methodology 仓库根目录（装着 skills/、scripts/、templates/ 的那一层）。

与 ⑥ 同理，本节只放**跨阶段仍然成立的结论**；阶段性状态与进度登记在项目侧文档里。
⑥ 是 Phase 2 的增量，作为**历史节不改写**；凡 ⑥ 与本节冲突处一律以本节为准。具体地：
⑥「doctor id 统一重编号 + 唯一性」行记载的**位置化编号**（`id = <组号>.<组内 1-based 序号>`，
健康池下契约行字面为 `9.2`、无 `--project` 时为 `9.1`）以及由它派生的检查项总数，**自 Phase 3 起作废**，
由 ⑦.1 的稳定语义 id 与 ⑦.2 的行数期望取代。

### ⑦.1 doctor 检查 id：位置化 → 稳定语义 id（P3-8）

`id = <组号>.<稳定键>`。键由各组在 `_row(..., key=…)` 处一次性给出，`main()` 收齐全部 rows 后由
`_assign_ids` 统一拼装（旧函数 `_renumber` 已删除）；唯一性断言保留（重复 → `exit 2`）。
`--json` 的 `checks[].*` 字段集与 `summary` 口径**未变**（仍是 `group/id/level/object/message/detail`；
`key` 只存在于内存行，不进 JSON）。

**键表（唯一真源）**：

| 组 | 健康态行的键 | 违规诊断行的键 |
| --- | --- | --- |
| 1 仓库自完整 | `<skill 名>` | `manifest-<i>`（清单不可信）、`missing-<name>`（同包 skill 缺失） |
| 2 脚本可编译 | `<脚本 stem>`；无可编译脚本时 `none` | `pyc-dir`（py_compile 输出目录建不出来） |
| 3 同包引用 | `refs` | `refs-<i>` |
| 4 全局挂载 | `<skill 名>`；`--no-global` 或挂载根缺失时的单例行 `global` | 同键（level=fail） |
| 5 `.system` 未越界 | `system`（单例） | 同键 |
| 6 项目角色配置 | `<role>`；未给 `--project` 时的单例行 `roles` | `codex-dir`、`config`、`<role>` |
| 7 项目侧软链 | `<skill 名>` + `cursor-skills` | 同键 |
| 8 栈目录就位 | `gitignore`、`pointer`、`config` | `dir`、`gitignore-history`、`gitignore-pointer`、`config` |
| 9 长期池 + 跨组件契约 | `pool`、`contract` | `plan-file`、`issue-file`、`contract` |
| 10 暂存期路径前缀 | `legacy-prefix`（单例） | `legacy-<i>` |
| 11 栈内容门禁（opt-in） | `verify`（单例） | 同键 |
| 12 运行时指引布局无关 | `runtime-paths`（单例） | `bare-<i>`、`placeholder-<i>` |
| 13 三角色契约镜像 | `role-headings`（单例） | `role-headings-<i>` |

**索引规则（防新漂移）**：文档与消费者**只准索引健康态键**——它们来自对象身份（skill 名 / 脚本 stem /
角色名 / 单例检查的固定名），故**跨参数稳定**，同一检查在 `--project` 与 `--no-global` 下 id 相同。
诊断行的 `-<i>` 后缀是「本次输出里的第 i 条违规」，随仓库状态变化，**不得被文档、脚本或 issue 台账当作稳定标识引用**。

### ⑦.2 doctor 行数期望（B4 的新判据）

**本节是仓库内唯一允许写死这两个数字的位置**；`doctor.py` / `README.md` 一律只写「行数随参数与仓库状态变化，
以 `--json` 的 `summary.total` 为准」，不写具体数字（写死即第二真源，改判据时必然漂移）。

| 参数组合 | 行数 | 构成推导 | level 分布 |
| --- | --- | --- | --- |
| `--no-global`（无 `--project`） | **15 项** | 组1×5 + 组2×2 + 组3/4/5/6 各×1 + 组9 `contract`×1 + 组10×1 + 组12×1 + 组13×1（组7/8 无 project → 0 行；组11 opt-in 未开启 → 0 行） | ok 15 / warn 0 / error 0，`exit 0` |
| `--project <FP> --no-global` | **26 项** | 上表 15 项去掉 `6.roles` = 14，再加 `6.designer`/`6.executor`/`6.reviewer`×3 + 组7×6（5 个 skill + `cursor-skills`）+ 组8×2（`gitignore`、`pointer`）+ `9.pool`×1 | ok 20 / warn 6 / error 0，`exit 0`；warn 恰为 `7.<5 个 skill 名>` + `7.cursor-skills`（假项目未装软链，预期内） |

`<FP>` 的**固定构造**（26 只绑定这一条命令，换构造即失效）：

```bash
FP=$(mktemp -d /tmp/p3-fp-XXXXXX)
python3 <方法论仓库>/scripts/bootstrap_project.py "$FP" --backend codex --model m
python3 <方法论仓库>/scripts/doctor.py --project "$FP" --no-global --json
```

⚠ **不得把 26 复用到任何其他场合**（P3-10：项数对假项目构造方式敏感，历史上出现过 23 / 24 / 25 三个
「都算通过」的 N，等于没有判据）。`--no-global` 与 A7 的既有结论仍有效：第 10 组 0 warn、
且只有 `--no-global`（或全局挂载确实就位）时才 `exit 0`；id 变为 `10.legacy-prefix`。

### ⑦.3 新组 12「运行时指引布局无关」（P3-9 + P3-15）

把 Phase 2 的 B7 纯文本 grep **固化成一个检查组**（B7 只覆盖 `skills/` 下 3 个脚本名的裸相对路径，
`scripts/`、`docs/`、`templates/` 内的同类文案扫不到；那次缺陷是靠人工 grep 才发现的）。

**判据原文**：

- 检查 A（裸路径）：正则 `(?<![/\w.-])scripts/(?:bootstrap_project|install|doctor)\.py` 命中 → `fail`，id `12.bare-<i>`，
  detail 含 `文件:行号` + 修法（写成 `<方法论仓库>/scripts/…` 占位符形态，或输出解析后的真实路径）。
  负向后顾天然放行 `<方法论仓库>/…` 占位符形态、绝对路径、`{repo}/…` f-string 拼接、`skills/<slug>/scripts/…` 跨 skill 形态。
- 检查 B（占位符定义行，正向断言）：文件含 `<方法论仓库>` 但没有匹配 ``<方法论仓库>\s*[`"']{0,2}\s*[=＝]`` 的行 → `fail`，id `12.placeholder-<i>`。
- 全过 → 单 ok 行 `12.runtime-paths`。
- 扫描范围（排序、去重）：`README.md` + `docs/*.md` + `scripts/*.py` + `templates/**` +
  `skills/*/SKILL.md` + `skills/*/references/*.md` + `skills/*/scripts/*.py` + `skills/*/agents/*.yaml`。

**已知盲区**：

1. 只匹配**路径形态**。「裸程序名」（如「重跑 bootstrap_project.py」「跑一下 install.py --check」）**无机械覆盖** ——
   按名提及的散文在 docs/README 里实测约 20 处，Phase 2 B7 已定性其非缺陷；泛匹配会把过程真源文档变成
   永久黄噪音，或逼着重写历史叙述（违背「文档与实现同源」的本意）。
2. 三个脚本名写死在 alternation 里：仓库新增第 4 个仓库级脚本时必须**同批**扩这个 alternation，否则新脚本的裸路径指引不被看护。
3. 正则字面量**不自命中**是靠 alternation 的书写形态保证的（源码里出现的是 `scripts/(?:…`，`scripts/` 之后紧跟 `(`）。
   若改写成等价但形态不同的正则（例如拆成三条），就会自命中；改时必须重跑阴性/阳性对照。

### ⑦.4 新组 13「三角色契约镜像一致」（决策 ④）

- **真源**：`skills/single-phase-execution-loop/references/role-contract.md` §4 的 `<!-- role-headings-canonical … -->` 锚块。
- **正向断言**：锚块里每个字段名在该角色的 `templates/codex-agents/<role>.toml` 与 `templates/cursor-agents/<role>.md`
  两个模板里都以子串出现。
- **反向断言**：codex 模板里以中文顿号枚举的标识符串（正则 `[a-z][a-z0-9_]*(?:、[a-z][a-z0-9_]*)+`）中，
  必须存在一个其**全集与锚块该角色的字段集相等**；否则 `fail`。
  为什么必须有反向：只查「锚块 ⊆ 模板」的话，**锚块少写一个字段**这条最典型的漂移反而测不出来 ——
  模板仍然满足子串断言，本组会在契约已经被削掉一项时安静地变绿（假 PASS）。
- 锚块缺失 / 重复 / 未闭合 / 角色行不可解析 / 未知角色 / 字段名非法 / 缺角色行 / 字段为空 → 一律 `fail`
  （fail-closed），id `13.role-headings-<i>`；健康 → 单 ok 行 `13.role-headings`。
- **已知盲区**：① 只看护**仓库内** 6 个模板 ↔ 锚块，已渲染到各项目 `.codex/agents/*.toml`、
  `.cursor/agents/*.md` 的产物不在断言范围（属新增检查组，登记为 Phase 4b / 未来工作）；
  ② cursor 模板只做子串断言——它们用 `## <字段名>` 分节与 YAML 代码块两种形态，没有统一的机器可读枚举，
  故反向全集断言只对 codex 模板成立；③ 断言的是**字段名在位**，不断言字段的**语义描述**未漂移。

### ⑦.5 组 1 齐全性（G1）与「不硬编码 skill 名」的表述限定

- 新增模块常量 `CANONICAL_SKILLS`（5 个名字，来源 = 全局硬约束 5「skill 名不变」）。
- `_group1` 末尾对 `set(CANONICAL_SKILLS) - set(磁盘实存名单)` 逐个产 fail 行：id `1.missing-<name>`、
  message「同包 skill 缺失（哪一层没装：仓库 skills/）」、detail 含期望路径与现有名单，并说明
  「全局层与项目层的缺失分别由第 4 / 第 7 组报告，本行只判仓库自身」。
- **缺才报**：健康态零新增行，故不影响 ⑦.2 的行数推导。
- 为什么必须有它：`_common.iter_skills` 只枚举磁盘实存的 skill，删掉一个 skill 目录时第 1 组只会少一行 ok、
  **不报任何 fail**——「本包承诺分发的 skill 少了一个」这条最该红的信号反而静默通过（实测缺口）。
- **表述限定**：README「目录约定」的 `skills/` 行已补「例外：`doctor.py` 持有本包规范 5 skill 名单
  （`CANONICAL_SKILLS`）仅用于齐全性判据；挂载/扫描逻辑仍按磁盘驱动」。`scripts/_common.py:iter_skills`
  docstring 里的同句「不硬编码 skill 名」需要同样限定，但 `_common.py` **不在本批改动白名单内**
  （Phase 3 要求它与真源逐字节一致），故本批只在 ⑦ 登记、留待后续批次同批修改。实质上该表述仍然成立：
  名单只服务齐全性判据，挂载与扫描逻辑完全由磁盘驱动。

### ⑦.6 组 3 的外部 skill 启发式（issue 7）

- **规则**：`$<slug>` 命中且 slug 不在仓库 `skills/` 时，**仅当同一文件内**该 slug 也以
  `<slug>/{references,scripts,agents,SKILL.md}` 形态出现（同包意图证据）才判 fail；否则视为 Codex 自带的
  外部 skill 点名（`$template-creator`、`$skill-creator` 之类），跳过并在 ok 行 message 里计数披露
  （`另有 M 处 $<slug> 视为外部 skill`）——**不静默**。
- 刻意**不引入** `--external-skill` 白名单：零配置优先；白名单会把维护成本转嫁给每个 CI 与文档消费者，
  而它的通道目前无人消费。
- `--expect` 行为不变。
- **已知漏报**：同包 `$点名` 所在文件恰好没有任何路径引用时，会被当成外部 skill 放过。

### ⑦.7 issue 6：`CURSOR_MODEL_WARNING` 新文案

- 旧文案把**来源项目名**（`diamond-agent 现值`）与**本活动内部编号**（`open_questions Q4`）带进每一个新项目，
  而 `open_questions` 只存在于本活动的 scratch 设计文档、**不会随仓库 promote** → 新项目里读到它们只会一头雾水。
- 新文案**由默认值常量派生**（f-string 引用 `DEFAULT_CURSOR_MODEL` / `DEFAULT_CURSOR_EXECUTOR_MODEL`），
  形态为「Cursor 模型名未显式指定，使用仓库默认值：designer/reviewer=… 、executor=…（未验证在他机可用）；
  可用 `--cursor-model` / `--cursor-executor-model` 覆盖」。**本节刻意不抄录具体模型名**：
  抄录即第二真源，改默认值时必然漂移；要看当前值请读 `bootstrap_project.py` 的常量或跑一次 `--dry-run`。
- 触发条件不变：只有「本次确实用上了仓库默认值」时才发（两个 Cursor 模型都显式给出 → 不发）。

### ⑦.8 占位符统一与定义行（决策 ③ + P3-15）

- 仓库内曾并存两种词形：`<本仓库>`（README×5、bootstrap docstring×3、install docstring×2，共 10 处）与
  `<方法论仓库>`（`stack.py` 2 处）。本批统一为 **`<方法论仓库>`**，残留 `<本仓库>` = 0 处。
  为什么选它而不是反过来：R30 已裁定 `<方法论仓库>` 是运行时唯一诚实形态——全局安装后用户机器上
  未必有仓库克隆，写「本仓库」会暗示一个不一定存在的 cwd；改名则属未申报的范围扩张。
- 含该占位符的文件**逐一放定义行**，机械形态（= 组 12 检查 B 的判据原文）：
  同文件存在匹配 ``<方法论仓库>\s*[`"']{0,2}\s*[=＝]`` 的行。
- 本批落点共 **6 个文件**：`README.md`（「快速开始」代码块前的 `> **占位符约定**：…` 引用行）、
  仓库级三脚本 `install.py` / `bootstrap_project.py` / `doctor.py`（均在 `<方法论仓库>/scripts/` 下）、
  `skills/campaign-work-stack/scripts/stack.py`、`skills/single-phase-execution-loop/scripts/check_codex_backend.py`。
  脚本侧一律是模块 docstring 之后的**一行 `#` 注释**，5 处文本逐字同形；`doctor.py` 例外——它的 docstring
  「用法」块本身就用该占位符，故定义行放在 docstring 内紧邻首次使用处（同一句话，只是所在语法位置不同）。
  `docs/migration-diamond-agent.md` 因本节引用该占位符，也在节首放了一行定义（即本节开头那条引用）。
- 另一类**不需要占位符**的场景：doctor / install 自己知道仓库根（`Path(__file__).resolve().parents[1]`），
  输出里直接给**解析后的真实路径**（f-string 拼 `repo`），比占位符更可用。本批已把 9 处裸仓库级相对路径
  运行时指引改成这种形态（`doctor.py` 8 处：组 4×3、组 6×2、组 7×2、组 8×1；`install.py` 1 处）。
- RR29 同批关闭：`check_codex_backend.py` 的 `HINT_ROLE_CONFIG` 由裸程序名改为
  ``运行 `<方法论仓库>/scripts/bootstrap_project.py <PROJECT> --backend codex` `` 的占位符形态
  （裸程序名只在「cwd 恰好是仓库根」时才照做得通，而本脚本调用方的 cwd 是**项目根**）。

### ⑦.9 `campaign-work-stack` 的 description 治理（13 行 → 8 行）

- 实测只有 `campaign-work-stack` 超标（frontmatter `>-` 块体 13 行）；其余 4 份为 3 / 2 / 1 / 1 行，均 ≤8，本批**不动**。
- `allow_implicit_invocation` **保持现值**：它不在任何 `SKILL.md` frontmatter，而在 `agents/openai.yaml` ——
  `explain-task-failure: true`、`guided-goal-orchestrator: false`、`campaign-work-stack: true`
  （附「survey/show/stacks/propose/verify/retro 全只读」的理由注释）；`multi-phase-plan-orchestrator` 与
  `single-phase-execution-loop` **没有 openai.yaml**。3 个 yaml 全部不在本批改动白名单内（与真源逐字节一致），
  即「隐式调用只落在只读命令上」这条性质由文件不变性机械保证。
- **27 个必保触发信号词**（逐词 grep ≥1）：总目标推进栈、campaign、先登记再决定、survey、长期待办池、
  启用与恢复路由、唯一指针、还剩什么、做到哪了、别丢了、接下来做什么、要不要建栈、用哪个栈、工作计划、
  下一步做什么、问题清单、复盘、弯路、改了主意、修订判据、任务树、压缩、换模型、交接、单步问答、
  guided-goal-orchestrator、single-phase-execution-loop。
- **允许丢失**（已确认可接受，同义触发词已保留、27 词清单机械把关）：「现在推进到哪个子任务」（≈做到哪了）、
  「从计划里选一个」（≈工作计划）、「修订某一帧的判据」（→修订判据）。若日后真实使用中发现触发率下降，
  可在 8 行额度内回补，届时的替换对象由用户点名。
- 正文（frontmatter 以下）**零改动**。

### ⑦.10 接线规则收敛：原位置 → 新位置映射

| 原位置 | 新位置 | 处置 |
| --- | --- | --- |
| `single-phase-execution-loop/SKILL.md`「## 推进栈接线」的「时点 × 机械动作 × 强度」全表（8 行，含 `verify` fail-closed 行、`amend`/终态帧不可改写行、`retro` 行、禁止 `ensure`/首次 `push` 行） | `campaign-work-stack/references/activation-and-recovery.md`「### 通用接线动作表（三个编排身份共用）」 | **逐字迁入** |
| 同节「`verify` 失败意味着…」与「`retro` 同理不是可选项…」两段 | 同文件「### `verify` 门禁与 `retro` 语义」 | **逐字迁入** |
| 同节「### 栈帧与 Phase 的对应关系」小节（4 条 bullet） | 同文件「### 栈帧与 Phase / 阶段的对应关系」 | **逐字迁入**（标题加「阶段」以覆盖 guided 身份，正文 4 条 bullet 未改），并补一行指向 role-contract.md §3 的第 1 类分流 |
| `single-phase-execution-loop/SKILL.md` Step 0/1/2 的三份「必须输入 / 必须输出」清单、Reviewer YAML 代码块（七字段原样）、及其后「`residual_risks` 与 `issues` 同样必须逐条 `capture`」段 | `single-phase-execution-loop/references/role-contract.md` §2 | **逐字迁入** |
| 同文件「## FAIL 分流规则（核心）」四类 + 「### 失败后的通俗解释」两段 | 同文件 §3 | **逐字迁入**，并补一行「受控目标模式覆盖第 2 类」的指向 |
| 同文件「### 本 Skill 是三角色字段契约的真源」节 | 同文件 §1 真源声明 | 语义迁入：真源身份由本 Skill 转移到 `role-contract.md`；原节位置留一行指针 |
| `guided-goal-orchestrator/SKILL.md`「#### 角色字段契约…」节的字段名枚举 | 引用 `role-contract.md` §2 | 删除枚举（枚举即第二真源）；**覆盖表与「禁止把授权强度参数化」整段原样保留** |
| `guided-goal-orchestrator/SKILL.md` 绝对约束 9 的探测/申请/拒绝处置细节与理由句 | 细节 → 引用 activation-and-recovery 身份表 guided 行；理由句（「阶段间收尾发生在 Goal 释放之后，栈是唯一状态载体」）→ **逐字迁入**该身份表 guided 行 | 约束 9 压缩为 2 行（≤3）；**约束 8 的 `verify` `exit 0` 门禁原样保留**，强度未降 |
| `guided-goal-orchestrator/SKILL.md`「#### 推进栈接线」与「## 恢复与输出」的探测/语义匹配细节 | 引用 activation-and-recovery | 各留一行引用 + 覆盖项；guided 特有展示义务（`show` 的推进树 + 位置指针两段原样、`retro` 三段）**保留** |
| `multi-phase-plan-orchestrator/SKILL.md`「启动时必须」第 6 条 | 引用 activation-and-recovery 身份表 multi-phase 行 | 压缩为 3 行（≤3）；覆盖项保留「栈绑总目标、不得为新一轮另起」与「存在未关闭帧先请示收口或 `parked`」 |
| `multi-phase-plan-orchestrator/SKILL.md`「阶段结果决策」节末「接线细节以 `single-phase-execution-loop` 的『推进栈接线』章节为准」 | 改指 activation-and-recovery「各编排身份的接线」+ `role-contract.md` | 消除指向已瘦身章节的**悬空指针** |

三个编排 SKILL.md 各留「一行引用 + 本身份覆盖项」，覆盖项就地可读、强度不低于真源；
接线规则的细节从此只有一份。`grep -rl '| 时点 | 机械动作 | 强度 |' skills/` 恰命中 1 个文件
（activation-and-recovery.md），是该收敛的机械判据。

### ⑦.11 决策落档（① ~ ⑤）

| 决策点 | 裁定 | 理由摘要（备选方案的取舍） |
| --- | --- | --- |
| ① doctor id 方案 | **稳定语义 id**，不搞「固定槽位 + `skipped`」 | 槽位方案会让 `--no-global` 行数膨胀到约 30、需新增 level、改 summary/JSON 消费口径，churn 大而收益相同（「跳过的检查也可见」这项收益已由 N/A 行承担）；语义 id 与既有 `9.pool`/`9.contract` 命名先例一致 |
| ② issue 7 | **同文件共现启发式**，不引入 `--external-skill` | 计划验收原文（零参数 `exit 0`）只有启发式满足；白名单通道目前无人消费，属投机通用性 |
| ③ 占位符 | 统一 **`<方法论仓库>`** | 双词形并存正是本批要消灭的病；改自解释新名属范围扩张（R30 已锁定形态，且定义行落地后已自解释） |
| ④ 6 个角色模板 | **保持运行时自包含**，不指针化；重复由 doctor 组 13 看护 | 模板是 bootstrap 载荷，渲染进项目后必须脱离本仓库独立生效；指针化会让角色契约依赖运行时文件解析（脆弱，且 Cursor 侧无对应发现机制）。收窄 grep 口径缓办则留下无看护的第二真源，违背本批目标 |
| ⑤ 组 12 判据形态 | 裸路径正则 + 占位符定义断言，**不做**裸程序名泛匹配 | 按名提及的散文实测约 20 处，Phase 2 B7 已定性非缺陷；泛匹配会把过程真源文档变成永久黄噪音或逼着重写历史叙述 |

**⑤「Phase 3」第 8 条的收口口径**：原措辞「消除 6 个角色模板之间的正文重复」按决策 ④ 解释为
「消除**语义真源**的重复」，而非「消除模板正文的重复」——模板正文重复是刻意保留的运行时自包含性质，
由组 13 机械看护其不漂移；语义真源的唯一化在 `role-contract.md` 完成。

### ⑦.12 结构现状

Phase 1 口径的 32 文件 / 21 目录是**历史基线**（见 ④）。Phase 3 后现状 = **33 文件 / 22 目录（含仓库根）**，
推导式：`32 + 1`（新增 `skills/single-phase-execution-loop/references/role-contract.md`）/
`21 + 1`（新增目录 `skills/single-phase-execution-loop/references/`），两者均按「含仓库根」口径。
机械判据：`find <repo> -type f | wc -l` = 33、`find <repo> -type d | wc -l` = 22、
`find <repo> \( -name '__pycache__' -o -name '*.pyc' \)` = 空。

### ⑦.13 本批未覆盖的残留（登记，不顺手改）

1. **裸程序名形态无机械覆盖**（⑦.3 盲区 1）：组 12 只匹配路径形态，「重跑 bootstrap_project.py」这类散文不被看护。
2. **`_common.py:iter_skills` docstring 的「不硬编码 skill 名」未同批限定**（⑦.5）：该文件不在本批改动白名单内。
3. **组 13 不看护项目侧渲染产物**（⑦.4 盲区 ①）：若要 doctor `--project` 模式顺带核对项目侧 `.codex/agents/*.toml`、
   `.cursor/agents/*.md` 与锚块一致，属新增检查组，登记为 Phase 4b / 未来工作。
4. **组 3 外部 skill 启发式的已知漏报**（⑦.6）。
5. **`_group8_layout_config` 的 warn 文案仍写「对齐留待 Phase 3」**，而本批并未做该对齐
   （自定义布局下第 8/9 组结论仍不覆盖自定义位置）。该文案不在本批设计列举的改动点内，故未动，登记为待办。
6. **`doctor.py` 仍保留 5 处「第 11 项」的序数表述**（模块 docstring、`:366` 的 N/A 文案、argparse
   `description`、`--project` 与 `--stack-verify` 的 help；其中 docstring 与 argparse `description` 两处
   是 ⑦.2 新措辞「12 个常规检查组 + 1 个 opt-in 组（第 11 项，--stack-verify）」自带进来的），
   指第 11 组这个 opt-in 检查，**组号未变**故语义正确；但它与新措辞共用一个「项」字，留下「项 = 检查组」
   与「项 = 输出行」两种读法的口径歧义（见 ⑦.2 为什么本批不写死行数）。
   **连带后果（判据形态）**：该序数字样在仓库内属**合法存在**（上述 5 处，加上本条自身对它的引用），
   故任何**全仓**范围的「该字样命中为 0 / 为某个固定总数」判据自本批起都**机械不可达**——它会被
   本节的说明文字自身计入，并随文档改写而漂移（自指陷阱）。可机械核验且稳定的形态是把范围限定到
   `README.md`：该文件内不得再出现以「序数 + 项」指代 doctor 自检规模的连写形态（旧措辞已按 ⑦.2
   改写为「12 组 + 1 opt-in 组」），本批实测 `grep -c` = **0**。

---

## ⑧ Phase 4a / 4b 收口增量（2026-09-24）

> 与 ⑥/⑦ 同理，本节只放**跨阶段仍然成立的结论**；过程记录与四栏原文在项目侧
> `scratch/workbench/methodology-skills-extraction/`（`progress.md` 执行留痕、`phase4b-executor-report.md`）。

### ⑧.1 两端同源达成

- 全局挂载（`~/.codex/skills/<name>` 5 条）与项目侧（diamond-agent `.agents/skills/<name>` 5 条）全部为指向
  `agent-methodology/skills/<name>` 的软链，实体副本 = **0**；`.cursor/skills` 仍为二级软链（`../.agents/skills`），
  5 个入口逐一可穿透解析到真源（`SKILL.md` 全可读）。
- 替换前的 5 个项目内实体目录（15 文件）已完整备份到
  `~/client/agent-methodology-backup/diamond-agent-project-skills-4b/`，相对路径口径逐文件 shasum 与替换前冻结清单
  **逐行相同**（含那个游离 `.pyc`，它是 P2-N4/R28 的现成物证；`install.py` 的破坏性替换按约定生成）。
- 依据：Phase 4b 判据 V1 / V1b / V3 / V10（四栏原文由 Executor 与 Reviewer 双侧独立重跑）。

### ⑧.2 doctor 项数的 4b 口径（三变量表；数字复用禁令）

| 口径 | 三变量（`--project` 有无 / `--no-global` 有无 / 目标布局） | `status` | `summary` | `exit` |
| --- | --- | --- | --- | --- |
| A | 无 `--project` + 带全局 + live 真源仓库 | `ok` | `total=19, error=0, warn=0, ok=19` | 0 |
| B | `--project <diamond-agent>` + `--no-global` + live 真源仓库 | `ok` | `total=27, error=0, warn=0, ok=27` | 0 |
| C | `--project <diamond-agent>` + 带全局 + live 真源仓库 | `ok` | `total=31, error=0, warn=0, ok=31` | 0 |
| D | `--no-global` + 无 `--project` + live 真源仓库 | `ok` | `total=15, error=0, warn=0, ok=15` | 0 |

- 闭合算式：`31 = 30 − 5 + 1 + 5` —— 4b 前口径 C 实测 `total=30 / error=5 / exit=1`；4b 后
  `7.<skill>` 5 条由 fail 转 ok（行数不变，第 7 组恒 6 行 = 5 skill + `cursor-skills`），
  另第 8 组新增 `8.config`（ok，`workstacks/config.json` 存在且全部取默认值）1 行；`27 = 26 + 1` 同理。
- **与 ⑦.2 不得互相代入**：⑦.2 的 `15 / 26` 绑定的是 **`mktemp -d` 假项目 + `bootstrap_project.py` 构造**，
  本表绑定的是 **live diamond-agent + live 真源仓库**构造；数值巧合 ≠ 同一判据（41-5 / P3-10）。

### ⑧.3 `stack.py` 的唯一用户可感知输出差

- `survey` 第 109 行内嵌脚本自身路径（`Path(__file__).resolve()`，真源 `stack.py:1608`，全脚本唯一
  `__file__` 用法）。4b 后项目侧入口经软链解析到真源路径，该行比旧实体脚本时代短 4 B：
  算式 `12189 − 12185 = 4 = 81 − 77`（路径长度差 × 出现次数 1）。
- 其余 4 个只读入口（`stacks` / `show` / `verify` / `retro`）输出**逐字节不变**
  （armB(pre) vs armP(post) `diff = 0` 行 × 4；等价性回归在替换前已完成并经用户 G3 确认，2026-09-24）。
- 另两项行为放宽（仓库根发现标记集 1→4、die 文案 1→2 行）只在非 `.git` 目录 / 失败路径显现，同批获用户确认。

### ⑧.4 不变量：真源仓库路径不得变更

- **真源仓库路径 `/Users/bole/client/agent-methodology` 不得移动、改名或删除**：10 条绝对路径软链
  （全局 5 + 项目侧 5）依赖它；断链后项目侧与全局侧的方法论 skill 同时不可见。
- 检测手段：`<方法论仓库>/scripts/install.py --check`（报 `drift`）与 `<方法论仓库>/scripts/doctor.py`
  第 4/7 组（报 `fail`）。
- 破坏性替换的备份目录约定 = `~/client/agent-methodology-backup/`：**不得落 `/tmp`**
  （2026-09-21 19:44 有被外部清理前科）、**不得落 `scratch/`**（项目侧可重建可丢弃区，同日误删事件的靶区）。

### ⑧.5 P2-N6 结案：`survey` 原始字节数是输入侧移动靶

- 机制结论（4b V12 实测）：`survey` 原始字节数 = f(**在飞栈正文**, **长期池条数**, **路径回显**) 的三变量移动靶。
  路径回显实测含**两类**：第 109 行的脚本自身路径（`Path(__file__).resolve()`）与第 79/83 行的【工作计划】/【问题清单】
  仓库根绝对路径回显 —— 后者是 4b 实测对设计前提「`survey` 输出不含仓库根路径」的**更正**（V12 申报件 DR-14）。
  「不以历史字节数为期望值」自 4a 起已制度化，此处维持并给出机制级证据。
- 机制级归因实验（夹具在独立目录 `/tmp/p4b-p2n6/live`，不触碰真实项目；真实 `docs/operations/` 双哈希前后同值）：
  ① **夹具完备性**：完整夹具（`workstacks/` + `docs/operations/` 副本）与 live 输出的 `diff` **恰 2 行**
  （`:79`/`:83` 两条仓库根路径回显行），全部内容行逐字节相同；字节差 `12157 − 12185 = −28 = 2 × (18 − 32)`
  （夹具根路径长度 − 项目根路径长度，出现次数 2）→ 夹具在**内容面**完备，路径回显是唯一偏差变量。
  ② **单变量扰动**：夹具 `issues.md` 末尾加 1 行 ISS 表格行（97 B）→ 输出 Δ = **+56 B** =
  新增 2 条渲染行（类别行 `  验收/证据（1 条）` 27 B + 条目行 `    ISS-900  open         P2` 29 B）
  + `未解决 17 条` → `18 条`（字节差 0）；插入的表格行**不被逐字回显**，而是被渲染为展示格式
  → 「长期池条数」变量被机械证明（设计预期的「Δ 恰等于插入行字节数」被实测更正，同属 DR-14）。
  ③ **不可复现性**：`workstacks/<campaign>/history/` 只有 2026-09-18 / 09-20 两个 `.bak`，Git HEAD 态
  夹具实测 `11081 B`；Phase 2 时点的中间态既未提交也无快照 → `12189 − 12114 = 75`（Phase 2 时点 vs
  4b 时点）归因到**类别**（输入侧漂移）成立，归因到**字段**机械不可达。
- 处置：**不往项目 `docs/operations/issues.md` 立项**。三条理由：① 会改 doctor `9.pool` 的文本
  （`issues.md 17 条` → `18 条`），给健康判据凭空加一个变量；② 该文件是**另一 campaign 的长期池真源**，
  注入方法论条目会污染 `survey` 菜单语义；③ ISS id 有并发撞号风险（现存最大 `ISS-023`，在飞栈正文已出现 `ISS-024`）。

### ⑧.6 4b 新登记 3 条（登记不顺手改）

1. **P4B-N1**：`install.py:333` 的可写性守卫未排除 `--mode check` → `--check`（自称零副作用）在只读目标根下
   `exit=2`（stdout 恰 1 行 `[FAIL] 目标根不可写：…`），与其 docstring「强制零副作用」矛盾。
   建议 1 行修复：守卫条件加 `and mode != "check"`。**4b 不做**（Q4 裁决；避免牵动等价性面）。
2. **P4B-N2**：diamond-agent 的 `tests/core/agent/test_orchestration_backend.py:12` 硬编码旧 backend 脚本路径
   （`.agents/skills/multi-phase-plan-orchestrator/scripts/`），4b 后该路径悬空，3 个 test 会在 `exec_module` 处
   `FileNotFoundError`。该文件未入 Git、CI 干净检出不可见，属他人未提交 WIP，**4b 不修**（Q3 裁决）。1 行补丁文本（登记用）：

   ```python
   # tests/core/agent/test_orchestration_backend.py:12
   -    / ".agents/skills/multi-phase-plan-orchestrator/scripts/check_codex_backend.py"
   +    / ".agents/skills/single-phase-execution-loop/scripts/check_codex_backend.py"
   ```

   API 兼容性已核：真源版保留 `RoleConfig.sandbox_mode`、`load_role_configs(repo_root)`、
   `validate_backend(*, role_configs, active_model, available_models)` 与两条错误文案字面量，新增项全是 additive。
3. **P4B-N3**：`bootstrap_project.py:435` 的 `--force` 备份目录约定默认落 `<TMP>/agent-methodology-backup/<ts>/`，
   与 ⑧.4 的「备份不得落 /tmp」约定同族（P2-N12），未排期。
