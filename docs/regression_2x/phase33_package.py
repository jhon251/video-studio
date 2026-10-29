# -*- coding: utf-8 -*-
"""P33-5：材料包 v2（含**新旧两版对比** + 四项终审问题处置记录）。零 promotion。"""
from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys
import time

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
FFPROBE = R / "bin" / "ffprobe.exe"
sys.stdout.reconfigure(encoding="utf-8")


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def dur(p):
    if not pathlib.Path(p).is_file():
        return None
    r = subprocess.run([str(FFPROBE), "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", str(p)], capture_output=True, text=True)
    return round(float(r.stdout.strip().splitlines()[0]), 3) if r.stdout.strip() else None


def main() -> int:
    p32 = json.loads((L / "phase32_promotion_package.json").read_text(encoding="utf-8"))
    acc = json.loads((L / "phase33_candidate_acceptance.json").read_text(encoding="utf-8"))
    tb = json.loads((R / "output/phase33_voice/timebase_v41.json").read_text(encoding="utf-8"))
    fx = json.loads((R / "output/phase33_p33_4_sandbox/fixture.json")
                    .read_text(encoding="utf-8"))
    dl = [json.loads(x) for x in (L / "p33_4_delivery_candidate.jsonl")
          .read_text(encoding="utf-8").splitlines() if x.strip()] \
        if (L / "p33_4_delivery_candidate.jsonl").is_file() else []
    latest = dl[-1] if dl else {}
    old = p32["versions"]["C_p32_40seg"]

    pkg = {
        "schema": "phase33-promotion-package-v2",
        "stage": "Phase 33 P33-5 材料包 v2（新旧两版对比 + 四项终审问题处置）",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "zero_promotion": True,
        "baseline_note": ("Phase 33 产出**第二部交付级候选**：v4.1 稿**首次真正入片**"
                          "（含本期配音与新时基）。**promotion 基线不变**（A/P19 21 景）；"
                          "两版候选并列入材料包，**promotion 与发布留待人工二次终审**。"),
        "versions": {
            "A_p19_21seg": p32["versions"]["A_p19_21seg"],
            "B_p16c_40seg": p32["versions"]["B_p16c_40seg"],
            "C_p32_40seg_old_audio": {
                **{k: old.get(k) for k in ("name", "candidate", "bytes", "sha256",
                                           "duration_s", "segments", "gate_state")},
                "audio_lineage": "v3/V20 谱系音频（977.88s）+ v4.1 文本 ⇒ **文本与声音非同一稿**",
                "role": "过程留档（被 D 取代）"},
            "D_p33_40seg_v41": {
                "name": "D（Phase 33 v4.1 首次入片，含本期配音）",
                "candidate": acc["final_film"],
                "bytes": acc["final_bytes"],
                "sha256": sha(R / acc["final_film"]),
                "duration_s": acc["duration"]["final_s"],
                "segments": 40,
                "gate_state": ("全门通过（PI/响度/时长新契约/字幕+一致性门/逐景 40-40/"
                               "MOTION+MOTION_QUALITY/三指标/构造断言/DQ-2 share+adjacent）"),
                "timebase": {"new_contract_s": acc["timebase"]["new_contract_s"],
                             "old_contract_s": 978.7,
                             "rule": tb["rule"],
                             "why": "旧 978.7±1 契约随 v3/V20 谱系废止；本版按新时基登记"},
                "audio": {"narration_s": tb["narration_measured_s"],
                          "sum_speech_s": tb["sum_measured_speech_s"],
                          "sum_pause_s": tb["sum_pause_s"],
                          "trailing_s": tb["trailing_pad_s"],
                          "voice": "edge-tts zh-CN-XiaoxiaoNeural（原音色）",
                          "segments_ok": 40},
                "dq2": {k: acc["dq2"].get(k) for k in
                        ("state", "unique_assets", "max_asset_share", "threshold")},
                "dq2_new_check": acc["dq2_adjacent_same_asset"],
                "max_scenes_per_asset": acc["max_scenes_per_asset"],
                "dq3": {k: acc["dq3"].get(k) for k in
                        ("state", "scenes", "mean_hold_s", "max_hold_s",
                         "holds_over_threshold", "share_over_threshold")},
                "motion": {k: acc["motion_metrics"].get(k) for k in
                           ("freeze_ratio", "longest_static_s", "opening_changes",
                            "all_pass")},
                "dark_scene_spread": acc["dark_scene_spread"],
                "pool_size": acc["pool_size"],
                "arbitration": acc.get("arbitration"),
                "role": "**本阶段第二部交付级候选**（append-only 登记；未 promotion）"},
        },
        "new_vs_old": {
            "audio_lineage": {"old": "v3/V20 谱系（字幕由 v4.1 脚本生成 ⇒ **可能整片错配**）",
                              "new": "v4.1 稿逐段 edge-tts 合成（**同一份文本**，C1/C2 门可证）"},
            "timebase": {"old": 977.88, "new": tb["audio_time_base_s"],
                         "delta_s": round(tb["audio_time_base_s"] - 977.88, 3)},
            "pool": {"old": 12, "new": acc["pool_size"]},
            "allocation": {"old": "无每素材景数上限、无相邻约束",
                           "new": "≤3 景/素材 + 相邻禁同素材（内存注入，可选）"},
            "motion": {"old": "全片平移**同向**（系统性 →RIGHT）",
                       "new": "方向按景平衡（LEFT/RIGHT 均衡）+ 居中锚定 + 单调性门"},
            "new_gates": ["script_media_consistency_test（文本↔音频↔字幕）",
                          "motion_quality_test（运动质量）",
                          "allocation_discipline_test（分配纪律）"],
        },
        "four_review_dispositions": {
            "① v4.1 从未入片（缺 TTS 授权）": "**已处置**：本期逐段合成 40 段（edge-tts 原音色，"
                                              "40/40 成功、0 重试），v4.1 首次真正入片并登记候选 D。",
            "② 运动质量无门（只测变化不测质量）": "**已处置**：新增 `motion_quality_test`"
                                                  "（Q1 无往复振荡 / Q2 净漂移 ≤ 宣称幅度 / Q3 居中锚定 /"
                                                  " Q4 方向平衡 / Q5 闭式⇔逐帧 / Q6 头静止+单调+末帧到位 /"
                                                  " Q7 幅度上限未放宽），**8/8 PASS**；并修复平移方向"
                                                  "系统性同向（实测旧版 9 个平移景全部 →RIGHT）。",
            "③ 素材疲劳是池容量问题": "**已处置（部分）**：受治理获取 5 张（**网络请求 10，达上限**）"
                                      "⇒ 池 12→**17**（< 目标 20，**如实登记差额**）；新增分配纪律"
                                      "（≤3 景/素材 + 相邻禁同素材）并进 tests（**7/7 PASS**）；"
                                      "S17–S18 暗色段素材分散已量化。",
            "④ 文本一致性无门": "**已处置**：新增 `script_media_consistency_test`"
                                "（C1 逐段 cue 文本==narration / C2 音频 text_sha256==脚本 sha /"
                                " C3 整片文本守恒 / C4 时基一致性 / C5 cue 落在声明窗口 /"
                                " C6 全段成功），**6/6 PASS**。",
        },
        "known_limitations": [
            "**池未达目标 20（如实）**：受治理获取上限 10 次请求已用满，落地 **5 张**（另 2 次搜索"
            "因 IPv6 握手/读取超时失败、3 张被许可或尺寸门拒收）⇒ 池 **17**。目标 ≥20 **未达成**。",
            "**v4.1 事实核查链未独立重跑（#76 口径延续）**：`claims` 结论为**命题保持映射**"
            "（文本经 P27 逐字搬运，未新增事实主张），**发布前需人工终审**。",
            "**DQ-3 未达 ≤20%**：按**新时间轴**如实复算（见 `dq3`），只报数值、不报 PASS。",
            "**时长契约变更已登记**：新时基 **{:.3f}s**（旧 978.7±1 随 v3/V20 谱系废止）；"
            "本轮渲染前闸门曾以旧声明时长**正确 fail-closed**（PI-1 覆盖 0.7125 / PI-2 shortfall "
            "281.97s），据授权书 §3 重算新时基后通过。".format(tb["audio_time_base_s"]),
            "**pause 归因口径**：本轮 pause = 脚本 `pause_budget_s`（0.384615，原始边界）；"
            "**必须**随 voice 产物携带 `pause_attribution` 表，否则 `narration_plan` 回落冻结常量 "
            "0.75 ⇒ 时基出现 +14.25s 幻影膨胀（**实测踩坑并已修复**，见报告）。",
            "**H7 片尾卡**：in-window overlay（TS 拼接），总时长不变、音轨与基片逐字节一致。",
            "**#80** 已在 P32 关闭为 `NOT_A_DEFECT`（全处置链见 v1 材料包与 KNOWN_ISSUES）。",
        ],
        "recommendation": {
            "candidate": acc["final_film"],
            "why": "**唯一在 v4.1 新时基下全门通过**的版本；文本↔音频↔字幕三者同源可证。",
            "review_focus": ["v4.1 旁白与画面的对应关系（换稿后语义是否仍贴合）",
                             "新时长 700s 的节奏观感",
                             "DQ-3 长静态段（新时间轴口径）",
                             "H7 片尾卡"],
        },
    }
    p = L / "phase33_promotion_package.json"
    p.write_text(json.dumps(pkg, ensure_ascii=False, indent=1), encoding="utf-8")
    for k, v in pkg["versions"].items():
        print("{:<26} {:>12,}B {:>9}s  {}".format(
            k, v.get("bytes") or 0, v.get("duration_s") or 0,
            str(v.get("gate_state"))[:52]))
    print()
    print("-> " + p.relative_to(R).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
