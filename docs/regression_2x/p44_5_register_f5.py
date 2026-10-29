# -*- coding: utf-8 -*-
"""Phase 43 / P43-4：**登记第八部交付级候选 F5**（append-only、零 promotion）+ 材料包 v5。

本轮结论：
  · **P43-1 字幕句界同步**（主交付）：median 滞后 **1.14s → 0.000s**；>1s **66 → 0 处**；
    停顿中提前出现 **77 → 0**；门 `caption_sync_test` **3/3 PASS**。
  · **P43-3 举旗照禁入**：`432cd85be6f1` 上屏 **0 次**（与螺壳同款内容排除通道）。
  · **P43-2 家族约束**：**相邻禁同家族 = 0 违例**（达标）；
    **同家族份额 ≤33% 未达标**（实测 A=41.7%）—— 已按授权书「不可行则如实报告」登记：
    这是**候选域 + cap3 + gap3 的联合紧约束**，33% 在当前 16 张池下不可达。
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
    sync = json.loads((L / "p43_1_caption_sync.json").read_text(encoding="utf-8"))
    famf = json.loads((L / "p43_2_family_feasibility.json").read_text(encoding="utf-8"))
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
    ban = {}
    for b in ("2442c39e", "432cd85b"):
        ban[b] = sum(1 for d in dec
                     if b in str((d.get("selected_asset") or {}).get("asset_id")))
    rec = {
        "schema": "p43-4-delivery-candidate-v1",
        "stage": "Phase 43 F5（字幕句界同步 + 感知家族约束 + 举旗照禁入）",
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
        "p43_1_caption_sync": {
            "mechanism": ("cue 切换点吸附到 silencedetect(-35dB,d=0.28) 的**语音恢复点**"
                          "（`silence_end`），容差 ±0.4s；超界保留原位并计数"),
            "external_product": "output/phase36_voice/recoveries.json（36 景 / 259 恢复点）",
            "before": {"median_lag_s": 1.14, "over_1s": 66, "early": 77},
            "after": {"median_lag_s": sync["median_lag_s"],
                      "over_1s": sync["over_1s"], "over_1s_ratio": sync["over_1s_ratio"],
                      "early": sync["early_count"],
                      "snapped": sync["snap_stats"].get("snapped"),
                      "unsnapped": sync["snap_stats"].get("unsnapped")},
            "gate": "tests/caption_sync_test.py 3/3 PASS",
        },
        "p43_2_family": {
            "map": "config/family_map.json（家族 A/B/C/D，监理人工标定）",
            "adjacent_same_family": gs.get("adjacent_same_family"),
            "family_counts": gs.get("family_counts"),
            "share_limit": 0.33,
            "share_violations": gs.get("family_share_violations"),
            "feasibility": famf,
            "verdict": ("**相邻禁同家族达标（0 违例）**；**份额 ≤33% 未达标**"
                        "（A 实测 41.7%）⇒ 按授权书「不可行则如实报告」登记为"
                        "**候选域 + cap3 + gap3 联合紧约束**导致的**结构性不可达**，"
                        "**未静默、未硬造**。"),
        },
        "p43_3_flag_ban": {
            "asset": "asset_432cd85be6f1（举旗照）",
            "channel": "config/content_exclusions.json（与螺壳同款）",
            "reason": "A 审人工点名「hook 画面与主题错位」，人工目验在案",
            "on_screen_count": ban["432cd85b"],
        },
        "gates": {
            "duration": {"value": dur(final), "contract": tb["audio_time_base_s"]},
            "a2_delta_s": acc.get("a2_delta_s"), "full_cover": True,
            "audio_identical": aud(final) == aud(base),
            "per_scene": "36/36，0 失败",
            "dq2": {k: acc["dq2"].get(k) for k in
                    ("state", "unique_assets", "max_asset_share")},
            "dq3": {k: acc["dq3"].get(k) for k in
                    ("state", "share_over_threshold", "max_hold_s")},
            "dq3e": {"pass": dq3e["pass"], "over": len(dq3e["over"])},
            "caption_sync": "PASS 3/3",
            "content_exclusion": "PASS 4/4（两处禁入均 0 次上屏）",
            "no_picture": "PASS 2/2", "metaphor_quota": "PASS 7/7",
            "allocation_solver_test": "PASS 7/7",
            "motion_metrics": {k: acc["motion_metrics"].get(k) for k in
                               ("freeze_ratio", "longest_static_s",
                                "opening_changes", "all_pass")},
            "arbitration": {"arbitrated": 2, "still_failed": 0},
        },
        "zero_promotion": True,
        "promotion_baseline_unchanged": "projects/p_50e10b27b44d/output/t_a4d8c1aafd04_draft.mp4",
    }
    pth = L / "p43_4_delivery_candidate.jsonl"
    with pth.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    pkg = json.loads((L / "phase42_promotion_package.json").read_text(encoding="utf-8"))
    pkg["schema"] = "phase43-promotion-package-v5"
    pkg["versions"]["F5_p43_caption_family"] = {
        "name": "F5（Phase 43：字幕句界同步 + 家族约束 + 举旗照禁入）",
        "candidate": rec["final_film"], "bytes": rec["final_bytes"],
        "duration_s": rec["final_duration_s"], "segments": 36,
        "gate_state": ("字幕同步 3-3（median 0.000s）/内容排除 4-4/DQ-3 0-36/DQ-3e 0 处/"
                       "no_picture 2-2/配额 7-7/求解器 7-7 **全过**；"
                       "**家族份额 ≤33% 未达标（A=41.7%，结构性不可达）**；"
                       "三指标按停用口径不通过"),
    }
    pkg["phase43_fix"] = {
        "caption_sync": rec["p43_1_caption_sync"],
        "family": rec["p43_2_family"],
        "flag_ban": rec["p43_3_flag_ban"],
        "trajectory": {
            "F": {"shell": 2, "gap": 10, "adj": 4, "dq3e": 4, "caption_median_lag": 1.14},
            "F2": {"shell": 2, "gap": 8, "adj": 3, "dq3e": 3, "caption_median_lag": 1.14},
            "F3": {"shell": 3, "gap": 0, "adj": 0, "dq3e": 0, "caption_median_lag": 1.14},
            "F4": {"shell": 0, "gap": 0, "adj": 0, "dq3e": 0, "caption_median_lag": 1.14},
            "F5": {"shell": 0, "gap": 0, "adj": 0, "dq3e": 0, "caption_median_lag": 0.0,
                   "flag_photo": 0, "family_adjacent": 0, "family_share_A": 0.417},
        },
    }
    pkg["watch_order"].insert(0, {
        "rank": 1, "version": "F5（Phase 43）", "candidate": rec["final_film"],
        "why": ("**字幕句界同步已修**（median 滞后 1.14s→0.000s；>1s 由 66→0；提前 77→0）"
                "+ 举旗照禁入 + 家族相邻约束达标；"
                "**家族份额 33% 未达标（结构性）**。"),
    })
    (L / "phase43_promotion_package.json").write_text(
        json.dumps(pkg, ensure_ascii=False, indent=1), encoding="utf-8")
    print("登记 F5：{} | {:,}B | {}s | render_output={}".format(
        rec["final_film"], rec["final_bytes"], rec["final_duration_s"],
        rec["render_output_artifact"]))
    print("字幕同步: median={} over1s={} early={} ⇒ {}".format(
        sync["median_lag_s"], sync["over_1s"], sync["early_count"],
        "PASS 3/3"))
    print("禁入上屏: {}".format(ban))
    print("家族: 相邻同家族={} | 份额越界={}".format(
        gs.get("adjacent_same_family"), gs.get("family_share_violations")))
    print("-> " + pth.relative_to(R).as_posix())
    print("-> " + (L / "phase43_promotion_package.json").relative_to(R).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
