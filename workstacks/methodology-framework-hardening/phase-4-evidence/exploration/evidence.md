# 标题检索路线探索证据

## 原任务、预算与授权

原需求见 workstacks/title-search/goal-ledger.md；方法论来源：
`/Users/bole/client/agent-methodology/skills/exploration-loop/SKILL.md`、
`/Users/bole/client/agent-methodology/skills/campaign-work-stack/SKILL.md`，
均只读。项目约束来自本目录 AGENTS.md。
问题：whitespace 与 words 哪条路线在当前 samples.json 标注查询上的 top-1 更好？
解锁：后续搜索入口的分词选择；不授权本轮实现入口。
总预算：同一问题累计最多 2 次完整实验，开始时已用 0/2、剩余 2。
若一轮已有足以选路的证据立即停止；两轮无有效进展或预算耗尽则暂停并交用户。
换会话、角色、路线或重新开帧都不得刷新预算。

## 实验 1（预先定义）

- H1：words 的 top-1 正确数严格高于 whitespace。
- H2：whitespace 的 top-1 正确数严格高于 words。
- H0：两者相同，本指标不能区分。
- 最小实验：调用未修改的 candidates.search；同一份全部 4 条查询、同一文档顺序，
  唯一变化为 tokenizer。输出逐查询排序、top-1 id、正确与否、交集分数及并列情况。
- 预先判据：正确数较高者作为本样本原型路线；相同则不宣称优胜，
  判断是否需要在原数据上进一步取证。零分或并列同样按现有稳定排序取首项，
  不改变评分或用标签打破并列。
- 不测试生产泛化、性能、中文、规模、未标注查询，不更改候选函数或样本。

## 实际命令日志（顺序）

执行目录均为 `/private/tmp/methodology-phase4.olQYVP/exploration`（文档读取使用绝对路径）。

1. `cat /Users/bole/client/agent-methodology/skills/exploration-loop/SKILL.md`
2. `cat /Users/bole/client/agent-methodology/skills/campaign-work-stack/SKILL.md /Users/bole/client/agent-methodology/skills/exploration-loop/references/frame-protocol.md /Users/bole/client/agent-methodology/skills/exploration-loop/references/budget-and-progress.md /Users/bole/client/agent-methodology/skills/project-context-brief/references/task-contract.md`
3. `cat /Users/bole/client/agent-methodology/skills/campaign-work-stack/references/activation-and-recovery.md /Users/bole/client/agent-methodology/skills/campaign-work-stack/references/output-contract.md`
4. `rg --files -g '!__pycache__/**' -g '!workstacks/**' .` → 仅 AGENTS.md、candidates.py、samples.json。
5. `cat AGENTS.md candidates.py samples.json` → 2 条候选分词、4 文档、4 标注查询。
6. `python3 /Users/bole/client/agent-methodology/skills/campaign-work-stack/scripts/stack.py survey --repo-root /private/tmp/methodology-phase4.olQYVP/exploration --campaign title-search` → 无已有栈；无长期池文档，未擅自初始化整个项目。
7. `python3 /Users/bole/client/agent-methodology/skills/campaign-work-stack/scripts/stack.py ensure --repo-root /private/tmp/methodology-phase4.olQYVP/exploration --campaign title-search --activation user_declared --title 标题检索原型` → 新建栈；台账未绑定，因此用 apply_patch 创建本台账后再次 ensure 接线。

8. `python3 /Users/bole/client/agent-methodology/skills/campaign-work-stack/scripts/stack.py ensure --repo-root /private/tmp/methodology-phase4.olQYVP/exploration --campaign title-search` → 已补绑 goal-ledger.md。
9. `python3 /Users/bole/client/agent-methodology/skills/campaign-work-stack/scripts/stack.py push --repo-root /private/tmp/methodology-phase4.olQYVP/exploration --campaign title-search --title 确定分词路线 --goal '仅以当前标注样本top-1选择路线并交接' --criteria '可复查实验支持选路，适用范围、预算和下一步权限已记录到evidence.md' --activate` → F-001 active。
10. `python3 /Users/bole/client/agent-methodology/skills/campaign-work-stack/scripts/stack.py push --repo-root /private/tmp/methodology-phase4.olQYVP/exploration --campaign title-search --title 实现并验收搜索入口 --goal '根据选路证据实现本地原型入口；本轮不实施' --criteria '另获授权后明确入口输入输出及验收，完成实现并记录验证证据'` → F-002 queued。
11. `python3 /Users/bole/client/agent-methodology/skills/campaign-work-stack/scripts/stack.py capture --repo-root /private/tmp/methodology-phase4.olQYVP/exploration --campaign title-search --found-in F-001 --disposition blocks --text '当前未知whitespace与words在现有4条标注查询上的top-1优劣；需最小对照实验才能选路'` → C-001。
12. `python3 /Users/bole/client/agent-methodology/skills/campaign-work-stack/scripts/stack.py push --repo-root /private/tmp/methodology-phase4.olQYVP/exploration --campaign title-search --title 验证两种分词的样本top-1 --goal '用最多2次完整实验解锁F-001选路并交接原型实现者' --criteria '候选假设、预先判据、预算、逐样本结果、结论及返回权限均有证据' --parent F-001 --activate` → F-003 active，F-001 suspended。
13. `python3 /Users/bole/client/agent-methodology/skills/campaign-work-stack/scripts/stack.py resolve --repo-root /private/tmp/methodology-phase4.olQYVP/exploration --campaign title-search --capture C-001 --disposition blocks --frame F-003` → 阻塞关联探索子帧。

文档读取和栈操作不算完整实验。实验脚本由 apply_patch 创建，运行前预算仍是 0/2。

14. `python3 -B experiment.py` → exit 0，实验 1 完成；输出关键结果如下。

## 实验 1：实际结果与判断

运行环境：Python `3.13.2 (main, Feb 4 2025, 14:51:09) [Clang 16.0.0 (clang-1600.0.26.6)]`。
固定文档输入顺序：b, a, c, d。输入/实验脚本 SHA-256：

```text
candidates.py  1e2820b6ccaeb34c6d956310dbe8fce24b7f8792ee11b303405814407b2adca6
samples.json   6771c1d4911f253f85ae750fb7534c5b6311024abe4e564665ee5d3ec63c16dc
experiment.py  f4d7d794c76c6863a403442bd98951141a372e1e45049a0ca67d3de4dc0dd360
```

| 路线 | 查询 | 预期 | 完整排序 | 对应交集分数 | top-1 | 正确 | 最高分并列数 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| whitespace | red flower | a | b,a,c,d | 0,0,0,0 | b | 否 | 4 |
| whitespace | BLUE, sky | c | c,b,a,d | 1,0,0,0 | c | 是 | 1 |
| whitespace | green-tree | d | b,a,c,d | 0,0,0,0 | b | 否 | 4 |
| whitespace | ocean | b | b,a,c,d | 1,0,0,0 | b | 是 | 1 |
| words | red flower | a | a,b,c,d | 2,0,0,0 | a | 是 | 1 |
| words | BLUE, sky | c | c,b,a,d | 2,0,0,0 | c | 是 | 1 |
| words | green-tree | d | d,b,a,c | 2,0,0,0 | d | 是 | 1 |
| words | ocean | b | b,a,c,d | 1,0,0,0 | b | 是 | 1 |

whitespace 的查询 token 依次为 `{red, flower}`、`{blue,, sky}`、
`{green-tree}`、`{ocean}`；words 则为 `{red, flower}`、`{blue, sky}`、
`{green, tree}`、`{ocean}`。whitespace 的两个失败查询为全零分稳定排序，
返回输入中的第一个 b，而非有效匹配。

汇总：whitespace 2/4（50%），words 4/4（100%），words 多命中 2 条、提升 50 个百分点。
支持 H1，推翻本样本上的 H2 和 H0。因标点与连字符被 words 分开，当前标注查询得分
和排序得到改善；BLUE, sky 两条路线均正确，但 words 匹配词数从 1 到 2。

有效进展：是，新增可复查的逐查询对照证据，解除当前样本选路阻塞。
连续无有效进展轮数：0。累计完整实验：1/2；剩余：1。
停止原因：已取得足以满足预先判据的证据，不为用满预算再实验。
本次证据限于上述文件指纹、四条查询、四个文档、现有重叠计分和稳定排序；
不能推断全量、中文、生产准确率、稳健性、性能或已完成入口验收。

## 交接原型实现者

返回位置：探索 F-003 → 选路父帧 F-001；后续工作为 F-002。
建议路线：调用现有 `candidates.search(query, documents, candidates.words)`。
本轮未修改 candidates.py、samples.json，未创建搜索入口；experiment.py 只是离线对照实验。
实现者可据本报告直接承接选路，不必无依据重启诊断。

剩余必需工作：获得用户对 F-002 的实施授权，明确入口形式和输入输出约定，接入 words，
实现入口，再通过入口验证当前四条标注查询；明确并验证空查询/无匹配/并列等边界行为。
现有候选 search 对全零分仍返回文档，入口的呈现/处理策略尚未确定，不能宣称已解决。
这些缺口属于已登记 F-002 的实现和验收，不阻塞本轮样本选路，也不新增未经授权的任务。
生产化数据覆盖、性能和中文等不在本轮成功标准之内，若以后需要应另行约定。

恢复时先读取本报告的需求、指纹和预算，再使用本项目根 --repo-root 的 show + verify
核对栈；保留本问题累计 1/2，不能换代理后清零。用户准确续做指令可为：
“继续 title-search 的 F-002：先确认搜索入口输入输出和验收细节，再实现并验收；
沿用 evidence.md 的 words 选路结论与累计实验预算。”

## 收尾实际命令及关键结果

15. `python3 /Users/bole/client/agent-methodology/skills/campaign-work-stack/scripts/stack.py amend --repo-root /private/tmp/methodology-phase4.olQYVP/exploration --campaign title-search --frame F-003 --origin '认知缺口C-001；返回F-001及后续原型实现者；本轮不实施F-002' --pointers '{"report":"evidence.md","experiment":"experiment.py","samples":"samples.json","candidates":"candidates.py"}'` → 记录来源与证据指针。
16. `python3 /Users/bole/client/agent-methodology/skills/campaign-work-stack/scripts/stack.py amend --repo-root /private/tmp/methodology-phase4.olQYVP/exploration --campaign title-search --frame F-002 --origin '用户原请求；本轮明确不实施，后续需授权' --pointers '{"handoff":"evidence.md","task_contract":"workstacks/title-search/goal-ledger.md"}'` → 记录未授权实施及交接指针。
17. `python3 /Users/bole/client/agent-methodology/skills/campaign-work-stack/scripts/stack.py verify --repo-root /private/tmp/methodology-phase4.olQYVP/exploration --campaign title-search` → PASS，exit 0。
18. `python3 /Users/bole/client/agent-methodology/skills/campaign-work-stack/scripts/stack.py pop --repo-root /private/tmp/methodology-phase4.olQYVP/exploration --campaign title-search --frame F-003 --terminal done --note '预算累计1/2，剩余1；预先H1为words优于whitespace；固定4查询/4文档及search只替换分词。结果words=4/4、whitespace=2/4，支持H1；证据evidence.md、experiment.py及输入指纹。有效进展：解除选路阻塞，连续无进展0，已有充分证据停止。返回F-001及原型实现者，适用范围仅当前样本，不证明生产质量；F-002待授权且本轮不实施。'` → exit 0；F-003 done，自动恢复 F-001。
19. `python3 /Users/bole/client/agent-methodology/skills/campaign-work-stack/scripts/stack.py verify --repo-root /private/tmp/methodology-phase4.olQYVP/exploration --campaign title-search` → PASS，exit 0。
20. `python3 /Users/bole/client/agent-methodology/skills/campaign-work-stack/scripts/stack.py pop --repo-root /private/tmp/methodology-phase4.olQYVP/exploration --campaign title-search --frame F-001 --terminal done --note '已核对F-003证据并选择words：本样本top-1为4/4，对照whitespace为2/4。验收达成：evidence.md保存原需求、预算1/2、预先判据、逐样本结果、指纹及原型实现者交接。C-001已由F-003解决；本轮停止。仅F-002保持queued，不实施、不宣称原型或生产验收完成；下一步需用户授权实现入口并明确输入输出和边界验收。'` → exit 0；F-001 done，F-002 queued，不激活下一项。
21. `python3 /Users/bole/client/agent-methodology/skills/campaign-work-stack/scripts/stack.py verify --repo-root /private/tmp/methodology-phase4.olQYVP/exploration --campaign title-search` → PASS，exit 0；仅软警告“有 queued 帧但无 active”，与用户要求选路后停止一致，不以激活下一项消除此警告。
22. `python3 /Users/bole/client/agent-methodology/skills/campaign-work-stack/scripts/stack.py retro --repo-root /private/tmp/methodology-phase4.olQYVP/exploration --campaign title-search` → done 2，wontfix/parked/escalated 各 0，用户方向切换 0，深度峰值 d1，C-001 blocks 已落 F-003；两次 amend 仅补来源和指针，不改判据。
23. `python3 /Users/bole/client/agent-methodology/skills/campaign-work-stack/scripts/stack.py show --repo-root /private/tmp/methodology-phase4.olQYVP/exploration --campaign title-search` → F-001 与 F-003 done，仅 F-002 queued；当前无 active。
24. `shasum -a 256 candidates.py samples.json experiment.py` → 三个指纹与实验输出完全一致；未重跑实验。

## 最终回看

- 结论：本样本选 words；已完成预先定义的选路验收，不等于原型实现完成。
- 衍生：C-001 的认知阻塞由 F-003 解决，没有遗留 pending 或未经授权展开的新任务。
- 剩余：F-002“实现并验收搜索入口”仍为 queued，等待用户后续指令。
- 复盘：未选 whitespace 作为本样本路线；无生产淘汰结论，无用户改道，
  没有浪费第二次实验。无 parked/wontfix 帧；F-002 是原定待办而不是遗忘。
- 下一步与权限：按上文准确续做指令交给原型实现者；本轮停在选路交接。

所有写入仅位于本隔离项目；方法论仓库保持只读。未联网、安装包、调用外部 API、
创建真实平台 Goal、提交或委托其他代理。栈状态及事件通过 stack.py 写入，
没有手工编辑 active-work-stack.json 或其 Markdown 视图。
