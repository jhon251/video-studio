# -*- coding: utf-8 -*-
"""Phase 44 诊断 v2：**扫描口径**以复现监理的 F5 基线（median 0.53s / 62 处 >1s）。

扫描维度：
  · 容差：0.3/0.4/0.5/0.6/0.8/1.0/1.5/2.0 s
  · 定义：L1 = 仅取恢复点**之后**最近切换点（滞后）；L2 = 残余静音（下条起步 - 恢复点，
    需 >0）；L3 = 最近边界距离（起或终，双向）
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


def lags_for(cues, tol, kind):
    starts = sorted(c["start"] for c in cues)
    ents = sorted(c["end"] for c in cues)
    out = []
    for r in abs_rec:
        k = bisect.bisect_left(starts, r)
        if kind == "L1":
            if k < len(starts) and 0 <= starts[k] - r <= tol:
                out.append(starts[k] - r)
        elif kind == "L2":
            if k < len(starts):
                out.append(starts[k] - r)
        else:
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
                out.append(min(cand))
    return out


def main() -> int:
    cues = C.build_cues(PAY, windows=WINS, recoveries=RECS)
    print("目标基线：median 0.53s / 62 处 >1s（监理实测）")
    print()
    print("{:<4} {:<6} {:>6} {:>9} {:>8} {:>7}".format("定义", "容差", "匹配", "median", ">1s", "占比"))
    best = None
    for kind in ("L1", "L2", "L3"):
        for tol in (0.3, 0.4, 0.5, 0.6, 0.8, 1.0, 1.5, 2.0):
            lg = lags_for(cues, tol, kind)
            if not lg:
                continue
            med = statistics.median(lg)
            over = sum(1 for x in lg if x > 1.0)
            d = abs(med - 0.53) + abs(over - 62) / 100.0
            print("{:<4} {:<6} {:>6} {:>9.3f} {:>8} {:>6.1%}".format(
                kind, tol, len(lg), med, over, over / len(lg)))
            if best is None or d < best[0]:
                best = (d, kind, tol, len(lg), med, over)
    print()
    print("最接近监理基线的口径：{} tol={} ⇒ 匹配 {} | median {:.3f}s | >1s {}".format(
        best[1], best[2], best[3], best[4], best[5]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
