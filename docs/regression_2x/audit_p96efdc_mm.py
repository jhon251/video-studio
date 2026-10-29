# -*- coding: utf-8 -*-
"""审计 H：对 p_96efdc03e1aa **按镜头**跑 4-B / 5-A / 5-D 并用 Judge 的 J0–J6 融合（只读）。

说明：`run.py mm-judge` 是**冻结真值集驱动**的（对任意项目不适用，见审计发现）；
本脚本直接用 `mm_judge.judge_scene` 把三层的**逐镜头**结果融合，得到该项目的最终判定。

用法：python docs/regression_2x/audit_p96efdc_mm.py
产出：docs/regression_2x/logs/audit_p96efdc_mm.json
"""
import json
import pathlib
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
PID = "p_96efdc03e1aa"
LOGS = ROOT / "docs" / "regression_2x" / "logs"

from video_studio.core.mm_judge import judge_scene  # noqa: E402
from video_studio.ops.metrics import semantic_report  # noqa: E402
from video_studio.ops.mm_temporal import temporal_report  # noqa: E402
from video_studio.ops.multimodal import multimodal_report  # noqa: E402

DB = ROOT / "projects" / "video_studio.db"
cfg = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8-sig"))
tmp = pathlib.Path(tempfile.mkdtemp(prefix="audit_p96_mm_"))

print("=== 4-B（文本语义）===")
r4b = semantic_report(DB, PID)
s4b = {s["scene_id"]: s for s in r4b.get("scenes") or []}
print("  counts:", r4b.get("counts"))

print("\n=== 5-A（单帧 CLIP，3 帧/镜头）===")
r5a = multimodal_report(DB, PID, config=cfg, frames_dir=tmp / "5a")
s5a = {s["scene_id"]: s for s in r5a.get("scenes") or []}
print("  counts:", r5a.get("counts"), "| frames:", (r5a.get("meta") or {}).get("frames_extracted"))

print("\n=== 5-D（多帧时序，7 帧/镜头）===")
r5d = temporal_report(DB, PID, config=cfg, frames_dir=tmp / "5d", with_five_a=False)
s5d = {s["scene_id"]: s for s in r5d.get("scenes") or []}
print("  counts:", r5d.get("counts"), "| frames:", (r5d.get("meta") or {}).get("frames_extracted"))

rows = []
for sid in sorted(set(s4b) | set(s5a) | set(s5d)):
    a, b, c = s4b.get(sid) or {}, s5a.get(sid) or {}, s5d.get(sid) or {}
    layers = {"4b": {"verdict": a.get("verdict"), "code": a.get("code") or a.get("rule")},
              "5a": {"verdict": b.get("verdict"), "code": b.get("code")},
              "5d": {"verdict": c.get("verdict"), "code": c.get("code")}}
    j = judge_scene(layers)
    rows.append({"scene_id": sid,
                 "4b": a.get("verdict"), "5a": b.get("verdict"), "5d": c.get("verdict"),
                 "judge": j["verdict"], "rule": j["rule"], "reason_code": j["reason_code"],
                 "expected_domain": c.get("expected_domain") or b.get("expected_domain"),
                 "5d_margin": (c.get("aggregate") or {}).get("median_margin"),
                 "5d_vote": (c.get("aggregate") or {}).get("vote_expected"),
                 "5d_stability": (c.get("stability") or {}).get("visual_stability_mean"),
                 "asset": ((c.get("frames") or [{}])[0] or {}).get("id")})
counts = {"MATCH": 0, "MISMATCH": 0, "UNKNOWN": 0}
reasons = {}
for r in rows:
    counts[r["judge"]] = counts.get(r["judge"], 0) + 1
    reasons[r["reason_code"]] = reasons.get(r["reason_code"], 0) + 1
print("\n=== 逐镜头最终判定（4-B / 5-A / 5-D → Judge J0–J6）===")
for r in rows:
    print("  {:<4} 4B={:<8} 5A={:<8} 5D={:<8} → {:<9} {:<26} 期望域={:<16} 边际={} 投票={} 一致性={}".format(
        r["scene_id"], str(r["4b"]), str(r["5a"]), str(r["5d"]), str(r["judge"]),
        str(r["reason_code"]), str(r["expected_domain"]), r["5d_margin"], r["5d_vote"],
        r["5d_stability"]))
print("\n最终计数:", counts, "| 理由码:", reasons)
out = {"project_id": PID, "counts_4b": r4b.get("counts"), "counts_5a": r5a.get("counts"),
       "counts_5d": r5d.get("counts"), "judge_counts": counts, "reason_codes": reasons,
       "rows": rows,
       "note": "5-A/5-D 由本项目现场只读重跑得到；Judge 用 core.mm_judge.judge_scene 逐镜头融合"}
(LOGS / "audit_p96efdc_mm.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                            encoding="utf-8")
print("written", LOGS / "audit_p96efdc_mm.json")
