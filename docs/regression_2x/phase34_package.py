# -*- coding: utf-8 -*-
"""P34-5：材料包 **v3**（四/五版本对比 + 三条终审意见处置 + 两项口径变更）。零 promotion。"""
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
    p33 = json.loads((L / "phase33_promotion_package.json").read_text(encoding="utf-8"))
    acc = json.loads((L / "phase34_candidate_acceptance.json").read_text(encoding="utf-8"))
    tb = json.loads((R / "output/phase34_voice/timebase_v42.json").read_text(encoding="utf-8"))
    rw = json.loads((L / "p34_3_rewrite_report.json").read_text(encoding="utf-8"))
    scan = json.loads((L / "p34_1_no_picture_scan.json").read_text(encoding="utf-8"))
    fx = json.loads((R / "output/phase34_p34_4_sandbox/fixture.json")
                    .read_text(encoding="utf-8"))
    dl = [json.loads(x) for x in (L / "p34_4_delivery_candidate.jsonl")
          .read_text(encoding="utf-8").splitlines() if x.strip()]

    vs = dict(p33["versions"])
    E = {
        "name": "E（Phase 34 v4.2 净稿 + 无画面清零 + 运动停用）",
        "candidate": acc["final_film"],
        "bytes": acc["final_bytes"], "sha256": sha(R / acc["final_film"]),
        "duration_s": acc["duration"]["final_s"], "segments": 40,
        "gate_state": ("全门通过（PI/响度/时长新契约/一致性门/逐景 40-40/**no_picture 0**/"
                       "DQ-2/DQ-3/构造断言）；**三指标按运动停用后新口径不通过（已登记）**"),
        "timebase": {"rule": tb["rule"], "contract_s": tb["audio_time_base_s"],
                     "sum_speech_s": tb["sum_measured_speech_s"],
                     "narration_s": tb["narration_measured_s"],
                     "prev_v41_contract_s": 685.592,
                     "note": "授权书预期 ~650s；实测 628.8s（净稿更短），已如实登记"},
        "v42_rewrite": {"meta_spans_applied": len(rw.get("meta_spans_applied") or []),
                        "blacklist_residue": len(rw.get("blacklist_residue") or []),
                        "conservation_violations":
                            len((rw.get("conservation") or {}).get(
                                "numbers_entities_violations") or []),
                        "chars": rw.get("chars"), "method": rw.get("method"),
                        "cta_retained": rw.get("cta_retained")},
        "no_picture": {"card_scenes_before": len(scan["card_scenes"]),
                       "card_scenes_after": len(fx.get("card_scenes_remaining") or []),
                       "pure_color_frames_before_s":
                           scan["scan"]["pure_color_seconds"],
                       "pure_color_frames_after_s": 0,
                       "longest_dark_before_s": max(
                           [w["duration_s"] for w in scan["scan"]["dark_windows"]] or [0]),
                       "residual_dark_verdict": "内容性暗场（std≈54 / uniq=256，有内容）"},
        "motion": {"enabled": fx.get("motion_enabled"),
                   "note": "P34-2 全片停用；能力保留（future: 摄影类素材 + 人工样片批准）"},
        "dq2": {k: acc["dq2"].get(k) for k in
                ("state", "unique_assets", "max_asset_share", "threshold")},
        "dq2_adjacent_same_asset": acc["dq2_adjacent_same_asset"],
        "max_scenes_per_asset": acc["max_scenes_per_asset"],
        "dq3": {k: acc["dq3"].get(k) for k in
                ("state", "share_over_threshold", "max_hold_s", "mean_hold_s")},
        "motion_metrics": {k: acc["motion_metrics"].get(k) for k in
                           ("freeze_ratio", "longest_static_s", "opening_changes", "all_pass")},
        "role": "**本阶段第二部（第 3 个）交付级候选**（append-only；未 promotion）",
    }
    vs["E_p34_v42_clean"] = E

    pkg = {
        "schema": "phase34-promotion-package-v3",
        "stage": "Phase 34 P34-5 材料包 v3（多版本对比 + 三条终审意见处置 + 口径变更登记）",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "zero_promotion": True,
        "baseline_note": ("Phase 34 产出**第三部交付级候选**（E：v4.2 净稿 + 无画面清零 + 运动停用）。"
                          "**promotion 基线仍为 A（P19 21 景）**；A/C/D/E 四部并存，"
                          "**promotion 决策留待用户终审**（本次只看三件事：还有没有「没画面」、"
                          "还有没有「蠕动」、还有没有「核查腔」）。"),
        "versions": vs,
        "watch_order": [
            {"rank": 1, "version": "E（Phase 34 v4.2 净稿）", "candidate": E["candidate"],
             "why": "**无画面清零（有旁白+纯色卡 = 0）**、**运动停用（无蠕动）**、"
                    "**核查腔清零（黑名单 0 残留）** 三项终审关切全部处置；"
                    "DQ-2 0.0881/17、DQ-3 **0/40 超 25s（PASS）**、时长 630.8s。"
                    "代价：三指标按运动停用后新口径 `freeze_ratio 68.7% > 50%` **不通过**（已登记口径变更）。"},
            {"rank": 2, "version": "D（Phase 33 v4.1）", "candidate": p33["versions"]
             ["D_p33_40seg_v41"]["candidate"],
             "why": "除「无画面/蠕动/核查腔」三项外全门通过；作为 E 的对照版本（同音频谱系、不同净稿）。"},
            {"rank": 3, "version": "C（Phase 32 旧音频）",
             "candidate": p33["versions"]["C_p32_40seg_old_audio"]["candidate"],
             "why": "文本与声音**非同一稿**，仅作历史对照。"},
            {"rank": 4, "version": "A（P19 21 景）", "candidate": p33["versions"]
             ["A_p19_21seg"]["candidate"],
             "why": "既有 promotion 基线；DQ-3 100% 超 25s、无片尾卡、素材池贫瘠。"},
        ],
        "three_review_dispositions": {
            "① 运动默认关（蠕动不可接受）": {
                "action": "**DONE**：`render_motion.json` → `enabled=false`（全片停用）",
                "evidence": "构造断言与三指标照跑；本片运动景 = 0",
                "capability_retained": "`core/motion.py` + `tests/motion_quality_test.py`（8/8）未动；"
                                       "未来仅对摄影类素材经**人工样片批准**后启用",
                "metric_basis_change": "运动停用后 `freeze_ratio` 度量的是**切镜密度**而非运动幅度；"
                                       "本片实测 68.7% ⇒ 按现口径不通过，**阈值未改、已登记**"},
            "② 口播元叙述归零（不确定性口语化）": {
                "action": "**DONE**：22 处跨度级清零；黑名单 0 残留；"
                          "不确定性改自然口语（「有说法是」「据说是」）",
                "red_line_kept": "**红线在账上不在嘴上**：`claims` 映射与 "
                                 "`content_conclusions_inherited` 原文保留；未新增叙事性免责",
                "cta_retained": "片尾互动 CTA 保留（授权书 §0②），仅去核查腔"},
            "③ 无画面定义与清零": {
                "action": "**DONE**：8 个卡景（≈129s）全部具名绑定池内素材；"
                          "纯色帧 18s → **0s**；新门 `no_picture_scan_test` 2/2 PASS",
                "residual": "3 段 18–19s 近黑窗口（std≈54/uniq=256）判为**内容性暗场**，留证复验"},
        },
        "metric_changes_registered": {
            "近黑指标（P31 已废）": "旧「全片无 ≥3s 连续近黑」废弃 ⇒ 改 **A1/A2/A3 构造断言**"
                                    "（`tests/no_completion_blackboard_test.py`）；"
                                    "P34 另立 **no_picture 门**（纯色卡 + 持续近黑）。",
            "运动指标（P34 变更）": "运动停用 ⇒ `freeze_ratio` 语义由「运动幅度」变为「切镜密度」；"
                                    "本片 68.7% **不通过**（如实登记，阈值未改）。",
        },
        "known_limitations": [
            "**三指标按现口径不通过**（`freeze_ratio 68.7% > 50%`）：运动停用的直接后果；"
            "若监理认为该口径在运动停用下不再适用，请裁定**口径替代**（如改判「切镜密度」阈值）"
            "或接受该值。",
            "**未调用 LLM（LLM $0）**：元叙述清零用**规则 + 全量守恒校验**完成（22 处跨度、"
            "0 实体违例、0 黑名单残留）；若要求以 LLM 重写以降低与 v4.1 的文本重合（92.8%），"
            "请单独授权。",
            "**相邻同素材 2 处**未解（池 17、cap 3，候选集内无可替代）。",
            "**残留 3 段内容性暗场**（18–19s）：有内容，非「无画面」。",
            "**池仍 17 张（< 目标 20）**：P33-2 请求预算用满，本轮网络 0。",
            "**v4.2 事实核查链未独立重跑**（#76 口径延续）⇒ 发布前需人工终审。",
        ],
        "recommendation": {
            "candidate": E["candidate"],
            "why": "三项终审关切（没画面 / 蠕动 / 核查腔）**全部处置**；DQ-2、DQ-3 均 PASS。",
            "review_focus": ["还有没有「没画面」（重点看 S03p1/S05p1/S05p2/S13p1/S16p1/S17p1/S17p2/S21p1 新绑定）",
                             "还有没有「蠕动」（运动已停用）",
                             "还有没有「核查腔」（元叙述已清零）",
                             "内容性暗场段（S16p2/S18p1 等）观感是否可接受"],
        },
    }
    p = L / "phase34_promotion_package.json"
    p.write_text(json.dumps(pkg, ensure_ascii=False, indent=1), encoding="utf-8")
    for k, v in pkg["versions"].items():
        print("{:<26} {:>12,}B {:>9}s".format(k, v.get("bytes") or 0,
                                              v.get("duration_s") or 0))
    print()
    print("-> " + p.relative_to(R).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
