# -*- coding: utf-8 -*-
"""P32-5：三版材料包**终版**（含 #80 全处置链、cap=2 废除记录、#78.3、edge-tts、#76 LIMITATION）。
零 promotion。
"""
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
    p21 = json.loads((L / "phase21_promotion_package.json").read_text(encoding="utf-8"))
    acc = json.loads((L / "phase32_candidate_acceptance.json").read_text(encoding="utf-8"))
    cap2 = json.loads((L / "p32_3_cap2_abolition.json").read_text(encoding="utf-8"))
    dl = [json.loads(x) for x in
          (L / "p32_4_delivery_candidate.jsonl").read_text(encoding="utf-8").splitlines()
          if x.strip()]
    latest = dl[-1]
    vers = p21["versions"]
    A, B = vers["A_p19_21seg"], vers["C_p21_40seg"]

    def entry(name, cand, extra):
        p = R / cand
        return {"name": name, "candidate": cand,
                "bytes": (p.stat().st_size if p.is_file() else None),
                "sha256": (sha(p) if p.is_file() else None),
                "duration_s": dur(p), **extra}

    Ae = entry("A（P19 21 景）", A["candidate"], {
        "segments": 21, "gate_state": "ALL_PASS（既有唯一全门通过）",
        "dq2": {"state": "PASS", "max_asset_share": 0.2354, "unique_assets": 10},
        "dq3": {"share_over_threshold": 1.0, "max_hold_s": 67.374},
        "role": "promotion 基线（保持不变）"})
    Be = entry("B（P16-C 40 段 version C）", B["candidate"], {
        "segments": 40, "gate_state": "fail-closed（派生段逐景核验 33 处误报）",
        "dq2": {"state": "PASS", "max_asset_share": 0.1778, "unique_assets": 10},
        "dq3": {"share_over_threshold": 0.425, "max_hold_s": 37.201},
        "role": "过程留档（被 C 取代）"})
    Ce = entry("C（Phase 32 交付级候选，含 H7 片尾卡）", latest["final_film"], {
        "segments": 40,
        "gate_state": "**全门通过**（PI/响度/时长/字幕/逐景 40-40/MOTION/三指标/构造断言/DQ-2 PASS）",
        "duration_s_measured": latest["final_duration_s"],
        "video_track_s": latest["final_video_track_s"],
        "audio_identical_to_base": latest["h7"]["audio_identical_to_base"],
        "render_output_registered": latest["render_output_registered"],
        "render_output_artifact": latest["render_output_artifact"],
        "bank_chain": latest["bank_chain"],
        "dq2": {"state": "PASS", "max_asset_share": acc["dq2"]["max_asset_share"],
                "unique_assets": acc["dq2"]["unique_assets"],
                "threshold": acc["dq2"]["threshold"]},
        "dq3": {"state": "FAIL（报改善）",
                "share_over_threshold": acc["dq3"]["share_over_threshold"],
                "max_hold_s": acc["dq3"]["max_hold_s"],
                "mean_hold_s": acc["dq3"].get("mean_hold_s"),
                "holds_over_threshold": acc["dq3"].get("holds_over_threshold")},
        "per_scene": acc["per_scene"],
        "motion_metrics": {k: acc["motion_metrics"][k] for k in
                           ("freeze_ratio", "longest_static_s", "opening_changes",
                            "all_pass")},
        "loudness": acc.get("loudness"),
        "role": "**本阶段交付级候选**（append-only 登记；未 promotion）"})

    pkg = {
        "schema": "phase32-promotion-package-v1",
        "stage": "Phase 32 P32-5 三版材料包终版（全维度 + 推荐序 + 限制清单）",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "zero_promotion": True,
        "baseline_note": ("Phase 32 **全门通过并登记交付级候选**（C 版，含 H7 片尾卡、已登记 "
                          "render_output）。**promotion 基线保持不变**：仍为 A（P19 21 景）"
                          "`projects/p_50e10b27b44d/output/t_a4d8c1aafd04_draft.mp4`。"
                          "本阶段**不做任何 promotion/发布**，候选交人工终审（看+听+读）。"),
        "versions": {"A_p19_21seg": Ae, "B_p16c_40seg": Be, "C_p32_40seg": Ce},
        "watch_order": [
            {"rank": 1, "version": "C（Phase 32 交付级候选）",
             "candidate": Ce["candidate"],
             "why": "**唯一全门通过且已登记 render_output** 的 40 景版本：时长 977.934s ∈ 978.7±1、"
                    "逐景核验 **40/40（0 失败）**、DQ-2 PASS（0.3341/13）、三指标 11.9%/6.0s/83 全过、"
                    "构造断言 A1/A2 成立、音轨与基片逐字节一致、**含 H7 片尾卡**；"
                    "DQ-3 相对 A 大幅改善（100%→42.5%，max 67.374→37.201s）但**仍未达 ≤20%，只报改善**。"},
            {"rank": 2, "version": "A（P19 21 景）",
             "candidate": Ae["candidate"],
             "why": "既有 promotion 基线、全门通过；代价：DQ-3 100% 超 25s（max 67.374s，长静态明显）、"
                    "且**无片尾卡**。"},
            {"rank": 3, "version": "B（P16-C 40 段 version C）",
             "candidate": Be["candidate"],
             "why": "被 C 全面取代（逐景核验口径缺陷致 fail-closed），仅作过程留档。"},
        ],
        "known_limitations": [
            "**DQ-3 未达 ≤20%（如实）**：C 版 `share_over 0.425`、`max_hold 37.201s`（17/40 超 25s）⇒ "
            "按授权只**报改善**、**不报 PASS**。相对 A（100%/67.374s）为 −30.2s。",
            "**bank-derived-v2 的历史手工语料正门未达 100%**：P17 attr_pack 语料上 v2 = 14/17、"
            "冻结 v1 = **13/17** ⇒ 该语料的 `S07 frame_50`（0.2766）在 v1/v2/SSIM 三种口径下均 < 0.30。"
            "**采纳依据是生产 40 景实测**（`corr_bank` 32/32、S11p2 0.3199 / S13p2 0.3332 过阈、"
            "需仲裁景 12→2、0 失败），**非该手工语料**；阈值与口径未改。",
            "**P32-4 曾踩坑并已修正**：H7 首版用 MP4 `-c copy` concat ⇒ 接头时间戳断裂、"
            "**视频轨仅 975.73s**（容器 977.88s）＝末段 2.1s 变成「无新帧」补齐（构造断言 A1 不成立）。"
            "改用 **MPEG-TS** 拼接后视频轨 **977.933s 满覆盖**。首版产物**已弃用**，不作候选。",
            "**#80 全处置链（终态）**：① P29「时基>内容 ⇒ 补黑」诊断 → ② P30「pause 真实化」"
            "（音频侧 DONE，黑板未变 ⇒ 归因更正）→ ③ P30/P31「多数深色为**素材固有暗色**」"
            "（`Close-packed spheres` 固有 mean 42.54）→ ④ P31「旧『近黑』指标**废弃**，改"
            "**构造断言 A1/A2/A3**」→ ⑤ P32-4 实测**末段 976/977s mean 134.56/117.31（亮）**、"
            "S21p2 窗口内 `uniq=256`（有内容）⇒ **#80 关闭为 `NOT_A_DEFECT`**；"
            "全片技术性黑板 = 0（A1/A2 成立）。",
            "**cap=2 废除（记录）**：算术不可达（40 景需 ≥20 唯一素材；现 12+上限 6=18）⇒ 废除；"
            "替代硬门 = DQ-2（share ≤0.35 且 unique ≥6）＋ `prefer_unused`；**6 张获取授权撤回**。",
            "**#78.3 / edge-tts / #76**：#78.3 沿用既有登记（本阶段未变更）；"
            "TTS 仍为 **edge-tts**（`zh-CN-XiaoxiaoNeural`，逐段 sha256 可核、零重合成/变速）；"
            "**#76 事实核查 LIMITATION 保持**（该限制不由本阶段解除，交付物须保留其声明）。",
            "**字幕形态**：中文字幕为**烧录**（`ass` 滤镜），成片内**无内嵌字幕流** ⇒ 播放器字幕开关"
            "不适用；字幕对齐口径沿用 P27–P30 链（171 cue、语音内 1.0、越界 0s）。",
            "**VLM 成本**：本轮仲裁 ≤ **$0.0084**（≤$0.5 预算；2 景命中缓存记 0）。",
            "**未做**：图内元素动画、视频素材接入、句中拆分、改旁白文本、promotion、发布。",
        ],
        "recommendation": {
            "candidate": Ce["candidate"],
            "why": "全门通过 + 已登记 render_output ⇒ 按授权书登记为**交付级候选**；"
                   "promotion 与发布**留待人工**终审（看 + 听 + 读）。",
            "review_focus": ["H7 片尾卡观感与位置（末 2.2s）",
                             "DQ-3 长静态段（max 37.201s）是否可接受",
                             "末段暗色素材段（S17p1–S18p1/S21p2）观感"],
        },
        "cap2_abolition": cap2["arithmetic_proof"],
    }
    p = L / "phase32_promotion_package.json"
    p.write_text(json.dumps(pkg, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in pkg["versions"].items()}, ensure_ascii=False)[:500])
    print()
    for k, v in pkg["versions"].items():
        print("{:<18} {:>12,}B {:>9}s  {}".format(
            k, v["bytes"] or 0, v["duration_s"] or 0, v["gate_state"][:56]))
    print()
    print("-> " + p.relative_to(R).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
