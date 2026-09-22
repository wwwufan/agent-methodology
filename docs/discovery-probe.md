# skill 发现机制探针结论（稳定版）

本文是「Codex / Cursor 如何发现并列出 skill」这一问题的**结论与证据边界**，是挂载布局决策的依据。
证据采集于 2026-09-20 ~ 2026-09-21，采集对象是迁出前的 diamond-agent 项目与本机 `~/.codex`。

标注约定：凡写「**实测**」的结论都有可复现的观测点；凡写「**未验证**」或「**推测**」的，
**不得**被后续阶段当作设计前提或已证事实引用。

---

## A1 · 探针软链（实测）

在个人根与 Cursor 全局根各建一条指向项目内 skill 的软链：

```text
~/.codex/skills/explain-task-failure  -> <project>/.agents/skills/explain-task-failure
~/.cursor/skills/explain-task-failure -> <project>/.agents/skills/explain-task-failure
```

- 两条软链均可解析：经软链能读到 `SKILL.md` 与 `agents/`，frontmatter 的 `name` 正确。
- `~/.cursor/skills/` 此前**不存在**，由探针 `mkdir -p` 创建（无覆盖风险）；探针结束后已连同该目录一并
  `rmdir` 移除，环境恢复探针前状态。
- 探针目标刻意选 `explain-task-failure`：它是 5 个方法论 skill 中最自包含的一个（无 `scripts/`、
  无 `references/`，只被别人引用），且项目内副本仍在 —— 于是同一个探针能同时回答 A2 与 A3。
- `~/.codex/skills/explain-task-failure` 探针**保留**，作为 A2 / A3 的证据，由 `install.py` 在接管阶段重指真源仓库。

## A2 · Codex 是否跟随软链发现 skill → **是（实测，两个独立观测点）**

| 观测点 | 内容 |
| --- | --- |
| 会话注入的 skill 根清单 | 探针**前**一轮没有 `~/.codex/skills` 这个根；探针**后**一轮出现 `r0 = ~/.codex/skills`，且 `~/.codex/skills/.system` 被当作另一个独立根 `r1` |
| 会话注入的 skill 条目原文 | `explain-task-failure: …（file: r0/explain-task-failure/SKILL.md）` —— 条目路径经软链解析成功 |

判定：`~/.codex/skills` 被识别为**独立的个人 skill 根**，Codex 跟随软链发现 skill。

由此得到的**实测推论**：skill 的安装粒度是「某个根目录下的直接子目录」。
`r0` / `r1` / 项目根三者并列、且条目路径形态都是 `<根>/<skill>/SKILL.md`，
所以**必须逐 skill 建软链**；把整个仓库软链成一条 `~/.codex/skills/<repo>` 不成立。

> **未验证**：把整个仓库软链成一个条目后，其内层 `skills/*` 是否会被枚举。`.system` 被当作独立根是一个
> 特例（它本身就是 `~/.codex/skills` 的直接子目录），不能外推。设计上**不采用**这种做法，故无需先验证它。
> 若要验证：建一条仓库级软链后读下一轮会话注入的条目路径形态即可，零成本。

## A3 · 同名 skill 是否双列 → **不双列（实测）；成因「遮蔽 vs 同源去重」未区分**

同一份注入清单中 `explain-task-failure` **只出现 1 次**，来源标为 `r0`（个人根）；
项目根下同名 skill 的实体副本当时仍在磁盘上（`ls` 可证），但未被列出。

已确认的只是**结果**：清单中该 skill 恰好出现 1 次、来源标为个人根。

### A3 证据边界（**未验证**，不得写成已证事实）

- **「个人根遮蔽项目根」与「同内容合并去重」两种机制本次观测无法区分**：探针两端指向**同一目录**，
  因此两种机制在本次观测下产生完全相同的结果。优先级归属未知。
- 该不确定性**不影响**最终布局，因为布局选定了一条对两种机制都安全的不变量（见下节）。
- 附带核实：`guided-goal-orchestrator` 在两轮清单中都不出现，原因**不是**遮蔽，而是它的
  `agents/openai.yaml` 里写着 `allow_implicit_invocation: false`（只能 `$name` 显式点名）。
  → 判读「某个 skill 不在清单里」时必须区分这两种成因，否则会误判成发现机制故障。

### 不变量：两端只能是**同源**软链

最终布局要求 `<codex_home>/skills/<name>` 与项目 `.agents/skills/<name>` **都只能是指向本仓库同一目录的软链**。
两端内容恒同，于是无论生效机制是「遮蔽」还是「同源去重」，注入清单的结果都一致（每个 skill 恰好 1 条）。
A3 的成因不确定性被这条不变量兜住，不需要先判别它。

**零成本判别观测（留待接管阶段执行，本文不执行）**：把个人软链重指真源仓库、而项目内实体副本**尚未替换**时，
读下一轮会话注入清单中该 skill 条目的 `file:` 路径 —— 标个人根即「遮蔽 / 个人优先」，标项目根即「项目优先」。
唯一暴露窗口是「个人软链已指真源、项目内仍是旧实体副本」这一小段，此时两端内容可能不同；
风险可接受，因为等价性回归在替换项目内副本**之前**执行，回归通过才允许替换，替换完成后该窗口永久关闭。

## A4 · Cursor 是否支持全局 skill → **已由用户明确排除出范围**

用户原话（2026-09-21）：**「不需要考虑Cursor支持全局skill」**。

- 这条回复满足「有用户明确回复」的收口条件，但回复的内容是**把该问题排除出范围**，
  而不是对 Cursor 客户端能力的观测结论。
- 因此本文**不把「Cursor 不支持全局 skill」写成已证事实**（**未验证**：Cursor 客户端对指向仓库外的软链
  的实际渲染行为没有取证；也没有找到可探测 Cursor 模型的 CLI 证据）。
- 结论：**Cursor 全局 skill 支持不在本活动范围内**。Cursor 侧继续走项目内既有链路
  `.cursor/skills -> ../.agents/skills`，该链路不因迁出而改变。

既有链路核实（实测，只读）：

```text
$ ls -ld <project>/.cursor/skills
lrwxr-xr-x  .cursor/skills -> ../.agents/skills
$ ls -1d <project>/.agents/skills/*/ | wc -l
17
```

该软链把 `.agents/skills/` 下 17 个 skill 目录整体暴露给 Cursor。
**证据边界**：上述计数是 **Codex 侧**的可读证据；Cursor 客户端对同一软链的实际渲染**未取证**，本活动也无需取证。

## A5 · 挂载布局分支 → **选定「两端都挂」**

| 探针结果 | 落法 |
| --- | --- |
| **A2 是 + A3 不双列** ← 实测命中 | **两端都挂（个人级 + 项目内软链）** |
| A2 是 + A3 双列 + A4 支持 | 只挂个人级，项目内不留软链 |
| A2 是 + A3 双列 + A4 不支持 | 两端都挂（Cursor 可用性优先），接受 Codex 列表重复，文档注明软链非副本 |
| A2 否 | 改为复制安装 + 漂移检测，Git 仓库仍为唯一真源 |

选定理由：

- **Codex 侧**：个人根软链 → 真源仓库；同名只列 1 条（成因未区分，见 A3），项目内即使保留软链也不会双列。
- **Cursor 侧**：项目内软链 → 真源仓库，经既有 `.cursor/skills -> ../.agents/skills` 链路可见。
- **关键收益：布局不依赖 A4**。因为「两端都挂」在「A3 = 不双列」的前提下对 Codex 无副作用，
  而 Cursor 走的是项目内既有链路；A4 又已被用户排除出范围。
- 一致性要求：真源永远是 Git 仓库；两个挂载点**只能是软链，禁止实体副本**（写入项目侧约定文档）。

---

## 附：探针期间的环境事实（实测，供后续阶段引用）

- `python3` = 3.13.2；`tomllib` 可读，**`tomli_w` 未安装**（`ModuleNotFoundError`）→ TOML 只能读不能写，
  这是 `bootstrap_project.py` 采用「文本级围栏块追加」而不是「读 → 改 → 整体重写」的直接原因。
- `codex` CLI 的 `WARNING: … could not create PATH aliases` 走 **stderr**，stdout 干净
  （用 `2>/dev/null` 与 `2>&1 1>/dev/null` 分离验证）→ 脚本可安全只解析 stdout。
- `~/.codex/config.toml` 确有 `# >>> codexpool-managed >>>` … `# <<< codexpool-managed <<<` 围栏与
  `# codexpool-managed-default` 行尾标记，同目录另有 `config.toml.codexpool.bak.<ts>`
  → **该文件确实被外部工具反复改写**，所以整体重写会毁掉别人的托管机制。
- `~/.codex/skills/` 下有 `.system/`——一个**实体目录**，内含 Codex 自带 skill，且它本身被当作独立 skill 根。
  → 挂载脚本**不得遍历** `<codex_home>/skills`，只按仓库清单的名字集合逐个操作。
