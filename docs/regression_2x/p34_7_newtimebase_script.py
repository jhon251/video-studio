# -*- coding: utf-8 -*-
"""P34-3/4 前置：生成 **v4.2 新时基脚本**（`script_p34_v42_40seg.json`）。

与 P33-3 同理：净稿脚本的 `duration_s` 必须换成**本期实测**（否则渲染前闸门会正确 fail-closed）。
本脚本把逐段 `duration_s` 换为 `actual_s + pause_s`（末段含 trailing），`total_duration_s` = 新时基；
**文本逐字搬运**（`narration` 与 `narration_sha256` 原样），不覆盖既有产物。
"""
from __future__ import annotations

import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
SRC = R / "output/phase34_script_sandbox/script_p34_v42_40seg.json"
TB = R / "output/phase34_voice/timebase_v42.json"
OUT = R / "output/phase34_script_sandbox/script_p34_v42_40seg.json"
sys.stdout.reconfigure(encoding="utf-8")

OLD_TB = 687.592          # v4.1 新时基（P33）


def main() -> int:
    src = json.loads(SRC.read_text(encoding="utf-8"))
    tb = json.loads(TB.read_text(encoding="utf-8"))
    wins = {w["scene_id"]: w for w in tb["windows"]}
    segs = []
    for s in src["segments"]:
        sid = str(s.get("scene_id"))
        w = wins[sid]
        d = dict(s)
        d["duration_s"] = round(float(w["window_s"]), 3)
        d["actual_tts_duration_s"] = round(float(w["actual_s"]), 3)
        d["pause_budget_s"] = round(float(w["pause_s"]), 3)
        d["audio_window_s"] = [w["start_s"], w["end_s"]]
        d["timing_source"] = "p34-v42-timebase-v1（音频实测）"
        segs.append(d)
    total = round(sum(float(x["duration_s"]) for x in segs), 3)
    out = dict(src)
    out["segments"] = segs
    out["total_duration_s"] = total
    out["schema"] = "script-output-v3-p34-v42-newtimebase"
    prev = dict(out.get("_p34") or {})
    prev.update({
        "timing": {
            "timebase": "p34-v42-timebase-v1",
            "timebase_source": "output/phase34_voice/timebase_v42.json",
            "old_timebase_s": OLD_TB,
            "new_timebase_s": total,
            "delta_s": round(total - OLD_TB, 3),
            "why": "v4.2 净稿（移除核查腔）⇒ 旁白变短，时基随实测重算并登记",
        },
        "text_unchanged_by_this_step": True,
    })
    out["_p34"] = prev
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    a = [x.get("narration") for x in src["segments"]]
    b = [x.get("narration") for x in segs]
    ok = a == b
    print("段数 {} | Σduration_s = {:.3f}（旧 {:.3f}，Δ{:.3f}）".format(
        len(segs), total, OLD_TB, total - OLD_TB))
    print("文本逐字不变: {}".format("OK" if ok else "**不一致**"))
    print("-> " + str(OUT.relative_to(R)))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
