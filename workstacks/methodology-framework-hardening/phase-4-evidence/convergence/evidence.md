# 实际读取与行为证据

## 测试边界

这是给定历史决策测试，不是真实纠正/探索运行。四个历史来自本目录 `states.md`，彼此独立。未读取其他场景、父报告、项目真实进度文件或真实角色报告。不存在本轮角色输出、实验结果或新业务验收结论；没有预设或宣告测试 PASS。

## 实际完整读取的文件

1. `/private/tmp/methodology-phase4.olQYVP/convergence/states.md`：四种给定历史和“只问建议”的授权边界；文件共四项，在一次读取中完整显示。
2. `/Users/bole/client/agent-methodology/skills/single-phase-execution-loop/SKILL.md`：标准角色顺序、主代理职责、阶段授权与门禁、重试恢复引用、PASS 收尾。
3. `/Users/bole/client/agent-methodology/skills/exploration-loop/SKILL.md`：问题级探索、暂停优先级、知识问题交接及单阶段接线。
4. `/Users/bole/client/agent-methodology/skills/single-phase-execution-loop/references/role-contract.md`：完整读取；核心依据为 §2 三角色契约及 §3「纠正轮次与恢复」「达到最大重试」「失败后的通俗解释」。
5. `/Users/bole/client/agent-methodology/skills/exploration-loop/references/budget-and-progress.md`：完整读取；问题预算连续性、完整尝试与有效进展定义、嵌套证据不重复计数、连续两轮无进展暂停与恢复。
6. `/Users/bole/client/agent-methodology/skills/project-context-brief/references/task-contract.md`：完整读取；只补当前步骤所需输入、交接边界、分析请求到建议为止、输入充分不等于执行授权。
7. `/Users/bole/client/agent-methodology/skills/explain-task-failure/SKILL.md`：完整读取；用于 C、D 的已知/未知、失败影响及有限恢复条件说明。
8. `/Users/bole/client/agent-methodology/skills/campaign-work-stack/references/output-contract.md`：完整读取；按正常推进/暂停分级展示，不改变状态、计数或授权。

没有读取 `frame-protocol.md` 或执行栈接线资料：本任务没有在栈帧中记录探索或执行任何栈操作，用户明确禁止建栈与改状态。没有调用 `ai-task-triage`：已有规则和给定记录足以确定 A/B 待评审、C 额度耗尽停下、D 无进展暂停交用户的路由，无需另做诊断。

## 结论与规则对应

| 结论 | 给定历史 | 规则依据 |
| --- | --- | --- |
| A 下一角色 Reviewer，retry 仍为 1，探索仍用 1/2 | E1 已返回、本轮未评审；此前探索和重设计属于同一纠正 | role-contract §3：从来源 FAIL 纠正启动到下一次 Reviewer 结论为一轮，修复/探索/重设计/返回不重复加 retry；§2 Reviewer 接收完整方案和实施报告 |
| B 允许最后一轮评审，retry 仍为 3 | 本轮纠正已启动但未评审，无其他暂停 | role-contract §3：retry 等于上限不取消尚未结束的最后一轮，评审后再判断耗尽 |
| C 停止自动尝试，复用已有 issue，额外额度需批准 | R3 FAIL、3/3、已有 local-issue-7、未追加额度 | role-contract §3 最大重试与恢复规则：停止、保留真实 issue 指针和证据；获准新上限后累计值仍保留 |
| D 不能用新帧执行第三次实验 | 同一知识问题、2/3、连续两轮无进展暂停、无新数据/授权 | budget-and-progress：同一问题跨窗口/路线/帧累计；暂停不因尚有预算解除；恢复需新依据/策略及用户允许范围 |
| A/B 新进展不清空预算；D 不推算 retry | 仅题目给定范围可用 | budget-and-progress：有进展只重置连续无进展轮数；task-contract：不虚构绑定、历史或权限 |

## 本轮实际行为

- 列出并读取本测试目录文件；实际只有 `states.md` 被作为历史输入。
- 读取上述规则与参考文件，未运行项目命令、角色、实验、栈脚本、Goal 或测试程序。
- 仅新增本目录 `response.md` 和 `evidence.md`；未改动 `states.md`、阶段记录、预算、retry、问题台账或方法论源文件。
- 初次 shell 读取出现本地启动配置的 `ps` 权限及 pyenv 可写提示；读取仍成功完成。后续读取关闭 login shell。这些是读取环境噪声，不是场景中的失败证据。
- `response.md` 是建议报告，不是新的阶段计数真源。真实恢复前仍需读取原进度与实际角色报告；本次没有将给定摘要假称为真实执行记录。
