# -*- coding: utf-8 -*-
"""H5 后 **DQ 完整复算**（只读）：修正投影缺陷 + 补评 DQ-3 成片冻结块分量 + DQ-5 前后归因。

产出: docs/regression_2x/logs/phase6g_h5_dq_recompute.json
"""
import hashlib
import json
import pathlib
import sqlite3
import sys
import time

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import direction as core_direction            # noqa: E402
from video_studio.ops import execution as OPX                        # noqa: E402

L = R / "docs" / "regression_2x" / "logs"
FF = str(R / "bin/ffmpeg.exe")
OUT = L / "phase6g_h5_dq_recompute.json"
P2 = json.loads((L / "phase6f_rebuild_plan_v2.json").read_text(encoding="utf-8"))
B1 = json.loads((L / "phase6g_exec_batch1.json").read_text(encoding="utf-8"))
H5R = json.loads((L / "phase6g_exec_h5.json").read_text(encoding="utf-8"))
E45 = json.loads((L / "phase6g_exec_e4_e5.json").read_text(encoding="utf-8"))
regs = [json.loads(x) for x in (L / "phase6g_rebuild_proposal_register.jsonl").read_text(
    encoding="utf-8").splitlines() if x.strip()]
con = sqlite3.connect("file:{}?mode=ro".format(
    (R / "projects/video_studio.db").as_posix()), uri=True)
con.row_factory = sqlite3.Row
con.execute("PRAGMA query_only=ON")
row = next(dict(x) for x in con.execute(
    "select path from artifacts where type='render_output' and task_id='t_d0a54bdf1810'"))
con.close()
rend = json.loads(pathlib.Path(row["path"]).read_text(encoding="utf-8"))
OLD = {str(e.get("scene_id")): (e.get("selected_asset") or {})
       for e in (rend.get("material_timeline") or [])}
NEW = {s: dict(H5R["asset_records"][s]) for s in ("S05", "S11")}
script = json.loads((R / B1["sandbox"] / "artifacts/script_output.json").read_text(encoding="utf-8"))
chain = P2["remapping_21_segments"]
TL = [{"scene_id": c["scene_id"], "start_s": c["new_timeline_window_s"][0],
       "end_s": c["new_timeline_window_s"][1]} for c in chain]


def build(with_new: bool) -> list:
    proj = [dict(e, selected_asset=OLD.get(e["scene_id"], {})) for e in TL]
    for stage in ("H3a", "H3b"):
        sp = next(s["exec"]["exec_evidence"]["split_plan"] for s in B1["stages"]
                  if s["stage"] == stage)
        _apply(proj, sp, OLD, ("S11",) if (with_new and stage == "H3b") else ())
    for lab in ("H3c-1", "H3c-2"):
        p = next(x for x in regs if x.get("label") == lab)
        sp = OPX.split_plan({"timeline": [dict(e) for e in TL], "timeline_identity": None,
                             "caption_timeline": None}, p)
        _apply(proj, sp, OLD, ("S05",) if with_new else ())
    if with_new:
        for e in proj:
            if e["scene_id"] in NEW:
                e["selected_asset"] = NEW[e["scene_id"]]
    return proj


def _apply(entries, sp, amap, replace_scenes=()):
    for rr in sp.get("scenes", []):
        base = next(e for e in entries if e["scene_id"] == rr["scene_id"])
        d = rr["sub_duration_s"]
        sa = NEW[rr["scene_id"]] if rr["scene_id"] in replace_scenes else amap.get(
            rr["scene_id"], {})
        new = [{"scene_id": "{}.{}".format(rr["scene_id"], j + 1),
                "start_s": round(rr["window"][0] + d * j, 3),
                "end_s": round(rr["window"][0] + d * (j + 1), 3),
                "selected_asset": sa} for j in range(rr["sub_count"])]
        i = entries.index(base)
        entries[i:i + 1] = new
    return entries


proj_new, proj_old = build(True), build(False)
tl21_new = [dict(e, selected_asset=NEW.get(e["scene_id"], OLD.get(e["scene_id"], {})))
            for e in TL]
tl21_old = [dict(e, selected_asset=OLD.get(e["scene_id"], {})) for e in TL]
film_new = R / H5R["output"]["path"]
film_old = R / E45["stages"][1]["output"]["path"]
t0 = time.time()
fb_new_raw, err_new = core_direction.measure_freeze(film_new, FF,
                                                    H5R["output"]["format_duration_s"])
fb_old_raw, err_old = core_direction.measure_freeze(film_old, FF,
                                                    E45["stages"][1]["output"]["format_duration_s"])
fb_new = core_direction.close_open_blocks(fb_new_raw, H5R["output"]["format_duration_s"])
fb_old = core_direction.close_open_blocks(fb_old_raw, E45["stages"][1]["output"]["format_duration_s"])
print("freezedetect 用时 {:.0f}s | 冻结块 new={} old={}".format(
    time.time() - t0, len(fb_new), len(fb_old)))
dq = {
    "after_H5": {"DQ-2": core_direction.asset_reuse(proj_new),
                 "DQ-3": core_direction.static_hold(proj_new, freeze_blocks=fb_new),
                 "DQ-4": core_direction.visual_density(proj_new, freeze_blocks=fb_new),
                 "DQ-5": core_direction.climax_coverage(script.get("segments") or [], tl21_new),
                 "DQ-8": core_direction.narration_visual_support(script.get("segments") or [],
                                                                 tl21_new)},
    "before_H5": {"DQ-2": core_direction.asset_reuse(proj_old),
                  "DQ-3": core_direction.static_hold(proj_old, freeze_blocks=fb_old),
                  "DQ-4": core_direction.visual_density(proj_old, freeze_blocks=fb_old),
                  "DQ-5": core_direction.climax_coverage(script.get("segments") or [], tl21_old),
                  "DQ-8": core_direction.narration_visual_support(script.get("segments") or [],
                                                                  tl21_old)},
}
uniq = sorted({(e.get("selected_asset") or {}).get("asset_id") or "SOLID_COLOR"
               for e in proj_new})
use = {a: len([e for e in proj_new
               if ((e.get("selected_asset") or {}).get("asset_id") or "SOLID_COLOR") == a])
       for a in uniq}
hold_over = [{"scene_id": e["scene_id"], "hold_s": round(e["end_s"] - e["start_s"], 3)}
             for e in proj_new if (e["end_s"] - e["start_s"]) > 25.0]
out = {"schema": "phase6g-h5-dq-recompute-v2", "stage": "6-G / H5（DQ 完整复算，只读）",
       "measured_on": {"output_path": H5R["output"]["path"],
                       "output_sha256": H5R["output"]["sha256"],
                       "duration_s": H5R["output"]["format_duration_s"],
                       "audio_md5": H5R["output"]["audio_md5"]},
       "projection_fix": {
           "entries": {"H5 脚本内（错误）": H5R["DQ"]["projection_entries"],
                       "修正后": len(proj_new)},
           "fix_1": "补应用 H3c-1/H3c-2 切分（34 → 48 条目，与既有 6-G 口径一致）",
           "fix_2": "替换写入 S05 与 **S11 的全部子镜**（执行器替换的是整段窗口）",
           "impact": "H5 执行脚本内的 DQ-2(5)/DQ-3(FAIL)/DQ-5 数值**均为投影缺陷所致**，"
                     "以本文件为准（该错误仅影响报告读数，未写入台账：台账不含 DQ 字段）"},
       "DQ": dq, "unique_assets": uniq, "unique_count": len(uniq), "scene_use_counts": use,
       "holds_over_25s": hold_over,
       "freeze_blocks": {"after_H5": fb_new, "before_H5": fb_old},
       "state_changes": {k: "{} → {}".format(dq["before_H5"][k]["state"],
                                             dq["after_H5"][k]["state"])
                         for k in ("DQ-2", "DQ-3", "DQ-4", "DQ-5", "DQ-8")},
       "attribution": {
           "DQ-2": "4 → 6 唯一素材（新增两件真实素材；四件原素材仍在用）⇒ FAIL → PASS",
           "DQ-3": "继续 PASS（逐镜子镜保持 ≤24.195s，无 >25s 场景；成片冻结块分量本轮已一并评估）",
           "DQ-4": "继续 PASS",
           "DQ-5": "**非 H5 引入**：核心镜保持时长基于**脚本对齐的 21 场景视图**（父窗口本就"
                   "长达 30–58s），H5 前后同判 FAIL ⇒ 属既有口径问题，本轮如实标注，未据以放宽",
           "DQ-8": "**非 H5 引入**：缺既有只读多模态证据 ⇒ NOT_ASSESSABLE（≠ PASS）"},
       "no_dq_closure_claim": "只报实测；DQ-1/DQ-6/DQ-7 未评估",
       }
out["recompute_sha256"] = hashlib.sha256(json.dumps(
    out, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode()).hexdigest()
OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print("== DQ 状态变化 ==")
for k, v in out["state_changes"].items():
    print("  {}: {}".format(k, v))
for tag in ("before_H5", "after_H5"):
    d = dq[tag]
    print("  [{}] DQ-2 {} unique {} | DQ-3 {} max_hold {} freeze_blocks {} | DQ-4 {} {}/min "
          "| DQ-5 {} | DQ-8 {}".format(
              tag, d["DQ-2"]["state"], d["DQ-2"].get("unique_assets"), d["DQ-3"]["state"],
              d["DQ-3"].get("max_hold_s"), d["DQ-3"].get("freeze_blocks"),
              d["DQ-4"]["state"], d["DQ-4"].get("scene_changes_per_min"), d["DQ-5"]["state"],
              d["DQ-8"]["state"]))
print("unique:", len(uniq), json.dumps(use, ensure_ascii=False))
print(">25s 场景:", hold_over)
print("recompute ->", OUT)
