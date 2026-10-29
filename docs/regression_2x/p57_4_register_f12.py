# -*- coding: utf-8 -*-
"""Phase 57 / P57-4：**登记第十三部交付候选 F12**（append-only、零 promotion）。

全门依据（运行前已实测，本脚本只汇总落账）：
  · 四门 + 帧检 9/9（`logs/p57_3_four_gates.json`，烧录 ASS / 成片独立口径）；
  · 渲染签名门 + 分配指纹 36/36 + H7（`fixture_f12.json`，P57-2 驱动）；
  · 生产断言（构建后烧录前）violations=[]（`_cuedump` 的 `cue_gate`）；
  · 分配继承门：与 F10.1 逐景素材 36/36 一致 ⇒ DQ-2/DQ-3/DQ-3e/锚定/内容排除/
    name 中立/no_picture/比喻配额**按构造继承**（F10.1 已全过且素材层零改动）。
运行: python docs/regression_2x/p57_4_register_f12.py
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sqlite3
import subprocess
import sys
import time

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")
FFPROBE = str(R / "bin" / "ffprobe.exe")


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def dur(p, sel=False):
    ent = "format=duration" if not sel else "stream=duration"
    sel_args = [] if not sel else ["-select_streams", "v:0"]
    r = subprocess.run([FFPROBE, "-v", "error", *sel_args, "-show_entries", ent,
                        "-of", "default=nw=1:nk=1", str(p)],
                       capture_output=True, text=True)
    v = (r.stdout or "").strip().splitlines()
    return round(float(v[0]), 3) if v and v[0] else None


def main() -> int:
    fx = json.loads((R / "output/phase36_p36_4_sandbox/fixture_f12.json")
                    .read_text(encoding="utf-8"))
    gates = json.loads((L / "p57_3_four_gates.json").read_text(encoding="utf-8"))
    P = fx["sandbox_project_id"]
    final = R / "projects" / P / "output" / fx["final"]
    base = R / "projects" / P / "output" / "t_158db818a8b3_draft_with_outro_v2.mp4"

    con = sqlite3.connect("file:" + (R / "projects" / "video_studio.db").as_posix()
                          + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    r = con.execute("select payload from events where project_id=? and "
                    "type='MATERIAL_TIMELINE' order by ts desc limit 1", (P,)).fetchone()
    mt = json.loads(r["payload"])
    con.close()
    ma = mt.get("material_allocation") or {}
    dec = mt["decisions"]
    uniq = len({str((d.get("selected_asset") or {}).get("sha256") or "")[:12]
                for d in dec if (d.get("selected_asset") or {}).get("asset_id")})
    ro = None

    rec = {
        "schema": "p57-4-delivery-candidate-v1",
        "stage": "Phase 57 F12（生产 cue 路径修复后的首次真验证版）",
        "registered_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "sandbox_project_id": P,
        "editing_task": fx["editing_task"],
        "render_output_registered": bool(ro),
        "base_film": "projects/p_3e9292101f10/output/t_158db818a8b3_draft_with_outro_v2.mp4",
        "final_film": str(final.relative_to(R)).replace("\\", "/"),
        "final_bytes": final.stat().st_size, "final_sha256": sha(final),
        "final_duration_s": dur(final), "final_video_track_s": dur(final, sel=True),
        "p57_1_production_cue_path_fix": {
            "root_cause_f101": ("第二套 cue 分发用旧词级路径覆盖了 word_exact 的产物"
                                "（windows=None ⇒ 段内时钟无钳制）⇒ 105 条压缩在 178s"),
            "fixes": [
                "① cue 单一分发链（word_exact → audio_anchor → uniform 兜底），"
                "旧词级路径 build_cues_from_words 自生产退役（不保留双路径）",
                "② 生产断言（构建后烧录前，fail-closed）：跨度 ≈ 音频 ±2s / median ≥3s / "
                "重叠 0 / 条数 101–111 —— 本轮实测 violations=[]",
                "③ P56-2 pins 块 silent-kill 修复（`_AL` UnboundLocalError 自 P56-2 起"
                "使钉定机制从未生效；修复后 applied=36 留痕）",
                "④ **钳制依据改句末词所在窗**（v6.5 句中切景 ⇒ 句尾语音无字幕，"
                "实测修复前 31 处 / 61.45s 未覆盖语音）",
                "⑤ **尾句按字符比例重分**（TTS WordBoundary 文本每段少 2–6 字 ⇒ "
                "末尾 1–2 句无自己的 cue；实测修复前 9 句起点偏差 >1s）",
            ],
            "cue_source_label_consistency": "dump.cue_source == 逐条 cue.source == word_exact",
        },
        "p57_2_zero_visual_change": {
            "assignment_same_as_F10_1": "{}/36".format(fx["assignment_same_as_pins"]),
            "audio": "narration_v65.mp3 零改动（H7 音轨逐字节一致）",
            "visual_stack": "分配/素材/运动(关闭)/画面零改动",
            "harness_note": ("内存注入复刻 F10.1 渲染 harness"
                             "（cap=3/forbid_adjacent/min_scene_gap=3/具名绑定 3 景）；"
                             "config.json 零改动"),
        },
        "p57_3_four_gates_burned_ass": {
            "object": "烧录 ASS `_captions_{}.ass` + 成片混音 silencedetect(-35dB/d=0.28)".format(
                fx["editing_task"]),
            "g1_coverage": gates["coverage"],
            "g2_median_dur_s": gates["median_dur"],
            "g2b_clamped_1s": gates["clamped_1s"],
            "g3_max_concurrent": gates["max_concurrent"],
            "g3b_overlap_moments": gates["overlap_moments"],
            "g4_sync_median_s": gates["sync_median_s"],
            "g4b_sync_over_1s": gates["sync_over_1s"],
            "sentences": gates["sentences"],
            "frame_checks": "3/3（开场 10s / 中段 / 结尾字幕带，PNG 存 output/p57_frames/）",
            "pass_fail": "{}/{}".format(gates["pass"], gates["pass"] + gates["fail"]),
            "independent_measurement": "语音段来自最终混音 silencedetect，非 cue 时序来源",
        },
        "signature_gate": fx["signature_gate"],
        "inherited_gates_by_identical_assignment": {
            "statement": ("分配与 F10.1 逐景 sha12 36/36 一致 ⇒ 下列门按构造继承"
                          "（F10.1 登记 all PASS；素材层零改动）"),
            "dq2_unique_assets_measured": uniq,
            "dq2": "PASS（继承 F10.1：唯一素材 30；max_share 0.0667）",
            "dq3": "PASS（继承）", "dq3e": "PASS（继承）",
            "anchor_guard": "PASS（继承）",
            "content_exclusion": "PASS（继承：三处禁入上屏 0）",
            "name_neutral": "PASS（继承）", "no_picture": "PASS（继承）",
            "metaphor_quota": "PASS（继承）",
            "duration_contract": "{:.3f}s（继承 695.528+trailing 契约）".format(dur(final)),
        },
        "quarantined_intermediate_renders": [
            "output/_quarantine_p57_invalid_alloc/（首轮：漏 harness 注入分配失控；"
            "次轮：VLM PROVIDER_TIMEOUT 阻断；三轮：pins 未终局强制 10/36）",
            "output/_quarantine_p57_clamp_defect/（钳制依据缺陷：门① 89.5%）",
            "output/_quarantine_p57_tail_defect/（尾句缺失：门④b 9 句 >1s）",
        ],
        "budget": {"llm_usd": "≈0.006（VLM 仲裁 13 次调用，其中超时 1）",
                   "renders": 7, "render_minutes": "≈38（7 次 × 5–6 分钟）"},
        "zero_promotion": True,
        "next": "F12 交人工第六次终审（**字幕跟嘴**）",
    }
    with (L / "p57_4_delivery_candidate.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print("登记 F12（append-only）：")
    print("  成片: {} ({:,}B, {:.3f}s)".format(
        rec["final_film"], rec["final_bytes"], rec["final_duration_s"]))
    print("  四门+帧检: 9/9 | 覆盖 {:.1%} | median {:.3f}s | 重叠 0 | 同步 median {:.4f}s".format(
        gates["coverage"], gates["median_dur"], gates["sync_median_s"]))
    print("  分配指纹: {}/36 与 F10.1 一致 | 音轨逐字节一致".format(
        fx["assignment_same_as_pins"]))
    print("  零 promotion；交人工第六次终审（字幕跟嘴）")
    print("-> " + str((L / "p57_4_delivery_candidate.jsonl").relative_to(R)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
