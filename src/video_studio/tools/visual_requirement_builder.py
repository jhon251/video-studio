# -*- coding: utf-8 -*-
"""P7-1：**确定性、离线** VisualRequirement Builder（无网络、无 LLM、无素材获取）。

输入（**只读**）：上游真实产物字段
  · `render_output.material_timeline[i]`（镜头身份 + original_requirement 的显式字段）
  · `script_output.segments[]`（旁白文本，按 segment_index 对齐）
  · `visual_plan_output.shots[]`（可选的 shot.source / shot_size / description）

输出：`VisualRequirement`（契约见 `core.visual_requirement`）+ artifact（含 source identity/hash、
规则清单、逐条 hash、整体 hash）。

**不臆造**：subject/action/object/environment/concept 在无结构化来源时一律 `NOT_DERIVABLE`；
英文查询只取输入中**已存在**的拉丁 token（不做翻译、不做同义词扩展）。
"""
from __future__ import annotations

import re

from ..core.materials import extract_constraints
from ..core.visual_requirement import (ARTIFACT_SCHEMA, ARTIFACT_VERSION, EVIDENCE_TYPE_MAP,
                                       STOPWORDS_EN, STATUS_DERIVABLE, STATUS_NOT_DERIVABLE,
                                       VisualRequirementError, INVALID_NO_SOURCE_TEXT,
                                       artifact_hash, canonical, field_status, make_requirement,
                                       norm_list, norm_text, requirement_hash, sha256_text,
                                       validate_requirement)

BUILDER = "deterministic-offline-v1"
_NUM = re.compile(r"(?<!\d)((?:19|20)\d{2}|\d+(?:\.\d+)?%?)(?!\d)")
_LATIN = re.compile(r"[A-Za-z][A-Za-z0-9\-_]{1,}")
_MAX_CONCEPTS = 12
_MAX_QUERIES = 6
_MAX_LADDER_PAIRS = 3

BUILDER_RULES = [
    {"id": "R-IDENT", "fields": ["scene_id"],
     "desc": "镜头身份直接取自 material_timeline[i].scene_id（显式，不改写）"},
    {"id": "R-GOAL", "fields": ["visual_goal"],
     "desc": "visual_goal ← upstream shot_description，缺失则 shot_gen_prompt（显式文本）"},
    {"id": "R-KIND", "fields": ["expected_kind"],
     "desc": "expected_kind ← original_requirement.expected_kind（显式）"},
    {"id": "R-POLICY", "fields": ["reuse_policy", "min_match_score"],
     "desc": "reuse_policy/min_match_score ← original_requirement 显式值（口径不变）"},
    {"id": "R-NEG", "fields": ["avoid_list", "concepts_neg"],
     "desc": "avoid_list ← 显式 constraints[] + core.materials.extract_constraints(既有否定短语规则)；"
             "concepts_neg ← 同源否定短语（表层 token）"},
    {"id": "R-TOKENS", "fields": ["concepts_pos"],
     "desc": "concepts_pos ← **内容文本**（narration + shot_description + shot_gen_prompt）中的"
             "年份/数字 + ASCII token（≥2 字符，去停用词，**排除否定短语中的 token**）；"
             "按(-词频, 词形) 排序取前 {}".format(_MAX_CONCEPTS)},
    {"id": "R-QEN", "fields": ["queries_en"],
     "desc": "queries_en ← **内容文本**中已存在的 ASCII token（≥3 字符，去停用词，"
             "**排除否定短语中的 token**），按(-词频, 词形) 取前 {}；**不翻译**；"
             "style_constraint 仅用于否定约束提取，不作为查询来源".format(_MAX_QUERIES)},
    {"id": "R-LADDER", "fields": ["query_ladder"],
     "desc": "query_ladder ← 仅由 queries_en/concepts_pos 中已有 token 机械组合"
             "（对偶查 → 单词查 → 概念查）"},
    {"id": "R-EVID", "fields": ["evidence_type"],
     "desc": "evidence_type ← 显式 shot.source 经固定映射表（无映射 ⇒ NOT_DERIVABLE）"},
    {"id": "R-SEM", "fields": ["subject", "action", "object", "environment", "concept"],
     "desc": "**不推导**：当前输入无结构化语义来源 ⇒ 一律 NOT_DERIVABLE"
             "（留待未来 StructuredExtractor，必须附证据引用）"},
]


def _texts(scene: dict, narration: str | None, shot: dict | None) -> dict:
    req = scene.get("original_requirement") or {}
    return {
        "scene_id": scene.get("scene_id"),
        "narration": norm_text(narration) or "",
        "shot_description": norm_text(req.get("shot_description")) or "",
        "shot_gen_prompt": norm_text(req.get("shot_gen_prompt")) or "",
        "style_constraint": norm_text(req.get("style_constraint")) or "",
        "chapter": norm_text(scene.get("chapter")) or "",
        "shot_source": norm_text((shot or {}).get("source")),
        "shot_size": norm_text((shot or {}).get("shot_size")),
        "shot_description_plan": norm_text((shot or {}).get("description")) or "",
    }


def _tokens(text: str, min_len: int) -> list[str]:
    out = []
    for m in _LATIN.finditer(text or ""):
        t = m.group(0)
        if len(t) >= min_len and t.casefold() not in STOPWORDS_EN:
            out.append(t)
    return out


def _ranked(tokens: list[str], limit: int) -> list[str]:
    """确定性排序：(-频次, 词形小写, 原形) ⇒ 取前 limit。"""
    counts: dict[str, int] = {}
    forms: dict[str, str] = {}
    for t in tokens:
        k = t.casefold()
        counts[k] = counts.get(k, 0) + 1
        forms.setdefault(k, t)
    keys = sorted(counts, key=lambda k: (-counts[k], k))
    return [forms[k] for k in keys[:limit]]


def _numbers(text: str) -> list[str]:
    return sorted({m.group(0) for m in _NUM.finditer(text or "")},
                  key=lambda s: (len(s), s))


def derive_fields(scene: dict, narration: str | None, shot: dict | None) -> tuple[dict, dict]:
    """返回 (values, statuses)——纯函数、无副作用、无网络。"""
    tx = _texts(scene, narration, shot)
    req = scene.get("original_requirement") or {}
    joined = " ".join(x for x in (tx["narration"], tx["shot_description"],
                                  tx["shot_gen_prompt"], tx["style_constraint"]) if x)
    values: dict = {}
    st: dict = {}

    # 语义字段：不推导
    for f in ("subject", "action", "object", "environment", "concept"):
        values[f] = None
        st[f] = field_status(STATUS_NOT_DERIVABLE, "none",
                            "当前输入无结构化语义来源（留待 StructuredExtractor + 证据引用）")

    # visual_goal：显式上游文本
    goal = tx["shot_description"] or tx["shot_gen_prompt"] or None
    values["visual_goal"] = goal
    st["visual_goal"] = field_status(
        STATUS_DERIVABLE if goal else STATUS_NOT_DERIVABLE,
        "material_timeline.original_requirement.shot_description|shot_gen_prompt" if goal
        else "none", "" if goal else "上游未提供镜头画面描述")

    # 显式策略字段
    for f, key, src in (("expected_kind", "expected_kind", "original_requirement.expected_kind"),
                        ("reuse_policy", "reuse_policy", "original_requirement.reuse_policy")):
        v = norm_text(req.get(key))
        values[f] = v
        st[f] = field_status(STATUS_DERIVABLE if v else STATUS_NOT_DERIVABLE,
                             src if v else "none", "" if v else "上游未提供该显式字段")
    mk = req.get("min_match_score")
    values["min_match_score"] = int(mk) if isinstance(mk, (int, float)) else None
    st["min_match_score"] = field_status(
        STATUS_DERIVABLE if values["min_match_score"] is not None else STATUS_NOT_DERIVABLE,
        "original_requirement.min_match_score" if values["min_match_score"] is not None else "none",
        "" if values["min_match_score"] is not None else "上游未提供阈值（口径不改）")

    # 否定与禁用项（既有确定性规则）
    neg_src_ok = bool(joined) or bool(req.get("constraints"))
    cons = extract_constraints({"constraints": req.get("constraints") or [],
                                "style_constraint": tx["style_constraint"],
                                "gen_prompt": tx["shot_gen_prompt"],
                                "description": tx["shot_description"]}, tx["narration"])
    values["avoid_list"] = cons or None
    values["concepts_neg"] = cons or None
    for f in ("avoid_list", "concepts_neg"):
        st[f] = field_status(STATUS_DERIVABLE if neg_src_ok else STATUS_NOT_DERIVABLE,
                            "constraints[] + style_constraint/gen_prompt（existing-negation-rule）"
                            if neg_src_ok else "none",
                            "" if neg_src_ok else "无否定/禁用来源文本")

    # 表层 token 概念：**仅内容文本**；排除否定短语里的 token（不把"要避免的"当正向线索）
    content = " ".join(x for x in (tx["narration"], tx["shot_description"],
                                   tx["shot_gen_prompt"]) if x)
    neg_tokens = {t.casefold() for phrase in cons for t in _LATIN.findall(phrase)}
    toks2 = [t for t in _tokens(content, 2) if t.casefold() not in neg_tokens]
    nums = _numbers(content)
    concepts = nums + _ranked(toks2, _MAX_CONCEPTS)
    values["concepts_pos"] = concepts or None
    st["concepts_pos"] = field_status(
        STATUS_DERIVABLE if concepts else STATUS_NOT_DERIVABLE,
        "content text（narration+shot_description+shot_gen_prompt）" if concepts else "none",
        "" if concepts else "内容文本中无数字/拉丁 token ⇒ 无法确定概念内容")

    # 英文查询（不翻译）：仅内容文本，排除否定 token
    q = _ranked([t for t in _tokens(content, 3) if t.casefold() not in neg_tokens],
                _MAX_QUERIES)
    values["queries_en"] = q or None
    st["queries_en"] = field_status(
        STATUS_DERIVABLE if q else STATUS_NOT_DERIVABLE,
        "input latin tokens(≥3, existing-only)" if q else "none",
        "" if q else "输入无拉丁 token ⇒ 不生成英文查询（不做翻译）")

    # 检索阶梯：只用已有 token
    ladder = None
    if q:
        pairs = ["{} {}".format(q[i], q[j]) for i in range(len(q))
                 for j in range(i + 1, len(q))][:_MAX_LADDER_PAIRS]
        ladder = [pairs, list(q), list(concepts[: _MAX_QUERIES])] if pairs else [list(q)]
        ladder = [s for s in ladder if s]
    values["query_ladder"] = ladder or None
    st["query_ladder"] = field_status(
        STATUS_DERIVABLE if ladder else STATUS_NOT_DERIVABLE,
        "derived-from queries_en/concepts_pos" if ladder else "none",
        "" if ladder else "queries_en 不可推导 ⇒ 阶梯不生成")

    # 证据类型：显式 shot.source 映射
    ev = None
    if tx["shot_source"]:
        ev = EVIDENCE_TYPE_MAP.get(tx["shot_source"].casefold())
    values["evidence_type"] = ev
    st["evidence_type"] = field_status(
        STATUS_DERIVABLE if ev else STATUS_NOT_DERIVABLE,
        "visual_plan_output.shots[].source（fixed-map）" if ev else "none",
        "" if ev else ("shot.source={!r} 无固定映射".format(tx["shot_source"])
                       if tx["shot_source"] else "上游未提供 shot.source"))
    return values, st


def build_requirement(scene: dict, narration: str | None = None, shot: dict | None = None,
                      *, source_id: str, source_sha256: str, source_path: str = "",
                      record_index: int | None = None) -> dict:
    """单镜 → VisualRequirement（fail-closed：身份/溯源/内容缺失即按契约处理）。"""
    sid = scene.get("scene_id")
    tx = _texts(scene, narration, shot)
    if not tx["narration"] and not tx["shot_description"] and not tx["shot_gen_prompt"] \
            and not tx["chapter"]:
        raise VisualRequirementError(
            INVALID_NO_SOURCE_TEXT,
            "镜头 {} 无任何可用文本来源（旁白/画面描述/章节）⇒ 不得生成需求".format(sid))
    values, st = derive_fields(scene, narration, shot)
    prov = {
        "source_id": source_id, "source_sha256": source_sha256, "source_path": source_path,
        "record_index": record_index,
        "used_fields": {"narration": bool(tx["narration"]),
                        "shot_description": bool(tx["shot_description"]),
                        "shot_gen_prompt": bool(tx["shot_gen_prompt"]),
                        "style_constraint": bool(tx["style_constraint"]),
                        "constraints": list((scene.get("original_requirement") or {})
                                            .get("constraints") or []),
                        "shot_source": tx["shot_source"], "chapter": tx["chapter"]},
        "rules": [r["id"] for r in BUILDER_RULES],
        "builder": BUILDER,
        "inference": "none（P7-1 不做推断，不做翻译，不访问网络）",
    }
    return make_requirement(scene_id=sid, values=values, statuses=st, provenance=prov)


def build_artifact(scenes: list[dict], *, narrations: list[str] | None = None,
                   shots: dict | None = None, sources: list[dict] | None = None,
                   narration_mapping: str | None = None) -> dict:
    """21 镜 → artifact（确定性：不含时间戳；同输入同字节）。"""
    narrations = narrations or []
    shots = shots or {}
    reqs, seen = [], set()
    for i, sc in enumerate(scenes):
        sid = sc.get("scene_id")
        if sid in seen:
            raise VisualRequirementError("VR_INVALID_DUPLICATE_SCENE", str(sid))
        seen.add(sid)
        sidx = (sc.get("original_requirement") or {}).get("shot_index")
        shot = shots.get(sidx) if sidx is not None else None
        nar = narrations[i] if i < len(narrations) else None
        src = (sources or [{}])[0]
        reqs.append(build_requirement(sc, nar, shot, source_id=src.get("artifact_id") or "unknown",
                                      source_sha256=src.get("sha256") or "0" * 64,
                                      source_path=src.get("path") or "", record_index=i))
    reqs.sort(key=lambda r: r["scene_id"])
    fs_counts: dict[str, dict] = {}
    for r in reqs:
        for name, meta in r["field_status"].items():
            fs_counts.setdefault(name, {"DERIVABLE": 0, "NOT_DERIVABLE": 0})
            fs_counts[name][meta["status"]] += 1
    art = {
        "schema": ARTIFACT_SCHEMA, "version": ARTIFACT_VERSION,
        "generation_method": "deterministic-offline（无网络、无 LLM、无素材获取）",
        "builder": BUILDER,
        "builder_rules": BUILDER_RULES,
        "normalization": {"unicode": "NFC", "whitespace": "collapse-to-single-space+strip",
                          "unordered_lists": "dedupe(casefold)+sort(casefold,form)",
                          "ordered_lists": "preserve-order",
                          "json": "sort_keys+compact+utf-8",
                          "timestamps": "artifact 内不含时间戳（保证同输入同字节）"},
        "source_identity": {"sources": sources or [], "scene_count": len(scenes),
                            "narration_mapping": narration_mapping},
        "counts": {"requirements": len(reqs),
                   "derivable": sum(1 for r in reqs if r["status"] == STATUS_DERIVABLE),
                   "not_derivable": sum(1 for r in reqs
                                        if r["status"] == STATUS_NOT_DERIVABLE),
                   "field_status_counts": {k: fs_counts[k] for k in sorted(fs_counts)}},
        "requirements": reqs,
        "requirement_hashes": {r["scene_id"]: r["deterministic_hash"] for r in reqs},
    }
    art["artifact_hash"] = artifact_hash(art)
    return art


def validate_artifact(art: dict) -> list[str]:
    """artifact 级校验：schema/计数/逐条校验/整体 hash。"""
    errs: list[str] = []
    if art.get("schema") != ARTIFACT_SCHEMA:
        errs.append("artifact schema 非法")
    if art.get("artifact_hash") != artifact_hash(art):
        errs.append("artifact_hash 不一致")
    reqs = art.get("requirements") or []
    if art.get("counts", {}).get("requirements") != len(reqs):
        errs.append("counts.requirements 与实际条数不一致")
    for r in reqs:
        for e in validate_requirement(r):
            errs.append("{}: {}".format(r.get("scene_id"), e))
    hashes = art.get("requirement_hashes") or {}
    for r in reqs:
        if hashes.get(r["scene_id"]) != r["deterministic_hash"]:
            errs.append("{}: requirement_hashes 不一致".format(r.get("scene_id")))
    return errs


def artifact_digest(art: dict) -> str:
    return sha256_text(canonical(art))
