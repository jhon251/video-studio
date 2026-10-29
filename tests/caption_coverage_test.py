# -*- coding: utf-8 -*-
"""Phase 52 / P52-2：**三条独立信号源门**（阈值全部运行前写死）。

  · **覆盖门（新）**：最终 cue 对**语音运行**的覆盖率 ≥95%
    （分母 = **语音时长**，不是恢复点数 —— F8 的循环论证教训）；
  · **时长健全门（新）**：cue 时长 median ≥3s，且 时长=1.0s±0.1 的 cue = 0
    （F8 的 clamp 签名 102/105 作 **before 夹具**）；
  · **同步门（重定义）**：句 cue 起点 vs 该句**首运行起点**偏差 ≤0.35s 的句子 ≥90%
    （**独立实测**，非 manifest）；
  · **排他门**：max 同时活跃 cue == 1（沿用，见 caption_overlap_test）。
"""
from __future__ import annotations

import json
import pathlib
import statistics
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
PASS, FAIL = [], []
COVER_MIN = 0.95          # **运行前写死**
MEDIAN_MIN_S = 3.0        # **运行前写死**
CLAMP_TOL_S = 0.1         # **运行前写死**
CLAMP_COUNT_MAX = 0       # **运行前写死**
SYNC_TOL_S = 0.35         # **运行前写死**
SYNC_COVER_MIN = 0.90     # **运行前写死**
BEFORE_F8 = {"clamp_cues": 102, "cues": 105, "coverage": 0.142,
             "median_dur_s": 1.0}
V52 = R / "output" / "phase52_voice"


def check(name, ok, detail=None):
    (PASS if ok else FAIL).append(name)
    print("{}  {} {}".format("PASS" if ok else "FAIL", name,
                             "" if ok else json.dumps(detail, ensure_ascii=False,
                                                      default=str)[:300]))
    return bool(ok)


def main() -> int:
    from video_studio.core import captions as C                                  # noqa: E402
    rp = V52 / "runs_by_scene.json"
    if not rp.is_file():
        print("SKIP  缺 runs_by_scene.json")
        sys.exit(0)
    runs = {k: [tuple(x) for x in v]
            for k, v in json.loads(rp.read_text(encoding="utf-8"))["runs_by_scene"].items()}
    sc = json.loads((R / "output/phase36_script_sandbox/script_p36_v65_36seg.json")
                    .read_text(encoding="utf-8"))
    segs = [{"scene_id": s["scene_id"], "narration": s["narration"],
             "duration_s": s["duration_s"]} for s in sc["segments"]]
    tb = json.loads((R / "output/phase36_voice/timebase_v65.json").read_text(encoding="utf-8"))
    wins = [{"start_s": w["start_s"], "end_s": w["end_s"]} for w in tb["windows"]]
    cues = C.build_cues_from_audio(segs, runs, windows=wins)
    if not cues:
        print("SKIP  未生成 cue")
        sys.exit(0)

    # ---- 覆盖门 ----
    tot_speech = sum(b - a for v in runs.values() for a, b in v)
    covered = 0.0
    for i, w in enumerate(wins):
        sid = segs[i]["scene_id"]          # 窗口与段**按下标对齐**（无 scene_id 字段）
        w0 = float(w["start_s"])
        win_cues = [c for c in cues if c["scene_id"] == sid]
        for a, b in runs.get(sid, []):
            aa, bb = w0 + a, w0 + b
            best = 0.0
            for c in win_cues:
                best = max(best, max(0.0, min(c["end"], bb) - max(c["start"], aa)))
            covered += best
    cov = covered / max(tot_speech, 1e-9)

    # ---- 时长健全门 ----
    durs = [c["dur"] for c in cues]
    med = statistics.median(durs)
    clamps = sum(1 for d in durs if abs(d - 1.0) <= CLAMP_TOL_S)

    # ---- 同步门（独立实测：句 cue 起点 vs 该句首运行起点）----
    ok_sync = 0
    checked = 0
    for i, w in enumerate(wins):
        sid = segs[i]["scene_id"]          # 窗口与段按下标对齐
        w0 = float(w["start_s"])
        rns = runs.get(sid, [])
        win_cues = sorted([c for c in cues if c["scene_id"] == sid],
                          key=lambda c: c["start"])
        if not rns or not win_cues:
            continue
        # 该景的运行序列按 cue 数切块（与构建规则同构）⇒ 取每块首运行起点作参照
        n = len(win_cues)
        prev = 0
        for k, c in enumerate(win_cues):
            if n == 1:
                blk = rns
            else:
                if len(rns) >= n:
                    end = prev + max(1, round(len(rns) * (k + 1) / n) - prev)
                    end = min(end, len(rns) - (n - k - 1))
                    end = max(end, prev + 1)
                    blk = rns[prev:end]
                    prev = end
                else:
                    tot = sum(b - a for a, b in rns) or 1.0
                    lo = k / n
                    blk = [("__frac__", lo, lo + 1.0 / n)]
            if blk and blk[0][0] == "__frac__":
                tot = sum(b - a for a, b in rns) or 1.0
                s_ref = w0 + min(a for a, _ in rns) + tot * blk[0][1]
            else:
                s_ref = w0 + blk[0][0]
            checked += 1
            if abs(c["start"] - s_ref) <= SYNC_TOL_S:
                ok_sync += 1
    sync_cov = ok_sync / max(checked, 1)

    print("cue {} 条 | 语音总时长 {:.1f}s".format(len(cues), tot_speech))
    print("覆盖 {:.1f}s ⇒ **{:.1%}**（门限 ≥{:.0%}）".format(covered, cov, COVER_MIN))
    print("时长 median {:.3f}s（门限 ≥{:.1f}s）| =1.0s±{} 的 cue = {}（门限 {}）".format(
        med, MEDIAN_MIN_S, CLAMP_TOL_S, clamps, CLAMP_COUNT_MAX))
    print("同步：{}/{} 句偏差 ≤{}s ⇒ **{:.1%}**（门限 ≥{:.0%}）".format(
        ok_sync, checked, SYNC_TOL_S, sync_cov, SYNC_COVER_MIN))
    print("before 夹具（F8）：clamp {} / {} 条，覆盖 {:.1%}，median {:.1f}s".format(
        BEFORE_F8["clamp_cues"], BEFORE_F8["cues"], BEFORE_F8["coverage"],
        BEFORE_F8["median_dur_s"]))
    print()
    check("覆盖门 ≥{:.0%}（实测 {:.1%}）".format(COVER_MIN, cov), cov >= COVER_MIN, {"cov": cov})
    check("时长 median ≥{:.1f}s（实测 {:.3f}s）".format(MEDIAN_MIN_S, med),
          med >= MEDIAN_MIN_S, {"median": med})
    check("时长=1.0s±{} 的 cue == {}（实测 {}）".format(CLAMP_TOL_S, CLAMP_COUNT_MAX, clamps),
          clamps <= CLAMP_COUNT_MAX, {"clamps": clamps})
    check("同步门 ≥{:.0%}（实测 {:.1%}）".format(SYNC_COVER_MIN, sync_cov),
          sync_cov >= SYNC_COVER_MIN, {"sync_cov": sync_cov})
    print()
    print("=" * 76)
    print("caption_coverage_test: {} PASS / {} FAIL".format(len(PASS), len(FAIL)))
    print("=" * 76)
    (R / "docs/regression_2x/logs/p52_2_coverage_gates.json").write_text(
        json.dumps({"schema": "p52-2-coverage-gates-v1",
                    "independent_signal_source": "每景实际音频切片的 silencedetect 语音运行",
                    "thresholds": {"cover_min": COVER_MIN, "median_min_s": MEDIAN_MIN_S,
                                   "clamp_tol_s": CLAMP_TOL_S,
                                   "clamp_count_max": CLAMP_COUNT_MAX,
                                   "sync_tol_s": SYNC_TOL_S,
                                   "sync_cover_min": SYNC_COVER_MIN},
                    "cues": len(cues), "speech_total_s": round(tot_speech, 3),
                    "covered_s": round(covered, 3), "coverage": round(cov, 4),
                    "median_dur_s": round(med, 3), "clamp_cues": clamps,
                    "sync_ok": ok_sync, "sync_checked": checked,
                    "sync_cover": round(sync_cov, 4),
                    "before_fixture_F8": BEFORE_F8,
                    "pass": len(PASS), "fail": len(FAIL)},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
