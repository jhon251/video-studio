# -*- coding: utf-8 -*-
"""P14-2 真值集候选盘点（只读）：把每一对可标注的 (scene, asset) 与其人工标签列举出来。

标签语义（严格）：
  RELEVANT   —— 人工**明确接受/选定**该 (scene, asset)
  IRRELEVANT —— 人工**明确否决/替换掉**该 (scene, asset)
  （未出现人工正/负证据的对，一律不进入本清单：不得把机器判定充当人工真值）
"""
from __future__ import annotations

import json
import pathlib
import sqlite3
import sys
from collections import Counter, defaultdict

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")

pos: dict[tuple, dict] = {}
neg: dict[tuple, dict] = {}

# ---------- 来源 A：visual_relevance.json 的人工证据 ----------
vr = json.loads((L / "visual_relevance.json").read_text(encoding="utf-8"))
for s in vr["scene_results"]:
    for c in (s.get("candidate_results") or []):
        d = c.get("decision")
        if d not in ("RELEVANT", "IRRELEVANT"):
            continue
        key = (c["scene_id"], c["asset_id"])
        ev = (c.get("evidence") or [{}])[0]
        det = ev.get("detail") or {}
        rec = {"scene_id": c["scene_id"], "asset_id": c["asset_id"],
               "requirement_id": c["requirement_id"], "label": d,
               "source": "A:visual_relevance.json",
               "rule": c.get("decision_rule"),
               "human_reason": str(det.get("reason") or "")[:160],
               "human_by": det.get("by"), "evidence_kind": ev.get("kind")}
        (pos if d == "RELEVANT" else neg)[key] = rec

# ---------- 来源 E：DB selection_override（人工选定 = 正；被替换掉的 = 负）----------
con = sqlite3.connect("file:" + (R / "projects" / "video_studio.db").as_posix() + "?mode=ro",
                      uri=True)
con.row_factory = sqlite3.Row
SO = [dict(r) for r in con.execute(
    "select decision_id, made_by, rationale, artifact_snapshot from decisions "
    "where node='selection_override'")]
con.close()

so_pos, so_neg = {}, {}
for d in SO:
    snap = d.get("artifact_snapshot")
    try:
        j = json.loads(snap) if isinstance(snap, str) else snap
    except Exception:                                                       # noqa: BLE001
        continue
    if not isinstance(j, dict):
        continue
    sid, aid, before = j.get("scene_id"), j.get("asset_id"), j.get("before_asset_id")
    if sid and aid and not str(aid).startswith("asset_不存在"):
        k = (sid, aid)
        so_pos.setdefault(k, {
            "scene_id": sid, "asset_id": aid, "label": "RELEVANT",
            "source": "E:db.selection_override(human selected)",
            "human_reason": str(d.get("rationale") or "")[:160],
            "human_by": d.get("made_by"), "decision_id": d.get("decision_id")})
    if sid and before:
        k2 = (sid, before)
        so_neg.setdefault(k2, {
            "scene_id": sid, "asset_id": before, "label": "IRRELEVANT",
            "source": "E:db.selection_override(human replaced away)",
            "human_reason": str(d.get("rationale") or "")[:160],
            "human_by": d.get("made_by"), "decision_id": d.get("decision_id")})

# ---------- 来源 B：review ledger 的人工否决（需可解析出 scene/asset）----------
led = [json.loads(x) for x in (L / "phase6b_m2_review_ledger_v9.jsonl")
       .read_text(encoding="utf-8").splitlines() if x.strip()]
led_pairs = []
for x in led:
    if x.get("decision") == "REJECT" and x.get("scene_id") and x.get("asset_id"):
        led_pairs.append({"scene_id": x["scene_id"], "asset_id": x["asset_id"],
                          "label": "IRRELEVANT", "source": "B:review_ledger_v9",
                          "human_reason": str(x.get("reason") or "")[:160],
                          "human_by": x.get("decided_by"),
                          "finding_id": x.get("finding_id")})

print("=" * 78)
print("来源 A（visual_relevance 人工证据）")
print("=" * 78)
print("  RELEVANT 对:", len(pos), " | IRRELEVANT 对:", len(neg))
for k, v in sorted(pos.items()):
    print("   + {} {}".format(k[0], k[1]))
for k, v in sorted(neg.items()):
    print("   - {} {} | {}".format(k[0], k[1], v["human_reason"][:70]))

print()
print("=" * 78)
print("来源 E（DB selection_override）")
print("=" * 78)
print("  选定(=正):", len(so_pos), " | 被替换掉(=负):", len(so_neg))
for k, v in sorted(so_pos.items()):
    print("   + {} {} | {}".format(k[0], k[1], v["human_reason"][:70]))
for k, v in sorted(so_neg.items()):
    print("   - {} {} | {}".format(k[0], k[1], v["human_reason"][:70]))

print()
print("=" * 78)
print("来源 B（review ledger 可解析对）")
print("=" * 78)
print("  条数:", len(led_pairs))
for v in led_pairs:
    print("   - {} {} | {}".format(v["scene_id"], v["asset_id"], v["human_reason"][:70]))

# ---------- 合并 ----------
merged_pos = dict(pos)
for k, v in so_pos.items():
    merged_pos.setdefault(k, v)
merged_neg = dict(neg)
for k, v in so_neg.items():
    merged_neg.setdefault(k, v)
for v in led_pairs:
    merged_neg.setdefault((v["scene_id"], v["asset_id"]), v)

print()
print("=" * 78)
print("合并后（去重）")
print("=" * 78)
print("  RELEVANT :", len(merged_pos))
print("  IRRELEVANT:", len(merged_neg))
total = len(merged_pos) + len(merged_neg)
print("  合计     :", total)

# 与 asset_index 可配对性（图像必须真实存在且属于 8 个索引素材）
ai = json.loads((L / "asset_index.json").read_text(encoding="utf-8"))
idx_by_asset = {c["asset_id"]: c for c in ai["candidates"]}
print()
print("  可在 asset_index 中解析到图像的:")
okp = [k for k in merged_pos if k[1] in idx_by_asset]
okn = [k for k in merged_neg if k[1] in idx_by_asset]
print("    RELEVANT :", len(okp), "/", len(merged_pos))
print("    IRRELEVANT:", len(okn), "/", len(merged_neg))
notin = sorted({k[1] for k in list(merged_pos) + list(merged_neg)
                if k[1] not in idx_by_asset})
print("    不在 8 素材索引中的 asset_id:", notin)

# 需求可解析性
reqs = json.loads((L / "visual_requirements.json").read_text(encoding="utf-8"))["requirements"]
req_by_scene = {r["scene_id"]: r for r in reqs}
print()
print("  场景在 visual_requirements 中的:")
print("    RELEVANT 场景可解析:", sum(1 for k in merged_pos if k[0] in req_by_scene))
print("    IRRELEVANT 场景可解析:", sum(1 for k in merged_neg if k[0] in req_by_scene))

out = {
    "provenance_note": "仅收录**存在人工正/负证据**的 (scene, asset) 对；机器判定不得充当人工真值",
    "relevant": [v for _, v in sorted(merged_pos.items())],
    "irrelevant": [v for _, v in sorted(merged_neg.items())],
    "counts": {"relevant": len(merged_pos), "irrelevant": len(merged_neg),
               "total": total,
               "resolvable_image_relevant": len(okp),
               "resolvable_image_irrelevant": len(okn)},
}
p = L / "phase14_label_inventory.json"
p.write_text(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
print()
print("inventory ->", p)
