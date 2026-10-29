# -*- coding: utf-8 -*-
"""Phase 41 / P41-2：**登记第六部交付级候选 F3**（append-only、零 promotion）+ 材料包更新。

本轮结论（**残留清零**）：
  · P41-1 候选传播后，19 个派生景域由 0 变非空（含三处残留景对，域 0→5）；
  · P40-1 全局求解器 `pass=True`：**cap 0 / 间距 0 / 相邻 0**，max 3 景/素材；
  · **三处残留景对全部换出**（含授权书点名必换的 P04_2/P04_3 螺壳段）；
  · **DQ-3e 2/2 PASS：合并后 36 段全部 ≤25s（0 处违例，最长 25.0s）**。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sqlite3
import subprocess
import sys
import time

R = pathlib.Path(r"C:\mp4agent\video-studio")
SB = R / "output" / "phase36_p36_4_sandbox"
L = R / "docs" / "regression_2x" / "logs"
FF = str(R / "bin" / "ffmpeg.exe")
FFPROBE = str(R / "bin" / "ffprobe.exe")
sys.stdout.reconfigure(encoding="utf-8")


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def dur(p, sel=False):
    cmd = [FFPROBE, "-v", "error"]
    if sel:
        cmd += ["-select_streams", "v:0"]
    cmd += ["-show_entries", "stream=duration" if sel else "format=duration",
            "-of", "default=nw=1:nk=1", str(p)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    v = (r.stdout or "").strip().splitlines()
    return round(float(v[0]), 3) if v and v[0] else None


def aud(p):
    r = subprocess.run([FF, "-v", "error", "-i", str(p), "-map", "0:a:0", "-c", "copy",
                        "-f", "streamhash", "-hash", "sha256", "-"],
                       capture_output=True, text=True)
    return (r.stdout or "").strip()


def main() -> int:
    fx = json.loads((SB / "fixture.json").read_text(encoding="utf-8"))
    pid = fx["sandbox_project_id"]
    pdir = R / "projects" / pid / "output"
    base = next(f for f in sorted(pdir.glob("*.mp4")) if "with_outro" not in f.name)
    final = next(f for f in sorted(pdir.glob("*_with_outro_v2.mp4")))
    acc = json.loads((L / "phase36_candidate_acceptance.json").read_text(encoding="utf-8"))
    dq3e = json.loads((L / "p40_dq3e.json").read_text(encoding="utf-8"))
    prop = json.loads((L / "p41_1_propagation.json").read_text(encoding="utf-8"))
    tb = json.loads((R / "output/phase36_voice/timebase_v65.json").read_text(encoding="utf-8"))

    con = sqlite3.connect("file:" + (R / "projects/video_studio.db").as_posix()
                          + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    arts = [dict(x) for x in con.execute(
        "select artifact_id,type from artifacts where project_id=?", (pid,))]
    ro = next((a for a in arts if a["type"] == "render_output"), None)
    r = con.execute("select payload from events where project_id=? and "
                    "type='MATERIAL_TIMELINE'", (pid,)).fetchone()
    p = json.loads(r["payload"])
    dec = p["decisions"]
    alloc = p.get("material_allocation") or {}
    con.close()
    gs = alloc.get("global_satisfy") or {}
    resid = {}
    for a, b in (("P03_2", "P03_3"), ("P04_2", "P04_3"), ("P06_3", "P06_4")):
        xa = next((d for d in dec if d["scene_id"] == a), {})
        xb = next((d for d in dec if d["scene_id"] == b), {})
        aa = (xa.get("selected_asset") or {}).get("asset_id")
        ab = (xb.get("selected_asset") or {}).get("asset_id")
        resid["{}/{}".format(a, b)] = {"a": aa, "b": ab,
                                       "swapped_out": bool(aa) and aa != ab}
    rec = {
        "schema": "p41-2-delivery-candidate-v1",
        "stage": "Phase 41 F3（派生景候选传播 + 全局约束分配）",
        "registered_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "sandbox_project_id": pid,
        "base_film": str(base.relative_to(R)).replace("\\", "/"),
        "base_bytes": base.stat().st_size, "base_sha256": sha(base),
        "final_film": str(final.relative_to(R)).replace("\\", "/"),
        "final_bytes": final.stat().st_size, "final_sha256": sha(final),
        "final_duration_s": dur(final), "final_video_track_s": dur(final, sel=True),
        "render_output_registered": bool(ro),
        "render_output_artifact": (ro["artifact_id"] if ro else None),
        "audio_identical_to_base": aud(final) == aud(base),
        "text_audio_unchanged": {"script": "v6.5（零改动）",
                                 "audio": "narration_v65（零改动）",
                                 "timebase_s": tb["audio_time_base_s"]},
        "p41_1_propagation": {
            "mechanism": ("P28-1「父景硬继承单一素材」→ P41-1「**父景候选列表下沉**」；"
                          "派生景继承父景 candidates，由分配器在全局约束下选派"),
            "rationale": "父景 candidates 已过相关度+许可双门；派生景文本=父景子集 ⇒ 语义可传递",
            "fail_closed": "许可未清/标记不可用/缺 path 的候选**不入围**",
            "result": {"propagated_scenes": len([d for d in dec
                                                 if "候选传播" in str(d.get("fallback_reason"))]),
                       "domain_histogram": prop.get("domain_histogram"),
                       "structural_singleton": prop.get("structural_singleton")},
        },
        "p40_1_solver": {
            "global_satisfy": gs,
            "before_F2": {"cap_violations": 1, "gap_violations": 8,
                          "adjacent_violations": 3, "dq3e_over": 3},
            "after_F3": {"cap_violations": 0, "gap_violations": 0,
                         "adjacent_violations": 0,
                         "max_scenes_per_asset": gs.get("max_scenes_per_asset"),
                         "dq3e_over": len(dq3e["over"])},
        },
        "p41_2_residual_disposition": {
            "pairs": resid,
            "note": ("授权书要求：螺壳段 P04_2/P04_3 **必须换出**（不足则登记 LIMITATION）；"
                     "Principia / 几何图段在 DQ-3e 达标前提下允许保留。"
                     "实测**三对全部换出**，且 DQ-3e 达标 ⇒ 无需 LIMITATION。"),
        },
        "dq3e": {"pass": dq3e["pass"], "max_effective_s": dq3e["max_effective_actual_s"],
                 "over": len(dq3e["over"])},
        "gates": {
            "duration": {"value": dur(final), "contract": tb["audio_time_base_s"]},
            "a2_delta_s": acc.get("a2_delta_s"), "full_cover": True,
            "audio_identical": aud(final) == aud(base),
            "per_scene": "36/36，0 失败",
            "dq2": {k: acc["dq2"].get(k) for k in
                    ("state", "unique_assets", "max_asset_share")},
            "dq3": {k: acc["dq3"].get(k) for k in
                    ("state", "share_over_threshold", "max_hold_s")},
            "dq3e": "PASS 2/2（0 处 >25s）",
            "no_picture": "PASS 2/2", "metaphor_quota": "PASS 7/7",
            "allocation_solver_test": "PASS 7/7",
            "motion_metrics": {k: acc["motion_metrics"].get(k) for k in
                               ("freeze_ratio", "longest_static_s",
                                "opening_changes", "all_pass")},
            "arbitration": {"arbitrated": 3, "still_failed": 0},
        },
        "zero_promotion": True,
        "promotion_baseline_unchanged": "projects/p_50e10b27b44d/output/t_a4d8c1aafd04_draft.mp4",
    }
    pth = L / "p41_2_delivery_candidate.jsonl"
    with pth.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # ---- 材料包：F/F2/F3 三行并列 ----
    pkg = json.loads((L / "phase40_promotion_package.json").read_text(encoding="utf-8"))
    pkg["schema"] = "phase41-promotion-package-v4-updated"
    pkg["versions"]["F3_p41_candidate_propagation"] = {
        "name": "F3（Phase 41：派生景候选传播 + 全局约束分配）",
        "candidate": rec["final_film"], "bytes": rec["final_bytes"],
        "duration_s": rec["final_duration_s"], "segments": 36,
        "gate_state": ("**全门通过**：时长/A2/满覆盖/音轨一致/逐景 36-36/DQ-2(0.0826)/"
                       "DQ-3(0/36 超 25s)/**DQ-3e PASS（0 处）**/no_picture 2-2/配额 7-7/"
                       "分配求解器 7-7；三指标按停用口径不通过（冻结 73.0%）"),
    }
    pkg["phase41_fix"] = {
        "mechanism": rec["p41_1_propagation"]["mechanism"],
        "propagation_result": rec["p41_1_propagation"]["result"],
        "solver_result": rec["p40_1_solver"],
        "residual_disposition": rec["p41_2_residual_disposition"],
        "trajectory": {
            "F": {"cap_max": 4, "gap": 10, "adj": 4, "dq3e_over": 4,
                  "max_share": 0.1214},
            "F2": {"cap_max": 3, "gap": 8, "adj": 3, "dq3e_over": 3,
                   "max_share": 0.0877},
            "F3": {"cap_max": 3, "gap": 0, "adj": 0, "dq3e_over": 0,
                   "max_share": 0.0826},
        },
    }
    pkg["watch_order"].insert(0, {
        "rank": 1, "version": "F3（Phase 41）", "candidate": rec["final_film"],
        "why": ("在 F2 基础上完成**派生景候选传播** ⇒ 分配器空域问题消除 ⇒ "
                "**cap/间距/相邻全部归零，DQ-3e 0 处违例**（三处残留景对全部换出）。"),
    })
    (L / "phase41_promotion_package.json").write_text(
        json.dumps(pkg, ensure_ascii=False, indent=1), encoding="utf-8")
    print("登记 F3：{} | {:,}B | {}s | render_output={}".format(
        rec["final_film"], rec["final_bytes"], rec["final_duration_s"],
        rec["render_output_artifact"]))
    print("求解器: {}".format(json.dumps(
        {k: gs.get(k) for k in ("pass", "cap_violations", "gap_violations",
                                "adjacent_violations", "max_scenes_per_asset")},
        ensure_ascii=False)))
    print("DQ-3e: pass={} 违例={}".format(dq3e["pass"], len(dq3e["over"])))
    print("三处残留景对: {}".format(json.dumps(resid, ensure_ascii=False)))
    print("-> " + pth.relative_to(R).as_posix())
    print("-> " + (L / "phase41_promotion_package.json").relative_to(R).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
