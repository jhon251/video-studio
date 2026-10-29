# -*- coding: utf-8 -*-
"""P31 验收（候选级）：时长 / DQ-2 / DQ-3 / 三指标（运动）/ 成片探针。零 LLM、零 VLM、零网络。

注：逐景核验（per_scene）由渲染链内部的 `ASSET_INSUFFICIENT` 闸门决定 —— 本脚本从
`render.log` 读取其结论，避免重复抽帧。
"""
from __future__ import annotations

import collections
import json
import pathlib
import re
import subprocess
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
SANDBOX = R / "output" / "phase31_p31_3_sandbox"
L = R / "docs" / "regression_2x" / "logs"
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import narration as NAR                                # noqa: E402
from video_studio.core import direction as DIR                                # noqa: E402
from video_studio.core import motion_metrics as MM                            # noqa: E402

FF = str(R / "bin" / "ffmpeg.exe")
FFPROBE = str(R / "bin" / "ffprobe.exe")
SCRIPT = R / "output/phase27_script_sandbox/script_p27_v41_40seg.json"
VOICE = R / "output/phase20_voice_sandbox/voice_output_40seg_v21.json"
POOL = R / "docs/regression_2x/logs/phase16_retrieval_payload.json"


def main() -> int:
    fx = json.loads((SANDBOX / "fixture.json").read_text(encoding="utf-8"))
    pid = fx["sandbox_project_id"]
    films = sorted((R / "projects" / pid / "output").glob("*.mp4"),
                   key=lambda p: -p.stat().st_size)
    film = films[0]
    dur = float(subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                                "-of", "default=nw=1:nk=1", str(film)],
                               capture_output=True, text=True).stdout.strip().splitlines()[0])
    print("成片 {} ({:,}B) | {:.3f}s".format(film.name, film.stat().st_size, dur))

    # 权威时间轴
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
    print()
    print("=== DQ-2 ===")
    print("  state={} unique={} max_share={} threshold={}".format(
        dq2["state"], dq2["unique_assets"], dq2["max_asset_share"], dq2["threshold"]))
    print("=== DQ-3（adv={}）===".format(dq3.get("enforced")))
    print("  state={} scenes={} mean_hold={} max_hold={} over={} share_over={}".format(
        dq3["state"], dq3.get("scenes"), dq3.get("mean_hold_s"), dq3.get("max_hold_s"),
        dq3.get("holds_over_threshold"), dq3.get("share_over_threshold")))

    # 三指标（运动）
    mm = MM.evaluate(str(film), FF)
    print()
    print("=== 三指标（320x180 MAD，阈值不变）===")
    print("  冻结占比 {:.1%} | 最长静止 {}s | 开场变化 {} | 全过 {}".format(
        mm["freeze_ratio"], mm["longest_static_s"], mm["opening_changes"], mm["all_pass"]))

    # 渲染闸门结论
    log = (SANDBOX / "render.log").read_text(encoding="utf-8", errors="replace")
    m = re.search(r"render: status=(\S+) error=(.*)", log)
    status = m.group(1) if m else "UNKNOWN"
    err = (m.group(2) if m else "")[:400]
    fails = []
    # render.log 里 ASSET_INSUFFICIENT 的 JSON 明细（可能被截断 ⇒ 逐景正则提取）
    for m3 in re.finditer(
            r'\{"scene_id": "([^"]+)", "expected": ([^,]+), "best": ([^,]+), '
            r'"corr_expected": ([\d.]+), "corr_best": ([\d.]+), "sample_t": ([\d.]+)',
            log):
        fails.append({"scene_id": m3.group(1), "expected": m3.group(2).strip('"'),
                      "best": m3.group(3).strip('"'),
                      "corr_expected": float(m3.group(4)),
                      "corr_best": float(m3.group(5)),
                      "sample_t": float(m3.group(6))})
    print()
    print("=== 渲染闸门 ===")
    print("  status={} | failed_scenes={}".format(status, len(fails)))
    for f in fails[:6]:
        print("   {} expected={} corr_expected={} corr_best={}".format(
            f.get("scene_id"), f.get("expected"), f.get("corr_expected"), f.get("corr_best")))

    rep = {"schema": "phase31-candidate-acceptance-v1",
           "film": str(film.relative_to(R)).replace("\\", "/"),
           "film_bytes": film.stat().st_size, "duration_s": round(dur, 3),
           "duration_contract": {"measured_s": round(dur, 3), "target_s": 978.7,
                                 "tolerance_s": 1.0,
                                 "within": abs(dur - 978.7) <= 1.0},
           "declared_time_base_s": plan["audio_time_base_s"],
           "video_track_total_s": dq2["total_s"],
           "dq2": {k: v for k, v in dq2.items() if k != "findings"},
           "dq3": {k: v for k, v in dq3.items() if k != "findings"},
           "motion_metrics": mm,
           "render_gate": {"status": status, "error": err,
                           "failed_scenes": fails},
           "zero_llm": True, "zero_vlm": True, "zero_network": True}
    p = L / "phase31_candidate_acceptance.json"
    p.write_text(json.dumps(rep, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    print()
    print("-> " + p.relative_to(R).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
