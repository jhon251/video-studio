# -*- coding: utf-8 -*-
"""P13E-3 ② 全门复验 + DQ 双口径 + 逐景 MOTION_VERIFIED 证据。

用法：
  python p13e3_verify.py --project p_xxx

只读成片（不修改候选）；写出 logs/phase13e_p13e3_render.json。
口径全部取自生产代码：frame_corr/gray48（48×48 灰度 Pearson，min_corr=0.30）、
integrity.*（PI-1/2/3/4/5/6）、narration.*（时长契约 v2 / 字幕对齐）、
direction.*（DQ-1…DQ-7 只读复核 + DQ-3 freezedetect）。
**不宣称 PASS**：只列实测值与各口径判定，供人工裁定。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.core import direction as DIR                                        # noqa: E402
from video_studio.core import integrity as IG                                         # noqa: E402
from video_studio.core import materials as MAT                                        # noqa: E402
from video_studio.core import narration as NAR                                        # noqa: E402
from video_studio.core.materials import frame_corr, gray48                            # noqa: E402

FFMPEG = str(R / "bin" / "ffmpeg.exe")
FFPROBE = str(R / "bin" / "ffprobe.exe")
LOGS = R / "docs" / "regression_2x" / "logs"
OUT = LOGS / "phase13e_p13e3_render.json"
CORR_MIN = 0.30                     # materials.DEFAULT_POLICY["frame_match_min_corr"]
DUR_TARGET = 978.7
DUR_TOL = 1.0
FPS = 25


def sh(cmd, timeout=3600):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def probe_dur(p):
    rc, out = sh([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                  "-of", "default=nw=1:nk=1", str(p)], timeout=300)
    try:
        return float(out.strip().splitlines()[0])
    except Exception:                                                       # noqa: BLE001
        return None


def extract(p, t, dst):
    rc, _ = sh([FFMPEG, "-v", "error", "-y", "-ss", "{:.3f}".format(max(t, 0.0)),
                "-i", str(p), "-frames:v", "1", str(dst)], timeout=600)
    return rc == 0 and dst.is_file()


def gray_n(p, size=(480, 270)):
    import numpy as np
    from PIL import Image
    with Image.open(p) as im:
        return np.asarray(im.convert("L").resize(size), dtype=np.float64)


def gray_diff(p1, p2, size=(480, 270)):
    import numpy as np
    a, b = gray_n(p1, size), gray_n(p2, size)
    return round(float(np.abs(a - b).mean()), 4)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    args = ap.parse_args()
    pid = args.project

    import sqlite3
    con = sqlite3.connect("file:" + (R / "projects" / "video_studio.db").as_posix() + "?mode=ro",
                          uri=True)
    con.row_factory = sqlite3.Row
    proj = R / "projects" / pid

    # ---------- 1. 渲染产物 ----------
    rtask = None
    for t in con.execute("select * from tasks where project_id=? and agent_role='editing' "
                         "order by created_at", (pid,)):
        rtask = dict(t)
    arts = [dict(r) for r in con.execute(
        "select * from artifacts where project_id=? order by created_at", (pid,))]
    ro = [a for a in arts if a["type"] == "render_output"]
    script_seg_cache = {}
    for a in arts:
        if a["type"] == "script_output":
            script_seg_cache = json.loads(pathlib.Path(a["path"]).read_text(encoding="utf-8"))
    report = {
        "schema": "phase13e-p13e3-render-v1",
        "stage": "Phase 13-E P13E-3 ② 全片运动候选渲染（v2 时基）",
        "sandbox_project_id": pid,
        "render_task": {"task_id": (rtask or {}).get("task_id"),
                        "status": (rtask or {}).get("status"),
                        "error": (rtask or {}).get("error")},
        "render_output_artifact": (ro[0]["artifact_id"] if ro else None),
        "disclaimer": ("本报告只登记**实测值**与各冻结口径的判定；"
                       "**不宣称 PASS**（交付裁定权属人类）。"),
    }

    if not ro:
        # 渲染后核验硬门失败 ⇒ fail-closed：不写 render_output（成片仍在 output/ 供人工审查）
        report["verdict"] = "NO_RENDER_OUTPUT_GATE_BLOCKED"
        report["blocked_error"] = str((rtask or {}).get("error"))[:2000]
        draft = sorted((proj / "output").glob("*.mp4"), key=lambda x: -x.stat().st_size)
        if not draft:
            OUT.write_text(json.dumps(report, ensure_ascii=False, indent=1, sort_keys=True),
                           encoding="utf-8")
            print("无 render_output 产物，也无 draft mp4；任务状态:",
                  (rtask or {}).get("status"), (rtask or {}).get("error"))
            con.close()
            return 2
        timeline = []
        for e in con.execute("select payload from events where project_id=? "
                             "and type='MATERIAL_TIMELINE'", (pid,)):
            j = json.loads(e["payload"])
            for d in j.get("decisions") or []:
                timeline.append({"scene_id": d.get("scene_id"),
                                 "selected_asset": d.get("selected_asset"),
                                 "fallback_state": d.get("fallback_state"),
                                 "insufficiency_class": d.get("insufficiency_class")})
        # 窗口从派生脚本重建（与 _build_material_timeline 同公式：v2 用音频窗口）
        sec = 0.0
        for i, tg in enumerate(timeline):
            seg = None
            for s in (script_seg_cache.get("segments") or []):
                if s.get("scene_id") == tg["scene_id"]:
                    seg = s
                    break
            dur = float(seg.get("duration_s") or 0) if seg else 0.0
            tg["start_s"] = round(sec, 3)
            tg["end_s"] = round(sec + max(dur, 3.0), 3)
            sec = tg["end_s"]
        report["timeline_source"] = "events.MATERIAL_TIMELINE + derived script windows"
        film = draft[0]
        report["film"] = {"path": str(film.relative_to(R)).replace("\\", "/"),
                          "bytes": film.stat().st_size, "is_draft": True}
        # 跳到公共流程（跳过 data 解析）
        data = {"material_timeline": timeline}
    else:
        data = json.loads(pathlib.Path(ro[0]["path"]).read_text(encoding="utf-8"))
        timeline = data.get("material_timeline") or data.get("timeline") or []
        film_rel = data.get("output") or data.get("film") or data.get("output_path")
        report["render_output_keys"] = sorted(data.keys())
        report["film_path_field"] = film_rel
        cands = []
        if film_rel:
            p = pathlib.Path(str(film_rel))
            cands.append(p if p.is_absolute() else (proj / p))
        cands += sorted((proj / "output").glob("*.mp4"), key=lambda x: -x.stat().st_size)
        film = next((c for c in cands if c.is_file()), None)
        if film is None:
            report["verdict"] = "NO_FILM_FILE"
            OUT.write_text(json.dumps(report, ensure_ascii=False, indent=1, sort_keys=True),
                           encoding="utf-8")
            print("找不到成片 mp4")
            con.close()
            return 2
        report["film"] = {"path": str(film.relative_to(R)).replace("\\", "/"),
                          "bytes": film.stat().st_size}

    # ---------- 2. 时长契约（978.7±1s）----------
    dur = probe_dur(film)
    tl_total = (data.get("timeline_total_s") or data.get("audio_time_base_s")
                or data.get("total_s"))
    report["duration_contract"] = {
        "measured_s": dur,
        "target_s": DUR_TARGET, "tolerance_s": DUR_TOL,
        "delta_s": (round(dur - DUR_TARGET, 3) if dur else None),
        "within_978_7_pm_1": (bool(dur and abs(dur - DUR_TARGET) <= DUR_TOL)),
        "render_path_timeline_total_s": tl_total,
        "authoritative_film_s": 978.7,
    }

    # ---------- 3. PI 全门（渲染后：PI-3/4/5）----------
    # 渲染后门禁在成片产出后调用、不入库 ⇒ 用同一生产函数复算（口径一致、可复算）
    v2_voice = None
    for a in arts:
        if a["type"] == "voice_output":
            v2_voice = json.loads(pathlib.Path(a["path"]).read_text(encoding="utf-8"))
    script_art = None
    for a in arts:
        if a["type"] == "script_output":
            script_art = json.loads(pathlib.Path(a["path"]).read_text(encoding="utf-8"))
    cfg = json.loads((R / "config" / "config.json").read_text(encoding="utf-8"))
    plan = NAR.narration_plan(script_art, v2_voice, config=cfg)
    cues = []
    from video_studio.core import captions as CAP
    from video_studio.core.strip import strip_claims as _sc
    cues = CAP.build_cues(
        [{"narration": _sc(s.get("narration", "")), "duration_s": s.get("duration_s")}
         for s in (script_art.get("segments") or []) if _sc(s.get("narration", "")).strip()],
        windows=(plan["segments"] or None))

    tl_for_gate = plan["audio_time_base_s"]
    pre = IG.pre_render_gate(script_art.get("segments") or [], v2_voice, tl_for_gate,
                             IG.gate_policy(cfg),
                             narration_duration_s=float(v2_voice.get("narration_duration_s")),
                             narration_plan=plan, cues=cues)
    post = IG.post_render_gate(film, tl_for_gate, cues,
                               narration_end_s=(plan["segments"][-1]["end_s"]
                                                if plan.get("segments") else None),
                               narration_expected=True, ffmpeg=FFMPEG, ffprobe=FFPROBE,
                               policy=IG.gate_policy(cfg), narration_plan=plan)
    report["pi_gates"] = {
        "basis_timeline_s": tl_for_gate,
        "pre_render": {"blocked": pre["blocked"],
                       "states": {k: (v or {}).get("state") for k, v in pre["metrics"].items()},
                       "reasons": pre["reasons"]},
        "post_render": {"blocked": post["blocked"],
                        "promote_blocked": post.get("promote_blocked"),
                        "states": {k: (v or {}).get("state") for k, v in post["metrics"].items()},
                        "reasons": post["reasons"],
                        "metrics": post["metrics"]},
    }

    # ---------- 4. 响度契约（-16 LUFS ±1 / TP ≤ -1.5 dBTP）----------
    from video_studio.core import audio as AUD
    contract = AUD.contract_from_config(cfg)
    measured = AUD.measure_loudness(film, exe=FFMPEG) if hasattr(AUD, "measure_loudness") else None
    report["loudness"] = {
        "contract": contract,
        "render_reported": {k: data.get(k) for k in
                            ("audio_loudness", "loudness", "loud_film") if k in data},
        "independent_measure": measured,
    }

    # ---------- 5. 字幕 ↔ 旁白对齐 ----------
    sa = NAR.subtitle_alignment(cues, plan, IG.gate_policy(cfg))
    orphan = IG.subtitle_orphans(cues, plan["segments"][-1]["end_s"] if plan.get("segments")
                                 else None, tl_for_gate, IG.gate_policy(cfg))
    report["subtitle_alignment"] = {"v2_alignment": sa, "orphans": orphan,
                                   "cue_count": len(cues)}

    # ---------- 6. DQ 只读复核（原口径）+ DQ-3 freezedetect ----------
    freeze_blocks, _ferr = DIR.measure_freeze(film, FFMPEG, duration_s=dur)
    dq = {}
    try:
        dq["DQ-3_static_hold"] = DIR.static_hold(timeline, freeze_blocks)
    except Exception as exc:                                                # noqa: BLE001
        dq["DQ-3_static_hold"] = {"error": "{}: {}".format(type(exc).__name__, exc)}
    try:
        dq["DQ-2_asset_reuse"] = DIR.asset_reuse(timeline)
    except Exception as exc:                                                # noqa: BLE001
        dq["DQ-2_asset_reuse"] = {"error": "{}: {}".format(type(exc).__name__, exc)}
    report["dq_readonly"] = dq
    report["dq3_freezedetect"] = {
        "blocks": len(freeze_blocks),
        "block_list": freeze_blocks[:40],
        "params": {"scale_filter": "scale=320:-2", "noise_db": -60.0, "min_dur_s": 1.0},
        "semantics_note": ("DQ-3 freezedetect 语义（原口径）与**运动层**语义并列："
                           "crop 平移/缩放使画面像素持续变化 ⇒ freezedetect 冻结块应显著减少；"
                           "**不平移/不缩放**的静止场景仍被计入冻结属预期，**不据此宣称 PASS**。"),
    }

    # ---------- 7. 逐景 MOTION_VERIFIED（10%/90% 抽帧 + corr）----------
    ev = {e["scene_id"]: e for e in (data.get("motion_evidence") or [])}
    mj = {}
    me_path = proj / "render" / "motion_evidence.json"
    if me_path.is_file():
        mj = json.loads(me_path.read_text(encoding="utf-8"))
    applied = {e["scene_id"]: e for e in (mj.get("applied") or [])}
    scenes = []
    work = proj / "render" / "verify_frames"
    work.mkdir(parents=True, exist_ok=True)
    for s in timeline:
        sid = s.get("scene_id")
        a = s.get("selected_asset") or {}
        st, en = float(s.get("start_s") or 0), float(s.get("end_s") or 0)
        d = max(en - st, 0.5)
        f10 = work / "{}_10.png".format(sid)
        f90 = work / "{}_90.png".format(sid)
        ok10 = extract(film, st + 0.10 * d, f10)
        ok90 = extract(film, st + 0.90 * d, f90)
        row = {"scene_id": sid, "window_s": [st, en], "duration_s": round(d, 3),
               "asset_id": a.get("asset_id"), "asset_name": a.get("name"),
               "motion_enabled": sid in applied,
               "motion_type": (applied.get(sid) or {}).get("motion_type")}
        if ok10 and ok90:
            row["frame_diff_10_vs_90"] = gray_diff(f10, f90)
        else:
            row["frame_diff_10_vs_90"] = None
        if ok90 and a.get("path") and pathlib.Path(a["path"]).is_file():
            try:
                row["corr_asset_vs_frame90"] = round(
                    float(frame_corr(gray48(a["path"]), gray48(f90))), 4)
            except Exception as exc:                                        # noqa: BLE001
                row["corr_asset_vs_frame90"] = "ERR:{}".format(type(exc).__name__)
        else:
            row["corr_asset_vs_frame90"] = None
        c = row["corr_asset_vs_frame90"]
        row["corr_ge_0_30"] = (isinstance(c, float) and c >= CORR_MIN)
        # MOTION_VERIFIED：启用运动 ⇒ 像素差需显著；静止 ⇒ 期望很小
        if row["motion_enabled"]:
            row["motion_verified"] = bool(row["frame_diff_10_vs_90"] is not None
                                          and row["frame_diff_10_vs_90"] > 0.5)
        else:
            row["motion_verified"] = "N/A_STATIC"
        scenes.append(row)
    static_diffs = [r["frame_diff_10_vs_90"] for r in scenes
                    if not r["motion_enabled"] and r["frame_diff_10_vs_90"] is not None]
    report["motion_verification"] = {
        "plan_counts": mj.get("plan_counts"),
        "enabled_scenes": sorted(applied.keys()),
        "fallback": mj.get("fallback"),
        "scenes": scenes,
        "threshold": {"corr_min": CORR_MIN, "frame_diff_min_for_motion": 0.5,
                      "diff_metric": "480×270 灰度平均绝对差"},
        "summary": {
            "motion_enabled_count": sum(1 for r in scenes if r["motion_enabled"]),
            "motion_verified_count": sum(1 for r in scenes if r["motion_verified"] is True),
            "corr_ge_0_30_count": sum(1 for r in scenes if r["corr_ge_0_30"]),
            "corr_failed_scenes": [r["scene_id"] for r in scenes
                                   if r["corr_asset_vs_frame90"] is not None
                                   and not r["corr_ge_0_30"]],
            "corr_narrow_margin_scenes": [
                {"scene_id": r["scene_id"], "corr": r["corr_asset_vs_frame90"]}
                for r in scenes if isinstance(r["corr_asset_vs_frame90"], float)
                and CORR_MIN <= r["corr_asset_vs_frame90"] < CORR_MIN + 0.05],
            "static_frame_diff_max": (max(static_diffs) if static_diffs else None),
            "all_corr_ok": all(r["corr_ge_0_30"] for r in scenes
                               if r["corr_asset_vs_frame90"] is not None),
        },
        "honest_note": ("逐景 corr 一律用冻结口径 48×48 灰度 Pearson、阈值 0.30；"
                        "**小裕度场景如实记录，未调整任何阈值**。"),
    }

    report["zero_llm"] = True
    report["zero_network"] = True
    report["promotion"] = False
    report["verdict"] = ("NO_PASS_CLAIMED（只登记实测；候选交人工观看）")
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=1, sort_keys=True),
                   encoding="utf-8")

    print("成片:", film.name, film.stat().st_size, "B")
    print("时长: {} s | 目标 978.7±1 ⇒ {}".format(
        dur, report["duration_contract"]["within_978_7_pm_1"]))
    print("PI pre blocked={} | post blocked={} promote_blocked={}".format(
        pre["blocked"], post["blocked"], post.get("promote_blocked")))
    print("字幕对齐:", sa.get("code"), "| orphan_share:", orphan.get("orphan_share"))
    print("freeze blocks:", len(freeze_blocks))
    print("运动: enabled={} verified={} | corr≥0.30: {}/{}".format(
        report["motion_verification"]["summary"]["motion_enabled_count"],
        report["motion_verification"]["summary"]["motion_verified_count"],
        report["motion_verification"]["summary"]["corr_ge_0_30_count"], len(scenes)))
    print("corr 小裕度:", json.dumps(
        report["motion_verification"]["summary"]["corr_narrow_margin_scenes"],
        ensure_ascii=False))
    print("产物:", OUT)
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
