# -*- coding: utf-8 -*-
"""Phase 44 诊断：核对字幕同步口径 —— 复核监理的 F5 基线（median 0.53s / 62 处 >1s）。

两种口径差异：
  · **口径 A（我 F5 用的）**：恢复点 → 取**最近 cue 切换点**，若在 +0.4s 内记滞后；
  · **口径 B（监理口径，推测）**：恢复点 → 取**最近 cue 边界（起点或终点）**的**距离**，
    不论在恢复点前或后 —— 这会把「cue 已结束但下一条还没起」也算作滞后。
本脚本同时跑两种，并输出 F5 基线与「句级吸附后」的对比。
"""
from __future__ import annotations

import bisect
import json
import pathlib
import statistics
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import captions as C                                      # noqa: E402

V = R / "output" / "phase36_voice"
TB = json.loads((V / "timebase_v65.json").read_text(encoding="utf-8"))
REC = json.loads((V / "recoveries.json").read_text(encoding="utf-8"))
SCRIPT = json.loads((R / "output/phase36_script_sandbox/script_p36_v65_36seg.json")
                    .read_text(encoding="utf-8"))
PAY = [{"narration": s["narration"], "duration_s": s["duration_s"]}
       for s in SCRIPT["segments"]]
WINS = [{"start_s": w["start_s"], "end_s": w["end_s"]} for w in TB["windows"]]
RECS = {int(k): v for k, v in REC["recoveries"].items()}
abs_rec = sorted(round(WINS[i]["start_s"] + float(x), 3)
                 for i in sorted(RECS) for x in RECS[i])


def measure(cues, mode):
    starts = sorted(c["start"] for c in cues)
    ents = sorted(c["end"] for c in cues)
    lags = []
    for r in abs_rec:
        k = bisect.bisect_left(starts, r)
        if mode == "A":                      # 仅「之后最近的切换点」
            if k < len(starts) and starts[k] - r <= 0.4:
                lags.append(starts[k] - r)
        else:                                # B：**最近的 cue 边界**（起或终）
            cand = []
            if k < len(starts):
                cand.append(abs(starts[k] - r))
            if k > 0:
                cand.append(abs(starts[k - 1] - r))
            e = bisect.bisect_left(ents, r)
            for j in (e - 1, e):
                if 0 <= j < len(ents):
                    cand.append(abs(ents[j] - r))
            if cand:
                lags.append(min(cand))
    return lags


def main() -> int:
    print("恢复点 {} 个（silencedetect -35dB/d=0.28）".format(len(abs_rec)))
    print("监理口径提示：全片句界 211 个 —— 与本机实测 {} 个不同源，如实登记。".format(
        len(abs_rec)))
    print()
    for tag, kw in (("F5 基线（±0.4s，无句级复吸）", dict(recoveries=RECS)),
                    ("句级吸附（±0.5s）", dict(recoveries=RECS, snap_tol_s=0.5))):
        cues = C.build_cues(PAY, windows=WINS, **kw)
        for mode in ("A", "B"):
            lg = measure(cues, mode)
            med = statistics.median(lg) if lg else -1
            over = sum(1 for x in lg if x > 1.0)
            print("{:<28} 口径{}: 匹配 {:>3} | median {:.3f}s | >1s {:>3} ({:.1%})".format(
                tag, mode, len(lg), med, over, over / max(len(lg), 1)))
    print()
    print("→ 若口径 B 能复现监理的 0.53s/62，则该口径为准（本阶段门将采用它）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
