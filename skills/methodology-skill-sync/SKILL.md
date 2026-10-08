---
name: methodology-skill-sync
description: >-
  检查或同步 agent-methodology 的全部或指定 skill 到本机已登记项目，复用 install.py
  安全管理项目 `.agents/skills` 软链并保持 DiamondSpins system-ai 的本地 Git 忽略。
  当用户说“同步/分发/暴露方法论 skill”、新增或重命名方法论 skill 后使用；不用于同步业务 skill 或代码发布。
---

# 方法论 Skill 同步

## 定位

本 Skill 是 `agent-methodology` 的分发入口。真源仍是 `<方法论仓库>/skills/`；
它不复制 skill 内容，只把各项目中的直接子项软链对齐到真源。

`<方法论仓库>` = 包含 `skills/`、`scripts/` 和 `templates/` 的 `agent-methodology` 仓库根。

机械动作由：

```bash
python3 <方法论仓库>/scripts/sync_projects.py
```

完成。不要逐项目手写 `ln -s`，也不要在各 skill 中放自己的 init 脚本。

## 授权边界

- `--check` 只读，可直接运行。
- 用户明确要求“同步、分发、暴露、安装到已登记项目”时，可运行写模式。
- 本 Skill 的授权只覆盖软链、本地 Git exclude 登记与同步后检查；不授权 commit、push、改业务文件或运行 DiamondSpins 完整 `ai-init`。
- `--prune` 只删除指向本方法论仓库且真源已不存在的软链；未经用户明确要求清理时不使用。

## 配置

默认读：

```text
<方法论仓库>/.local/sync-targets.json
```

该文件是本机状态，必须被 Git 忽略。脚本在配置缺失、目标重复、项目路径不存在或不是 Git 根时 fail-closed，不扫描整个用户目录猜项目。

## 常用模式

```bash
# 只读检查全部已登记项目
python3 <方法论仓库>/scripts/sync_projects.py --check

# 同步全部方法论 skill
python3 <方法论仓库>/scripts/sync_projects.py

# 新增一个 skill 后只分发它
python3 <方法论仓库>/scripts/sync_projects.py --only <skill-name>

# 显式清理真源已删除的受管软链
python3 <方法论仓库>/scripts/sync_projects.py --prune
```

## 标准流程

1. 新增或更新 skill 后，先运行该 skill 的 `quick_validate.py` 与仓库 `doctor.py`。
2. 先运行 `sync_projects.py --check`，向用户报告哪些项目缺失或漂移。
3. 用户已授权同步时，运行写模式。脚本会先对所有项目做 dry-run；任一目标冲突时全部停止，不进入写阶段。
4. 脚本写入后自动重跑检查。只在总结为 `exit=0` 时宣称同步完成。
5. 报告每个项目的创建、跳过、冲突、失效软链和 exclude 结果；不用“已同步”掩盖部分成功。

## DiamondSpins 暴露语义

DiamondSpins 的 `.agents/skills` 与 `.cursor/skills` 都指向 `tools/system-ai/skills`。
因此 `install.py --project-link` 把软链写入 `.agents/skills` 后，已同时暴露给项目与 Cursor；
不必为了新方法论 skill 运行会重写 AGENTS.md、local rules 和 hook 的完整 `ai-init`。

对 `ignore_links: true` 的目标，脚本会把当前方法论 skill 的真实项目内路径追加到 `.git/info/exclude`，避免本机软链污染业务仓库。

## 安全不变量

- 不复制 skill，不产生第二份真源。
- 不覆盖实体目录、实体文件或指向他处的软链。
- 不自动发现或新增项目；目标必须来自显式本机配置。
- 不调用各业务项目的完整 init、hook 或生成器。
- 不修改、暂存或提交业务仓库的其他文件。
- 单个目标写入后失败时不声称全局回滚；如实报告已完成与未完成目标。
