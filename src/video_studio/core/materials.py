"""素材不足降级分类学 + 可追溯决策记录（3.x Phase 2-C）。

问题：镜头找不到足够匹配的真实素材时，系统**不得**静默地拿错误素材顶替、伪造命中，或产出一部
无法解释的成片。本模块给出唯一的分类与策略定义，供 EditingAgent（决策方）与验收驱动（审计方）共用。

## 一、两级字段（诊断 vs 动作）—— 必须分开看

- `insufficiency_class`（**诊断**，为什么不足）∈
    NONE / NO_CANDIDATE / LOW_MATCH / ASSET_UNUSABLE / ASSET_CONFLICT / ASSET_EXHAUSTED
- `fallback_state`（**动作**，最终怎么处理）∈
    LOCAL_INGEST（正常命中）/ THEME_FALLBACK（同主题降级）/ SOLID_COLOR_CARD（安全占位）/
    BLOCKED_FOR_HUMAN（阻断等人工补素材）
- `assembly_class`（**装配级诊断**）∈ NONE / ASSEMBLY_BLOCKED
    ASSEMBLY_BLOCKED = 已提供本地素材（material_mode=local_ingest）却**没有任何镜头**能用真实素材完成装配
    → 装配无法完成，render 必须在调用 ffmpeg 之前阻断（不产出"看起来成功"的成片）。

## 二、分类规则（确定性、按序判定）

1. 候选 = 素材池中 `match_score > 0` 的素材（分数 = 2×CJK 二元组 + 1×单字 + 2×拉丁词≥3）。
2. 候选全部不可用（解码失败/尺寸不合格）→ **ASSET_UNUSABLE**（保留 `unusable_reason`）。
3. 候选与镜头**负向约束**冲突（`style_constraint`/`description` 中的"不出现X/不得含X/no X"命中素材名）
   → **ASSET_CONFLICT**（保留命中的约束原文）。
4. 无任何候选 → **NO_CANDIDATE**。
5. 有可用候选但最高分 < `min_match_score` → **LOW_MATCH**。
6. 有可用候选且达到阈值，但全部已被其他镜头占用且策略禁止复用 → **ASSET_EXHAUSTED**。
7. 否则 → **NONE**（正常命中，`fallback_state=LOCAL_INGEST`）。

## 三、降级动作（策略可配置，默认值保持既有行为）

| 诊断 | 默认动作 | 说明 |
|---|---|---|
| NONE | LOCAL_INGEST | 正常命中 |
| LOW_MATCH | THEME_FALLBACK | 同主题降级：仍用该素材，但**明确标注**为降级（不伪装成命中），需人工知悉 |
| NO_CANDIDATE | SOLID_COLOR_CARD | 安全占位（纯色底），不伪造素材 |
| ASSET_UNUSABLE | SOLID_COLOR_CARD（先试次优可用候选） | 不可用素材**绝不**进入渲染 |
| ASSET_CONFLICT | SOLID_COLOR_CARD（跳过冲突素材） | 约束冲突素材不进入渲染 |
| ASSET_EXHAUSTED | SOLID_COLOR_CARD | 仅在复用被禁止时出现 |

任一场景落到 `BLOCKED_FOR_HUMAN`（策略指定或装配级 ASSEMBLY_BLOCKED）→ render 阻断。

## 四、禁止静默降级（代码级保证）

- 降级必定写入 `insufficiency_class` + `fallback_reason` + `selection_reason`（含分数与阈值）。
- `fallback_state` 只有 `LOCAL_INGEST` 才代表"正常命中"；降级素材一律 `THEME_FALLBACK`。
- `SOLID_COLOR_CARD` 场景 `selected_asset=None`，成片抽帧核验会确认它**不是**任一素材（占位被证实）。
- 阻断场景 `allowed_in_final_render=False`：render 直接失败，不产出成片，也不改写任务状态。

## 五、`needs_hitl` 的语义边界

`needs_hitl` 是**记录/建议**字段（供人工与后续闸门使用），**不改变**现有 HITL 闸门、任务审批顺序或
Claim 机制（Phase 2-C 明确不修改 HITL 核心）。真正的"阻断"通过 render 任务失败（FAILED→BLOCKED）实现。
"""

from __future__ import annotations

import json
import re

INSUFFICIENCY_CLASSES = ("NONE", "NO_CANDIDATE", "LOW_MATCH", "ASSET_UNUSABLE", "ASSET_CONFLICT",
                         "ASSET_EXHAUSTED")
FALLBACK_STATES = ("LOCAL_INGEST", "THEME_FALLBACK", "SOLID_COLOR_CARD", "BLOCKED_FOR_HUMAN")
ASSEMBLY_CLASSES = ("NONE", "ASSEMBLY_BLOCKED")

DEFAULT_POLICY = {
    "min_match_score": 3,                 # 低于此分视为 LOW_MATCH
    "low_match_policy": "theme_fallback",  # theme_fallback | placeholder | block
    "zero_match_policy": "placeholder",    # placeholder | block
    "unusable_policy": "placeholder",      # placeholder | block
    "conflict_policy": "placeholder",      # placeholder | block
    "exhausted_policy": "placeholder",     # placeholder | block
    "asset_reuse_policy": "prefer_unused",  # allow | prefer_unused | forbid
    "block_when_all_degraded": True,       # material_mode=local_ingest 且全场景降级 → ASSEMBLY_BLOCKED
    "min_asset_width": 320,
    "min_asset_height": 180,
    "frame_verify": True,
    "frame_match_min_corr": 0.30,
    "frame_argmax_margin": 0.15,   # 期望素材相关度允许比最高者低这么多（真实相似素材场景）
}

# 负向约束抽取：不出现X / 不得含X / 避免X / 禁止X / 不要X / no X / without X
# 捕获项可带一个后续 ASCII 词（"品牌 Logo"），并去掉"任何/所有"等前置修饰词，
# 使抽取出的约束能真正用于与素材名做子串匹配。
_NEG_PATTERNS = (
    re.compile(r"不(?:得|要|应|能)?(?:出现|包含|含|使用|带|露)\s*"
               r"([^\s，。；、,;.]{1,12}(?:\s+[A-Za-z0-9][A-Za-z0-9_\-]{0,15})?)"),
    re.compile(r"避免\s*([^\s，。；、,;.]{1,12}(?:\s+[A-Za-z0-9][A-Za-z0-9_\-]{0,15})?)"),
    re.compile(r"禁止\s*([^\s，。；、,;.]{1,12}(?:\s+[A-Za-z0-9][A-Za-z0-9_\-]{0,15})?)"),
    re.compile(r"\bno\s+([A-Za-z0-9_\- ]{2,20})", re.I),
    re.compile(r"\bwithout\s+([A-Za-z0-9_\- ]{2,20})", re.I),
)
_MODIFIER_PREFIX = re.compile(r"^(?:任何|所有|其它|其他|额外|明显|过多|再|一些|一个|the|any|all)\s*", re.I)


def _clean_constraint(term: str) -> str:
    term = _MODIFIER_PREFIX.sub("", str(term).strip()).strip()
    return term


class MaterialInsufficientError(RuntimeError):
    """素材不足导致装配无法完成（ASSEMBLY_BLOCKED / 策略阻断）——必须在渲染前阻断。"""


# ---------------- 许可合规（Phase 3-A；机械规则，不做法律判断） ----------------
LICENSE_CLASSES = ("PUBLIC_DOMAIN", "FREE_ATTRIBUTION", "RESTRICTED", "UNKNOWN")
_PD_HINTS = ("cc0", "public domain", "pd-", "pd ", "no restrictions")
_FREE_HINTS = ("cc by", "cc-by", "cc by-sa", "cc-by-sa", "attribution", "share alike")
_RESTRICTED_HINTS = ("fair use", "non-free", "nonfree", "all rights reserved", "copyright",
                     "permission", "licence required", "license required")


def classify_license(declared: str | None) -> tuple[str, bool]:
    """把提供方**声明**的许可证映射为类别。返回 (license_class, cleared)。

    只做字符串到类别的机械映射（**不猜测、不判定合法性**）：CC0/PD → PUBLIC_DOMAIN；
    CC BY* → FREE_ATTRIBUTION（可用但须署名）；fair use/non-free/all rights reserved → RESTRICTED；
    空/unknown/unchecked → UNKNOWN。
    """
    s = (declared or "").strip().lower()
    if not s or s in ("unknown", "unchecked", "n/a", "none", "-"):
        return "UNKNOWN", False
    if any(h in s for h in _RESTRICTED_HINTS):
        return "RESTRICTED", False
    if any(h in s for h in _PD_HINTS):
        return "PUBLIC_DOMAIN", True
    if any(h in s for h in _FREE_HINTS):
        return "FREE_ATTRIBUTION", True
    return "UNKNOWN", False


LOCAL_PROVIDERS = ("", "none", "local", "local_ingest")


def is_external_candidate(candidate: dict) -> bool:
    """候选是否来自**外部 provider**（= 3-A 许可门禁与署名台账的适用范围）。"""
    return str(candidate.get("provider") or "").strip().lower() not in LOCAL_PROVIDERS


def license_gate_applies(candidate: dict, require_license: bool = True) -> bool:
    """许可门禁**适用范围**：外部（provider 来源）素材。

    3-A 契约针对的是**外部素材**——它们带 provider/source_id/source_url/license 声明，
    需要署名台账与合规断言。**本地 ingest 素材**是用户自备文件（管线没有任何提供方声明
    可查，`license` 通常为 "unchecked"）：管线既不做许可判定，也不假装判定，仍原样记录
    其声明值。这把门禁限定在它能真正负责的范围内（并与冻结基线行为一致：
    Phase 2-C/2-D 的本地素材回归套件在 3-A 前后都必须通过）。
    """
    if not require_license:
        return False
    return is_external_candidate(candidate)


def license_block_reason(candidate: dict, require_license: bool = True) -> str | None:
    """候选是否因许可原因**不得入片**；返回错误码或 None。

    Phase 3-A 契约：`RESTRICTED` / `UNKNOWN` 素材不得出现在最终成片中。
    本函数是**纯判定原语**（只看候选自身的许可信息，不看来源范围）；
    适用范围由 `license_gate_applies` 决定，调用方按需组合。
    该判定在**分类阶段**（`classify_scene`）与 provider 层都执行（纵深防御）。
    """
    if not require_license:
        return None
    declared = candidate.get("license")
    klass = candidate.get("license_class") or classify_license(declared)[0]
    cleared = candidate.get("license_cleared")
    if cleared is None:
        cleared = classify_license(declared)[1]
    if klass == "RESTRICTED":
        return "ASSET_LICENSE_RESTRICTED"
    if klass == "UNKNOWN" or not cleared:
        return "ASSET_LICENSE_MISSING" if not (declared or "").strip() else "ASSET_LICENSE_UNCLEAR"
    return None


def policy_from_config(config: dict | None) -> dict:
    """从 config.editing 读取策略（缺省即默认值；非法值回落默认，不做猜测）。"""
    pol = dict(DEFAULT_POLICY)
    raw = ((config or {}).get("editing") or {})
    for k, default in DEFAULT_POLICY.items():
        if k not in raw:
            continue
        v = raw[k]
        if isinstance(default, bool):
            pol[k] = bool(v)
        elif isinstance(default, int):
            try:
                pol[k] = int(v)
            except (TypeError, ValueError):
                pass
        elif isinstance(default, float):
            try:
                pol[k] = float(v)
            except (TypeError, ValueError):
                pass
        else:
            if isinstance(v, str) and v:
                pol[k] = v
    return pol


def extract_constraints(shot: dict | None, narration: str = "") -> list[str]:
    """收集该镜头的负向约束（结构化字段优先，其次从 style_constraint/description 文本抽取）。"""
    shot = shot or {}
    out: list[str] = []
    for key in ("avoid_list", "constraints", "must_not", "forbidden"):
        v = shot.get(key)
        if isinstance(v, (list, tuple)):
            out.extend(str(x).strip() for x in v if str(x).strip())
        elif isinstance(v, str) and v.strip():
            out.extend(x.strip() for x in re.split(r"[，,;；]", v) if x.strip())
    for key in ("style_constraint", "description", "gen_prompt"):
        text = str(shot.get(key) or "")
        for pat in _NEG_PATTERNS:
            for m in pat.finditer(text):
                term = _clean_constraint(m.group(1))
                if term:
                    out.append(term)
    return list(dict.fromkeys(out))          # 去重保序


def conflict_hits(candidate: dict, constraints: list[str]) -> list[str]:
    """素材名/路径命中负向约束 → 返回命中的约束原文（大小写不敏感）。"""
    hay = "{} {}".format(candidate.get("name") or "", candidate.get("relative_path") or "").lower()
    hits = []
    for c in constraints:
        term = str(c).strip().lower()
        if term and term in hay:
            hits.append(c)
    return hits


def classify_scene(*, scene_id: str, requirement: dict, candidates: list[dict],
                   used_asset_ids: set[str], policy: dict, material_provided: bool,
                   excluded_candidates: list | None = None,
                   provider_requested: bool = False) -> dict:
    """对一个镜头做**确定性**分类与降级决策，返回完整可追溯记录。

    candidates: 每个元素含 asset_id/name/source/sha256/path/relative_path/bytes/match_score/
                matched_tokens/usable/unusable_reason/used_by_scenes
                （Phase 2-D 追加：provider/source_id/source_url/license/attribution/
                 usage_restrictions/license_cleared/needs_hitl/media_type/verified）
    excluded_candidates: Phase 2-D 被 provider 层**拒收**但本可命中的候选（如许可证未明）——
                只记录 + 置 needs_hitl，绝不参与选择，也不改变分类结果。
    """
    pol = {**DEFAULT_POLICY, **(policy or {})}
    thr = int(pol["min_match_score"])
    constraints = list(requirement.get("constraints") or [])

    scored = [c for c in candidates if int(c.get("match_score") or 0) > 0]
    # 排序口径与 Phase 2-A/B 保持一致（镜头分 → retrieval 分 → asset_id），
    # 保证 Phase 2-C 只**新增**分类与追溯，不改变既有素材分配结果。
    scored.sort(key=lambda c: (-int(c.get("match_score") or 0),
                               -int(c.get("retrieval_match_score") or 0),
                               c.get("asset_id") or ""))
    # Phase 3-A：许可门禁在**分类阶段**执行（纵深防御）——外部素材中受限/未知许可证者不可用。
    # 适用范围由 license_gate_applies 决定：本地自带素材不在门禁范围内（见该函数说明）。
    require_lic = bool(pol.get("license_required", True))
    for c in scored:
        if not license_gate_applies(c, require_license=require_lic):
            continue
        block = license_block_reason(c, require_license=require_lic)
        if block:
            c["usable"] = False
            c["unusable_reason"] = block
    usable = [c for c in scored if c.get("usable", True)]
    usable_unused = [c for c in usable if c.get("asset_id") not in used_asset_ids]
    conflict_free = [c for c in usable if not conflict_hits(c, constraints)]
    conflict_free_unused = [c for c in conflict_free if c.get("asset_id") not in used_asset_ids]
    best = scored[0] if scored else None
    best_usable = usable[0] if usable else None

    # ---- 逐类判定 ----
    klass, pick, fallback, action = "NONE", None, "LOCAL_INGEST", ""
    reason = ""
    if not scored:
        klass = "NO_CANDIDATE"
    elif not usable:
        klass = "ASSET_UNUSABLE"
    elif all(conflict_hits(c, constraints) for c in usable):
        klass = "ASSET_CONFLICT"
    elif best_usable and int(best_usable["match_score"]) < thr:
        klass = "LOW_MATCH"
    else:
        pool = conflict_free
        if pol["asset_reuse_policy"] == "prefer_unused":
            pool = conflict_free_unused or conflict_free
        elif pol["asset_reuse_policy"] == "forbid":
            pool = conflict_free_unused
        if pool:
            pick = pool[0]
            klass = "NONE"
        else:
            klass = "ASSET_EXHAUSTED"

    # ---- 由诊断映射到降级动作（策略可配）----
    if klass == "NONE":
        fallback, action = "LOCAL_INGEST", "正常命中"
        reason = "关键词命中 {} 个（素材分={} ≥ 阈值 {}）".format(
            len(pick.get("matched_tokens") or []), pick.get("match_score"), thr)
    elif klass == "LOW_MATCH" and pol["low_match_policy"] == "theme_fallback":
        pick = best_usable
        fallback = "THEME_FALLBACK"
        action = "同主题候选降级（明确标注，不视为正常命中）"
        reason = "最高素材分={} < 阈值 {}：{}".format(best_usable.get("match_score"), thr,
                                                   "；".join(best_usable.get("matched_tokens") or [])
                                                   or "仅有零星字面重叠")
    else:
        pol_key = {"NO_CANDIDATE": "zero_match_policy", "LOW_MATCH": "low_match_policy",
                   "ASSET_UNUSABLE": "unusable_policy", "ASSET_CONFLICT": "conflict_policy",
                   "ASSET_EXHAUSTED": "exhausted_policy"}[klass]
        if pol.get(pol_key) == "block":
            fallback = "BLOCKED_FOR_HUMAN"
            action = "按策略阻断，等待人工补充素材"
        else:
            fallback = "SOLID_COLOR_CARD"
            action = "安全占位（纯色底 + 字幕），不伪造素材"
        reason = {
            "NO_CANDIDATE": "无候选素材命中（关键词交集为空）",
            "LOW_MATCH": "最高素材分={} < 阈值 {}（策略={}）".format(
                best_usable.get("match_score") if best_usable else 0, thr, pol["low_match_policy"]),
            "ASSET_UNUSABLE": "候选素材不可用：{}".format(
                "；".join(sorted({str(c.get("unusable_reason")) for c in scored}))),
            "ASSET_CONFLICT": "候选素材与镜头约束冲突：{}".format("；".join(constraints)),
            "ASSET_EXHAUSTED": "候选素材已被其他镜头占用且复用策略={}（禁止复用）".format(
                pol["asset_reuse_policy"]),
        }[klass]

    if pick is not None:
        selection_reason = "{}；选定 {}（素材分={}，命中={}）".format(
            reason, pick.get("name"), pick.get("match_score"),
            "/".join((pick.get("matched_tokens") or [])[:6]))
    else:
        selection_reason = "{}；未选择任何素材（selected_asset=null）".format(reason)

    needs_hitl = fallback in ("THEME_FALLBACK", "BLOCKED_FOR_HUMAN") or (
        fallback == "SOLID_COLOR_CARD" and (material_provided or provider_requested))
    # Phase 2-D：被 provider 层拒收的候选（许可证未明等）出现在本镜头查询里 → 必须人工知悉
    excluded = list(excluded_candidates or [])
    license_pending = any(
        (e.get("error_code") or "").startswith("ASSET_LICENSE") for e in excluded)
    if excluded or license_pending:
        needs_hitl = True
    return {
        "scene_id": scene_id,
        # ---- 可追溯（需求 4）----
        "original_requirement": requirement,
        "candidates": [{
            "asset_id": c.get("asset_id"), "name": c.get("name"), "source": c.get("source"),
            "sha256": c.get("sha256"), "path": c.get("path"),
            "relative_path": c.get("relative_path"), "bytes": c.get("bytes"),
            "match_score": c.get("match_score"), "matched_tokens": c.get("matched_tokens"),
            "usable": bool(c.get("usable", True)), "unusable_reason": c.get("unusable_reason"),
            "width": c.get("width"), "height": c.get("height"),
            "used_by_scenes": sorted(c.get("used_by_scenes") or []),
            "conflict_hits": conflict_hits(c, constraints),
            # ---- Phase 2-D：来源与许可 ----
            "provider": c.get("provider"), "source_id": c.get("source_id"),
            "source_url": c.get("source_url"), "license": c.get("license"),
            "license_class": c.get("license_class"),
            "attribution": c.get("attribution"),
            "usage_restrictions": c.get("usage_restrictions"),
            "license_cleared": c.get("license_cleared"), "verified": c.get("verified"),
            "media_type": c.get("media_type"),
        } for c in scored],
        "candidates_total": len(scored),
        # Phase 2-D：被拒候选（不参与选择、不改变分类；仅供追溯与 HITL）
        "excluded_candidates": excluded,
        "license_pending": bool(license_pending),
        "insufficiency_class": klass,
        "fallback_state": fallback,
        "fallback_action": action,
        "fallback_reason": reason,
        "selected_asset": ({k: pick.get(k) for k in
                            ("asset_id", "name", "source", "sha256", "path", "relative_path",
                             "bytes", "retrieval_match_score", "width", "height",
                             "provider", "source_id", "source_url", "license",
                             "license_class", "attribution",
                             "usage_restrictions", "license_cleared")}
                           if pick is not None else None),
        "selection_reason": selection_reason,
        "needs_hitl": bool(needs_hitl),
        "allowed_in_final_render": fallback != "BLOCKED_FOR_HUMAN",
    }


def assembly_class(scenes: list[dict], material_provided: bool, policy: dict | None = None) -> dict:
    """装配级诊断。

    ASSEMBLY_BLOCKED 的判据 = 已提供本地素材（material_mode=local_ingest）却**没有任何镜头**
    能把真实素材放上屏（全部 `selected_asset is None`）→ 装配无法完成，render 必须阻断。
    注意：`THEME_FALLBACK`（同主题降级）**有真实素材上屏**，属于"降级但可完成"，不判阻断。
    """
    pol = {**DEFAULT_POLICY, **(policy or {})}
    normal = [s for s in scenes if s.get("fallback_state") == "LOCAL_INGEST"]
    material_driven = [s for s in scenes if s.get("selected_asset")]
    counts: dict[str, int] = {}
    for s in scenes:
        counts[s.get("insufficiency_class")] = counts.get(s.get("insufficiency_class"), 0) + 1
    blocked_by_policy = [s["scene_id"] for s in scenes
                         if s.get("allowed_in_final_render") is False]
    klass, reason = "NONE", ""
    if blocked_by_policy:
        klass = "ASSEMBLY_BLOCKED"
        reason = "策略指定阻断的场景：{}".format(blocked_by_policy)
    elif material_provided and not material_driven and scenes and pol["block_when_all_degraded"]:
        klass = "ASSEMBLY_BLOCKED"
        reason = ("已提供素材（本地素材索引或外部 provider 返回过候选）但 {} 个镜头全部无法把真实素材上屏"
                  "（selected_asset 全为 null），装配无法完成".format(len(scenes)))
    return {"assembly_class": klass, "assembly_reason": reason,
            "class_counts": counts, "normal_scenes": [s["scene_id"] for s in normal],
            "material_driven_scenes": [s["scene_id"] for s in material_driven],
            "degraded_scenes": [s["scene_id"] for s in scenes
                                if s.get("fallback_state") != "LOCAL_INGEST"],
            "blocked_scenes": blocked_by_policy}


def insufficient_message(detail: dict) -> str:
    """统一的阻断文案（明确错误码 [ASSET_INSUFFICIENT]）。"""
    return "[ASSET_INSUFFICIENT] {}".format(json.dumps(detail, ensure_ascii=False))


def frame_corr(a, b) -> float:
    """48×48 灰度 Pearson 相关（与验收驱动同一口径）。"""
    import numpy as np
    a = a - a.mean()
    b = b - b.mean()
    d = float(np.sqrt((a ** 2).sum()) * np.sqrt((b ** 2).sum()))
    return float((a * b).sum() / d) if d else 0.0


def gray48(path) -> "object":
    """读图为 48×48 灰度 ndarray（供成片抽帧核验）。"""
    import numpy as np
    from PIL import Image
    with Image.open(path) as im:
        return np.asarray(im.convert("L").resize((48, 48)), dtype=np.float64)
