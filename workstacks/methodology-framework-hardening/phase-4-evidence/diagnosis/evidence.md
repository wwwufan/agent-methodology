# 读取记录与处理范围

输入仅为 `/private/tmp/methodology-phase4.olQYVP/diagnosis/materials.md`。A、B 均按给定测试历史解释，没有将其表述成本轮测试或实验结果。

完整读取的 Skill：

- `/Users/bole/client/agent-methodology/skills/explain-task-failure/SKILL.md`：用于两份实际用户答复。
- `/Users/bole/client/agent-methodology/skills/ai-task-triage/SKILL.md`：仅用于 B 的一次条件式只读诊断。触发依据是连续调整无有效进展、根因尚不能区分且没有已有的有证据下一步；诊断结果合并于 B，不另开执行流程。

完整读取的必需参考：

- `/Users/bole/client/agent-methodology/skills/campaign-work-stack/references/output-contract.md`：由失败解释 Skill 要求读取，用于按可继续与预算耗尽场景控制展示深度。仅阅读此参考，不启用任务栈。
- `/Users/bole/client/agent-methodology/skills/project-context-brief/references/task-contract.md`：由诊断 Skill 要求读取，用于检查 B 的输入、验收和权限边界。未调用上下文整理 Skill。

路由区别：

- A：直接原因及 Reviewer 修复动作明确，不触发额外诊断；保持“先不要改代码”的限制，保留 retry 记录。
- B：主技术缺口为可区分根因的证据；硬门禁为流程已暂停、预算 3/3 耗尽且未批准追加。建议先核对已有事实，再按证据决定是否需要探索；所有实验动作仍需批准，未自动恢复。

实际操作仅为读取上述 Skill、参考和材料，列出本 diagnosis 目录文件，以及创建 `response-a.md`、`response-b.md`、`evidence.md`。没有读取其他测试目录或方法论 workstacks；没有修改方法论源、输入材料或业务代码，没有运行实验、创建任务栈、委托代理或调用平台 Goal。
