# -*- coding: utf-8 -*-
"""P60：解释级可视化生成器——输入输出契约 / 异常 / 可复现性 独立测试。
运行: python tests/explain_viz_test.py
"""
from __future__ import annotations

import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio").resolve()
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import explain_viz as EV                                   # noqa: E402

TMP = R / "output" / "p60_test"
TMP.mkdir(parents=True, exist_ok=True)
PASS, FAIL = [], []
CUES = [{"start": 0.0, "end": 5.25, "text": "1977 年，Appel 和 Haken 宣布四色定理证出来了。"},
        {"start": 5.25, "end": 14.24, "text": "任何一张平面地图，最多用四种颜色，相邻不一样。"},
        {"start": 14.24, "end": 17.18, "text": "这问题 1852 年就有人提出。"}]


def check(name, ok, detail=None):
    (PASS if ok else FAIL).append(name)
    print("{}  {} {}".format("PASS" if ok else "FAIL", name,
                             "" if ok else json.dumps(detail, ensure_ascii=False, default=str)[:240]))


def plan(beats, window=(0.0, 17.18)):
    return {"schema": "p60-beat-plan-test", "window": list(window),
            "canvas": [640, 360], "style": {"dark": True},
            "beats": [dict(b) for b in beats]}


B_TIMELINE = {"start": 0.0, "end": 5.25, "template": "timeline",
              "params": {"marker": "1977", "marker_u": 0.3, "caption": "Appel 和 Haken 宣布"},
              "narration": "1977 年，Appel 和 Haken 宣布",
              "semantic_tag": "事件时间锚点", "explanation_goal": "建立时间锚点",
              "expected_understanding": "记住起点是 1977"}
B_COLOR = {"start": 5.25, "end": 14.24, "template": "coloring",
           "params": {"map_seed": 20261015, "cols": 5, "rows": 2,
                      "conflict_at": 10.9, "conflict_end": 12.1, "conflict_pair": [2, 3]},
           "narration": "任何一张平面地图，最多用四种颜色",
           "semantic_tag": "约束可视化", "explanation_goal": "展示四色着色约束：相邻必须不同色",
           "expected_understanding": "看到逐块着色且相邻不同色"}


def main() -> int:
    # ---- 契约：合法计划 ----
    errs, proj = EV.validate_beat_plan(plan([B_TIMELINE, B_COLOR]), CUES)
    check("T1 合法双拍计划校验通过", not errs and len(proj) == 2, errs)

    # ---- 异常：未知模板 ----
    bad = plan([{"start": 0.0, "end": 5.0, "template": "hologram",
                 "explanation_goal": "x"}])
    errs2, _ = EV.validate_beat_plan(bad, CUES)
    check("T2 未知模板被拒", any("未知模板" in x for x in errs2), errs2)

    # ---- 异常：解释节拍缺 goal ----
    b = dict(B_COLOR, explanation_goal="")
    errs3, _ = EV.validate_beat_plan(plan([b]), CUES)
    check("T3 解释节拍缺 explanation_goal 被拒",
          any("explanation_goal" in x for x in errs3), errs3)

    # ---- 异常：节拍间隙 >3s ----
    g1 = dict(B_TIMELINE, start=0.0, end=3.0)
    g2 = dict(B_COLOR, start=10.0, end=14.24)
    errs4, _ = EV.validate_beat_plan(plan([g1, g2]), CUES)
    check("T4 节拍间 >3s 未解释空隙被拒", any("未解释空隙" in x for x in errs4), errs4)

    # ---- 异常：旁白引用与 cue 不符 ----
    wrong = dict(B_TIMELINE, narration="完全无关的一句话呀")
    errs5, _ = EV.validate_beat_plan(plan([wrong]), CUES)
    check("T5 旁白引用与 cue 不符被拒", any("旁白引用" in x for x in errs5), errs5)

    # ---- 可复现性：同输入两次渲染 sha 一致 ----
    p1 = TMP / "repro_1.mp4"
    p2 = TMP / "repro_2.mp4"
    r1 = EV.render_animation(plan([B_TIMELINE, B_COLOR]), CUES, p1,
                             ffmpeg=str(R / "bin/ffmpeg.exe"), fps=10)
    r2 = EV.render_animation(plan([B_TIMELINE, B_COLOR]), CUES, p2,
                             ffmpeg=str(R / "bin/ffmpeg.exe"), fps=10)
    check("T6 同输入两次渲染 sha 一致",
          r1["ok"] and r2["ok"] and r1["output_sha256"] == r2["output_sha256"],
          {"r1": r1.get("output_sha256", "")[:12], "r2": r2.get("output_sha256", "")[:12]})

    # ---- 回退：非法计划不产出文件 ----
    p3 = TMP / "fallback_should_not_exist.mp4"
    bad_plan = plan([{"start": 0.0, "end": 5.0, "template": "hologram",
                      "explanation_goal": "x"}])
    r3 = EV.render_animation(bad_plan, CUES, p3, ffmpeg=str(R / "bin/ffmpeg.exe"), fps=10)
    check("T7 非法计划 ⇒ ok=False 且不产出文件",
          (not r3["ok"]) and not p3.exists(), r3.get("fallback"))

    # ---- 着色正确性：相邻不同色（性质测试，3 个 seed）----
    ok_cols = True
    for seed in (1, 20261015, 777):
        rnd = EV.Renderer({"style": {"dark": True, "palette": None},
                           "canvas": [640, 360]})
        pr = {"map_seed": seed, "cols": 5, "rows": 2}
        regions, colors, adj = rnd._map_spec(pr)
        regions = [(rid, colors[rid], poly) for rid, col, poly in regions]
        for (rid, col, poly) in regions:
            for rid2 in adj.get(rid, []):
                if rid < rid2 and colors[rid] == colors[rid2]:
                    ok_cols = False
    check("T8 着色分配：相邻区域不同色（3 seed 性质测试）", ok_cols)

    # ---- 渲染级像素校验：着色帧上区域质心颜色 = 期望填充（可抓解包/坐标类缺陷）----
    r = EV.Renderer({"style": {"dark": True}, "canvas": [640, 360]})
    beat = dict(B_COLOR, start=5.25, end=14.24)
    fr = r.frame(beat, 13.0)          # u≈0.87 ⇒ 全部 10 块已着色
    regions, colors, adj = r._map_spec(B_COLOR["params"])
    px_ok = True
    for rid, _c, poly in regions[:5]:
        cx = int(sum(p_[0] for p_ in poly) / 4)
        cy = int(sum(p_[1] for p_ in poly) / 4)
        want = r.pal[colors[rid] % 4]
        got = fr.getpixel((cx, cy))
        if max(abs(a - b_) for a, b_ in zip(got, want)) > 12:
            px_ok = False
    check("T9 着色帧像素：区域质心 = 四色调色板色", px_ok)

    # ---- 真实交付计划：beat_plan_v2 对真实 cue 的契约校验 ----
    bp = R / "output" / "p60_ep2" / "beat_plan_v2.json"
    cp = R / "output" / "p60_ep2" / "cues_p01_v2.json"
    if bp.is_file() and cp.is_file():
        plan_v2 = json.loads(bp.read_text(encoding="utf-8"))
        cues_v2 = json.loads(cp.read_text(encoding="utf-8"))["cues"]
        errs_v, proj_v = EV.validate_beat_plan(plan_v2, cues_v2)
        goals = all(b_.get("explanation_goal") and b_.get("semantic_tag")
                    for b_ in proj_v)
        check("T10 真实 beat_plan_v2：11 拍校验通过且逐拍带解释目标",
              (not errs_v) and len(proj_v) == 11 and goals,
              errs_v[:2])
    else:
        check("T10 真实 beat_plan_v2：交付物缺失（先运行 p60_1_beats_anim.py）",
              False, str(bp))

    print()
    print("=" * 70)
    print("explain_viz_test: {} PASS / {} FAIL".format(len(PASS), len(FAIL)))
    print("=" * 70)
    (R / "docs/regression_2x/logs/p60_explain_viz_test.json").write_text(
        json.dumps({"pass": len(PASS), "fail": len(FAIL)}, ensure_ascii=False),
        encoding="utf-8")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
