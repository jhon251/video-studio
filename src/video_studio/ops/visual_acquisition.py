# -*- coding: utf-8 -*-
"""P7-5：受治理获取 **ops 入口**（**严格只读**：不写文件、零网络、无 DB 写入；默认 DRY_RUN）。

用法：
  python -m video_studio.ops.visual_acquisition build [--mode dry_run|live] [--authorize-live]
  python -m video_studio.ops.visual_acquisition verify PATH

* `build --mode dry_run`（默认）：只做需求分析 / request / query / provider policy / 预算 /
  license 要求 / plan —— **不下载任何素材**。
* `build --mode live`：**默认拒绝**（需 `--authorize-live` + `--out-dir` 在 `output/` 下）；
  且本仓库默认 `provider=none` ⇒ 即使授权也会 fail-closed（`PROVIDER_NOT_CONFIGURED`），
  **本阶段不会产生任何网络请求**。真正的下载路径在
  `core.visual_acquisition.fetch_candidates(transport=…)`（**每一条安全门都可注入 transport 测试**）。

artifact 落盘 = `docs/regression_2x/phase7_p7_5_build.py`（ops 契约：不得写文件）。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

from ..core import visual_acquisition as VA
from ..core.asset_candidate import UNKNOWN
from ..core.materials import classify_license, license_block_reason, license_gate_applies
from ..tools import material_provider as MP

DEFAULT_DB = r"C:\mp4agent\video-studio\projects\video_studio.db"
DEFAULT_TASK = "t_d0a54bdf1810"
DEFAULT_LOGS = r"C:\mp4agent\video-studio\docs\regression_2x\logs"
DEFAULT_OUT = r"C:\mp4agent\video-studio\docs\regression_2x\logs\visual_acquisition.json"
#: 既有阈值来源（**数据来源**：6-G 冻结的 DQ 重算产物；不引用任何 DQ 模块，不改阈值）
DQ_RECOMPUTE_ARTIFACT = "phase6g_h5_dq_recompute.json"
DQ2_THRESHOLD_PATH = "DQ.after_H5.DQ-2.threshold"


class SourceMissing(RuntimeError):
    """必需输入产物缺失 ⇒ fail-closed。"""


def sha256_file(p) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def _json(p) -> dict:
    return json.loads(Path(p).read_text(encoding="utf-8"))


def _db_ro(db: str) -> sqlite3.Connection:
    con = sqlite3.connect("file:{}?mode=ro".format(Path(db).as_posix()), uri=True)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA query_only=ON")
    return con


def _require(p: Path, what: str) -> Path:
    if not p.is_file():
        raise SourceMissing("{} 缺失：{}".format(what, p))
    return p


def probe_providers() -> dict:
    """**只读能力探测**（仅调用 `capabilities()`，不发起任何网络请求）。"""
    out = {"configured_provider": MP.DEFAULT_POLICY.get("provider"),
           "require_https": MP.DEFAULT_POLICY.get("require_https"),
           "max_bytes": MP.DEFAULT_POLICY.get("max_bytes"),
           "timeout_s": MP.DEFAULT_POLICY.get("timeout_s"),
           "provider_errors": list(MP.PROVIDER_ERRORS),
           "probed": [], "external_provider_available": False}
    for cls in (getattr(MP, "LocalIngestProvider", None), getattr(MP, "LocalCatalogProvider", None),
                getattr(MP, "HttpCatalogProvider", None)):
        if cls is None:
            continue
        try:
            inst = cls({}) if cls.__name__ != "LocalCatalogProvider" else cls(None)
            cap = inst.capabilities()
            out["probed"].append(cap)
            if cap.get("is_external"):
                out["external_provider_available"] = True
        except Exception as exc:                                          # noqa: BLE001
            out["probed"].append({"provider": cls.__name__, "error": type(exc).__name__})
    wik = None
    try:
        from ..tools import provider_wikimedia as PW
        cls = None
        for name in dir(PW):
            obj = getattr(PW, name)
            if isinstance(obj, type) and hasattr(obj, "search") and hasattr(obj, "_fetch_one"):
                cls = obj
                break
        wik = {"module": "tools/provider_wikimedia.py", "api": getattr(PW, "API", None),
               "provider_class": getattr(cls, "__name__", None),
               "search": bool(cls and hasattr(cls, "search")),
               "fetch_one": bool(cls and hasattr(cls, "_fetch_one")),
               "transport_injectable": bool(cls and "transport" in
                                            (getattr(cls, "__init__").__code__.co_varnames
                                             if cls else ())),
               "note": "真实 Wikimedia Commons provider 存在且可注入 transport；"
                       "本阶段**不调用**（零网络）"}
    except Exception as exc:                                              # noqa: BLE001
        wik = {"module": "tools/provider_wikimedia.py", "error": type(exc).__name__}
    out["wikimedia_provider"] = wik
    out["live_fetch_default"] = "DISABLED（provider={}）".format(out["configured_provider"])
    return out


def load_existing_diversity_threshold(logs: Path) -> dict:
    """读取 6-G 冻结重算产物中的既有 DQ-2 阈值（**数据来源**；未新造、未修改任何阈值）。"""
    p = Path(logs) / DQ_RECOMPUTE_ARTIFACT
    if not p.is_file():
        return {"min_unique_assets": UNKNOWN, "source": str(p), "status": "NOT_AVAILABLE",
                "why": "重算产物缺失 ⇒ 不猜阈值（INSUFFICIENT_DIVERSITY 不触发）"}
    j = _json(p)
    th = (((j.get("DQ") or {}).get("after_H5") or {}).get("DQ-2") or {}).get("threshold") or {}
    v = th.get("min_unique_assets", UNKNOWN)
    return {"min_unique_assets": v, "max_asset_share": th.get("max_asset_share", UNKNOWN),
            "source": str(p), "source_sha256": sha256_file(p),
            "path_in_artifact": DQ2_THRESHOLD_PATH,
            "note": "复用 6-G 冻结重算所用既有阈值（只读数据来源；P7-5 未新造、未修改阈值）",
            "status": "OK" if isinstance(v, int) else "NOT_AVAILABLE"}


def load_sources(db: str = DEFAULT_DB, task_id: str = DEFAULT_TASK, logs: str = DEFAULT_LOGS):
    L = Path(logs)
    paths = {"requirements": _require(L / "visual_requirements.json", "P7-1"),
             "index": _require(L / "asset_index.json", "P7-2"),
             "diversity": _require(L / "asset_diversity.json", "P7-3"),
             "relevance": _require(L / "visual_relevance.json", "P7-4")}
    con = _db_ro(db)
    try:
        row = con.execute("select artifact_id,path from artifacts where type='render_output' "
                          "and task_id=? order by created_at desc limit 1", (task_id,)).fetchone()
        if not row:
            raise SourceMissing("render_output(task={}) 缺失".format(task_id))
        ro = dict(row)
    finally:
        con.close()
    ro_p = _require(Path(ro["path"]), "render_output")
    return {"requirements": _json(paths["requirements"]), "index": _json(paths["index"]),
            "diversity": _json(paths["diversity"]), "relevance": _json(paths["relevance"]),
            "render": _json(ro_p),
            "sources": [{"role": r, "path": str(p), "sha256": sha256_file(p)}
                        for r, p in (("p7_1_visual_requirements", paths["requirements"]),
                                     ("p7_2_asset_index", paths["index"]),
                                     ("p7_3_asset_diversity", paths["diversity"]),
                                     ("p7_4_visual_relevance", paths["relevance"]),
                                     ("render_output", ro_p))]}


def build_scene_evidence(src: dict) -> dict:
    """逐场景本地证据（来自 P7-4/P7-2，只读取，不做新判定）。"""
    cands = {c["asset_id"]: c for c in (src["index"].get("candidates") or [])}
    ev = {}
    for s in src["relevance"].get("scene_results") or []:
        sid = s["scene_id"]
        cur = s.get("current_asset_id")
        cur_c = cands.get(cur) or {}
        cur_res = next((c for c in s["candidate_results"] if c.get("is_scene_current_asset")), {})
        others = [c["decision"] for c in s["candidate_results"]
                  if not c.get("is_scene_current_asset")
                  and c["decision"] in ("IRRELEVANT", "RELEVANT")]
        other_relevant = sorted(c["asset_id"] for c in s["candidate_results"]
                                if not c.get("is_scene_current_asset")
                                and c["decision"] == "RELEVANT"
                                and c.get("confidence") == "HUMAN_RECORDED")
        blocker = license_block_reason(cur_c, require_license=True) if cur_c else None
        gate = license_gate_applies(cur_c, require_license=True) if cur_c else False
        lic_dec = VA.license_decision(cur_c.get("license"), cur_c.get("license_class")) \
            if cur_c else {"decision": UNKNOWN, "license_class": UNKNOWN}
        prov_gap = []
        if gate and lic_dec.get("decision") == "ALLOW":
            for f in ("provider", "source_id", "source_url", "license"):
                if (cur_c.get(f) or UNKNOWN) == UNKNOWN:
                    prov_gap.append(f)
        ev[sid] = {
            "current_asset_id": cur,
            "current_asset_decision": s.get("current_asset_decision"),
            "current_asset_evidence": [e for e in (cur_res.get("evidence") or [])][:3],
            "current_asset_license": {"license": cur_c.get("license", UNKNOWN),
                                      "license_class": cur_c.get("license_class", UNKNOWN),
                                      "license_gate_applies": gate,
                                      "block_reason_when_gate_applies": blocker if gate else None,
                                      "decision": lic_dec.get("decision")},
            "license_block": blocker if (gate and lic_dec.get("decision") == "DENY") else None,
            "provenance_incomplete_required": prov_gap or None,
            "other_candidates_reliable": sorted(others),
            "other_candidates_relevant": other_relevant,
            "other_candidates_not_assessable": sum(
                1 for c in s["candidate_results"]
                if not c.get("is_scene_current_asset") and c["decision"] == "NOT_ASSESSABLE"),
            "counts": {"candidates": s["scene_candidate_count"],
                       "relevant": s["relevant_candidate_count"],
                       "partial": s["partial_candidate_count"],
                       "irrelevant": s["irrelevant_candidate_count"],
                       "not_assessable": s["not_assessable_candidate_count"]},
        }
    return ev


def build_project_signals(src: dict, thr: dict | None = None) -> dict:
    primary = next((s for s in src["diversity"]["scopes"]
                    if s["scope"] == src["diversity"]["primary_scope"]),
                   src["diversity"]["scopes"][0])
    fam = primary["A_asset_level"]["unique_perceptual_families"]
    thr = thr or {"min_unique_assets": UNKNOWN, "status": "NOT_AVAILABLE"}
    thresh = thr.get("min_unique_assets")
    below = bool(isinstance(thresh, int) and fam < thresh)
    ext_no_url = [c["asset_id"] for c in (src["index"].get("candidates") or [])
                  if c.get("source_url") == UNKNOWN and c.get("source_type") in ("external", "web")]
    return {"diversity": {"unique_perceptual_families": fam,
                          "existing_threshold_min_unique_assets": thresh,
                          "threshold_source": thr.get("source"),
                          "threshold_source_sha256": thr.get("source_sha256"),
                          "threshold_path_in_artifact": thr.get("path_in_artifact"),
                          "threshold_status": thr.get("status"),
                          "primary_scope": primary["scope"],
                          "note": "阈值来自 6-G 冻结重算产物（只读数据），未新造阈值"},
            "diversity_below_existing_threshold": below,
            "project_provenance_gaps": {"assets_missing_source_url": ext_no_url,
                                        "count": len(ext_no_url),
                                        "note": "项目级治理缺口；**不**据此为场景批量发起获取"},
            "relevance_capability_gap": {
                "machine_visual_relevant": src["relevance"]["aggregate"][
                    "relevant_by_evidence_kind"]["machine_visual"],
                "not_assessable_pairs": src["relevance"]["aggregate"]["decision_counts"][
                    "NOT_ASSESSABLE"],
                "note": "验证能力缺口 ⇒ **不等于**缺素材，不得据此发起获取"}}


def build(db: str = DEFAULT_DB, task_id: str = DEFAULT_TASK, logs: str = DEFAULT_LOGS,
          mode: str = VA.DRY_RUN, authorize_live: bool = False,
          out_dir: str | None = None) -> dict:
    src = load_sources(db, task_id, logs)
    prov = probe_providers()
    if mode == VA.LIVE_FETCH:
        if not authorize_live:
            raise VA.AcquisitionError("LIVE_FETCH_REQUIRES_EXPLICIT_AUTHORIZATION",
                                      "默认 DRY_RUN；live 需显式 --authorize-live")
        if not out_dir:
            raise VA.AcquisitionError("LIVE_FETCH_REQUIRES_OUT_DIR", "需 --out-dir（output/ 下）")
        VA.assert_storage_boundary(out_dir)
        if prov["configured_provider"] in (None, "none", ""):
            raise VA.AcquisitionError("PROVIDER_NOT_CONFIGURED",
                                      "provider={} ⇒ 无可用外部 provider（fail-closed，不发起请求）"
                                      .format(prov["configured_provider"]))
    provider_policy = {
        "provider": prov["configured_provider"],
        "available_providers": prov["probed"],
        "allowed_source_types": ["local_ingest", "wikimedia_commons", "local_catalog"],
        "external_provider_available": prov["external_provider_available"],
        "require_https": prov["require_https"],
        "redirects": "denied",
        "max_bytes": prov["max_bytes"], "timeout_s": prov["timeout_s"],
        "provider_errors": prov["provider_errors"],
        "provider_failure_structured": "PROVIDER_* 结构化错误；禁止 silent fallback",
        "live_fetch_default": "DISABLED",
        "requirements_artifact_hash": src["requirements"].get("artifact_hash"),
        "index_artifact_hash": src["index"].get("artifact_hash"),
        "diversity_artifact_hash": src["diversity"].get("artifact_hash"),
        "relevance_artifact_hash": src["relevance"].get("artifact_hash"),
    }
    license_policy = {
        "governance": VA.LICENSE_GOVERNANCE,
        "classes": list(VA.LICENSE_BUDGET_CLASSES),
        "unknown_is_not_allow": True,
        "source": "core.materials.classify_license / license_block_reason / license_gate_applies",
        "attribution_required_for": ["FREE_ATTRIBUTION"],
    }
    ev = build_scene_evidence(src)
    thr = load_existing_diversity_threshold(Path(logs))
    sig = build_project_signals(src, thr)
    src["sources"].append({"role": "existing_dq2_threshold_source",
                           "path": thr.get("source"),
                           "sha256": thr.get("source_sha256")})
    reqs = src["requirements"].get("requirements") or []
    plan = VA.build_plan(requirements=reqs, scene_evidence=ev, provider_policy=provider_policy,
                         license_policy=license_policy, budget=VA.BUDGET_DEFAULTS, mode=mode,
                         project_signals=sig)
    plan["provider_capability_probe"] = prov
    plan["artifact_hash"] = VA.plan_hash(plan)
    plan["sources"] = src["sources"]
    # 契约示例（**真实需求**构造，明确标注为预览，不计入预算、不下载、不代表需要获取）
    if reqs:
        demo_req = next((r for r in reqs if (r.get("queries_en") or [])), reqs[0])
        preview = VA.build_request(requirement=demo_req,
                                   scene_evidence=ev.get(demo_req.get("scene_id")) or {},
                                   provider_policy=provider_policy, license_policy=license_policy,
                                   budget=VA.BUDGET_DEFAULTS, reason_code="NO_ACQUISITION_NEEDED",
                                   reason_detail={"preview": "契约示例（非获取请求）"}, mode=VA.DRY_RUN)
        preview["preview_only"] = True
        preview["not_an_acquisition_request"] = True
        preview["why"] = "仅用于展示 request 契约字段（query/query_ladder/provider/license/budget）；" \
                         "当前该场景**不需要**获取"
        del preview["deterministic_hash"]
        preview["request_id"] = "aq-preview-" + VA.sha256_text(
            VA.canonical({k: v for k, v in preview.items()
                          if k not in ("request_id", "preview_only")}))[:12]
        preview["deterministic_hash"] = VA.sha256_text(
            VA.canonical({k: v for k, v in preview.items() if k != "deterministic_hash"}))
        plan["request_contract_preview"] = preview
    plan["artifact_hash"] = VA.plan_hash(plan)
    errs = VA.validate_plan(plan)
    if errs:
        raise ValueError("acquisition plan 校验失败：{}".format("; ".join(errs[:5])))
    return plan


def verify(path: str, db: str = DEFAULT_DB, task_id: str = DEFAULT_TASK,
           logs: str = DEFAULT_LOGS) -> dict:
    old = _json(path)
    new = build(db, task_id, logs)
    if old.get("artifact_hash") != new.get("artifact_hash"):
        raise ValueError("verify 失败：artifact_hash 不一致")
    return {"ok": True, "artifact_hash": new["artifact_hash"],
            "requests": len(new["requests"])}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="visual_acquisition")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--mode", default="dry_run", choices=["dry_run", "live"])
    b.add_argument("--authorize-live", action="store_true")
    b.add_argument("--out-dir", default=None)
    b.add_argument("--db", default=DEFAULT_DB)
    b.add_argument("--task-id", default=DEFAULT_TASK)
    b.add_argument("--logs", default=DEFAULT_LOGS)
    b.add_argument("--json", action="store_true")
    v = sub.add_parser("verify")
    v.add_argument("path")
    v.add_argument("--db", default=DEFAULT_DB)
    v.add_argument("--task-id", default=DEFAULT_TASK)
    v.add_argument("--logs", default=DEFAULT_LOGS)
    a = ap.parse_args(argv)
    try:
        if a.cmd == "build":
            mode = VA.LIVE_FETCH if a.mode == "live" else VA.DRY_RUN
            plan = build(a.db, a.task_id, a.logs, mode=mode, authorize_live=a.authorize_live,
                         out_dir=a.out_dir)
            if a.json:
                print(json.dumps(plan, ensure_ascii=False, indent=1))
                return 0
            print("mode={} dry_run={} scenes={} requests={} acquisition_needed={}".format(
                plan["mode"], plan["dry_run"], plan["counts"]["scenes"],
                plan["counts"]["requests"], plan["counts"]["acquisition_needed"]))
            print("by_reason:", json.dumps(plan["counts"]["by_reason"], ensure_ascii=False))
            print("budget_ok={} usage={}".format(plan["budget_check"]["ok"],
                                                 json.dumps(plan["budget_check"]["usage"])))
            for r in plan["requests"]:
                print("  request {} scene={} reason={} fetchable={} queries={}".format(
                    r["request_id"], r["scene_id"], r["reason"]["code"], r["fetchable"],
                    len(r["queries_en"])))
            print("artifact_hash={}".format(plan["artifact_hash"]))
            return 0
        r = verify(a.path, a.db, a.task_id, a.logs)
        print("verify OK:", json.dumps(r, ensure_ascii=False))
        return 0
    except VA.AcquisitionError as exc:
        print("FAIL-CLOSED [{}]: {}".format(exc.code, exc.detail), file=sys.stderr)
        return 3 if exc.code.startswith("LIVE_FETCH_REQUIRES") else 2
    except Exception as exc:                                              # noqa: BLE001
        print("FAIL-CLOSED [{}]: {}".format(type(exc).__name__, exc), file=sys.stderr)
        return 2


if __name__ == "__main__":                                                 # pragma: no cover
    sys.exit(main())
