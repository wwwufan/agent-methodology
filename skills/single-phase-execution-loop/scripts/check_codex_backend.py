#!/usr/bin/env python3
"""校验 Codex 协作编排所需的项目代理配置与父会话模型继承策略。

归属：本检查是 `single-phase-execution-loop`（阶段内 designer→executor→reviewer 循环）在
**委托子代理之前**必须跑的门禁，故脚本住在本 skill 的 `scripts/` 下（Phase 2 从
`multi-phase-plan-orchestrator/scripts/` 移来）；`multi-phase-plan-orchestrator` 只是引用它。

刻意**不 import `scripts/_common.py`**：本文件要能随单个 skill 目录被挂载后独立运行，
引入仓库级模块会让「skill 自包含」这条性质失效（且 doctor 第 2 组的 py_compile 是单文件编译）。

退出码：0 = ready；1 = not-ready（stdout 上是一个 JSON 文档，零 traceback）；2 = 用法错误。
"""

# <方法论仓库> = agent-methodology 仓库根目录（装着 skills/、scripts/、templates/ 的那一层）；用户可见定义见 README.md「占位符约定」。

from __future__ import annotations

import argparse
import json
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path


REQUIRED_ROLES = ("designer", "executor", "reviewer")

# 配置结构缺失与模型继承/权限不满足分别报告，避免把模型名写回角色文件。
REASON_ROLE_CONFIG = "role-config"
REASON_MODEL_BINDING = "model-binding"

# RR29：hint 里的脚本路径改为 `<方法论仓库>/…` 占位符形态。裸程序名（`bootstrap_project.py`）
# 只在「cwd 恰好是仓库根」时才照做得通，而本脚本的调用方（编排 skill）cwd 是**项目根**，
# 于是那条指引在真实调用场景下必然失败。占位符的定义行就在本文件 docstring 之后。
HINT_ROLE_CONFIG = (
    "运行 `<方法论仓库>/scripts/bootstrap_project.py <PROJECT> --backend codex` 铺设 "
    ".codex/config.toml 的围栏注册与三角色配置，然后重跑本检查；已有配置则按 reason 里的具体缺失项补齐。"
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
    model: str | None
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

    if "default_subagent_model" in agents:
        raise ValueError("项目 agents.default_subagent_model 覆盖父会话模型，请移除该覆盖")
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
        model = str(payload["model"]) if "model" in payload else None
        sandbox_mode = str(payload.get("sandbox_mode") or "")
        approval_policy = str(payload.get("approval_policy") or "")
        developer_instructions = str(payload.get("developer_instructions") or "").strip()
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
    active_model: str | None = None,
    available_models: set[str] | None = None,
) -> None:
    """校验继承策略与权限；不探测 CLI 全局默认模型来猜测主窗口模型。

    active_model / available_models 只接收调用方明确提供的会话信息，保留旧调用兼容。
    """
    if active_model and available_models is not None and active_model not in available_models:
        raise ValueError(f"Codex 当前活动模型不在可用模型列表: {active_model}")
    for role in REQUIRED_ROLES:
        config = role_configs[role]
        if config.model is not None:
            raise ValueError(f"Codex 角色必须省略 model，以继承主窗口模型: {role}")
    if role_configs["designer"].sandbox_mode != "read-only":
        raise ValueError("Codex Designer 必须配置为 read-only")
    if role_configs["reviewer"].sandbox_mode != "read-only":
        raise ValueError("Codex Reviewer 必须配置为 read-only")
    if role_configs["executor"].sandbox_mode != "workspace-write":
        raise ValueError("Codex Executor 必须配置为 workspace-write")


def _load_role_configs_or_not_ready(repo_root: Path) -> dict[str, RoleConfig]:
    """把角色配置阶段的所有可预期失败收敛成 NotReady(role-config)。"""
    try:
        return load_role_configs(repo_root)
    except (ValueError, FileNotFoundError, OSError,
            tomllib.TOMLDecodeError) as exc:  # TOMLDecodeError 是 ValueError 子类；显式列出只为可读
        raise NotReady(REASON_ROLE_CONFIG, f"{type(exc).__name__}: {exc}",
                       HINT_ROLE_CONFIG) from exc


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
            "三个角色的 TOML 必须省略 model，调用时不指定具体模型，由后端继承主窗口模型；"
            "权限错误请按 reason 修复 sandbox_mode，不要写回具体模型名。",
        ) from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="校验 Codex 编排后端")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--active-model")
    parser.add_argument("--available-model", action="append", default=None)
    parser.add_argument("--codex-bin", default="codex",
                        help="兼容旧调用；不再通过 CLI 探测主窗口模型")
    args = parser.parse_args()

    try:
        role_configs = _load_role_configs_or_not_ready(args.repo_root)
        active_model = args.active_model
        available_models = set(args.available_model) if args.available_model is not None else None
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
