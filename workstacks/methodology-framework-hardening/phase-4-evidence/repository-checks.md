# 仓库复验记录

日期：2026-10-20；执行目录 `/Users/bole/client/agent-methodology`。
下列为根会话实际命令与关键输出摘要，不是模拟历史。

## 自动回归

`python3 -B -m unittest discover -s tests -v`

`Ran 21 tests in 17.435s`，`OK`。
覆盖模型继承/配置门禁、栈启用/关闭/恢复/指针隔离与项目链接同步。
不以这些脚本测试代替 Agent 行为验证。

## 仓库自检

`python3 -B scripts/doctor.py --no-global`

`doctor: 24 项检查 · 0 error / 0 warn · exit=0`。
`--no-global` 明确跳过全局安装检查；未给 --project，不假称业务项目角色副本已验证或更新。

## 登记项目链接

`python3 -B scripts/sync_projects.py --check`

首次在沙箱内四项目均因“目标根不可写”预检失败，exit1；没有修链动作。
获准沙箱外执行同一只读检查后：

- diamond-agent：9 ok，conflict/drift/missing/stale 均0。
- diamond-1：9 ok，conflict/drift/missing/stale 均0。
- diamond-2：9 ok，conflict/drift/missing/stale 均0。
- diamond-3：9 ok，conflict/drift/missing/stale 均0。
- 汇总：projects=4，ok=4，failed=0，exit0。

created/repointed/replaced/removed/exclude-added 均0，未覆盖角色配置或修改业务文件。
阶段四尚无源规则变更，不重复执行写入同步。

## 差异

`git diff --check` 无输出，exit0。已存在的未提交变更保留；本轮不 commit/push。
