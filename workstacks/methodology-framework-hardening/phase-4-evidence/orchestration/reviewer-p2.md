```yaml
review_id: number-tools-phase-2
review_subject: "number-tools / Phase 2 / F-002，main，retry 0/2；依据两阶段执行授权及已返回的 Designer、Executor 报告，独立只读复核当前源码与测试。"
verdict: PASS
checks:
  - name: 授权与角色契约
    status: pass
    output: "已完整读取 AGENTS.md、plan.md、两份阶段报告、实际 reviewer.toml 及 role-contract.md；调用条件和输出契约一致。"
  - name: 批量裁剪验收标准
    status: pass
    output: "clamp_many 前置检查逆界，随后以列表推导调用 clamp；测试覆盖顺序、重复项、输入不变及返回新列表。"
  - name: 边界与异常路径
    status: pass
    output: "合法空输入返回独立空列表；空与非空输入逆界均抛 ValueError；等界合法，端点与区间内原值保留。"
  - name: Phase 1 行为回归
    status: pass
    output: "独立复核 clamp 实现，并通过全部 5 项 Phase 1 测试。"
  - name: 设计及全局约束符合性
    status: pass
    output: "当前实现符合推荐方案，保留函数签名，无类型转换、额外依赖或架构扩展；本次评审未修改文件、联网、发布、创建 Goal 或提交。"
  - name: 独立验证命令
    status: pass
    output: "在项目目录执行 python3 -B -m unittest test_phase1 test_phase2 -v；Ran 11 tests in 0.000s，OK，退出码 0。"
issues: []
fix_instructions: []
residual_risks:
  - "业务文件当前均未被 Git 跟踪，无法通过 git diff 独立证明历史改动范围；本次结论依据当前源码检查及独立验收，未发现当前阶段关键验证缺口。"
  - "建议主代理依已有授权执行阶段收尾并维护记录；本报告未关闭阶段帧，PASS 不代表用户新批准或自动解锁额外工作。"
```
