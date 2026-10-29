# -*- coding: utf-8 -*-
"""只读补测：H3c-2 的冻结 PI-4 值与流级时长（用于区分 A1 严格验收 vs 冻结门禁口径）。"""
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import integrity as core_integrity            # noqa: E402

L = R / "docs" / "regression_2x" / "logs"
B2 = json.loads((L / "phase6g_exec_batch2.json").read_text(encoding="utf-8"))
FF, FP = str(R / "bin" / "ffmpeg.exe"), str(R / "bin" / "ffprobe.exe")
film = R / B2["stages"][1]["measured"]["path"]
probe = core_integrity.probe_tracks(str(film), FP)
pi4 = core_integrity.av_track_consistency(probe, 978.656)
pi4_h1 = core_integrity.av_track_consistency(
    core_integrity.probe_tracks(B2["stages"][0]["measured"]["path"], FP), 978.656)
out = {"film": B2["stages"][1]["measured"]["path"],
       "A1_harness_gate": {"required_s": 978.656, "tolerance_s": 0.05,
                           "measured_s": B2["stages"][1]["measured"]["format_duration_s"],
                           "status": "FAIL"},
       "frozen_PI4_gate": {"policy_max_video_timeline_delta_s":
                           core_integrity.DEFAULT_POLICY["max_video_timeline_delta_s"],
                           "state": pi4["state"], "video_vs_timeline_s": pi4.get("video_vs_timeline_s"),
                           "track_delta_s": pi4.get("track_delta_s")},
       "frozen_PI4_reference_H3c1": {"state": pi4_h1["state"],
                                     "video_vs_timeline_s": pi4_h1.get("video_vs_timeline_s")},
       "streams": B2["stages"][1]["measured"]["streams"],
       "audio_duration_s": B2["stages"][1]["measured"]["audio_duration_s"],
       "video_duration_s": B2["stages"][1]["measured"]["video_duration_s"],
       "frames": B2["stages"][1]["measured"]["video_frames"],
       "note": "A1(±0.05s) 是本批 harness 的**严格验收**；冻结 PI-4 口径为 ±1.0s。"
               "两者均未修改；H3c-2 按 A1 失败并 STOP，其产物未被接受。"}
(L / "phase6g_batch2_h3c2_diag.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                                 encoding="utf-8")
print(json.dumps(out, ensure_ascii=False, indent=1))
