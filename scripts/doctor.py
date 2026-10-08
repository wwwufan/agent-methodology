#!/usr/bin/env python3
"""本仓库安装健康的唯一判据：只读自检：12 个常规检查组 + 1 个 opt-in 组（第 11 项，--stack-verify）；行数随参数与仓库状态变化，以 --json 的 summary.total 为准。

<方法论仓库> = agent-methodology 仓库根目录（装着 skills/、scripts/、templates/ 的那一层）；用户可见定义见 README.md「占位符约定」。

检查组一览（**组号稳定，行数与 id 随参数变化**）：
    第 1~10 组 = 仓库自完整 / 脚本可编译 / 同包引用 / 全局挂载 / .system 未越界 / 项目角色配置 /
                 项目侧软链 / 栈目录就位 / 长期池可解析 + 跨组件契约 / 暂存期路径前缀
    第 12 组「运行时指引布局无关」= 全仓库扫描裸 scripts/<name>.py 形态的运行时指引，
                 并正向断言 `<方法论仓库>` 占位符在同文件内有定义行
    第 13 组「三角色契约镜像一致」= role-contract.md 的规范标题锚块 ↔ 6 个角色模板的字段名全集双向断言
    第 11 组 = opt-in 的栈内容门禁（--stack-verify），默认关闭

**id 规则**：`id = <组号>.<稳定键>`。健康态行的键 = **对象身份**（skill 名 / 脚本 stem / 角色名 /
单例检查的固定名），故**跨参数稳定**——同一检查在 `--project` 与 `--no-global` 下 id 相同，
文档与消费者可以按 id 索引。违规诊断行允许 `<键>-<i>` 位置后缀（如 `refs-1`、`bare-2`、
`role-headings-1`），它们只对当次输出有意义、**不得被文档或脚本索引**。
键表全文见 docs/migration-diamond-agent.md ⑦。

用法（完整参数以 --help 为准）：
    python3 <方法论仓库>/scripts/doctor.py                       # 仓库自完整 + 全局挂载
    python3 <方法论仓库>/scripts/doctor.py --project <PROJ>      # 追加项目侧第 6~9 组
    python3 <方法论仓库>/scripts/doctor.py --no-global           # 跳过第 4~5 组
    python3 <方法论仓库>/scripts/doctor.py --json                # 只输出 JSON

退出码：
    0 = 无 error（**可以有 warn**）
    1 = ≥1 error
    2 = 用法/环境错误（无法定位仓库根、--project 路径不存在或非目录、非法 flag）
    warn **永不**影响退出码：doctor 要能被当作 CI/门禁判据，而 warn 是"值得知道但不阻塞"。

只读铁律：全程零写入（不 mkdir 项目、不建软链、不在仓库内生成 __pycache__）。
第 2 组要编译 .py，一律 py_compile.compile(..., cfile=<TMP>/...) 把产物写到临时目录。

为什么默认不调用 check_codex_backend.py、也不默认调 stack.py verify：
    前者除结构检查外还要求三角色 model **等于当前活动模型**（编排期门禁，不是安装缺陷），
    并且 shell out 到 codex CLI（没有 codex 的机器上 doctor 就跑不了）；
    后者校验的是栈内容一致性，且 diamond-agent 的在飞栈正被其他窗口并发推进——
    把移动靶纳入 doctor 的退出码，等于制造假 authority。故 verify 设为 --stack-verify 显式开关。
"""

from __future__ import annotations

import argparse
import json
import os
import py_compile
import re
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

# 防止 import _common 时在本仓库 scripts/ 下生成 __pycache__（会污染仓库清单并烙进本机绝对路径）。
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    SkillManifestError,
    codex_home,
    emit,
    iter_skills,
    repo_root,
)

ROLES = ("designer", "executor", "reviewer")
SANDBOX_EXPECT = {"designer": "read-only", "executor": "workspace-write", "reviewer": "read-only"}
REQUIRED_TOML_KEYS = ("model", "sandbox_mode", "approval_policy", "developer_instructions")
JSON_KEYS = ("group", "id", "level", "object", "message", "detail")
# 第 1 组「同包 skill 齐全性」判据的规范名单（来源：全局硬约束 5「skill 名不变」）。
# **只服务这一条判据**：挂载与扫描逻辑仍完全由磁盘驱动（`_common.iter_skills`），所以这份常量不是
# 第二份清单真源，而是「本包承诺分发哪几个 skill」的显式声明。
# 为什么必须有它：`iter_skills` 只枚举磁盘实存的 skill，删掉一个 skill 目录时第 1 组只会少一行 ok、
# 不报任何 fail —— 最该红的信号反而静默通过（实测缺口）。
CANONICAL_SKILLS = ("explain-task-failure", "exploration-loop", "guided-goal-orchestrator",
                    "methodology-skill-sync", "multi-phase-plan-orchestrator",
                    "single-phase-execution-loop", "work-queue-stack")

# 第 3 组：同包引用的两种形态（$<slug> 点名 / <slug>/子目录 路径引用）
_DOLLAR_REF_RE = re.compile(r"\$([a-z][a-z0-9]*(?:-[a-z0-9]+)+)")
_PATH_REF_RE = re.compile(
    r"(?<![A-Za-z0-9-])([a-z][a-z0-9]*(?:-[a-z0-9]+)+)/(?:references|scripts|agents|SKILL\.md)\b"
)
# 第 9 组：与 stack.py 的 parse_work_plans / parse_issue_index **逐字相同**的 4 条正则。
# 锚点刻意用**内容**而不是行号：行号一改就失效，而失效的锚点比没有锚点更坏（它看起来还在把关）。
# 契约由本文件的 _group9_stack_contract（检查项 `9.contract`）机械自校验 —— 它直接读 stack.py 源码，
# 断言这 4 条 `r"…"` 字面量与两个解析函数定义逐字存在，不成立即 error。
_PLAN_ID_RE = re.compile(r"^##\s+(N-\d+)\s*·\s*(.+?)\s*$")
_PLAN_STATUS_RE = re.compile(r"^-\s+\*\*状态\*\*：\s*`?([^`\n]+?)`?\s*$")
_PLAN_PRIORITY_RE = re.compile(r"^-\s+\*\*优先级\*\*：\s*(\S+)\s*$")
_ISSUE_ROW_RE = re.compile(r"^\|\s*(ISS-\d+)\s*\|(.*)$")
# 第 10 组：判据 = 「skill 正文里还写着项目侧 `.agents/skills/<slug>/` 前缀」。
# Phase 2 放宽（裁决 R14 / 偏离 D3）：去掉 `/scripts/` 尾巴、扫描范围加 `skills/*/references/*.md`。
# 为什么必须放宽：窄判据只跟踪 3 处，而同类失效引用实测有 6 处 / 5 文件 —— 剩下 3 处在
# references/ 里，于是「warn 归零」会在仍有失效引用时变绿，那是**假 PASS**。放宽是加强门禁。
# 为什么放宽不引入噪音：docs/migration-diamond-agent.md ③ 担心的「十几条黄噪音」来自
# `scratch/workbench/…` 的提及（v3→v4 迁移史的合法叙述，stack.py 的 migrate 命令依赖这套旧路径
# 语义）；本正则只匹配 `.agents/skills/<slug>/` 前缀，两者命中集合**零交集**（实测）。
_LEGACY_PREFIX_RE = re.compile(r"\.agents/skills/[A-Za-z0-9_-]+/")
_STACK_SCRIPT_REL = "skills/work-queue-stack/scripts/stack.py"
# 第 9 组的 `contract` 项：跨组件契约的内容锚点。四个正则字面量在 stack.py 源码里都写作 r"…"，
# 故可直接子串匹配；两个解析函数名是 survey 与本组共用的口径来源。
_STACK_CONTRACT_RE = (_PLAN_ID_RE, _PLAN_STATUS_RE, _PLAN_PRIORITY_RE, _ISSUE_ROW_RE)
# 函数名用 `^def <name>\b`（多行模式）而不是裸子串：裸子串会把 `def parse_work_plans_v2`
# 也算命中，于是「函数被改名」这条最典型的漂移反而测不出来。
_STACK_CONTRACT_FUNCS = ("parse_work_plans", "parse_issue_index", "load_layout")
# 第 8 组：`workstacks/config.json` 的 schema。真源是 stack.py 的 load_layout（本文件不 shell out、
# 也不 import skill 脚本，故此处是**受 `9.contract` 机械看护的镜像**：它会断言这些键名与 load_layout
# 仍在 stack.py 源码里，键名一旦漂移，`9.contract` 先报 error，不会让本组静默按旧 schema 下结论）。
_LAYOUT_CONFIG_REL = "workstacks/config.json"
# stack.py 里声明布局键与默认值的那几行（**逐字**）。doctor 的 _LAYOUT_KEYS / _LAYOUT_DEFAULTS
# 直接从这些字面量派生，且 `9.contract` 会断言它们在 stack.py 源码里逐字存在 ——
# 于是「schema 镜像漂移」在构造上不可能：改任一侧都会让字面量不再匹配，`9.contract` 立刻 error。
# （不用 `'"issue_doc"' in src` 这种裸子串判据：实测它会被 stack.py 里其他位置的
#   同名出现喂饱，把「键被改名」这条最典型的漂移漏掉。）
_STACK_LAYOUT_LITERAL_KEYS = 'LAYOUT_KEYS = ("workstack_root", "plan_doc", "issue_doc")'
_STACK_LAYOUT_LITERAL_DEFAULTS = (
    'WORKSTACK_ROOT = "workstacks"',
    'PLAN_DOC = Path("docs/operations/next-work-plan.md")',
    'ISSUE_DOC = Path("docs/operations/issues.md")',
)
_LAYOUT_KEYS = tuple(re.findall(r'"([^"]+)"', _STACK_LAYOUT_LITERAL_KEYS))
_LAYOUT_DEFAULTS = dict(zip(_LAYOUT_KEYS, ("workstacks",
                                          "docs/operations/next-work-plan.md",
                                          "docs/operations/issues.md")))
# 第 3 / 10 组共用的扫描范围（skills/*/SKILL.md + skills/*/references/*.md）
_SKILL_TEXT_GLOBS = ("*/SKILL.md", "*/references/*.md")


class DoctorUsageError(Exception):
    pass


def _row(group, level, obj, message, detail=None, *, key):
    """产出一行检查结果。**id 不在这里拼** —— 由 main() 收齐全部 rows 后按 `<组号>.<稳定键>` 统一拼装。

    `key` 是**必填关键字参数**，取值规则见模块 docstring 的「id 规则」与
    docs/migration-diamond-agent.md ⑦ 的键表：健康态行的键 = 对象身份（skill 名 / 脚本 stem / 角色名 /
    单例检查的固定名），故同一检查在 `--project` 与 `--no-global` 下 id 相同；违规诊断行用 `<键>-<i>`
    位置后缀，只对当次输出有意义、不得被文档或脚本索引。

    曾经各组自己传 item 号，于是 `_group8` / `_group9` 里出现过硬编码的 `2` 与 `None`，
    同一组内产出重复 id（实测 `8.1` 出现两次），而 `--json` 的消费方正是按 id 定位检查项的。
    后来改成「组内 1-based 序号」（`_renumber`），重复 id 消失了，但 id 变成**位置化**的：
    同一条契约检查在 `--project` 下是 `9.2`、`--no-global` 下是 `9.1`，按 id 索引的消费者会
    **静默指向另一条检查**。改成稳定语义键之后两个问题都不会复发；末尾还有唯一性断言兜底（不成立 exit 2）。
    """
    return {"group": group, "id": None, "key": key, "level": level, "object": obj,
            "message": message, "detail": detail or []}


def _assign_ids(rows):
    """按 `id = <组号>.<稳定键>` 统一拼装 id（键由各组在 `_row(..., key=…)` 处一次性给出）。"""
    for r in rows:
        r["id"] = f"{r['group']}.{r['key']}"
    return rows


def _skill_text_files(repo: Path):
    """第 3 组与第 10 组共用的扫描范围（`_SKILL_TEXT_GLOBS`）。

    两组共用一份范围定义是刻意的：第 10 组判据放宽（裁决 R14）之所以成立，前提是它扫的范围
    与第 3 组一致 —— 否则「引用可解析」与「前缀已布局无关」两条结论会建立在不同文件集上，
    一条绿另一条黄时没人能说清是哪一份范围在起作用。
    """
    out = []
    for g in _SKILL_TEXT_GLOBS:
        out += sorted((repo / "skills").glob(g))
    return out


# ------------------------------------------------------------ 1 仓库自完整

def _group1(repo: Path, skills, manifest_error):
    rows = []
    if manifest_error:
        for i, problem in enumerate(manifest_error.problems, start=1):
            # object 与 message 不得重复同一段前缀（C1）：problem 的形态是 "<对象>: <结论>"，
            # 拆开各归其位 —— object 用于定位，message 用于说结论。
            obj, sep, rest = problem.partition(":")
            rows.append(_row(1, "fail", obj, rest.strip() if sep else problem, key=f"manifest-{i}"))
        return rows
    present = set()
    for name, d, fname, desc in skills:
        present.add(name)
        if not desc:
            rows.append(_row(1, "fail", name, "SKILL.md 可解析，但 description 为空",
                             [f"文件：{d / 'SKILL.md'}"], key=name))
        else:
            rows.append(_row(1, "ok", name, "SKILL.md 可解析，name/description 齐备",
                             [f"目录名 == frontmatter name == {fname}"], key=name))
    # 齐全性判据：**缺才报**（健康态零新增行，故不影响行数推导）。
    # 没有它的话，删掉一个 skill 目录只会让上面少一行 ok —— 「本包承诺分发的 skill 少了一个」
    # 这条最该红的信号反而静默通过。名单来源见 CANONICAL_SKILLS 的注释。
    for missing in sorted(set(CANONICAL_SKILLS) - present):
        rows.append(_row(1, "fail", missing, "同包 skill 缺失（哪一层没装：仓库 skills/）",
                         [f"期望存在：{repo / 'skills' / missing}",
                          f"本仓库现有：{', '.join(sorted(present)) or '(空)'}",
                          "本行只判仓库自身；全局层（<codex_home>/skills）与项目层"
                          "（<PROJECT>/.agents/skills）的缺失分别由第 4 / 第 7 组报告。"],
                         key=f"missing-{missing}"))
    return rows


# ------------------------------------------------------------ 2 脚本可编译

def _group2(repo: Path):
    rows = []
    pyc_dir = Path(tempfile.gettempdir()) / "am-doctor-pyc"
    try:
        pyc_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return [_row(2, "fail", str(pyc_dir), f"无法创建 py_compile 输出目录：{exc}", key="pyc-dir")]
    scripts = sorted((repo / "scripts").glob("*.py"))
    scripts += sorted((repo / "skills").glob("*/scripts/*.py"))
    if not scripts:
        return [_row(2, "ok", "skills/*/scripts/*.py", "没有需要编译的脚本", key="none")]
    for py in scripts:
        cfile = str(pyc_dir / (py.name + "c"))
        try:
            # cfile 一律指向 <TMP>：裸 python3 -m py_compile 会在源目录旁生成 __pycache__
            py_compile.compile(str(py), cfile=cfile, doraise=True)
            rows.append(_row(2, "ok", py.name, f"py_compile 通过（cfile={cfile}）", key=py.stem))
        except Exception as exc:
            rows.append(_row(2, "fail", py.name, f"{type(exc).__name__}: {exc}",
                             [f"文件：{py}"], key=py.stem))
    return rows


# ------------------------------------------------------------ 3 同包引用齐全

def _group3(repo: Path, names, expect):
    """同包引用齐全。

    issue 7 的**同文件共现启发式**：`$<slug>` 正则无法区分「同仓库 skill」与「Codex 自带的外部 skill」
    （`$template-creator`、`$skill-creator` 之类）。一旦正文出现对包外 skill 的 `$点名`，本组就会从
    「安装健康判据」变成**假阻塞**。故：`$<slug>` 命中且 slug 不在仓库 skills/ 时，**只有同一文件内**
    该 slug 也以 `<slug>/{references,scripts,agents,SKILL.md}` 形态出现（= 同包意图证据）才判 fail，
    否则视为外部 skill 点名、跳过，并在 ok 行 message 里计数披露（不静默）。

    刻意**不引入** `--external-skill` 白名单：零配置优先，白名单会把维护成本转嫁给每个 CI 与文档消费者。
    已知漏报：同包 `$点名` 所在文件恰好没有任何路径引用时会被当成外部 skill 放过（登记在
    docs/migration-diamond-agent.md ⑦ 的残留风险里）。
    """
    rows = []
    known = set(names)
    missing = []
    checked = 0
    external = 0
    files = _skill_text_files(repo)
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        # 先把本文件里以**路径形态**出现的 slug 收齐，作为「引用者确实在说同包 skill」的证据。
        cooccur = {m.group(1) for m in _PATH_REF_RE.finditer(text)}
        for lineno, line in enumerate(text.splitlines(), start=1):
            for rx in (_DOLLAR_REF_RE, _PATH_REF_RE):
                for m in rx.finditer(line):
                    ref = m.group(1)
                    if ref in known:
                        checked += 1
                        continue
                    if rx is _DOLLAR_REF_RE and ref not in cooccur:
                        external += 1
                        continue
                    checked += 1
                    missing.append((path, lineno, ref))
    for name in expect or ():
        if name not in known:
            missing.append((None, 0, name))
    if missing:
        for i, (path, lineno, ref) in enumerate(missing, start=1):
            if path is None:  # 来自 --expect，没有引用方文件
                rows.append(_row(3, "fail", f"--expect {ref}",
                                 "本仓库 skills/ 下不存在（--expect 要求它必须在；哪一层没装：仓库 skills/）",
                                 [f"期望存在：{repo / 'skills' / ref}",
                                  f"本仓库现有：{', '.join(sorted(known)) or '(空)'}"],
                                 key=f"refs-{i}"))
                continue
            try:
                rel = path.relative_to(repo)
            except ValueError:
                rel = path
            rows.append(_row(3, "fail", f"{rel} → {ref}",
                             "被引用但仓库内不存在（哪一层没装：仓库 skills/）",
                             [f"引用方：{rel}:{lineno}", f"期望存在：{repo / 'skills' / ref}"],
                             key=f"refs-{i}"))
        return rows
    message = f"同包引用 {checked} 处全部可解析"
    if external:
        message += (f"（另有 {external} 处 $<slug> 视为外部 skill：同文件内没有该 slug 的路径形态共现，"
                    "按启发式跳过，不判缺陷）")
    rows.append(_row(3, "ok", None, message,
                     [f"扫描范围：{len(files)} 个文件（{' + '.join('skills/' + g for g in _SKILL_TEXT_GLOBS)}）",
                      "判据形态：$<slug> 与 <slug>/{references,scripts,agents,SKILL.md}",
                      "外部 skill 启发式：$<slug> 未知且同文件无路径形态共现 → 视为包外点名并跳过（计数披露在 message 里）。"],
                     key="refs"))
    return rows


# ------------------------------------------------------------ 4/5 全局挂载

def _group4(home: Path, repo: Path, names, no_global: bool):
    root = home / "skills"
    if no_global:
        return [_row(4, "ok", str(root), "N/A（--no-global：跳过第 4~5 组）", key="global")]
    if not root.exists():
        # 运行时指引一律给**解析后的真实路径**：裸的仓库级相对路径只在「cwd 恰好是仓库根」时才对，
        # 而 doctor 的仓库根由 __file__ 推导、与 cwd 无关（第 12 组把这条口径固化成机械判据）。
        return [_row(4, "warn", str(root),
                     f"{root} 不存在：尚未安装，运行 {repo}/scripts/install.py", key="global")]
    rows = []
    for name in names:
        link = root / name
        target = repo / "skills" / name
        if not link.exists() and not link.is_symlink():
            rows.append(_row(4, "fail", name, "未安装（路径不存在）",
                             [f"期望：{link} → {target}", f"放行：{repo}/scripts/install.py"], key=name))
        elif not link.is_symlink():
            rows.append(_row(4, "fail", name,
                             '是实体目录而非软链（违反"两端只能是软链"不变量）',
                             [f"现状：{link}", f"期望：软链 → {target}"], key=name))
        else:
            real = Path(os.path.realpath(link))
            if real == target.resolve():
                rows.append(_row(4, "ok", name, f"软链正确指向本仓库（{real}）", key=name))
            else:
                rows.append(_row(4, "fail", name, "是软链但指向别处",
                                 [f"当前→{real}", f"期望→{target.resolve()}",
                                  f"放行：{repo}/scripts/install.py --adopt-symlink"], key=name))
    return rows


def _group5(home: Path, no_global: bool):
    root = home / "skills"
    if no_global:
        return [_row(5, "ok", str(root / ".system"), "N/A（--no-global：跳过第 4~5 组）", key="system")]
    if not root.exists():
        return [_row(5, "warn", str(root / ".system"),
                     f"{root} 不存在：无从判断 .system 是否被误伤，跳过", key="system")]
    sysdir = root / ".system"
    if sysdir.is_dir() and not sysdir.is_symlink():
        return [_row(5, "ok", ".system", "仍是实体目录（未被触碰）",
                     ["它是 Codex 自带 skill 的实体真源，且本身被当作一个独立 skill 根。"], key="system")]
    return [_row(5, "fail", ".system",
                 "已被替换为软链或缺失：install.py 可能越界操作，请立即检查",
                 [f"现状：{'不存在' if not sysdir.exists() else ('软链 → ' + os.path.realpath(sysdir) if sysdir.is_symlink() else '非目录')}",
                  f"期望：{sysdir} 是实体目录"], key="system")]


# ------------------------------------------------------------ 6 项目角色配置

def _group6(project, repo: Path):
    # 语义与 skills/single-phase-execution-loop/scripts/check_codex_backend.py 的 load_role_configs
    # 对齐（越界校验 + 四个必填字段 + sandbox_mode 期望值），但**不比对活动模型、不 shell out 到 codex**：
    # 那是编排期门禁，不是安装健康。
    # **未来工作（未排期）**：若给 check_codex_backend.py 加 --structure-only，本组可改为 subprocess
    # 复用并删除这段自实现。Phase 2 明确**不做**（裁决 R17）：计划范围未列它，且它会让 doctor 同时
    # 依赖「外部脚本可执行」与「刚移位的文件在位」两个条件，失败模式叠加，也与 §4.5「doctor 不 shell
    # out」同源原则冲突。这段重复是文档明示「唯一被接受的重复」，双向留痕见
    # docs/migration-diamond-agent.md 的「互指注释留痕」。
    rows = []
    if project is None:
        return [_row(6, "ok", "--project",
                 "N/A（未给 --project：跳过项目侧第 6~8 组、第 9 组的长期池解析与第 11 项；"
                 "第 9 组的跨组件契约是仓库侧的，照跑）", key="roles")]
    codex_dir = project / ".codex"
    if not codex_dir.is_dir():
        return [_row(6, "warn", str(codex_dir),
                     f"{codex_dir} 不存在：运行 {repo}/scripts/bootstrap_project.py {project} --backend codex",
                     key="codex-dir")]
    registry_path = codex_dir / "config.toml"
    if not registry_path.is_file():
        return [_row(6, "fail", str(registry_path), "config.toml 不存在",
                     [f"运行 {repo}/scripts/bootstrap_project.py {project} --backend codex"], key="config")]
    try:
        registry = tomllib.loads(registry_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        return [_row(6, "fail", str(registry_path), f"config.toml 不可解析：{exc}", key="config")]
    agents = registry.get("agents") if isinstance(registry.get("agents"), dict) else {}
    item = 1
    for role in ROLES:
        reg = agents.get(role)
        if not isinstance(reg, dict):
            rows.append(_row(6, "fail", role, "缺少角色注册 agents.%s" % role, key=role)); item += 1
            continue
        config_file = str(reg.get("config_file") or "")
        if not config_file:
            rows.append(_row(6, "fail", role, "缺少 config_file", key=role)); item += 1
            continue
        config_path = (registry_path.parent / config_file).resolve()
        try:
            config_path.relative_to(registry_path.parent.resolve())
        except ValueError:
            rows.append(_row(6, "fail", role, f"config_file 越出 .codex（{config_path}）", key=role))
            item += 1
            continue
        if not config_path.is_file():
            rows.append(_row(6, "fail", role, f"角色配置文件不存在（{config_path}）", key=role)); item += 1
            continue
        try:
            payload = tomllib.loads(config_path.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as exc:
            rows.append(_row(6, "fail", role, f"{config_path.name} 不可解析：{exc}", key=role)); item += 1
            continue
        bad = [k for k in REQUIRED_TOML_KEYS if not str(payload.get(k) or "").strip()]
        if bad:
            rows.append(_row(6, "fail", role,
                             f"{config_path.name} 缺少非空字段：{', '.join(bad)}", key=role)); item += 1
            continue
        got = str(payload["sandbox_mode"])
        if got != SANDBOX_EXPECT[role]:
            rows.append(_row(6, "fail", role,
                             f"sandbox_mode={got} 应为 {SANDBOX_EXPECT[role]}",
                             [f"文件：{config_path}"], key=role)); item += 1
            continue
        rows.append(_row(6, "ok", role,
                         f"注册与角色配置齐备（sandbox_mode={got}, approval_policy={payload['approval_policy']}, model={payload['model']}）",
                         [f"config_file={config_file}"], key=role))
        item += 1
    return rows


# ------------------------------------------------------------ 7 项目侧软链

def _group7(project, repo: Path, names):
    if project is None:
        return []
    rows = []
    root = project / ".agents" / "skills"
    item = 1
    for name in names:
        link = root / name
        target = (repo / "skills" / name).resolve()
        if not link.exists() and not link.is_symlink():
            rows.append(_row(7, "warn", name, "项目内未挂载（Cursor 侧将看不到）",
                             [f"期望：{link} → {target}",
                              f"放行：{repo}/scripts/install.py --project-link <PROJECT>"], key=name))
        elif not link.is_symlink():
            rows.append(_row(7, "fail", name, "项目内是实体目录（不变量要求只能是软链）",
                             [f"现状：{link}",
                              "该目录可能未被 Git 跟踪，替换前先提交或备份",
                              f"放行：{repo}/scripts/install.py --project-link <PROJECT> "
                              "--replace-dir --backup-dir <DIR>"], key=name))
        else:
            real = Path(os.path.realpath(link))
            if real == target:
                rows.append(_row(7, "ok", name, f"项目内软链同源（{real}）", key=name))
            else:
                rows.append(_row(7, "fail", name, "项目内软链指向别处（两端必须同源）",
                                 [f"当前→{real}", f"期望→{target}"], key=name))
        item += 1
    cursor_link = project / ".cursor" / "skills"
    if cursor_link.is_symlink():
        real = Path(os.path.realpath(cursor_link))
        want = (project / ".agents" / "skills").resolve()
        if real == want:
            rows.append(_row(7, "ok", ".cursor/skills",
                             f"→ ../.agents/skills（{os.readlink(cursor_link)}）", key="cursor-skills"))
        else:
            rows.append(_row(7, "warn", ".cursor/skills",
                             f"是软链但不指向 ../.agents/skills（当前→{real}）", key="cursor-skills"))
    elif cursor_link.exists():
        rows.append(_row(7, "warn", ".cursor/skills", "存在但不是软链", key="cursor-skills"))
    else:
        rows.append(_row(7, "warn", ".cursor/skills",
                         "不存在（Cursor 侧看不到项目 skill；Codex 侧不受影响）", key="cursor-skills"))
    return rows


# ------------------------------------------------------------ 8 栈目录就位

# 第 8 组：`workstacks/.gitignore` 缺规则时按规则名给稳定键（位置化序号会让 id 随缺失组合漂移）。
_GITIGNORE_RULE_KEYS = {"*/history/": "gitignore-history", "_current.json": "gitignore-pointer"}


def _group8(project, repo: Path):
    if project is None:
        return []
    rows = []
    base = project / "workstacks"
    if not base.is_dir():
        return [_row(8, "warn", str(base), "workstacks/ 不存在",
                     [f"运行 {repo}/scripts/bootstrap_project.py <PROJECT>（不加 --skip-operations）"],
                     key="dir")]
    gi = base / ".gitignore"
    if not gi.is_file():
        rows.append(_row(8, "warn", str(gi), "workstacks/.gitignore 不存在",
                         ["栈本体应纳入 Git；history/ 与 _current.json 应排除。"], key="gitignore"))
    else:
        text = gi.read_text(encoding="utf-8")
        absent = [r for r in ("*/history/", "_current.json") if r not in text]
        if absent:
            for rule in absent:
                rows.append(_row(8, "warn", str(gi), f"workstacks/.gitignore 缺少 {rule} 规则",
                                 ["指针会脏 Git" if rule == "_current.json"
                                  else "迁移备份会让每次 diff 多出无信息量的内容"],
                                 key=_GITIGNORE_RULE_KEYS[rule]))
        else:
            rows.append(_row(8, "ok", str(gi), "含 */history/ 与 _current.json 两条规则", key="gitignore"))
    ptr = base / "_current.json"
    if ptr.exists():
        try:
            data = json.loads(ptr.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("顶层不是 JSON 对象")
            rows.append(_row(8, "ok", str(ptr), f"可解析为 JSON 对象（campaign={data.get('campaign')}）",
                             key="pointer"))
        except (json.JSONDecodeError, ValueError, OSError) as exc:
            rows.append(_row(8, "warn", str(ptr), f"_current.json 不可解析：{exc}", key="pointer"))
    else:
        rows.append(_row(8, "ok", str(ptr), "无当前栈指针（克隆后的正常状态；恢复时按语义识别或用户指定）",
                         key="pointer"))
    rows += _group8_layout_config(project / _LAYOUT_CONFIG_REL)
    return rows


def _group8_layout_config(cfg: Path):
    """`workstacks/config.json` 感知（裁决 R15 / 偏离 D4）。

    - **文件不存在 → 不加任何行**。这是关键：绝大多数项目（含 diamond-agent）没有该文件，
      加一行 N/A 会让它们的 doctor 输出凭空多一行，而 doctor 输出是等价性回归的比对对象。
    - 解析失败 / 非法 → **1 行 error**：stack.py 会对同一份文件 `exit 2`，于是所有栈命令都不可用，
      这不是「值得知道但不阻塞」，是坏的。
    - 声明了非默认值 → **1 行 warn**：本组与第 9 组都按**默认**路径检查（`workstacks/`、
      `docs/operations/`），自定义布局下这两组的结论**不覆盖**实际位置 —— 如实说出来，
      比让用户以为「doctor 全绿 = 我的自定义布局也被检查过了」要好。对齐留待 Phase 3。
    """
    if not cfg.exists():
        return []
    try:
        raw = json.loads(cfg.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [_row(8, "fail", str(cfg), f"workstacks/config.json 不可解析（{exc}）",
                     _layout_config_detail(), key="config")]
    except OSError as exc:
        return [_row(8, "fail", str(cfg), f"workstacks/config.json 读取失败（{exc}）",
                     _layout_config_detail(), key="config")]
    if not isinstance(raw, dict):
        return [_row(8, "fail", str(cfg),
                     f"workstacks/config.json 根节点必须是 JSON object，实际是 {type(raw).__name__}",
                     _layout_config_detail(), key="config")]
    unknown = sorted(set(raw) - set(_LAYOUT_KEYS))
    if unknown:
        return [_row(8, "fail", str(cfg),
                     f"workstacks/config.json 含未知键 {', '.join(unknown)}（只允许 {' / '.join(_LAYOUT_KEYS)}）",
                     _layout_config_detail(), key="config")]
    bad = []
    for key in _LAYOUT_KEYS:
        if key not in raw:
            continue
        value = raw[key]
        if not isinstance(value, str) or not value.strip():
            bad.append(f"{key}={value!r}（必须是非空字符串）")
            continue
        rel = Path(value.strip())
        if rel.is_absolute():
            bad.append(f"{key}={value!r}（必须是仓库根相对路径）")
        elif ".." in rel.parts:
            bad.append(f"{key}={value!r}（不得含 `..` 段）")
        elif value.strip() == "." and key == "workstack_root":
            bad.append(f"{key}={value!r}（不得为 \".\"：会与仓库根重合）")
    if bad:
        return [_row(8, "fail", str(cfg), "workstacks/config.json 非法：" + "；".join(bad),
                     _layout_config_detail(), key="config")]
    custom = {k: str(raw[k]) for k in _LAYOUT_KEYS
              if k in raw and str(raw[k]) != _LAYOUT_DEFAULTS[k]}
    if not custom:
        return [_row(8, "ok", str(cfg),
                     "workstacks/config.json 存在且全部取默认值（等价于没有该文件）", key="config")]
    return [_row(8, "warn", str(cfg),
                 "workstacks/config.json 声明了非默认布局："
                 + "、".join(f"{k}={v}" for k, v in sorted(custom.items())),
                 ["第 8/9 组按默认路径检查，结论不覆盖自定义位置（对齐留待 Phase 3）。",
                  "stack.py 自身按该配置解析，故栈命令不受影响；受影响的是 doctor 这两组的覆盖面。"],
                 key="config")]


def _layout_config_detail():
    """与 stack.py 的 `_layout_die` 同源的期望形态说明（stack.py 会对同一份文件 exit 2）。"""
    return ["stack.py 会对这份配置 exit 2，于是全部栈命令不可用。",
            "期望形态：一个 JSON object，三个键全部可选，值必须是**仓库根相对路径**字符串：",
            '  {"workstack_root": "workstacks",',
            '   "plan_doc": "docs/operations/next-work-plan.md",',
            '   "issue_doc": "docs/operations/issues.md"}',
            "真源：skills/work-queue-stack/scripts/stack.py 的 load_layout（schema 见 "
            "skills/work-queue-stack/references/stack-schema.md）。"]


# ------------------------------------------------------------ 9 长期池可解析

def _parse_plans(path: Path):
    out = []
    if not path.exists():
        return out
    cur = None
    for line in path.read_text(encoding="utf-8").splitlines():
        m = _PLAN_ID_RE.match(line)
        if m:
            cur = {"id": m.group(1), "title": m.group(2)}
            out.append(cur)
            continue
        if cur is None:
            continue
        m = _PLAN_STATUS_RE.match(line)
        if m:
            cur["status"] = m.group(1).strip()
            continue
        m = _PLAN_PRIORITY_RE.match(line)
        if m:
            cur["priority"] = m.group(1).strip()
    return out


def _parse_issues(path: Path):
    out = []
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        m = _ISSUE_ROW_RE.match(line)
        if m:
            out.append(m.group(1))
    return out


def _group9_stack_contract(repo: Path):
    """跨组件契约的机械自校验（内容锚点，不用行号）。

    为什么要有这一项：Phase 1 用「stack.py:1348/1354/1358/1371」这样的**行号**当契约锚点，
    而 stack.py 一改行号就全错，锚点却还留在注释里、看起来仍在把关 —— 失效的锚点比没有锚点更坏。
    本项直接读 stack.py 源码断言契约本身（4 条正则字面量 + 2 个解析函数 + 布局配置 schema 的键名），
    于是「改一侧必须同步另一侧」从一句嘱咐变成一条会红的检查。
    与 `--project` **无关**（它校验的是仓库自身），故未给 --project 时本项照跑。
    """
    stack_py = repo / _STACK_SCRIPT_REL
    if not stack_py.is_file():
        return [_row(9, "fail", _STACK_SCRIPT_REL, "stack.py 不存在，无法校验跨组件契约",
                     [f"期望位置：{stack_py}"], key="contract")]
    try:
        src = stack_py.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return [_row(9, "fail", _STACK_SCRIPT_REL, f"读取 stack.py 失败：{exc}", key="contract")]
    missing = [f'r"{rx.pattern}"' for rx in _STACK_CONTRACT_RE if f'r"{rx.pattern}"' not in src]
    missing += [f"def {f}" for f in _STACK_CONTRACT_FUNCS
                if not re.search(rf"^def {f}\b", src, re.MULTILINE)]
    # 第 8 组 config.json 判据用的 schema 是 stack.py:load_layout 的镜像，同样由本项看护：
    # 键名一旦改名，第 8 组就会按旧 schema 下结论 —— 那正是「doctor 说谎」那一类缺陷。
    missing += [lit for lit in (_STACK_LAYOUT_LITERAL_KEYS, *_STACK_LAYOUT_LITERAL_DEFAULTS)
                if lit not in src]
    if missing:
        return [_row(9, "fail", _STACK_SCRIPT_REL,
                     "跨组件契约被打破：stack.py 源码里找不到下列内容锚点",
                     [f"缺失：{m}" for m in missing] +
                     ["4 条正则与 2 个解析函数是 doctor 第 9 组与 stack.py survey 的共同口径；",
                      "load_layout 与三个布局键名是第 8 组 config.json 判据的真源。",
                      "改任一侧都必须同步另一侧（本项就是那道同步门禁）。"], key="contract")]
    return [_row(9, "ok", _STACK_SCRIPT_REL,
                 "跨组件契约成立：4 条池解析正则字面量、parse_work_plans / parse_issue_index / "
                 "load_layout 三个函数定义、以及布局键与默认值的 4 行字面量均在 stack.py 源码里",
                 ["锚点是**内容**而非行号：stack.py 内部重排、增删函数都不会让本项假报。"],
                 key="contract")]


def _group9(project, repo: Path):
    if project is None:
        # 长期池解析是项目侧的，跳过；跨组件契约是仓库侧的，照跑。
        return _group9_stack_contract(repo)
    plan = project / "docs" / "operations" / "next-work-plan.md"
    issue = project / "docs" / "operations" / "issues.md"
    rows = []
    for p, pkey in ((plan, "plan-file"), (issue, "issue-file")):
        if not p.exists():
            rows.append(_row(9, "warn", str(p), "不存在",
                             ["survey 的长期待办池少一个来源；运行 bootstrap_project.py（不加 --skip-operations）"],
                             key=pkey))
    plans = _parse_plans(plan)
    issues = _parse_issues(issue)
    if not plans and not issues:
        rows.append(_row(9, "warn", "docs/operations/",
                         "两个池文件均解析出 0 条：survey 会 exit 0（两池皆空是正常运行态，不是错误）；"
                         "两个池文件都不存在时它改打 bootstrap_project.py 指引",
                         [f"{plan}: 0 条", f"{issue}: 0 条",
                          "两种空池的输出**可区分**：文件都缺失 → bootstrap 指引；文件存在但 0 条 → 本行这种 warn。"],
                         key="pool"))
    else:
        ids = ", ".join(p["id"] for p in plans) or "无"
        rows.append(_row(9, "ok", "docs/operations/",
                         f"next-work-plan.md 解析出 {len(plans)} 条（{ids}）；issues.md {len(issues)} 条",
                         ["4 条正则与 stack.py 的 parse_work_plans / parse_issue_index 逐字相同"
                          "（由下一项机械校验，不靠行号）"], key="pool"))
    return rows + _group9_stack_contract(repo)


# ------------------------------------------------------------ 10 暂存期路径前缀

def _group10(repo: Path):
    rows = []
    hits = []
    for path in _skill_text_files(repo):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        # finditer 而非 search：一行里出现两次前缀时，只报一次会低估修复面。
        found = [(i, m.group(0)) for i, line in enumerate(lines, start=1)
                 for m in _LEGACY_PREFIX_RE.finditer(line)]
        if found:
            hits.append((path, found))
    scope = " + ".join("skills/" + g for g in _SKILL_TEXT_GLOBS)
    if not hits:
        return [_row(10, "ok", scope,
                     "没有 .agents/skills/<slug>/ 项目侧前缀残留（路径表述已布局无关）",
                     [f"判据形态：{_LEGACY_PREFIX_RE.pattern}",
                      "Phase 2 放宽（裁决 R14）：去掉 /scripts/ 尾巴 + 扫描范围加 references/，",
                      "否则 references/ 里的同类失效引用会让本组在「warn 归零」时仍然漏报（假 PASS）。",
                      "注：SKILL.md 与 references/ 里另有 scratch/workbench/… 的提及，那是 v3→v4 迁移史的",
                      "    合法叙述（stack.py 的 migrate 命令依赖这套旧路径语义），不是缺陷，且与本判据的",
                      "    命中集合零交集 —— 放宽判据不会把它们变成永久黄噪音。"],
                     key="legacy-prefix")]
    for i, (path, found) in enumerate(hits, start=1):
        rel = path.relative_to(repo)
        rows.append(_row(10, "warn", str(rel),
                         f"{len(found)} 处仍写着 .agents/skills/<slug>/ 项目侧前缀"
                         "（布局相关：换成别的挂载布局就失效）",
                         [f"{rel}:{lineno} → {frag}" for lineno, frag in found] +
                         ["修法：自指写 <本 skill 目录>/scripts/…，跨 skill 写 <skill 根>/<slug>/scripts/…",
                          "    后缀 <slug>/scripts/… 在三种布局下都不变，故既布局无关又被第 3 组校验。"],
                         key=f"legacy-{i}"))
    return rows


# ------------------------------------------------------------ 11 栈内容门禁

def _group11(project, repo: Path, enabled: bool):
    if not enabled:
        return []
    if project is None:
        return [_row(11, "warn", "--stack-verify", "未给 --project，无法定位栈，跳过", key="verify")]
    ptr = project / "workstacks" / "_current.json"
    if not ptr.exists():
        return [_row(11, "warn", str(ptr), "无 _current.json 指针，--stack-verify 跳过",
                     ["指针不入库（workstacks/.gitignore 排除 _current.json），克隆出来的项目本来就没有它。"],
                     key="verify")]
    try:
        campaign = json.loads(ptr.read_text(encoding="utf-8")).get("campaign")
    except (json.JSONDecodeError, OSError) as exc:
        return [_row(11, "warn", str(ptr), f"指针不可解析：{exc}", key="verify")]
    if not campaign:
        return [_row(11, "warn", str(ptr), "指针里没有 campaign 字段，跳过", key="verify")]
    stack_py = repo / _STACK_SCRIPT_REL
    if not stack_py.is_file():
        return [_row(11, "fail", str(stack_py), "stack.py 不存在，无法运行 verify", key="verify")]
    cmd = [sys.executable, str(stack_py), "verify",
           "--repo-root", str(project), "--campaign", str(campaign)]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    out = (proc.stdout or "") + (proc.stderr or "")
    tail = [l for l in out.splitlines() if l.strip()][-8:]
    if proc.returncode == 0:
        return [_row(11, "ok", f"stack.py verify --campaign {campaign}", "exit 0", tail, key="verify")]
    if proc.returncode == 2:
        return [_row(11, "warn", f"stack.py verify --campaign {campaign}",
                     f"exit 2（栈缺失/环境问题，不判 error）", tail, key="verify")]
    return [_row(11, "fail", f"stack.py verify --campaign {campaign}",
                 f"exit {proc.returncode}（原文附后）", tail, key="verify")]


# ------------------------------------------------------------ 12 运行时指引布局无关

# Phase 3 · P3-9：把 Phase 2 的 B7 纯文本 grep **固化成一个检查组**。
# B7 只覆盖 skills/ 下 3 个脚本名的裸相对路径；`scripts/`、`docs/`、`templates/` 内的同类文案扫不到，
# 那次缺陷是靠人工 grep 才发现的。本组把扫描范围扩到全仓库常规文件，并追加一条**正向断言**：
# `<方法论仓库>` 占位符必须在同文件内有定义行（P3-15：占位符运行时不可解析是设计意图内的唯一诚实形态
# ——全局安装后用户机器上未必有仓库克隆——但用户拿到指引后得知道它指什么）。
#
# 判据形态刻意**只匹配裸路径**，不做「裸程序名」泛匹配：docs/README 里有约 20 处「按名提及」的散文
# （`install.py --adopt-symlink` 之类），Phase 2 B7 已定性其非缺陷；泛匹配会把过程真源文档变成永久黄噪音，
# 或逼着重写历史叙述 —— 那正好违背「文档与实现同源」的本意。裸程序名形态**无机械覆盖**，
# 残留风险登记在 docs/migration-diamond-agent.md ⑦。
_G12_BARE_RE = re.compile(r"(?<![/\w.-])scripts/(?:bootstrap_project|install|doctor)\.py")
# 负向后顾 `(?<![\/\w.-])` 天然放行：`<方法论仓库>/scripts/…` 占位符形态、绝对路径、
# `{repo}/scripts/…` f-string 拼接、以及 `skills/<slug>/scripts/…` 跨 skill 形态。
# **正则字面量本身不自命中**：alternation 写成 `(?:bootstrap_project|install|doctor)`，源码里出现的是
# `scripts/(?:…`——`scripts/` 之后紧跟 `(`，不匹配任何一个分支。V7 的阳性对照就是这条性质的自证。
_G12_PLACEHOLDER = "<方法论仓库>"
_G12_DEF_RE = re.compile(r"""<方法论仓库>\s*[`"']{0,2}\s*[=＝]""")
# 扫描范围 = 全仓库常规文件。刻意不含 `.git/`；本仓库的只读铁律保证不产生 `__pycache__`。
_G12_ROOT_FILES = ("README.md",)
_G12_DIR_GLOBS = (("docs", "*.md"), ("scripts", "*.py"))
_G12_SKILL_GLOBS = ("*/SKILL.md", "*/references/*.md", "*/scripts/*.py", "*/agents/*.yaml")


def _group12_files(repo: Path):
    """第 12 组的扫描文件集（排序 + 去重，保证 `bare-<i>` 的编号在同一仓库状态下可复现）。"""
    out = []
    for rel in _G12_ROOT_FILES:
        f = repo / rel
        if f.is_file():
            out.append(f)
    for sub, pat in _G12_DIR_GLOBS:
        out += sorted((repo / sub).glob(pat))
    out += sorted(f for f in (repo / "templates").rglob("*") if f.is_file())
    for pat in _G12_SKILL_GLOBS:
        out += sorted((repo / "skills").glob(pat))
    uniq, seen = [], set()
    for f in out:
        if f not in seen:
            seen.add(f)
            uniq.append(f)
    return sorted(uniq, key=lambda f: str(f))


def _group12(repo: Path):
    rows = []
    files = _group12_files(repo)
    scanned = bare_i = ph_i = 0
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        scanned += 1
        rel = path.relative_to(repo)
        lines = text.splitlines()
        for lineno, line in enumerate(lines, start=1):
            for m in _G12_BARE_RE.finditer(line):
                bare_i += 1
                rows.append(_row(12, "fail", str(rel),
                                 f"运行时指引写着裸仓库级相对路径 {m.group(0)}"
                                 "（只在 cwd 恰好是仓库根时才对，而本仓库的根由 __file__ 推导、与 cwd 无关）",
                                 [f"{rel}:{lineno}",
                                  "修法：写成 `<方法论仓库>/scripts/…` 的占位符形态（并在同文件放定义行），"
                                  "或在脚本里用 f-string 输出 repo_root() 解析后的真实路径。"],
                                 key=f"bare-{bare_i}"))
        if _G12_PLACEHOLDER in text and not any(_G12_DEF_RE.search(ln) for ln in lines):
            ph_i += 1
            rows.append(_row(12, "fail", str(rel),
                             f"用了 {_G12_PLACEHOLDER} 占位符，但同文件没有定义行（用户不知道它指什么）",
                             [f"修法：在本文件加一行定义，形如「{_G12_PLACEHOLDER} = agent-methodology "
                              "仓库根目录（装着 skills/、scripts/、templates/ 的那一层）」。",
                              f"判据形态：{_G12_DEF_RE.pattern}"],
                             key=f"placeholder-{ph_i}"))
    if rows:
        return rows
    return [_row(12, "ok", f"{scanned} 个文件",
                 "运行时指引布局无关：没有裸仓库级相对路径，占位符都有同文件定义行",
                 [f"判据形态（裸路径）：{_G12_BARE_RE.pattern}",
                  f"判据形态（占位符定义行）：{_G12_DEF_RE.pattern}",
                  "扫描范围：README.md + docs/*.md + scripts/*.py + templates/** + "
                  + " + ".join(f"skills/{g}" for g in _G12_SKILL_GLOBS),
                  "按名提及的散文（如「跑一下 install.py --check」）**不在判据内**：Phase 2 B7 已定性其非缺陷，",
                  "    泛匹配会把过程真源文档变成永久黄噪音，或逼着重写历史叙述。",
                  "裸程序名形态**无机械覆盖**（本组只匹配路径形态），见 docs/migration-diamond-agent.md ⑦ 残留风险。"],
                 key="runtime-paths")]


# ------------------------------------------------------------ 13 三角色契约镜像一致

# Phase 3 · 决策 ④：6 个角色模板**保持运行时自包含**。它们是 bootstrap 载荷，渲染进项目后必须
# 脱离本仓库独立生效；指针化会让角色契约依赖运行时文件解析（脆弱，且 Cursor 侧无对应发现机制）。
# 代价是模板与语义真源之间出现**受控重复** —— 于是沿用仓库既有先例（第 8 组镜像 stack.py 的布局 schema、
# 由 `9.contract` 的内容锚断言看护），把重复变成「受看护镜像」：本组断言 role-contract.md 的规范标题锚块
# 与 6 个模板的字段名全集**双向一致**，改任一侧都会让本组变红。
_ROLE_CONTRACT_REL = "skills/single-phase-execution-loop/references/role-contract.md"
_ROLE_HEADINGS_OPEN = "<!-- role-headings-canonical"
_ROLE_HEADINGS_CLOSE = "-->"
_ROLE_HEADINGS_LINE_RE = re.compile(r"^([a-z][a-z0-9_-]*):\s+(.+?)\s*$")
_FIELD_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
# 模板里字段名以中文顿号枚举（codex TOML 的「按以下标题输出：a、b、c。」/「字段为 a、b、c。」）。
# 只认「≥2 个标识符被 `、` 连起来的串」，因此对模板的**措辞**改写不敏感，只对**字段全集**敏感。
_TEMPLATE_ENUM_RUN_RE = re.compile(r"[a-z][a-z0-9_]*(?:、[a-z][a-z0-9_]*)+")
_ROLE_TEMPLATES = {
    "designer": ("templates/codex-agents/designer.toml", "templates/cursor-agents/designer.md"),
    "executor": ("templates/codex-agents/executor.toml", "templates/cursor-agents/executor.md"),
    "reviewer": ("templates/codex-agents/reviewer.toml", "templates/cursor-agents/reviewer.md"),
}


def _parse_role_headings(text: str):
    """解析规范标题锚块。返回 `(block_dict, problems)`；锚块缺失/重复/格式坏时 block_dict 为 None。"""
    lines = text.splitlines()
    starts = [i for i, ln in enumerate(lines) if ln.strip() == _ROLE_HEADINGS_OPEN]
    if not starts:
        return None, [f"锚块缺失：找不到 `{_ROLE_HEADINGS_OPEN}` 行"]
    if len(starts) > 1:
        return None, [f"锚块重复：`{_ROLE_HEADINGS_OPEN}` 出现 {len(starts)} 次（真源只允许一处）"]
    block, closed = [], False
    for ln in lines[starts[0] + 1:]:
        if ln.strip() == _ROLE_HEADINGS_CLOSE:
            closed = True
            break
        block.append(ln)
    if not closed:
        return None, [f"锚块格式坏：`{_ROLE_HEADINGS_OPEN}` 之后没有闭合的 `{_ROLE_HEADINGS_CLOSE}` 行"]
    out, problems = {}, []
    for ln in block:
        if not ln.strip():
            continue
        m = _ROLE_HEADINGS_LINE_RE.match(ln.strip())
        if not m:
            problems.append(f"锚块行不可解析（应为 `<role>: <空格分隔字段名>`）：{ln.strip()!r}")
            continue
        role, fields = m.group(1), m.group(2).split()
        if role not in ROLES:
            problems.append(f"锚块含未知角色 `{role}`（只允许 {' / '.join(ROLES)}）")
            continue
        bad = [f for f in fields if not _FIELD_NAME_RE.match(f)]
        if bad:
            problems.append(f"锚块 `{role}` 行含非法字段名：{', '.join(bad)}")
        if role in out:
            problems.append(f"锚块 `{role}` 行重复出现")
        if not fields:
            problems.append(f"锚块 `{role}` 行字段为空")
        out[role] = fields
    absent = [r for r in ROLES if r not in out]
    if absent:
        problems.append(f"锚块缺角色行：{', '.join(absent)}")
    return out, problems


def _group13(repo: Path):
    rc = repo / _ROLE_CONTRACT_REL
    if not rc.is_file():
        return [_row(13, "fail", _ROLE_CONTRACT_REL, "role-contract.md 不存在，无法校验三角色契约镜像",
                     [f"期望位置：{rc}"], key="role-headings-1")]
    try:
        text = rc.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return [_row(13, "fail", _ROLE_CONTRACT_REL, f"读取 role-contract.md 失败：{exc}",
                     key="role-headings-1")]
    block, problems = _parse_role_headings(text)
    fails = [(_ROLE_CONTRACT_REL, pr,
              ["锚块是本组唯一的机器可读真源；它不可解析则镜像无从校验（fail-closed）。"])
             for pr in problems]
    for role in ROLES:
        fields = (block or {}).get(role) or []
        if not fields:
            continue
        for rel in _ROLE_TEMPLATES[role]:
            tpl = repo / rel
            if not tpl.is_file():
                fails.append((rel, f"`{role}` 角色模板不存在", [f"期望位置：{tpl}"]))
                continue
            try:
                ttext = tpl.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                fails.append((rel, f"`{role}` 角色模板读取失败：{exc}", []))
                continue
            absent = [f for f in fields if f not in ttext]
            if absent:
                fails.append((rel, f"`{role}` 模板缺少契约字段名：{', '.join(absent)}",
                              ["模板是**运行时快照**：渲染进项目后必须脱离本仓库独立生效，",
                               "故字段名必须在模板正文里就位，不能靠指针引用 role-contract.md。"]))
        # **反向**断言：codex 模板的字段枚举必须与锚块全集相等。只查「锚块 ⊆ 模板」的话，
        # 「锚块少写了一个字段」这条最典型的漂移反而测不出来 —— 模板仍然满足子串断言，
        # 于是本组会在契约已经被削掉一项时安静地变绿（假 PASS）。
        codex_rel = _ROLE_TEMPLATES[role][0]
        codex = repo / codex_rel
        if codex.is_file():
            try:
                runs = [m.group(0).split("、")
                        for m in _TEMPLATE_ENUM_RUN_RE.finditer(codex.read_text(encoding="utf-8"))]
            except (OSError, UnicodeDecodeError):
                runs = []
            if not any(set(run) == set(fields) for run in runs):
                best = max(runs, key=len) if runs else []
                fails.append((codex_rel,
                              f"`{role}` 模板的字段枚举与锚块不一致（模板枚举 = {best}；锚块声明 = {fields}）",
                              ["改任一侧都必须同步另一侧（本组就是那道同步门禁）。",
                               f"锚块位置：{_ROLE_CONTRACT_REL} 的 `{_ROLE_HEADINGS_OPEN}` 注释块。"]))
    if fails:
        return [_row(13, "fail", obj, msg, detail, key=f"role-headings-{i}")
                for i, (obj, msg, detail) in enumerate(fails, start=1)]
    return [_row(13, "ok", _ROLE_CONTRACT_REL,
                 "三角色契约镜像一致：锚块的 designer / executor / reviewer 字段名全集与 6 个角色模板双向对齐",
                 ["模板是**运行时快照**，语义真源在 role-contract.md §2；本组是同步门禁，不是第二真源。",
                  "正向：锚块每个字段名在该角色的 codex + cursor 两个模板里都以子串出现；",
                  "反向：codex 模板里以「、」枚举的字段全集与锚块**相等**（防「锚块少写一个字段」静默通过）。"],
                 key="role-headings")]


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="doctor.py",
        description="本仓库安装健康的唯一判据：只读自检：12 个常规检查组 + 1 个 opt-in 组（第 11 项，--stack-verify）；行数随参数与仓库状态变化，以 --json 的 summary.total 为准。",
        epilog="退出码：0=无 error（可以有 warn）；1=≥1 error；2=用法/环境错误。\n"
               "warn 永不影响退出码。全程只读：不 mkdir、不建软链、不在仓库内生成 __pycache__\n"
               "（第 2 组的 py_compile 产物写到 <TMP>/am-doctor-pyc/）。\n"
               "编排期门禁（三角色模型是否等于活动模型）请另跑 "
               "skills/single-phase-execution-loop/scripts/check_codex_backend.py。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--project", metavar="PROJECT",
                        help="项目侧检查（第 6~9 组、第 11 项）的根；缺省则这些组标 N/A 并跳过")
    parser.add_argument("--codex-home", metavar="DIR",
                        help="全局挂载检查（第 4~5 组）的根；口径同 install.py：flag > $CODEX_HOME > ~/.codex")
    parser.add_argument("--expect", metavar="NAME", action="append", default=None,
                        help='可重复；追加要求"这个 skill 必须在仓库里"，缺则 error')
    parser.add_argument("--no-global", action="store_true",
                        help="跳过第 4~5 组（在没有 ~/.codex/skills 的机器上避免全红）")
    parser.add_argument("--stack-verify", action="store_true",
                        help="开启第 11 项（默认关闭：栈内容是编排期门禁，且可能是并发推进的移动靶）")
    parser.add_argument("--codex-bin", metavar="PATH", default="codex",
                        help="预留；Phase 1 doctor 不 shell out 到 codex（见第 6 组注释里的接缝说明）")
    parser.add_argument("--json", action="store_true", help="只输出 JSON，不混排人读行")
    args = parser.parse_args()

    project = None
    if args.project:
        project = Path(args.project).expanduser()
        if not project.is_dir():
            print(f"[FAIL] --project 路径不存在或不是目录：{project}", file=sys.stderr)
            return 2
    home = codex_home(args.codex_home)

    try:
        repo = repo_root()
    except Exception as exc:  # 理论上不会发生；保留 fail-closed 出口
        print(f"[FAIL] 无法定位仓库根：{exc}", file=sys.stderr)
        return 2
    if not (repo / "skills").is_dir():
        print(f"[FAIL] 无法定位仓库根：{repo} 下没有 skills/ 目录", file=sys.stderr)
        return 2

    skills, manifest_error = [], None
    try:
        skills = iter_skills(repo)
    except SkillManifestError as exc:
        manifest_error = exc
    names = [s[0] for s in skills]

    rows = []
    rows += _group1(repo, skills, manifest_error)
    rows += _group2(repo)
    rows += _group3(repo, names, args.expect)
    rows += _group4(home, repo, names, args.no_global)
    rows += _group5(home, args.no_global)
    rows += _group6(project, repo)
    rows += _group7(project, repo, names)
    rows += _group8(project, repo)
    rows += _group9(project, repo)
    rows += _group10(repo)
    rows += _group12(repo)
    rows += _group13(repo)
    rows += _group11(project, repo, args.stack_verify)

    # id 只有一个来源：收齐全部 rows 后按 `<组号>.<稳定键>` 统一拼装
    # （各组自己编号曾经产出重复 id，位置化编号又让 id 随参数漂移，见 _row 的说明）。
    _assign_ids(rows)
    ids = [r["id"] for r in rows]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        # doctor 自己的缺陷不该伪装成「被检查对象有问题」，故走 exit 2（用法/环境错误口径）。
        print(f"[FAIL] doctor 自身缺陷：检查项 id 重复 {dupes}", file=sys.stderr)
        return 2

    errors = sum(1 for r in rows if r["level"] == "fail")
    warns = sum(1 for r in rows if r["level"] == "warn")
    oks = sum(1 for r in rows if r["level"] == "ok")
    code = 1 if errors else 0
    emit(rows, args.json,
         envelope={"status": "error" if errors else "ok", "repo_root": str(repo),
                   "codex_home": str(home), "project": str(project) if project else None},
         rows_key="checks", json_keys=JSON_KEYS,
         summary={"total": len(rows), "error": errors, "warn": warns, "ok": oks},
         summary_line=f"doctor: {len(rows)} 项检查 · {errors} error / {warns} warn · exit={code}",
         exit_code=code)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
