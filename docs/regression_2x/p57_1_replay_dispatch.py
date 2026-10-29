# -*- coding: utf-8 -*-
"""Phase 57 / P57-1：**生产 cue 分发路径重放**（dump 实参确认 + 修复前后对照）。

授权书 §1：以 F10.1 烧录 ASS 的 105-cue-178s 签名为指引，dump 生产路径实参确认。
做法：用 F10.1 沙箱 `p_3e9292101f10` 的**真实生产输入**（script/voice 产物、
words_manifest、runs_by_scene）直接调 `EditingAgent._narration_args` ——
即渲染时真正走到的 cue 构建函数 —— 并解析其写出的烧录 ASS，
给出签名（cue 数 / 跨度 / median / max_end）。

任务 id 按阶段命名（`t_p57dryb`=before / `t_p57drya`=after），产物文件名带 task_id，
**不触碰** F10.1 证据（`_captions_t_158db818a8b3.ass` / `_cuedump_t_158db818a8b3.json`）。

运行: python docs/regression_2x/p57_1_replay_dispatch.py [before|after]
"""
from __future__ import annotations

import json
import pathlib
import re
import statistics
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")

P = "p_3e9292101f10"
VOICE_ART = R / "projects" / P / "artifacts" / "a_19df682cbaa4.json"
SCRIPT_ART = R / "projects" / P / "artifacts" / "a_aec6a870612e.json"


class Eng:
    """最小引擎桩：真实项目目录 + 空 config（母带链/BGM 关闭，等价 F10.1 渲染口径）。"""
    config = None

    def __init__(self, pdir: pathlib.Path):
        self._p = pdir

    def project_dir(self, pid):
        return self._p


def parse_ass(p: pathlib.Path):
    txt = p.read_text(encoding="utf-8")
    rows = []
    for m in re.finditer(r"Dialogue: 0,([0-9:.]+),([0-9:.]+),", txt):
        def sec(ts):
            h, mm, rest = ts.split(":")
            return int(h) * 3600 + int(mm) * 60 + float(rest)
        rows.append((sec(m.group(1)), sec(m.group(2))))
    return rows


def signature(rows):
    durs = [round(e - s, 3) for s, e in rows]
    span = round(max(e for _, e in rows) - min(s for s, _ in rows), 3)
    ov = sum(1 for i in range(1, len(rows)) if rows[i][0] < rows[i - 1][1] - 1e-9)
    return {"cues": len(rows), "span_s": span,
            "first_start": round(min(s for s, _ in rows), 3),
            "max_end": round(max(e for _, e in rows), 3),
            "median_dur": round(statistics.median(durs), 3) if durs else None,
            "min_dur": round(min(durs), 3) if durs else None,
            "max_dur": round(max(durs), 3) if durs else None,
            "overlap_pairs": ov,
            "d_1s_clamped": sum(1 for d in durs if abs(d - 1.0) <= 0.1)}


def main() -> int:
    mode = (sys.argv[1] if len(sys.argv) > 1 else "before").lower()
    tid = "t_p57dryb" if mode == "before" else "t_p57drya"
    from video_studio.agents.editing.agent import EditingAgent

    script = json.loads(SCRIPT_ART.read_text(encoding="utf-8"))
    voice = json.loads(VOICE_ART.read_text(encoding="utf-8"))
    # **F10.1 真实生产形状**：voice 产物**不带** `audio_time_base_s` 字段
    # ⇒ run() 的 Duration Contract v2 门不启用 ⇒ run() 传给 _narration_args 的是
    # `segment_windows=[] / audio_time_base_s=None`（非 v2 派生窗）。
    # 重放必须与 run() 同形状，否则复现不了 105-cue-178s 签名。
    has_v2 = bool(voice.get("audio_time_base_s"))
    v2w = []
    print("mode={} | 景 {} | voice.audio_time_base_s={} ⇒ v2 门={} | "
          "segment_windows=[] audio_time_base_s=None（run() 真实形状）".format(
              mode, len(script["segments"]), voice.get("audio_time_base_s"), has_v2))

    eng = Eng(R / "projects" / P)
    args = EditingAgent._narration_args(
        eng, {"project_id": P, "task_id": tid}, script, "1920x1080", 25,
        {"codec": "libx264"}, narration_audio="media/voice/narration_v65.mp3",
        timeline=[], segment_windows=(v2w or None), audio_time_base_s=None)
    ass = R / "projects" / P / "artifacts" / ("_captions_{}.ass".format(tid))
    dump = R / "projects" / P / "artifacts" / ("_cuedump_{}.json".format(tid))
    print("写出: {} ({}B) | dump: {}".format(
        ass.name, ass.stat().st_size, dump.is_file()))
    if dump.is_file():
        d = json.loads(dump.read_text(encoding="utf-8"))
        print("dump.cue_source = {} | dump.cues = {}".format(
            d.get("cue_source"), d.get("cues")))
        if d.get("first5"):
            print("dump.cue[0..2].source = {}".format(
                [c.get("source") for c in d["first5"][:3]]))
    sig = signature(parse_ass(ass))
    print("签名: {}".format(json.dumps(sig, ensure_ascii=False)))
    ref = {"cues": 105, "span_s": 178.263, "max_end": 178.363}
    hit = (sig["cues"] == ref["cues"] and abs(sig["span_s"] - ref["span_s"]) < 0.5)
    print("F10.1 签名（105-cue-178s）复现: {}".format("是" if hit else "否"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
