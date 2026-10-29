# -*- coding: utf-8 -*-
"""P60-1：**语义节拍计划 v2 + 解释动画渲染**（解释级可视化生成器 MVP 的自主生成案例）。

上一轮（2026-10-17 早）遗留缺陷的修正：
  · 旧 beat_plan.json 窗口 = 48.6s，而第二期 P01_1..P01_3 真实语音 = 61.74s
    （EP2 script artifact a_b2e4a14ac1ba 的 audio_window_s），⇒ F17 渲染被
    NARRATION_INCOMPLETE fail-closed 拦下。本脚本以**真实景窗**重建。
  · 旧计划未随 `B_P60_full_animation.mp4` 留档（不可审计）。本脚本把计划、
    cue 来源、词锚定证据全部落盘。

语义映射的来源（诚实的边界）：
  · cue 边界 = 第二期烧录 ASS 的真实句界（WordBoundary 派生），非本脚本猜测；
  · 冲突闪现/绿色跑完等**词锚** = words_manifest 真实词时刻
    （说「相邻…不一样」时闪现冲突，说「跑完」时清单收束），非关键词模板套用；
  · 每拍的 semantic_tag / explanation_goal / expected_understanding 为显式标注，
    由 `core/explain_viz.validate_beat_plan` 对照 cue 逐拍校验（不符 ⇒ 拒绝渲染）。
运行: python docs/regression_2x/p60_1_beats_anim.py
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
import time

R = pathlib.Path(r"C:\mp4agent\video-studio").resolve()
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")

EP2_PID = "p_2eac65565600"
EP2_ASS = R / "projects" / EP2_PID / "artifacts" / "_captions_t_ee63a79fe9f4.ass"
EP2_WORDS = R / "projects" / EP2_PID / "media" / "voice" / "words_manifest.json"
OUT = R / "output" / "p60_ep2"
WINDOW_END = 61.74          # P01_1..P01_3 真实语音窗（EP2 script audio_window_s）


def sec(ts: str) -> float:
    h, mm, rest = ts.split(":")
    return int(h) * 3600 + int(mm) * 60 + float(rest)


def main() -> int:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)

    # ---- 1. 真实 cue：第二期烧录 ASS，取 [0, 61.74) 的 10 句 ----
    txt = EP2_ASS.read_text(encoding="utf-8")
    pat = re.findall(r"Dialogue: 0,([0-9:.]+),([0-9:.]+),[^,]*,[^,]*,[^,]*,[^,]*,"
                     r"[^,]*,[^,]*,(.*)", txt)
    cues = [{"start": round(sec(a), 3), "end": round(sec(b), 3),
             "text": t.replace("\\N", "")}
            for a, b, t in pat if sec(a) < WINDOW_END]
    assert len(cues) == 10, "期望 10 句，得 {}".format(len(cues))
    (OUT / "cues_p01_v2.json").write_text(
        json.dumps({"schema": "p60-cues-v2", "source": str(EP2_ASS.relative_to(R)),
                    "window": [0.0, WINDOW_END], "cues": cues},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    print("cue: 10 句（EP2 ASS 真实句界）0.1 → {:.2f}s".format(cues[-1]["end"]))

    # ---- 2. 词锚：从 words_manifest 取真实词时刻 ----
    man = json.loads(EP2_WORDS.read_text(encoding="utf-8"))
    words = [p_ for p_ in man["paras"] if p_["para"] == "P01"][0]["words"]
    words = [w_ for w_ in words if w_["start_s"] < WINDOW_END]

    def find(text, lo, hi):
        """词锚 = 连续 token 拼接命中（TTS 分词不等价于词，如「不|一样」）。"""
        seq = [w_ for w_ in words if lo <= w_["start_s"] < hi]
        for i in range(len(seq)):
            acc, j = "", i
            while j < len(seq) and len(acc) < len(text):
                acc += seq[j]["text"]
                j += 1
            if acc == text:
                return {"text": text, "start_s": seq[i]["start_s"],
                        "dur_s": round(seq[j - 1]["start_s"] + seq[j - 1]["dur_s"]
                                       - seq[i]["start_s"], 3)}
        raise AssertionError("词锚未命中: {} in [{:.2f},{:.2f})".format(text, lo, hi))

    w_adj = find("相邻", 5.25, 14.24)          # 「相邻的两个区域颜色不一样」
    w_diff = find("不一样", 5.25, 14.24)
    w_four = find("四种颜色", 5.25, 14.24)
    w_done = find("跑完", 54.92, WINDOW_END)   # 「或者跑到跑完」
    anchors = {"四种颜色": w_four, "相邻": w_adj, "不一样": w_diff, "跑完": w_done}
    print("词锚:", {k_: round(v_["start_s"], 2) for k_, v_ in anchors.items()})

    conflict_at = round(max(w_adj["start_s"] - 0.15, 5.25), 3)
    conflict_end = round(min(w_diff["start_s"] + w_diff["dur_s"] + 0.20, 14.24), 3)

    # ---- 3. 节拍计划 v2（11 拍，覆盖 [0.1, 61.74]，拍界=句界，无空隙）----
    starts = [c_["start"] for c_ in cues] + [WINDOW_END]
    b = lambda i: starts[i]                                                    # noqa: E731
    P = lambda a, b_=None: a if b_ is None else a + "/" + b_                   # noqa: E731
    beats = [
        {"start": b(0), "end": b(1), "template": "timeline",
         "params": {"marker": "1977", "marker_u": 0.30,
                    "caption": "Appel 和 Haken 宣布：四色定理证出来了"},
         "narration": cues[0]["text"], "semantic_tag": "事件时间锚点",
         "explanation_goal": "把观众注意力钉在 1977 这个宣布时刻，建立故事起点",
         "expected_understanding": "记住起点：1977 年 Appel-Haken 宣布证明"},
        {"start": b(1), "end": b(2), "template": "coloring",
         "params": {"map_seed": 20261016, "cols": 5, "rows": 2,
                    "conflict_at": conflict_at, "conflict_end": conflict_end,
                    "conflict_pair": [2, 3],
                    "caption": "任何一张平面地图：最多 4 种颜色，相邻颜色不同"},
         "narration": cues[1]["text"], "semantic_tag": "约束可视化+冲突修正",
         "explanation_goal": P("把「四色」和「相邻必须不同色」变成看得见的逐块着色；"
                               "在词锚 {:.2f}s（说「相邻」）闪现同色冲突，随后修正为合法四色".format(conflict_at)),
         "expected_understanding": "看到地图逐块上色、相邻颜色不同；冲突出现后被修正"},
        {"start": b(2), "end": b(3), "template": "counting",
         "params": {"value_text": "1852", "caption": "这问题，1852 年就有人提出"},
         "narration": cues[2]["text"], "semantic_tag": "历史时间锚点",
         "explanation_goal": "把问题历史推到 1852，与开头 1977 形成时间差",
         "expected_understanding": "意识到问题已有 125 年历史"},
        {"start": b(3), "end": b(4), "template": "counting",
         "params": {"value_text": "120+ 年", "caption": "没人搞定。几代数学家，从年轻干到退休"},
         "narration": cues[3]["text"], "semantic_tag": "时间跨度量化",
         "explanation_goal": "把「没人搞定」变成可感知的时间跨度",
         "expected_understanding": "感受到 120 年的分量"},
        {"start": b(4), "end": b(5), "template": "hold",
         "params": {"caption": "他们走的路，是一场豪赌"},
         "narration": cues[4]["text"], "semantic_tag": "叙事转折（无动画拍）",
         "explanation_goal": "短句停顿制造转折；文字卡承载判断句",
         "expected_understanding": "预期下文解释「赌」在哪里"},
        {"start": b(5), "end": b(6), "template": "collapse",
         "params": {"phase1_end": 0.35, "mini_maps": 24,
                    "bins": ["构型 A", "构型 B", "构型 C"],
                    "caption1": "人手算不完：无穷多张地图",
                    "caption": "归约成有限多种构型，交给计算机一种一种跑"},
         "narration": cues[5]["text"], "semantic_tag": "归约概念演示",
         "explanation_goal": "前 35% 展示无穷地图网格，随后坍缩为 3 个构型堆——把「无穷归约为有限」画出来",
         "expected_understanding": "理解归约：无穷情况 → 有限构型 → 计算机逐一种"},
        {"start": b(6), "end": b(7), "template": "hold",
         "params": {"caption": "纸笔上的硬活：说服所有人，一张都没漏"},
         "narration": cues[6]["text"], "semantic_tag": "证明负担（无动画拍）",
         "explanation_goal": "强调归约证明本身的工作量",
         "expected_understanding": "理解「说服所有人」是证明的一部分"},
        {"start": b(7), "end": b(8), "template": "checklist",
         "params": {"caption": "检查那一头是机器的活", "items": 30,
                    "item_pattern": "config {:03d} ... OK", "items_per_s": 12,
                    "done_text": "人手：做不动"},
         "narration": cues[7]["text"], "semantic_tag": "机器检查可视化",
         "explanation_goal": "用清单扫过展示「逐条检查」的机械性；终态对照人手的不可能",
         "expected_understanding": "看清机器检查的逐条性与规模"},
        {"start": b(8), "end": b(9), "template": "hold",
         "params": {"caption": "手指头，早就酸得抬不起来了"},
         "narration": cues[8]["text"], "semantic_tag": "情绪点·人肉代价（无动画拍）",
         "explanation_goal": "短句停顿承载情绪：人肉检查的身体代价",
         "expected_understanding": "共情「人做不动」"},
        {"start": b(9), "end": 59.50, "template": "checklist",
         "params": {"caption": "计算机不懂数学：照着规则一条条跑", "items": 24,
                    "item_pattern": "case {:04d} ... run", "items_per_s": 12,
                    "done_text": "跑到出错"},
         "narration": "计算机不懂数学，它做的是照着规则一条条跑，跑到出错。",
         "semantic_tag": "机械执行过程",
         "explanation_goal": "以更快的逐条扫描演示程序执行的机械性，终态停在「跑到出错」分支",
         "expected_understanding": "理解程序只是照规则跑，出错即停"},
        {"start": 59.50, "end": WINDOW_END, "template": "checklist",
         "params": {"caption": "或者——跑到跑完", "items": 20,
                    "item_pattern": "case {:04d} ... OK", "items_per_s": 14,
                    "done_text": "跑完 · 没报错"},
         "narration": "或者跑到跑完。",
         "semantic_tag": "情绪点·如释重负",
         "explanation_goal": P("在词锚 {:.2f}s（说「跑完」）附近绿色清单收束 + 「没报错」终态，"
                               "交付如释重负的情绪节拍".format(w_done["start_s"])),
         "expected_understanding": "与上一拍的「出错」分支对照，收到「跑完」的释然"},
    ]
    plan = {"schema": "p60-beat-plan-v2",
            "provenance": {"cue_source": "EP2 ASS (WordBoundary 派生句界)",
                           "word_anchor_source": "EP2 words_manifest (p58-7)",
                           "scene_windows_source":
                               "EP2 script artifact a_b2e4a14ac1ba (audio_window_s)",
                           "window_basis": "P01_1..P01_3 真实语音 61.74s"},
            "window": [0.0, WINDOW_END], "fps": 25, "canvas": [1920, 1080],
            "style": {"dark": True, "font_dir": "C:/Windows/Fonts/"},
            "seed": 20261016, "beats": beats,
            "word_anchors": {k_: {"text": v_["text"], "start_s": v_["start_s"],
                                  "dur_s": v_["dur_s"]}
                             for k_, v_ in anchors.items()}}
    (OUT / "beat_plan_v2.json").write_text(
        json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    print("beat_plan_v2.json: 11 拍，冲突词锚 {:.2f}-{:.2f}s".format(
        conflict_at, conflict_end))

    # ---- 4. 模块校验 + 渲染（失败即退出，不产出动画）----
    from video_studio.core import explain_viz as EV
    errs, proj = EV.validate_beat_plan(plan, cues)
    if errs:
        print("**beat plan 校验 FAIL-CLOSED**:", errs)
        return 1
    print("校验: 11/11 拍通过（旁白引用逐拍比对 cue）")
    anim = OUT / "B_P60_explainer_v2.mp4"
    ev = EV.render_animation(plan, cues, anim, ffmpeg=str(R / "bin/ffmpeg.exe"),
                             fps=25)
    ev["word_anchors"] = plan["word_anchors"]
    ev["validation_errors"] = errs
    ev["wall_s"] = round(time.time() - t0, 1)
    (OUT / "render_evidence_v2.json").write_text(
        json.dumps(ev, ensure_ascii=False, indent=1), encoding="utf-8")
    print("渲染: ok={} frames={} {:.1f}s sha={}".format(
        ev["ok"], ev.get("frames"), ev["wall_s"], (ev.get("output_sha256") or "")[:12]))
    return 0 if ev["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
