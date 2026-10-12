#!/usr/bin/env python3
"""agent-methodology 三个仓库级脚本共用的真源解析与输出工具。

本模块是 install.py / bootstrap_project.py / doctor.py 的**唯一**共享实现：仓库根推导、
CODEX_HOME 口径、skills/ 清单扫描、frontmatter 解析、统一输出前缀、原子软链。
**禁止在各脚本内复制一份** —— 第二份实现就是第二真源：日后改口径必然只改到一处，
剩下那处会静默漂移，而这类漂移恰好发生在"安装是否健康"的判据上，最难被发现。

只用标准库（与 skills/campaign-work-stack/scripts/stack.py 口径一致，不引入 PyYAML）。
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

SKILLS_DIR_NAME = "skills"

_FRONTMATTER_DELIM = "---"
# 只在第一个 ---…--- 块内匹配；不依赖 PyYAML
_NAME_RE = re.compile(r'^name:\s*"?([^"\n]+?)"?\s*$')
_DESC_RE = re.compile(r"^description:\s*(.*?)\s*$")
_BLOCK_SCALARS = {"", ">", ">-", ">+", "|", "|-", "|+"}

LEVEL_PREFIX = {"ok": "[OK]", "warn": "[WARN]", "fail": "[FAIL]"}
_DETAIL_INDENT = " " * 7


class SkillManifestError(Exception):
    """skills/ 清单不可信：目录缺失、为空、SKILL.md 缺 name、或目录名 != frontmatter name。

    `problems` 是**全部**不一致项的汇总。调用方应一次性打印后 exit 2（fail-closed）：
    清单是安装与自检的真源，真源有歧义时继续跑只会得到看起来正常的错误结果。
    """

    def __init__(self, problems):
        self.problems = [str(p) for p in problems]
        super().__init__("；".join(self.problems))


def repo_root() -> Path:
    """本仓库根 = 本文件的上上级目录（scripts/ 的父目录），与 cwd 无关。

    不写死仓库路径：本仓库最终落点尚未确认（G2），写死后改名要回改多处。
    """
    return Path(__file__).resolve().parents[1]


def codex_home(cli_override=None) -> Path:
    """CODEX_HOME 口径：`--codex-home` > `$CODEX_HOME` > `~/.codex`。

    这个覆盖开关是可测性的关键：端到端验证一律在 /tmp 的假 home 上做，永不触碰真实 ~/.codex/skills。
    """
    if cli_override:
        return Path(cli_override).expanduser()
    env = os.environ.get("CODEX_HOME")
    if env:
        return Path(env).expanduser()
    return Path(os.path.expanduser("~/.codex"))


def _frontmatter_lines(path: Path):
    """返回第一个 `---`…`---` 块内的行；无合法围栏或不可读时返回 None。"""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    lines = text.splitlines()
    if not lines or lines[0].strip() != _FRONTMATTER_DELIM:
        return None
    for i in range(1, len(lines)):
        if lines[i].strip() == _FRONTMATTER_DELIM:
            return lines[1:i]
    return None


def parse_frontmatter_name(path: Path):
    """取 SKILL.md frontmatter 的 `name`；取不到返回 None。"""
    lines = _frontmatter_lines(path)
    if lines is None:
        return None
    for line in lines:
        m = _NAME_RE.match(line)
        if m:
            return m.group(1).strip() or None
    return None


def parse_frontmatter_description(path: Path) -> str:
    """取 SKILL.md frontmatter 的 `description`；支持单行值与 YAML 块标量（`>-` / `|`）。

    只服务"非空"判据，不做完整 YAML 解析（那需要 PyYAML，本仓库脚本只用标准库）。
    """
    lines = _frontmatter_lines(path)
    if lines is None:
        return ""
    for idx, line in enumerate(lines):
        m = _DESC_RE.match(line)
        if not m:
            continue
        inline = m.group(1).strip()
        if inline not in _BLOCK_SCALARS:
            return inline.strip('"').strip("'").strip()
        buf = []
        for nxt in lines[idx + 1:]:
            if not nxt.strip():
                buf.append("")
                continue
            if nxt[:1] in (" ", "\t"):
                buf.append(nxt.strip())
            else:
                break
        return " ".join(p for p in buf if p).strip()
    return ""


def iter_skills(root: Path):
    """扫 `<root>/skills/*/SKILL.md`，返回按 name 排序的 `[(name, dir, frontmatter_name, description)]`。

    不硬编码 skill 名：清单来自磁盘，Phase 3 改 description、未来增减 skill 都不需要同步改脚本。
    fail-closed：所有不一致项**汇总**进一次 SkillManifestError，不逐个报错退出。
    """
    skills_dir = Path(root) / SKILLS_DIR_NAME
    if not skills_dir.is_dir():
        raise SkillManifestError(
            [f"{skills_dir} 不存在：本仓库没有 skills/ 目录，无法确定 skill 清单"]
        )
    entries = sorted((p for p in skills_dir.iterdir() if p.is_dir()), key=lambda p: p.name)
    if not entries:
        raise SkillManifestError([f"{skills_dir} 为空：本仓库没有任何 skill 目录"])

    out = []
    problems = []
    for d in entries:
        skill_md = d / "SKILL.md"
        if not skill_md.is_file():
            problems.append(f"{d.name}: 缺少 SKILL.md（{skill_md}）")
            continue
        fname = parse_frontmatter_name(skill_md)
        if not fname:
            problems.append(f"{d.name}: SKILL.md 的 frontmatter 里没有 name（{skill_md}）")
            continue
        if fname != d.name:
            problems.append(
                f"{d.name}: 目录名与 frontmatter name 不一致（dir={d.name} name={fname}）"
            )
            continue
        out.append((fname, d, fname, parse_frontmatter_description(skill_md)))
    if problems:
        raise SkillManifestError(problems)
    return out


def atomic_symlink(target: Path, link_path: Path) -> None:
    """建绝对路径软链：先建 `<link>.tmp-<pid>` 再 `os.replace`，避免中途失败留下断链。"""
    link_path = Path(link_path)
    tmp = link_path.with_name(f"{link_path.name}.tmp-{os.getpid()}")
    if tmp.is_symlink() or tmp.exists():
        tmp.unlink()
    os.symlink(str(Path(target)), tmp)
    try:
        os.replace(tmp, link_path)
    except BaseException:
        if tmp.is_symlink() or tmp.exists():
            tmp.unlink()
        raise


def count_levels(rows) -> dict:
    """统计 ok / warn / fail 三档条数。"""
    out = {"ok": 0, "warn": 0, "fail": 0}
    for r in rows:
        lvl = r.get("level", "ok")
        out[lvl if lvl in out else "ok"] += 1
    return out


def emit(rows, as_json=False, *, envelope=None, rows_key="results", json_keys=None,
         summary=None, summary_line=None, exit_code=0) -> None:
    """统一输出。

    人读模式：每行 `[OK]/[WARN]/[FAIL] [<id>] [<object>]: <message>`，detail 逐行缩进 7 空格。
    `--json` 模式：**只**输出一个 JSON 文档（不混排 `[OK]/[FAIL]` 行），保证 `json.load` 可解析。
    """
    rows = list(rows)
    if as_json:
        payload = dict(envelope or {})
        if json_keys:
            payload[rows_key] = [{k: r.get(k) for k in json_keys} for r in rows]
        else:
            payload[rows_key] = [dict(r) for r in rows]
        payload["summary"] = summary if summary is not None else count_levels(rows)
        payload["exit"] = exit_code
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    for r in rows:
        level = r.get("level", "ok")
        head = LEVEL_PREFIX.get(level, LEVEL_PREFIX["ok"])
        if r.get("id"):
            head = f"{head} {r['id']}"
        if r.get("object"):
            head = f"{head} {r['object']}"
        msg = r.get("message") or ""
        print(f"{head}: {msg}" if msg else head)
        detail = r.get("detail")
        if detail:
            lines = detail if isinstance(detail, (list, tuple)) else str(detail).splitlines()
            for ln in lines:
                print(f"{_DETAIL_INDENT}{ln}" if ln else "")
    if summary_line:
        print(summary_line)
