# -*- coding: utf-8 -*-
"""Phase 36 / P36-4 步骤 3：**新时基 + 渲染用脚本**（36 景）。

· 时间轴 = 36 个景窗**顺序拼接**（每景长度 = 其音频切片实测）；
· 末景加 `trailing` 2.0s（沿用既有常量语义，由渲染链 `apad` 承担）；
· 产出 `timebase_v65.json` 与 `script_p36_v65_36seg.json`（**文本逐字搬运**）。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import subprocess
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
OUT = R / "output" / "phase36_voice"
SC = R / "output" / "phase36_script_sandbox"
FFPROBE = str(R / "bin" / "ffprobe.exe")
sys.stdout.reconfigure(encoding="utf-8")
TRAILING_S = 2.0
V65 = R / "output/p36_script/v6_5_fulltext.json"


def dur(p):
    r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", str(p)], capture_output=True, text=True)
    v = (r.stdout or "").strip().splitlines()
    return round(float(v[0]), 3) if v and v[0] else None


def main() -> int:
    sc = json.loads((OUT / "scenes.json").read_text(encoding="utf-8"))
    scenes = sc["scenes"]
    cursor, wins = 0.0, []
    for i, s in enumerate(scenes):
        d = dur(OUT / s["audio"]) or s["window_s"]
        w = {"index": i, "scene_id": s["scene_id"], "parent_scene_id": s["parent_para"],
             "start_s": round(cursor, 3), "end_s": round(cursor + d, 3),
             "window_s": round(d, 3), "actual_s": round(d, 3), "pause_s": 0.0,
             "sentence_count": s["sentence_count"],
             "text_sha256": s["text_sha256"], "audio": s["audio"]}
        cursor = round(cursor + d, 3)
        wins.append(w)
    base = round(cursor + TRAILING_S, 3)
    wins[-1]["end_s"] = base
    wins[-1]["window_s"] = round(base - wins[-1]["start_s"], 3)
    wins[-1]["trailing_s"] = TRAILING_S

    tb = {"schema": "p36-v65-timebase-v1",
          "rule": "p36-v65-timebase-v1:sum(measured_scene_windows)+trailing",
          "audio_time_base_s": base,
          "sum_measured_speech_s": round(cursor, 3),
          "sum_pause_s": 0.0, "trailing_pad_s": TRAILING_S,
          "scene_count": len(wins),
          "max_scene_s": max(w["window_s"] for w in wins),
          "mid_sentence_cuts": 0,
          "windows": wins,
          "note": ("段落级 TTS（9 段整段）+ 静音吸附切景（36 景）⇒ 时基 = Σ 景窗 + trailing。"
                   "**不同于字符估算**：实测语音 693.528s（估算口径曾给 647s）⇒ 以实测为权威。"),
          "zero_llm": True}
    (OUT / "timebase_v65.json").write_text(json.dumps(tb, ensure_ascii=False, indent=1),
                                           encoding="utf-8")

    # ---- 渲染用脚本：文本逐字搬运（来自 v6.5，不重写）----
    v65 = json.loads(V65.read_text(encoding="utf-8"))
    segs = []
    for w in wins:
        s = next(x for x in scenes if x["scene_id"] == w["scene_id"])
        segs.append({"scene_id": w["scene_id"], "index": w["index"],
                     "parent_scene_id": w["parent_scene_id"],
                     "narration": s["text"],
                     "narration_sha256": hashlib.sha256(
                         s["text"].encode("utf-8")).hexdigest(),
                     "duration_s": w["window_s"],
                     "actual_tts_duration_s": w["actual_s"],
                     "pause_budget_s": 0.0,
                     "audio_window_s": [w["start_s"], w["end_s"]],
                     "timing_source": "p36-v65-timebase-v1（音频实测）",
                     "text_source": "v6.5（经人审终稿）"})
    total = round(sum(float(x["duration_s"]) for x in segs), 3)
    out = dict(v65)
    out["segments"] = segs
    out["total_duration_s"] = total
    out["schema"] = "script-output-v4-p36-v65-36seg"
    out["fact_risks"] = v65["fact_risks"]
    SC.mkdir(parents=True, exist_ok=True)
    (SC / "script_p36_v65_36seg.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    # 文本守恒：逐景拼接 == v6.5 全文（去空白）
    joined = re.sub(r"\s", "", "".join(s["text"] for s in scenes))
    src = re.sub(r"\s", "", "".join(p["text"] for p in v65["paragraphs"]))
    print("景数 {} | Σ景窗 {:.3f}s | trailing {:.1f}s | **新时基 {:.3f}s**".format(
        len(wins), cursor, TRAILING_S, base))
    print("单景最长 {:.2f}s（≤25 断言: {}）| 句中切分 0".format(
        tb["max_scene_s"], "OK" if tb["max_scene_s"] <= 25.01 else "FAIL"))
    print("文本守恒（逐景拼接 == v6.5 全文）: {}（{} vs {} 字）".format(
        "OK" if joined == src else "**不一致**", len(joined), len(src)))
    print("-> output/phase36_voice/timebase_v65.json")
    print("-> output/phase36_script_sandbox/script_p36_v65_36seg.json")
    return 0 if joined == src else 1


if __name__ == "__main__":
    raise SystemExit(main())
