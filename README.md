# agent-methodology

跨项目复用的**方法论 skill 真源仓库**：把「怎么推进一项复杂工作」的编排方法（分阶段编排、单阶段三角色闭环、
栈式工作队列、证据驱动探索、跨项目同步、受控目标编排、失败通俗解释）从具体业务项目里迁出来，独立成仓库，由各项目以**软链**方式挂载。

本仓库**不放任何业务内容**：没有业务数据、没有项目专属流程、没有某个游戏的资料库。
业务 skill 留在各业务项目自己的 `.agents/skills/` 下。

## 快速开始

完整参数以各脚本 `--help` 为准（本 README 刻意不复制参数表，避免出现第二真源）。

> **占位符约定**：`<方法论仓库>` = agent-methodology 仓库根目录（装着 skills/、scripts/、templates/ 的那一层）；未克隆仓库时如何取得这些脚本见 docs/migration-diamond-agent.md（Phase 4a 补用户指引）。

```bash
# 1) 把本仓库 skills/ 下的全部方法论 skill 软链到 Codex 个人根（<codex_home>/skills）
python3 <方法论仓库>/scripts/install.py

# 2) 只做漂移检测，零副作用（连目标根都不会创建）；安装健康与否以它和 doctor 为准
python3 <方法论仓库>/scripts/install.py --check

# 3) 给一个新项目铺好项目侧前提：三角色配置 + Codex 围栏注册 + 长期池文档 + workstacks/
python3 <方法论仓库>/scripts/bootstrap_project.py <PROJECT>

# 4) 只读自检（12 组 + 1 opt-in 组；行数随参数变化，以 --json summary.total 为准），是"安装健康"的唯一判据（warn 不影响退出码）
python3 <方法论仓库>/scripts/doctor.py --project <PROJECT>

# 5) 把全部方法论 skill 同步到本机已登记项目（先查后写）
python3 <方法论仓库>/scripts/sync_projects.py --check
python3 <方法论仓库>/scripts/sync_projects.py
```

> **写盘事务性**：`bootstrap_project.py` 是「全或无」的——任一文件写失败、或围栏写入后复检不过，本次运行已写的文件
> 全部还原，磁盘状态与运行前一致，不留半成品（退出码：复检失败 `1`、`OSError` `2`；FAIL 文案会写明「已回滚 N 个文件」）。
>
> **仓库布局可配置**：`stack.py` 会在它所运行的项目仓库根发现 `workstacks/config.json`（键 `workstack_root` / `plan_doc` /
> `issue_doc`，缺省即当前默认布局）；schema 见 `skills/work-queue-stack/references/stack-schema.md`。该文件不存在时一切走
> 默认值，输出与未引入此特性前逐字一致（diamond-agent 即此情形）。

项目侧改软链（把既有实体目录换成指向本仓库的软链）用同一条 `install.py`：

```bash
python3 <方法论仓库>/scripts/install.py --project-link <PROJECT> --dry-run
```

## 目录约定

| 路径 | 内容 |
| --- | --- |
| `skills/` | **唯一真源**。每个子目录是一个 skill（`SKILL.md` + 可选 `scripts/`、`references/`、`agents/`）。目录名必须等于 `SKILL.md` frontmatter 里的 `name`——脚本按此扫描，不硬编码 skill 名。例外：`doctor.py` 持有本包规范 7 skill 名单（`CANONICAL_SKILLS`）仅用于齐全性判据；挂载/扫描逻辑仍按磁盘驱动 |
| `scripts/` | 仓库级工具：`install.py`（单目标挂载/漂移检测/卸载）、`sync_projects.py`（已登记项目的批量同步）、`bootstrap_project.py`（新项目 onboarding）、`doctor.py`（只读自检）、`_common.py`（共用真源解析，禁止在脚本内各自复制一份） |
| `templates/` | `bootstrap_project.py` 的载荷：`codex-agents/`、`cursor-agents/`、`codex-config.fragment.toml`、`docs-operations/`、`workstacks/` |
| `docs/` | 稳定文档：`discovery-probe.md`（skill 发现机制的探针结论与证据边界）、`migration-diamond-agent.md`（从 diamond-agent 迁出的过程真源，含暂存期不一致清单与口径注记） |

脚本只用 Python 标准库，不引入 PyYAML 等第三方依赖；仓库根一律由 `Path(__file__).resolve().parents[1]`
推导，与 cwd 无关，也不写死仓库落点（最终路径与仓库名待确认，见 `docs/migration-diamond-agent.md`）。

## 本机同步目标

`sync_projects.py` 默认读 `<方法论仓库>/.local/sync-targets.json`。`.local/` 被 Git 忽略，
只保存当前机器的项目路径；不把个人绝对路径提交进方法论仓库。配置格式：

```json
{
  "schema_version": 1,
  "projects": [
    {"name": "example", "path": "/absolute/project/path", "ignore_links": true}
  ]
}
```

`ignore_links: true` 表示脚本会把方法论软链的真实项目内路径追加到该仓库
`.git/info/exclude`，适合 `tools/system-ai/skills` 中的本机挂载；需要跟踪软链的项目设为 `false`。

## 不变量：两端只能是软链，禁止实体副本

真源永远是本仓库。挂载点——Codex 个人根 `<codex_home>/skills/<name>` 与项目内
`<PROJECT>/.agents/skills/<name>`——**都只能是指向本仓库对应目录的软链**，禁止任何一端留实体副本。

理由：两端内容一旦分叉，"哪一份生效"就取决于发现机制的优先级，而这个优先级本身尚未被完全判别
（见 `docs/discovery-probe.md` 的 A3 证据边界）。两端同源之后，无论生效机制是哪一种，结果都一致。

`install.py` 与 `doctor.py` 都按名字集合逐个操作，**从不遍历挂载根目录**，因此挂载根下的其他内容
（例如 Codex 自带的 `.system/`、你自己装的 skill、项目里的业务 skill）在原理上不可达。

## 编排后端

Codex 与 Cursor 的角色配置**职责分离，不互相作为来源**：`templates/codex-agents/*.toml` 供 Codex
named-agent 后端，`templates/cursor-agents/*.md` 供 Cursor `Subagent` 后端。`bootstrap_project.py`
的 `--backend` 决定铺哪一组，铺 codex 时不读 `.cursor/`，铺 cursor 时不读 `.codex/`。

编排期门禁（三角色模型是否等于当前活动模型）不在 `doctor.py` 的职责内，请另跑
`skills/single-phase-execution-loop/scripts/check_codex_backend.py`（Phase 2 已从 `multi-phase-plan-orchestrator/scripts/` 移到此处的单一执行闭环 skill 下）。
