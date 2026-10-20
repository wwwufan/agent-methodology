# 独立上下文恢复审计

日期：2026-10-20。范围：仅 `/private/tmp/methodology-phase4.olQYVP/exploration` 与方法论只读源。任务是恢复状态并回答位置、剩余、证据、预算和下一步；不实验、不实施、不修改既有文件、不创建 Goal、不委托代理。

## 实际读取及命令

以下按实际先后列出工具调用中的命令。首次命令默认工作目录为环境 cwd，仅 `pwd` 输出位置，未读取该目录文件。首次登录 shell 自身输出 rvm 的 ps 权限提示与 pyenv rehash 不可写提示；命令退出 0，后续均关闭 login shell。

1. `pwd`
2. `sed -n '1,240p' /Users/bole/client/agent-methodology/skills/campaign-work-stack/SKILL.md`
3. `sed -n '241,500p' /Users/bole/client/agent-methodology/skills/campaign-work-stack/SKILL.md`
4. `sed -n '1,260p' /Users/bole/client/agent-methodology/skills/campaign-work-stack/references/activation-and-recovery.md`
5. `sed -n '1,260p' /Users/bole/client/agent-methodology/skills/campaign-work-stack/references/output-contract.md`
6. `rg --files --hidden /private/tmp/methodology-phase4.olQYVP/exploration`
7. `python3 /Users/bole/client/agent-methodology/skills/campaign-work-stack/scripts/stack.py stacks --repo-root /private/tmp/methodology-phase4.olQYVP/exploration`

以下相对文件路径的执行目录均为 `/private/tmp/methodology-phase4.olQYVP/exploration`：

8. `sed -n '1,240p' AGENTS.md`
9. `sed -n '1,280p' evidence.md`
10. `sed -n '1,260p' workstacks/title-search/goal-ledger.md`
11. `sed -n '1,320p' workstacks/title-search/active-work-stack.json`
12. `python3 /Users/bole/client/agent-methodology/skills/campaign-work-stack/scripts/stack.py show --campaign title-search --repo-root /private/tmp/methodology-phase4.olQYVP/exploration`
13. `python3 /Users/bole/client/agent-methodology/skills/campaign-work-stack/scripts/stack.py verify --campaign title-search --repo-root /private/tmp/methodology-phase4.olQYVP/exploration`
14. `python3 /Users/bole/client/agent-methodology/skills/campaign-work-stack/scripts/stack.py survey --campaign title-search --repo-root /private/tmp/methodology-phase4.olQYVP/exploration`
15. `python3 /Users/bole/client/agent-methodology/skills/campaign-work-stack/scripts/stack.py retro --campaign title-search --repo-root /private/tmp/methodology-phase4.olQYVP/exploration`
16. `sed -n '1,300p' /Users/bole/client/agent-methodology/skills/campaign-work-stack/references/stack-schema.md`
17. `sed -n '1,260p' candidates.py`
18. `sed -n '1,260p' experiment.py`
19. `sed -n '1,220p' samples.json`
20. `shasum -a 256 candidates.py samples.json experiment.py`
21. `sed -n '301,500p' /Users/bole/client/agent-methodology/skills/campaign-work-stack/references/stack-schema.md`
22. `apply_patch`：新增本文件和 recovery-response.md，未改既有文件。

所选 skill 及三个参考均已读完整。未读取其他测试目录或父会话报告；`evidence.md` 是本测试目录内既有实验记录，不是外部报告。未执行其中记录的历史命令。

## 本轮直接验证

- `stacks`：一个 open 栈 title-search，title 为“标题检索原型”，无当前指针。
- `show` / JSON：F-001 done，F-003 done，F-002 queued，无 active；捕获 C-001 指向完成的探索子帧 F-003；13 条历史事件，2 条 pop 日志。
- `verify`：PASS，exit 0。唯一软警告为有 queued 帧而无 active；视图与真源一致、绑定和结构通过。该命令对派生 Markdown 进行了核对，未另用 sed 读取该视图。
- `survey`：两份长期池文档不存在；未执行其建议的 bootstrap，不将缺失误报为空池。
- `retro`：done 2，其余终态组为 0，用户方向切换 0，DFS 抢占/恢复 4 次，峰值 d1；两次 amend 仅涉及 origin/pointers。
- 三份文件指纹与 evidence.md 历史记录一致：

```text
candidates.py  1e2820b6ccaeb34c6d956310dbe8fce24b7f8792ee11b303405814407b2adca6
samples.json   6771c1d4911f253f85ae750fb7534c5b6311024abe4e564665ee5d3ec63c16dc
experiment.py  f4d7d794c76c6863a403442bd98951141a372e1e45049a0ca67d3de4dc0dd360
```

静态阅读可确认 search 使用词交集计分，words 使用 `[a-z0-9]+`，样本有四条查询/四个文档；实验脚本对两个 tokenizer 使用同一 search 和数据，未实现搜索入口。

## 沿用历史证据，不冒充本轮实验

历史 evidence.md 记录 words 4/4、whitespace 2/4，实验 1 退出 0；本轮未独立重跑这一结果。预算真源记录累计 1/2、剩余 1，连续无进展 0，本轮新增实验 0。因已有足够证据而停止，不再消费预算。

## 未验证与权限边界

- 搜索入口尚未实现/验收，接口、空查询、无匹配和并列处理待定。
- 未验证生产、中文、规模、性能、其他样本或稳健性。
- 长期待办池缺失，不能核验池内剩余。
- 无当前指针；根据唯一候选和台账语义识别为 title-search，但不宣称已完成指针绑定。
- 常规恢复规则需要 `use` / `ensure`；本轮明确只读且只准新增两个报告，因此不执行这两项写操作。既有 bound_ledger 已正确，无需为了报告位置而修改它。
- 未激活 F-002；先等实施授权及入口约定。无新 Goal、委托、网络、外部 API、安装包或提交。

本记录及 recovery-response.md 仅为恢复输出，不构成新的推进状态或预算真源。
