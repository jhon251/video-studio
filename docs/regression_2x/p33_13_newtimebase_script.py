# -*- coding: utf-8 -*-
"""P33-3/4 前置：生成 **v4.1 新时基脚本**（`script_p33_v41_40seg.json`）。

为什么需要：原 v4.1 脚本的 `duration_s` 是**旧谱系（v3/V20）的规划估计**（Σ=978.634），
与本期实测新时基（700.592）不符 ⇒ 渲染前闸门 PI-1/PI-2 正确 **fail-closed**
（实测 shortfall 281.97s、旁白覆盖 0.7125）。按授权书 §3「时长契约按新时基重算并如实登记」，
本脚本把逐段 `duration_s` 换为**音频实测事实**（`actual_s + pause_s`），末段含 trailing，
`total_duration_s` = 新时基。

**文本逐字不变**（`narration` 原样搬运；`narration_sha256` 保持一致）；
**不覆盖**任何既有产物（另存新文件，登记 lineage）。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
SRC = R / "output/phase27_script_sandbox/script_p27_v41_40seg.json"
TB = R / "output/phase33_voice/timebase_v41.json"
OUT = R / "output/phase33_script_sandbox/script_p33_v41_40seg.json"
sys.stdout.reconfigure(encoding="utf-8")


def main() -> int:
    src = json.loads(SRC.read_text(encoding="utf-8"))
    tb = json.loads(TB.read_text(encoding="utf-8"))
    wins = {w["scene_id"]: w for w in tb["windows"]}
    segs = []
    for i, s in enumerate(src["segments"]):
        sid = str(s.get("scene_id"))
        w = wins[sid]
        d = dict(s)
        # 新时基事实：逐段窗口 = 实测语音 + 该边界 pause；末段含 trailing
        d["duration_s"] = round(float(w["window_s"]), 3)
        d["actual_tts_duration_s"] = round(float(w["actual_s"]), 3)
        d["pause_budget_s"] = round(float(w["pause_s"]), 3)
        d["audio_window_s"] = [w["start_s"], w["end_s"]]
        d["timing_source"] = "p33-v41-timebase-v1（音频实测）"
        segs.append(d)
    total = round(sum(float(x["duration_s"]) for x in segs), 3)
    out = dict(src)
    out["segments"] = segs
    out["total_duration_s"] = total
    out["schema"] = "script-output-v3-p33-v41-newtimebase"
    out["_p33"] = {
        "derived_from": "output/phase27_script_sandbox/script_p27_v41_40seg.json",
        "derived_from_sha256": hashlib.sha256(SRC.read_bytes()).hexdigest(),
        "timebase": "p33-v41-timebase-v1",
        "timebase_source": "output/phase33_voice/timebase_v41.json",
        "what_changed": "**仅** `duration_s` / `actual_tts_duration_s` / `pause_budget_s` / "
                        "`audio_window_s` / `total_duration_s`（旧谱系规划值 → 本期音频实测）",
        "text_changed": False,
        "narrations_edited": False,
        "old_timebase_s": 978.634,
        "new_timebase_s": total,
        "delta_s": round(total - 978.634, 3),
        "why": "旧 978.7±1 时长契约随 v3/V20 谱系废止；本版按新时基登记（授权书 §3）",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    # 校验：文本逐字不变
    a = [x.get("narration") for x in src["segments"]]
    b = [x.get("narration") for x in segs]
    h_src = hashlib.sha256("".join(a).encode("utf-8")).hexdigest()
    h_new = hashlib.sha256("".join(b).encode("utf-8")).hexdigest()
    print("段数 {} | Σduration_s = {:.3f}（旧 978.634）".format(len(segs), total))
    print("文本逐字不变: {}（{} vs {}）".format(
        "OK" if (a == b and h_src == h_new) else "**不一致**", h_src[:12], h_new[:12]))
    print("-> " + str(OUT.relative_to(R)))
    return 0 if a == b else 1


if __name__ == "__main__":
    raise SystemExit(main())
