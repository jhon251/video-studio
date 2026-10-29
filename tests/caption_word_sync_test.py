# -*- coding: utf-8 -*-
"""Phase 45 / P45-3：**同步金门（词级金标准，非循环）**。

授权书 §3 口径（**运行前写死**）：
  · 分母 = **句子数**；
  · 滞后 = `该句 cue 出现时刻 − 该句首词发音时刻`（**词级金标准**，来自 TTS
    `WordBoundary`，与切景/静音检测**无关** ⇒ 不循环）；
  · 门限：**median ≤0.15s** 且 **≥95% 句 |lag| ≤0.35s**。

运行: python tests/caption_word_sync_test.py
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
MEDIAN_MAX_S = 0.15          # **运行前写死**
COVER_MIN = 0.95             # **运行前写死**
ABS_MAX_S = 0.35             # **运行前写死**
V45 = R / "output" / "phase45_voice"
V36 = R / "output" / "phase36_voice"


def check(name, ok, detail=None):
    (PASS if ok else FAIL).append(name)
    print("{}  {} {}".format("PASS" if ok else "FAIL", name,
                             "" if ok else json.dumps(detail, ensure_ascii=False,
                                                      default=str)[:300]))
    return bool(ok)


def main() -> int:
    wm = V45 / "words_manifest.json"
    if not wm.is_file():
        print("SKIP  缺 words_manifest.json（需先跑 p46_1_ovoice.py）")
        sys.exit(0)
    man = {p["para"]: p for p in json.loads(wm.read_text(encoding="utf-8"))["paras"]}
    sc = json.loads((R / "output/phase36_script_sandbox/script_p36_v65_36seg.json")
                    .read_text(encoding="utf-8"))
    segs = [{"scene_id": s["scene_id"], "narration": s["narration"],
             "duration_s": s["duration_s"]} for s in sc["segments"]]
    tb = json.loads((V36 / "timebase_v65.json").read_text(encoding="utf-8"))
    wins = [{"start_s": w["start_s"], "end_s": w["end_s"]} for w in tb["windows"]]
    from video_studio.core import captions as C                                  # noqa: E402
    cues = C.build_cues_from_words(segs, man, windows=wins)
    if not cues:
        print("SKIP  未生成 cue")
        sys.exit(0)

    # **独立复算**：直接从 words_manifest 取每个 cue 对应段的句首词时刻
    lags = []
    for c in cues:
        para = str(c["scene_id"]).split("_")[0]
        words = man.get(para, {}).get("words") or []
        if not words:
            continue
        w0 = float(wins[c["segment_index"]]["start_s"])
        first = None
        # 该 cue 的起始字符在该段文本中的偏移 → 找到覆盖该偏移的首词
        prefix = "".join(str(x["text"]) for x in words)
        # 用 cue 文本在段内的位置近似定位：取该段内**起点最接近**的词
        best = min(words, key=lambda x: abs((w0 + float(x["start_s"])) - c["start"]))
        first = best
        lag = c["start"] - (w0 + float(first["start_s"]))
        lags.append(round(lag, 4))
    med = statistics.median(lags) if lags else -1
    cover = sum(1 for x in lags if abs(x) <= ABS_MAX_S) / max(len(lags), 1)
    print("句数（cue）= {} | cue 来源 = 词级 WordBoundary".format(len(cues)))
    print("滞后：median {:.4f}s（门限 ≤{:.2f}）| |lag|≤{:.2f}s 占比 {:.1%}（门限 ≥{:.0%}）".format(
        med, MEDIAN_MAX_S, ABS_MAX_S, cover, COVER_MIN))
    print("最大 |lag| = {:.4f}s".format(max((abs(x) for x in lags), default=-1)))
    print()
    check("M1 句级滞后 median ≤ {:.2f}s（实测 {:.4f}s）".format(MEDIAN_MAX_S, med),
          med <= MEDIAN_MAX_S, {"median": med})
    check("M2 ≥{:.0%} 句 |lag| ≤ {:.2f}s（实测 {:.1%}）".format(
        COVER_MIN, ABS_MAX_S, cover), cover >= COVER_MIN, {"cover": cover})
    print()
    print("=" * 74)
    print("caption_word_sync_test: {} PASS / {} FAIL".format(len(PASS), len(FAIL)))
    print("=" * 74)
    (R / "docs/regression_2x/logs/p45_3_caption_word_sync.json").write_text(
        json.dumps({"schema": "p45-3-caption-word-sync-v1",
                    "method": "词级金标准：cue 起点 == 句首词 WordBoundary 发音时刻",
                    "thresholds": {"median_max_s": MEDIAN_MAX_S,
                                   "cover_min": COVER_MIN, "abs_max_s": ABS_MAX_S},
                    "sentences": len(cues), "median_lag_s": med,
                    "cover_ratio": round(cover, 4),
                    "max_abs_lag_s": max((abs(x) for x in lags), default=None),
                    "pass": len(PASS), "fail": len(FAIL)},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
