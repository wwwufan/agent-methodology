#!/usr/bin/env python3
"""栈式工作队列：把「一轮里的多个待办」与「推进中衍生的新问题」外化到文件。

## 为什么需要脚本而不是靠记性

一轮里常有多个待办（①②③）。推进 ① 时衍生出新问题，若当场展开，思路被带走，
① 做完时 ②③ 与衍生项全都只存在于对话记忆里；而对话记忆会被压缩、换模型、跨天丢弃。
本脚本把队列变成文件里的显式栈，并把三条纪律做成**机械动作**而非自觉：

1. `show` 随时可跑 → 新工作开始前先把已有队列摊开
2. `capture` 先登记再决定 → 衍生问题不会因为在忙而消失
3. `pop` **自动打印**四段回看 → 关掉一帧时必然看到「还剩什么、下一步做什么」

`activate` 区分两种切换：目标是当前栈顶的后代 → 栈顶转 `suspended`，关掉子帧后**自动恢复**；
目标与栈顶无祖先关系（用户临时改主意）→ 栈顶退回 `queued` 并**显式告警**，因为它不会被自动恢复。

`verify` 把「未处置的衍生登记」和「静默消失的 queued 帧」判为失败，
所以遗忘会在收工时被抓到，而不是在下一轮才发现。

## 真源边界

本文件（`active-work-stack.json`）只存**推进状态与指针**，不复制
`docs/operations/issues.md` / `goal-ledger.md` / `next-work-plan.md` 的正文。
跨轮次缺陷应升级立项，栈里改 `escalated` 并留 `ISS-0xx` 指针。

## 用法

    S=<本 skill 目录>/scripts/stack.py   # <本 skill 目录> = 装着本脚本的那个 skill 根目录
    python3 $S ensure  --campaign <id> [--activation auto_orchestration|user_declared]
    python3 $S show    --campaign <id>
    python3 $S push    --campaign <id> --title … [--goal …] [--criteria …]… [--parent F-00x] [--activate]
    python3 $S capture --campaign <id> --text … [--found-in F-00x] [--disposition blocks|spawns|note]
    python3 $S resolve --campaign <id> --capture C-00x --disposition … [--frame F-00y] [--pointer ISS-0zz]
    python3 $S pop     --campaign <id> --frame F-00x --terminal done|parked|escalated|wontfix --note …
    python3 $S verify  --campaign <id>
    python3 $S render  --campaign <id> [--check]

## 退出码

- `0` 成功（含 `verify` 无违规、`render --check` 一致）
- `1` `verify` 发现不变量违规；或 `pop` 时存在未处置衍生项
- `2` 用法/环境错误（栈文件缺失或损坏、frame_id 不存在、状态迁移非法、深度超限、
  `push` 时栈不存在——创建栈只有 `ensure` 一个门，防止 `--campaign` 打错导致栈分叉）
"""
# <方法论仓库> = agent-methodology 仓库根目录（装着 skills/、scripts/、templates/ 的那一层）；用户可见定义见 README.md「占位符约定」。

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import shutil
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple

SCHEMA_VERSION = "work-queue-stack-v3"
PREV_SCHEMA_VERSION = "work-queue-stack-v2"
V1_SCHEMA_VERSION = "work-queue-stack-v1"

# 栈的绑定对象是**总目标（campaign）**，与同目录的总目标台账 goal-ledger.md 一对一绑定。
# 刻意不绑轮次 / 对话窗口 / 阶段 Goal：
#   - Goal 是独占、串行、不可暂停资源，一阶段一个、收口即释放，而阶段之间的收尾工作
#     恰恰发生在 Goal 释放之后 —— 绑 Goal 会在最该留状态的时候把栈丢掉；
#   - phase 装不下跨阶段的帧（例如「把编排契约改动 commit」）与不属于任何阶段的工具自建帧；
#   - campaign 是唯一能横跨多 Goal / 多 phase / 多会话 / 跨天的稳定标识。
# 因此栈跨轮续用，retro 复盘的是整个 campaign，不是「一轮」。
LEDGER_FILE_NAME = "goal-ledger.md"

# 栈是怎么被启用的。受控目标模式与多阶段编排自动启用（auto_orchestration）；
# 其他情况必须用户显式声明（user_declared）；v3 之前创建的栈无从考证，如实记 pre-v3-unknown。
# v4：栈的启用一律经用户 —— 用户主动声明，或代理评估复杂度后申请并获批准。
# `auto_orchestration` 降为 legacy：编排 skill 曾无条件 ensure 建栈，现改为「评估 + 申请」。
# legacy 值只接受、不再新发，verify 见到给软警告（不改写历史，猜出来的绑定比没有更坏）。
ACTIVATIONS = ("user_declared", "user_approved_on_proposal", "pre-v3-unknown", "auto_orchestration")
LEGACY_ACTIVATIONS = ("auto_orchestration",)

# 事件种类。event_log 是复盘（retro）的真源：只追加，永不改写。
# actor 只对 activated/suspended/resumed/requeued 有意义，用于区分
# 「DFS 自动抢占」与「用户主动改道」——后者是复盘最关心的弯路信号。
EVENT_KINDS = ("pushed", "activated", "suspended", "resumed", "requeued",
               "captured", "resolved", "popped", "amended", "migrated",
               "proposed", "pointer_switched", "retitled")
ACTORS = ("dfs", "user", "auto")

# 栈真源与派生视图在 campaign 目录内的固定文件名
STACK_FILE_NAME = "active-work-stack.json"
VIEW_FILE_NAME = "active-work-stack.md"

# v4：任务栈文件夹。栈搬出 scratch/（那里被 gitignore、且 clean-scratch-intermediates 会清空内容），
# 改为项目内纳入 Git 的目录 —— 于是 git clean -fdx 与清理 skill 都删不掉被契约定为「唯一真源」的推进状态。
# 注意：从这里到 DEFAULT_LAYOUT 的三组值都只是**默认布局**，不是硬约定 ——
# 项目可以在 <repo_root>/workstacks/config.json 里覆盖（见 load_layout），
# 于是本 skill 不再假设任何具体的目录约定（仓库级路径发现的唯一真源是 Layout）。
WORKSTACK_ROOT = "workstacks"
# 旧位置（v3 及以前）：scratch/workbench/<campaign>/。仅用于迁移、台账回退查找与拒绝栈分叉
LEGACY_WORKBENCH = ("scratch", "workbench")
# 单栈指针：一个对话只允许绑一个栈，全局只留一个指针（用户 2026-09-20「排除复杂情况」）。
# 不入库 —— 否则每次切换都脏 Git，多窗口还会互相覆盖。
POINTER_FILE_NAME = "_current.json"

# 长期待办池的两个真源：进 Git、跨轮次。survey 只读它们抽索引，绝不复制正文进栈。
PLAN_DOC = Path("docs/operations/next-work-plan.md")
ISSUE_DOC = Path("docs/operations/issues.md")

# 布局配置文件名固定为 <repo_root>/workstacks/config.json —— **不随 workstack_root 变**，
# 否则「先知道布局才能找到布局配置」就成了自指循环（配置里改 workstack_root 会让配置自己失踪）。
LAYOUT_CONFIG_NAME = "config.json"
LAYOUT_KEYS = ("workstack_root", "plan_doc", "issue_doc")


class Layout(NamedTuple):
    """一次运行内解析出的仓库布局；三个字段都是**仓库根相对路径**。

    存在理由：把「栈住哪、两个长期池住哪」从散落在各命令里的字面量收敛成一个值对象，
    于是新增一种布局只需改配置发现，不必逐处改文案与路径拼接。
    """

    workstack_root: str
    plan_doc: Path
    issue_doc: Path


DEFAULT_LAYOUT = Layout(WORKSTACK_ROOT, PLAN_DOC, ISSUE_DOC)

# 仓库根标记，按优先级排。find_repo_root **分四趟**查找（每趟独立从起点向上走），
# 而不是「逐层看哪个标记先命中」：pass1 与去 .git 硬依赖之前的实现完全同构，
# 于是「旧代码能成功的输入，新代码返回值必然相同」是构造性成立的（行为等价的免证依据）；
# pass2~4 只在旧实现必然 die(2) 的输入上生效。
# 已知限制：pass2 的标记名用**默认** workstacks —— 唯一标记是自定义 workstack_root 的仓库
# 必须显式传 --repo-root（配置文件自身住在 <root>/workstacks/ 下，先有根才能读到它）。
ROOT_MARKERS = (".git", WORKSTACK_ROOT, "AGENTS.md", ".codex")

# 未关闭状态：仍在栈里
OPEN_STATUS = ("queued", "active", "suspended")
# 终态：必须带 close_note，并在 pop_log 留一行，不得静默消失
TERMINAL_STATUS = ("done", "parked", "escalated", "wontfix")
ALL_STATUS = OPEN_STATUS + TERMINAL_STATUS

# 允许的栈深上限（depth 取值 0..MAX_DEPTH-1）。超限说明当前帧定义太粗，应先拆分或 parked。
MAX_DEPTH = 4

DISPOSITIONS = ("pending", "blocks", "spawns", "note")


# ---------------------------------------------------------------- 基础设施


def die(code: int, msg: str) -> "NoReturn":  # noqa: F821
    print(f"[exit {code}] {msg}", file=sys.stderr)
    raise SystemExit(code)


def now() -> str:
    return datetime.now(timezone.utc).astimezone().replace(microsecond=0).isoformat()


def _markers_root(start: Path) -> Path | None:
    """仓库根解析的**唯一真源**：四趟、按 ROOT_MARKERS 优先级，每趟独立从 start 向上走。

    首个命中即短路返回；多级父目录都命中同一标记时取最近的一层（与去 .git 硬依赖前一致）。
    找不到返回 None，由调用方决定是 die 还是降级（`--path` 指到仓库外时不应致命）。
    """
    for marker in ROOT_MARKERS:
        for cand in (start, *start.parents):
            if (cand / marker).exists():
                return cand
    return None


def find_repo_root(start: Path) -> Path:
    root = _markers_root(start)
    if root is None:
        die(2, f"无法从 {start} 向上定位仓库根（依次查找标记：{' / '.join(ROOT_MARKERS)}）。\n"
               "     或显式传 --repo-root <仓库根>；"
               f"或先运行 `python3 <方法论仓库>/scripts/bootstrap_project.py <PROJECT>` 铺 {WORKSTACK_ROOT}/")
    return root


def _start_from_args(args: argparse.Namespace) -> Path:
    """`--repo-root` 只覆盖**起点**，不做权威根（保持既有语义 → 向后兼容）。

    起点不存在或不是目录 → exit 2：静默回退到 cwd 会让「打错 --repo-root」变成
    「在另一个仓库里操作」，而这类错误的表现是命令看起来成功了。
    """
    raw = getattr(args, "repo_root", None)
    if not raw:
        return Path.cwd()
    p = Path(raw).expanduser()
    if not p.is_dir():
        die(2, f"--repo-root 指向的路径不存在或不是目录：{p}")
    return p


def _layout_die(cfg: Path, msg: str) -> "NoReturn":  # noqa: F821
    """布局配置非法一律 exit 2（与既有「用法/环境错误」口径一致），文案自带修复示例。"""
    die(2, f"{cfg}: {msg}\n"
           "     期望形态：一个 JSON object，三个键全部可选，值必须是**仓库根相对路径**字符串：\n"
           '       {"workstack_root": "workstacks",\n'
           '        "plan_doc": "docs/operations/next-work-plan.md",\n'
           '        "issue_doc": "docs/operations/issues.md"}')


def load_layout(root: Path) -> Layout:
    """读 `<root>/workstacks/config.json` 得到本仓库布局。

    缺省语义（刻意）：**文件不存在 = 全默认 + 零输出**（stdout/stderr 都不许多一个字节），
    部分键缺失 = 缺的键取默认。于是「加配置发现」这件事对既有仓库是纯增量、行为零变化。
    非法一律 exit 2 并说明是哪个键 —— 拼错键名如果静默不生效，用户会得到
    「配置写了却没用」的最难排查形态，所以宁炸不默（与 `install.py --only` 含清单外名字同口径）。
    """
    cfg = root / WORKSTACK_ROOT / LAYOUT_CONFIG_NAME
    if not cfg.exists():
        return DEFAULT_LAYOUT
    try:
        raw = json.loads(cfg.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        _layout_die(cfg, f"JSON 不可解析（{exc}）")
    except OSError as exc:
        _layout_die(cfg, f"读取失败（{exc}）")
    if not isinstance(raw, dict):
        _layout_die(cfg, f"根节点必须是 JSON object，实际是 {type(raw).__name__}")
    unknown = sorted(set(raw) - set(LAYOUT_KEYS))
    if unknown:
        _layout_die(cfg, f"未知键 {', '.join(unknown)}；只允许 {' / '.join(LAYOUT_KEYS)}"
                         "（拼错会静默不生效，故宁炸不默）")
    given: dict = {}
    for key in LAYOUT_KEYS:
        if key not in raw:
            continue
        value = raw[key]
        if not isinstance(value, str) or not value.strip():
            _layout_die(cfg, f"键 {key} 的值必须是非空字符串，实际是 {value!r}")
        rel = Path(value.strip())
        if rel.is_absolute():
            _layout_die(cfg, f"键 {key} 必须是仓库根相对路径，不能是绝对路径：{value!r}")
        if ".." in rel.parts:
            _layout_die(cfg, f"键 {key} 不得含 `..` 段：{value!r}")
        try:
            (root / rel).resolve().relative_to(root.resolve())
        except ValueError:
            _layout_die(cfg, f"键 {key} 解析后逃出仓库根：{value!r}")
        given[key] = rel
    workstack_root = str(given.get("workstack_root", Path(WORKSTACK_ROOT)))
    if workstack_root == ".":
        _layout_die(cfg, 'workstack_root 不得为 "."（会与仓库根重合，栈目录失去边界）')
    return Layout(workstack_root,
                  given.get("plan_doc", PLAN_DOC),
                  given.get("issue_doc", ISSUE_DOC))


def layout_for_root(root: Path | None) -> Layout:
    """`root is None`（仓库外）→ 全默认，不读盘、不报错。"""
    return DEFAULT_LAYOUT if root is None else load_layout(root)


def resolve_paths(args: argparse.Namespace) -> tuple[Path, Path]:
    """返回 (json 真源路径, markdown 视图路径)。"""
    if getattr(args, "path", None):
        p = Path(args.path).expanduser()
        if p.is_dir():
            # 容错：把 campaign 目录当 --path 传入时自动补栈文件名，
            # 避免抛 IsADirectoryError traceback（人和模型都会自然这么传）。
            print(f"[提示] --path 是目录，已解析为 {p / STACK_FILE_NAME}", file=sys.stderr)
            p = p / STACK_FILE_NAME
        return p, p.with_suffix(".md")
    campaign = getattr(args, "campaign", None)
    if not campaign:
        die(2, "必须提供 --campaign <id> 或 --path <json 路径>")
    root = find_repo_root(_start_from_args(args))
    d = root / layout_for_root(root).workstack_root / campaign
    jp = d / STACK_FILE_NAME
    if not jp.exists():
        _refuse_legacy_fork(jp, campaign, root)
    return jp, d / VIEW_FILE_NAME


def _repo_root_or_none(start: Path) -> Path | None:
    """同 `_markers_root`（共用唯一真源，不各写一份）；找不到返回 None。

    `--path` 指到仓库外时不应致命 —— 台账回退查找、近似提示、指针读取都靠这个降级出口。
    """
    return _markers_root(start)


def _ledger_rel(json_path: Path) -> str | None:
    """总目标台账的仓库根相对路径；台账不存在则 None。

    查找顺序：① 栈同目录的 `goal-ledger.md`；② v4 起栈住 `workstacks/<campaign>/`
    而台账可能仍在旧的 `scratch/workbench/<campaign>/`，故按**同名 campaign** 回退查找。
    台账缺失不是错误（临时栈、或台账尚未落盘），但 `verify` 会如实报软警告，不假装绑过。
    """
    ledger = json_path.parent / LEDGER_FILE_NAME
    if not ledger.exists():
        root0 = _repo_root_or_none(json_path.parent)
        if root0 is not None:
            alt = (root0 / LEGACY_WORKBENCH[0] / LEGACY_WORKBENCH[1]
                   / json_path.parent.name / LEDGER_FILE_NAME)
            if alt.exists():
                ledger = alt
    if not ledger.exists():
        return None
    root = _repo_root_or_none(json_path.parent)
    if root is None:
        return str(ledger)
    try:
        return str(ledger.relative_to(root))
    except ValueError:
        return str(ledger)


def _pointer_path(root: Path, layout: Layout) -> Path:
    return root / layout.workstack_root / POINTER_FILE_NAME


def _read_pointer(pp: Path) -> dict | None:
    """读单栈指针；缺失或损坏一律当「没有指针」，不抛栈trace —— 指针是便利，不是真源。"""
    if not pp.exists():
        return None
    try:
        d = json.loads(pp.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return d if isinstance(d, dict) else None


def _write_pointer(pp: Path, data: dict) -> None:
    pp.parent.mkdir(parents=True, exist_ok=True)
    tmp = pp.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, pp)


def stack_status(data: dict) -> str:
    """派生栈的终态：全部帧终态即 `closed`，否则 `open`。

    **刻意不存 status 字段** —— 存了就多一个可能与 frames 不一致、需要额外不变量去校验的标志位；
    派生值永远与真源一致。
    """
    return "open" if open_frames(data) else "closed"


def _resolve_ledger_path(json_path: Path, data: dict | None = None) -> Path | None:
    """定位总目标台账的绝对路径，供 `check_invariants` 校验绑定。

    查找顺序：① 栈同目录；② `bound_ledger`（仓库根相对）；③ 旧 `scratch/workbench/<同名 campaign>/`。
    v4 起栈与台账可以不同目录，若仍按「同目录」硬推导，搬迁会把「绑定自洽」误判成「绑定已断」硬违规。
    三处都找不到时：`bound_ledger` 有值就返回那条（并不存在的）路径，让 `verify` 如实报
    「指向 X 但文件不存在：绑定已断」，而不是降级成「未绑定」软警告 —— fail-closed，不假装绑过。
    """
    root = _repo_root_or_none(json_path.parent)
    bound = (data or {}).get("bound_ledger")
    same_dir = json_path.parent / LEDGER_FILE_NAME
    if same_dir.exists():
        return same_dir
    if bound and root is not None and (root / bound).exists():
        return root / bound
    if root is not None:
        legacy = (root / LEGACY_WORKBENCH[0] / LEGACY_WORKBENCH[1]
                  / json_path.parent.name / LEDGER_FILE_NAME)
        if legacy.exists():
            return legacy
    return (root / bound) if (bound and root is not None) else None


_LEDGER_CID_RE = re.compile(r"campaign_id[^\w`]*[`\']?([A-Za-z0-9_.\-]+)")


def _read_ledger_campaign_id(path: Path) -> str | None:
    """从台账正文解析 `campaign_id`；解析不到返回 None（调用方必须如实声明未校验）。"""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    m = _LEDGER_CID_RE.search(text)
    return m.group(1) if m else None


def new_stack(campaign: str, *, bound_ledger: str | None = None,
              activation: str = "user_declared") -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "campaign_id": campaign,
        "bound_ledger": bound_ledger,
        "activation": activation,
        "updated_at": now(),
        "frames": [],
        "captures": [],
        "pop_log": [],
        "event_log": [],
    }


def _log(data: dict, kind: str, **fields) -> dict:
    """追加一条事件到 event_log。seq 自增，只追加不改写。"""
    assert kind in EVENT_KINDS, f"非法事件种类：{kind}"
    log = data.setdefault("event_log", [])
    ev = {"seq": (log[-1]["seq"] + 1) if log else 1, "at": now(), "kind": kind}
    ev.update({k: v for k, v in fields.items() if v is not None})
    log.append(ev)
    return ev


def migrate_v1_to_v2(data: dict) -> dict:
    """v1 栈升级 v2：从 frames.created_at / pop_log / captures.at 回填事件。

    回填不到的历史（activate / resolve 等）无法重建，留空；
    `migrated_from` 标记会让 retro 主动声明「v1 时期事件不完整」，
    不假装拥有并不存在的历史。
    """
    events: list[dict] = []
    for f in data.get("frames", []):
        if f.get("created_at"):
            events.append({"at": f["created_at"], "kind": "pushed",
                           "frame_id": f["frame_id"], "detail": "（v1 回填）"})
    for e in data.get("pop_log", []):
        if e.get("at"):
            events.append({"at": e["at"], "kind": "popped", "frame_id": e["frame_id"],
                           "terminal": e.get("terminal"), "detail": "（v1 回填）"})
    for c in data.get("captures", []):
        if c.get("at"):
            events.append({"at": c["at"], "kind": "captured",
                           "capture_id": c["capture_id"],
                           "disposition": c.get("disposition"), "detail": "（v1 回填）"})
    events.sort(key=lambda x: x["at"])
    for i, ev in enumerate(events, 1):
        ev["seq"] = i
    data["event_log"] = events
    data["schema_version"] = PREV_SCHEMA_VERSION
    data["migrated_from"] = V1_SCHEMA_VERSION
    return data


def migrate_v2_to_v3(data: dict) -> dict:
    """v2 → v3：补 `bound_ledger` / `activation` 两个绑定字段。

    **不伪造历史**：v2 时期没有记录栈是被谁启用的，迁移后一律记 `pre-v3-unknown`，
    而不是猜一个 `auto_orchestration` 填上去 —— 猜出来的绑定在复盘时比没有绑定更坏。
    `bound_ledger` 由 `ensure` 在台账真实存在时补；缺失就留 None，`verify` 报软警告。
    """
    data.setdefault("bound_ledger", None)
    data.setdefault("activation", "pre-v3-unknown")
    data["schema_version"] = SCHEMA_VERSION
    data.setdefault("migrated_from", PREV_SCHEMA_VERSION)
    return data


_CRIT_PREFIX_RE = re.compile(r"^判据\s*\d+\s*[:：]\s*")


def _crit_strip(c: str) -> str:
    """剥掉条目自带的「判据N:」前缀，避免渲染时出现「判据1: 判据1: …」。"""
    return _CRIT_PREFIX_RE.sub("", c)


def _crit_label(n: int, c: str) -> str:
    return f"判据{n}: {_crit_strip(c)}"


def load(json_path: Path, *, allow_missing: bool = False) -> dict:
    if json_path.is_dir():
        die(
            2,
            f"--path 指向目录而不是栈文件：{json_path}\n"
            f"请指到 {json_path / STACK_FILE_NAME}",
        )
    if not json_path.exists():
        if allow_missing:
            return new_stack(json_path.parent.name, bound_ledger=_ledger_rel(json_path))
        die(2, f"栈文件不存在：{json_path}\n先运行 `stack.py ensure …` 启用（编排模式自动调用），"
               "或 `stack.py push …` 直接压第一帧")
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        die(2, f"栈文件损坏（不是合法 JSON）：{json_path}\n{exc}")
    sv = data.get("schema_version")
    if sv == V1_SCHEMA_VERSION:
        data = migrate_v1_to_v2(data)
        sv = data["schema_version"]
    if sv == PREV_SCHEMA_VERSION:
        data = migrate_v2_to_v3(data)
        sv = data["schema_version"]
    if sv != SCHEMA_VERSION:
        die(2, f"schema_version 不符：期望 {SCHEMA_VERSION}"
               f"（可由 {V1_SCHEMA_VERSION} / {PREV_SCHEMA_VERSION} 自动链式迁移），实际 {sv!r}")
    for key in ("frames", "captures", "pop_log", "event_log"):
        if not isinstance(data.get(key), list):
            die(2, f"栈文件缺少合法的 {key!r} 数组：{json_path}")
    # v4：核心任务名。老栈没有这个字段，回退用 campaign_id 顶上（不猜更好听的名字）
    data.setdefault("title", data.get("campaign_id"))
    return data


def save(json_path: Path, data: dict) -> None:
    data["updated_at"] = now()
    json_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = json_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, json_path)


def next_id(items: list[dict], prefix: str, key: str) -> str:
    used = {it.get(key, "") for it in items}
    n = len(items) + 1
    while f"{prefix}-{n:03d}" in used:
        n += 1
    return f"{prefix}-{n:03d}"


def find_frame(data: dict, frame_id: str) -> dict:
    for f in data["frames"]:
        if f["frame_id"] == frame_id:
            return f
    die(2, f"frame_id 不存在：{frame_id}（现有：{[f['frame_id'] for f in data['frames']] or '空栈'}）")


def find_capture(data: dict, cap_id: str) -> dict:
    for c in data["captures"]:
        if c["capture_id"] == cap_id:
            return c
    die(2, f"capture_id 不存在：{cap_id}")


def open_frames(data: dict) -> list[dict]:
    return [f for f in data["frames"] if f["status"] in OPEN_STATUS]


def active_frame(data: dict) -> dict | None:
    act = [f for f in data["frames"] if f["status"] == "active"]
    return act[0] if act else None


# ---------------------------------------------------------------- 不变量


def check_invariants(data: dict, *, ledger_path: Path | None = None) -> tuple[list[str], list[str]]:
    """返回 (硬违规, 软警告)。硬违规非空 = 队列不可信，必须处理。"""
    v: list[str] = []
    w: list[str] = []
    frames = data["frames"]
    by_id = {f["frame_id"]: f for f in frames}

    if len(by_id) != len(frames):
        v.append("frame_id 存在重复")

    # 1) 未关闭帧中最多一个 active（空栈允许 0 个）
    act = [f for f in frames if f["status"] == "active"]
    opens = open_frames(data)
    if len(act) > 1:
        v.append(f"同时有 {len(act)} 个 active 帧：{[f['frame_id'] for f in act]}（只能有一个栈顶）")

    # 2) suspended 必须由「子帧抢占」产生，因此必须是 active 帧的祖先
    if act:
        anc, cur = set(), act[0]
        while cur.get("parent"):
            anc.add(cur["parent"])
            cur = by_id.get(cur["parent"])
            if cur is None:
                break
        for f in frames:
            if f["status"] == "suspended" and f["frame_id"] not in anc:
                v.append(f"{f['frame_id']} 处于 suspended，却不是 active 帧的祖先（挂起状态来路不明）")
    else:
        for f in frames:
            if f["status"] == "suspended":
                v.append(f"{f['frame_id']} 处于 suspended，但栈里没有 active 帧可以恢复它")

    # 3) 深度上限
    for f in opens:
        if f["depth"] >= MAX_DEPTH:
            v.append(f"{f['frame_id']} 深度 {f['depth']} 已达上限 {MAX_DEPTH}：当前帧定义太粗，应拆分或 parked")

    # 4) parent / spawned 指针必须存在，且 depth 自洽
    for f in frames:
        if f.get("parent"):
            if f["parent"] not in by_id:
                v.append(f"{f['frame_id']} 的 parent {f['parent']} 不存在")
            elif by_id[f["parent"]]["depth"] + 1 != f["depth"]:
                v.append(f"{f['frame_id']} depth={f['depth']} 与父帧 depth={by_id[f['parent']]['depth']} 不自洽")
        elif f["depth"] != 0:
            v.append(f"{f['frame_id']} 无父帧但 depth={f['depth']}（应为 0）")
        for sp in f.get("spawned", []):
            if sp not in by_id:
                v.append(f"{f['frame_id']} 的 spawned {sp} 不存在")

    # 5) 终态必须带 close_note 与 closed_at，且在 pop_log 有记录 —— queued 帧不得静默消失
    logged = {e["frame_id"] for e in data["pop_log"]}
    for f in frames:
        if f["status"] in TERMINAL_STATUS:
            if not f.get("close_note"):
                v.append(f"{f['frame_id']} 已终结为 {f['status']} 但没有 close_note（等于静默消失）")
            if not f.get("closed_at"):
                v.append(f"{f['frame_id']} 已终结但缺 closed_at")
            if f["frame_id"] not in logged:
                v.append(f"{f['frame_id']} 已终结但 pop_log 无记录")
        elif f.get("closed_at"):
            v.append(f"{f['frame_id']} 状态为 {f['status']} 却有 closed_at")

    # 6) 未处置的衍生登记 = 硬违规（防遗忘的核心断言）
    for c in data["captures"]:
        if c["disposition"] == "pending":
            v.append(f"衍生登记 {c['capture_id']} 仍未处置（pending）：{c['text'][:60]}")
        elif c["disposition"] in ("blocks", "spawns") and not c.get("frame_id") and not c.get("pointer"):
            v.append(f"衍生登记 {c['capture_id']} 判为 {c['disposition']} 却没有 frame_id 或 pointer")

    # 7) 取值合法性
    for f in frames:
        if f["status"] not in ALL_STATUS:
            v.append(f"{f['frame_id']} 状态非法：{f['status']!r}")
        if not f.get("criteria"):
            w.append(f"{f['frame_id']} 没有完成判据：收工时无法客观自检")
    for c in data["captures"]:
        if c["disposition"] not in DISPOSITIONS:
            v.append(f"{c['capture_id']} disposition 非法：{c['disposition']!r}")

    # 8) event_log 完整性（复盘真源；只追加，不允许改写）
    ev = data.get("event_log")
    migrated = data.get("migrated_from")
    if not isinstance(ev, list):
        v.append(f"缺少合法的 event_log 数组（{SCHEMA_VERSION} 必需；"
                 f"{PREV_SCHEMA_VERSION} 栈会在 load 时自动迁移）")
    else:
        seqs = [e.get("seq") for e in ev]
        if len(set(seqs)) != len(seqs):
            v.append("event_log 存在重复 seq")
        if seqs != sorted(seqs):
            v.append("event_log 的 seq 非递增：事件日志只允许追加，不允许插入或改写")
        # 缺号 = 有人删过事件。只查递增查不出删除，故强制 1..N 连续。
        if seqs and seqs != list(range(1, len(seqs) + 1)):
            missing = sorted(set(range(1, len(seqs) + 1)) ^ set(seqs))[:5]
            v.append(f"event_log 的 seq 不是连续的 1..{len(seqs)}（异常 seq：{missing}）："
                     "事件日志只允许追加，缺号说明历史被删改")
        for e in ev:
            if e.get("kind") not in EVENT_KINDS:
                v.append(f"event_log seq={e.get('seq')} 种类非法：{e.get('kind')!r}")
            if e.get("actor") is not None and e["actor"] not in ACTORS:
                v.append(f"event_log seq={e.get('seq')} actor 非法：{e['actor']!r}")
        if migrated:
            w.append(f"本栈由 {migrated} 迁移而来：activate/resolve 历史无法回填，"
                     "retro 的「用户方向切换」计数只覆盖迁移点之后")
        else:
            pushed = {e.get("frame_id") for e in ev if e.get("kind") == "pushed"}
            popped = {e.get("frame_id") for e in ev if e.get("kind") == "popped"}
            capped = {e.get("capture_id") for e in ev if e.get("kind") == "captured"}
            for f in frames:
                if f["frame_id"] not in pushed:
                    w.append(f"{f['frame_id']} 无 pushed 事件")
                if f["status"] in TERMINAL_STATUS and f["frame_id"] not in popped:
                    w.append(f"{f['frame_id']} 已终结却无 popped 事件")
            for c in data["captures"]:
                if c["capture_id"] not in capped:
                    w.append(f"{c['capture_id']} 无 captured 事件")

    # 9) 绑定：栈必须绑到总目标台账，且台账 campaign_id 与栈一致
    activation = data.get("activation")
    if activation not in ACTIVATIONS:
        v.append(f"activation 非法：{activation!r}（应为 {ACTIVATIONS} 之一）")
    elif activation in LEGACY_ACTIVATIONS:
        w.append(f"activation={activation!r} 是 legacy 值：v4 起栈的启用一律经用户"
                 "（`user_declared` 主动声明 / `user_approved_on_proposal` 批准申请）。"
                 "不改写历史，但新栈不得再用这个值")
    if not str(data.get("title") or "").strip():
        w.append("title（核心任务名）为空：router 的语义恢复要靠它匹配当前对话，"
                 "缺了就只能拿 campaign_id 猜。用 `retitle --title <核心任务名>` 补")
    bound = data.get("bound_ledger")
    if not bound:
        w.append("bound_ledger 为空：本栈未绑定总目标台账（仓库外的临时栈可接受；"
                 "若属某个 campaign，运行 `ensure` 补绑，否则跨窗口交接时无从证明栈属于哪个总目标）")
    elif ledger_path is None or not ledger_path.exists():
        v.append(f"bound_ledger 指向 {bound}，但该文件不存在：栈与总目标台账的绑定已断")
    else:
        cid = _read_ledger_campaign_id(ledger_path)
        if cid is None:
            w.append(f"无法从 {bound} 解析 campaign_id，绑定一致性**未校验**（不假装校验过）")
        elif cid != data.get("campaign_id"):
            v.append(f"绑定不一致：台账 campaign_id={cid!r} 而栈 campaign_id={data.get('campaign_id')!r}"
                     "（栈绑的是总目标，两者必须是同一个 campaign）")

    # 软警告：有未关闭帧却没有栈顶 —— 合法（等用户选），但必须显式化
    if opens and not act:
        w.append(f"栈里有 {len(opens)} 个未关闭帧却没有 active 栈顶："
                 f"{[f['frame_id'] for f in opens]}（等用户选下一个，别让它悬着）")

    return v, w


# ---------------------------------------------------------------- 渲染


def _tree_order(data: dict) -> list[dict]:
    """按父帧就近排列，使同深度缩进后读起来是一棵树；保持压栈先后。"""
    frames = data["frames"]
    by_parent: dict[object, list[dict]] = {}
    for f in frames:
        by_parent.setdefault(f.get("parent"), []).append(f)
    out: list[dict] = []

    def walk(parent: object) -> None:
        for f in by_parent.get(parent, []):
            out.append(f)
            walk(f["frame_id"])

    walk(None)
    # 兜底：父指针缺失导致未被遍历到的帧也要显示，绝不静默丢帧
    seen = {f["frame_id"] for f in out}
    out.extend(f for f in frames if f["frame_id"] not in seen)
    return out


# 树形图里的状态记号。CJK 在终端占两列，对齐一律用 _dwidth 而不是 len。
TREE_MARK = {
    "active": "● 正在做",
    "suspended": "◐ 被打断",
    "queued": "○ 待办",
    "done": "✓ done",
    "parked": "⏸ parked",
    "escalated": "↑ escalated",
    "wontfix": "✗ wontfix",
}
TREE_LEGEND = ("图例：● 正在做　◐ 被打断（子帧关闭后自动恢复）　○ 待办　"
               "✓ done　⏸ parked　↑ escalated　✗ wontfix")


def _dwidth(s: str) -> int:
    """终端显示宽度：东亚全角字符按 2 列算，否则树形对齐会歪。"""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def _children_map(data: dict) -> dict:
    """parent_id -> [子帧]。父指针指向不存在的帧时一律挂到根，绝不静默丢帧。"""
    known = {f["frame_id"] for f in data["frames"]}
    m: dict = {}
    for f in data["frames"]:
        p = f.get("parent")
        m.setdefault(p if p in known else None, []).append(f)
    return m


def render_tree_lines(data: dict, *, include_closed: bool = True,
                      label_width: int = 24) -> list[str]:
    """渲染成真树形（├─ └─ │ 分支符），并在当前 active 帧后标出「◀ 当前位置」。"""
    if not data["frames"]:
        return ["（栈是空的：本 campaign 还没有登记任何待办）"]
    kids = _children_map(data)
    act = active_frame(data)
    act_id = act["frame_id"] if act else None
    out: list[str] = []

    def walk(parent: object, prefix: str) -> None:
        children = kids.get(parent, [])
        if not include_closed:
            children = [c for c in children if c["status"] in OPEN_STATUS]
        for i, f in enumerate(children):
            last = i == len(children) - 1
            label = f"[{f['frame_id']}] {TREE_MARK.get(f['status'], f['status'])}"
            pad = " " * max(1, label_width - _dwidth(label))
            here = "　◀━━ 当前位置" if f["frame_id"] == act_id else ""
            out.append(f"{prefix}{'└─ ' if last else '├─ '}{label}{pad}{f['title']}{here}")
            walk(f["frame_id"], prefix + ("   " if last else "│  "))

    walk(None, "")
    return out


def render_position(data: dict) -> list[str]:
    """位置指针：当前在哪一帧、从哪个根帧一路推进过来、关掉后会回到谁。"""
    act = active_frame(data)
    if not act:
        opens = open_frames(data)
        ids = ", ".join(f["frame_id"] for f in opens) or "（无）"
        return ["当前位置：（无 active 栈顶 —— 需要选下一个）",
                f"待选帧：{ids}"]
    chain: list[dict] = []
    cur: object = act
    seen: set = set()
    while isinstance(cur, dict) and cur["frame_id"] not in seen:
        seen.add(cur["frame_id"])
        chain.append(cur)
        pid = cur.get("parent")
        cur = find_frame(data, pid) if pid else None
    chain.reverse()
    lines = [
        f"当前位置：{act['frame_id']} · {act['title']}（depth {act['depth']}）",
        "推进路径：" + " ▸ ".join(f"{f['frame_id']} {f['title']}" for f in chain),
    ]
    suspended = [f for f in chain[:-1] if f["status"] == "suspended"]
    if suspended:
        a = suspended[-1]
        lines.append(f"会自动恢复：{a['frame_id']} · {a['title']}"
                     f"（当前帧关闭后回到它，不用你记）")
    return lines


def render_progress(data: dict) -> str:
    """进度计数：关闭比例、未关闭数、当前深度与栈深上限。"""
    frames = data["frames"]
    closed = [f for f in frames if f["status"] in TERMINAL_STATUS]
    opens = open_frames(data)
    act = active_frame(data)
    total = len(frames)
    pct = round(100 * len(closed) / total) if total else 0
    depth = act["depth"] if act else "—"
    return (f"进度：已关闭 {len(closed)}/{total} 帧（{pct}%）｜未关闭 {len(opens)}"
            f"｜当前 depth {depth}｜栈深上限 {MAX_DEPTH}")


def _flag(f: dict) -> str:
    return {"active": "　← 正在做", "suspended": "　← 被子帧打断", "queued": ""}.get(f["status"], "")


def render_table(data: dict) -> str:
    """把全部帧渲染成缩进树：一眼看出「在做什么、被打断的有什么、还剩什么」。"""
    if not data["frames"]:
        return "_（栈是空的：本 campaign 还没有登记任何待办）_"
    lines = [
        "| frame_id | 标题 | 状态 | 完成判据 | 来源 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for f in _tree_order(data):
        indent = "&nbsp;&nbsp;&nbsp;&nbsp;" * f["depth"]
        mark = {"active": "**→ 正在做**", "suspended": "被打断", "queued": "待办"}.get(
            f["status"], f"已关闭({f['status']})")
        crit = "<br>".join(f"{n}. {_crit_strip(c)}"
                       for n, c in enumerate(f.get("criteria") or ["—"], 1))
        title = f"{indent}{indent and '└ ' or ''}{f['title']}"
        lines.append(f"| `{f['frame_id']}` d{f['depth']} | {title} | {mark} | {crit} | {f.get('origin') or '—'} |")
    return "\n".join(lines)


def render_open_list(data: dict) -> str:
    """只列未关闭帧，供 pop 的「栈剩余」段落使用。"""
    opens = open_frames(data)
    if not opens:
        return "（栈已空：没有未关闭的待办帧）"
    return "\n".join(
        f"{'  ' * f['depth']}- `{f['frame_id']}` d{f['depth']} **{f['status']}**{_flag(f)}：{f['title']}"
        for f in _tree_order(data) if f["status"] in OPEN_STATUS
    )


def render_closed(data: dict) -> str:
    closed = [f for f in data["frames"] if f["status"] in TERMINAL_STATUS]
    if not closed:
        return "_（尚无已关闭帧）_"
    lines = ["| frame_id | 终态 | 标题 | 关闭时间 | 结论 | 衍生 |", "| --- | --- | --- | --- | --- | --- |"]
    for f in closed:
        lines.append(
            f"| `{f['frame_id']}` | {f['status']} | {f['title']} | {f.get('closed_at') or '—'} | "
            f"{(f.get('close_note') or '—').replace(chr(10), ' ')} | {', '.join(f.get('spawned') or []) or '—'} |"
        )
    return "\n".join(lines)


def render_captures(data: dict) -> str:
    if not data["captures"]:
        return "_（无衍生登记）_"
    lines = [
        "| capture_id | 发现于 | disposition | 去向 | 内容 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for c in data["captures"]:
        dest = c.get("frame_id") or c.get("pointer") or "**未处置**"
        lines.append(
            f"| `{c['capture_id']}` | {c.get('found_in') or '—'} | {c['disposition']} | {dest} | {c['text']} |"
        )
    return "\n".join(lines)


def render_markdown(data: dict) -> str:
    opens = open_frames(data)
    act = active_frame(data)
    tree_text = "\n".join(render_tree_lines(data))
    position_text = "\n".join(render_position(data))
    progress_text = render_progress(data)
    return f"""# 推进栈 · {data['campaign_id']}

> **本文件由 `work-queue-stack/scripts/stack.py render` 生成，请勿手改。**
> 真源是同目录的 `active-work-stack.json`；两者不一致时 `render --check` 会失败。

- schema：`{data['schema_version']}`
- 绑定总目标台账：{('`' + data['bound_ledger'] + '`') if data.get('bound_ledger') else '**（未绑定）**'}
- 启用方式：`{data.get('activation')}`（auto_orchestration=受控/多阶段自动启用 · user_declared=用户显式声明 · pre-v3-unknown=v3 前创建、无从考证）
- 更新时间：{data['updated_at']}
- 未关闭帧：**{len(opens)}**（active {len([f for f in opens if f['status'] == 'active'])} / \
queued {len([f for f in opens if f['status'] == 'queued'])} / \
suspended {len([f for f in opens if f['status'] == 'suspended'])}）
- 已关闭帧：{len([f for f in data['frames'] if f['status'] in TERMINAL_STATUS])}
- 衍生登记：{len(data['captures'])}（未处置 \
{len([c for c in data['captures'] if c['disposition'] == 'pending'])}）
- 当前栈顶：{('`' + act['frame_id'] + '` ' + act['title']) if act else '（无）'}
- 事件日志：{len(data.get('event_log') or [])} 条（`retro` 可复盘弯路）

## 推进树（分支 = 父子关系；◀ 标出当前推进到哪一帧）

```text
{TREE_LEGEND}

{tree_text}
```

**位置指针**

```text
{position_text}
```

{progress_text}

## 全部帧明细（判据 / 来源 / 指针）

{render_table(data)}

## 衍生登记（发现即登记，登记后才决定）

{render_captures(data)}

## 已关闭帧（回看记录）

{render_closed(data)}

## 出栈日志

{chr(10).join('- ' + e['at'] + ' · `' + e['frame_id'] + '` → **' + e['terminal'] + '** · 剩余 '
              + (', '.join('`' + r + '`' for r in e['remaining']) or '空') + ' · ' + e['note']
              for e in data['pop_log']) or '_（无）_'}
"""


def print_show(data: dict) -> None:
    opens = open_frames(data)
    act = active_frame(data)
    closed = [f for f in data["frames"] if f["status"] in TERMINAL_STATUS]
    pend = [c for c in data["captures"] if c["disposition"] == "pending"]
    print(f"推进栈 · {data['campaign_id']}　更新时间 {data['updated_at']}")
    print(f"未关闭 {len(opens)} 帧"
          f"（active {len([f for f in opens if f['status'] == 'active'])}"
          f" / queued {len([f for f in opens if f['status'] == 'queued'])}"
          f" / suspended {len([f for f in opens if f['status'] == 'suspended'])}）"
          f"；已关闭 {len(closed)}；衍生登记 {len(data['captures'])}（未处置 {len(pend)}）")
    print(f"当前栈顶：{(act['frame_id'] + ' ' + act['title']) if act else '（无 —— 需要选下一个）'}")
    print()
    if not data["frames"]:
        print("（栈是空的：本 campaign 还没有登记任何待办）")
        return
    print(TREE_LEGEND)
    print()
    for line in render_tree_lines(data):
        print(line)
    print()
    for line in render_position(data):
        print(line)
    print(render_progress(data))
    print()
    print("── 未关闭帧明细 ──")
    for f in _tree_order(data):
        if f["status"] in TERMINAL_STATUS:
            continue
        indent = "    " * f["depth"]
        print(f"{indent}[{f['frame_id']}] d{f['depth']} {f['status']:9} {f['title']}{_flag(f)}")
        for n, c in enumerate(f.get("criteria") or [], 1):
            print(f"{indent}          {_crit_label(n, c)}")
        if f.get("origin"):
            print(f"{indent}          来源: {f['origin']}")
        if f.get("pointers"):
            print(f"{indent}          指针: {json.dumps(f['pointers'], ensure_ascii=False)}")
    if closed:
        print(f"\n已关闭 {len(closed)} 帧：" + ", ".join(f"{f['frame_id']}({f['status']})" for f in closed))
    if pend:
        print(f"\n⚠ 有 {len(pend)} 条衍生登记未处置（verify 会判硬违规）：")
        for c in pend:
            print(f"   - [{c['capture_id']}] {c['text']}")


# ---------------------------------------------------------------- 命令


def _existing_campaign_ids(json_path: Path) -> list[str]:
    """已存在的 campaign 目录名（有栈文件或台账者）。仅用于拼错时给提示。

    同时扫 `workstacks/`（v4 新位置）与 `scratch/workbench/`（旧位置，未 migrate 的栈与台账可能还在那里），
    否则迁移后近似提示会失灵 —— 而近似提示正是防栈分叉的那道防线。
    """
    root = _repo_root_or_none(json_path.parent)
    bases = ([root / layout_for_root(root).workstack_root,
              root / LEGACY_WORKBENCH[0] / LEGACY_WORKBENCH[1]]
             if root else [json_path.parent.parent])
    ids: set[str] = set()
    for b in bases:
        if b.is_dir():
            for d in b.iterdir():
                if d.is_dir() and ((d / STACK_FILE_NAME).exists()
                                   or (d / LEDGER_FILE_NAME).exists()):
                    ids.add(d.name)
    return sorted(ids)


def _die_no_stack(json_path: Path) -> None:
    """栈不存在时**拒绝静默新建** —— 创建栈只有一个门：`ensure`。

    静默新建的后果是**栈分叉**：`--campaign` 打错一个字母就会在另一个目录建出一个空栈，
    帧压进空栈、真栈一帧未动，而 `verify` 对那个新栈照样 PASS，没人会发现。
    v2 时期 `push` 就是这样建栈的（实测 `ui-image-system-recogntion` 少一个 `i` 即分叉）。
    """
    wanted = json_path.parent.name
    ids = _existing_campaign_ids(json_path)
    close = difflib.get_close_matches(wanted, ids, n=3, cutoff=0.6)
    if close:
        hint = "\n你是不是想找：" + "、".join(f"`{c}`" for c in close) + "？"
    elif ids:
        hint = "\n现有 campaign：" + "、".join(f"`{i}`" for i in ids[:8])
    else:
        hint = ""
    die(2, f"栈不存在：{json_path}\n"
           "`push` 不再静默新建栈（打错 `--campaign` 会造成栈分叉：帧进了空栈、真栈没动、verify 还 PASS）。\n"
           f"要启用一个新栈请**显式**运行：`stack.py ensure --campaign {wanted} --activation user_declared`{hint}")


def cmd_push(args: argparse.Namespace) -> int:
    jp, mp = resolve_paths(args)
    if not jp.exists():
        _die_no_stack(jp)
    data = load(jp)
    if args.campaign and data.get("campaign_id") not in (None, args.campaign):
        data["campaign_id"] = args.campaign

    parent = None
    depth = 0
    if args.parent:
        parent = find_frame(data, args.parent)
        depth = parent["depth"] + 1
        if depth >= MAX_DEPTH:
            die(2, f"压栈后深度 {depth} 达上限 {MAX_DEPTH}：请把 {parent['frame_id']} 拆分或先 parked")

    cur = active_frame(data)
    activate = args.activate or (cur is None)
    if activate and cur is not None:
        # 强制 DFS：只有当前栈顶的直接子帧才允许抢占为 active
        if args.parent != cur["frame_id"]:
            die(2, f"已有 active 帧 {cur['frame_id']}；要抢占为栈顶，新帧必须是它的直接子帧"
                   f"（--parent {cur['frame_id']}），否则请用默认 queued")
        cur["status"] = "suspended"
        cur["suspended_reason"] = f"子帧接管（{now()}）"
        _log(data, "suspended", frame_id=cur["frame_id"], actor="dfs",
             detail="被新压入的子帧抢占")

    frame = {
        "frame_id": next_id(data["frames"], "F", "frame_id"),
        "depth": depth,
        "parent": args.parent,
        "title": args.title,
        "status": "active" if activate else "queued",
        "goal": args.goal or "",
        "criteria": list(args.criteria or []),
        "origin": args.origin or "",
        "pointers": json.loads(args.pointers) if args.pointers else {},
        "spawned": [],
        "created_at": now(),
        "closed_at": None,
        "close_note": None,
    }
    data["frames"].append(frame)
    _log(data, "pushed", frame_id=frame["frame_id"], parent=args.parent,
         detail=frame["title"])
    if activate:
        # --activate 只允许压入当前栈顶的直接子帧（上面已强制），属计划内深入 → actor=dfs。
        # 记成 user 会让 retro 把「按树往下钻」误报成「用户改道」，污染最重要的复盘信号。
        _log(data, "activated", frame_id=frame["frame_id"],
             actor="dfs" if args.activate else "auto",
             detail="压栈时 --activate 抢占（父帧直接子帧，计划内深入）" if args.activate
                    else "栈无 active 帧，自动成为栈顶")
    if parent is not None:
        parent.setdefault("spawned", []).append(frame["frame_id"])
    save(jp, data)
    render_view(jp, mp, data)
    print(f"[OK] 压栈 {frame['frame_id']}（depth {depth}，{frame['status']}）：{frame['title']}")
    if not activate:
        print(f"     当前栈顶仍是 {cur['frame_id']}；本帧挂起为 queued —— 挂起不是丢弃。")
    print()
    print_show(data)
    return 0


def cmd_activate(args: argparse.Namespace) -> int:
    """把某个未关闭帧设为栈顶。两种情形语义不同，必须区分：

    - 目标是当前栈顶的**后代** → 当前栈顶转 `suspended`（被子帧打断，pop 子帧后自动恢复）
    - 目标与当前栈顶**无祖先关系** → 当前栈顶退回 `queued`（用户驱动的上下文切换，
      不会被自动恢复，必须之后重新选中，因此显式打印提醒，避免切换后把它忘了）
    """
    jp, mp = resolve_paths(args)
    data = load(jp)
    target = find_frame(data, args.frame)
    if target["status"] in TERMINAL_STATUS:
        die(2, f"{args.frame} 已是终态 {target['status']}，不能再激活")
    if target["status"] == "active":
        print(f"[OK] {args.frame} 已经是栈顶，无需切换")
        return 0

    by_id = {f["frame_id"]: f for f in data["frames"]}
    cur = active_frame(data)

    def ancestors(fid: str) -> set[str]:
        out, node = set(), by_id.get(fid)
        while node and node.get("parent"):
            out.add(node["parent"])
            node = by_id.get(node["parent"])
        return out

    actor = "user"
    if cur is not None:
        if cur["frame_id"] in ancestors(target["frame_id"]):
            actor = "dfs"
            cur["status"] = "suspended"
            cur["suspended_reason"] = f"子帧 {target['frame_id']} 接管（{now()}）"
            _log(data, "suspended", frame_id=cur["frame_id"], actor="dfs",
                 detail=f"被后代帧 {target['frame_id']} 抢占")
            print(f"[OK] {cur['frame_id']} 转 suspended（被 {target['frame_id']} 打断；"
                  f"关掉 {target['frame_id']} 后会自动恢复）")
        else:
            cur["status"] = "queued"
            _log(data, "requeued", frame_id=cur["frame_id"], actor="user",
                 detail=f"用户改道去 {target['frame_id']}；原栈顶退回 queued，不会自动恢复")
            print(f"⚠ 上下文切换：原栈顶 {cur['frame_id']}「{cur['title']}」退回 queued，"
                  f"**不会**被自动恢复。收工回看时会再次列出它，别让它就这样沉底。")
    target["status"] = "active"
    target.pop("suspended_reason", None)
    _log(data, "activated", frame_id=target["frame_id"], actor=actor,
         detail=target["title"])
    save(jp, data)
    render_view(jp, mp, data)
    print(f"[OK] 栈顶切换为 {target['frame_id']}：{target['title']}")
    print()
    print_show(data)
    return 0


def cmd_capture(args: argparse.Namespace) -> int:
    jp, mp = resolve_paths(args)
    data = load(jp)
    if args.found_in:
        find_frame(data, args.found_in)
    cap = {
        "capture_id": next_id(data["captures"], "C", "capture_id"),
        "at": now(),
        "text": args.text,
        "found_in": args.found_in,
        "disposition": args.disposition,
        "frame_id": args.frame,
        "pointer": args.pointer,
    }
    data["captures"].append(cap)
    _log(data, "captured", capture_id=cap["capture_id"], frame_id=args.found_in,
         disposition=cap["disposition"], detail=cap["text"][:80])
    save(jp, data)
    render_view(jp, mp, data)
    print(f"[OK] 已登记衍生 {cap['capture_id']}（disposition={cap['disposition']}）：{cap['text']}")
    hint = {
        "pending": "⚠ 尚未处置：verify 会判失败。请 push 成帧或 resolve 到某个指针。",
        "blocks": "→ 必须现在处理：请 `push --parent <当前栈顶> --activate` 建子帧，再 `resolve --frame`。",
        "spawns": "→ 真问题但不阻塞：请 `push`（默认 queued，不要当场展开），再 `resolve --frame`。",
        "note": "→ 非独立问题：请 `resolve --pointer <归属，如 ISS-007>` 写明去处。",
    }[cap["disposition"]]
    print(f"     {hint}")
    return 0


def cmd_resolve(args: argparse.Namespace) -> int:
    jp, mp = resolve_paths(args)
    data = load(jp)
    cap = find_capture(data, args.capture)
    cap["disposition"] = args.disposition
    if args.frame:
        find_frame(data, args.frame)
        cap["frame_id"] = args.frame
    if args.pointer:
        cap["pointer"] = args.pointer
    if cap["disposition"] in ("blocks", "spawns") and not cap.get("frame_id") and not cap.get("pointer"):
        die(2, f"{cap['capture_id']} 判为 {cap['disposition']} 时必须给 --frame 或 --pointer")
    _log(data, "resolved", capture_id=cap["capture_id"], disposition=cap["disposition"],
         frame_id=cap.get("frame_id"), pointer=cap.get("pointer"))
    save(jp, data)
    render_view(jp, mp, data)
    print(f"[OK] {cap['capture_id']} → disposition={cap['disposition']}"
          f" frame={cap.get('frame_id') or '—'} pointer={cap.get('pointer') or '—'}")
    return 0


def cmd_pop(args: argparse.Namespace) -> int:
    jp, mp = resolve_paths(args)
    data = load(jp)
    frame = find_frame(data, args.frame)
    if frame["status"] in TERMINAL_STATUS:
        die(2, f"{args.frame} 已是终态 {frame['status']}，不能重复 pop")
    if not args.note:
        die(2, "pop 必须给 --note：终态帧没有结论就等于静默消失")

    was_active = frame["status"] == "active"
    if was_active and not args.force:
        deeper = [f for f in open_frames(data) if f["depth"] > frame["depth"]
                  and f.get("parent") == frame["frame_id"]]
        if deeper:
            die(2, f"{args.frame} 还有未关闭的子帧 {[f['frame_id'] for f in deeper]}；"
                   "栈是后进先出，请先关掉子帧（或用 --force 明确越序）")

    frame["status"] = args.terminal
    frame["closed_at"] = now()
    frame["close_note"] = args.note
    if args.spawned:
        for s in args.spawned:
            find_frame(data, s)
            if s not in frame["spawned"]:
                frame["spawned"].append(s)
    if args.pointers:
        frame.setdefault("pointers", {}).update(json.loads(args.pointers))

    # 出栈后自动恢复最近的 suspended 祖先为栈顶
    resumed = None
    if was_active:
        for f in reversed(data["frames"]):
            if f["status"] == "suspended":
                f["status"] = "active"
                f.pop("suspended_reason", None)
                resumed = f
                break

    remaining = [f["frame_id"] for f in open_frames(data)]
    data["pop_log"].append({
        "at": now(), "frame_id": frame["frame_id"], "terminal": args.terminal,
        "note": args.note, "spawned": list(frame.get("spawned") or []),
        "remaining": remaining,
    })
    _log(data, "popped", frame_id=frame["frame_id"], terminal=args.terminal,
         detail=(args.note or "")[:80])
    if resumed:
        _log(data, "resumed", frame_id=resumed["frame_id"], actor="dfs",
             detail=f"{frame['frame_id']} 关闭后自动恢复栈顶")
    save(jp, data)
    render_view(jp, mp, data)

    # ---- 强制四段回看：由脚本打印，模型无法跳过 ----
    print("=" * 72)
    print(f"【1/4 本帧结论】{frame['frame_id']} · {frame['title']} → {args.terminal}")
    print(f"  结论：{args.note}")
    if frame.get("criteria"):
        print("  完成判据（逐条自检后在此确认）：")
        for n, c in enumerate(frame["criteria"], 1):
            print(f"    {_crit_label(n, c)}")
    if frame.get("pointers"):
        print(f"  指针：{json.dumps(frame['pointers'], ensure_ascii=False)}")

    print()
    mine = [c for c in data["captures"] if c.get("found_in") == frame["frame_id"]]
    print(f"【2/4 本帧衍生】共 {len(mine)} 条")
    if not mine:
        print("  （本帧期间没有登记任何衍生问题）")
    for c in mine:
        dest = c.get("frame_id") or c.get("pointer") or "**未处置**"
        print(f"  - [{c['capture_id']}] {c['disposition']:8} → {dest}：{c['text']}")
    if frame.get("spawned"):
        print(f"  子帧：{', '.join(frame['spawned'])}")

    print()
    print(f"【3/4 栈剩余】未关闭 {len(remaining)} 帧")
    print_show(data)

    print()
    print("【4/4 下一步】")
    if resumed:
        print(f"  已自动恢复栈顶：{resumed['frame_id']} · {resumed['title']}（它此前被子帧打断）")
    nxt = active_frame(data)
    if nxt:
        print(f"  建议继续：{nxt['frame_id']} · {nxt['title']}")
    elif remaining:
        print(f"  栈里没有 active 帧，剩余 {remaining}：请用 `activate --frame <id>` 选中一个，"
              "或让用户决定下一件事 —— 不要让栈悬在无栈顶状态")
    else:
        print("  栈已空 —— 未关闭帧已全部关闭。请跑 `survey` 回到长期池选下一件事。")
    print("=" * 72)

    violations, warnings = check_invariants(data, ledger_path=_resolve_ledger_path(jp, data))
    mine_pend = [c for c in data["captures"]
                 if c.get("found_in") == frame["frame_id"] and c["disposition"] == "pending"]
    if mine_pend:
        print(f"\n[exit 1] 本帧有 {len(mine_pend)} 条衍生登记未处置，不得收工："
              f"{[c['capture_id'] for c in mine_pend]}", file=sys.stderr)
        return 1
    if violations:
        print(f"\n⚠ verify 有 {len(violations)} 项硬违规（不影响本次出栈，但队列已不可信，需尽快处理）：",
              file=sys.stderr)
        for x in violations:
            print(f"   - {x}", file=sys.stderr)
    for x in warnings:
        print(f"   ⚠ 软警告：{x}")
    return 0


def cmd_amend(args: argparse.Namespace) -> int:
    """修订未关闭帧的标题/判据/来源/指针，并在 event_log 留痕。

    **已关闭帧不得改写**：终态帧是历史记录，改它等于篡改复盘证据。
    需要纠正时新压一帧说明，让弯路本身留在树里。
    """
    jp, mp = resolve_paths(args)
    data = load(jp)
    f = find_frame(data, args.frame)
    if f["status"] in TERMINAL_STATUS:
        die(2, f"{args.frame} 已关闭（{f['status']}），历史不得改写；"
               "如需纠正请新压一帧说明，让这次返工留在树里")
    changes: list[str] = []
    if args.title is not None and args.title != f["title"]:
        changes.append(f"title: {f['title']!r} → {args.title!r}")
        f["title"] = args.title
    if args.goal is not None and args.goal != f.get("goal"):
        changes.append(f"goal: {f.get('goal') or '—'!r} → {args.goal!r}")
        f["goal"] = args.goal
    if args.origin is not None and args.origin != f.get("origin"):
        changes.append(f"origin: {f.get('origin') or '—'!r} → {args.origin!r}")
        f["origin"] = args.origin
    if args.criteria:
        old = f.get("criteria") or []
        changes.append(f"criteria: {len(old)} 条 → {len(args.criteria)} 条（整组替换）")
        f["criteria"] = list(args.criteria)
    if args.pointers:
        new = json.loads(args.pointers)
        changes.append(f"pointers: 合并 {list(new)}")
        f.setdefault("pointers", {}).update(new)
    if not changes:
        print(f"[OK] {args.frame} 没有需要修改的字段")
        return 0
    _log(data, "amended", frame_id=f["frame_id"], detail="; ".join(changes)[:200])
    save(jp, data)
    render_view(jp, mp, data)
    print(f"[OK] 已修订 {f['frame_id']}（改动留痕于 event_log，retro 可查）：")
    for c in changes:
        print(f"     - {c}")
    return 0


def cmd_retro(args: argparse.Namespace) -> int:
    """弯路复盘：只读。把终态帧与 event_log 汇总成「我们走过哪些弯路」。"""
    jp, _ = resolve_paths(args)
    data = load(jp)
    ev = data.get("event_log") or []
    frames = data["frames"]
    bar = "═" * 72

    def stamp(s: str | None) -> str:
        return (s or "")[:16].replace("T", " ")

    print(f"弯路复盘 · {data['campaign_id']}")
    print(bar)
    if data.get("migrated_from"):
        print(f"⚠ 本栈由 {data['migrated_from']} 迁移而来：迁移点之前的 activate/resolve")
        print("  历史无法回填，「用户方向切换」计数只覆盖迁移之后的部分。")
        print()

    # `escalated` 的立项去向取自解析后的布局，不写死 docs/operations/issues.md。
    # 渲染成**仓库根相对路径** → 默认布局下与既有字面量逐字相同（行为等价的实现方式）。
    issue_doc = layout_for_root(_repo_root_or_none(jp)).issue_doc
    groups = (
        ("wontfix", "放弃的方案", "决定不走的路 —— 最典型的弯路"),
        ("parked", "明确搁置", "真问题但当下不做，别让它沉底"),
        ("escalated", "升级为长期缺陷", f"已立项到 {issue_doc}"),
        ("done", "已完成", ""),
    )
    for terminal, label, note in groups:
        grp = [f for f in frames if f["status"] == terminal]
        print(f"【{label} · {terminal}】{len(grp)} 条" + (f"　{note}" if note else ""))
        for f in grp:
            print(f"  {stamp(f.get('closed_at'))}  {f['frame_id']}  {_plain(f['title'], 54)}")
            if terminal != "done" and f.get("close_note"):
                print(f"      原因：{_plain(f['close_note'], 140)}")
        print()

    # 一次改道会先记 requeued（原栈顶退回 queued）再记 activated(actor=user)。
    # 只数「改道次数」，不把同一次切换的两条事件数成两次。
    switches: list[dict] = []
    for i, e in enumerate(ev):
        if e.get("kind") == "requeued":
            switches.append(e)
        elif e.get("kind") == "activated" and e.get("actor") == "user":
            prev = ev[i - 1] if i else None
            if not (prev and prev.get("kind") == "requeued"):
                switches.append(e)
    print(f"【用户方向切换】{len(switches)} 次　← 复盘最该看的信号"
          f"（显示最近 {args.tail} 条）")
    for e in switches[-args.tail:]:
        print(f"  {stamp(e.get('at'))}  #{e.get('seq')} {e.get('kind'):9} "
              f"{e.get('frame_id') or '—'}　{_plain(e.get('detail') or '', 70)}")
    print()

    dfs = [e for e in ev if e.get("actor") == "dfs"]
    print(f"【DFS 自动抢占/恢复】{len(dfs)} 次　（计划内深入，不算弯路）")
    print()

    disp: dict[str, int] = {}
    for c in data["captures"]:
        disp[c["disposition"]] = disp.get(c["disposition"], 0) + 1
    print(f"【衍生问题】共 {len(data['captures'])} 条 → "
          + ("，".join(f"{k} {v}" for k, v in sorted(disp.items())) or "无"))
    src: dict[str, int] = {}
    for c in data["captures"]:
        k = c.get("found_in") or "（未标注来源帧）"
        src[k] = src.get(k, 0) + 1
    if src:
        print("  来源分布：" + "，".join(f"{k}×{v}"
              for k, v in sorted(src.items(), key=lambda x: -x[1])))
    print()

    amended = [e for e in ev if e.get("kind") == "amended"]
    print("【结构指标】")
    print(f"  帧总数 {len(frames)}｜已关闭 "
          f"{len([f for f in frames if f['status'] in TERMINAL_STATUS])}｜"
          f"未关闭 {len(open_frames(data))}")
    print(f"  栈深峰值 d{max([f['depth'] for f in frames], default=0)}"
          f"（上限 {MAX_DEPTH}）｜事件 {len(ev)} 条｜帧修订 {len(amended)} 次")
    for e in amended[-args.tail:]:
        print(f"    #{e.get('seq')} {e.get('frame_id')}　{_plain(e.get('detail') or '', 90)}")
    print(bar)
    return 0


def render_view(jp: Path, mp: Path, data: dict) -> None:
    mp.parent.mkdir(parents=True, exist_ok=True)
    mp.write_text(render_markdown(data), encoding="utf-8")


def cmd_render(args: argparse.Namespace) -> int:
    jp, mp = resolve_paths(args)
    data = load(jp)
    text = render_markdown(data)
    if args.check:
        if not mp.exists():
            die(1, f"Markdown 视图缺失：{mp}")
        cur = mp.read_text(encoding="utf-8")
        if cur != text:
            die(1, f"Markdown 视图与 JSON 真源不一致：{mp}\n请运行 `stack.py render` 重新生成（勿手改视图）")
        print(f"[OK] 视图与真源一致：{mp}")
        return 0
    render_view(jp, mp, data)
    print(f"[OK] 已渲染视图：{mp}")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    jp, _ = resolve_paths(args)
    print_show(load(jp))
    return 0


# ---------------------------------------------------------------- survey（吸收自 next-work-plan）

# 两个长期待办池的**默认**路径在文件头的常量区（PLAN_DOC / ISSUE_DOC）；
# 实际生效值一律由 load_layout 决定 —— 项目可在 <repo>/workstacks/config.json 里覆盖。


def _plain(s: str, limit: int = 72) -> str:
    """去掉 Markdown 强调并按显示宽度截断，让菜单在终端里对齐可读。"""
    s = re.sub(r"\s+", " ", s.replace("**", "").replace("`", "")).strip()
    if _dwidth(s) <= limit:
        return s
    cut = ""
    for ch in s:
        if _dwidth(cut + ch) > limit - 1:
            break
        cut += ch
    return cut + "…"


def parse_work_plans(path: Path) -> list[dict]:
    """抽 `## N-00x · 标题` 及其状态/优先级。只抽索引，不复制正文。"""
    if not path.exists():
        return []
    out: list[dict] = []
    cur: dict | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^##\s+(N-\d+)\s*·\s*(.+?)\s*$", line)
        if m:
            cur = {"id": m.group(1), "title": m.group(2), "status": "?", "priority": "?"}
            out.append(cur)
            continue
        if cur is None:
            continue
        m = re.match(r"^-\s+\*\*状态\*\*：\s*`?([^`\n]+?)`?\s*$", line)
        if m:
            cur["status"] = m.group(1).strip()
            continue
        m = re.match(r"^-\s+\*\*优先级\*\*：\s*(\S+)\s*$", line)
        if m:
            cur["priority"] = m.group(1).strip()
    return out


def parse_issue_index(path: Path) -> list[dict]:
    """抽 issues.md「未解决问题总览」表：| ID | 标题 | 优先级 | 类型 | 状态 | 依赖 |"""
    if not path.exists():
        return []
    out: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\|\s*(ISS-\d+)\s*\|(.*)$", line)
        if not m:
            continue
        cells = [c.strip() for c in m.group(2).split("|")]

        def cell(i: int, default: str = "?") -> str:
            return cells[i] if len(cells) > i and cells[i] else default

        out.append({
            "id": m.group(1),
            "title": cell(0, ""),
            "priority": cell(1),
            "type": cell(2),
            "status": cell(3),
            "depends": cell(4, "—"),
        })
    return out


def _pool_label(layout: Layout) -> str:
    """survey 第二步标题里的池位置标签。

    两个池同目录（默认布局即如此）→ 渲染该目录 + `/`，于是默认布局下与既有硬编码
    字面量 `docs/operations/` **逐字相同**；不同目录 → 如实渲染两个相对路径，不假装它们同处一地。
    """
    pool_dir = layout.plan_doc.parent
    if layout.issue_doc.parent == pool_dir:
        return f"{pool_dir}/"
    return f"{pool_dir}/ 与 {layout.issue_doc.parent}/"


def cmd_survey(args: argparse.Namespace) -> int:
    """先看当前栈（campaign 级），再看长期池。**只读**：不修改栈，不渲染视图，不改池文档。"""
    jp, _ = resolve_paths(args)
    root = find_repo_root(_start_from_args(args))
    layout = layout_for_root(root)
    campaign = args.campaign or (jp.parent.name if jp.exists() else None)
    bar = "═" * 72

    print(bar)
    print("第一步 · 当前推进栈（campaign 级，最容易丢的东西，先看这个）")
    print(bar)
    stack_ids: set = set()
    has_open = False
    if jp.exists():
        data = load(jp)
        campaign = campaign or data.get("campaign_id")
        opens = open_frames(data)
        has_open = bool(opens)
        print_show(data)
        for f in opens:
            stack_ids.update((f.get("pointers") or {}).get("issues") or [])
        for c in data.get("captures") or []:
            if c.get("pointer"):
                stack_ids.add(c["pointer"])
    else:
        print(f"本 campaign 还没有推进栈：{jp} 不存在（尚未 ensure / push）。")
    print()

    print(bar)
    print(f"第二步 · 长期待办池（{_pool_label(layout)}，进 Git 的跨轮次真源）")
    print(bar)
    plan_path, issue_path = root / layout.plan_doc, root / layout.issue_doc
    plans, issues = parse_work_plans(plan_path), parse_issue_index(issue_path)
    if not plans and not issues:
        # 两种「空池」必须**可区分**（裁决 R16）：
        #   ① 两个池文件都不存在 → 项目还没铺长期池，给 bootstrap 指引；
        #   ② 文件存在但解析出 0 条 → 这是正常运行态（当前没有待办 / 没有未解决问题），
        #      保留既有 warn 行原文，不换成 bootstrap 指引，否则等于谎报「文件缺失」。
        # 两种情形都 exit 0：survey 是只读信息命令，用非零退出码表达「没内容」
        # 会污染任何调用它的脚本。
        if not plan_path.exists() and not issue_path.exists():
            print(f"⚠ 未解析到任何池条目，且两个池文件都不存在：{plan_path}、{issue_path}")
            print("  这两个文件是 work-queue-stack 的项目侧前提，由仓库初始化脚本铺设：")
            print(f"    python3 <方法论仓库>/scripts/bootstrap_project.py {root}")
            return 0
        print(f"⚠ 未解析到任何池条目。检查是否存在：{plan_path}、{issue_path}")
        return 0

    print(f"\n【工作计划】{plan_path}　共 {len(plans)} 条")
    for pl in plans:
        print(f"  {pl['id']}  {pl['priority']:<4}{pl['status']:<13}{_plain(pl['title'])}")

    by_pri: dict = {}
    for it in issues:
        by_pri.setdefault(it["priority"], []).append(it)
    print(f"\n【问题清单】{issue_path}　未解决 {len(issues)} 条")
    for pri in sorted(by_pri):
        print(f"  {pri}（{len(by_pri[pri])} 条）")
        for it in by_pri[pri]:
            dep = "" if it["depends"] in ("—", "", "?") else f"　依赖 {it['depends']}"
            dup = "　⟵ 已在栈里" if it["id"] in stack_ids else ""
            print(f"    {it['id']}  {it['status']:<13}{_plain(it['title'], 58)}{dep}{dup}")
            if args.commands and it["id"] not in stack_ids:
                print(f"      $S push --campaign {campaign or '<campaign>'} "
                      f"--title \"{it['id']} {_plain(it['title'], 40)}\" "
                      f"--origin \"survey 长期池\" --pointers '{{\"issues\":[\"{it['id']}\"]}}'")

    print()
    print(bar)
    print("选完之后怎么落到栈里（只存指针，不复制池正文）")
    print(bar)
    if stack_ids:
        print(f"⚠ 已在栈里、不要重复压：{', '.join(sorted(str(x) for x in stack_ids))}")
    print(f"  python3 {Path(__file__).resolve()} push --campaign {campaign or '<campaign>'} \\")
    print('      --title "ISS-0xx <一句话标题>" \\')
    print('      --criteria "判据1: …" --criteria "判据2: …" \\')
    print("      --origin \"survey 长期池\" --pointers '{\"issues\":[\"ISS-0xx\"]}'")
    if has_open:
        print()
        print("纪律：栈里还有未关闭帧。要么先收口，要么显式 parked 并写明理由——")
        print("      不允许因为挑了新的大事就让旧帧静默消失。")
    return 0


def cmd_ensure(args: argparse.Namespace) -> int:
    """幂等启用推进栈：不存在则创建并绑定总目标台账，存在则补绑并回显栈顶。

    **创建必须显式授权**：新建栈时 `--activation` 只能是 `user_declared`（用户主动声明需要栈）
    或 `user_approved_on_proposal`（用户批准了 `propose` 申请卡）；缺省、或传 legacy 值
    `auto_orchestration`，一律 `exit 2` 且**不产生任何目录与文件**。
    **编排身份不构成启用授权** —— 受控目标模式与多阶段编排在栈不存在时只能 `propose` 申请，
    等用户批准；单阶段编排、直接做、普通对话同理。
    **幂等**：栈已存在时重复调用不新建、不改 activation、不动任何帧，只补 bound_ledger 并回显状态，
    因此「接线」这一步任何身份都可以无条件调用，不会因为重复调用而制造出第二个栈。
    """
    jp, mp = resolve_paths(args)
    created = not jp.exists()
    data = load(jp, allow_missing=True)
    if getattr(args, "title", None):
        if data.get("title") not in (None, data.get("campaign_id"), args.title):
            print(f"[OK] 核心任务名更新：{data.get('title')} → {args.title}")
        data["title"] = args.title
    data.setdefault("title", data.get("campaign_id"))
    if created:
        if not getattr(args, "force_new", False):
            _refuse_near_match_fork(jp, jp.parent.name)
        if not args.activation:
            die(2, "创建栈必须显式声明启用方式：--activation user_declared（用户主动声明需要栈）"
                   "或 user_approved_on_proposal（用户批准了申请卡）。\n"
                   "     编排身份不构成启用授权。栈不存在又确有需要时，先运行只读的 "
                   "`propose --campaign <id> --signal … --cost …` 打印申请卡（不落任何文件），"
                   "等用户批准后再 ensure。")
        if args.activation in LEGACY_ACTIVATIONS:
            die(2, f"--activation {args.activation} 是 legacy 值（v3 时期「编排自动启用」留下的），"
                   "不再用于新建栈；只接受 user_declared 或 user_approved_on_proposal。\n"
                   "     改记既有 pre-v3-unknown 栈的历史值请显式带 --set-activation。")
        if args.campaign:
            data["campaign_id"] = args.campaign
        data["activation"] = args.activation
        data["bound_ledger"] = _ledger_rel(jp)
        print(f"[OK] 已启用推进栈（新建，activation={args.activation}）：{jp}")
    else:
        if data.get("activation") in (None, "pre-v3-unknown") and args.set_activation:
            data["activation"] = args.activation
            print(f"[OK] activation 由 pre-v3-unknown 显式改记为 {args.activation}")
        if not data.get("bound_ledger"):
            rel = _ledger_rel(jp)
            if rel:
                data["bound_ledger"] = rel
                print(f"[OK] 已补绑总目标台账：{rel}")
            else:
                print(f"[提示] 同目录没有 {LEDGER_FILE_NAME}，bound_ledger 保持为空"
                      "（verify 会给软警告）", file=sys.stderr)
        else:
            print(f"[OK] 推进栈已存在，绑定不变：{data['bound_ledger']}")
    save(jp, data)
    render_view(jp, mp, data)
    print(f"     campaign={data['campaign_id']} · activation={data.get('activation')} · "
          f"bound_ledger={data.get('bound_ledger') or '（未绑定）'}")
    return cmd_show(args)


def cmd_verify(args: argparse.Namespace) -> int:
    jp, mp = resolve_paths(args)
    data = load(jp)
    violations, warnings = check_invariants(data, ledger_path=_resolve_ledger_path(jp, data))
    # 10) 单栈指针：一个对话只允许一个栈
    root = _repo_root_or_none(jp)
    ptr = _read_pointer(_pointer_path(root, layout_for_root(root))) if root is not None else None
    if ptr:
        if ptr.get("campaign") != data.get("campaign_id"):
            warnings.append(f"当前指针指向 {ptr.get('campaign')!r}，而正在校验的是 "
                            f"{data.get('campaign_id')!r}（一个对话只允许一个栈；"
                            "切换用 `use --campaign <id>`，会留痕）")
        elif stack_status(data) == "closed":
            violations.append("当前指针指向一个已 closed（全部帧终态）的栈：指针已失效，"
                              "请 `use --campaign <id>` 指向正在推进的栈")
    if not mp.exists():
        violations.append(f"Markdown 视图缺失：{mp}（运行 `stack.py render` 生成）")
    elif mp.read_text(encoding="utf-8") != render_markdown(data):
        violations.append(f"Markdown 视图与 JSON 真源不一致：{mp}（勿手改视图，运行 `render` 重生成）")
    opens = open_frames(data)
    print(f"栈 {jp}")
    print(f"  未关闭 {len(opens)} 帧 / 已关闭 "
          f"{len([f for f in data['frames'] if f['status'] in TERMINAL_STATUS])} 帧 / "
          f"衍生登记 {len(data['captures'])} 条 / 出栈日志 {len(data['pop_log'])} 条")
    for x in warnings:
        print(f"   ⚠ 软警告：{x}")
    if violations:
        print(f"[FAIL] {len(violations)} 项硬违规：")
        for x in violations:
            print(f"   - {x}")
        return 1
    print("[PASS] 硬不变量全过：单一栈顶、挂起来路可追、深度合规、指针自洽、"
          "无静默消失的帧、无未处置衍生、视图与真源一致")
    return 0


# ---------------------------------------------------------------- CLI


def _migrate_ledger_only(root: Path, legacy_dir: Path, new_dir: Path) -> int:
    """把总目标台账与 `phases/` 也搬进 `workstacks/<campaign>/`。

    搬完绑定回到「同目录」，且台账成为 tracked 文件 —— `clean-scratch-intermediates`
    只清 `scratch/`、`git clean -fdx` 不删 tracked 文件，两条删除路径同时失效。
    **不改写台账历史条目里的旧路径**（那是历史），只在一级标题后插入一条迁移说明做映射。
    """
    dst = new_dir / STACK_FILE_NAME
    data = load(dst)
    b_frames = len(data.get("frames", []))
    b_seq = [e.get("seq") for e in data.get("event_log", [])]

    moved = [LEDGER_FILE_NAME]
    shutil.move(str(legacy_dir / LEDGER_FILE_NAME), str(new_dir / LEDGER_FILE_NAME))
    src_phases = legacy_dir / "phases"
    if src_phases.is_dir():
        if (new_dir / "phases").exists():
            die(2, f"新位置已存在 phases/，拒绝覆盖：{new_dir / 'phases'}")
        shutil.move(str(src_phases), str(new_dir / "phases"))
        moved.append("phases/")

    lp = new_dir / LEDGER_FILE_NAME
    lines = lp.read_text(encoding="utf-8").split("\n")
    note = (f"> **路径迁移说明（{now()[:10]}）**：本台账与 `phases/` 已由 "
            f"`{legacy_dir.relative_to(root)}/` 迁至 `{new_dir.relative_to(root)}/` 并纳入 Git。"
            "下文历史条目里出现的旧路径按此映射理解，**历史正文一律不改写**。")
    idx = next((i for i, ln in enumerate(lines) if ln.startswith("# ")), -1)
    lines.insert((idx + 1) if idx >= 0 else 0, "\n" + note)
    lp.write_text("\n".join(lines), encoding="utf-8")

    data["bound_ledger"] = str((new_dir / LEDGER_FILE_NAME).relative_to(root))
    _log(data, "migrated",
         text=f"总目标台账与 phases/ 由 {legacy_dir.relative_to(root)} 迁至 "
              f"{new_dir.relative_to(root)}（纳入 Git；bound_ledger 回到同目录）")
    save(dst, data)
    render_view(dst, new_dir / VIEW_FILE_NAME, data)

    after = json.loads(dst.read_text(encoding="utf-8"))
    a_seq = [e.get("seq") for e in after.get("event_log", [])]
    assert len(after.get("frames", [])) == b_frames, "帧数变了"
    assert a_seq[:len(b_seq)] == b_seq, "原 event_log 的 seq 被改写"
    print(f"[OK] 台账已搬迁：搬运 {len(moved)} 项：{', '.join(moved)}")
    print(f"     bound_ledger = {after['bound_ledger']}（回到同目录）")
    print(f"     帧数 {b_frames}（不变）；event_log {len(b_seq)} → {len(a_seq)}（只追加 1 条）")
    return 0


def _refuse_near_match_fork(json_path: Path, campaign: str) -> None:
    """`ensure` 新建栈时的拼写防线：与既有 campaign 高度相似即拒绝，防**栈分叉**。

    `_die_no_stack` 只挡 `push`，而它给出的补救建议恰恰是「去跑 `ensure`」——
    `ensure` 自己若不校验，这道防线就等于把人导向分叉。实测：
    `ensure --campaign ui-image-system-recogntion --activation user_declared`（少一个 `i`）
    会安静地建出一个空栈并 `verify` PASS，真栈一帧未动。
    确实要建一个名字相近的**不同**栈时，显式带 `--force-new`。
    """
    ids = [i for i in _existing_campaign_ids(json_path) if i != campaign]
    close = difflib.get_close_matches(campaign, ids, n=3, cutoff=0.6)
    if not close:
        return
    listing = "、".join(f"`{c}`" for c in close)
    die(2, f"疑似 campaign 拼写错误：已存在 {listing}，而你要新建 `{campaign}`。\n"
           "     `ensure` 是创建栈的唯一入口，在这里放过拼写错误就会造成**栈分叉**：\n"
           "     帧压进新空栈、真栈一帧未动，而两边 verify 都 PASS（分叉是静默的）。\n"
           "     请核对拼写后重试；确实要建一个名字相近的**不同**栈，显式带 --force-new。")


def _refuse_legacy_fork(new_json: Path, campaign: str, root: Path) -> None:
    """旧位置有栈、新位置没有 → 拒绝操作，防止在 `workstacks/` 里建出第二个栈。

    与 `_die_no_stack` 同一立场：栈分叉的危险在于它**静默且两边自检都 PASS**。
    搬迁期间最容易出现——旧栈还在 `scratch/workbench/`，而命令已按新根解析。
    """
    legacy = root / LEGACY_WORKBENCH[0] / LEGACY_WORKBENCH[1] / campaign / STACK_FILE_NAME
    if legacy.exists():
        die(2, f"栈仍在旧位置：{legacy}\n"
               f"不得在新位置 {new_json} 另起一个栈（帧会进新栈、真栈一帧未动，而两边 verify 都 PASS）。\n"
               f"请先运行：stack.py migrate --campaign {campaign}")


def cmd_migrate(args: argparse.Namespace) -> int:
    """把栈从旧位置 `scratch/workbench/<campaign>/` 迁到 `workstacks/<campaign>/`（纳入 Git）。

    只搬运 + 留痕：不改 frames、不改既有 event_log 的 seq、不改判据、不动台账。
    **验收是机械断言而不是描述**：迁移前后帧数相同、原 seq 序列逐位相同、
    event_log 只多出一条 `migrated`；`.bak` 备份收进 `history/`，不污染清单。
    """
    campaign = getattr(args, "campaign", None)
    if not campaign:
        die(2, "migrate 需要 --campaign <id>（不支持 --path：迁移必须知道 campaign 才能定位新旧两处）")
    root = find_repo_root(_start_from_args(args))
    layout = layout_for_root(root)
    legacy_dir = root / LEGACY_WORKBENCH[0] / LEGACY_WORKBENCH[1] / campaign
    new_dir = root / layout.workstack_root / campaign
    src, dst = legacy_dir / STACK_FILE_NAME, new_dir / STACK_FILE_NAME
    if dst.exists():
        # 栈已迁过：台账若仍在旧位置，就执行「只搬台账」（用户 2026-09-20 决定：台账跟着搬）
        if (legacy_dir / LEDGER_FILE_NAME).exists():
            return _migrate_ledger_only(root, legacy_dir, new_dir)
        die(2, f"新位置已存在栈、旧位置也没有台账，无需迁移：{dst}")
    if not src.exists():
        die(2, f"旧位置没有栈，无需迁移：{src}")

    before = json.loads(src.read_text(encoding="utf-8"))
    b_frames = len(before.get("frames", []))
    b_seq = [e.get("seq") for e in before.get("event_log", [])]

    new_dir.mkdir(parents=True, exist_ok=True)
    (new_dir / "history").mkdir(exist_ok=True)
    moved = [src.name]
    shutil.move(str(src), str(dst))
    view = legacy_dir / VIEW_FILE_NAME
    if view.exists():
        shutil.move(str(view), str(new_dir / VIEW_FILE_NAME))
        moved.append(view.name)
    for bak in sorted(legacy_dir.glob(STACK_FILE_NAME + "*.bak")):
        shutil.move(str(bak), str(new_dir / "history" / bak.name))
        moved.append(f"history/{bak.name}")

    data = load(dst)
    if not data.get("bound_ledger"):
        rel = _ledger_rel(dst)
        if rel:
            data["bound_ledger"] = rel
    _log(data, "migrated",
         text=f"栈目录由 {legacy_dir.relative_to(root)} 迁至 {new_dir.relative_to(root)}"
              f"（纳入 Git 版本管理；**本条只记第一段** —— 台账与 phases/ 仍在旧位置，"
              f"再跑一次同一条 migrate 命令把它们搬进同目录；当前 bound_ledger={data.get('bound_ledger')}）")
    save(dst, data)
    render_view(dst, new_dir / VIEW_FILE_NAME, data)

    after = json.loads(dst.read_text(encoding="utf-8"))
    a_frames = len(after.get("frames", []))
    a_seq = [e.get("seq") for e in after.get("event_log", [])]
    assert a_frames == b_frames, f"帧数变了：{b_frames} → {a_frames}"
    assert a_seq[:len(b_seq)] == b_seq, "原 event_log 的 seq 被改写（迁移只允许追加）"
    assert len(a_seq) == len(b_seq) + 1, f"event_log 应只多一条 migrated：{len(b_seq)} → {len(a_seq)}"

    print(f"[OK] 已迁移：{legacy_dir.relative_to(root)} → {new_dir.relative_to(root)}")
    print(f"     搬运 {len(moved)} 个文件：{', '.join(moved)}")
    print(f"     帧数 {b_frames} → {a_frames}（不变）；event_log {len(b_seq)} → {len(a_seq)}（只追加 1 条 migrated）")
    print(f"     bound_ledger = {after.get('bound_ledger')}")
    print("[提示] 第一段只搬了栈：旧目录仍保留台账 goal-ledger.md 与阶段快照 phases/。"
          "**再跑一次同一条 migrate 命令**即可把它们搬进同目录（用户 2026-09-20 定案：台账跟着搬）。")
    print("     搬完再复核 `verify` 与 `render --check`，然后决定是否 "
          f"`git add {layout.workstack_root}/`；未搬之前它们仍暴露在 scratch/ 的清理射程内。")
    return 0


def cmd_propose(args: argparse.Namespace) -> int:
    """**只读**打印「推进栈启用申请卡」。不创建目录、不写任何文件、不改任何状态。

    存在的理由：启用栈是**用户的决策**，不是代理的默认动作；而「为什么要用栈」必须结构化、
    可横向比较，不能每次由代理临场编一段话。命中的复杂度信号由 `--signal` 逐条传入，
    脚本负责算命中数与结论（≥2 条即建议启用，依据 orchestration-strength-guide 的信号表）。
    """
    jp, _ = resolve_paths(args)
    campaign = jp.parent.name
    if jp.exists():
        data = load(jp)
        print(f"[提示] 该 campaign 已有推进栈，**无需申请** —— 直接接线（ensure 幂等、不提问）：{jp}")
        print(f"     核心任务名：{data.get('title')}｜未关闭 {len(open_frames(data))} 帧"
              f"｜状态 {stack_status(data)}")
        return 0
    signals = list(getattr(args, "signal", None) or [])
    negatives = list(getattr(args, "negative", None) or [])
    cost = getattr(args, "cost", None) or "待办与衍生问题只存在于对话记忆，被压缩 / 换模型 / 跨天即丢"
    hit = len(signals)
    print("【推进栈启用申请】")
    print(f"  campaign：{campaign}")
    print("  栈状态：不存在（已存在则不申请，直接接线）")
    print(f"  复杂度信号命中 {hit}/6：")
    for x in signals:
        print(f"    ✓ {x}")
    for x in negatives:
        print(f"    ✗ {x}")
    print(f"  不启用的代价：{cost}")
    if hit >= 2:
        print("  结论：**建议启用**")
        print(f"  批准后执行：stack.py ensure --campaign {campaign} "
              f"--activation user_approved_on_proposal --title \"<核心任务名>\"")
    else:
        print("  结论：**不建议启用**（信号不足 2 条 —— 直接做，别加仪式）")
    print("  [说明] 本命令只读：没有创建目录、没有写文件；未获批准不得 ensure。")
    return 0


def cmd_stacks(args: argparse.Namespace) -> int:
    """**只读**列出全部任务栈 —— 多栈共存时的全局视图（此前缺这一层，多栈却没有多栈视图）。"""
    root = find_repo_root(_start_from_args(args))
    layout = layout_for_root(root)
    base = root / layout.workstack_root
    ptr = _read_pointer(_pointer_path(root, layout))
    if not base.is_dir():
        print(f"[提示] 还没有任务栈文件夹：{base}")
        return 0
    rows = []
    for d in sorted(base.iterdir()):
        jp = d / STACK_FILE_NAME
        if not d.is_dir() or not jp.exists():
            continue
        data = load(jp)
        opens = open_frames(data)
        act = next((f for f in opens if f["status"] == "active"), None)
        frames = data.get("frames", [])
        rows.append((data, jp, opens, act, frames))
    if not rows:
        print(f"[提示] {base} 下没有任何栈")
        return 0
    n_open = sum(1 for r in rows if r[2])
    print(f"任务栈清单 · {base.relative_to(root)}/　共 {len(rows)} 个"
          f"（open {n_open} / closed {len(rows) - n_open}）")
    if ptr:
        print(f"当前指针：{ptr.get('campaign')}　（{ptr.get('title') or '未命名'}"
              f"，绑定于 {str(ptr.get('at', ''))[:16].replace('T', ' ')}）")
    else:
        print("当前指针：（无 —— 恢复时需语义识别或用户指定，不得猜）")
    print()
    rows.sort(key=lambda r: (bool(r[2]) is False, str(r[0].get("updated_at", ""))), reverse=False)
    for data, jp, opens, act, frames in rows:
        cur = bool(ptr and ptr.get("campaign") == data.get("campaign_id"))
        mark = "▶" if cur else ("　" if opens else "·")
        st = "open" if opens else "closed"
        orphan = "　⚠孤儿空栈" if not frames else ""
        print(f"{mark} [{st:^6}] {data.get('title')}{orphan}")
        print(f"         campaign={data.get('campaign_id')}｜activation={data.get('activation')}"
              f"｜帧 未关闭 {len(opens)} / 已关闭 {len(frames) - len(opens)}"
              f"｜更新 {str(data.get('updated_at', ''))[:16].replace('T', ' ')}")
        top = (act or {}).get("title")
        print(f"         栈顶：{(act or {}).get('frame_id', '（无）')} {top or ''}"
              .rstrip())
    print()
    print("说明：一个对话只允许绑一个栈（▶ 为当前指针所指）；closed 表示全部帧已终态，"
          "代理不得删除任何栈，清理无需代理参与。")
    return 0


def cmd_use(args: argparse.Namespace) -> int:
    """把某个栈设为「当前栈」（单对话单栈单指针）。切换留痕于该栈 event_log 与指针文件。"""
    jp, mp = resolve_paths(args)
    if not jp.exists():
        _die_no_stack(jp)
    data = load(jp)
    if not open_frames(data):
        die(2, f"该栈已全部收口（closed），不得设为当前栈：{jp}\n"
               "要复用它请先 `push` 新帧说明返工原因，让返工留在树里可查")
    root = find_repo_root(_start_from_args(args))
    pp = _pointer_path(root, layout_for_root(root))
    old = _read_pointer(pp)
    old_cid = (old or {}).get("campaign")
    if old_cid == data["campaign_id"]:
        print(f"[OK] 当前栈未变：{data['campaign_id']}（{data.get('title')}）")
    else:
        _log(data, "pointer_switched",
             text=f"当前栈指针：{old_cid or '（无）'} → {data['campaign_id']}"
                  f"（一个对话只允许一个栈；被切走的栈保持原状，未关闭帧不会丢）")
        save(jp, data)
        render_view(jp, mp, data)
        _write_pointer(pp, {"campaign": data["campaign_id"], "title": data.get("title"),
                            "stack_path": str(jp.relative_to(root)), "at": now()})
        print(f"[OK] 当前栈切换：{old_cid or '（无）'} → {data['campaign_id']}")
        print(f"     被切走的栈保持原状，其未关闭帧不会丢；回去用 `use --campaign {old_cid}`"
              if old_cid else "     指针文件不入库（切换不会脏 Git）")
    return cmd_show(args)


def cmd_retitle(args: argparse.Namespace) -> int:
    """改核心任务名（title）。campaign_id 不变 —— 指针、bound_ledger 与历史引用都不受影响。"""
    jp, mp = resolve_paths(args)
    data = load(jp)
    old = data.get("title")
    if old == args.title:
        print(f"[OK] 核心任务名未变：{old}")
        return 0
    data["title"] = args.title
    _log(data, "retitled", text=f"核心任务名：{old} → {args.title}")
    save(jp, data)
    render_view(jp, mp, data)
    print(f"[OK] 核心任务名已改：{old} → {args.title}")
    print("     campaign_id 不变，指针与历史引用不受影响；改动留痕 event_log")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="stack.py",
        description="栈式工作队列：待办压栈、衍生登记、出栈回看与不变量校验",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--campaign", help="campaign_id；栈落在 <workstack_root>/<campaign>/"
                                           "（默认 workstacks，可在 <仓库根>/workstacks/config.json 覆盖；"
                                           "旧位置需先 migrate）")
        sp.add_argument("--path", help="直接指定 active-work-stack.json 路径（优先于 --campaign）")
        sp.add_argument("--repo-root", help="仓库根，默认从当前目录向上找 .git / workstacks/ / AGENTS.md / .codex")

    sp = sub.add_parser("show", help="回显全栈（任何时候都可以跑）")
    common(sp)
    sp.set_defaults(func=cmd_show)

    sp = sub.add_parser("survey", help="先看当前栈、再看长期待办池（只读；吸收自 next-work-plan）")
    common(sp)
    sp.add_argument("--commands", action="store_true",
                    help="为每个池条目额外打印可直接执行的 push 命令")
    sp.set_defaults(func=cmd_survey)

    sp = sub.add_parser("push", help="压入一帧待办")
    common(sp)
    sp.add_argument("--title", required=True)
    sp.add_argument("--goal", help="这一帧要达成什么")
    sp.add_argument("--criteria", action="append", help="完成判据，可重复")
    sp.add_argument("--parent", help="父帧 frame_id；给出则 depth+1")
    sp.add_argument("--origin", help="来源（谁/哪一轮要求的），便于事后回溯")
    sp.add_argument("--pointers", help='JSON 对象，如 {"issues":["ISS-021"],"commits":["bcc5f6f"]}')
    sp.add_argument("--activate", action="store_true",
                    help="抢占为栈顶（须是当前栈顶的直接子帧）；默认无 active 帧时才自动成为栈顶")
    sp.set_defaults(func=cmd_push)

    sp = sub.add_parser("activate", help="把某个未关闭帧设为栈顶（DFS 抢占 或 用户驱动切换）")
    common(sp)
    sp.add_argument("--frame", required=True)
    sp.set_defaults(func=cmd_activate)

    sp = sub.add_parser("capture", help="登记一个推进中发现的新问题（先登记，再决定）")
    common(sp)
    sp.add_argument("--text", required=True, help="现象 + 发现位置，一行说清")
    sp.add_argument("--found-in", help="在哪一帧里发现的")
    sp.add_argument("--disposition", choices=DISPOSITIONS, default="pending",
                    help="blocks=阻塞当前帧 / spawns=真问题但不阻塞 / note=非独立问题 / pending=稍后决定")
    sp.add_argument("--frame", help="已立帧时给出 frame_id")
    sp.add_argument("--pointer", help="归属指针，如 ISS-007 或某个文件路径")
    sp.set_defaults(func=cmd_capture)

    sp = sub.add_parser("resolve", help="把 pending 的衍生登记处置掉")
    common(sp)
    sp.add_argument("--capture", required=True)
    sp.add_argument("--disposition", choices=DISPOSITIONS, required=True)
    sp.add_argument("--frame")
    sp.add_argument("--pointer")
    sp.set_defaults(func=cmd_resolve)

    sp = sub.add_parser("pop", help="关闭一帧，并自动打印强制四段回看")
    common(sp)
    sp.add_argument("--frame", required=True)
    sp.add_argument("--terminal", choices=TERMINAL_STATUS, required=True,
                    help="done=完成 / parked=明确搁置 / escalated=升级为 issues.md 条目 / wontfix=不做")
    sp.add_argument("--note", required=True, help="结论：做了什么、判据是否达成、证据在哪")
    sp.add_argument("--spawned", action="append", help="本帧衍生的 frame_id，可重复")
    sp.add_argument("--pointers", help="JSON 对象，补充证据指针")
    sp.add_argument("--force", action="store_true", help="允许在子帧未关时越序出栈")
    sp.set_defaults(func=cmd_pop)

    sp = sub.add_parser("ensure", help="幂等启用推进栈并绑定总目标台账（须用户声明或批准申请，编排不得自动创建）")
    common(sp)
    sp.add_argument("--activation", choices=ACTIVATIONS, default=None,
                    help="启用方式（**新建栈必填**）：user_declared=用户主动声明需要任务栈；"
                         "user_approved_on_proposal=用户批准了 propose 申请卡。"
                         "auto_orchestration 是 legacy 值，只用于 --set-activation 改记既有栈的历史")
    sp.add_argument("--set-activation", action="store_true",
                    help="仅当既有栈 activation 为 pre-v3-unknown 时，允许改记为 --activation 的值"
                         "（必须显式声明，不静默改写历史）")
    sp.add_argument("--title", help="核心任务名（语义恢复的匹配素材；缺省用 campaign_id）")
    sp.add_argument("--force-new", action="store_true",
                    help="确认这是与既有 campaign 名字相近的**不同**栈，绕过 ensure 的拼写分叉防线")
    sp.set_defaults(func=cmd_ensure)

    sp = sub.add_parser("verify", help="不变量校验（违规 exit 1）")
    common(sp)
    sp.set_defaults(func=cmd_verify)

    sp = sub.add_parser("amend", help="修订未关闭帧的标题/判据/来源/指针（留痕 event_log）")
    common(sp)
    sp.add_argument("--frame", required=True)
    sp.add_argument("--title")
    sp.add_argument("--goal")
    sp.add_argument("--origin")
    sp.add_argument("--criteria", action="append", help="整组替换判据，可重复")
    sp.add_argument("--pointers", help="JSON 对象，与既有 pointers 合并")
    sp.set_defaults(func=cmd_amend)

    sp = sub.add_parser("retro", help="弯路复盘：放弃/搁置/升级/用户改道（只读）")
    common(sp)
    sp.add_argument("--tail", type=int, default=20, help="每类最多显示多少条，默认 20")
    sp.set_defaults(func=cmd_retro)

    sp = sub.add_parser("render", help="生成 Markdown 视图；--check 只校验不写")
    common(sp)
    sp.add_argument("--check", action="store_true")
    sp.set_defaults(func=cmd_render)

    sp = sub.add_parser("migrate", help="把栈（及台账与 phases/）从 scratch/workbench/ "
                                        "迁到 <workstack_root>/（默认 workstacks）")
    common(sp)
    sp.set_defaults(func=cmd_migrate)

    sp = sub.add_parser("propose", help="只读打印「推进栈启用申请卡」，不创建任何文件")
    common(sp)
    sp.add_argument("--signal", action="append", help="命中的复杂度信号（可重复）")
    sp.add_argument("--negative", action="append", help="未命中的信号（可重复，只为如实呈现）")
    sp.add_argument("--cost", help="不启用的代价（缺省用通用表述）")
    sp.set_defaults(func=cmd_propose)

    sp = sub.add_parser("stacks", help="只读列出全部任务栈（多栈共存的全局视图）")
    common(sp)
    sp.set_defaults(func=cmd_stacks)

    sp = sub.add_parser("use", help="把某个栈设为当前栈（单对话单栈单指针，切换留痕）")
    common(sp)
    sp.set_defaults(func=cmd_use)

    sp = sub.add_parser("retitle", help="改核心任务名（campaign_id 不变，引用不受影响）")
    common(sp)
    sp.add_argument("--title", required=True)
    sp.set_defaults(func=cmd_retitle)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
