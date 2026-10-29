# -*- coding: utf-8 -*-
"""Phase 52：**落账（FAIL-CLOSED）** —— 音频锚定构建器已建成并通过新门，
但**烧录 ASS 的时间轴仍是坏的**，故**不登记 F9**。

## 已完成（且证据充分）
· **P52-1 音频锚定构建器** `core/captions.py::build_cues_from_audio`
  （独立信号源：每景**实际音频切片**的 `silencedetect(-30dB,d=0.05)` 语音运行）；
· **逐景语音运行**：`output/phase52_voice/runs_by_scene.json`（**36 景 / 733 运行 /
  511.4s 语音**）；
· **P52-2 四条门全部通过**（`tests/caption_coverage_test.py` 4/4）：
  · **覆盖门**：**99.3%**（门限 ≥95%；F8 为 **14.2%**）
  · **时长健全门**：median **5.720s**（门限 ≥3.0s）；**=1.0s±0.1 的 cue = 0**
    （门限 0；F8 为 **102/105**）
  · **同步门**：**100.0%**（门限 ≥90%）
  · 排他门：构建器输出 max 同时活跃 = 1（单元级验证）

## 阻断（本轮未能定位到底）
**烧录 ASS 的时间轴与构建器输出**不符：
```
Dialogue: 0,0:00:00.00,0:00:06.80,Cap,,0,0,0,,有限单群分类就是一个由几百位数学家…   ← 文本属 P04
Dialogue: 0,0:00:06.80,0:00:04.78,Cap,,0,0,0,,几何题在自动推理里一直算不上好啃…   ← 起点=上条终点，终点=**下一条的时长**
Dialogue: 0,0:00:04.78,0:00:05.33,Cap,,0,0,0,,六道做出四道…
```
读出两个**具体异常**：
  1. **`start = 上一条的 end`、`end = 下一条的时长`** —— 这个交错模式说明
     cue 列表在**写入前被某种位移/复用**（或 `start`/`end` 之一被当成了 `dur`）；
  2. **cue 文本与区间不对应**（首条文本属 P04，却拿到 0.00–6.80）。

已排除：`to_ass()` 是**纯格式化**（逐字核对，无重排/无时移）；
cue 数 **111** 与音频锚定路径**一致**（legacy 为 161、词级为 100）
⇒ 用的是**音频锚定路径的 cue 集合**，但**时间字段被破坏**。
**未定位到破坏点**，如实登记，不编造解释。

## 交付候选
保持 **F / F2 / F3 / F4 / F5 / F6 / F7 / F7.1 / F8** 不变；**F9 未登记**；零 promotion。

## 建议下一轮（定位方法同 P48 成功的「转储 diff」）
在 `cap_path.write_text(to_ass(cues…))` **之前**把 `cues` 完整转储为 JSON，
与「同一输入直接调用 `build_cues_from_audio` 的结果」**逐字段 diff** ⇒
即可确定是**构建器在 agent 内被不同参数调用**还是**写入前被改写**。
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")
CAND_ASS = R / "projects/p_2b2ba564282e/artifacts/_captions_t_f23af892b21a.ass"


def main() -> int:
    cov = json.loads((L / "p52_2_coverage_gates.json").read_text(encoding="utf-8"))
    runs = json.loads((R / "output/phase52_voice/runs_by_scene.json")
                      .read_text(encoding="utf-8"))
    raw = []
    if CAND_ASS.is_file():
        for line in CAND_ASS.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.startswith("Dialogue:"):
                raw.append(line[:150])
    rec = {
        "schema": "p52-failclosed-v1",
        "stage": "Phase 52（词时刻音频锚定 + 覆盖门）—— FAIL-CLOSED，未登记 F9",
        "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "accepted_supervisor_diagnosis": {
            "①clock_drift": "合成 manifest 时钟 ≠ 实际音频时钟 —— **实测确认**（F8 覆盖仅 14.2%）",
            "②clamp_cascade": "**实测确认**（F8 的 105 条 cue 中 **102 条**恰为 1.0s±0.1）",
            "③coverage_gap": "**实测确认**（F8 覆盖 14.2%，610 个语音运行覆盖 <50%）",
            "supervisor_own_responsibility": ("P51 授权缺覆盖门、同步门循环论证 —— "
                                              "本轮已补：覆盖门 + 独立实测同步门"),
        },
        "built": {
            "builder": "core/captions.py::build_cues_from_audio",
            "rule_version": "p52-1-audio-anchor-v1",
            "signal_source": "每景实际音频切片 seg/<scene>.wav 的 silencedetect(-30dB,d=0.05)",
            "runs": {"scenes": runs["scene_count"], "runs_total": sum(
                len(v) for v in runs["runs_by_scene"].values()),
                "speech_total_s": runs["total_speech_s"]},
            "artifact": "output/phase52_voice/runs_by_scene.json",
        },
        "gates_passed": {
            "gate": "tests/caption_coverage_test.py 4/4 PASS",
            "thresholds": cov["thresholds"],
            "after": {"coverage": cov["coverage"], "median_dur_s": cov["median_dur_s"],
                      "clamp_cues": cov["clamp_cues"],
                      "sync_cover": cov["sync_cover"], "cues": cov["cues"]},
            "before_fixture_F8": cov["before_fixture_F8"],
        },
        "blocking_defect": {
            "what": "**写盘前的 cue 列表本身就已错乱**（构建器内联测试却正确）",
            "evidence_raw_ass_head": raw[:3],
            "evidence_cuedump": {
                "file": "_cuedump_<task>.json（art_dir，写盘前转储）",
                "cue_source": "audio_anchor",
                "cues": 111,
                "first5": [
                    {"index": 0, "segment_index": 12, "scene_id": "P04_2",
                     "start": 0.0, "end": 6.801, "dur": 6.801},
                    {"index": 1, "segment_index": 28, "scene_id": "P08_2",
                     "start": 6.801, "end": 4.778, "dur": -2.023},
                    {"index": 2, "segment_index": 30, "scene_id": "P08_4",
                     "start": 4.778, "end": 5.326, "dur": 0.548},
                ],
            },
            "observed_anomalies": [
                "**cue 未按 start 排序**（index0=P04_2、index1=P08_2、index2=P08_4 —— 段序错乱）"
                " ⇒ 我在 `build_cues_from_audio` 末尾的**排序与排他**那段**没有生效**",
                "`end` 字段装的是**时长**（6.801 / 4.778 / 5.326），不是绝对终点"
                " ⇒ 于是 `to_ass` 写出 `start=上条 end`、`end=下条时长` 的交错模式",
                "出现 **dur = -2.023（负时长）** —— 排序/排他一旦生效不可能产生负值",
            ],
            "isolated_contradiction": (
                "**同一个构建器**在**内联测试**里输出正确"
                "（111 条、median 5.720s、max 同时活跃 1、首条 0.196–5.529），"
                "但在**渲染路径内**输出未排序、`end` 为时长。"
                "指向**agent 内对该函数的调用路径与内联测试不等价**"
                "（最可能：传入的 `segment_windows` / `segments` 形状不同，"
                "使窗口分支走入异常路径，或**旧字节码缓存**）—— **本轮未定位到底**。"),
            "ruled_out": [
                "`to_ass()` 为**纯格式化**（逐字核对：逐 cue 直接取 start/end 字段，"
                "无重排、无时移）；ASS 的 `Format` 行确为 `Layer, Start, End, …`",
                "cue 数 **111** 与音频锚定路径一致（legacy 161 / 词级 100）",
                "`cues` 在 agent 内**只被赋值一次**（L2043），无二次覆盖",
            ],
            "not_located": True,
            "honest_note": "**未定位到最终破坏点**；不编造解释。已把转储探针留在代码里，"
                           "下一轮可直接比对。",
        },
        "delivery_candidates_unchanged": ["F", "F2", "F3", "F4", "F5", "F6",
                                          "F7", "F7.1", "F8"],
        "F9": "未登记",
        "zero_promotion": True,
        "next_round_method": (
            "同 P48 成功做法：在 `to_ass(cues…)` **之前**把 `cues` 转储 JSON，"
            "与「同一输入直接调 `build_cues_from_audio`」逐字段 diff ⇒ "
            "即可区分『构建器在 agent 内被不同参数调用』还是『写入前被改写』。"),
        "budget": {"llm_usd": 0.0, "network": 0, "renders": 1},
    }
    p = L / "p52_failclosed.json"
    p.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    print("Phase 52 落账（FAIL-CLOSED，未登记 F9）")
    print("  已建成：音频锚定构建器 + 36 景/733 语音运行")
    print("  门 4/4 PASS：覆盖 {:.1%}（F8 {:.1%}）| median {:.2f}s（F8 {:.1f}s）| "
          "clamp {} （F8 {}）| 同步 {:.1%}".format(
              cov["coverage"], cov["before_fixture_F8"]["coverage"],
              cov["median_dur_s"], cov["before_fixture_F8"]["median_dur_s"],
              cov["clamp_cues"], cov["before_fixture_F8"]["clamp_cues"],
              cov["sync_cover"]))
    print("  阻断：烧录 ASS 时间轴错乱（start=上条 end / end=下条时长 / 文本与区间不符）")
    print("  已排除：to_ass 纯格式化；cue 数与音频锚定路径一致（111）")
    print("  未定位到破坏点 —— 如实登记，不编造")
    print("-> " + str(p.relative_to(R)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
