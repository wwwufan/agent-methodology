# 根会话真实调度审计

日期 2026-10-20。原委托代理能力限制见 orchestration-startup.md，不覆盖其结果。
根会话仅负责角色输入、调度、文件基线、状态收尾与独立补充核验，没有设计/修改样例实现或代替 Reviewer 宣告 PASS。
各角色 `fork_turns=none`，未传 model；角色契约来自隔离项目 `.codex/agents/*.toml`。
模型继承由后端管理，不宣称运行时测得具体型号。真实平台 Goal 调用 0 次。

## Phase 1

1. 根会话重跑 check_codex_backend.py，ready，三个角色无 model，权限和指令校验通过；
   对测试目录显式 --repo-root 运行 verify，exit0。
2. 调用前 `find . -type f -not -path './.git/*' -exec shasum -a 256 {} + | sort` 保存工具输出清单，
   共 14 文件（含所有未跟踪文件）。独立 `/root/designer_p1` 实际返回 READY；
   同命令调用后清单逐项一致。根会话之后才保存 designer-p1.md。
3. 独立 `/root/executor_p1` 修改 utils.py/test_phase1.py，实际五项测试通过；返回原文保存 executor-p1.md。
4. 审阅前用 audit_workspace.py snapshot 创建 reviewer-p1-baseline.json，16 项。
   独立 `/root/reviewer_p1` 重跑五项并返回业务 PASS，compare unchanged=true，changed_paths=[]。
   首次报告 checks 中文键不符合规范；根会话未接受其完整门禁，保留 reviewer-p1-original.md。
5. 根提示原先没有传入规范嵌套 YAML；补充要求读取 role-contract.md 的现有契约。
   新快照 reviewer-p1-format-baseline.json，17 项。同 Reviewer 重新独立重跑，返回合规 YAML PASS；
   compare unchanged=true，changed_paths=[]。这不是干净新代理测试；不把同角色格式复核称作独立样本。
   原要求和代码均未改变，没有 Reviewer 业务 FAIL、没有代码纠正轮，retry 保留0/2。
6. 根独立运行 `python3 -B -m unittest test_phase1 -v`，5 tests，OK，exit0。
7. 角色残余风险按来源合并登记 C-002（无 Git 历史但完整哈希补偿）、
   C-003（未要求数值语义不扩展）、C-004（Phase2 queued）并 resolve；C-001 根调度路径已恢复。
8. 内层实际 pre-verify exit0 → pop F-001 exit0 → post-verify exit0。
   pop_log 此时1条；F-002仍queued，不要求提前完成，不重复关闭或计数。
9. 仅在上述收尾成功后 progress Phase1 写 done 和 review_id=number-tools-phase-1。
   外层核对并选择Phase2，激活已有F-002；不重复pop Phase1。

## Phase 2 启动

原两阶段授权仍有效，无新增批准要求。check_codex_backend.py 再次 ready。
progress Phase2 designing、retry0/max2；调用前 designer-p2-baseline.json 共18项。
`/root/designer_p2` 实际返回 READY。compare 精确报告唯一新增 `scratch/root-audit.md`：
这是根会话在角色执行期间用 apply_patch 新建的本审计文件，工具记录可归因；
原18项均未变，无其他新增/删除。不将该比较误报为 unchanged=true，也无证据归咎只读角色。
后续只读角色运行期间根会话不再写被审计目录。

## Phase 2 实施与评审

独立 `/root/executor_p2` 修改 utils.py/test_phase2.py，原始报告 executor-p2.md，11项通过。
未评审风险 C-005 登记并关联报告。三个角色配置 SHA-256 与启动清单一致。
独立 `/root/reviewer_p2` 前21项基线，调用后 compare unchanged=true / changed_paths=[]。
Reviewer 完整读取规范字段，首次返回合规 YAML PASS，review_id=number-tools-phase-2；
独立重跑11项，原文 reviewer-p2.md。
根会话读取最终函数和两个测试文件，再独立重跑同命令：11 tests，OK，exit0。
Reviewer 无历史Git基线风险复用 C-002，由完整文件哈希及当前源码核查补偿；
C-005 的待评审条件已由真实评审解除，不从测试结果自行宣告阶段PASS。
Phase2 没有业务FAIL或纠正轮，retry保持0/2。
真实 pre-verify exit0 → pop F-002 exit0 → post-verify exit0 后，progress写done。
最终两个Phase各1条pop（累计2条），5条capture均有处置；没有为了下一阶段queued而提前关帧。
retro实际执行：放弃/搁置/升级均0，1次activated是计划内Phase切换，不是路线返工。
两阶段由根会话内层负责完成记录/计数/关闭，外层仅核对及选择下一阶段。
没有真实业务FAIL纠正链；格式复核不能冒充一次实现失败重试。
