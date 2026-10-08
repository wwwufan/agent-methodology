# agent-methodology 仓库约定

## Skill 变更的分发门禁

当任务在 `skills/` 下新增、重命名或删除方法论 skill 时：

1. 使用 `skill-creator` 创建或修改 skill，并运行它要求的校验。
2. 运行 `python3 scripts/doctor.py --no-global`，仓库自检必须通过。
3. 运行 `python3 scripts/sync_projects.py`，把当前规范 skill 集合对齐到 `.local/sync-targets.json` 登记的项目。
4. 运行 `python3 scripts/sync_projects.py --check`，只有全部目标 `exit=0` 才宣称分发完成。

新增或更新 skill 的授权包含上述已登记项目的软链同步，但不包含 commit、push、业务文件修改或完整 `ai-init`。
配置缺失、目标冲突或某个项目不可写时必须 fail-closed 并报告，不得自行猜测项目路径或绕过冲突。

`--prune` 具有删除软链的副作用，只在用户明确要求清理已删除 skill 的失效挂载时使用。
