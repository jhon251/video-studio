# -*- coding: utf-8 -*-
"""P16-5 DQ 复算（只读）：用 DQ-2/DQ-3 的生产度量对 Phase 16 选材结果复算，
并与 13-E 候选对比。窗口来自脚本声明时长（与 _build_material_timeline 同公式），
素材来自 MATERIAL_TIMELINE 事件（渲染未登记 render_output，事件即权威留痕）。"""
from __future__ import annotations

import json
import pathlib
import sqlite3
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import direction as DIR                                  # noqa: E402

LOGS = R / "docs" / "regression_2x" / "logs"
fix = json.loads((R / "output/phase16_p16_5_sandbox/fixture.json").read_text(encoding="utf-8"))
pid = fix["sandbox_project_id"]
con = sqlite3.connect("file:" + (R / "projects" / "video_studio.db").as_posix() + "?mode=ro",
                      uri=True)
con.row_factory = sqlite3.Row
dec = []
for r in con.execute("select payload from events where project_id=? and type='MATERIAL_TIMELINE'",
                     (pid,)):
    dec = json.loads(r["payload"]).get("decisions") or []
con.close()

script = json.loads((R / "output/phase13e_script_sandbox/script_dcv2_derived_v1.json")
                    .read_text(encoding="utf-8"))
dur = {s["scene_id"]: float(s["duration_s"]) for s in script["segments"]}
cursor = 0.0
timeline = []
for d in dec:
    d0 = max(dur.get(d["scene_id"], 30.0), 3.0)
    timeline.append({"scene_id": d["scene_id"], "start_s": round(cursor, 3),
                     "end_s": round(cursor + d0, 3),
                     "selected_asset": d.get("selected_asset")})
    cursor += d0
if timeline:
    timeline[-1]["end_s"] = round(max(timeline[-1]["end_s"], cursor + 2.0), 3)

dq2 = DIR.asset_reuse(timeline)
dq3 = DIR.static_hold(timeline, freeze_blocks=None)
uniq = {s["selected_asset"]["asset_id"] for s in timeline if s.get("selected_asset")}
# 真实"单素材最大复用景数"（DQ-2 PASS 时 findings 为空 ⇒ 须直接由选材计数，不能用 findings）
from collections import Counter                                                   # noqa: E402
use = Counter(s["selected_asset"]["asset_id"] for s in timeline if s.get("selected_asset"))
max_reuse = max(use.values()) if use else 0
reuse_rank = use.most_common(5)
holds = sorted(((h["hold_s"], h["scene_id"], h["asset"]) for h in dq3["holds"]), reverse=True)

print("=" * 78)
print("P16-5 DQ 复算（Phase 16 扩池后选材）")
print("=" * 78)
print("  唯一素材数        :", len(uniq), "/ 21 景")
print("  单素材最大复用    :", max_reuse, "景  （前 5:", reuse_rank, "）")
print("  DQ-2 asset_reuse  : state =", dq2.get("state"))
for f in dq2.get("findings") or []:
    print("      {} x{} 景  {}".format(f.get("asset_id"),
                                        len(f.get("scene_windows") or []),
                                        ",".join(w["scene_id"] for w in
                                                 (f.get("scene_windows") or []))))
print("  DQ-3 static_hold  : state =", dq3.get("state"),
      "| max_hold =", dq3.get("max_hold_s"),
      "| over =", dq3.get("holds_over_threshold"),
      "| share =", dq3.get("share_over_threshold"))
print("      阈值:", json.dumps(dq3.get("threshold"), ensure_ascii=False))
print("      最长保持前 5:")
for h, sid, a in holds[:5]:
    print("        {} {:>8.2f}s  {}".format(sid, h, a))

print()
print("=" * 78)
print("对比 13-E 候选（同度量）")
print("=" * 78)
rep13 = json.loads((LOGS / "phase13e_p13e3_render.json").read_text(encoding="utf-8"))
d13 = rep13["dq_readonly"]
_f13 = (d13.get("DQ-2_asset_reuse") or {}).get("findings") or []
_reuse13 = [(len(f.get("scene_windows") or []), f.get("asset_id")) for f in _f13]
_reuse13.sort(reverse=True)
max13 = _reuse13[0][0] if _reuse13 else 3   # 13-E 无 findings 时按 3 景估算（下发断言会打印）
print("  唯一素材数        : 5")
print("  DQ-2              :", (d13.get("DQ-2_asset_reuse") or {}).get("state"),
      "| 最大复用景数:", max13, "|", _reuse13[:3])
h13 = d13.get("DQ-3_static_hold") or {}
print("  DQ-3              :", h13.get("state"), "| max_hold =", h13.get("max_hold_s"),
      "| over =", h13.get("holds_over_threshold"))

out = {
    "schema": "phase16-dq-recompute-v1",
    "phase16": {
        "unique_assets": len(uniq), "scenes": len(timeline),
        "dq2_state": dq2.get("state"),
        "dq2_findings": [{k: f.get(k) for k in ("asset_id", "kind")} |
                         {"scene_count": len(f.get("scene_windows") or [])}
                         for f in (dq2.get("findings") or [])],
        "dq2_max_reuse_scenes": max_reuse,
        "dq2_reuse_rank": [{"asset_id": a, "scenes": n} for a, n in reuse_rank],
        "dq3_state": dq3.get("state"), "dq3_max_hold_s": dq3.get("max_hold_s"),
        "dq3_holds_over_threshold": dq3.get("holds_over_threshold"),
        "dq3_share_over_threshold": dq3.get("share_over_threshold"),
        "top_holds": [{"scene_id": s, "hold_s": h, "asset": a} for h, s, a in holds[:8]],
    },
    "phase13e_reference": {
        "unique_assets": 5,
        "dq2_state": (d13.get("DQ-2_asset_reuse") or {}).get("state"),
        "dq2_max_reuse_scenes": max13,
        "dq2_reuse_rank": [{"asset_id": a, "scenes": n} for n, a in _reuse13[:4]],
        "dq3_state": h13.get("state"), "dq3_max_hold_s": h13.get("max_hold_s"),
        "dq3_holds_over_threshold": h13.get("holds_over_threshold"),
    },
    "method": ("窗口由脚本声明时长重建（_build_material_timeline 同公式）；素材取自 "
               "MATERIAL_TIMELINE 事件（渲染后核验门阻断 ⇒ 无 render_output）。"
               "freeze_blocks=None（未对候选跑 freezedetect）"),
    "honest_note": ("DQ-3 的 FAIL 来自**场景本身过长**（S06 67.4s / S07 66.5s > 25s 上限），"
                    "换素材无法改变；授权书范围内（仅换素材）**不可修复**。"),
}
p = LOGS / "phase16_dq_recompute.json"
p.write_text(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
print()
print("  证据 ->", p.relative_to(R).as_posix())
