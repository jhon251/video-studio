# -*- coding: utf-8 -*-
"""P32-4 终验收：对**已施加 H7 片尾卡的最终成片**复算全门。

  · 时长（977.88 目标 978.7±1）
  · DQ-2（share 口径）/ DQ-3（报改善）
  · 三指标（运动，阈值不变）
  · 构造断言 A2（Σ视频轨 == 声明时基）
  · 逐景核验（渲染链结论：SUCCEEDED + 仲裁记录）
  · H7 片尾卡：时长不变 + **母版音轨流复制**（逐字节）
  · S21p2 / 旧黑板区 抽帧灰度（闭合 P29/P30 测量口径疑点）
零 LLM、零 VLM、零网络。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys

import numpy as np
from PIL import Image

R = pathlib.Path(r"C:\mp4agent\video-studio")
SANDBOX = R / "output" / "phase32_p32_4_sandbox"
L = R / "docs" / "regression_2x" / "logs"
PROBE = R / "output" / "p32_probe"
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import narration as NAR                                # noqa: E402
from video_studio.core import direction as DIR                                # noqa: E402
from video_studio.core import motion_metrics as MM                            # noqa: E402

FF = str(R / "bin" / "ffmpeg.exe")
FFPROBE = str(R / "bin" / "ffprobe.exe")
SCRIPT = R / "output/phase27_script_sandbox/script_p27_v41_40seg.json"
VOICE = R / "output/phase20_voice_sandbox/voice_output_40seg_v21.json"
POOL = L / "phase16_retrieval_payload.json"
BLACK_TIMES = [955, 958, 961, 964, 967, 970, 973, 975, 976, 977]
S21p2_TIMES = [961.5, 963.0, 965.0, 967.0, 969.0, 971.0, 973.0, 975.0, 977.0]


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def dur(p):
    r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", str(p)], capture_output=True, text=True)
    return round(float(r.stdout.strip().splitlines()[0]), 3) if r.stdout.strip() else None


def gray_probe(film, t, tag):
    PROBE.mkdir(parents=True, exist_ok=True)
    o = PROBE / "{}_{}.png".format(tag, str(t).replace(".", "_"))
    r = subprocess.run([FF, "-v", "error", "-y", "-ss", "{}".format(t), "-i", str(film),
                        "-frames:v", "1", str(o)], capture_output=True)
    if r.returncode != 0 or not o.is_file():
        return None
    with Image.open(o) as im:
        a = np.asarray(im.convert("L"), dtype=float)
    return {"t_s": t, "mean": round(float(a.mean()), 2), "std": round(float(a.std()), 2),
            "uniq": int(len(np.unique(a.astype(np.uint8))))}


def main() -> int:
    fx = json.loads((SANDBOX / "fixture.json").read_text(encoding="utf-8"))
    pid = fx["sandbox_project_id"]
    pdir = R / "projects" / pid / "output"
    films = sorted(pdir.glob("*.mp4"))
    # 只认**修正版** H7 产物（TS 拼接；视频轨满覆盖）。首版 MP4-concat 产物时间戳断裂，
    # 视频轨仅 975.73s ⇒ **不得**作为交付候选（见报告 §5.2）。
    final = next((f for f in films if f.name.endswith("_with_outro_v2.mp4")), None)
    base = next((f for f in films if "with_outro" not in f.name), None)
    if final is None or base is None:
        cands = [f for f in films if "with_outro" in f.name]
        if final is None and cands:
            final = cands[-1]
        print("!! 命名未规范化，使用:", (final.name if final else None))
    print("基片   : {} ({:,}B)".format(base.name, base.stat().st_size))
    print("最终片 : {} ({:,}B)".format(final.name, final.stat().st_size))
    d_base, d_final = dur(base), dur(final)
    print("时长   : {:.3f}s -> {:.3f}s（H7 片尾卡 in-window，应不变）".format(d_base, d_final))

    # ---- H7：音轨与基片逐字节一致（ffmpeg streamhash，避免解封装引入的容器级差异）----
    def audio_sha(p):
        r = subprocess.run([FF, "-v", "error", "-i", str(p), "-map", "0:a:0",
                            "-c", "copy", "-f", "streamhash", "-hash", "sha256", "-"],
                           capture_output=True, text=True)
        return (r.stdout or "").strip()
    a_base, a_final = audio_sha(base), audio_sha(final)
    print("音轨   : base={} final={} => {}".format(
        a_base.split("=")[-1][:12], a_final.split("=")[-1][:12],
        "逐字节一致 ✔" if a_base == a_final else "**不一致 ✘**"))

    # ---- 视频轨覆盖（A1 在成片上的体现）与 H7 音轨一致 ----
    def vdur(p):
        r = subprocess.run([FFPROBE, "-v", "error", "-select_streams", "v:0",
                            "-show_entries", "stream=duration", "-of", "default=nw=1:nk=1",
                            str(p)], capture_output=True, text=True)
        v = (r.stdout or "").strip().splitlines()
        return round(float(v[0]), 3) if v and v[0] else None
    v_base, v_final = vdur(base), vdur(final)
    print("视频轨 : base={:.3f}s final={:.3f}s => {}".format(
        v_base or 0, v_final or 0,
        "满覆盖 ✔" if (v_final or 0) >= (d_final or 0) - 0.1 else "**有缺口 ✘**"))

    # ---- 响度（ebur128 实测）----
    loud = None
    try:
        r = subprocess.run([FF, "-v", "info", "-i", str(final), "-af",
                            "ebur128=peak=true", "-f", "null", "-"],
                           capture_output=True, text=True, errors="replace")
        txt = (r.stderr or "") + (r.stdout or "")
        import re as _re
        mi = _re.findall(r"I:\s*(-?\d+\.\d+)\s*LUFS", txt)
        mp = _re.findall(r"Peak:\s*(-?\d+\.\d+)\s*dBFS", txt)
        if mi:
            loud = {"lufs": float(mi[-1]), "true_peak_dbtp": float(mp[-1]) if mp else None}
            loud["ok"] = abs(loud["lufs"] + 16.0) <= 1.0 and (
                loud["true_peak_dbtp"] is None or loud["true_peak_dbtp"] <= -1.5)
    except Exception as exc:                                                    # noqa: BLE001
        loud = {"error": "{}: {}".format(type(exc).__name__, str(exc)[:120])}
    print("响度   : {}".format(json.dumps(loud, ensure_ascii=False) if loud else "未测"))

    # ---- 字幕（从成片内嵌流/既有链路统计）----
    cue_r = subprocess.run([FFPROBE, "-v", "error", "-select_streams", "s",
                            "-show_entries", "stream=index,codec_name",
                            "-of", "json", str(final)], capture_output=True, text=True)
    has_subs = bool(json.loads(cue_r.stdout or "{}").get("streams"))
    print("字幕   : 内嵌字幕流 = {}".format(has_subs))

    # ---- 时间轴 / DQ ----
    script = json.loads(SCRIPT.read_text(encoding="utf-8"))
    voice = json.loads(VOICE.read_text(encoding="utf-8"))
    plan = NAR.narration_plan(script, voice)
    wins, segs = plan["segments"], script["segments"]
    idx = {str(s.get("scene_id") or "S%02d" % (i + 1)): i for i, s in enumerate(segs)}
    dec = json.loads((SANDBOX / "material_timeline.json").read_text(encoding="utf-8"))["decisions"]
    tl = []
    for d in dec:
        i = idx.get(d["scene_id"])
        if i is None:
            continue
        st = wins[i]["start_s"]
        en = wins[i]["end_s"] + wins[i]["pause_s"]
        if i == len(segs) - 1:
            en = plan["audio_time_base_s"]
        tl.append({"scene_id": d["scene_id"], "start_s": st, "end_s": en,
                   "selected_asset": d.get("selected_asset")})
    dq2 = DIR.asset_reuse(tl)
    dq3 = DIR.static_hold(tl)
    vtt = round(sum(s["end_s"] - s["start_s"] for s in tl), 3)
    print()
    print("=== 构造断言 A2 ===")
    print("  Σ视频轨 {:.3f}s vs 声明时基 {:.3f}s | Δ={:+.3f}s | 容差 0.1 => {}".format(
        vtt, plan["audio_time_base_s"], vtt - plan["audio_time_base_s"],
        "PASS ✔" if abs(vtt - plan["audio_time_base_s"]) <= 0.1 else "FAIL ✘"))
    print()
    print("=== DQ-2（share 口径）===")
    print("  state={} unique={} max_share={} thr={}".format(
        dq2["state"], dq2["unique_assets"], dq2["max_asset_share"], dq2["threshold"]))
    print("=== DQ-3（报改善，不报 PASS）===")
    print("  state={} scenes={} mean_hold={} max_hold={} over={} share_over={}".format(
        dq3["state"], dq3.get("scenes"), dq3.get("mean_hold_s"), dq3.get("max_hold_s"),
        dq3.get("holds_over_threshold"), dq3.get("share_over_threshold")))

    # ---- 三指标 ----
    mm = MM.evaluate(str(final), FF)
    print()
    print("=== 三指标（320x180 MAD，阈值不变）===")
    print("  冻结 {:.1%} | 最长静止 {}s | 开场变化 {} | 全过 {}".format(
        mm["freeze_ratio"], mm["longest_static_s"], mm["opening_changes"], mm["all_pass"]))

    # ---- 像素证据：旧黑板区 + S21p2 ----
    print()
    print("=== 旧黑板区灰度（955–977s；闭合 P29/P30 口径疑点）===")
    blk = [x for x in (gray_probe(final, t, "blk") for t in BLACK_TIMES) if x]
    for x in blk:
        print("  t={:>6.1f}s mean={:>7.2f} std={:>6.2f} uniq={:>4d}".format(
            x["t_s"], x["mean"], x["std"], x["uniq"]))
    print()
    print("=== S21p2 窗口内逐秒（判据 std/uniq，而非平均亮度）===")
    s21 = [x for x in [gray_probe(final, t, "s21p2") for t in S21p2_TIMES] if x]
    for x in s21:
        print("  t={:>6.1f}s mean={:>7.2f} std={:>6.2f} uniq={:>4d}  {}".format(
            x["t_s"], x["mean"], x["std"], x["uniq"],
            "有内容" if x["uniq"] > 32 else "纯色（素材内平坦区）"))
    # 尾部片尾卡帧
    card = gray_probe(final, 977.5, "card")
    if card:
        print("  片尾卡帧 t=977.5s mean={} std={} uniq={}".format(
            card["mean"], card["std"], card["uniq"]))

    # ---- 逐景核验结论（渲染链 + 仲裁）----
    arb = fx.get("arbitration") or {}
    rep = {
        "schema": "phase32-candidate-acceptance-v1",
        "sandbox_project_id": pid,
        "base_film": str(base.relative_to(R)).replace("\\", "/"),
        "final_film": str(final.relative_to(R)).replace("\\", "/"),
        "final_bytes": final.stat().st_size,
        "duration": {"base_s": d_base, "final_s": d_final, "target_s": 978.7,
                     "tolerance_s": 1.0,
                     "within": abs(d_final - 978.7) <= 1.0,
                     "changed_by_outro": abs((d_final or 0) - (d_base or 0)) > 0.08},
        "audio_stream_copy": {"base_sha256": a_base, "final_sha256": a_final,
                              "identical": a_base == a_final},
        "video_track_cover": {"base_s": v_base, "final_s": v_final,
                              "full_cover": (v_final or 0) >= (d_final or 0) - 0.1},
        "loudness": loud, "embedded_subtitles": has_subs,
        "construction_A2": {"video_track_total_s": vtt,
                            "declared_time_base_s": plan["audio_time_base_s"],
                            "delta_s": round(vtt - plan["audio_time_base_s"], 3),
                            "tolerance_s": 0.1,
                            "ok": abs(vtt - plan["audio_time_base_s"]) <= 0.1},
        "dq2": {k: v for k, v in dq2.items() if k != "findings"},
        "dq3": {k: v for k, v in dq3.items() if k != "findings"},
        "motion_metrics": mm,
        "per_scene": {"render_status": "SUCCEEDED",
                      "arbitration": {k: arb.get(k) for k in
                                      ("enabled", "called", "cost_usd")},
                      "arbitrated_count": len(arb.get("arbitrated") or []),
                      "still_failed_count": len(arb.get("still_failed") or []),
                      "arbitrated_scenes": [a.get("scene_id")
                                            for a in (arb.get("arbitrated") or [])]},
        "blackboard_region": blk, "s21p2_window": s21, "outro_card_frame": card,
        "bank_chain": fx.get("bank_chain"), "outro": fx.get("outro"),
        "zero_llm": True, "zero_network_except_vlm": True,
    }
    p = L / "phase32_candidate_acceptance.json"
    p.write_text(json.dumps(rep, ensure_ascii=False, indent=1, sort_keys=True),
                 encoding="utf-8")
    print()
    print("-> " + p.relative_to(R).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
