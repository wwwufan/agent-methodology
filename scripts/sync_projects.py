#!/usr/bin/env python3
"""Synchronize agent-methodology skill symlinks to explicitly registered projects.

The canonical skill inventory and link behavior stay in ``install.py``.  This
script adds only multi-project routing, local exclude maintenance, preflight,
post-write verification, and optional pruning of stale managed symlinks.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import SkillManifestError, iter_skills, repo_root  # noqa: E402


DEFAULT_CONFIG = Path(".local/sync-targets.json")
CONFIG_KEYS = {"schema_version", "projects"}
PROJECT_KEYS = {"name", "path", "ignore_links"}
EXCLUDE_HEADER = "# Local agent-methodology skill links (managed locally)"


class SyncConfigError(Exception):
    pass


@dataclass(frozen=True)
class Target:
    name: str
    path: Path
    ignore_links: bool


def _json_load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SyncConfigError(
            f"sync config not found: {path}\n"
            "Create .local/sync-targets.json or pass --config <path>."
        ) from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise SyncConfigError(f"cannot read sync config {path}: {exc}") from exc


def _git_root(path: Path) -> Path:
    proc = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise SyncConfigError(f"project is not a Git worktree: {path}")
    return Path(proc.stdout.strip()).resolve()


def load_targets(config_path: Path) -> list[Target]:
    config_path = config_path.expanduser().resolve()
    raw = _json_load(config_path)
    if not isinstance(raw, dict):
        raise SyncConfigError("sync config root must be a JSON object")
    unknown = set(raw) - CONFIG_KEYS
    if unknown:
        raise SyncConfigError(f"unknown sync config keys: {', '.join(sorted(unknown))}")
    if raw.get("schema_version") != 1:
        raise SyncConfigError("sync config schema_version must be 1")
    projects = raw.get("projects")
    if not isinstance(projects, list) or not projects:
        raise SyncConfigError("sync config projects must be a non-empty list")

    targets: list[Target] = []
    seen_names: set[str] = set()
    seen_paths: set[Path] = set()
    for index, item in enumerate(projects, start=1):
        if not isinstance(item, dict):
            raise SyncConfigError(f"projects[{index}] must be a JSON object")
        extra = set(item) - PROJECT_KEYS
        if extra:
            raise SyncConfigError(
                f"projects[{index}] has unknown keys: {', '.join(sorted(extra))}"
            )
        name = item.get("name")
        value = item.get("path")
        ignore_links = item.get("ignore_links", False)
        if not isinstance(name, str) or not name.strip():
            raise SyncConfigError(f"projects[{index}].name must be a non-empty string")
        if not isinstance(value, str) or not value.strip():
            raise SyncConfigError(f"projects[{index}].path must be a non-empty string")
        if not isinstance(ignore_links, bool):
            raise SyncConfigError(f"projects[{index}].ignore_links must be boolean")
        project = Path(value).expanduser()
        if not project.is_absolute():
            project = config_path.parent / project
        project = project.resolve()
        if not project.is_dir():
            raise SyncConfigError(f"project path does not exist: {project}")
        root = _git_root(project)
        if root != project:
            raise SyncConfigError(
                f"project path must be the Git worktree root: configured={project} actual={root}"
            )
        clean_name = name.strip()
        if clean_name in seen_names:
            raise SyncConfigError(f"duplicate project name: {clean_name}")
        if project in seen_paths:
            raise SyncConfigError(f"duplicate project path: {project}")
        seen_names.add(clean_name)
        seen_paths.add(project)
        targets.append(Target(clean_name, project, ignore_links))
    return targets


def _run_install(
    repo: Path,
    target: Target,
    names: list[str],
    *,
    check: bool,
    dry_run: bool = False,
):
    command = [
        sys.executable,
        str(repo / "scripts" / "install.py"),
        "--project-link",
        str(target.path),
        "--json",
    ]
    if check:
        command += ["--mode", "check"]
    if dry_run:
        command.append("--dry-run")
    for name in names:
        command += ["--only", name]
    proc = subprocess.run(command, text=True, capture_output=True, check=False)
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        payload = {
            "error": "install.py returned non-JSON output",
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "exit": 2,
        }
        return 2, payload
    return proc.returncode, payload


def _intended_target(link: Path) -> Path | None:
    if not link.is_symlink():
        return None
    try:
        raw = os.readlink(link)
    except OSError:
        return None
    target = Path(raw)
    if not target.is_absolute():
        target = link.parent / target
    return Path(os.path.realpath(target))


def stale_managed_links(repo: Path, target: Target, current_names: set[str]) -> list[Path]:
    root = target.path / ".agents/skills"
    if not root.exists():
        return []
    canonical = (repo / "skills").resolve()
    stale: list[Path] = []
    try:
        children = list(root.iterdir())
    except OSError:
        return []
    for child in children:
        intended = _intended_target(child)
        if intended is None:
            continue
        try:
            intended.relative_to(canonical)
        except ValueError:
            continue
        if child.name not in current_names or not intended.exists():
            stale.append(child)
    return sorted(stale, key=lambda p: p.name)


def _git_exclude_path(project: Path) -> Path:
    proc = subprocess.run(
        [
            "git",
            "-C",
            str(project),
            "rev-parse",
            "--path-format=absolute",
            "--git-path",
            "info/exclude",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        raise SyncConfigError(f"cannot resolve Git exclude file for {project}")
    return Path(proc.stdout.strip())


def expected_exclude_patterns(target: Target, names: list[str]) -> list[str]:
    if not target.ignore_links:
        return []
    resolved_root = (target.path / ".agents/skills").resolve()
    try:
        relative = resolved_root.relative_to(target.path.resolve())
    except ValueError as exc:
        raise SyncConfigError(
            f"resolved skill root escapes project for {target.name}: {resolved_root}"
        ) from exc
    prefix = relative.as_posix().strip("/")
    return [f"/{prefix}/{name}" for name in names]


def ensure_excludes(target: Target, names: list[str], *, check: bool):
    patterns = expected_exclude_patterns(target, names)
    if not patterns:
        return {"added": [], "missing": []}
    path = _git_exclude_path(target.path)
    try:
        text = path.read_text(encoding="utf-8") if path.exists() else ""
    except OSError as exc:
        raise SyncConfigError(f"cannot read {path}: {exc}") from exc
    lines = set(text.splitlines())
    missing = [pattern for pattern in patterns if pattern not in lines]
    if check or not missing:
        return {"added": [], "missing": missing}

    suffix = ""
    if text and not text.endswith("\n"):
        suffix += "\n"
    if EXCLUDE_HEADER not in lines:
        if text.strip():
            suffix += "\n"
        suffix += EXCLUDE_HEADER + "\n"
    suffix += "".join(pattern + "\n" for pattern in missing)
    try:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(suffix)
    except OSError as exc:
        raise SyncConfigError(f"cannot update {path}: {exc}") from exc
    return {"added": missing, "missing": []}


def _result_row(
    target: Target,
    install_payload,
    excludes,
    stale,
    *,
    sync_summary=None,
    exclude_added=None,
):
    install_exit = int(install_payload.get("exit", 2))
    missing_excludes = excludes.get("missing", [])
    ok = install_exit == 0 and not missing_excludes and not stale
    return {
        "name": target.name,
        "path": str(target.path),
        "ok": ok,
        "install_exit": install_exit,
        "sync_summary": sync_summary or {},
        "install_summary": install_payload.get("summary", {}),
        "exclude_added": exclude_added if exclude_added is not None else excludes.get("added", []),
        "exclude_missing": missing_excludes,
        "stale_managed_links": [str(path) for path in stale],
        "install_error": install_payload.get("error"),
    }


def _emit(rows, *, mode: str, as_json: bool, exit_code: int):
    summary = {
        "projects": len(rows),
        "ok": sum(1 for row in rows if row["ok"]),
        "failed": sum(1 for row in rows if not row["ok"]),
    }
    if as_json:
        print(
            json.dumps(
                {"mode": mode, "projects": rows, "summary": summary, "exit": exit_code},
                ensure_ascii=False,
                indent=2,
            )
        )
        return
    for row in rows:
        prefix = "[OK]" if row["ok"] else "[FAIL]"
        bits = [
            f"sync={row['sync_summary']}",
            f"install={row['install_summary']}",
            f"exclude-added={len(row['exclude_added'])}",
            f"exclude-missing={len(row['exclude_missing'])}",
            f"stale={len(row['stale_managed_links'])}",
        ]
        print(f"{prefix} {row['name']}: {' · '.join(bits)}")
        if row["install_error"]:
            print(f"       install error: {row['install_error']}")
        for value in row["exclude_missing"]:
            print(f"       missing exclude: {value}")
        for value in row["stale_managed_links"]:
            print(f"       stale managed link: {value}")
    print(
        f"sync-projects: mode={mode} · projects={summary['projects']} · "
        f"ok={summary['ok']} · failed={summary['failed']} · exit={exit_code}"
    )


def _fail(message: str, *, as_json: bool, code: int = 2):
    if as_json:
        print(json.dumps({"error": message, "exit": code}, ensure_ascii=False, indent=2))
    else:
        print(f"[FAIL] {message}")
    return code


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Synchronize canonical agent-methodology skills to registered projects."
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Local target registry; default: <repo>/.local/sync-targets.json",
    )
    parser.add_argument("--only", action="append", default=None, metavar="SKILL")
    parser.add_argument("--check", action="store_true", help="Read-only drift check")
    parser.add_argument(
        "--prune",
        action="store_true",
        help="Remove stale symlinks that still point into this repository",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.prune and args.only:
        return _fail("--prune cannot be combined with --only", as_json=args.json)
    if args.prune and args.check:
        return _fail("--prune is a write operation and cannot be combined with --check", as_json=args.json)

    repo = repo_root()
    config = Path(args.config).expanduser() if args.config else repo / DEFAULT_CONFIG
    try:
        skills = iter_skills(repo)
        targets = load_targets(config)
    except (SkillManifestError, SyncConfigError) as exc:
        detail = "; ".join(exc.problems) if isinstance(exc, SkillManifestError) else str(exc)
        return _fail(detail, as_json=args.json)

    all_names = [item[0] for item in skills]
    if args.only:
        unknown = sorted(set(args.only) - set(all_names))
        if unknown:
            return _fail(
                f"unknown skill names: {', '.join(unknown)}; available: {', '.join(all_names)}",
                as_json=args.json,
            )
        selected = [name for name in all_names if name in set(args.only)]
    else:
        selected = all_names

    actions = {}
    if not args.check:
        preflight_failures = []
        for target in targets:
            code, payload = _run_install(repo, target, selected, check=False, dry_run=True)
            if code != 0:
                preflight_failures.append((target, payload))
        if preflight_failures:
            rows = []
            for target, payload in preflight_failures:
                rows.append(
                    _result_row(
                        target,
                        payload,
                        {"added": [], "missing": []},
                        stale_managed_links(repo, target, set(all_names)),
                    )
                )
            _emit(rows, mode="preflight", as_json=args.json, exit_code=1)
            return 1

        for target in targets:
            code, payload = _run_install(repo, target, selected, check=False)
            if code != 0:
                # install.py reports exactly what was already changed.  Stop before touching later targets.
                row = _result_row(
                    target,
                    payload,
                    {"added": [], "missing": []},
                    stale_managed_links(repo, target, set(all_names)),
                )
                _emit([row], mode="sync-partial", as_json=args.json, exit_code=1)
                return 1
            try:
                exclude_changes = ensure_excludes(target, selected, check=False)
            except SyncConfigError as exc:
                return _fail(str(exc), as_json=args.json)
            actions[target.name] = {
                "summary": payload.get("summary", {}),
                "exclude_added": exclude_changes.get("added", []),
            }

        if args.prune:
            for target in targets:
                for link in stale_managed_links(repo, target, set(all_names)):
                    link.unlink()

    rows = []
    for target in targets:
        _, payload = _run_install(repo, target, selected, check=True)
        try:
            excludes = ensure_excludes(target, selected, check=True)
            stale = stale_managed_links(repo, target, set(all_names))
        except SyncConfigError as exc:
            payload = {"exit": 2, "error": str(exc), "summary": {}}
            excludes = {"added": [], "missing": []}
            stale = []
        action = actions.get(target.name, {})
        rows.append(
            _result_row(
                target,
                payload,
                excludes,
                stale,
                sync_summary=action.get("summary"),
                exclude_added=action.get("exclude_added"),
            )
        )

    exit_code = 0 if all(row["ok"] for row in rows) else 1
    _emit(rows, mode="check" if args.check else "sync", as_json=args.json, exit_code=exit_code)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
