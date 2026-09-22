# 从 diamond-agent 迁出方法论 skill（过程真源）

本文是「把方法论 skill 从 diamond-agent 项目迁出为独立真源仓库」这件事的**过程真源**：
为什么迁、分几步、当前处于哪个中间态、哪些不一致是**故意留着**的、以及后续各阶段必须记得做的事。

阶段性状态与进度登记在项目侧的计划/进度文档里（不入本仓库）；本文只放跨阶段仍然成立的结论与待办。

---

## ① 动机与范围

**动机**：`work-queue-stack`、`multi-phase-plan-orchestrator`、`single-phase-execution-loop`、
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
| 1 | `skills/work-queue-stack/SKILL.md:128` | `S=.agents/skills/work-queue-stack/scripts/stack.py` | 新仓库里该脚本位于 `skills/work-queue-stack/scripts/stack.py`，没有 `.agents/` 前缀；挂载后经软链访问的路径也不是这个 | **2 · 已修**：改为自指占位符 `S=<本 skill 目录>/scripts/stack.py`（首次使用处带 1 行占位符定义） |
| 2 | `skills/single-phase-execution-loop/SKILL.md:163` | 同上形式的 `S=.agents/skills/work-queue-stack/scripts/stack.py` | 同上（这是**跨 skill** 引用：spel 正文里用 wqs 的 `stack.py`） | **2 · 已修**：改为跨 skill 占位符 `S=<skill 根>/work-queue-stack/scripts/stack.py` |
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

8. 抽 `references/role-contract.md`（三角色公共契约），消除 6 个角色模板之间的正文重复。
9. 治理 skill 的 `description` 与 `references/` 结构。
10. 若希望新项目也能用 `module-investigator`（第 4 个角色，AGENTS.md 规定它"只能由用户显式点名，
    不得自动委托"），加 `--with-investigator` 开关。Phase 1 **不 bootstrap 它**。

### Phase 4a / 4b

11. **G2**：确认仓库最终路径与名字。Phase 1 已规避硬编码 —— 脚本一律用
    `Path(__file__).resolve().parents[1]` 推导仓库根，文档里出现路径处写「本仓库」；
    但 `bootstrap_project.py` 写的围栏注释里有一行 `agent-methodology/scripts/bootstrap_project.py`，
    若最终仓库改名，这一行需要同步。
12. **G3**：等价性回归双采比对（`stack.py` 行为不变）必须在替换项目内实体副本**之前**执行。
13. **4b 硬前置**：`explain-task-failure/` 在 diamond-agent 里**未纳入 Git**（实测 `??`），
    用软链替换实体目录前必须先提交它、或确认备份目录里有它，否则那 2 个文件将只剩暂存区一份副本。
    这条风险也写在 `install.py` 的 `conflict(real)` **输出**里，不是只写在文档里。

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
