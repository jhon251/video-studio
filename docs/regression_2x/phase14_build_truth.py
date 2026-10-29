# -*- coding: utf-8 -*-
"""P14-2 冻结真值集构建：`tests/fixtures/vlm_relevance_truth_v1.json`。

**收录纪律**：只收录**存在逐对人工正/负证据**的 (要求, 素材图) 对；
机器判定、词面匹配、时长类 DQ 发现**一律不得**充当人工真值。
每条记录带 provenance（来源文件 + 定位字段 + 人工原文理由）。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
FIX = R / "tests" / "fixtures"
sys.stdout.reconfigure(encoding="utf-8")

GATE = {"min_agreement": 0.90, "max_human_irrelevant_to_machine_relevant": 0}
MIN_PAIRS = 30


def norm12(x: str) -> str:
    """把 `asset_<sha12>` / `ast-<hash16>` 归一到 12 位 hex 前缀（同一素材的两种命名）。"""
    s = str(x or "")
    for pre in ("asset_h5_", "asset_", "ast-"):
        if s.startswith(pre):
            s = s[len(pre):]
            break
    return s[:12]


reqs = json.loads((L / "visual_requirements.json").read_text(encoding="utf-8"))["requirements"]
req_by_scene = {r["scene_id"]: r for r in reqs}
ai = json.loads((L / "asset_index.json").read_text(encoding="utf-8"))
assets = {norm12(c["asset_id"]): c for c in ai["candidates"]}

#: 扩展索引：**仅**收录有逐对人工标签、且文件真实存在、但不在冻结 7-2 素材索引内的素材。
#: 之所以收录：这些正是人工**接受**（H5 S05/S11）或人工**否决**所指向的真实上屏素材；
#: 排除它们会把最强的人工正/负证据丢掉。全部逐条登记 provenance 与合法性。
EXTENDED = [
    {"asset_id": "asset_h5_S05_65377b888b778226",
     "path": r"C:\mp4agent\h5_asset_candidates\S05\Russell_PM_1+1=2.png",
     "note": "H5 人工验收接受的 S05 上屏素材（PD-US）"},
    {"asset_id": "asset_h5_S11_1e9d2ab4e64ef982",
     "path": r"C:\mp4agent\h5_asset_candidates\S11\research\S11-DIPIcs-ITP-2023-24_p08_tactic-state-rw.png",
     "note": "H5 人工验收接受的 S11 上屏素材（CC BY 4.0）"},
]
for e in EXTENDED:
    p = pathlib.Path(e["path"])
    if not p.is_file():
        # 容错：按 sha 前缀在候选目录内查找
        base = pathlib.Path(r"C:\mp4agent\h5_asset_candidates")
        pref = norm12(e["asset_id"].split("_")[-1])
        hits = [f for f in base.rglob("*.png") if norm12(
            hashlib.sha256(f.read_bytes()).hexdigest()) == pref]
        if hits:
            p = hits[0]
    if not p.is_file():
        print("!! 扩展素材文件缺失，跳过:", e["asset_id"])
        continue
    sha = hashlib.sha256(p.read_bytes()).hexdigest()
    assets[norm12(sha)] = {"asset_id": e["asset_id"], "path": str(p), "sha256": sha,
                           "bytes": p.stat().st_size, "_extended": True, "_note": e["note"]}
    print("扩展素材已收录:", norm12(sha), p.name, "|", e["note"])

vr = json.loads((L / "visual_relevance.json").read_text(encoding="utf-8"))

pairs: list[dict] = []

# ---------------- P7-4 需求构建的上游输入（narration / shot_description）----------------
# `visual_requirements.json#source_identity` 明确记录：P7-4 的需求由
#   `shot_description`（→ visual_goal）+ `narration` + `shot_plan` 三者构建。
# 因此需求文本必须同时给出「画面目标」与「本镜旁白」，否则模型看到的需求比 P7-4 自身
# 可用的更贫瘠（会把「主题相关」一律判无关）。**这里只回填 P7-4 构建时已用的输入**，
# 不提供任何候选排序、分数或人工结论。
_script_p = (R / "output" / "phase13e_script_sandbox" / "script_dcv2_derived_v1.json")
_script = json.loads(_script_p.read_text(encoding="utf-8")) if _script_p.is_file() else {}
narr_by_scene = {s.get("scene_id"): (s.get("narration") or "")
                 for s in (_script.get("segments") or [])}
if not narr_by_scene:      # 回退：既有 21 段脚本产物
    for f in sorted((R / "projects" / "p_96efdc03e1aa" / "artifacts").glob("a_49b58fb3dc01.json")):
        j = json.loads(f.read_text(encoding="utf-8"))
        narr_by_scene = {("S{:02d}".format(i + 1)): (s.get("narration") or "")
                         for i, s in enumerate(j.get("segments") or [])}

# ---------------- 来源 A：visual_relevance.json 的人工正/负证据 ----------------
for s in vr["scene_results"]:
    for c in (s.get("candidate_results") or []):
        d = c.get("decision")
        if d not in ("RELEVANT", "IRRELEVANT"):
            continue
        ev = (c.get("evidence") or [{}])[0]
        det = ev.get("detail") or {}
        pairs.append({
            "pair_id": "A-{}-{}".format(c["scene_id"], norm12(c["asset_id"])),
            "scene_id": c["scene_id"],
            "requirement_id": c["requirement_id"],
            "asset_key12": norm12(c["asset_id"]),
            "human_label": d,
            "human_reason": str(det.get("reason") or ""),
            "human_by": det.get("by") or det.get("source"),
            "provenance": {
                "source": "logs/visual_relevance.json",
                "locator": "scene_results[scene_id={}].candidate_results[asset_id={}]".format(
                    c["scene_id"], c["asset_id"]),
                "evidence_kind": ev.get("kind"),
                "decision_rule": c.get("decision_rule"),
                "confidence": c.get("confidence"),
            },
        })

# ---------------- 来源 F：H5 人工接受（S05/S11 的替换素材）----------------
# 人工验收原文：`phase6g_exec_h5.json#human_decision = "D0 / S05 PD-US（人工已接受地域）"`，
# 且 `binding`/`asset_records`/`asset_replacement_evidence` 记载该素材**已上屏**。
h5 = json.loads((L / "phase6g_exec_h5.json").read_text(encoding="utf-8"))
for sid, rec in (h5.get("asset_records") or {}).items():
    pairs.append({
        "pair_id": "F-{}-{}".format(sid, norm12(rec["sha256"])),
        "scene_id": sid,
        "requirement_id": None,
        "asset_key12": norm12(rec["sha256"]),
        "human_label": "RELEVANT",
        "human_reason": "人工验收接受该素材用于本镜（H5 human_decision: {}）".format(
            h5.get("human_decision")),
        "human_by": "human（H5 acceptance，见 phase6g_exec_h5.human_decision）",
        "provenance": {
            "source": "logs/phase6g_exec_h5.json",
            "locator": "asset_records[{}] + binding + asset_replacement_evidence.per_scene".format(sid),
            "human_decision": h5.get("human_decision"),
            "license": rec.get("license"),
            "on_screen": True,
        },
    })

# ---------------- 来源 B/D：人工否决（负例）----------------
led = [json.loads(x) for x in (L / "phase6b_m2_review_ledger_v9.jsonl")
       .read_text(encoding="utf-8").splitlines() if x.strip()]
for x in led:
    if x.get("decision") == "REJECT" and x.get("scene_id") and x.get("asset_id"):
        pairs.append({
            "pair_id": "B-{}-{}".format(x["scene_id"], norm12(x["asset_id"])),
            "scene_id": x["scene_id"],
            "requirement_id": None,
            "asset_key12": norm12(x["asset_id"]),
            "human_label": "IRRELEVANT",
            "human_reason": str(x.get("reason") or ""),
            "human_by": x.get("decided_by"),
            "provenance": {"source": "logs/phase6b_m2_review_ledger_v9.jsonl",
                           "locator": "finding_id={}".format(x.get("finding_id")),
                           "ledger_entry_sha256": x.get("entry_sha256")},
        })

# ---------------- 去重（同 scene × 同素材只保留一条；人工负例优先于正例）----------------
byl: dict[tuple, dict] = {}
for p in sorted(pairs, key=lambda q: (q["human_label"] != "IRRELEVANT", q["pair_id"])):
    k = (p["scene_id"], p["asset_key12"])
    if k in byl:
        byl[k]["also_claimed"] = byl[k].get("also_claimed", []) + [
            {"human_label": p["human_label"], "source": p["provenance"]["source"],
             "note": "**同对存在冲突的人工证据，已按负例优先并如实登记**"}]
        continue
    byl[k] = p
final = list(byl.values())

# ---------------- 解析出可评估性（需求 + 图像路径）----------------
rows, unresolvable = [], []
for p in final:
    req = req_by_scene.get(p["scene_id"])
    a = assets.get(p["asset_key12"])
    if req is None or a is None:
        unresolvable.append({"pair_id": p["pair_id"],
                             "has_requirement": req is not None,
                             "has_asset": a is not None})
        continue
    pth = pathlib.Path(a["path"])
    if not pth.is_file():
        unresolvable.append({"pair_id": p["pair_id"], "reason": "图像文件不存在",
                             "path": a["path"]})
        continue
    p["asset_id"] = a["asset_id"]
    p["asset_sha256"] = a["sha256"]
    p["asset_origin"] = ("extended-index（不在冻结 7-2 素材索引内；逐条登记）"
                         if a.get("_extended") else "frozen asset_index.json")
    p["image_path"] = a["path"].replace("\\", "/")
    p["image_bytes"] = a["bytes"]
    p["requirement_snapshot"] = {
        k: req.get(k) for k in ("scene_id", "visual_goal", "subject", "action", "object",
                                "environment", "concept", "concepts_pos", "concepts_neg",
                                "avoid_list", "expected_kind", "evidence_type", "status")}
    p["requirement_snapshot"]["narration"] = narr_by_scene.get(p["scene_id"]) or ""
    p["requirement_snapshot"]["requirement_artifact_hash"] = \
        (vr.get("requirements_snapshot") or {}).get("artifact_hash")
    rows.append(p)

rows.sort(key=lambda p: (p["scene_id"], p["asset_key12"]))
counts = {"RELEVANT": 0, "IRRELEVANT": 0}
for p in rows:
    counts[p["human_label"]] += 1

doc = {
    "schema": "vlm-relevance-truth-v1",
    "version": 1,
    "purpose": ("P14-2 真实评测门禁的冻结真值集：VLM 视觉相关性判定 vs 人工真值"),
    "label_semantics": {
        "RELEVANT": "人工明确接受/选定该 (镜头, 素材) 组合",
        "IRRELEVANT": "人工明确否决该 (镜头, 素材) 组合",
        "excluded": "PARTIAL / NOT_ASSESSABLE 无逐对人工真值 ⇒ **不收录**（不得由机器判定充当真值）",
    },
    "gate_frozen_before_run": {
        "min_agreement": GATE["min_agreement"],
        "max_human_irrelevant_to_machine_relevant":
            GATE["max_human_irrelevant_to_machine_relevant"],
        "note": "达标线**运行前写死**（见 PHASE14_REPORT.md §4 / 授权书）；运行后不得调整",
    },
    "min_pairs_required": MIN_PAIRS,
    "pair_count": len(rows),
    "meets_min_pairs": len(rows) >= MIN_PAIRS,
    "counts": counts,
    "sources_used": sorted({p["provenance"]["source"] for p in rows}),
    "unresolvable": unresolvable,
    "pairs": rows,
}
FIX.mkdir(parents=True, exist_ok=True)
out = FIX / "vlm_relevance_truth_v1.json"
raw = json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=True)
out.write_text(raw, encoding="utf-8")
h = hashlib.sha256(raw.encode("utf-8")).hexdigest()

print("=== 冻结真值集 ===")
print("  文件 :", out)
print("  sha256:", h)
print("  对数 :", len(rows), "| 达标要求 ≥", MIN_PAIRS,
      "⇒", "满足" if len(rows) >= MIN_PAIRS else "**不足（如实登记）**")
print("  分布 :", counts)
print("  来源 :", doc["sources_used"])
if unresolvable:
    print("  无法解析:", json.dumps(unresolvable, ensure_ascii=False))
print()
print("  逐对（label | scene | asset | 人工理由）:")
for p in rows:
    print("   {:10s} {} {} | {}".format(p["human_label"], p["scene_id"],
                                        p["asset_key12"], p["human_reason"][:64]))
print()
print("  truth sha256 =", h)
