# -*- coding: utf-8 -*-
"""Phase 36 / §3：**登记第四部交付级候选**（append-only、零 promotion）+ 材料包 v4（六版对比）。

**如实登记两处观察**（不隐藏）：
  ① **分配纪律未真正达标**：cap=3 实测 max **4**；min_scene_gap=3 实测违例 **10** 处；
     `unresolved` **12** 景。根因：17 张池要同时满足「≤3 景/素材 + 间距≥3」对 36 景
     是**紧约束**（需 ≥12 张等效可用且可间隔 3 布局），贪心改选会 overshoot 且不回退。
     ⇒ 门 `allocation_discipline_test` 在**独立桩**下通过、在**实盘**下不通过 ⇒ 如实登记为缺陷。
  ② **三指标不通过**（冻结 73.3%）：运动停用的直接后果（P34-2 口径变更已登记）。
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
SB = R / "output" / "phase36_p36_4_sandbox"
L = R / "docs" / "regression_2x" / "logs"
FF = str(R / "bin" / "ffmpeg.exe")
FFPROBE = str(R / "bin" / "ffprobe.exe")
sys.stdout.reconfigure(encoding="utf-8")


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def dur(p, sel=False):
    cmd = [FFPROBE, "-v", "error"]
    if sel:
        cmd += ["-select_streams", "v:0"]
    cmd += ["-show_entries", "stream=duration" if sel else "format=duration",
            "-of", "default=nw=1:nk=1", str(p)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    v = (r.stdout or "").strip().splitlines()
    return round(float(v[0]), 3) if v and v[0] else None


def aud(p):
    r = subprocess.run([FF, "-v", "error", "-i", str(p), "-map", "0:a:0", "-c", "copy",
                        "-f", "streamhash", "-hash", "sha256", "-"],
                       capture_output=True, text=True)
    return (r.stdout or "").strip()


def main() -> int:
    fx = json.loads((SB / "fixture.json").read_text(encoding="utf-8"))
    pid = fx["sandbox_project_id"]
    pdir = R / "projects" / pid / "output"
    base = next(f for f in sorted(pdir.glob("*.mp4")) if "with_outro" not in f.name)
    final = next(f for f in sorted(pdir.glob("*with_outro_v2.mp4")))
    acc = json.loads((L / "phase36_candidate_acceptance.json").read_text(encoding="utf-8"))
    tb = json.loads((R / "output/phase36_voice/timebase_v65.json").read_text(encoding="utf-8"))
    sc = json.loads((R / "output/phase36_voice/scenes.json").read_text(encoding="utf-8"))

    con = sqlite3.connect("file:" + (R / "projects/video_studio.db").as_posix()
                          + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    arts = [dict(r) for r in con.execute(
        "select artifact_id,type,path from artifacts where project_id=?", (pid,))]
    ro = next((a for a in arts if a["type"] == "render_output"), None)
    r = con.execute("select payload from events where project_id=? and "
                    "type='MATERIAL_TIMELINE'", (pid,)).fetchone()
    alloc = (json.loads(r["payload"]).get("material_allocation") or {}) if r else {}
    con.close()
    counts = alloc.get("final_counts") or {}
    max_cnt = max(counts.values()) if counts else None
    seq = [(d.get("selected_asset") or {}).get("asset_id")
           for d in json.loads((SB / "material_timeline.json")
                               .read_text(encoding="utf-8"))["decisions"]]
    gapv = 0
    for i, a in enumerate(seq):
        if not a:
            continue
        for j in range(max(0, i - 3), min(len(seq), i + 4)):
            if j != i and seq[j] == a:
                gapv += 1
                break

    rec = {
        "schema": "p36-4-delivery-candidate-v1",
        "stage": "Phase 36 第四部交付级候选（v6.5 单线重构；段落级 TTS + 静音吸附切景）",
        "registered_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "sandbox_project_id": pid,
        "base_film": str(base.relative_to(R)).replace("\\", "/"),
        "base_sha256": sha(base), "base_bytes": base.stat().st_size, "base_duration_s": dur(base),
        "final_film": str(final.relative_to(R)).replace("\\", "/"),
        "final_sha256": sha(final), "final_bytes": final.stat().st_size,
        "final_duration_s": dur(final), "final_video_track_s": dur(final, sel=True),
        "render_output_registered": bool(ro),
        "render_output_artifact": (ro["artifact_id"] if ro else None),
        "audio_identical_to_base": aud(final) == aud(base),
        "script": {"version": "v6.5", "sha256": sha(R / "output/p36_script/v6_5_fulltext.json"),
                   "chars": 3448, "paragraphs": 9, "scenes": 36,
                   "mid_sentence_cuts": sc["mid_sentence_cuts"],
                   "silence_snap": {"silence": sum(x["snap_silence"] for x in sc["snap_log"]),
                                    "ratio": sum(x["snap_ratio"] for x in sc["snap_log"])}},
        "tts": {"mode": "段落级（9 段整段合成）", "voice": "zh-CN-XiaoxiaoNeural",
                "segments_ok": 9, "sum_speech_s": tb["sum_measured_speech_s"]},
        "timebase": {"rule": tb["rule"], "contract_s": tb["audio_time_base_s"],
                     "trailing_s": tb["trailing_pad_s"],
                     "note": "实测语音 693.528s（字符估算曾给 647s）⇒ 以实测为权威"},
        "gates": {"duration": {"value": dur(final), "contract": tb["audio_time_base_s"]},
                  "a2_delta_s": acc.get("a2_delta_s"), "full_cover": True,
                  "audio_streamhash_identical": aud(final) == aud(base),
                  "dq2": {k: acc["dq2"].get(k) for k in
                          ("state", "unique_assets", "max_asset_share")},
                  "dq3": {k: acc["dq3"].get(k) for k in
                          ("state", "share_over_threshold", "max_hold_s")},
                  "motion_metrics": {k: acc["motion_metrics"].get(k) for k in
                                     ("freeze_ratio", "longest_static_s",
                                      "opening_changes", "all_pass")},
                  "no_picture": "PASS（有旁白+纯色卡 = 0；纯色帧 0s）",
                  "metaphor_quota": "PASS（7/7）",
                  "arbitration": {"arbitrated": 3, "still_failed": 0,
                                  "cost_usd": 0.0}},
        "honest_findings": {
            "allocation_discipline_not_met": {
                "cap_declared": alloc.get("cap"), "cap_actual_max_scenes": max_cnt,
                "min_scene_gap_declared": alloc.get("min_scene_gap"),
                "gap_violations": gapv, "unresolved": len(alloc.get("unresolved") or []),
                "reassigned": len(alloc.get("reassigned") or []),
                "root_cause": ("17 张池对 36 景同时满足「≤3 景/素材 + 间距≥3」是**紧约束**；"
                               "贪心改选会 overshoot 且**不回退**，无解时保留原分配（已记账）。"),
                "classification": ("**缺陷**：`allocation_discipline_test` 在独立桩下通过、"
                                   "在实盘下不通过 ⇒ 测试与实盘行为不一致，如实登记"),
                "impact": "观感影响有限（DQ-2 share 0.1214 仍 PASS），但**纪律未被真正执行**",
            },
            "motion_metrics_fail": {
                "freeze_ratio": acc["motion_metrics"].get("freeze_ratio"),
                "note": "运动停用的直接后果；口径变更已在 P34-2 登记，阈值未改",
            },
        },
        "zero_promotion": True,
        "promotion_baseline_unchanged": "projects/p_50e10b27b44d/output/t_a4d8c1aafd04_draft.mp4",
    }
    p = L / "p36_4_delivery_candidate.jsonl"
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # ---------------- 材料包 v4（六版对比）----------------
    p33 = json.loads((L / "phase33_promotion_package.json").read_text(encoding="utf-8"))
    p34 = json.loads((L / "phase34_promotion_package.json").read_text(encoding="utf-8"))
    versions = {}
    for src in (p33["versions"], p34["versions"]):
        for k, v in src.items():
            if isinstance(v, dict):
                versions[k] = {kk: v.get(kk) for kk in
                               ("name", "candidate", "bytes", "duration_s",
                                "segments", "gate_state")}
            else:
                versions[k] = v
    versions["F_p36_v65_singleline"] = {
        "name": "F（Phase 36 v6.5 单线重构「凭什么信」）",
        "candidate": rec["final_film"], "bytes": rec["final_bytes"],
        "duration_s": rec["final_duration_s"], "segments": 36,
        "gate_state": ("时长/A2/满覆盖/音轨一致/DQ-2/DQ-3(0/36 超 25s)/no_picture 0/配额 7-7 全过；"
                       "**分配纪律未达标（cap 3→实测 4、gap 违例 10）**；三指标按新口径不通过"),
    }
    pkg = {
        "schema": "phase36-promotion-package-v4",
        "stage": "Phase 36 P36-5 材料包 v4（六版对比）",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "zero_promotion": True,
        "baseline_note": ("Phase 36 产出**第四部交付级候选**（F：v6.5 单线重构 + 段落级 TTS + "
                          "静音吸附切景）。**promotion 基线仍为 A（P19 21 景）**；"
                          "A/C/D/E/F 多部并存，**promotion 决策留待用户第四次终审**（看+听+读）。"),
        "versions": versions,
        "watch_order": [
            {"rank": 1, "version": "F（v6.5 单线重构）", "candidate": rec["final_film"],
             "why": ("唯一「单一脊柱贯穿」（凭什么信）+ **段落级 TTS**（韵律连贯、非逐句重置）"
                     "+ **静音吸附切景**（切点落在真实静音、句中切分 0）+ 无画面清零 + 无蠕动。"
                     "代价：分配纪律未达标、三指标按停用口径不通过。")},
            {"rank": 2, "version": "E（Phase 34 v4.2 净稿）",
             "candidate": p34["versions"]["E_p34_v42_clean"]["candidate"],
             "why": "上一步候选；逐景 TTS（韵律较碎）作为对照。"},
            {"rank": 3, "version": "D（Phase 33 v4.1）",
             "candidate": p33["versions"]["D_p33_40seg_v41"]["candidate"],
             "why": "v4.1 首次入片版本。"},
            {"rank": 4, "version": "A（P19 21 景）",
             "candidate": p33["versions"]["A_p19_21seg"]["candidate"],
             "why": "promotion 基线。"},
        ],
        "phase36_changes": {
            "骨架": "40 景/12 段 → **36 景/9 段**；五主角轮换 → **一个问题贯穿（凭什么信）**",
            "TTS": "逐段独立（40 次韵律重置）→ **段落级（9 段整段）**",
            "切景": "按旧音频比例映射（句中腰斩）→ **静音吸附**（silencedetect，句中切分 0）",
            "文本": "v4.2 → v5 → v5.1 → v5.2 → v6 → v6.3 → v6.4 → **v6.5**（经五轮人审）",
            "新增门": ["钩子衔接（8/8 BROKEN=0）", "比喻配额 7/7", "信号 k（抽象名词密度）",
                       "no_picture（卡景 0）", "静音吸附（句中切分 0）"],
        },
        "honest_findings": rec["honest_findings"],
        "recommendation": {"candidate": rec["final_film"],
                           "review_focus": ["单一脊柱是否成立（每段末句钩子是否勾住你）",
                                            "段落级配音的韵律是否明显好于 E",
                                            "切点是否听不出断句",
                                            "分配纪律未达标的观感影响（有无素材重复感）"]},
    }
    pv4 = L / "phase36_promotion_package.json"
    pv4.write_text(json.dumps(pkg, ensure_ascii=False, indent=1), encoding="utf-8")
    print("登记：{} | {:,}B | {}s | render_output={}".format(
        rec["final_film"], rec["final_bytes"], rec["final_duration_s"],
        rec["render_output_artifact"]))
    print("分配纪律：cap 声明 {} / 实测 max {} | gap 违例 {} | unresolved {}".format(
        alloc.get("cap"), max_cnt, gapv, len(alloc.get("unresolved") or [])))
    print("材料包 v4：{} 版".format(len(versions)))
    print("-> " + p.relative_to(R).as_posix())
    print("-> " + pv4.relative_to(R).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
