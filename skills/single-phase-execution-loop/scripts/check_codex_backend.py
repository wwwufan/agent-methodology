#!/usr/bin/env python3
"""校验 Codex 协作编排所需的项目代理配置与当前运行模型。

归属：本检查是 `single-phase-execution-loop`（阶段内 designer→executor→reviewer 循环）在
**委托子代理之前**必须跑的门禁，故脚本住在本 skill 的 `scripts/` 下（Phase 2 从
`multi-phase-plan-orchestrator/scripts/` 移来）；`multi-phase-plan-orchestrator` 只是引用它。

刻意**不 import `scripts/_common.py`**：本文件要能随单个 skill 目录被挂载后独立运行，
引入仓库级模块会让「skill 自包含」这条性质失效（且 doctor 第 2 组的 py_compile 是单文件编译）。

退出码：0 = ready；1 = not-ready（stdout 上是一个 JSON 文档，零 traceback）；2 = 用法错误。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path


REQUIRED_ROLES = ("designer", "executor", "reviewer")

# 三类 not-ready 成因。分类是**给编排者看的**：role-config 要跑 bootstrap 铺配置，
# model-binding 要改角色 model 或换后端，probe 要修 codex CLI 或显式传模型 —— 三者的下一步完全不同。
REASON_ROLE_CONFIG = "role-config"
REASON_MODEL_BINDING = "model-binding"
REASON_PROBE = "probe"

HINT_ROLE_CONFIG = (
    "运行 bootstrap_project.py <repo-root> --backend codex 铺设 .codex/config.toml 的围栏注册"
    "与三角色配置，然后重跑本检查；已有配置则按 reason 里的具体缺失项补齐。"
)


class NotReady(Exception):
    """可预期的「没准备好」。携带 reason_class / reason / hint，由 main() 渲染成 JSON。

    存在的理由：缺项目角色配置时抛裸 ValueError 会打印一整屏 traceback，
    而调用方（编排 skill）需要的是一条机器可读的结论 + 一句人能照做的修复指引。
    """

    def __init__(self, reason_class: str, reason: str, hint: str):
        self.reason_class = reason_class
        self.reason = reason
        self.hint = hint
        super().__init__(reason)


@dataclass(frozen=True)
class RoleConfig:
    role: str
    config_path: str
    model: str
    sandbox_mode: str
    approval_policy: str
    has_developer_instructions: bool


def _read_toml(path: Path) -> dict:
    with path.open("rb") as file:
        payload = tomllib.load(file)
    if not isinstance(payload, dict):
        raise ValueError(f"TOML 根必须是对象: {path}")
    return payload


def load_role_configs(repo_root: Path) -> dict[str, RoleConfig]:
    """从 Codex 项目配置真源读取三个编排角色。"""
    repo_root = repo_root.resolve()
    registry_path = repo_root / ".codex/config.toml"
    registry = _read_toml(registry_path)
    agents = registry.get("agents")
    if not isinstance(agents, dict):
        raise ValueError(f"Codex 项目配置缺少 agents: {registry_path}")

    result: dict[str, RoleConfig] = {}
    for role in REQUIRED_ROLES:
        registration = agents.get(role)
        if not isinstance(registration, dict):
            raise ValueError(f"Codex 项目配置缺少角色注册: {role}")
        config_file = str(registration.get("config_file") or "")
        if not config_file:
            raise ValueError(f"Codex 角色缺少 config_file: {role}")
        config_path = (registry_path.parent / config_file).resolve()
        try:
            config_path.relative_to(registry_path.parent.resolve())
        except ValueError as exc:
            raise ValueError(f"Codex 角色配置越出 .codex: {role}: {config_path}") from exc
        payload = _read_toml(config_path)
        model = str(payload.get("model") or "")
        sandbox_mode = str(payload.get("sandbox_mode") or "")
        approval_policy = str(payload.get("approval_policy") or "")
        developer_instructions = str(payload.get("developer_instructions") or "").strip()
        if not model:
            raise ValueError(f"Codex 角色缺少 model: {role}")
        if not sandbox_mode:
            raise ValueError(f"Codex 角色缺少 sandbox_mode: {role}")
        if not approval_policy:
            raise ValueError(f"Codex 角色缺少 approval_policy: {role}")
        if not developer_instructions:
            raise ValueError(f"Codex 角色缺少 developer_instructions: {role}")
        result[role] = RoleConfig(
            role=role,
            config_path=config_path.relative_to(repo_root).as_posix(),
            model=model,
            sandbox_mode=sandbox_mode,
            approval_policy=approval_policy,
            has_developer_instructions=True,
        )
    return result


def validate_backend(
    *,
    role_configs: dict[str, RoleConfig],
    active_model: str,
    available_models: set[str],
) -> None:
    """验证无 per-call model 参数的协作后端可以安全继承当前模型。"""
    if not active_model:
        raise ValueError("无法确定 Codex 当前活动模型")
    if active_model not in available_models:
        raise ValueError(f"Codex 当前活动模型不在可用模型列表: {active_model}")
    for role in REQUIRED_ROLES:
        config = role_configs[role]
        if config.model not in available_models:
            raise ValueError(f"Codex 角色模型不可用: {role}: {config.model}")
        if config.model != active_model:
            raise ValueError(
                "当前 spawn_agent 不支持 per-call model；角色模型必须与活动模型一致: "
                f"{role}: configured={config.model} active={active_model}"
            )
    if role_configs["designer"].sandbox_mode != "read-only":
        raise ValueError("Codex Designer 必须配置为 read-only")
    if role_configs["reviewer"].sandbox_mode != "read-only":
        raise ValueError("Codex Reviewer 必须配置为 read-only")
    if role_configs["executor"].sandbox_mode != "workspace-write":
        raise ValueError("Codex Executor 必须配置为 workspace-write")


def _run_json(command: list[str]) -> dict | list:
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if not result.stdout.strip():
        raise ValueError(
            f"命令未返回 JSON: {' '.join(command)}: {result.stderr.strip()}"
        )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(f"命令返回非法 JSON: {' '.join(command)}") from exc


def detect_active_model(codex_bin: str = "codex") -> str:
    report = _run_json([codex_bin, "doctor", "--json"])
    if not isinstance(report, dict):
        raise ValueError("codex doctor 输出必须是对象")
    checks = report.get("checks")
    if not isinstance(checks, dict):
        raise ValueError("codex doctor 输出缺少 checks")
    config_load = checks.get("config.load")
    if not isinstance(config_load, dict):
        raise ValueError("codex doctor 输出缺少 config.load")
    details = config_load.get("details")
    if not isinstance(details, dict):
        raise ValueError("codex doctor config.load 缺少 details")
    return str(details.get("model") or "")


def detect_available_models(codex_bin: str = "codex") -> set[str]:
    payload = _run_json([codex_bin, "debug", "models"])
    rows = payload if isinstance(payload, list) else payload.get("models", [])
    if not isinstance(rows, list):
        raise ValueError("codex debug models 输出缺少 models")
    models = {
        str(row.get("slug") or row.get("id") or row.get("model") or "")
        for row in rows
        if isinstance(row, dict)
    }
    models.discard("")
    return models


def _load_role_configs_or_not_ready(repo_root: Path) -> dict[str, RoleConfig]:
    """把角色配置阶段的所有可预期失败收敛成 NotReady(role-config)。"""
    try:
        return load_role_configs(repo_root)
    except (ValueError, FileNotFoundError, OSError,
            tomllib.TOMLDecodeError) as exc:  # TOMLDecodeError 是 ValueError 子类；显式列出只为可读
        raise NotReady(REASON_ROLE_CONFIG, f"{type(exc).__name__}: {exc}",
                       HINT_ROLE_CONFIG) from exc


def _probe_models_or_not_ready(args) -> tuple[str, set[str]]:
    """把探测阶段（shell out 到 codex CLI）的可预期失败收敛成 NotReady(probe)。"""
    try:
        active_model = args.active_model or detect_active_model(args.codex_bin)
        available_models = (
            set(args.available_model)
            if args.available_model is not None
            else detect_available_models(args.codex_bin)
        )
    except (ValueError, FileNotFoundError, OSError, subprocess.SubprocessError) as exc:
        raise NotReady(
            REASON_PROBE, f"{type(exc).__name__}: {exc}",
            "无法从 codex CLI 读到模型信息：确认 --codex-bin 指向可执行的 codex"
            f"（当前 {args.codex_bin}），或用 --active-model / --available-model 显式传入。",
        ) from exc
    return active_model, available_models


def _validate_or_not_ready(role_configs, active_model, available_models) -> None:
    """把模型绑定阶段的失败收敛成 NotReady(model-binding)（编排期门禁，不是安装缺陷）。"""
    try:
        validate_backend(
            role_configs=role_configs,
            active_model=active_model,
            available_models=available_models,
        )
    except ValueError as exc:
        raise NotReady(
            REASON_MODEL_BINDING, str(exc),
            "当前协作后端不支持 per-call model，角色模型必须等于活动模型"
            f"（活动模型：{active_model or '未探测到'}）：把 .codex/agents/<role>.toml 的 model "
            "改成活动模型后重跑，或改用支持 named-agent / per-call model 的后端。",
        ) from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="校验 Codex 编排后端")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--active-model")
    parser.add_argument("--available-model", action="append", default=None)
    parser.add_argument("--codex-bin", default="codex",
                        help="探测活动模型与可用模型时调用的 codex 可执行文件；缺省 codex")
    args = parser.parse_args()

    try:
        role_configs = _load_role_configs_or_not_ready(args.repo_root)
        active_model, available_models = _probe_models_or_not_ready(args)
        _validate_or_not_ready(role_configs, active_model, available_models)
    except NotReady as exc:
        # 结论走 **stdout**（调用方按 JSON 读），退出码 1；零 traceback 是本改造的硬要求。
        print(json.dumps({
            "status": "not-ready",
            "backend": "codex_collaboration",
            "reason_class": exc.reason_class,
            "reason": exc.reason,
            "hint": exc.hint,
            "repo_root": str(args.repo_root),
        }, ensure_ascii=False, indent=2))
        return 1

    print(
        json.dumps(
            {
                "status": "ready",
                "backend": "codex_collaboration",
                "active_model": active_model,
                "model_binding": "backend_managed_inheritance",
                "roles": {
                    role: asdict(config) for role, config in role_configs.items()
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
