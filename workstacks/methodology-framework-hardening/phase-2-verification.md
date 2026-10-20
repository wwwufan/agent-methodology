# 阶段二：输入、质量要求与交接

- 日期：2026-10-20
- campaign_id：methodology-framework-hardening
- 对应帧：F-002
- 授权：用户对本对话阶段二方案回复“批准”。
- 执行方式：任务栈 + 直接实施；未执行三角色编排、未运行实际多轮 Agent 行为验证。
- 状态：已完成；F-002 已关闭，出栈前后 verify 均通过。

## 修改与责任归属

| 范围 | 修改 |
| --- | --- |
| `skills/project-context-brief/references/task-contract.md` | 新增唯一共享语义：六项最小输入、按用途确定质量、五项交接信息；无新表单、状态机或授权 |
| `project-context-brief` / `ai-task-triage` | 复用已知材料；区分熟悉度与质量；交还具体原任务和下一步权限 |
| `exploration-loop` / `references/frame-protocol.md` | 保留返回位置、证据适用范围、剩余缺口及权限，不把样本结果当成全量验收或实施完成 |
| `single-phase-execution-loop` / `references/role-contract.md` | 三角色继承同一任务要求；报告沿用原字段；接收交接后核对位置、证据和授权再继续 |
| `multi-phase-plan-orchestrator` | 按已确认用途/质量选择实现；不擅自升降标准；外层交接不能绕过内层收尾 |
| `guided-goal-orchestrator` / `references/ledger-template.md` | 新方案承载质量要求，旧快照不为模板升级而重写；质量/验收变化仍走版本和批准流程 |
| `campaign-work-stack/references/activation-and-recovery.md` | 仅保留位置与证据指针，父帧恢复不等于获得新权限 |
| 六个 Codex/Cursor 源角色模板 | 独立具备质量边界与交接语义；不把“最小实现”本身作为失败理由，不丢失必要风险和项目硬约束 |

没有新增顶层 Skill；没有改脚本、栈 schema、角色输出标题、Reviewer YAML 字段、模型继承、
重试/探索预算、人工门禁或输出分级。此前未提交修改均保留。

## 五场景规则走查

以下是对本次文档与模板的人工静态走查，不是模型实跑成绩；情境是验收示例，不是已执行的业务任务。

| 情境输入 | 核对的决策 | 当前规则依据与结论 |
| --- | --- | --- |
| 熟悉业务任务已给计划、相关实现、约束及测试入口 | 直接复用，不再要求新表单或全仓库阅读 | `task-contract.md` 输入节、上下文 Skill 及单阶段输入前置一致；只补影响下一步的缺口 |
| 本地图片检索原型明确不做多租户和通用扩展框架，已有最小可用判据 | Designer 不追加框架；Reviewer 不因缺少该框架 FAIL；最小可用证据与数据权限仍需满足 | 共享质量节、三角色共同输入、六个模板均区分必须/暂缓/建议；核对未保留无条件“最佳长期实现”规则 |
| 技术陌生但明确要求生产兼容性、稳定性及回归验收 | 可以先探索，但不能把交付要求降为原型 | 诊断、探索、编排和模板均将熟悉度与质量独立处理；探索证据不得改写原成功判据 |
| 探索在特定样本上支持一条路线，原执行任务仍未完成 | 返回原任务与具体接收者，说明样本限制、解锁步骤、剩余缺口和权限 | 探索返回节、帧协议及角色交接都有落点；不默认重新诊断，不把恢复父帧当新授权 |
| 用户只要求分析，所有输入均已充分 | 输出建议并交还用户，不自动实现、运行实验或调度角色 | 共享约定区分就绪/授权，诊断和上下文保留只读边界，角色继续受显式调用与阶段授权限制 |

补充边界核对：

- 质量等级标签缺失但项目约束和验收充分：Reviewer 不仅因缺少标签而 FAIL。
- 原型诉求与项目硬约束冲突：提出来源和影响，不静默降级。
- 旧受控快照已充分：直接复用，不为新增模板标题修改字节或 SHA-256。
- Reviewer 仍对必要风险、关键未验证项及未满足的目标 FAIL；纯未来改进只是建议。
- 共享引用只用于读取约定，不构成强制串行调用整组 Skill。

## 校验记录

- 七个相关 Skill 的 `quick_validate.py` 全部输出 `Skill is valid!`。
  使用已有缓存 PyYAML，没有安装依赖。
- 第一轮 `python3 -B -m unittest discover -s tests -v`：21 tests / OK。
  本阶段没有新增仅匹配措辞的测试，也没有用这 21 项替代 Agent 行为验证。
- 第一轮 `python3 -B scripts/doctor.py --no-global`：24 项检查，0 error / 0 warn；
  31 处同包引用可解析，角色字段镜像保持一致。
- `git diff --check`：通过。
- 补齐 Reviewer 默认质量语义后的最终复跑：
  `python3 -B -m unittest discover -s tests -q`：21 tests / OK；
  `python3 -B scripts/doctor.py --no-global`：24 项检查，0 error / 0 warn；
  `git diff --check`：通过。
- 四项目 `sync_projects.py --check` → `sync_projects.py` → `sync_projects.py --check` 均 exit=0：

| 项目 | 最终检查 | 同步写模式 | exclude / 冲突 / 漂移 / 失效 |
| --- | --- | --- | --- |
| diamond-agent | 9/9 正确 | skipped=9；新增/重指向/替换/删除均为 0 | 新增/缺失/冲突/漂移/失效均为 0 |
| diamond-1 | 9/9 正确 | 同上 | 同上 |
| diamond-2 | 9/9 正确 | 同上 | 同上 |
| diamond-3 | 9/9 正确 | 同上 | 同上 |

没有运行 `--prune` 或完整初始化；软链继续直接指向本仓库真源。

收尾：`pop` exit=0；出栈前后 `verify` 均 PASS。仅有后续 2 帧 queued、无 active 的预期软提示，
表示等待用户批准，不自动激活。当前帧无衍生登记；累计 retro 放弃 0、搁置 0、
用户方向切换 1（脚本统计用户批准后激活 F-002，不是路线返工）。

## 分发边界与后续

Skill 真源通过已有软链暴露；同步只覆盖登记项目的软链和本地忽略配置。
六个源角色模板的语义已更新，但不覆盖项目内 `.codex/agents` / `.cursor/agents` 的实体副本；
现有副本刷新需另行明确授权并保留定制，不能宣称运行中角色已加载新模板。

阶段三（收敛与输出）和阶段四（完整组合行为回归）仍未授权执行。
本阶段没有修改业务代码、PPT、项目质量标准或业务批准快照，没有 commit/push。
