# -*- coding: utf-8 -*-
"""P7-3：**视觉素材多样性度量**（只读、确定性、零网络、零 LLM）。

`AssetIndex + material_timeline → Diversity Metrics → Coverage Report`

三件事必须分开（不得混为一谈、不得当作质量分）
------------------------------------------------
1. **identity diversity**（身份多样性）：有多少**互不相同**的资产/感知家族/来源家族；
2. **reuse distribution**（复用分布）：这些身份在场景上如何分布（集中度）；
3. **semantic coverage**（语义覆盖）：需求字段有多少**可证明**（P7-1 的 DERIVABLE），
   以及**核心语义字段是否根本不可推导**（P7-1 明确 NOT_DERIVABLE ⇒ 本阶段**不得**生成）。

边界与失败语义
--------------
* `UNKNOWN`         —— 无法确定（不得当 0/False）
* `NOT_AVAILABLE`   —— 该类别不适用（如图像无时长）
* `NOT_ASSESSABLE`  —— 当前数据无法可靠计算该指标（例如 timeline 中的 asset 无法映射到索引）
禁止：静默回落、猜测、用文件名推断语义、用路径推断 license、用"资产数量"直接宣称视觉质量提高。
"""
from __future__ import annotations

from .asset_candidate import UNKNOWN
from .visual_requirement import canonical, sha256_text

SCHEMA = "asset-diversity-v1"
VERSION = 1

NOT_ASSESSABLE = "NOT_ASSESSABLE"

#: 本阶段**禁止**生成的语义字段（P7-1 明确 NOT_DERIVABLE）
FORBIDDEN_SEMANTIC_FIELDS = ("subject", "action", "object", "environment", "concept")

# ------------------------------------------------------------------ 指标规格（machine-readable）
METRIC_SPEC = {
    # ---- A. Asset-level ----
    "unique_assets": {
        "group": "A_asset_level", "unit": "count",
        "why": "身份多样性基线：时间轴上出现过多少个**互不相同**的资产身份",
        "formula": "|{stable asset_id : 出现在 timeline}|",
        "inputs": ["material_timeline.selected_asset.asset_id", "asset_index.legacy_asset_ids"],
        "edge_cases": ["无法映射到索引的 asset ⇒ 该条目计入 unmapped_scenes，指标标 NOT_ASSESSABLE"],
    },
    "unique_perceptual_families": {
        "group": "A_asset_level", "unit": "count",
        "why": "不同文件 ≠ 不同视觉内容：按 dHash 家族去重后的真实视觉身份数",
        "formula": "|{perceptual_family_id : 该家族至少有一个在时间轴上的资产}|",
        "inputs": ["asset_index.relationships.perceptual_families"],
        "edge_cases": ["家族信息不可用（dHash UNKNOWN）的资产不计入，另记 family_unknown_assets"],
    },
    "unique_source_families": {
        "group": "A_asset_level", "unit": "count",
        "why": "来源集中度：素材是否来自同一起源（同 provider/source_id 视为同一来源家族）",
        "formula": "|{source_family_id}|；source_family_id 规则见 SOURCE_FAMILY_RULE",
        "inputs": ["asset_index.candidates.provider/source_id/source_type"],
        "edge_cases": ["provider=UNKNOWN ⇒ 家族 id 为 sf-UNKNOWN（**保留** UNKNOWN，不猜来源）"],
    },
    "asset_reuse_histogram": {
        "group": "A_asset_level", "unit": "map",
        "why": "复用分布的形状（多少资产被用 1 次 / 2 次 / …）",
        "formula": "{reuse_count: 资产个数}，reuse_count = 使用该资产的场景数",
        "inputs": ["timeline 场景→资产映射"],
        "edge_cases": ["空时间轴 ⇒ {}"],
    },
    "max_asset_reuse": {
        "group": "A_asset_level", "unit": "scenes",
        "why": "最严重的单资产复用程度",
        "formula": "max(该资产被多少场景使用)",
        "inputs": ["timeline 场景→资产映射"],
        "edge_cases": ["空时间轴 ⇒ NOT_ASSESSABLE"],
    },
    "max_family_reuse": {
        "group": "A_asset_level", "unit": "scenes",
        "why": "最严重的**视觉家族**复用程度（比单资产更能反映画面单调）",
        "formula": "max(该感知家族被多少场景使用)",
        "inputs": ["timeline + asset_index 家族"],
        "edge_cases": ["家族 UNKNOWN 的资产不参与，另记 family_unknown_assets"],
    },
    # ---- B. Scene-level ----
    "scene_count": {"group": "B_scene_level", "unit": "count",
                    "why": "时间轴场景数（度量的分母）",
                    "formula": "len(timeline)", "inputs": ["timeline"],
                    "edge_cases": ["0 ⇒ 所有比例类指标 NOT_ASSESSABLE"]},
    "scenes_with_unique_asset": {
        "group": "B_scene_level", "unit": "count",
        "why": "独享素材的场景数（视觉独立性最强的部分）",
        "formula": "|{场景 : 其资产仅被该场景使用}|", "inputs": ["timeline"],
        "edge_cases": ["同资产被同场景多次使用不重复计数（场景为单位）"]},
    "scenes_reusing_asset": {
        "group": "B_scene_level", "unit": "count",
        "why": "与其他场景共享素材的场景数",
        "formula": "scene_count - scenes_with_unique_asset", "inputs": ["timeline"],
        "edge_cases": ["恒等于 scene_count - scenes_with_unique_asset（定义式）"]},
    "scene_asset_reuse_rate": {
        "group": "B_scene_level", "unit": "ratio",
        "why": "共享素材的场景占比（0=每场景独享，1=全片共享）",
        "formula": "scenes_reusing_asset / scene_count", "inputs": ["timeline"],
        "edge_cases": ["scene_count=0 ⇒ NOT_ASSESSABLE"]},
    "scene_family_reuse_rate": {
        "group": "B_scene_level", "unit": "ratio",
        "why": "与其他场景共享**视觉家族**的场景占比（感知层面的单调度）",
        "formula": "|{场景 : 其家族被 ≥2 场景使用}| / scene_count", "inputs": ["timeline", "家族"],
        "edge_cases": ["家族 UNKNOWN 的场景不计入分子，另记 family_unknown_scenes"]},
    # ---- C. Concentration ----
    "asset_hhi": {
        "group": "C_concentration", "unit": "index(0..1)",
        "why": "资产复用集中度（HHI）：1 表示全部场景用同一资产，1/n 表示完全均分",
        "formula": "Σ_i (scenes_i / scene_count)^2，i 遍历资产",
        "inputs": ["timeline"], "edge_cases": ["scene_count=0 或无资产 ⇒ NOT_ASSESSABLE"]},
    "source_family_hhi": {
        "group": "C_concentration", "unit": "index(0..1)",
        "why": "来源集中度（HHI）：高值表示全部素材来自同一起源",
        "formula": "Σ_j (scenes_j / scene_count)^2，j 遍历 source_family",
        "inputs": ["timeline", "source_family_id"],
        "edge_cases": ["provider UNKNOWN 归入 sf-UNKNOWN（保留未知）"]},
    "max_asset_share": {
        "group": "C_concentration", "unit": "ratio",
        "why": "单一资产最大占比（比 HHI 更直观；与 DQ-2 的 max_asset_share 口径一致但**独立计算**）",
        "formula": "max_i(scenes_i) / scene_count", "inputs": ["timeline"],
        "edge_cases": ["scene_count=0 ⇒ NOT_ASSESSABLE"]},
    # ---- D. Independence / coverage ----
    "asset_identity_coverage": {
        "group": "D_independence", "unit": "ratio(0..1]",
        "why": "身份层面的独立性上限：1.0 = 每个场景都有互不相同的资产身份",
        "formula": "unique_assets / scene_count", "inputs": ["timeline"],
        "edge_cases": ["scene_count=0 ⇒ NOT_ASSESSABLE"]},
    "perceptual_family_coverage": {
        "group": "D_independence", "unit": "ratio(0..1]",
        "why": "**视觉内容**层面的独立性（不同文件可能同家族，故此值 ≤ identity 覆盖）",
        "formula": "unique_perceptual_families / scene_count", "inputs": ["timeline", "家族"],
        "edge_cases": ["家族 UNKNOWN 时偏低但**不得**用文件数替代"]},
    "source_family_coverage": {
        "group": "D_independence", "unit": "ratio(0..1]",
        "why": "来源层面的独立性（同一起源的多张图不构成来源独立）",
        "formula": "unique_source_families / scene_count", "inputs": ["timeline", "source 家族"],
        "edge_cases": ["本地自备素材全部归入 sf-local_ingest（同一来源家族）"]},
    # ---- E. Semantic coverage（只统计，不生成） ----
    "requirements_total": {"group": "E_semantic_coverage", "unit": "count",
                           "why": "P7-1 需求条数（分母）", "formula": "len(requirements)",
                           "inputs": ["visual_requirements.json"], "edge_cases": ["缺失 ⇒ NOT_ASSESSABLE"]},
    "requirement_status_counts": {"group": "E_semantic_coverage", "unit": "map",
                                  "why": "需求整体可推导状态分布",
                                  "formula": "{status: count}", "inputs": ["visual_requirements.json"],
                                  "edge_cases": ["空 ⇒ NOT_ASSESSABLE"]},
    "field_derivable_counts": {"group": "E_semantic_coverage", "unit": "map",
                               "why": "逐字段**可证明**（DERIVABLE）数量",
                               "formula": "{field: count(status=DERIVABLE)}",
                               "inputs": ["visual_requirements.json.field_status"],
                               "edge_cases": ["缺失字段不计入"]},
    "field_not_derivable_counts": {"group": "E_semantic_coverage", "unit": "map",
                                   "why": "逐字段不可推导数量（**不得**当作匹配成功）",
                                   "formula": "{field: count(status=NOT_DERIVABLE)}",
                                   "inputs": ["visual_requirements.json.field_status"],
                                   "edge_cases": ["核心五字段必然全 NOT_DERIVABLE"]},
    "visual_goal_coverage": {"group": "E_semantic_coverage", "unit": "ratio",
                             "why": "画面意图可用的需求占比（P7-4 relevance 的前提）",
                             "formula": "count(visual_goal DERIVABLE) / requirements_total",
                             "inputs": ["visual_requirements.json"], "edge_cases": ["无需求 ⇒ NOT_ASSESSABLE"]},
    "expected_kind_coverage": {"group": "E_semantic_coverage", "unit": "ratio",
                               "why": "媒体种类要求可用占比（准入必要条件）",
                               "formula": "count(expected_kind DERIVABLE) / requirements_total",
                               "inputs": ["visual_requirements.json"], "edge_cases": ["同上"]},
    "query_coverage": {"group": "E_semantic_coverage", "unit": "ratio",
                       "why": "检索词可用占比（P7-5 获取的前提；无拉丁 token 时必然缺失）",
                       "formula": "count(queries_en DERIVABLE) / requirements_total",
                       "inputs": ["visual_requirements.json"], "edge_cases": ["同上"]},
    "semantic_core_coverage": {
        "group": "E_semantic_coverage", "unit": "NOT_ASSESSABLE",
        "why": "核心语义（subject/action/object/environment/concept）覆盖 —— P7-1 已判定"
               "**当前输入不可推导**，本阶段**不得生成**",
        "formula": "NOT_ASSESSABLE（P7-1 全 NOT_DERIVABLE ⇒ 无可用输入）",
        "inputs": ["visual_requirements.json（只读）"],
        "edge_cases": ["**禁止**用文件名/路径/旁白猜测填充该字段"]},
}

SOURCE_FAMILY_RULE = {
    "id": "source-family-v1",
    "definition": "source_family_id = 'sf-' + (provider if provider 已知 else 'UNKNOWN')"
                  " + ('|' + source_id if source_id 已知 else '|UNKNOWN')",
    "local": "provider ∈ {local, local_ingest, none, ''} ⇒ 'sf-local_ingest'",
    "unknown": "provider == UNKNOWN ⇒ 'sf-UNKNOWN'（**保留** UNKNOWN，不猜来源）",
    "forbidden": ["不得由 URL 字符串推断 source/provider", "不得由路径推断 license 或来源",
                  "不得合并不同 source_id 为同一家族（除非 provider 相同且 source_id 均缺失）"],
    "deterministic": True,
    "does_not_modify_p7_2_artifact": True,
}

LOCAL_PROVIDERS = ("local", "local_ingest", "none", "")


def source_family_of(candidate: dict) -> str:
    """稳定 source-family id（规则见 SOURCE_FAMILY_RULE）。"""
    prov = candidate.get("provider") or UNKNOWN
    sid = candidate.get("source_id") or UNKNOWN
    if prov == UNKNOWN:
        return "sf-UNKNOWN"
    if str(prov).strip().lower() in LOCAL_PROVIDERS:
        return "sf-local_ingest"
    return "sf-{}|{}".format(prov, sid if sid != UNKNOWN else UNKNOWN)


def _hhi(shares: list[float]) -> float | None:
    if not shares:
        return None
    return round(sum(s * s for s in shares), 6)


def family_of(asset_id: str, families: list[dict]) -> str:
    for f in families:
        if asset_id in f.get("members", []):
            return f["family_id"]
    return UNKNOWN


# ------------------------------------------------------------------ 主测量
def measure(*, timeline_rows: list[dict], index: dict, requirements: dict | None,
            scope_label: str, scope_note: str = "") -> dict:
    """按 §A–§E 计算指标。`timeline_rows` = [{scene_id, asset_id(可为 legacy)}]。"""
    cands = {c["asset_id"]: c for c in (index.get("candidates") or [])}
    legacy = {}
    for c in cands.values():
        for lid in c.get("legacy_asset_ids") or []:
            legacy[lid] = c["asset_id"]
    fams = (index.get("relationships") or {}).get("perceptual_families") or []

    mapped, unmapped = [], []
    for r in timeline_rows:
        aid = r.get("asset_id")
        stable = aid if aid in cands else legacy.get(aid)
        if stable is None and r.get("sha256"):
            stable = next((c["asset_id"] for c in cands.values()
                           if c["sha256"] == r["sha256"]), None)
        if stable is None:
            unmapped.append({"scene_id": r.get("scene_id"), "asset_id": aid})
        else:
            mapped.append({"scene_id": r.get("scene_id"), "asset_id": stable})

    scene_count = len(timeline_rows)
    use_count: dict[str, int] = {}
    for m in mapped:
        use_count[m["asset_id"]] = use_count.get(m["asset_id"], 0) + 1
    fam_use: dict[str, int] = {}
    fam_unknown_assets, fam_unknown_scenes = [], []
    for aid, n in use_count.items():
        fid = family_of(aid, fams)
        if fid == UNKNOWN:
            fam_unknown_assets.append(aid)
            fam_unknown_scenes.append(n)
            continue
        fam_use[fid] = fam_use.get(fid, 0) + n
    sf_use: dict[str, int] = {}
    for aid, n in use_count.items():
        sf = source_family_of(cands[aid]) if aid in cands else "sf-UNKNOWN"
        sf_use[sf] = sf_use.get(sf, 0) + n

    hist: dict[str, int] = {}
    for n in use_count.values():
        hist[str(n)] = hist.get(str(n), 0) + 1
    unique_assets = len(use_count)
    unique_fams = len(fam_use)
    unique_sfs = len(sf_use)
    unique_scenes = sum(1 for aid, n in use_count.items() if n == 1)
    reuse_scenes = scene_count - unique_scenes
    fam_reuse_scenes = sum(n for fid, n in fam_use.items() if n >= 2)
    assessable = (scene_count > 0 and not unmapped and mapped)
    A = {
        "unique_assets": unique_assets,
        "unique_perceptual_families": unique_fams,
        "unique_source_families": unique_sfs,
        "asset_reuse_histogram": {k: hist[k] for k in sorted(hist, key=int)},
        "max_asset_reuse": max(use_count.values()) if use_count else NOT_ASSESSABLE,
        "max_family_reuse": max(fam_use.values()) if fam_use else NOT_ASSESSABLE,
        "family_unknown_assets": sorted(fam_unknown_assets),
        "status": "OK" if assessable else NOT_ASSESSABLE,
    }
    B = {
        "scene_count": scene_count,
        "scenes_with_unique_asset": unique_scenes,
        "scenes_reusing_asset": reuse_scenes,
        "scene_asset_reuse_rate": round(reuse_scenes / scene_count, 6) if assessable else None,
        "scene_family_reuse_rate": round(fam_reuse_scenes / scene_count, 6) if assessable else None,
        "family_unknown_scenes": fam_unknown_scenes,
        "status": "OK" if assessable else NOT_ASSESSABLE,
    }
    if assessable:
        a_shares = [n / scene_count for n in use_count.values()]
        sf_shares = [n / scene_count for n in sf_use.values()]
        C = {"asset_hhi": _hhi(a_shares), "source_family_hhi": _hhi(sf_shares),
             "max_asset_share": round(max(a_shares), 6),
             "asset_shares": {aid: round(n / scene_count, 6)
                              for aid, n in sorted(use_count.items())},
             "source_family_shares": {k: round(v / scene_count, 6)
                                      for k, v in sorted(sf_use.items())},
             "status": "OK"}
        D = {"asset_identity_coverage": round(unique_assets / scene_count, 6),
             "perceptual_family_coverage": round(unique_fams / scene_count, 6),
             "source_family_coverage": round(unique_sfs / scene_count, 6),
             "note": "不同文件 ≠ 不同视觉内容：三者按 identity→perceptual→source 逐层收紧",
             "status": "OK"}
    else:
        C = {"asset_hhi": None, "source_family_hhi": None, "max_asset_share": None,
             "asset_shares": {}, "source_family_shares": {}, "status": NOT_ASSESSABLE}
        D = {"asset_identity_coverage": None, "perceptual_family_coverage": None,
             "source_family_coverage": None, "status": NOT_ASSESSABLE}
    E = _semantic(requirements)
    reuse_note = {
        "identity_diversity": {
            "unique_assets": unique_assets, "unique_perceptual_families": unique_fams,
            "unique_source_families": unique_sfs,
            "reading": "身份层面互不相同的资产/家族/来源数量（与场景数无关）"},
        "reuse_distribution": {
            "scene_count": scene_count, "asset_reuse_histogram": A["asset_reuse_histogram"],
            "max_asset_reuse": A["max_asset_reuse"], "asset_hhi": C["asset_hhi"],
            "scene_asset_reuse_rate": B["scene_asset_reuse_rate"],
            "reading": "同样多的身份，在**更多场景**上分布时必然出现复用（分布问题，非身份问题）"},
        "semantic_coverage": {
            "visual_goal_coverage": E.get("visual_goal_coverage"),
            "query_coverage": E.get("query_coverage"),
            "semantic_core_coverage": E.get("semantic_core_coverage"),
            "reading": "相关性/语义是否被满足**无法**由当前数据判定（核心语义字段 NOT_DERIVABLE）"},
    }
    return {"scope": scope_label, "scope_note": scope_note,
            "mapping": {"mapped_scenes": len(mapped), "unmapped_scenes": unmapped,
                        "status": "OK" if not unmapped else NOT_ASSESSABLE},
            "A_asset_level": A, "B_scene_level": B, "C_concentration": C,
            "D_independence": D, "E_semantic_coverage": E,
            "three_axis_summary": reuse_note}


def _semantic(req: dict | None) -> dict:
    """§E：只统计 P7-1 已有字段；**不生成**核心语义。"""
    base = {"requirements_total": NOT_ASSESSABLE, "requirement_status_counts": None,
            "field_derivable_counts": None, "field_not_derivable_counts": None,
            "visual_goal_coverage": None, "expected_kind_coverage": None, "query_coverage": None,
            "semantic_core_coverage": NOT_ASSESSABLE,
            "semantic_core_fields": list(FORBIDDEN_SEMANTIC_FIELDS),
            "semantic_core_reason": "P7-1 判定这五个字段在当前输入中 NOT_DERIVABLE ⇒ "
                                    "本阶段不得生成、不得当作匹配成功",
            "semantic_match_claimed": False,
            "status": NOT_ASSESSABLE}
    reqs = ((req or {}).get("requirements") or [])
    if not reqs:
        return base
    total = len(reqs)
    st: dict[str, int] = {}
    deriv: dict[str, int] = {}
    nond: dict[str, int] = {}
    for r in reqs:
        st[r["status"]] = st.get(r["status"], 0) + 1
        for f, meta in (r.get("field_status") or {}).items():
            if meta["status"] == "DERIVABLE":
                deriv[f] = deriv.get(f, 0) + 1
            else:
                nond[f] = nond.get(f, 0) + 1
    cov = lambda f: round(deriv.get(f, 0) / total, 6)          # noqa: E731
    return {"requirements_total": total, "requirement_status_counts": st,
            "field_derivable_counts": {k: deriv[k] for k in sorted(deriv)},
            "field_not_derivable_counts": {k: nond[k] for k in sorted(nond)},
            "visual_goal_coverage": cov("visual_goal"),
            "expected_kind_coverage": cov("expected_kind"),
            "query_coverage": cov("queries_en"),
            "semantic_core_coverage": NOT_ASSESSABLE,
            "semantic_core_fields": list(FORBIDDEN_SEMANTIC_FIELDS),
            "semantic_core_reason": "P7-1 判定这五个字段在当前输入中 NOT_DERIVABLE ⇒ "
                                    "本阶段不得生成、不得当作匹配成功",
            "semantic_match_claimed": False,
            "status": "OK"}


def answer_reuse_question(report: dict, index: dict) -> dict:
    """特别要求：用**实测数字**解释「8 素材=8 家族」却仍出现明显复用（机器可读、无主观评价）。"""
    scopes = report["scopes"]
    primary = next((s for s in scopes if s["scope"] == report["primary_scope"]), scopes[0])
    A, B, C, E = (primary["A_asset_level"], primary["B_scene_level"],
                  primary["C_concentration"], primary["E_semantic_coverage"])
    idx_cands = len(index.get("candidates") or [])
    idx_fams = len((index.get("relationships") or {}).get("perceptual_families") or [])
    facts = [
        "索引内共 {} 个视觉候选、{} 个感知家族（P7-2 实测：真实素材间**无** A/B/C 类近重复）"
        .format(idx_cands, idx_fams),
        "本 scope（{}）场景数 {}，时间轴上实际出现 {} 个不同资产、{} 个感知家族、{} 个来源家族"
        .format(primary["scope"], B["scene_count"], A["unique_assets"],
                A["unique_perceptual_families"], A["unique_source_families"]),
        "复用直方图（资产→被多少场景使用）：{}".format(A["asset_reuse_histogram"]),
        "单资产最大复用 {} 场景；共享素材场景占比 {}；资产 HHI {}".format(
            A["max_asset_reuse"], B["scene_asset_reuse_rate"], C["asset_hhi"]),
    ]
    return {
        "question": "为什么「8 个真实视觉素材 = 8 个 perceptual family」，6-G 母片仍出现明显素材复用？",
        "answer_kind": "measurement_decomposition（无主观评价、无质量分数）",
        "facts": facts,
        "decomposition": {
            "identity_diversity": {
                "value": {"unique_assets": A["unique_assets"],
                          "unique_perceptual_families": A["unique_perceptual_families"],
                          "unique_source_families": A["unique_source_families"]},
                "verdict": "身份多样性**本身没有问题**：8 个素材确实互不相同（8 个感知家族）"},
            "reuse_distribution": {
                "value": {"scene_count": B["scene_count"],
                          "max_asset_reuse": A["max_asset_reuse"],
                          "scene_asset_reuse_rate": B["scene_asset_reuse_rate"],
                          "asset_hhi": C["asset_hhi"],
                          "histogram": A["asset_reuse_histogram"]},
                "verdict": "复用来自**分布**：场景数远多于可用身份数 ⇒ 每个资产平均被多个场景使用；"
                           "这是『身份数 < 场景数』的算术必然，不是感知去重失败"},
            "semantic_coverage": {
                "value": {"visual_goal_coverage": E.get("visual_goal_coverage"),
                          "query_coverage": E.get("query_coverage"),
                          "semantic_core_coverage": E.get("semantic_core_coverage"),
                          "semantic_match_claimed": E.get("semantic_match_claimed")},
                "verdict": "**相关性/语义是否满足无法判定**：P7-1 的核心语义字段全部 NOT_DERIVABLE "
                           "⇒ 不能据此说『复用的素材语义也合适』或『不合适』"},
        },
        "therefore": ["素材单调的现象由**可用身份数量**与**语义可用性**共同决定",
                      "仅增加身份数量（例如把一张图切成多张）**不会**提升视觉相关性 —— "
                      "P7 目标序为 relevance > semantic coverage > diversity > quantity",
                      "下一步（P7-4）需要相关性判定，才能真正区分『复用但相关』与『复用且不相关』"],
        "no_quality_score": True, "no_subjective_evaluation": True,
    }


def build_report(*, index: dict, scopes: list[dict], requirements: dict | None,
                 primary_scope: str, sources: list[dict]) -> dict:
    art = {
        "schema": SCHEMA, "version": VERSION,
        "generation_method": "deterministic-offline（零网络/零 LLM/零获取；只读消费 P7-2/P7-1 产物）",
        "metric_spec": METRIC_SPEC, "source_family_rule": SOURCE_FAMILY_RULE,
        "unknown_semantics": {"UNKNOWN": "无法确定", "NOT_AVAILABLE": "类别不适用",
                              "NOT_ASSESSABLE": "当前数据无法可靠计算（不猜）"},
        "forbidden_semantic_fields": list(FORBIDDEN_SEMANTIC_FIELDS),
        "sources": sources,
        "index_snapshot": {"artifact_hash": index.get("artifact_hash"),
                           "candidates": len(index.get("candidates") or []),
                           "families": len((index.get("relationships") or {})
                                           .get("perceptual_families") or [])},
        "primary_scope": primary_scope, "scopes": scopes,
        "concentration_formula": "HHI = Σ share²（share = 该身份的**场景数** / scene_count）",
        "dq_note": "P7-3 **不修改 DQ-2 或任何既有 DQ 阈值**；本报告为独立度量",
        "artifact_hash": "",
    }
    art["reuse_explanation"] = answer_reuse_question(art, index)
    art["artifact_hash"] = report_hash(art)
    return art


def report_body(art: dict) -> dict:
    return {k: v for k, v in art.items() if k != "artifact_hash"}


def report_hash(art: dict) -> str:
    return sha256_text(canonical(report_body(art)))


def validate_report(art: dict) -> list[str]:
    errs = []
    if art.get("schema") != SCHEMA:
        errs.append("schema 非法")
    if art.get("artifact_hash") != report_hash(art):
        errs.append("artifact_hash 不一致")
    if not art.get("metric_spec"):
        errs.append("metric_spec 缺失")
    if art.get("reuse_explanation", {}).get("no_quality_score") is not True:
        errs.append("reuse_explanation 缺少 no_quality_score 声明")
    for s in art.get("scopes") or []:
        for grp in ("A_asset_level", "B_scene_level", "C_concentration", "D_independence",
                    "E_semantic_coverage"):
            if grp not in s:
                errs.append("{} 缺少 {}".format(s.get("scope"), grp))
        if s["E_semantic_coverage"].get("semantic_match_claimed") is not False:
            errs.append("{} 不得声称语义匹配成功".format(s.get("scope")))
    if "created" in canonical(art)[:300].lower():
        errs.append("artifact 含时间戳（破坏确定性）")
    return errs
