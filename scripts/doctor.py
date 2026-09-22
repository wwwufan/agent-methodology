#!/usr/bin/env python3
"""本仓库安装健康的唯一判据：只读自检 11 项（10 组 + 1 项 opt-in）。

用法（完整参数以 --help 为准）：
    python3 <本仓库>/scripts/doctor.py                       # 仓库自完整 + 全局挂载
    python3 <本仓库>/scripts/doctor.py --project <PROJ>      # 追加项目侧第 6~9 组
    python3 <本仓库>/scripts/doctor.py --no-global           # 跳过第 4~5 组
    python3 <本仓库>/scripts/doctor.py --json                # 只输出 JSON

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

# 第 3 组：同包引用的两种形态（$<slug> 点名 / <slug>/子目录 路径引用）
_DOLLAR_REF_RE = re.compile(r"\$([a-z][a-z0-9]*(?:-[a-z0-9]+)+)")
_PATH_REF_RE = re.compile(
    r"(?<![A-Za-z0-9-])([a-z][a-z0-9]*(?:-[a-z0-9]+)+)/(?:references|scripts|agents|SKILL\.md)\b"
)
# 第 9 组：与 stack.py 的 parse_work_plans / parse_issue_index **逐字相同**的 4 条正则。
# 锚点刻意用**内容**而不是行号：行号一改就失效，而失效的锚点比没有锚点更坏（它看起来还在把关）。
# 契约由本文件的 _group9_stack_contract（检查项 9.2）机械自校验 —— 它直接读 stack.py 源码，
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
# 第 9.2 项：跨组件契约的内容锚点。四个正则字面量在 stack.py 源码里都写作 r"…"，
# 故可直接子串匹配；两个解析函数名是 survey 与本组共用的口径来源。
_STACK_CONTRACT_RE = (_PLAN_ID_RE, _PLAN_STATUS_RE, _PLAN_PRIORITY_RE, _ISSUE_ROW_RE)
# 函数名用 `^def <name>\b`（多行模式）而不是裸子串：裸子串会把 `def parse_work_plans_v2`
# 也算命中，于是「函数被改名」这条最典型的漂移反而测不出来。
_STACK_CONTRACT_FUNCS = ("parse_work_plans", "parse_issue_index", "load_layout")
# 第 8 组：`workstacks/config.json` 的 schema。真源是 stack.py 的 load_layout（本文件不 shell out、
# 也不 import skill 脚本，故此处是**受 9.2 机械看护的镜像**：9.2 会断言这些键名与 load_layout
# 仍在 stack.py 源码里，键名一旦漂移，9.2 先报 error，不会让本组静默按旧 schema 下结论）。
_LAYOUT_CONFIG_REL = "workstacks/config.json"
# stack.py 里声明布局键与默认值的那几行（**逐字**）。doctor 的 _LAYOUT_KEYS / _LAYOUT_DEFAULTS
# 直接从这些字面量派生，且 9.2 会断言它们在 stack.py 源码里逐字存在 ——
# 于是「schema 镜像漂移」在构造上不可能：改任一侧都会让字面量不再匹配，9.2 立刻 error。
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


def _row(group, level, obj, message, detail=None):
    """产出一行检查结果。**id 不在这里拼** —— 由 main() 收齐全部 rows 后按组统一重编号。

    曾经各组自己传 item 号，于是 `_group8` / `_group9` 里出现过硬编码的 `2` 与 `None`，
    同一组内产出重复 id（实测 `8.1` 出现两次），而 `--json` 的消费方正是按 id 定位检查项的。
    编号只留一个来源就不会漂；末尾还有唯一性断言兜底（不成立 exit 2）。
    """
    return {"group": group, "id": None, "level": level, "object": obj,
            "message": message, "detail": detail or []}


def _renumber(rows):
    """按组统一重编号：`id = <组号>.<组内 1-based 序号>`（rows 已按组顺序追加，故序号连续）。"""
    seen = {}
    for r in rows:
        g = r["group"]
        seen[g] = seen.get(g, 0) + 1
        r["id"] = f"{g}.{seen[g]}"
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
        for problem in manifest_error.problems:
            # object 与 message 不得重复同一段前缀（C1）：problem 的形态是 "<对象>: <结论>"，
            # 拆开各归其位 —— object 用于定位，message 用于说结论。
            obj, sep, rest = problem.partition(":")
            rows.append(_row(1, "fail", obj, rest.strip() if sep else problem))
        return rows
    for i, (name, d, fname, desc) in enumerate(skills, start=1):
        if not desc:
            rows.append(_row(1, "fail", name, "SKILL.md 可解析，但 description 为空",
                             [f"文件：{d / 'SKILL.md'}"]))
        else:
            rows.append(_row(1, "ok", name, "SKILL.md 可解析，name/description 齐备",
                             [f"目录名 == frontmatter name == {fname}"]))
    return rows


# ------------------------------------------------------------ 2 脚本可编译

def _group2(repo: Path):
    rows = []
    pyc_dir = Path(tempfile.gettempdir()) / "am-doctor-pyc"
    try:
        pyc_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return [_row(2, "fail", str(pyc_dir), f"无法创建 py_compile 输出目录：{exc}")]
    scripts = sorted((repo / "skills").glob("*/scripts/*.py"))
    if not scripts:
        return [_row(2, "ok", "skills/*/scripts/*.py", "没有需要编译的脚本")]
    for i, py in enumerate(scripts, start=1):
        cfile = str(pyc_dir / (py.name + "c"))
        try:
            # cfile 一律指向 <TMP>：裸 python3 -m py_compile 会在源目录旁生成 __pycache__
            py_compile.compile(str(py), cfile=cfile, doraise=True)
            rows.append(_row(2, "ok", py.name, f"py_compile 通过（cfile={cfile}）"))
        except Exception as exc:
            rows.append(_row(2, "fail", py.name, f"{type(exc).__name__}: {exc}",
                             [f"文件：{py}"]))
    return rows


# ------------------------------------------------------------ 3 同包引用齐全

def _group3(repo: Path, names, expect):
    rows = []
    known = set(names)
    missing = []
    total = 0
    files = _skill_text_files(repo)
    for path in files:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        for lineno, line in enumerate(lines, start=1):
            for rx in (_DOLLAR_REF_RE, _PATH_REF_RE):
                for m in rx.finditer(line):
                    total += 1
                    ref = m.group(1)
                    if ref not in known:
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
                                  f"本仓库现有：{', '.join(sorted(known)) or '(空)'}"]))
                continue
            try:
                rel = path.relative_to(repo)
            except ValueError:
                rel = path
            rows.append(_row(3, "fail", f"{rel} → {ref}",
                             "被引用但仓库内不存在（哪一层没装：仓库 skills/）",
                             [f"引用方：{rel}:{lineno}", f"期望存在：{repo / 'skills' / ref}"]))
        return rows
    rows.append(_row(3, "ok", None, f"同包引用 {total} 处全部可解析",
                     [f"扫描范围：{len(files)} 个文件（{' + '.join('skills/' + g for g in _SKILL_TEXT_GLOBS)}）",
                      "判据形态：$<slug> 与 <slug>/{references,scripts,agents,SKILL.md}"]))
    return rows


# ------------------------------------------------------------ 4/5 全局挂载

def _group4(home: Path, repo: Path, names, no_global: bool):
    root = home / "skills"
    if no_global:
        return [_row(4, "ok", str(root), "N/A（--no-global：跳过第 4~5 组）")]
    if not root.exists():
        return [_row(4, "warn", str(root),
                     f"{root} 不存在：尚未安装，运行 scripts/install.py")]
    rows = []
    for i, name in enumerate(names, start=1):
        link = root / name
        target = repo / "skills" / name
        if not link.exists() and not link.is_symlink():
            rows.append(_row(4, "fail", name, "未安装（路径不存在）",
                             [f"期望：{link} → {target}", "放行：scripts/install.py"]))
        elif not link.is_symlink():
            rows.append(_row(4, "fail", name,
                             '是实体目录而非软链（违反"两端只能是软链"不变量）',
                             [f"现状：{link}", f"期望：软链 → {target}"]))
        else:
            real = Path(os.path.realpath(link))
            if real == target.resolve():
                rows.append(_row(4, "ok", name, f"软链正确指向本仓库（{real}）"))
            else:
                rows.append(_row(4, "fail", name, "是软链但指向别处",
                                 [f"当前→{real}", f"期望→{target.resolve()}",
                                  "放行：scripts/install.py --adopt-symlink"]))
    return rows


def _group5(home: Path, no_global: bool):
    root = home / "skills"
    if no_global:
        return [_row(5, "ok", str(root / ".system"), "N/A（--no-global：跳过第 4~5 组）")]
    if not root.exists():
        return [_row(5, "warn", str(root / ".system"),
                     f"{root} 不存在：无从判断 .system 是否被误伤，跳过")]
    sysdir = root / ".system"
    if sysdir.is_dir() and not sysdir.is_symlink():
        return [_row(5, "ok", ".system", "仍是实体目录（未被触碰）",
                     ["它是 Codex 自带 skill 的实体真源，且本身被当作一个独立 skill 根。"])]
    return [_row(5, "fail", ".system",
                 "已被替换为软链或缺失：install.py 可能越界操作，请立即检查",
                 [f"现状：{'不存在' if not sysdir.exists() else ('软链 → ' + os.path.realpath(sysdir) if sysdir.is_symlink() else '非目录')}",
                  f"期望：{sysdir} 是实体目录"])]


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
                 "第 9 组的跨组件契约是仓库侧的，照跑）")]
    codex_dir = project / ".codex"
    if not codex_dir.is_dir():
        return [_row(6, "warn", str(codex_dir),
                     f"{codex_dir} 不存在：运行 scripts/bootstrap_project.py {project} --backend codex")]
    registry_path = codex_dir / "config.toml"
    if not registry_path.is_file():
        return [_row(6, "fail", str(registry_path), "config.toml 不存在",
                     [f"运行 scripts/bootstrap_project.py {project} --backend codex"])]
    try:
        registry = tomllib.loads(registry_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        return [_row(6, "fail", str(registry_path), f"config.toml 不可解析：{exc}")]
    agents = registry.get("agents") if isinstance(registry.get("agents"), dict) else {}
    item = 1
    for role in ROLES:
        reg = agents.get(role)
        if not isinstance(reg, dict):
            rows.append(_row(6, "fail", role, "缺少角色注册 agents.%s" % role)); item += 1
            continue
        config_file = str(reg.get("config_file") or "")
        if not config_file:
            rows.append(_row(6, "fail", role, "缺少 config_file")); item += 1
            continue
        config_path = (registry_path.parent / config_file).resolve()
        try:
            config_path.relative_to(registry_path.parent.resolve())
        except ValueError:
            rows.append(_row(6, "fail", role, f"config_file 越出 .codex（{config_path}）"))
            item += 1
            continue
        if not config_path.is_file():
            rows.append(_row(6, "fail", role, f"角色配置文件不存在（{config_path}）")); item += 1
            continue
        try:
            payload = tomllib.loads(config_path.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as exc:
            rows.append(_row(6, "fail", role, f"{config_path.name} 不可解析：{exc}")); item += 1
            continue
        bad = [k for k in REQUIRED_TOML_KEYS if not str(payload.get(k) or "").strip()]
        if bad:
            rows.append(_row(6, "fail", role,
                             f"{config_path.name} 缺少非空字段：{', '.join(bad)}")); item += 1
            continue
        got = str(payload["sandbox_mode"])
        if got != SANDBOX_EXPECT[role]:
            rows.append(_row(6, "fail", role,
                             f"sandbox_mode={got} 应为 {SANDBOX_EXPECT[role]}",
                             [f"文件：{config_path}"])); item += 1
            continue
        rows.append(_row(6, "ok", role,
                         f"注册与角色配置齐备（sandbox_mode={got}, approval_policy={payload['approval_policy']}, model={payload['model']}）",
                         [f"config_file={config_file}"]))
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
                              "放行：scripts/install.py --project-link <PROJECT>"]))
        elif not link.is_symlink():
            rows.append(_row(7, "fail", name, "项目内是实体目录（不变量要求只能是软链）",
                             [f"现状：{link}",
                              "该目录可能未被 Git 跟踪，替换前先提交或备份",
                              "放行：scripts/install.py --project-link <PROJECT> --replace-dir --backup-dir <DIR>"]))
        else:
            real = Path(os.path.realpath(link))
            if real == target:
                rows.append(_row(7, "ok", name, f"项目内软链同源（{real}）"))
            else:
                rows.append(_row(7, "fail", name, "项目内软链指向别处（两端必须同源）",
                                 [f"当前→{real}", f"期望→{target}"]))
        item += 1
    cursor_link = project / ".cursor" / "skills"
    if cursor_link.is_symlink():
        real = Path(os.path.realpath(cursor_link))
        want = (project / ".agents" / "skills").resolve()
        if real == want:
            rows.append(_row(7, "ok", ".cursor/skills",
                             f"→ ../.agents/skills（{os.readlink(cursor_link)}）"))
        else:
            rows.append(_row(7, "warn", ".cursor/skills",
                             f"是软链但不指向 ../.agents/skills（当前→{real}）"))
    elif cursor_link.exists():
        rows.append(_row(7, "warn", ".cursor/skills", "存在但不是软链"))
    else:
        rows.append(_row(7, "warn", ".cursor/skills",
                         "不存在（Cursor 侧看不到项目 skill；Codex 侧不受影响）"))
    return rows


# ------------------------------------------------------------ 8 栈目录就位

def _group8(project):
    if project is None:
        return []
    rows = []
    base = project / "workstacks"
    if not base.is_dir():
        return [_row(8, "warn", str(base), "workstacks/ 不存在",
                     ["运行 scripts/bootstrap_project.py <PROJECT>（不加 --skip-operations）"])]
    gi = base / ".gitignore"
    if not gi.is_file():
        rows.append(_row(8, "warn", str(gi), "workstacks/.gitignore 不存在",
                         ["栈本体应纳入 Git；history/ 与 _current.json 应排除。"]))
    else:
        text = gi.read_text(encoding="utf-8")
        absent = [r for r in ("*/history/", "_current.json") if r not in text]
        if absent:
            for i, rule in enumerate(absent, start=1):
                rows.append(_row(8, "warn", str(gi), f"workstacks/.gitignore 缺少 {rule} 规则",
                                 ["指针会脏 Git" if rule == "_current.json"
                                  else "迁移备份会让每次 diff 多出无信息量的内容"]))
        else:
            rows.append(_row(8, "ok", str(gi), "含 */history/ 与 _current.json 两条规则"))
    ptr = base / "_current.json"
    if ptr.exists():
        try:
            data = json.loads(ptr.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("顶层不是 JSON 对象")
            rows.append(_row(8, "ok", str(ptr), f"可解析为 JSON 对象（campaign={data.get('campaign')}）"))
        except (json.JSONDecodeError, ValueError, OSError) as exc:
            rows.append(_row(8, "warn", str(ptr), f"_current.json 不可解析：{exc}"))
    else:
        rows.append(_row(8, "ok", str(ptr), "无当前栈指针（克隆后的正常状态；恢复时按语义识别或用户指定）"))
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
                     _layout_config_detail())]
    except OSError as exc:
        return [_row(8, "fail", str(cfg), f"workstacks/config.json 读取失败（{exc}）",
                     _layout_config_detail())]
    if not isinstance(raw, dict):
        return [_row(8, "fail", str(cfg),
                     f"workstacks/config.json 根节点必须是 JSON object，实际是 {type(raw).__name__}",
                     _layout_config_detail())]
    unknown = sorted(set(raw) - set(_LAYOUT_KEYS))
    if unknown:
        return [_row(8, "fail", str(cfg),
                     f"workstacks/config.json 含未知键 {', '.join(unknown)}（只允许 {' / '.join(_LAYOUT_KEYS)}）",
                     _layout_config_detail())]
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
                     _layout_config_detail())]
    custom = {k: str(raw[k]) for k in _LAYOUT_KEYS
              if k in raw and str(raw[k]) != _LAYOUT_DEFAULTS[k]}
    if not custom:
        return [_row(8, "ok", str(cfg),
                     "workstacks/config.json 存在且全部取默认值（等价于没有该文件）")]
    return [_row(8, "warn", str(cfg),
                 "workstacks/config.json 声明了非默认布局："
                 + "、".join(f"{k}={v}" for k, v in sorted(custom.items())),
                 ["第 8/9 组按默认路径检查，结论不覆盖自定义位置（对齐留待 Phase 3）。",
                  "stack.py 自身按该配置解析，故栈命令不受影响；受影响的是 doctor 这两组的覆盖面。"])]


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
                     [f"期望位置：{stack_py}"])]
    try:
        src = stack_py.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return [_row(9, "fail", _STACK_SCRIPT_REL, f"读取 stack.py 失败：{exc}")]
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
                      "改任一侧都必须同步另一侧（本项就是那道同步门禁）。"])]
    return [_row(9, "ok", _STACK_SCRIPT_REL,
                 "跨组件契约成立：4 条池解析正则字面量、parse_work_plans / parse_issue_index / "
                 "load_layout 三个函数定义、以及布局键与默认值的 4 行字面量均在 stack.py 源码里",
                 ["锚点是**内容**而非行号：stack.py 内部重排、增删函数都不会让本项假报。"])]


def _group9(project, repo: Path):
    if project is None:
        # 长期池解析是项目侧的，跳过；跨组件契约是仓库侧的，照跑。
        return _group9_stack_contract(repo)
    plan = project / "docs" / "operations" / "next-work-plan.md"
    issue = project / "docs" / "operations" / "issues.md"
    rows = []
    for p in (plan, issue):
        if not p.exists():
            rows.append(_row(9, "warn", str(p), "不存在",
                             ["survey 的长期待办池少一个来源；运行 bootstrap_project.py（不加 --skip-operations）"]))
    plans = _parse_plans(plan)
    issues = _parse_issues(issue)
    if not plans and not issues:
        rows.append(_row(9, "warn", "docs/operations/",
                         "两个池文件均解析出 0 条：survey 会 exit 0（两池皆空是正常运行态，不是错误）；"
                         "两个池文件都不存在时它改打 bootstrap_project.py 指引",
                         [f"{plan}: 0 条", f"{issue}: 0 条",
                          "两种空池的输出**可区分**：文件都缺失 → bootstrap 指引；文件存在但 0 条 → 本行这种 warn。"]))
    else:
        ids = ", ".join(p["id"] for p in plans) or "无"
        rows.append(_row(9, "ok", "docs/operations/",
                         f"next-work-plan.md 解析出 {len(plans)} 条（{ids}）；issues.md {len(issues)} 条",
                         ["4 条正则与 stack.py 的 parse_work_plans / parse_issue_index 逐字相同"
                          "（由下一项机械校验，不靠行号）"]))
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
                      "    命中集合零交集 —— 放宽判据不会把它们变成永久黄噪音。"])]
    for path, found in hits:
        rel = path.relative_to(repo)
        rows.append(_row(10, "warn", str(rel),
                         f"{len(found)} 处仍写着 .agents/skills/<slug>/ 项目侧前缀"
                         "（布局相关：换成别的挂载布局就失效）",
                         [f"{rel}:{lineno} → {frag}" for lineno, frag in found] +
                         ["修法：自指写 <本 skill 目录>/scripts/…，跨 skill 写 <skill 根>/<slug>/scripts/…",
                          "    后缀 <slug>/scripts/… 在三种布局下都不变，故既布局无关又被第 3 组校验。"]))
    return rows


# ------------------------------------------------------------ 11 栈内容门禁

def _group11(project, repo: Path, enabled: bool):
    if not enabled:
        return []
    if project is None:
        return [_row(11, "warn", "--stack-verify", "未给 --project，无法定位栈，跳过")]
    ptr = project / "workstacks" / "_current.json"
    if not ptr.exists():
        return [_row(11, "warn", str(ptr), "无 _current.json 指针，--stack-verify 跳过",
                     ["指针不入库（workstacks/.gitignore 排除 _current.json），克隆出来的项目本来就没有它。"])]
    try:
        campaign = json.loads(ptr.read_text(encoding="utf-8")).get("campaign")
    except (json.JSONDecodeError, OSError) as exc:
        return [_row(11, "warn", str(ptr), f"指针不可解析：{exc}")]
    if not campaign:
        return [_row(11, "warn", str(ptr), "指针里没有 campaign 字段，跳过")]
    stack_py = repo / _STACK_SCRIPT_REL
    if not stack_py.is_file():
        return [_row(11, "fail", str(stack_py), "stack.py 不存在，无法运行 verify")]
    cmd = [sys.executable, str(stack_py), "verify",
           "--repo-root", str(project), "--campaign", str(campaign)]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    out = (proc.stdout or "") + (proc.stderr or "")
    tail = [l for l in out.splitlines() if l.strip()][-8:]
    if proc.returncode == 0:
        return [_row(11, "ok", f"stack.py verify --campaign {campaign}", "exit 0", tail)]
    if proc.returncode == 2:
        return [_row(11, "warn", f"stack.py verify --campaign {campaign}",
                     f"exit 2（栈缺失/环境问题，不判 error）", tail)]
    return [_row(11, "fail", f"stack.py verify --campaign {campaign}",
                 f"exit {proc.returncode}（原文附后）", tail)]


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="doctor.py",
        description="本仓库安装健康的唯一判据：只读自检 11 项（10 组 + 1 项 opt-in）。",
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
    rows += _group8(project)
    rows += _group9(project, repo)
    rows += _group10(repo)
    rows += _group11(project, repo, args.stack_verify)

    # id 只有一个来源：收齐全部 rows 后按组统一重编号（各组自己编号曾经产出重复 id，见 _row 的说明）。
    _renumber(rows)
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
