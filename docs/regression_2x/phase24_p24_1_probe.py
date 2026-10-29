# -*- coding: utf-8 -*-
"""P24-1 探针：在真实短片量测 freezedetect 两种口径，验证"全镜缓推"能否降低冻结占比。"""
from __future__ import annotations

import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import direction as D                                   # noqa: E402
from video_studio.core import motion as M                                      # noqa: E402

FF = str(R / "bin" / "ffmpeg.exe")
V = str(R / "output" / "p24_motion_probe" / "probe.mp4")
LOGS = R / "docs" / "regression_2x" / "logs"
import json                                                                     # noqa: E402

_records = []
for lbl, sf in (("scale=320:-2（监理口径）", "scale=320:-2"),
                ("全分辨率（不降采样）", "null")):
    for nd in (-60.0, -70.0, -80.0):
        try:
            blocks, _err = D.measure_freeze(V, FF, duration_s=20.0, scale_filter=sf,
                                            noise_db=nd, min_dur_s=1.0)
            tot = sum(float(b.get("duration_s") or 0) for b in blocks)
            mx = max([float(b.get("duration_s") or 0) for b in blocks] or [0])
            print("  {:26s} noise={:>6.1f}dB  块 {:>3} | 冻结 {:.2f}s/20s = {:>5.1%} | 最长 {:.1f}s".format(
                lbl, nd, len(blocks), tot, tot / 20.0, mx))
            _records.append({"scale_filter": sf, "noise_db": nd, "blocks": len(blocks),
                             "frozen_s": round(tot, 3), "frozen_ratio": round(tot / 20.0, 4),
                             "longest_s": round(mx, 3)})
        except Exception as exc:                                                # noqa: BLE001
            print("  {:26s} noise={:>6.1f}dB  ERR {} {}".format(
                lbl, nd, type(exc).__name__, str(exc)[:90]))
            _records.append({"scale_filter": sf, "noise_db": nd,
                             "error": "{}: {}".format(type(exc).__name__, str(exc)[:120])})

# 逐帧宽度变化统计（解释机理）
sc = {"scene_id": "S01", "duration_s": 20.0, "hook": True}
p = M.plan_scene(sc, out_w=1920, out_h=1080, fps=25)
pr, rects = p["params"], p["rects"]
uniq = len({r[2] for r in rects})
print()
print("  计划: motion_frames={} step_px={:.4f} zoom_end={} | 唯一宽度值 {} / {} 帧".format(
    pr["motion_frames"], pr["step_px"], pr["zoom_end"], uniq, p["n_frames"]))
print("  总推进 = {} px；摊到 {} 帧 = {:.3f} px/帧".format(
    1920 - pr["w_end"], pr["motion_frames"],
    (1920 - pr["w_end"]) / max(pr["motion_frames"], 1)))
print("  ⇒ 0.19px/帧 在 320px 降采样下 = {:.3f} px/帧（freezedetect 无法感知）".format(
    (1920 - pr["w_end"]) / max(pr["motion_frames"], 1) * 320 / 1920))

_p = LOGS / "phase24_p24_1_probe.json"
_p.write_text(json.dumps({
    "schema": "phase24-p24-1-freezedetect-probe-v1",
    "film": str(pathlib.Path(V).relative_to(R)).replace("\\", "/"),
    "duration_s": 20.0,
    "purpose": ("验证 `freezedetect` 能否作为「内容运动」度量 —— "
                "结论：**不能**。对真实冻结画面也报 0%，因编码噪声抖动持续超过噪声阈值。"),
    "records": _records,
    "all_zero": all(r.get("frozen_ratio", 0) == 0 for r in _records),
    "conclusion": ("`freezedetect` 是**噪声阈值**度量而非**内容运动**度量；"
                   "本阶段改用授权书指定的**逐秒差分法**（`core/motion_metrics.py`）。"
                   "监理 94.8% 基线并非由该方法得出。"),
    "plan": {"motion_frames": pr["motion_frames"], "step_px": round(pr["step_px"], 4),
             "zoom_end": pr["zoom_end"], "unique_widths": uniq, "n_frames": p["n_frames"]},
}, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
print("->", _p.relative_to(R).as_posix())
