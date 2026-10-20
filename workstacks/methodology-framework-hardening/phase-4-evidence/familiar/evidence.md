# unique_labels 修复证据

日期：2026-10-20。范围：仅本隔离项目；未联网、未提交、未调用其他代理、未读其他测试目录或方法论 workstacks。

## 当前一步最小上下文

- 任务与返回对象：完成调用者交付的 `labels.unique_labels` 顺序修复，返回简短交付。
- 目标：去重后保留首次出现顺序，其他行为不变。来源：任务请求、`test_labels.py::LabelTests.test_order`。
- 项目事实：原实现为 `sorted(set(labels))`，返回列表、使用可哈希值去重，但最终排序破坏首次出现顺序。来源：`labels.py` 和修复前测试输出。
- 硬约束：标准库、函数接口不变、直接函数式实现、不得引入依赖；仅业务文件 `labels.py` 与 `test_labels.py` 可改，验证命令为 `python3 -B -m unittest -v`。来源：`AGENTS.md`。本证据文件由任务请求另行明确授权。
- 非目标：任务栈、编排、发布、远程服务和方法论源修改。
- 质量与验收：原有空输入与顺序测试必须通过；额外检查重复值、输入不变、生成器输入和不可哈希值仍报 TypeError。
- 未决项：没有阻塞当前一步的缺口；无外部参考实现。最小上下文就绪后，按任务已有授权直接实施。
- 技能影响：先整理来源和范围，再做局部修复；没有创建任务栈、另立流程或扫描其他项目。

## 实际读取与命令

1. 只读技能全文：
   `cat /Users/bole/client/agent-methodology/skills/project-context-brief/SKILL.md`
   首次 shell 启动附带 rvm/pyenv 权限提示，但文件读取成功；后续命令关闭 login shell。
2. 只读必需引用：
   `cat /Users/bole/client/agent-methodology/skills/project-context-brief/references/task-contract.md`
3. 在本目录定向检查：
   `pwd; rg --files -g 'AGENTS.md' -g '!workstacks/**' -g '!**/.git/**' .; ls -la`
   找到本项目 `AGENTS.md`、`labels.py`、`test_labels.py`。
4. 读取本地约束、实现与测试：
   `cat AGENTS.md labels.py test_labels.py`
5. 修复前运行：
   `python3 -B -m unittest -v`
   退出码 1；共 2 项，`test_empty` 通过，`test_order` 失败：
   实际 `['a', 'b', 'z']`，期望 `['z', 'a', 'b']`。

## 实际修改

使用 apply_patch：

- `labels.py`：将 `sorted(set(labels))` 改为 `list(dict.fromkeys(labels))`。
  去重使用字典键的插入顺序，返回类型仍为列表，不改输入，不增加依赖。
- `test_labels.py`：保留原测试，新增 `test_all_duplicates`、
  `test_input_unchanged`、`test_generator`、`test_unhashable_label`。
- 本文件：记录上下文、命令、实际行动与测试证据。

## 修复后验证

命令（本目录）：`python3 -B -m unittest -v`

```text
test_all_duplicates (test_labels.LabelTests.test_all_duplicates) ... ok
test_empty (test_labels.LabelTests.test_empty) ... ok
test_generator (test_labels.LabelTests.test_generator) ... ok
test_input_unchanged (test_labels.LabelTests.test_input_unchanged) ... ok
test_order (test_labels.LabelTests.test_order) ... ok
test_unhashable_label (test_labels.LabelTests.test_unhashable_label) ... ok

Ran 6 tests in 0.001s

OK
```

退出码 0。结论：本次目标及上述回归范围通过；交还调用者，无剩余必需操作。
