#!/usr/bin/env python3
"""给一个新项目铺好 agent-methodology 的项目侧前提：角色配置 + Codex 围栏注册 + 长期池文档 + workstacks/。

用法（完整参数以 --help 为准）：
    python3 <方法论仓库>/scripts/bootstrap_project.py <PROJECT>
    python3 <方法论仓库>/scripts/bootstrap_project.py <PROJECT> --backend codex
    python3 <方法论仓库>/scripts/bootstrap_project.py <PROJECT> --dry-run     # 打印渲染全文，零写盘

铺什么：
    --backend codex   → .codex/agents/{designer,executor,reviewer}.toml + .codex/config.toml 围栏注册
    --backend cursor  → .cursor/agents/{designer,executor,reviewer}.md
    --backend both    → 上述两组（默认）
    与 backend 无关、除 --skip-operations 外总是铺：
        workstacks/.gitignore、docs/operations/{next-work-plan,issues}.md
    （这三者是 campaign-work-stack skill 的**项目侧前提**，不属任何编排后端，故不受 --backend 门控。）

明确不做（越界即错）：
    不创建 workstacks/<campaign>/、不创建 active-work-stack.json、不运行 stack.py ensure
        （"创建栈只有一个门：ensure"，且 ensure 对新建栈强制要求非 legacy 的 --activation）；
    不创建 AGENTS.md；不 bootstrap module-investigator；不碰 <PROJECT>/.cursor/skills；
    两端 backend 互不作为来源（codex 不读 .cursor/，cursor 不读 .codex/）。

退出码：
    0 = 全部 created 或 skipped（含 --dry-run）
    1 = 需人工决策的冲突：config.toml 不可解析 / 围栏标记不完整 / agents.* 存在于围栏外
        / 渲染结果残留 {{ 或 }} / 模板文件缺失 / 写入后复检失败（以上失败一律**整体回滚**）
    2 = 用法/环境错误：PROJECT 缺失或非目录、--backend 非法、
        --force 未配 --backup-dir、写盘 OSError（同样整体回滚）

写盘是**事务性**的：任一文件写失败或围栏复检不过，本次运行已写的文件全部还原，
不留下半成品态（半成品比什么都没铺更糟 —— 幂等规则是「路径存在即 skipped、不比对内容」，
残留文件永远不会被复检，两次模板内容不同就会静默留下与用户意图不符的角色配置）。
"""

# <方法论仓库> = agent-methodology 仓库根目录（装着 skills/、scripts/、templates/ 的那一层）；用户可见定义见 README.md「占位符约定」。

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tomllib
from pathlib import Path

# 防止 import _common 时在本仓库 scripts/ 下生成 __pycache__（缓存会污染仓库清单并烙进本机绝对路径）。
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    emit,
    repo_root,
)

ROLES = ("designer", "executor", "reviewer")
SANDBOX_EXPECT = {"designer": "read-only", "executor": "workspace-write", "reviewer": "read-only"}
REQUIRED_TOML_KEYS = ("sandbox_mode", "approval_policy", "developer_instructions")

FENCE_OPEN = "# >>> agent-methodology:agents >>>"
FENCE_CLOSE = "# <<< agent-methodology:agents <<<"
FENCE_NOTES = (
    "# 本区块由 agent-methodology/scripts/bootstrap_project.py 管理。",
    "# 手工编辑会在下次 bootstrap --force 时被覆盖；要永久自定义请删除本区块并自行维护 [agents.*]。",
)

DEFAULT_REASONING_EFFORT = "medium"
DEFAULT_PROJECT_IDENTITY = "本项目"

RESIDUAL_RE = re.compile(r"\{\{[^}]*\}\}?")
JSON_KEYS = ("path", "state", "action", "detail")
OPERATIONS_FILES = (
    ("templates/workstacks/.gitignore", "workstacks/.gitignore"),
    ("templates/docs-operations/next-work-plan.md", "docs/operations/next-work-plan.md"),
    ("templates/docs-operations/issues.md", "docs/operations/issues.md"),
)


class BootstrapError(Exception):
    """携带退出码的失败。"""

    def __init__(self, code, message, details=()):
        self.code = code
        self.message = message
        self.details = [str(d) for d in details]
        super().__init__(message)


# ---------------------------------------------------------------- 渲染

def _render(text: str, mapping: dict) -> str:
    """纯字面量替换，不用模板引擎（避免引入依赖与转义歧义；TOML 值在模板里已带好引号）。"""
    for key, value in mapping.items():
        text = text.replace("{{%s}}" % key, value)
    return text


def _residual(text: str):
    """返回 [(行号, 残留片段)]；模板占位符没被全部替换时用来 fail-closed。"""
    out = []
    for i, line in enumerate(text.splitlines(), start=1):
        for m in RESIDUAL_RE.finditer(line):
            out.append((i, m.group(0), line.strip()))
    return out


def _read_template(templates_root: Path, rel: str) -> str:
    path = templates_root / rel
    if not path.is_file():
        raise BootstrapError(1, f"模板文件缺失：{path}",
                             ["模板是本仓库的一部分；缺失说明仓库被破坏或 promote 不完整。"])
    return path.read_text(encoding="utf-8")


# ------------------------------------------------- 渲染后的联动自检（写盘前，全或无）

def _check_codex_toml(rel: str, text: str, role: str):
    try:
        payload = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise BootstrapError(1, f"{rel}: 渲染结果不是合法 TOML", [str(exc)])
    for key in REQUIRED_TOML_KEYS:
        if not str(payload.get(key) or "").strip():
            raise BootstrapError(1, f"{rel}: 渲染结果缺少非空的 {key}",
                                 ["这三项在模板里是硬编码、不得参数化；本自检防止有人日后把它们"
                                  "改成占位符，从而让 bootstrap 出来的项目永远过不了后端门禁。"])
    if "model" in payload:
        raise BootstrapError(1, f"{rel}: 角色配置必须省略 model，以继承主窗口模型")
    got = str(payload["sandbox_mode"])
    want = SANDBOX_EXPECT[role]
    if got != want:
        raise BootstrapError(1, f"{rel}: sandbox_mode={got} 应为 {want}",
                             ["对齐 check_codex_backend.py 的硬校验：designer/reviewer=read-only，"
                              "executor=workspace-write。"])


def _check_cursor_md(rel: str, text: str, role: str):
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise BootstrapError(1, f"{rel}: 渲染结果缺少 frontmatter 起始 ---", [])
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        raise BootstrapError(1, f"{rel}: frontmatter 没有结束的 ---", [])
    fm = {}
    for line in lines[1:end]:
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*?)\s*$", line)
        if m:
            fm[m.group(1)] = m.group(2)
    required = ["name", "readonly"] + (["is_background"] if role == "executor" else [])
    missing = [k for k in required if k not in fm or not fm[k]]
    if missing:
        raise BootstrapError(1, f"{rel}: frontmatter 缺少 {', '.join(missing)}", [])
    if "model" in fm:
        raise BootstrapError(1, f"{rel}: frontmatter 必须省略 model，以继承主窗口模型")
    if fm["name"] != role:
        raise BootstrapError(1, f"{rel}: frontmatter name={fm['name']} 与文件名主干 {role} 不一致", [])


# ------------------------------------------------------------- 围栏算法

def _fence_block(fragment: str) -> str:
    return "\n".join([FENCE_OPEN, *FENCE_NOTES]) + "\n" + fragment.rstrip("\n") + "\n" + FENCE_CLOSE + "\n"


def _role_header_line(lines, role):
    pat = re.compile(r"^\s*\[agents\." + re.escape(role) + r"\]\s*$")
    return [i for i, line in enumerate(lines) if pat.match(line)]


def _plan_fence(config_path: Path, block: str, force: bool):
    """按 §3.6 的六步算法产出围栏写入计划。返回 dict。

    唯一的硬安全点：TOML 规范禁止重复声明同一张表，所以**任一 [agents.<role>] 落在围栏外就 exit 1，
    绝不追加**——追加会让整个文件解析失败，把用户原本可用的编排配置一起弄坏。
    """
    plan = {"kind": "fence", "path": config_path, "block": block,
            "original_bytes": None, "new_content": None,
            "state": None, "action": None, "detail": []}

    if not config_path.exists():
        plan.update(state="absent", action="created", new_content="\n" + block,
                    detail=["文件不存在 → 新建：一个空行 + 围栏块（结尾带换行）"])
        return plan

    original_bytes = config_path.read_bytes()
    plan["original_bytes"] = original_bytes
    original = original_bytes.decode("utf-8")

    try:
        registry = tomllib.loads(original)
    except tomllib.TOMLDecodeError as exc:
        raise BootstrapError(1, f"{config_path}: 文件不可解析，bootstrap 拒绝在损坏的 TOML 上追加",
                             [str(exc),
                              "追加会让 check_codex_backend.py 也一起崩；请先修好该文件再重跑。"])

    lines = original.splitlines()
    open_idx = [i for i, l in enumerate(lines) if l.strip() == FENCE_OPEN]
    close_idx = [i for i, l in enumerate(lines) if l.strip() == FENCE_CLOSE]

    # ---- 第 2.5 步：围栏完整性检查（必须在「围栏外 [agents.*]」检查**之前**）
    # 不变量：重写区间严格等于唯一的一对 OPEN/CLOSE 之间（含标记行）；
    #         任一边界缺失、重复或顺序颠倒即中止，绝不追加。
    # 为什么不能把「标记不成对」当成「没有围栏」：那会走 EOF 追加，造出第 2 个 OPEN；
    # 下一次 --force 的重写区间就跨越了用户内容，把用户自有键静默吞掉（实测 exit=0 的数据丢失）。
    # 为什么必须排在「围栏外 [agents.*]」之前：标记被删一半时，围栏内的 [agents.*] 会被判成
    # 「围栏外」，于是报出来的是症状而不是真因，用户按提示去挪表头，永远修不好。
    # 0 处 / 0 处**不是**损坏态，那是「全新文件、还没有围栏」的正常态，必须放行到第 5 步 EOF 追加
    # （第 5 步的前置条件 `not open_idx and not close_idx` 正是由本步保证的）。
    # 损坏态 = 只出现了一部分、出现了多次、或顺序颠倒 —— 这些情况下「围栏在哪」无法唯一确定，
    # 而重写区间必须唯一确定，否则 --force 会跨越用户内容。
    if (open_idx or close_idx) and not (
            len(open_idx) == 1 and len(close_idx) == 1 and open_idx[0] < close_idx[0]):
        raise BootstrapError(
            1, f"{config_path}: 围栏标记不完整（OPEN {len(open_idx)} 处 / CLOSE {len(close_idx)} 处），拒绝写入",
            [f"OPEN 标记（{FENCE_OPEN}）所在行：{[i + 1 for i in open_idx] or '（无）'}",
             f"CLOSE 标记（{FENCE_CLOSE}）所在行：{[i + 1 for i in close_idx] or '（无）'}",
             "不变量：重写区间严格等于唯一的一对 OPEN/CLOSE 之间；标记不成对/不唯一/顺序颠倒即中止，绝不追加。",
             "为什么绝不追加：追加会造出第 2 个 OPEN，于是下一次 --force 的重写区间跨越围栏外的用户内容，"
             "把用户自有的键静默吞掉（TOML 还会因表重复声明而整体解析失败）。",
             "修复：删掉多余标记行或补回缺失标记行，使两个标记恰好各出现一次且 OPEN 在前，然后重跑。",
             "本次未写任何文件。"])
    fenced = bool(open_idx)
    lo, hi = (open_idx[0], close_idx[0]) if fenced else (None, None)

    agents = registry.get("agents") if isinstance(registry.get("agents"), dict) else {}
    outside = []
    for role in ROLES:
        header_lines = _role_header_line(lines, role)
        exists_in_toml = isinstance(agents.get(role), dict)
        if not header_lines:
            if exists_in_toml:
                # 用 dotted-key 等写法声明的表，无法定位表头行 → 一律视为围栏外
                outside.append((role, None))
            continue
        for ln in header_lines:
            if not fenced or not (lo < ln < hi):
                outside.append((role, ln + 1))
    if outside:
        detail = [f"agents.{role}" + (f"（第 {ln} 行）" if ln else "（无法定位表头行）")
                  for role, ln in outside]
        detail += [f"我们的围栏：{'第 %d–%d 行' % (lo + 1, hi + 1) if fenced else '不存在'}",
                   "请手工把这些段移进围栏，或删除后重跑 --force。",
                   "绝不追加：TOML 禁止重复声明同一张表，追加会让整个文件解析失败，",
                   "把 check_codex_backend.py 的 tomllib.load 一起弄坏。"]
        raise BootstrapError(1, f"{config_path}: [agents.*] 存在于围栏外，拒绝追加", detail)

    if fenced:
        existing = "\n".join(lines[lo:hi + 1]) + "\n"
        if existing == block:
            plan.update(state="fenced-identical", action="skipped(identical)",
                        new_content=None,
                        detail=[f"围栏内内容与本次渲染逐字相同（第 {lo + 1}–{hi + 1} 行）"])
            return plan
        if not force:
            plan.update(state="fenced-differs", action="skipped(differs)", new_content=None,
                        detail=[f"围栏内内容与本次渲染不同（第 {lo + 1}–{hi + 1} 行）",
                                "无 --force 时不写；确认后重跑并加 --force --backup-dir <DIR>。"])
            return plan
        new_lines = lines[:lo] + block.rstrip("\n").splitlines() + lines[hi + 1:]
        new_content = "\n".join(new_lines)
        if original.endswith("\n"):
            new_content += "\n"
        plan.update(state="fenced-differs", action="replaced", new_content=new_content,
                    detail=["--force：只替换两个标记行之间的内容（含标记行本身整体重写），",
                            "围栏外一个字节不动（其他工具的托管块与行尾标记不受影响）。"])
        return plan

    # 围栏不存在 → EOF 追加。前置条件由第 2.5 步保证：两个标记都为 0 处才可能走到这里。
    # 用显式检查而不是 `assert`：`python3 -O` 会把 assert 优化掉，而这正是最不该失效的一道闸。
    if open_idx or close_idx:
        raise BootstrapError(1, f"{config_path}: 内部错误：EOF 追加分支看到了围栏标记"
                                f"（OPEN {len(open_idx)} 处 / CLOSE {len(close_idx)} 处）",
                             ["第 2.5 步应当已经拦下这种输入；出现本行说明围栏完整性检查被改坏了。",
                              "本次未写任何文件。"])
    prefix = original if original.endswith("\n") else original + "\n"
    plan.update(state="unfenced", action="created", new_content=prefix + "\n" + block,
                detail=["围栏不存在 → EOF 追加。",
                        "为什么必须是 EOF：TOML 里 [table] 表头会重置后续键的归属上下文，",
                        "在文件中部插入会把用户的裸键吞进 [agents.reviewer]；追加到 EOF 之后",
                        "没有任何后续内容，故在任何合法 TOML 之后追加完整表头都是安全的。"])
    return plan


def _rollback(written):
    """把本次运行已写入的文件逐个还原，返回 (还原条数, 未能还原的路径列表)。

    还原方式按写入方式一一对应：`--force` 覆盖过的 → 从备份 `shutil.move` 回原位；
    围栏文件 → 用写前保存的 `original_bytes` 覆盖；本次新建的 → `unlink`。
    逆序执行：后写的先还原，避免「还原 A 时踩到还没还原的 B」。
    """
    undone = 0
    residual = []
    for entry in reversed(written):
        path = entry["path"]
        try:
            if entry["backup"] is not None:
                shutil.move(str(entry["backup"]), str(path))
            elif entry["original_bytes"] is not None:
                path.write_bytes(entry["original_bytes"])
            elif not entry["existed"]:
                path.unlink()
            else:
                # 写前已存在、又既无备份也无原始 bytes → 无法还原，如实报出来而不是假装回滚了。
                residual.append(path)
                continue
            undone += 1
        except OSError:
            residual.append(path)
    return undone, residual


def _rollback_report(written, headline, extra_details=()):
    """执行整体回滚并产出 BootstrapError 的 (message, details)。

    FAIL 文案必须说清「回滚了几个、磁盘是否回到运行前」；回滚自身失败时逐个列出残留路径 ——
    静默的回滚失败比不回滚更坏，因为它会让用户以为磁盘是干净的。
    """
    undone, residual = _rollback(written)
    details = list(extra_details)
    if not residual:
        details.append(f"已回滚 {undone} 个文件、磁盘状态与本次运行前一致。")
    else:
        details.append(f"已回滚 {undone} 个文件；**以下 {len(residual)} 个文件未回滚**：")
        details += [f"  {p}" for p in residual]
        details.append("请手工核对这些路径（--backup-dir 里可能有它们的原件）。")
    details.append("为什么整体回滚而不保留半成品：幂等规则是「路径存在即 skipped(exists)、不比对内容」，"
                   "残留文件永远不会被复检，于是两次模板内容不同就会静默留下与用户意图不符的角色配置。")
    return headline, details


def _recheck_fence(config_path: Path):
    """写入后复检：可解析 + 三个 config_file 存在且不越出 .codex
    （对齐 check_codex_backend.py 的 `load_role_configs` 越界校验）。"""
    registry_path = config_path
    payload = tomllib.loads(registry_path.read_text(encoding="utf-8"))
    agents = payload.get("agents")
    if not isinstance(agents, dict):
        raise ValueError("缺少 agents 表")
    for role in ROLES:
        reg = agents.get(role)
        if not isinstance(reg, dict):
            raise ValueError(f"缺少角色注册：agents.{role}")
        config_file = str(reg.get("config_file") or "")
        if not config_file:
            raise ValueError(f"agents.{role} 缺少 config_file")
        target = (registry_path.parent / config_file).resolve()
        target.relative_to(registry_path.parent.resolve())


# ------------------------------------------------------------------ 主流程

def main() -> int:
    parser = argparse.ArgumentParser(
        prog="bootstrap_project.py",
        description="给新项目铺 agent-methodology 的项目侧前提（角色配置 + 围栏注册 + 长期池 + workstacks/）。",
        epilog="退出码：0=全部 created/skipped；1=需人工决策的冲突；2=用法/环境错误。\n"
               "幂等：plain 文件路径存在即跳过（不比对内容、不覆盖，避免静默回滚用户编辑）；\n"
               "围栏内内容逐字相同才算 identical。差异可见性由 --dry-run（打印渲染全文）与 --force 提供。\n"
               "仓库根与模板根由 Path(__file__).resolve() 推导，不写死仓库路径。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("project", metavar="PROJECT", help="目标项目目录（必须已存在）")
    parser.add_argument("--backend", choices=("codex", "cursor", "both"), default="both")
    parser.add_argument("--project-name", metavar="NAME",
                        help='→ {{PROJECT_IDENTITY}} = "<NAME> 项目"；缺省 = "本项目"')
    parser.add_argument("--model", metavar="M", help="兼容旧调用；已弃用，不写入角色模型")
    parser.add_argument("--reasoning-effort", metavar="E", default=DEFAULT_REASONING_EFFORT,
                        help=f"→ {{{{CODEX_REASONING_EFFORT}}}}；缺省 {DEFAULT_REASONING_EFFORT}")
    parser.add_argument("--cursor-model", metavar="M", default=None,
                        help="兼容旧调用；已弃用，不写入角色模型")
    parser.add_argument("--cursor-executor-model", metavar="M", default=None,
                        help="兼容旧调用；已弃用，不写入角色模型")
    parser.add_argument("--codex-bin", metavar="PATH", default="codex", help="兼容旧调用；不再探测 CLI 模型")
    parser.add_argument("--dry-run", action="store_true",
                        help="走完渲染/冲突检测/三态判定并打印渲染全文，但零写盘（连目录都不建）")
    parser.add_argument("--force", action="store_true",
                        help="覆盖 plain 文件（先移入 --backup-dir）；围栏只重写两个标记行之间的区间")
    parser.add_argument("--backup-dir", metavar="DIR",
                        help="--force 覆盖前的备份目录（必须显式给出；约定 <TMP>/agent-methodology-backup/<ts>/，"
                             "不在项目里留 .bak）")
    parser.add_argument("--skip-operations", action="store_true",
                        help="不铺 workstacks/.gitignore 与 docs/operations/*")
    parser.add_argument("--json", action="store_true", help="只输出 JSON，不混排人读前缀")
    args = parser.parse_args()

    try:
        return _run(args)
    except BootstrapError as exc:
        emit([{"object": "bootstrap", "path": None, "level": "fail", "state": "error",
               "action": "error", "message": exc.message, "detail": exc.details}],
             args.json,
             envelope={"project": str(Path(args.project).expanduser()) if args.project else None,
                       "backend": args.backend, "dry_run": args.dry_run,
                       "rendered_values": {}, "warnings": []},
             rows_key="results", json_keys=JSON_KEYS,
             summary={"created": 0, "skipped": 0, "replaced": 0, "error": 1},
             summary_line=f"bootstrap: {exc.message} · exit={exc.code}", exit_code=exc.code)
        return exc.code


def _run(args) -> int:
    project = Path(args.project).expanduser()
    if not project.is_dir():
        raise BootstrapError(2, f"PROJECT 不存在或不是目录：{project}",
                            ["bootstrap 不会替你创建项目目录；先确认路径。"])
    if args.force and not args.backup_dir:
        raise BootstrapError(2, "--force 必须同时给 --backup-dir",
                            ["破坏性覆盖必须有备份；备份不落项目内（不留 .bak）。"])
    repo = repo_root()
    # 模板路径一律写成 `templates/…` 的**仓库相对路径**（与目录树的写法一致），
    # 所以这里的根是仓库根而不是 templates/ —— 否则会把 "templates/" 拼两遍。
    templates_root = repo
    want_codex = args.backend in ("codex", "both")
    want_cursor = args.backend in ("cursor", "both")

    # 模型由父会话继承，不把安装时 CLI 默认值固化进角色配置。
    identity = f"{args.project_name} 项目" if args.project_name else DEFAULT_PROJECT_IDENTITY
    mapping = {
        "PROJECT_IDENTITY": identity,
        "CODEX_REASONING_EFFORT": args.reasoning_effort,
    }
    rendered_values = {
        "{{PROJECT_IDENTITY}}": identity,
        "{{CODEX_REASONING_EFFORT}}": args.reasoning_effort,
        "model_policy": "inherit_parent",
    }

    # ---- 渲染（全或无：先渲染 + 自检全部通过，才允许写任何文件）
    rendered = []  # (rel_dst, content, kind)
    if want_codex:
        for role in ROLES:
            rel = f"templates/codex-agents/{role}.toml"
            text = _render(_read_template(templates_root, rel), mapping)
            left = _residual(text)
            if left:
                raise BootstrapError(1, f"{rel}: 渲染结果残留占位符，一个文件都不写",
                                     [f"第 {ln} 行：{frag}　→　{line}" for ln, frag, line in left])
            _check_codex_toml(f".codex/agents/{role}.toml", text, role)
            rendered.append((f".codex/agents/{role}.toml", text, "plain"))
    if want_cursor:
        for role in ROLES:
            rel = f"templates/cursor-agents/{role}.md"
            text = _render(_read_template(templates_root, rel), mapping)
            left = _residual(text)
            if left:
                raise BootstrapError(1, f"{rel}: 渲染结果残留占位符，一个文件都不写",
                                     [f"第 {ln} 行：{frag}　→　{line}" for ln, frag, line in left])
            _check_cursor_md(f".cursor/agents/{role}.md", text, role)
            rendered.append((f".cursor/agents/{role}.md", text, "plain"))
    if not args.skip_operations:
        for rel_src, rel_dst in OPERATIONS_FILES:
            text = _render(_read_template(templates_root, rel_src), mapping)
            left = _residual(text)
            if left:
                raise BootstrapError(1, f"{rel_src}: 渲染结果残留占位符，一个文件都不写",
                                     [f"第 {ln} 行：{frag}　→　{line}" for ln, frag, line in left])
            rendered.append((rel_dst, text, "plain"))

    fence_plan = None
    if want_codex:
        fragment = _render(_read_template(templates_root, "templates/codex-config.fragment.toml"), mapping)
        left = _residual(fragment)
        if left:
            raise BootstrapError(1, "templates/codex-config.fragment.toml: 渲染结果残留占位符",
                                 [f"第 {ln} 行：{frag}　→　{line}" for ln, frag, line in left])
        fence_plan = _plan_fence(project / ".codex" / "config.toml", _fence_block(fragment), args.force)

    # ---- 三态判定
    rows = []
    for rel_dst, content, _kind in rendered:
        path = project / rel_dst
        if path.exists():
            if args.force:
                rows.append({"object": rel_dst, "path": rel_dst, "level": "ok",
                             "state": "exists", "action": "replaced", "message": "--force 覆盖",
                             "detail": [f"备份到：{Path(args.backup_dir).expanduser() / rel_dst}",
                                        "覆盖前先整体移入备份目录，不在项目里留 .bak"],
                             "_write": content, "_force_backup": True})
            else:
                rows.append({"object": rel_dst, "path": rel_dst, "level": "ok",
                             "state": "exists", "action": "skipped(exists)",
                             "message": "路径已存在，跳过（不比对内容、不覆盖）",
                             "detail": ["按内容覆盖会静默回滚用户编辑；要看差异用 --dry-run，要覆盖用 --force。"],
                             "_write": None})
        else:
            rows.append({"object": rel_dst, "path": rel_dst, "level": "ok",
                         "state": "absent", "action": "created", "message": "新建",
                         "detail": [], "_write": content})
    if fence_plan:
        rows.append({"object": ".codex/config.toml", "path": ".codex/config.toml",
                     "level": "ok", "state": fence_plan["state"], "action": fence_plan["action"],
                     "message": f"围栏注册：{fence_plan['action']}",
                     "detail": fence_plan["detail"], "_fence": fence_plan})

    # 兼容旧参数，但明确报告其不再生效，避免静默忽略用户意图。
    warnings = []
    if any(value is not None for value in
           (args.model, args.cursor_model, args.cursor_executor_model)):
        warnings.append("模型覆盖参数已弃用并忽略；三个角色统一继承主窗口模型。")

    # ---- 人读输出：逐条打印实际替换值 + warnings（与上面的 JSON 列表同源，不各说一套）
    if not args.json:
        print(f"项目：{project}")
        print(f"backend：{args.backend}　dry-run：{args.dry_run}　force：{args.force}")
        print("渲染替换值（逐条）：")
        for key, value in rendered_values.items():
            print(f"  {key} = {value}")
        for warning in warnings:
            print(f"[WARN] {warning}")
        print()

    if args.dry_run and not args.json:
        for rel_dst, content, _kind in rendered:
            print(f"===== [DRY-RUN] 将写入 {rel_dst} 的渲染全文 =====")
            print(content.rstrip("\n"))
            print(f"===== [DRY-RUN] {rel_dst} 全文结束 =====\n")
        if fence_plan and fence_plan["new_content"]:
            print("===== [DRY-RUN] 围栏块全文 =====")
            print(fence_plan["block"].rstrip("\n"))
            print("===== [DRY-RUN] 围栏块结束 =====\n")

    # ---- 写盘
    if not args.dry_run:
        backup_root = Path(args.backup_dir).expanduser() if args.backup_dir else None
        dirs = set()
        for row in rows:
            if row.get("_write") is not None or row.get("_fence"):
                dirs.add((project / row["path"]).parent)
        for d in sorted(dirs, key=lambda p: len(p.parts)):
            d.mkdir(parents=True, exist_ok=True)  # 目录不计入报告条目

        # 事务日志：每写一个文件就记「路径 + 写前是否存在 + 备份位置 / 原始 bytes」，
        # 于是任一后续步骤失败时能精确还原（见 _rollback）。
        written = []
        try:
            for row in rows:
                path = project / row["path"]
                content = row.get("_write")
                if content is not None:
                    existed = path.exists()  # 必须在 shutil.move 之前取
                    backup = None
                    if row.get("_force_backup") and backup_root:
                        backup = backup_root / row["path"]
                        backup.parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(path), str(backup))
                    path.write_text(content, encoding="utf-8")
                    written.append({"path": path, "existed": existed,
                                    "backup": backup, "original_bytes": None})
                fence = row.get("_fence")
                if fence and fence["new_content"] is not None:
                    fence["path"].write_text(fence["new_content"], encoding="utf-8")
                    written.append({"path": fence["path"],
                                    "existed": fence["original_bytes"] is not None,
                                    "backup": None,
                                    "original_bytes": fence["original_bytes"]})
                    try:
                        _recheck_fence(fence["path"])
                    except Exception as exc:  # 复检失败 → **整体**回滚 → exit 1
                        msg, detail = _rollback_report(
                            written, f"{fence['path']}: 写入后复检失败", [str(exc)])
                        raise BootstrapError(1, msg, detail)
        except (OSError, shutil.Error) as exc:
            # 退出码 2，与 install.py:_apply 的「写入失败」口径对齐。
            msg, detail = _rollback_report(written, f"写盘失败：{exc}", [f"项目：{project}"])
            raise BootstrapError(2, msg, detail)

    summary = {"created": 0, "skipped": 0, "replaced": 0}
    for row in rows:
        act = row["action"]
        if act.startswith("created"):
            summary["created"] += 1
        elif act.startswith("replaced"):
            summary["replaced"] += 1
        else:
            summary["skipped"] += 1
    code = 0
    summary_line = (f"bootstrap: {len(rows)} 个条目 · created={summary['created']} "
                    f"skipped={summary['skipped']} replaced={summary['replaced']} · exit={code}")
    for row in rows:
        row.pop("_write", None)
        row.pop("_fence", None)
        row.pop("_force_backup", None)
    emit(rows, args.json,
         envelope={"project": str(project), "backend": args.backend, "dry_run": args.dry_run,
                   "rendered_values": rendered_values, "warnings": warnings},
         rows_key="results", json_keys=JSON_KEYS, summary=summary,
         summary_line=summary_line, exit_code=code)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
