# 推进栈 · methodology-framework-hardening

> **本文件由 `campaign-work-stack/scripts/stack.py render` 生成，请勿手改。**
> 真源是同目录的 `active-work-stack.json`；两者不一致时 `render --check` 会失败。

- schema：`work-queue-stack-v3`
- 绑定总目标台账：`workstacks/methodology-framework-hardening/goal-ledger.md`
- 启用方式：`user_approved_on_proposal`（auto_orchestration=受控/多阶段自动启用 · user_declared=用户显式声明 · pre-v3-unknown=v3 前创建、无从考证）
- 更新时间：2026-10-20T16:25:41+08:00
- 未关闭帧：**0**（active 0 / queued 0 / suspended 0）
- 已关闭帧：4
- 衍生登记：6（未处置 0）
- 当前栈顶：（无）
- 事件日志：28 条（`retro` 可复盘弯路）

## 推进树（分支 = 父子关系；◀ 标出当前推进到哪一帧）

```text
图例：● 正在做　◐ 被打断（子帧关闭后自动恢复）　○ 待办　✓ done　⏸ parked　↑ escalated　✗ wontfix

├─ [F-001] ✓ done          阶段一：规则一致性修复
├─ [F-002] ✓ done          阶段二：输入与交接
├─ [F-003] ✓ done          阶段三：收敛与输出
└─ [F-004] ✓ done          阶段四：组合行为回归
```

**位置指针**

```text
当前位置：（无 active 栈顶 —— 需要选下一个）
待选帧：（无）
```

进度：已关闭 4/4 帧（100%）｜未关闭 0｜当前 depth —｜栈深上限 4

## 全部帧明细（判据 / 来源 / 指针）

| frame_id | 标题 | 状态 | 完成判据 | 来源 |
| --- | --- | --- | --- | --- |
| `F-001` d0 | 阶段一：规则一致性修复 | 已关闭(done) | 1. 无栈路径可收口，有栈门禁不减弱<br>2. 阶段收尾唯一负责，正常排队不阻塞切换<br>3. 历史条款、引用和模板一致；保留人工审批<br>4. 校验、回归与四项目同步复查通过 | — |
| `F-002` d0 | 阶段二：输入与交接 | 已关闭(done) | 1. 共享最小输入复用已有材料，不强制新表单<br>2. 质量要求贯穿设计实施评审，保持硬约束与授权<br>3. 最小交接定位原任务，保留证据适用范围及继续权限<br>4. 五场景规则核对、校验回归及四项目同步复查通过 | 2026-10-20 用户批准本对话阶段二六部分修改方案 |
| `F-003` d0 | 阶段三：收敛与输出 | 已关闭(done) | 1. 统一纠正轮次与末次评审边界，探索预算和无进展记录跨恢复保留<br>2. 分级展示不删证据、风险、人工批准或停止门禁<br>3. 相关校验、现有回归、自检与四项目同步复查通过，并声明行为验证边界 | 2026-10-20 用户在阶段三具体方案后回复继续；批准统一纠正轮次、预算连续性、两轮无进展暂停、输出分级 |
| `F-004` d0 | 阶段四：组合行为回归 | 已关闭(done) | 1. 八组场景记录真实执行或给定状态恢复证据，至少一条真实设计实施评审链<br>2. 安全及门禁违规不计通过；失败修正最多两轮，保留首轮证据与未验证范围<br>3. 必要修正通过校验与分发，完成证据报告和栈收尾，不提交 | 2026-10-20 用户批准八组独立Agent隔离验证；最多两轮局部修正，不创建真实平台Goal，不修改业务项目 |

## 衍生登记（发现即登记，登记后才决定）

| capture_id | 发现于 | disposition | 去向 | 内容 |
| --- | --- | --- | --- | --- |
| `C-001` | F-001 | note | templates/codex-agents/; templates/cursor-agents/; skills/guided-goal-orchestrator/SKILL.md | 对齐模板时发现 guided-goal 已授权三角色但模板未列入合法调用入口；属于阶段一引用/模板一致性修复，保留仅显式批准当前阶段的限制。 |
| `C-002` | F-001 | note | tests/test_stack_lifecycle.py; skills/campaign-work-stack/scripts/stack.py | 最后一帧 pop 后未清理当前指针，疑似导致合法收尾后 verify 失败；使用临时栈复现并检查匹配路径边界 |
| `C-003` | F-001 | note | skills/single-phase-execution-loop/SKILL.md; skills/guided-goal-orchestrator/SKILL.md; workstacks/methodology-framework-hardening/phase-1-verification.md | pop 非事务操作，失败时可能已写入终态；本阶段用出栈前后 verify 与恢复核对防止误报成功，不扩展为事务引擎改造 |
| `C-004` | F-003 | note | workstacks/methodology-framework-hardening/phase-3-verification.md | 阶段三边界核对：两轮无进展是流程暂停，不自动满足平台 Goal blocked；新 retry 口径恢复旧记录时不能清零或伪造历史。纳入本阶段共享规则与静态走查。 |
| `C-005` | F-004 | note | workstacks/methodology-framework-hardening/phase-4-verification.md | 真实编排被测子会话没有二级代理调用接口，前置ready但未调用角色，正确停止且未伪造PASS；由具备collaboration工具的根会话接续测试调度，三个角色仍独立真实调用，不由根代理代替实施或评审。 |
| `C-006` | F-004 | note | workstacks/methodology-framework-hardening/phase-4-verification.md | 真实 Reviewer 首次返回 PASS 但 checks 使用中文键而非契约 name/status/output；根调度输入未附规范 YAML 嵌套格式。保留原报告，核对来源后仅补齐既有契约再复核；未接受该报告为阶段门禁。 |

## 已关闭帧（回看记录）

| frame_id | 终态 | 标题 | 关闭时间 | 结论 | 衍生 |
| --- | --- | --- | --- | --- | --- |
| `F-001` | done | 阶段一：规则一致性修复 | 2026-10-20T14:40:49+08:00 | 四项判据均完成：有栈/无栈路径、唯一收尾责任、历史规则与模板对齐；21项测试和仓库自检通过，四项目同步复查通过。证据见 phase-1-verification.md；完整Agent行为回归及项目角色副本刷新未执行。阶段二至四待批准。 | — |
| `F-002` | done | 阶段二：输入与交接 | 2026-10-20T14:54:38+08:00 | 四项判据完成：共享最小输入、质量要求贯穿角色、最小交接及权限边界已对齐；五场景静态走查完成，7个Skill校验、21项回归、仓库自检及四项目同步复查通过。证据见 phase-2-verification.md；未覆盖项目角色副本，未实跑多轮Agent。阶段三四待批准。 | — |
| `F-003` | done | 阶段三：收敛与输出 | 2026-10-20T15:46:19+08:00 | 统一 FAIL 后纠正轮次（默认3）、末轮评审及恢复计数；同一知识问题预算累计，连续两轮无有效进展暂停；分级展示保留完整记录和人工门禁。六个 Skill 校验、21 项既有测试、doctor 24项0错误0警告、diff检查、四项目同步与复查通过。13类人工静态走查完成，非实际多轮Agent行为验证。证据：workstacks/methodology-framework-hardening/phase-3-verification.md。衍生C-004已归入报告。F-004待批准；不commit/push，不覆盖项目角色配置。 | — |
| `F-004` | done | 阶段四：组合行为回归 | 2026-10-20T16:25:41+08:00 | 八组限定行为验证完成，根调度真实两阶段Designer/Executor/Reviewer通过（11项独立重跑）；原嵌套工具限制与首次Reviewer格式偏差保留，不外推未测范围。21项回归、doctor24项、四项目链接复查通过。源规则修正0/2；C5/C6归入phase-4-verification.md及phase-4-evidence/；未commit/push，未改业务项目或角色副本。 | — |

## 出栈日志

- 2026-10-20T14:40:49+08:00 · `F-001` → **done** · 剩余 `F-002`, `F-003`, `F-004` · 四项判据均完成：有栈/无栈路径、唯一收尾责任、历史规则与模板对齐；21项测试和仓库自检通过，四项目同步复查通过。证据见 phase-1-verification.md；完整Agent行为回归及项目角色副本刷新未执行。阶段二至四待批准。
- 2026-10-20T14:54:38+08:00 · `F-002` → **done** · 剩余 `F-003`, `F-004` · 四项判据完成：共享最小输入、质量要求贯穿角色、最小交接及权限边界已对齐；五场景静态走查完成，7个Skill校验、21项回归、仓库自检及四项目同步复查通过。证据见 phase-2-verification.md；未覆盖项目角色副本，未实跑多轮Agent。阶段三四待批准。
- 2026-10-20T15:46:19+08:00 · `F-003` → **done** · 剩余 `F-004` · 统一 FAIL 后纠正轮次（默认3）、末轮评审及恢复计数；同一知识问题预算累计，连续两轮无有效进展暂停；分级展示保留完整记录和人工门禁。六个 Skill 校验、21 项既有测试、doctor 24项0错误0警告、diff检查、四项目同步与复查通过。13类人工静态走查完成，非实际多轮Agent行为验证。证据：workstacks/methodology-framework-hardening/phase-3-verification.md。衍生C-004已归入报告。F-004待批准；不commit/push，不覆盖项目角色配置。
- 2026-10-20T16:25:41+08:00 · `F-004` → **done** · 剩余 空 · 八组限定行为验证完成，根调度真实两阶段Designer/Executor/Reviewer通过（11项独立重跑）；原嵌套工具限制与首次Reviewer格式偏差保留，不外推未测范围。21项回归、doctor24项、四项目链接复查通过。源规则修正0/2；C5/C6归入phase-4-verification.md及phase-4-evidence/；未commit/push，未改业务项目或角色副本。
