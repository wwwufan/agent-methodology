#!/usr/bin/env python3
"""把本仓库 skills/ 下的方法论 skill 以**绝对路径软链**挂载到 Codex 个人根或项目 .agents/skills/。

用法（完整参数以 --help 为准）：
    python3 <本仓库>/scripts/install.py                        # 安装到 <codex_home>/skills
    python3 <本仓库>/scripts/install.py --check                # 只检测漂移，零副作用
    python3 <本仓库>/scripts/install.py --project-link <PROJ>  # 目标根改为 <PROJ>/.agents/skills
    python3 <本仓库>/scripts/install.py --mode uninstall       # 只删指向本仓库的软链

退出码：
    0 = 全部成功或全部无需动作（含 --dry-run 下"本来就全对"）
    1 = 存在漂移，或存在需人工决策的冲突（哪怕只有 1 个 skill 冲突、其余 4 个成功）
    2 = 用法/环境错误：清单不一致、skills/ 缺失、目标根不可写、--replace-dir 未配 --backup-dir、
        --project-link 指向不存在的路径、--only 含清单外名字、--mode 非法值

安全边界（为什么**不得**遍历 <codex_home>/skills）：
    该目录下有 `.system/`——Codex 自带 skill 的**实体真源**，且它本身被当作一个独立 skill 根。
    因此本脚本只按 `_common.iter_skills(repo)` 返回的名字集合逐个操作，代码里不存在对
    <codex_home>/skills 的 iterdir()/glob()/os.listdir()，于是 `.system` 与用户自装的任何 skill
    在原理上不可达。uninstall 的删除判据是「is_symlink() 且 resolve() 落在本仓库内」。
    不写 .install-manifest.json：机器相关状态进仓库会脏 Git，且一旦与磁盘不符就成新的漂移源；
    旧 target 打印在安装日志里已足够追溯。
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

# 防止 import _common 时在本仓库 scripts/ 下生成 __pycache__（缓存目录会污染仓库清单，
# 且 .pyc 里会烙进本机绝对路径）。即使调用方忘了 PYTHONDONTWRITEBYTECODE=1 也生效。
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    SKILLS_DIR_NAME,
    SkillManifestError,
    atomic_symlink,
    codex_home,
    emit,
    iter_skills,
    repo_root,
)

MODES = ("install", "check", "uninstall")
# `scope` 让消费方能一眼分开「skill 条目」与「目标根条目」：后者的 name 是符号名
# `<target-root>`（不是路径），真实路径在 `path` 里 —— 否则 results 里会混进 name 以 `/`
# 开头的条目，任何按 name 当 skill 名处理的下游都会踩空。
JSON_KEYS = ("name", "scope", "path", "state", "action", "current", "expected", "detail")
SUMMARY_KEYS = ("created", "repointed", "replaced", "removed", "ok", "skipped",
                "conflict", "drift", "missing")


def _is_within(path, root) -> bool:
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
        return True
    except (ValueError, OSError, RuntimeError):
        return False


def _abs_target(link: Path, raw) -> str:
    """把 readlink 的结果规整成完整绝对路径（冲突时唯一的可追溯凭证）。"""
    if not raw:
        return "(读不到 target)"
    p = Path(raw)
    return str(p if p.is_absolute() else (Path(link).parent / p))


def _probe(link: Path, target: Path, repo: Path):
    """返回 (state, raw_target, points_into_repo)。

    state ∈ missing / ok / symlink-foreign / symlink-broken / real-dir / real-file。
    判定「指向本仓库」一律用 resolve() 比较，不用字符串比较（避开 ..、尾斜杠、软链嵌套差异）。
    """
    if link.is_symlink():
        try:
            raw = os.readlink(link)
        except OSError:
            raw = ""
        real = Path(os.path.realpath(link))
        try:
            if real == Path(target).resolve():
                return "ok", raw, True
        except OSError:
            pass
        into = _is_within(real, repo)
        if not link.exists():
            return "symlink-broken", raw, into
        return "symlink-foreign", raw, into
    if link.is_dir():
        return "real-dir", str(link), False
    if link.exists():
        return "real-file", str(link), False
    return "missing", None, False


def _row(name, level, state, action, message, detail=None, current=None, expected=None,
         scope="skill", path=None):
    """产出一行结果。`scope="skill"` 时 name 就是 skill 名；`scope="root"` 时 name 是符号名
    `<target-root>`、真实路径另置 `path`（C4）。人读输出的 object 一律取真实标识，故
    `object = path or name`，人读行与改造前逐字一致。
    """
    return {
        "object": path or name, "name": name, "scope": scope, "path": path,
        "level": level, "state": state, "action": action,
        "message": message, "detail": detail, "current": current, "expected": expected,
    }


def _summary_key(action: str) -> str:
    for key in SUMMARY_KEYS:
        if action == key or action.startswith(key + "("):
            return key
    return "skipped"


def _plan(name, target, link, mode, args, repo, backup_root):
    """按 §2.3 状态行为矩阵产出 (row, op)；op ∈ None/create/repoint/replace/remove。"""
    state, raw, into = _probe(link, target, repo)
    expected = str(target)
    old = _abs_target(link, raw)
    real_kind = "real dir" if state == "real-dir" else "real file"

    if mode == "install":
        if state == "missing":
            return _row(name, "ok", state, "created", f"建绝对软链 → {expected}",
                        None, None, expected), "create"
        if state == "ok":
            return _row(name, "ok", state, "skipped", "已是指向本仓库的软链，跳过",
                        None, str(link), expected), None
        if state in ("symlink-foreign", "symlink-broken"):
            if args.adopt_symlink:
                action = "repointed(was-broken)" if state == "symlink-broken" else "repointed"
                return _row(name, "ok", state, action, f"{action} → {expected}",
                            [f"旧 target：{old}",
                             f"期望 target：{expected}",
                             "已原子重指（临时链 + os.replace）"],
                            old, expected), "repoint"
            return _row(name, "fail", "conflict", "conflict", "目标已是指向别处的软链",
                        [f"旧 target：{old}",
                         f"期望 target：{expected}",
                         "放行：--adopt-symlink（原子重指；旧 target 已在上行留档）"],
                        old, expected), None
        if args.replace_dir and args.backup_dir:
            dest = Path(backup_root) / name
            return _row(name, "ok", state, f"replaced(backup={dest})",
                        f"整体移入备份目录后建软链 → {expected}",
                        [f"现状：{link} （{real_kind}，非软链）",
                         f"备份到：{dest}",
                         f"再建软链 → {expected}"],
                        str(link), expected), "replace"
        return _row(name, "fail", "conflict", "conflict",
                    f"目标已是实体{'目录' if state == 'real-dir' else '文件'}，拒绝覆盖",
                    [f"现状：{link} （{real_kind}，非软链）",
                     "风险：实体目录可能未被 Git 跟踪（本项目 explain-task-failure 即为未跟踪状态），",
                     '      直接替换会让唯一副本消失；"先立后破"要求全局软链就位并通过 doctor 后才动项目侧。',
                     "放行：--replace-dir --backup-dir <DIR>（原目录会整体移入备份目录，不删除）",
                     "本次未做任何写入。"],
                    str(link), expected), None

    if mode == "check":
        if state == "missing":
            return _row(name, "fail", "missing", "missing", f"未安装（{link} 不存在）",
                        [f"期望 target：{expected}"], None, expected), None
        if state == "ok":
            return _row(name, "ok", "ok", "ok", "软链正确指向本仓库",
                        None, str(link), expected), None
        if state in ("symlink-foreign", "symlink-broken"):
            kind = "symlink" if state == "symlink-foreign" else "broken"
            return _row(name, "fail", "drift", "drift", f"drift({kind}→{old})",
                        [f"旧 target：{old}", f"期望 target：{expected}"], old, expected), None
        return _row(name, "fail", "drift", "drift", f"drift({real_kind})",
                    [f"现状：{link} （{real_kind}，非软链）",
                     f"期望 target：{expected}"], str(link), expected), None

    # uninstall：删除判据 = is_symlink() 且 resolve() 落在本仓库内
    if state == "missing":
        return _row(name, "ok", "absent", "skipped", "本就未安装，无需动作",
                    None, None, expected), None
    if state == "ok" or (state == "symlink-broken" and into):
        note = "（断链，但旧 target 曾指向本仓库）" if state == "symlink-broken" else ""
        return _row(name, "ok", state, "removed", f"删除指向本仓库的软链{note}",
                    None, str(link), expected), "remove"
    if state in ("symlink-foreign", "symlink-broken"):
        return _row(name, "ok", state, "skipped", f"foreign, skipped：软链指向别处，不动（{old}）",
                    None, old, expected), None
    return _row(name, "warn", state, "skipped",
                f"real, skipped：目标是{real_kind}，不动",
                ["卸载只删「is_symlink() 且 resolve() 落在本仓库内」的条目；",
                 "实体副本需要人工决策（先提交或备份，再用 --replace-dir 改软链）。"],
                str(link), expected), None


def _apply(op, link, target, name, backup_root, dry_run):
    if dry_run or not op:
        return
    if op in ("create", "repoint"):
        link.parent.mkdir(parents=True, exist_ok=True)
        atomic_symlink(target, link)
    elif op == "replace":
        Path(backup_root).mkdir(parents=True, exist_ok=True)
        shutil.move(str(link), str(Path(backup_root) / name))
        atomic_symlink(target, link)
    elif op == "remove":
        link.unlink()


def _fail(args, code, message, details=()):
    if getattr(args, "json", False):
        print(json.dumps({
            "mode": getattr(args, "mode", None) or "install",
            "target_root": None, "codex_home": None,
            "dry_run": bool(getattr(args, "dry_run", False)),
            "results": [], "summary": {}, "exit": code,
            "error": message, "detail": list(details),
        }, ensure_ascii=False, indent=2))
    else:
        print(f"[FAIL] {message}")
        for d in details:
            print(f"       {d}")
    return code


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="install.py",
        description="把本仓库 skills/ 下的方法论 skill 以绝对路径软链挂载到 Codex 个人根或项目 .agents/skills/。",
        epilog="退出码：0=全部成功或无需动作；1=存在漂移或需人工决策的冲突；2=用法/环境错误。\n"
               "仓库根由 Path(__file__).resolve().parents[1] 推导，与 cwd 无关；软链一律绝对路径。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--mode", choices=MODES, default="install",
                        help="install（默认）/ check / uninstall")
    parser.add_argument("--check", action="store_true",
                        help="--mode check 的别名，且强制零副作用（连目标根都不创建）")
    parser.add_argument("--codex-home", metavar="DIR",
                        help="Codex home；口径 --codex-home > $CODEX_HOME > ~/.codex")
    parser.add_argument("--project-link", metavar="PROJECT",
                        help="目标根改为 <PROJECT>/.agents/skills/（项目侧改软链用）")
    parser.add_argument("--dry-run", action="store_true",
                        help='只报告不写；退出码反映"将会发生什么"（复用同一套判定）')
    parser.add_argument("--adopt-symlink", action="store_true",
                        help="允许把指向别处的软链重指到本仓库（只授权动软链，绝不授权动实体）")
    parser.add_argument("--replace-dir", action="store_true",
                        help="允许用软链替换实体目录/文件；必须同时给 --backup-dir")
    parser.add_argument("--backup-dir", metavar="DIR",
                        help="被替换的实体目录整体移入此处（不删除）。约定默认落 "
                             "<TMP>/agent-methodology-backup/<ts>/，但破坏性替换必须**显式**给出")
    parser.add_argument("--only", metavar="NAME", action="append", default=None,
                        help="可重复；只处理指定 skill（名字必须在本仓库清单内，否则 exit 2）")
    parser.add_argument("--json", action="store_true", help="只输出 JSON，不混排人读前缀")
    args = parser.parse_args()

    if args.check:
        if args.mode != "install" and args.mode != "check":
            return _fail(args, 2, f"--check 与 --mode {args.mode} 冲突",
                         ["--check 是 --mode check 的别名，不能与 --mode uninstall 同时给。"])
        args.mode = "check"
    mode = args.mode

    if args.replace_dir and not args.backup_dir:
        return _fail(args, 2, "--replace-dir 必须同时给 --backup-dir",
                     ["不允许无备份的破坏性替换；备份默认落 <TMP>/agent-methodology-backup/<ts>/，"
                      "不在仓库内、也不在项目内留 .bak。"])

    repo = repo_root()
    try:
        skills = iter_skills(repo)
    except SkillManifestError as exc:
        return _fail(args, 2, "skill 清单不可信，拒绝继续（fail-closed）", exc.problems)

    names = [s[0] for s in skills]
    dirs = {s[0]: s[1] for s in skills}

    if args.only:
        unknown = [n for n in args.only if n not in names]
        if unknown:
            return _fail(args, 2, "--only 含本仓库清单外的名字（打错名字必须炸，不能静默少装一个）",
                         [f"清单外：{', '.join(unknown)}", f"本仓库清单：{', '.join(names)}"])
        selected = [n for n in names if n in set(args.only)]
    else:
        selected = names

    if args.project_link:
        proj = Path(args.project_link).expanduser()
        if not proj.is_dir():
            return _fail(args, 2, f"--project-link 指向的路径不存在或不是目录：{proj}", [])
        target_root = proj / ".agents" / SKILLS_DIR_NAME
        home = None
    else:
        home = codex_home(args.codex_home)
        target_root = home / SKILLS_DIR_NAME

    rows = []
    root_existed = target_root.exists()
    if not root_existed:
        if mode == "check":
            # check 必须零副作用：报 missing-root + exit 1，绝不创建
            rows.append(_row("<target-root>", "fail", "missing-root", "missing-root",
                             "目标根不存在；--check 零副作用，不创建",
                             [f"期望目标根：{target_root}",
                              "安装请去掉 --check 后重跑 scripts/install.py"],
                             None, None, scope="root", path=str(target_root)))
            emit(rows, args.json,
                 envelope={"mode": mode, "target_root": str(target_root),
                           "codex_home": str(home) if home else None, "dry_run": args.dry_run},
                 rows_key="results", json_keys=JSON_KEYS,
                 summary={**{k: 0 for k in SUMMARY_KEYS}, "missing": len(rows)},
                 summary_line=f"install: mode={mode} · target_root={target_root} · "
                              f"missing-root=1 · exit=1",
                 exit_code=1)
            return 1
        if not args.dry_run:
            try:
                target_root.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                return _fail(args, 2, f"无法创建目标根：{target_root}", [str(exc)])

    if target_root.is_symlink():
        rows.append(_row("<target-root>", "warn", "symlink-root", "warn",
                         f"目标根本身是软链，按 resolve() 后的真实目录继续（{os.path.realpath(target_root)}）",
                         None, str(target_root), None, scope="root", path=str(target_root)))

    if not args.dry_run and target_root.exists() and not os.access(target_root, os.W_OK):
        return _fail(args, 2, f"目标根不可写：{target_root}", [])

    if args.dry_run and not args.json:
        print('[DRY-RUN] 只报告不写；退出码反映"将会发生什么"')

    backup_root = Path(args.backup_dir).expanduser() if args.backup_dir else None
    ops = []
    for name in selected:
        target = dirs[name]
        link = target_root / name
        row, op = _plan(name, target, link, mode, args, repo, backup_root)
        if args.dry_run and op:
            row["message"] = f"{row['message']}（--dry-run：未执行）"
        rows.append(row)
        ops.append((op, link, target, name))

    for op, link, target, name in ops:
        try:
            _apply(op, link, target, name, backup_root, args.dry_run)
        except OSError as exc:
            return _fail(args, 2, f"{name}: 写入失败：{exc}",
                         [f"目标：{link}", "已完成的动作不会自动回滚；请重跑 --check 确认当前状态。"])

    summary = {k: 0 for k in SUMMARY_KEYS}
    for r in rows:
        if r.get("state") in ("missing-root",):
            continue
        if r["name"] not in selected and r["level"] == "warn" and r["state"] == "symlink-root":
            continue
        summary[_summary_key(r["action"])] += 1
    code = 1 if any(r["level"] == "fail" for r in rows) else 0
    parts = " ".join(f"{k}={v}" for k, v in summary.items() if v) or "无动作"
    emit(rows, args.json,
         envelope={"mode": mode, "target_root": str(target_root),
                   "codex_home": str(home) if home else None, "dry_run": args.dry_run},
         rows_key="results", json_keys=JSON_KEYS, summary=summary,
         summary_line=f"install: mode={mode} · target_root={target_root} · {parts} · exit={code}",
         exit_code=code)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
