# -*- coding: utf-8 -*-
"""P12-2：**素材许可数据 join（增强覆盖层）** —— 把系统内**已记录的许可声明**搬运进素材索引视图。

铁律（本模块的设计契约）：
  · **只搬运已记录的声明**：license 文本/署名/出处一律取自记录，**绝不推断、绝不猜测**；
  · 记录缺失 ⇒ 保持 `UNKNOWN`（仍走 HITL）；记录冲突 ⇒ 标 `CONFLICT`（仍走 HITL，**不得择一采信**）；
  · `classify_license`（`core/materials.py`）**语义零改动**，本模块只调用；
  · 输出是**新的增强覆盖层 artifact**（canonical JSON + sha256）；**P7-2 原索引一个字节都不动**；
  · 覆盖层**默认不存在** ⇒ 消费方（P7-6 绑定路径）行为与现状**逐字节一致**（向后兼容硬验收）；
  · 纯 join 逻辑**零 I/O**（记录由调用方/阶段脚本只读加载后传入），确定性排序、无时间戳。

三态判定：
  `HAS_RECORD` —— 有记录且全部记录的判类一致且非 UNKNOWN（可用类解锁许可门）
  `MISSING`    —— 无记录，或记录本身声明 `unchecked/UNKNOWN`（`missing_reason=RECORDS_DECLARE_UNKNOWN`）
  `CONFLICT`   —— 多条记录判类不一致（两侧出处均留档；门禁按 UNKNOWN 处理）
"""
from __future__ import annotations

from ..core.materials import LICENSE_CLASSES, classify_license
from ..core.visual_requirement import canonical, sha256_text

SCHEMA = "asset-license-overlay-v1"
VERSION = 1
JOIN_RULE_VERSION = "asset-license-join-v1:record-only-no-inference"
HAS_RECORD, MISSING, CONFLICT = "HAS_RECORD", "MISSING", "CONFLICT"
STATES = (HAS_RECORD, MISSING, CONFLICT)

#: 记录来源类型（本阶段实际盘点到的存放处；见 logs/phase12_license_sources.json）
RECORD_SOURCE_TYPES = ("attribution_artifact", "render_material_timeline", "h5_report_asset_record",
                       "retrieval_candidates", "external_cache_index", "artifacts_table")
UNKNOWN_TOKENS = ("", "unknown", "unchecked", "none", "null", "n/a", "na")


def is_unknown_token(text) -> bool:
    """记录里的许可文本是否等于"未声明"（这些 token 不构成可用记录）。"""
    return str(text or "").strip().lower() in UNKNOWN_TOKENS


def license_record(*, asset_id: str | None, license_text, attribution=None, source_type: str,
                   locator: str, record_sha256: str | None = None, source_url=None,
                   asset_sha256=None, scene_id=None, extra=None) -> dict:
    """把一条**已记录**的许可声明规范化为记录（判类复用 classify_license，零语义改动）。"""
    cls, cleared = classify_license(license_text)
    return {"asset_id": asset_id, "source_type": source_type, "locator": locator,
            "record_sha256": record_sha256, "license_text": license_text,
            "license_class": cls,
            # 字段语义照抄 classify_license 的返回值（第二位是 **cleared**，不是 restricted）
            "license_cleared": cleared,
            "license_blocking": cls in ("RESTRICTED", "UNKNOWN"),
            "attribution": attribution, "source_url": source_url,
            "asset_sha256": asset_sha256, "scene_id": scene_id,
            "record_unknown": is_unknown_token(license_text),
            "extra": extra or {}}


def match_keys(*, asset_id=None, sha256=None, provider=None, source_id=None, source_url=None) -> dict:
    """一个索引资产的**匹配键集合**（join 只按这些键精确匹配，不做模糊/语义匹配）。"""
    keys = {}
    if asset_id:
        keys["asset_id"] = str(asset_id)
    if sha256:
        keys["sha256"] = str(sha256)
    if provider and source_id:
        keys["provider_source_id"] = "{}|{}".format(provider, source_id)
    if source_url:
        keys["source_url"] = str(source_url)
    return keys


def record_matches(record: dict, keys: dict) -> bool:
    """记录是否命中该资产（**精确键匹配**：任一键相等即命中）。"""
    if keys.get("asset_id") and record.get("asset_id") == keys["asset_id"]:
        return True
    if keys.get("sha256") and record.get("asset_sha256") == keys["sha256"]:
        return True
    if keys.get("provider_source_id"):
        prov = record.get("extra", {}).get("provider")
        sid = record.get("extra", {}).get("source_id")
        if prov and sid and "{}|{}".format(prov, sid) == keys["provider_source_id"]:
            return True
    if keys.get("source_url") and record.get("source_url") == keys["source_url"]:
        return True
    return False


def join_asset(records: list[dict]) -> dict:
    """单资产三态判定（纯函数）。"""
    recs = sorted(records, key=lambda r: (str(r.get("source_type")), str(r.get("locator"))))
    meaningful = [r for r in recs if not r.get("record_unknown")]
    classes = sorted({r["license_class"] for r in meaningful})
    if not meaningful:
        return {"state": MISSING, "license": None, "license_class": "UNKNOWN",
                "attribution": None, "records": recs,
                "missing_reason": ("RECORDS_DECLARE_UNKNOWN" if recs else "NO_RECORD"),
                "conflict": None}
    if len(classes) > 1:
        by_class = {c: [r for r in meaningful if r["license_class"] == c] for c in classes}
        return {"state": CONFLICT, "license": None, "license_class": "UNKNOWN",
                "attribution": None, "records": recs,
                "missing_reason": None,
                "conflict": {"classes": classes,
                             "sides": [{"license_class": c,
                                        "license_texts": sorted({str(r["license_text"]) for r in v}),
                                        "sources": [{"source_type": r["source_type"],
                                                     "locator": r["locator"]} for r in v]}
                                       for c, v in sorted(by_class.items())],
                             "policy": "门禁按 UNKNOWN 处理（HITL）；不得择一采信"}}
    pick = meaningful[0]
    return {"state": HAS_RECORD, "license": pick["license_text"],
            "license_class": pick["license_class"], "attribution": pick.get("attribution"),
            "records": recs, "missing_reason": None, "conflict": None,
            "source_of_record": {"source_type": pick["source_type"], "locator": pick["locator"],
                                 "record_sha256": pick.get("record_sha256"),
                                 "scene_id": pick.get("scene_id"),
                                 "source_url": pick.get("source_url")}}


def build_overlay(*, index: dict, records: list[dict], sources_manifest: list[dict] | None = None,
                  notes: list[str] | None = None) -> dict:
    """构建覆盖层 artifact：**不改动** `index`（只读消费其 asset_id/sha256/provider/source_id/source_url）。"""
    cands = sorted((index.get("candidates") or []), key=lambda c: str(c.get("asset_id")))
    recs = sorted(records, key=lambda r: (str(r.get("asset_id")), str(r.get("source_type")),
                                          str(r.get("locator"))))
    entries = []
    for c in cands:
        keys = match_keys(asset_id=c.get("asset_id"), sha256=c.get("sha256"),
                          provider=c.get("provider"), source_id=c.get("source_id"),
                          source_url=c.get("source_url"))
        matched = [r for r in recs if record_matches(r, keys)]
        joined = join_asset(matched)
        entries.append({
            "asset_id": c.get("asset_id"), "asset_sha256": c.get("sha256"),
            "index_license": c.get("license"), "index_license_class": c.get("license_class"),
            "index_attribution": c.get("attribution"),
            "state": joined["state"], "license": joined["license"],
            "license_class": joined["license_class"], "attribution": joined["attribution"],
            "license_cleared": (None if joined["state"] != HAS_RECORD else
                                all(r["license_cleared"] for r in
                                    [x for x in joined["records"] if not x["record_unknown"]])),
            "license_blocking": (None if joined["state"] != HAS_RECORD else
                                 any(r["license_blocking"] for r in
                                     [x for x in joined["records"] if not x["record_unknown"]])),
            "match_keys": keys, "record_count": len(joined["records"]),
            "source_of_record": joined.get("source_of_record"),
            "missing_reason": joined.get("missing_reason"), "conflict": joined.get("conflict"),
            "records": joined["records"],
            "changes_index_license": bool(joined["state"] == HAS_RECORD
                                          and joined["license_class"] != c.get("license_class")),
        })
    unmatched = [r for r in recs
                 if not any(record_matches(r, e["match_keys"]) for e in entries)]
    counts = {s: sum(1 for e in entries if e["state"] == s) for s in STATES}
    body = {
        "schema": SCHEMA, "version": VERSION, "join_rule_version": JOIN_RULE_VERSION,
        "generation_method": "deterministic-pure-join（零 LLM、零网络、零执行、零 I/O）",
        "index_schema": index.get("schema"), "index_sha256": sha256_text(canonical(index)),
        "index_candidates": len(cands), "record_count": len(recs),
        "sources_manifest": sources_manifest or [],
        "unknown_policy": ("HAS_RECORD 才可能解锁许可门；MISSING/CONFLICT 一律保持 UNKNOWN ⇒ 走 HITL；"
                           "冲突不择一采信"),
        "license_classes_allowed": list(LICENSE_CLASSES),
        "classify_license_untouched": True,
        "entries": entries, "counts": counts,
        "unmatched_records": unmatched,
        "notes": notes or [],
        "read_only": True, "zero_write": True, "applied": False, "executed": False,
        "artifact_hash": "",
    }
    body["artifact_hash"] = overlay_hash(body)
    return body


def overlay_hash(overlay: dict) -> str:
    return sha256_text(canonical({k: v for k, v in overlay.items() if k != "artifact_hash"}))


def overlay_lookup(overlay: dict | None) -> dict:
    return {e["asset_id"]: e for e in ((overlay or {}).get("entries") or [])}


def apply_to_candidate(candidate: dict, overlay: dict | None) -> tuple[dict, dict | None]:
    """把覆盖层应用到单个候选：仅 `HAS_RECORD` 资产替换 license/class/attribution（其余原样）。

    返回 `(candidate, provenance|None)`；`overlay is None` ⇒ **原对象原样返回**（向后兼容）。
    """
    if not overlay:
        return candidate, None
    entry = overlay_lookup(overlay).get(candidate.get("asset_id"))
    if not entry or entry.get("state") != HAS_RECORD:
        return candidate, None
    out = dict(candidate)
    out["license"] = entry["license"]
    out["license_class"] = entry["license_class"]
    if entry.get("attribution"):
        out["attribution"] = entry["attribution"]
    prov = {"join_rule_version": overlay.get("join_rule_version"),
            "overlay_schema": overlay.get("schema"),
            "overlay_artifact_hash": overlay.get("artifact_hash"),
            "state": entry["state"], "source_of_record": entry.get("source_of_record"),
            "index_license_class_before": entry.get("index_license_class"),
            "license_class_after": entry.get("license_class"),
            "record_count": entry.get("record_count")}
    return out, prov


def _rec_hash(obj) -> str:
    return sha256_text(canonical(obj))


def collect_records(*, db_path, project_id: str, logs_dir, h5_path=None,
                    cache_index_paths=(), retrieval_limit: int = 400) -> tuple[list, list, list]:
    """**只读**采集系统内已记录的许可声明（DB `mode=ro`+`query_only`；文件只读）。

    返回 `(records, sources_manifest, notes)`；**不写任何东西**。记录来源与定位键：
      · `attribution_artifact`：DB `artifacts(type='attribution')` ⇒ 条目 `provider|source_id|scene_id`
      · `render_material_timeline`：DB `artifacts(type='render_output')` ⇒ `material_timeline[].selected_asset`
      · `h5_report_asset_record`：`logs/phase6g_exec_h5.json` 的 `asset_records`
      · `retrieval_candidates`：DB `artifacts(type='retrieval_candidates')` ⇒ `candidates[]`
      · `external_cache_index` / `artifacts_table`：**负证据**（已盘点：无许可字段 / 全 NULL）
    """
    import json as _json
    import pathlib as _pathlib
    import sqlite3 as _sqlite3

    recs: list = []
    manifest: list = []
    notes: list = []
    con = _sqlite3.connect("file:" + _pathlib.Path(db_path).as_posix() + "?mode=ro", uri=True)
    con.row_factory = _sqlite3.Row
    con.execute("PRAGMA query_only=ON")
    try:
        rows = list(con.execute(
            "select artifact_id, path from artifacts where type='attribution' and project_id=? "
            "order by created_at desc limit 20", (project_id,)))
        n = 0
        for r in rows:
            try:
                j = _json.loads(_pathlib.Path(r["path"]).read_text(encoding="utf-8"))
            except (OSError, _json.JSONDecodeError):
                continue
            for e in j.get("entries") or []:
                if is_unknown_token(e.get("license")):
                    continue                                  # 记录本身声明未知 ⇒ 不算可用记录
                sa = e.get("selected_asset") or {}
                recs.append(license_record(
                    asset_id=sa.get("asset_id"), license_text=e.get("license"),
                    attribution=e.get("attribution"), source_type="attribution_artifact",
                    locator="{}#entries/scene={}".format(r["artifact_id"], e.get("scene_id")),
                    record_sha256=_rec_hash(e), source_url=e.get("source_url"),
                    asset_sha256=sa.get("sha256"), scene_id=e.get("scene_id"),
                    extra={"provider": e.get("provider"), "source_id": e.get("source_id"),
                           "scope": e.get("scope"), "license_class_recorded": e.get("license_class")}))
                n += 1
        manifest.append({"source_type": "attribution_artifact", "location": "artifacts(type=attribution)",
                         "locator_scheme": "artifact_id#entries/scene", "records": n,
                         "license_field": True, "artifacts_scanned": len(rows)})
        rows = list(con.execute(
            "select artifact_id, path from artifacts where type='render_output' and project_id=? "
            "order by created_at desc limit 5", (project_id,)))
        n = 0
        for r in rows:
            try:
                j = _json.loads(_pathlib.Path(r["path"]).read_text(encoding="utf-8"))
            except (OSError, _json.JSONDecodeError):
                continue
            for seg in j.get("material_timeline") or []:
                sa = seg.get("selected_asset") or {}
                if is_unknown_token(sa.get("license")) or not sa.get("license"):
                    continue
                recs.append(license_record(
                    asset_id=sa.get("asset_id"), license_text=sa.get("license"),
                    attribution=sa.get("attribution"), source_type="render_material_timeline",
                    locator="{}#material_timeline[scene={}]".format(r["artifact_id"],
                                                                    seg.get("scene_id")),
                    record_sha256=_rec_hash(sa), source_url=sa.get("source_url"),
                    asset_sha256=sa.get("sha256"), scene_id=seg.get("scene_id"),
                    extra={"provider": sa.get("provider")}))
                n += 1
        manifest.append({"source_type": "render_material_timeline",
                         "location": "artifacts(type=render_output).material_timeline",
                         "locator_scheme": "artifact_id#material_timeline[scene]", "records": n,
                         "license_field": True, "artifacts_scanned": len(rows)})
        rows = list(con.execute(
            "select artifact_id, path from artifacts where type='retrieval_candidates' and "
            "project_id=? order by created_at desc limit 5", (project_id,)))
        n = 0
        for r in rows:
            try:
                j = _json.loads(_pathlib.Path(r["path"]).read_text(encoding="utf-8"))
            except (OSError, _json.JSONDecodeError):
                continue
            for i, c in enumerate((j.get("candidates") or [])[:retrieval_limit]):
                if not isinstance(c, dict) or is_unknown_token(c.get("license")):
                    continue
                recs.append(license_record(
                    asset_id=c.get("asset_id"), license_text=c.get("license"),
                    attribution=c.get("attribution") or c.get("author"),
                    source_type="retrieval_candidates",
                    locator="{}#candidates[{}]".format(r["artifact_id"], i),
                    record_sha256=_rec_hash(c),
                    source_url=c.get("url") or c.get("source_url"),
                    asset_sha256=c.get("sha256"),
                    extra={"provider": c.get("provider"), "source_id": c.get("source_id")}))
                n += 1
        manifest.append({"source_type": "retrieval_candidates",
                         "location": "artifacts(type=retrieval_candidates).candidates",
                         "locator_scheme": "artifact_id#candidates[i]", "records": n,
                         "license_field": True, "artifacts_scanned": len(rows)})
        n_null = con.execute("select count(*) from artifacts where license is null").fetchone()[0]
        manifest.append({"source_type": "artifacts_table", "location": "artifacts.license",
                         "locator_scheme": "artifact_id", "records": 0, "license_field": False,
                         "note": "已盘点：全部 {} 行为 NULL（无可用记录）".format(n_null)})
    finally:
        con.close()
    if h5_path and _pathlib.Path(h5_path).is_file():
        try:
            jj = _json.loads(_pathlib.Path(h5_path).read_text(encoding="utf-8"))
            ar = jj.get("asset_records") or {}
            items = list(ar.values()) if isinstance(ar, dict) else list(ar)
            n = 0
            for i, a in enumerate(items):
                if not isinstance(a, dict) or is_unknown_token(a.get("license")):
                    continue
                recs.append(license_record(
                    asset_id=a.get("asset_id"), license_text=a.get("license"),
                    attribution=a.get("attribution"), source_type="h5_report_asset_record",
                    locator="phase6g_exec_h5.json#asset_records[{}]".format(i),
                    record_sha256=_rec_hash(a), source_url=a.get("source_url"),
                    asset_sha256=a.get("sha256"),
                    extra={"provider": a.get("provider"), "source_id": a.get("source_id")}))
                n += 1
            manifest.append({"source_type": "h5_report_asset_record", "location": str(h5_path),
                             "locator_scheme": "asset_records[i]", "records": n,
                             "license_field": True})
        except (OSError, _json.JSONDecodeError):
            notes.append("H5 报告读取失败（跳过，不推断）")
    for p in cache_index_paths:
        pth = _pathlib.Path(p)
        if not pth.is_file():
            continue
        try:
            jj = _json.loads(pth.read_text(encoding="utf-8"))
        except (OSError, _json.JSONDecodeError):
            continue
        keys = sorted({k for v in jj.values() if isinstance(v, dict) for k in v})
        has_lic = any("licen" in k.lower() or "attribut" in k.lower() for k in keys)
        manifest.append({"source_type": "external_cache_index", "location": str(pth),
                         "locator_scheme": "provider|source_id", "records": 0,
                         "license_field": bool(has_lic),
                         "note": "已盘点：字段={}（无许可字段 ⇒ 这是 P7-2 缺口的根因）".format(keys)})
    return recs, manifest, notes


def validate_overlay(overlay: dict) -> list[str]:
    errs = []
    if overlay.get("schema") != SCHEMA:
        errs.append("schema 非法")
    if overlay.get("artifact_hash") != overlay_hash(overlay):
        errs.append("artifact_hash 不一致")
    seen = set()
    for e in overlay.get("entries") or []:
        aid = e.get("asset_id")
        if aid in seen:
            errs.append("asset 重复: {}".format(aid))
        seen.add(aid)
        if e.get("state") not in STATES:
            errs.append("state 非法: {}".format(aid))
        if e.get("state") == HAS_RECORD:
            if e.get("license_class") not in LICENSE_CLASSES or e["license_class"] == "UNKNOWN":
                errs.append("HAS_RECORD 但 class 非可用: {}".format(aid))
            if not e.get("source_of_record"):
                errs.append("HAS_RECORD 缺 source_of_record: {}".format(aid))
            if not e.get("license"):
                errs.append("HAS_RECORD 缺 license 原文: {}".format(aid))
        if e.get("state") == CONFLICT and not (e.get("conflict") or {}).get("sides"):
            errs.append("CONFLICT 缺两侧出处: {}".format(aid))
        if e.get("state") != HAS_RECORD and e.get("license_class") != "UNKNOWN":
            errs.append("非 HAS_RECORD 必须保持 UNKNOWN: {}".format(aid))
    return errs
