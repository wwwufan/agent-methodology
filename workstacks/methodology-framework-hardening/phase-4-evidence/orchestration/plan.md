# number-tools 执行计划

## 全局约束

只用标准库，无发布/网络/外部变更。不建新的业务架构。
函数接口保留，值和上下界均按调用者提供的数字处理；无需增加未要求的类型转换。
本轮用户已批准按 multi-phase-plan-orchestrator 连续执行下列两个阶段，
包括各阶段 designer → executor → reviewer 委托；已明确启用本项目测试栈。
实际分支从本项目 Git 读取，不自行更换分支。不创建真实平台 Goal。

## Phase 1：单值裁剪

实现 utils.clamp：值低于下界则下界，高于上界则上界，否则原值；
上下界相等合法，下界大于上界抛 ValueError。
本阶段不实现 clamp_many。
验收：python3 -B -m unittest test_phase1 -v。

## Phase 2：批量裁剪

依赖 Phase 1 完成。实现 utils.clamp_many，保留顺序和重复项，不修改输入列表。
空列表返回空列表，但下界大于上界时即使为空也必须抛 ValueError。
验收：python3 -B -m unittest test_phase1 test_phase2 -v。
