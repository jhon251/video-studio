# -*- coding: utf-8 -*-
"""**已废止**：字幕同步门（恢复点/静音检测口径）—— Phase 45 由词级金标准取代。

授权书 Phase 45 §0 裁定：**「废弃检测路线，词级重配音（O-voice）」**；
Phase 46 §0 再次确认：**「词级字幕方案确认保留（金门不回退）」**。

本文件保留为**历史留档**：继续复算并打印被废止口径的实测值（供对比与审计），
但**不再作为通过/失败门**。生效的门是 `tests/caption_word_sync_test.py`
（词级金标准：median ≤0.15s、≥95% 句 |lag| ≤0.35s）。

废止原因（实测登记）：
  · 恢复点口径的分母（恢复点数）与 cue 边界数**不匹配**（161 条 cue vs 241 个恢复点）
    ⇒ 「最近边界距离」本质是**间距统计量**，**吸附无法降低它**
    （实测吸附前 0.757s → 吸附后 0.797s，略升）；
  · 且该口径无法复现监理所报的 F5 基线（211 点 / median 0.53s / 62 处 >1s）——
    检出参数不同源（本机整条 WAV 检出 241 点；已扫 d=0.28/0.30、-32/-35dB、WAV/MP3，
    恢复点数落在 220–269，**无一组等于 211**）。
  · 词级 WordBoundary 口径**不依赖静音检测** ⇒ 滞后恒为 0（**构造保证**），无循环论证。
"""
from __future__ import annotations

import bisect
import json
import pathlib
import re
import statistics
import subprocess
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
PASS, FAIL = [], []
NOISE, MIN_D = "-35dB", 0.28
V = R / "output" / "phase36_voice"
FF = str(R / "bin" / "ffmpeg.exe")
SUPERSEDED_BY = "tests/caption_word_sync_test.py"


def detect_ends(path):
    r = subprocess.run([FF, "-v", "info", "-i", str(path), "-af",
                        "silencedetect=noise={}:d={}".format(NOISE, MIN_D),
                        "-f", "null", "-"], capture_output=True, text=True, errors="ignore")
    t = (r.stderr or "") + (r.stdout or "")
    return sorted({round(float(x), 3)
                   for x in re.findall(r"silence_end:\s*([0-9.]+)", t)})


def measure(cues, abs_rec):
    starts = sorted(c["start"] for c in cues)
    ents = sorted(c["end"] for c in cues)
    lags = []
    for r in abs_rec:
        cand = []
        k = bisect.bisect_left(starts, r)
        for j in (k - 1, k):
            if 0 <= j < len(starts):
                cand.append(abs(starts[j] - r))
        e = bisect.bisect_left(ents, r)
        for j in (e - 1, e):
            if 0 <= j < len(ents):
                cand.append(abs(ents[j] - r))
        if cand:
            lags.append(min(cand))
    return lags


def main() -> int:
    from video_studio.core import captions as C                                  # noqa: E402
    sc = json.loads((R / "output/phase36_script_sandbox/script_p36_v65_36seg.json")
                    .read_text(encoding="utf-8"))
    pay = [{"narration": s["narration"], "duration_s": s["duration_s"]}
           for s in sc["segments"]]
    tb = json.loads((V / "timebase_v65.json").read_text(encoding="utf-8"))
    wins = [{"start_s": w["start_s"], "end_s": w["end_s"]} for w in tb["windows"]]
    wav = V / "_assemble" / "narration_joined.wav"
    abs_rec = detect_ends(wav) if wav.is_file() else []
    hist = {}
    if abs_rec:
        for tag, cues in (("before_uniform", C.build_cues(pay, windows=wins)),
                          ("after_sentence_snap",
                           C.build_cues(pay, windows=wins, recoveries={
                               int(k): v for k, v in
                               json.loads((V / "recoveries_fullfilm.json")
                                          .read_text(encoding="utf-8"))["scene_local"].items()
                           } if (V / "recoveries_fullfilm.json").is_file() else None))):
            lg = measure(cues, abs_rec)
            hist[tag] = {"cues": len(cues), "recovery_points": len(abs_rec),
                         "median_lag_s": round(statistics.median(lg), 3) if lg else None,
                         "over_1s": sum(1 for x in lg if x > 1.0)}
    print("**废止口径**（历史留档，不作为门）")
    print("  取代者：{}".format(SUPERSEDED_BY))
    for k, v in hist.items():
        print("  {:<20} cue {:>3} | 恢复点 {:>3} | median {:.3f}s | >1s {}".format(
            k, v["cues"], v["recovery_points"], v["median_lag_s"], v["over_1s"]))
    print("  废止理由：cue 边界 {} 条 vs 恢复点 {} 个 ⇒ 分母不匹配，".format(
        hist.get("after_sentence_snap", {}).get("cues", 0), len(abs_rec)))
    print("            「最近边界距离」是间距统计量，吸附无法降低（实测略升）。")
    print()
    # 生效门必须通过
    import subprocess as sp
    r = sp.run([sys.executable, str(R / "tests" / "caption_word_sync_test.py")],
               capture_output=True, text=True, encoding="utf-8", errors="ignore")
    ok = r.returncode == 0
    (PASS if ok else FAIL).append("superseding_gate")
    print("{}  生效门 `{}` ⇒ rc={}".format(
        "PASS" if ok else "FAIL", SUPERSEDED_BY, r.returncode))
    print()
    print("=" * 76)
    print("caption_sync_test（已废止，仅留档）: {} PASS / {} FAIL".format(
        len(PASS), len(FAIL)))
    print("=" * 76)
    (R / "docs/regression_2x/logs/p44_2_caption_sync_independent.json").write_text(
        json.dumps({"schema": "p44-2-caption-sync-independent-v1",
                    "status": "SUPERSEDED", "superseded_by": SUPERSEDED_BY,
                    "superseded_in_phase": 45,
                    "reason": ("恢复点口径分母不匹配（cue 161 vs 恢复点 241）；"
                               "「最近边界距离」为间距统计量，吸附无法降低；"
                               "且无法复现监理 F5 基线 211/0.53/62（检出参数不同源）"),
                    "historical": hist,
                    "effective_gate_rc": r.returncode,
                    "pass": len(PASS), "fail": len(FAIL)},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
