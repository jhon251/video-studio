# -*- coding: utf-8 -*-
"""6-E —— 冻结第二轮真值集（规范化 sha256 写回 + 记录摘要）。

用法: python docs/regression_2x/phase6e_build_truth.py
产出: logs/phase6e_truth_freeze.json
"""
import hashlib
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
LOGS = ROOT / "docs" / "regression_2x" / "logs"
TRUTH = ROOT / "tests" / "fixtures" / "directorial_round2_truth_v1.json"
R2 = LOGS / "phase6e_round2.json"
OUT = LOGS / "phase6e_truth_freeze.json"


def canonical(obj: dict) -> str:
    return hashlib.sha256(json.dumps({k: v for k, v in obj.items() if k != "frozen_sha256"},
                                     sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


data = json.loads(TRUTH.read_text(encoding="utf-8"))
sha = canonical(data)
data["frozen_sha256"] = sha
TRUTH.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
assert canonical(json.loads(TRUTH.read_text(encoding="utf-8"))) == sha

d = json.loads(R2.read_text(encoding="utf-8")) if R2.is_file() else {}
rec = {"schema": "directorial-round2-freeze-v1", "stage": "6-E",
       "truth_path": TRUTH.relative_to(ROOT).as_posix(),
       "truth_canonical_sha256": sha,
       "truth_file_sha256": hashlib.sha256(TRUTH.read_bytes()).hexdigest(),
       "review_entries": len(d.get("human_review_round2") or []),
       "proposal_count": d.get("proposal_count"),
       "proposals": [{"label": p["label"], "action": p["action"],
                      "scenes": p["affected_scope"]["scenes"],
                      "window": p["affected_scope"]["window"],
                      "share_of_film": p["affected_scope"]["share_of_film"],
                      "needs_new_material": p["material_requirement"]["needs_new_material"],
                      "needs_new_content_self_created":
                          p["material_requirement"]["needs_new_content_self_created"],
                      "asset_id": p["material_requirement"]["asset_id"],
                      "proposal_id": p["proposal_id"]}
                     for p in d.get("proposals") or []],
       "retention": [(r["kind"], r["scene_id"]) for r in d.get("retention_records") or []],
       "internal_conflicts": (d.get("conflict_matrix_6e") or {}).get("conflict_pair_count"),
       "cross_batch_overlaps": len(d.get("cross_batch_overlaps") or []),
       "integrity": d.get("integrity"),
       "note": "本阶段**只登记方案**：未执行、未渲染、未修改 C1–C4 / v9 / DB / timeline / 字幕 / 素材。"}
OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
print("truth canonical sha256:", sha)
print("review", rec["review_entries"], "| proposals", rec["proposal_count"],
      "| internal conflicts", rec["internal_conflicts"],
      "| cross-batch", rec["cross_batch_overlaps"])
print("proposals:", [(p["label"][:2], p["action"], p["scenes"]) for p in rec["proposals"]])
print("retention:", rec["retention"], "| 未执行:", (rec["integrity"] or {}).get("executed_anything"))
print("json ->", OUT)
