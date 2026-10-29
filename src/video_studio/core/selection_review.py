"""4.x Phase 4-C：人审候选替换的**核心规则**（纯函数 + 只读查询；不自动选材）。

机制（复用既有能力，不新增表/列）：
  · 人工选定先落到既有 `decisions` 表（`node="selection_override"`、`state="approved"`），
    并同步写既有 `changelog`（`human_confirmed=1`）；
  · 渲染（`editing`）读取每个镜头**最新一条已批准**的人工选定，校验它必须来自该镜头的
    **已验证候选池**、可用、且通过许可门禁 → 才使用，并把 `selection_source="human_review"` 与
    `human_selection`（decision_id / decided_by / reason / decided_at）写进素材时间轴；
  · 校验不通过 → **fail-closed**（`HUMAN_SELECTION_*` 错误码 → 渲染 BLOCKED），
    **绝不**静默回退到自动选材，也**不会**"随便选一个凑通过"。

**本模块不改动任何 4-A/4-B 判定逻辑，也不改动素材验证/许可门禁规则**：校验直接复用
`core.materials` 的 `license_gate_applies` / `license_block_reason`。
"""
from __future__ import annotations

from ..core.materials import license_block_reason, license_gate_applies  # noqa: F401

SELECTION_NODE = "selection_override"
SELECTION_STATE = "approved"

# `selected_asset` 的键集合必须与 `core.materials.classify_scene` 的投影保持一致
# （测试 H7 会断言两者一致，防止漂移）
SELECTION_KEYS = ("asset_id", "name", "source", "sha256", "path", "relative_path", "bytes",
                  "retrieval_match_score", "width", "height", "provider", "source_id",
                  "source_url", "license", "license_class", "attribution",
                  "usage_restrictions", "license_cleared")


class HumanSelectionError(Exception):
    """人工选定不可用 → 渲染必须 fail-closed（错误码见 `code`）。"""

    def __init__(self, code: str, detail: str = ""):
        super().__init__("[{}] {}".format(code, detail))
        self.code = code
        self.detail = detail


def selection_projection(candidate: dict) -> dict:
    """把候选记录投影成 `selected_asset`（与自动选材同构）。"""
    return {k: candidate.get(k) for k in SELECTION_KEYS}


def validate_choice(candidates: list[dict], asset_id: str, scene_id: str = "") -> tuple[bool, str, str]:
    """校验"人工选定的素材"是否可用于该镜头。返回 (ok, code, detail)；**不修改任何东西**。

    错误码：
      · `HUMAN_SELECTION_EMPTY_POOL`      该镜头没有任何候选（池为空）→ 必须 BLOCKED
      · `HUMAN_SELECTION_NOT_IN_POOL`     选定素材不在该镜头的候选池里
      · `HUMAN_SELECTION_UNUSABLE`        候选存在但不可用（解码/尺寸等）
      · `HUMAN_SELECTION_LICENSE_BLOCKED` 外部素材许可未清（RESTRICTED/UNKNOWN）
    """
    if not candidates:
        return False, "HUMAN_SELECTION_EMPTY_POOL", "镜头 {} 无任何候选（池为空）".format(scene_id)
    hit = next((c for c in candidates if c.get("asset_id") == asset_id), None)
    if hit is None:
        return (False, "HUMAN_SELECTION_NOT_IN_POOL",
                "素材 {} 不在镜头 {} 的候选池中（可选：{}）".format(
                    asset_id, scene_id, [c.get("asset_id") for c in candidates]))
    if not hit.get("usable", True):
        return (False, "HUMAN_SELECTION_UNUSABLE",
                "素材 {} 不可用：{}".format(asset_id, hit.get("unusable_reason")))
    if license_gate_applies(hit, require_license=True):
        block = license_block_reason(hit, require_license=True)
        if block:
            return (False, "HUMAN_SELECTION_LICENSE_BLOCKED",
                    "素材 {} 许可未清（{}，class={}）".format(asset_id, block,
                                                             hit.get("license_class")))
    return True, "", "ok"


def latest_selections_from_conn(conn, project_id: str) -> dict[str, dict]:
    """读取该项目**每个镜头最新一条已批准**的人工选定（只读 SELECT）。

    返回 {scene_id: {asset_id, decision_id, decided_by, reason, decided_at}}；无决定 → 空 dict。
    同一镜头多条时取 `created_at` 最新的一条。

    实现要点：用**位置索引**读取（列顺序 decision_id, made_by, state, rationale,
    artifact_snapshot, created_at），因此无论调用方是否设置 `row_factory=sqlite3.Row` 都能工作
    （早期版本用列名索引，遇到普通连接会静默返回空——由测试 H2c 抓到）。
    """
    out: dict[str, dict] = {}
    try:
        rows = conn.execute(
            "select decision_id, made_by, state, rationale, artifact_snapshot, created_at "
            "from decisions where project_id=? and node=? order by created_at",
            (project_id, SELECTION_NODE)).fetchall()
    except Exception:                                    # noqa: BLE001 —— 表/列缺失即视为"无人工决定"
        return {}
    for r in rows:
        try:
            snap = r[4]
            snap = json_loads(snap) if isinstance(snap, str) else (snap or {})
        except Exception:                                # noqa: BLE001
            continue
        if not isinstance(snap, dict):
            continue
        scene = snap.get("scene_id")
        asset = snap.get("asset_id")
        if not scene or not asset:
            continue
        if str(r[2]) != SELECTION_STATE:
            continue
        out[scene] = {"asset_id": asset, "decision_id": r[0],
                      "decided_by": r[1], "reason": r[3],
                      "decided_at": r[5]}
    return out


def json_loads(s: str):
    import json
    return json.loads(s)


def decision_row(project_id: str, scene_id: str, asset_id: str, decided_by: str, reason: str,
                 before: dict | None = None, after: dict | None = None,
                 render_task: str | None = None, artifact_id: str | None = None) -> dict:
    """构造 `decisions` 表的一行（人工选定的**证据**；由调用方写入既有表）。"""
    from ..core.engine import new_id

    return {
        "decision_id": new_id("d"),
        "project_id": project_id,
        "node": SELECTION_NODE,
        "made_by": decided_by,
        "state": SELECTION_STATE,
        "rationale": reason,
        "artifact_snapshot": {
            "scene_id": scene_id, "asset_id": asset_id,
            "before_asset_id": (before or {}).get("asset_id"),
            "before_asset_name": (before or {}).get("name"),
            "after_asset_name": (after or {}).get("name"),
            "render_task": render_task, "render_artifact": artifact_id,
            "source": "4-C human review（人工明确选定；非自动改选材）",
        },
    }
