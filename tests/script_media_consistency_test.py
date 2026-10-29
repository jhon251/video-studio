# -*- coding: utf-8 -*-
"""Phase 33 / P33-3 —— **脚本 ↔ 音频 ↔ 字幕 一致性门**。

动机（监理指出的空档）：此前没有任何门能保证"**屏幕上念的字** == **脚本里写的字**"。
本片谱系（v4.1 稿）与在片音频（v3/V20 谱系）长期**不是同一份文本**：v4.1 从未入片，
而字幕由脚本生成、音频来自旧谱系 ⇒ **文本与声音可能整片错配**且无门可察。

本门把三者的**同一性**写成运行前写死的断言：
  · **C1** 逐段：字幕 cue 文本（**空白规整后**）== 脚本 narration；且 cue 文本**可无损重建**整段；
  · **C2** 逐段：音频产物的 `text_sha256` == 脚本 `narration_sha256`（**同一份文本**被合成）；
  · **C3** 整片：Σ(cue 文本) 的规范化哈希集合与 Σ(narration) 一致（不漏段、不串段）；
  · **C4** 时基：`Σ实测语音 + Σpause == 整条旁白实测`（±0.1s，trailing 由 apad 承担）；
  · **C5** 覆盖：每段 cue 的展示时间**落在该段音频窗口内**（不越界、不跨段）；
  · **C6** 完整性：全部段 `status ∈ {SUCCESS, REUSED}`（任一段失败 ⇒ fail-closed）。

输入（真实产物，缺失即 SKIP 并如实标注，不假装通过）：
  · `output/phase27_script_sandbox/script_p27_v41_40seg.json`
  · `output/phase33_voice/voice_output_v41.json`
  · `output/phase33_voice/timebase_v41.json`
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import captions as CAP                                    # noqa: E402

SCRIPT = ROOT / "output/phase27_script_sandbox/script_p27_v41_40seg.json"
VOICE = ROOT / "output/phase33_voice/voice_output_v41.json"
TB = ROOT / "output/phase33_voice/timebase_v41.json"

PASS, FAIL, SKIP = [], [], []
TOL_TB = 0.1          # 运行前写死：时基一致性容差
TOL_EDGE = 0.6        # 运行前写死：cue 末端与窗口末端的允许差（尾部静音/片尾）


def check(name, ok, detail=None):
    (PASS if ok else FAIL).append(name)
    print("{}  {} {}".format("PASS" if ok else "FAIL", name,
                             "" if ok else json.dumps(detail, ensure_ascii=False,
                                                      default=str)[:300]))
    return bool(ok)


def norm(s):
    """空白规整（折叠全部空白与换行）—— 断言的比较口径。"""
    return re.sub(r"\s+", "", s or "")


def h12(t):
    return hashlib.sha256((t or "").encode("utf-8")).hexdigest()[:12]


missing = [str(p.relative_to(ROOT)) for p in (SCRIPT, VOICE, TB) if not p.is_file()]
if missing:
    print("SKIP  真实产物不在场：{}".format(missing))
    print("      （本门需 P33-3 的配音产物；未产出 ⇒ 不计通过）")
    SKIP.append("ARTIFACTS_ABSENT")
else:
    script = json.loads(SCRIPT.read_text(encoding="utf-8"))
    voice = json.loads(VOICE.read_text(encoding="utf-8"))
    tb = json.loads(TB.read_text(encoding="utf-8"))
    segs = script["segments"]
    vsegs = voice["segments"]
    wins = tb["windows"]

    # ---------------- C6 完整性（先判，失败即整体 fail-closed） ----------------
    bad_status = [v["scene_id"] for v in vsegs if v.get("status") not in ("SUCCESS", "REUSED")]
    check("C6 全段配音成功（status ∈ SUCCESS/REUSED；任一段失败即 fail-closed）",
          not bad_status and len(vsegs) == len(segs),
          {"bad": bad_status, "n_voice": len(vsegs), "n_script": len(segs)})

    # ---------------- C2 音频文本哈希 == 脚本 narration 哈希 ----------------
    c2_bad = []
    for s, v in zip(segs, vsegs):
        want = s.get("narration_sha256") or hashlib.sha256(
            (s.get("narration") or "").encode("utf-8")).hexdigest()
        if v.get("text_sha256") != want:
            c2_bad.append({"scene": s.get("scene_id"), "voice": (v.get("text_sha256") or "")[:12],
                           "script": want[:12]})
    check("C2 逐段：被合成的文本 sha256 == 脚本 narration_sha256（音频来自**同一份文本**）",
          not c2_bad, c2_bad[:4])

    # ---------------- C1 字幕 cue 文本 == narration ----------------
    wlist = [{"start_s": w["start_s"], "end_s": w["end_s"]} for w in wins]
    cues = CAP.build_cues([{"narration": s.get("narration") or "", "index": i}
                           for i, s in enumerate(segs)], windows=wlist)
    by_seg = {}
    for c in cues:
        by_seg.setdefault(c["segment_index"], []).append(c)
    c1_bad = []
    for i, s in enumerate(segs):
        joined = "".join(c["text"] for c in by_seg.get(i, []))
        if norm(joined) != norm(s.get("narration")):
            c1_bad.append({"scene": s.get("scene_id"), "cue": h12(joined),
                           "script": h12(s.get("narration"))})
    check("C1 逐段：字幕 cue 文本（空白规整）== 脚本 narration（可无损重建）",
          not c1_bad, c1_bad[:4])

    # ---------------- C3 整片文本守恒（不漏段/不串段） ----------------
    cue_all = norm("".join(c["text"] for c in cues))
    scr_all = norm("".join(s.get("narration") or "" for s in segs))
    check("C3 整片：Σ(cue 文本) == Σ(narration)（字符级，空片规整后逐字相等）",
          len(cue_all) == len(scr_all) and h12(cue_all) == h12(scr_all),
          {"cue_chars": len(cue_all), "script_chars": len(scr_all),
           "cue_h": h12(cue_all), "script_h": h12(scr_all)})

    # ---------------- C4 时基：Σ实测 + Σpause == 整条旁白实测 ----------------
    a = tb.get("assertion_frozen_before_render") or {}
    exp = float(tb.get("sum_measured_speech_s") or 0) + float(tb.get("sum_pause_s") or 0)
    meas = float(tb.get("narration_measured_s") or 0)
    check("C4 时基：Σ实测语音 {:.3f} + Σpause {:.3f} == 旁白实测 {:.3f}（±{}s；trailing 由 apad）"
          .format(float(tb.get('sum_measured_speech_s') or 0),
                  float(tb.get('sum_pause_s') or 0), meas, TOL_TB),
          abs(meas - exp) <= TOL_TB, {"expected": round(exp, 3), "measured": meas,
                                      "delta": round(meas - exp, 3), "frozen": a})

    # ---------------- C5 cue 落在本段**声明窗口**内 ----------------
    # 口径 = **冻结 PI-5 政策**（见 core/narration.subtitle_alignment）：
    #   ① 字幕不得**早于窗口起点**；② 字幕不得**越过窗口结束**（末段窗口**含 trailing**，
    #      故末段 cue 延入 trailing 是既有设计，不判违规）。
    # 段窗口由 build_cues 依 `windows` 派生 ⇒ 本门本质是"字幕确实按同一份窗口表布局"。
    c5_bad = []
    for i, w in enumerate(wins):
        cs = by_seg.get(i, [])
        if not cs:
            c5_bad.append({"scene": w["scene_id"], "why": "no_cue"})
            continue
        if cs[0]["start"] < w["start_s"] - 0.05:
            c5_bad.append({"scene": w["scene_id"], "why": "cue_starts_before_window",
                           "cue": cs[0]["start"], "win": w["start_s"]})
        if cs[-1]["end"] > w["end_s"] + 0.05:
            c5_bad.append({"scene": w["scene_id"], "why": "cue_ends_after_window",
                           "cue": cs[-1]["end"], "win": w["end_s"]})
    nrt = float(tb.get("audio_time_base_s") or 0)
    if cues and cues[-1]["end"] > nrt + 0.05:
        c5_bad.append({"why": "cue_beyond_narration_end", "cue": cues[-1]["end"],
                       "narration_end": nrt})
    check("C5 每段 cue 落在**该段声明窗口**内（不早于起点、不越过窗口/旁白结束）",
          not c5_bad, c5_bad[:4])

print()
print("=" * 70)
print("script_media_consistency_test: {} PASS / {} FAIL{}".format(
    len(PASS), len(FAIL), " / {} SKIP".format(len(SKIP)) if SKIP else ""))
if FAIL:
    print("FAILED:", json.dumps(FAIL, ensure_ascii=False))
print("=" * 70)
sys.exit(1 if FAIL else 0)
