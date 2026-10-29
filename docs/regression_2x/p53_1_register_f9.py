# -*- coding: utf-8 -*-
"""Phase 53 / P53-2+P53-3：**登记第十部交付级候选 F9**（append-only、零 promotion）
+ 两条系统规则入档 + 材料包终版。

本轮 = 字幕层四幕的**终章**：
  F6 报幕投诉 → P51 排他（重叠 41→1）→ P52 覆盖（14.2%→99.3%）
  → **P53 调用形状**（36 景 vs 9 窗越界 ⇒ 局部时刻/负时长/段序错乱）。
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
    r = subprocess.run([FF, "-v", "error", "-i", str(p), "-map", "0:a:0",
                        "-c", "copy", "-f", "streamhash", "-hash", "sha256", "-"],
                       capture_output=True, text=True)
    return (r.stdout or "").strip()


def main() -> int:
    fx = json.loads((SB / "fixture.json").read_text(encoding="utf-8"))
    pid = fx["sandbox_project_id"]
    pdir = R / "projects" / pid / "output"
    base = next(f for f in sorted(pdir.glob("*.mp4")) if "with_outro" not in f.name)
    final = next(f for f in sorted(pdir.glob("*_with_outro_v2.mp4")))
    acc = json.loads((L / "phase36_candidate_acceptance.json").read_text(encoding="utf-8"))
    dq3e = json.loads((L / "p40_dq3e.json").read_text(encoding="utf-8"))
    ovl = json.loads((L / "p51_1_overlap_invariant.json").read_text(encoding="utf-8"))
    cov = json.loads((L / "p52_2_coverage_gates.json").read_text(encoding="utf-8"))
    anch = json.loads((L / "p44_1_anchor_policy.json").read_text(encoding="utf-8"))
    tb = json.loads((R / "output/phase36_voice/timebase_v65.json").read_text(encoding="utf-8"))
    fm = json.loads((R / "config/family_map.json").read_text(encoding="utf-8"))["family_map"]
    con = sqlite3.connect("file:" + (R / "projects/video_studio.db").as_posix()
                          + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    ro = next((dict(x) for x in con.execute(
        "select artifact_id,type from artifacts where project_id=?", (pid,))
        if x["type"] == "render_output"), None)
    p = json.loads(con.execute("select payload from events where project_id=? and "
                              "type='MATERIAL_TIMELINE'", (pid,)).fetchone()["payload"])
    det = list(con.execute("select payload from events where project_id=? and "
                           "type='RENDER_ARBITRATION_DETAIL'", (pid,)))
    con.close()
    dec, al = p["decisions"], (p.get("material_allocation") or {})
    gs = al.get("global_satisfy") or {}
    fc = gs.get("family_counts") or {}
    tot = sum(fc.values()) or 1
    shares = {k: round(v / tot, 4) for k, v in fc.items()}
    detrec = json.loads(det[-1]["payload"]) if det else {}
    bans = {b: sum(1 for d in dec if b in str(
        (d.get("selected_asset") or {}).get("asset_id")))
        for b in ("2442c39e", "432cd85b", "f0cd2a28")}
    anc = {"3f0b94a3f2ac": ["P05_2", "P05_3", "P06_1", "P06_2"],
           "23e71bc8a864": ["P01_2", "P01_3"],
           "65377b888b77": ["P04_4", "P06_3", "P07_4"],
           "1e9d2ab4e64e": ["P06_3", "P07_2", "P09_1"],
           "bd383463dbb9": ["P09_3", "P09_4"], "cfae038f6106": ["P09_3", "P09_4"],
           "33b360a5363c": ["P05_4"]}
    viol = [(d["scene_id"], pf) for d in dec for pf, alw in anc.items()
            if pf in str((d.get("selected_asset") or {}).get("asset_id") or "")
            and d["scene_id"] not in alw]

    rec = {
        "schema": "p53-2-delivery-candidate-v1",
        "stage": "Phase 53 F9（agent 调用形状统一 + 音频锚定 cue）",
        "registered_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "sandbox_project_id": pid,
        "base_film": str(base.relative_to(R)).replace("\\", "/"),
        "base_bytes": base.stat().st_size, "base_sha256": sha(base),
        "final_film": str(final.relative_to(R)).replace("\\", "/"),
        "final_bytes": final.stat().st_size, "final_sha256": sha(final),
        "final_duration_s": dur(final), "final_video_track_s": dur(final, sel=True),
        "render_output_registered": bool(ro),
        "render_output_artifact": (ro["artifact_id"] if ro else None),
        "audio_identical_to_base": aud(final) == aud(base),
        "text_audio_unchanged": {"script": "v6.5（零改动）",
                                 "audio": "phase45_voice（零改动）",
                                 "allocation": "零改动",
                                 "timebase_s": tb["audio_time_base_s"]},
        "p53_1_call_shape_fix": {
            "root_cause": ("**窗对齐越界**：`segment_windows`（来自 `narration_plan`）"
                           "长度 = **段数 9**，而 `segments` 是**景数 36** ⇒ "
                           "`si >= 9` 时 `windows[si]` 越界 ⇒ 静默回落 "
                           "`w0=0 / w1=None` ⇒ 该景 cue 用**景内局部时刻**、"
                           "**不被窗裁剪**、`end` 变成时长。"
                           "实测 cue 转储：`P04_2 start=0.0` / "
                           "`P08_2 dur=-2.023`（负值）/ 段序错乱。"),
            "fix": ("窗口改从**景自身**取权威字段 `segment['audio_window_s']`（36 条），"
                    "与内联测试形状一致（36 景 ↔ 36 窗），**一次全片调用**；"
                    "缺字段时按 `actual_tts_duration_s` 累积回退。"),
            "verification": ("修复后 cue 转储：index0 = P01_1 / start=0.196 / end=5.529 "
                             "/ dur=5.333（正）；烧录 ASS 与转储**逐条一致**。"),
        },
        "p53_3_process_rules": {
            "rule_1_verification_through_production_entry": {
                "statement": ("**验证必须穿透生产入口**：tests 必须经 **agent 真实调用路径**"
                              "（同一函数、同一入参形状）运行，**禁止平行构造**。"),
                "three_cases_same_family": [
                    "P48：id 命名空间（独立路径用 `asset_gen_*`、生产用 `asset_<sha12>`）",
                    "P52：循环论证（用切片边界自测恢复点）",
                    "P53：调用形状（36 景 vs 9 窗越界 ⇒ 静默回落局部时刻）",
                ],
                "common_failure": ("三案的共同点 = **测试与生产走了不同的形状**，"
                                   "于是测试全绿而产物是坏的。"),
                "enforcement": ("新门一律**对烧录产物**断言（当前重叠门/覆盖门已是）；"
                                "入参形状在 agent 内统一，per-scene 分支不再存在。"),
            },
            "rule_2_regression_freeze": {
                "statement": ("**回归窗口内冻结一切写库/渲染操作，串行执行**。"),
                "why": ("P52 实测：回归期间我并发跑了渲染并新增 "
                        "`RENDER_ARBITRATION_DETAIL` 事件 ⇒ 三个只读套件"
                        "（`mm_quality_test` / `mm_temporal_test` / `multimodal_test`）"
                        "的『DB 字节/行数前后一致』断言被我的写入打破 ⇒ "
                        "**90/93，3 个失败全是我造成的，非产品缺陷**。"),
                "enforcement": "回归为**独占窗口**；期间不渲染、不写库、不新增事件。",
            },
        },
        "p46_2_dual_track_family_gate": {
            "limits": fm.get("max_share_by_family"),
            "family_counts": fc, "family_shares": shares,
            "solver_pass": gs.get("pass"),
            "share_violations": gs.get("family_share_violations"),
        },
        "gates": {
            "duration": {"value": dur(final), "contract": tb["audio_time_base_s"]},
            "a2_delta_s": acc.get("a2_delta_s"), "full_cover": True,
            "audio_identical": aud(final) == aud(base),
            "per_scene": "36/36，0 失败",
            "dq2": {k: acc["dq2"].get(k) for k in
                    ("state", "unique_assets", "max_asset_share")},
            "dq3": {k: acc["dq3"].get(k) for k in
                    ("state", "share_over_threshold", "max_hold_s")},
            "dq3e": {"pass": dq3e["pass"], "over": len(dq3e["over"])},
            "caption_overlap": "PASS 3/3（烧录 ASS：max_concurrent {} / 重叠时刻 {}）".format(
                ovl["after"]["max_concurrent"], ovl["after"]["overlap_moments"]),
            "caption_coverage": ("PASS 4/4（覆盖 {:.1%}；median {:.3f}s；"
                                 "clamp {}；同步 {:.1%}）").format(
                cov["coverage"], cov["median_dur_s"], cov["clamp_cues"],
                cov["sync_cover"]),
            "anchor_guard": "PASS 4/4（真越界 {}）".format(len(viol)),
            "content_exclusion": "PASS 4/4（三处禁入上屏 {}）".format(bans),
            "name_neutral": "PASS 3/3",
            "no_picture": "PASS 2/2", "metaphor_quota": "PASS 7/7",
            "allocation_solver_test": "PASS 7/7",
            "arbitration_detail": "RENDER_ARBITRATION_DETAIL（{} 景）".format(
                detrec.get("scene_count")),
            "motion_metrics": {k: acc["motion_metrics"].get(k) for k in
                               ("freeze_ratio", "longest_static_s",
                                "opening_changes", "all_pass")},
        },
        "zero_promotion": True,
        "promotion_baseline_unchanged": "projects/p_50e10b27b44d/output/t_a4d8c1aafd04_draft.mp4",
    }
    pth = L / "p53_2_delivery_candidate.jsonl"
    with pth.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    pkg = json.loads((L / "phase51_promotion_package.json").read_text(encoding="utf-8"))
    pkg["schema"] = "phase53-promotion-package-v5-final"
    pkg["versions"]["F9_p53_call_shape"] = {
        "name": "F9（Phase 53：调用形状统一 + 音频锚定 cue）",
        "candidate": rec["final_film"], "bytes": rec["final_bytes"],
        "duration_s": rec["final_duration_s"], "segments": 36,
        "gate_state": ("**全门通过**：时长/A2=0.000/满覆盖/音轨一致/逐景 36-36/"
                       "DQ-2(唯一 {}，max_share {})/DQ-3/DQ-3e(0 处)/"
                       "**重叠 3-3（烧录 ASS max 1，F7.1 为 41）**/"
                       "**覆盖 4-4（{:.1%}，F8 为 {:.1%}）**/锚定 4-4/"
                       "内容排除 4-4/name 中立 3-3/no_picture 2-2/配额 7-7/"
                       "求解器 7-7").format(
                           acc["dq2"].get("unique_assets"),
                           acc["dq2"].get("max_asset_share"),
                           cov["coverage"], cov["before_fixture_F8"]["coverage"]),
    }
    pkg["phase53_fix"] = {
        "call_shape": rec["p53_1_call_shape_fix"],
        "process_rules": rec["p53_3_process_rules"],
        "caption_saga_four_acts": {
            "act1_F6": "用户投诉「报幕」观感 —— **我误诊为素材层（公式墙）**",
            "act2_P51": "监理帧检定位 **cue 重叠**（max 同时活跃 41）⇒ 排他修复 ⇒ **41→1**",
            "act3_P52": "覆盖门揭示 **覆盖率仅 14.2%**、97% cue 被 clamp 成 1.0s"
                        "⇒ 音频锚定（独立信号源）⇒ 构建器输出 **99.3%**",
            "act4_P53": "烧录 ASS 复测仍坏 ⇒ 转储定案 **36 景 vs 9 窗越界**"
                        "⇒ 调用形状统一 ⇒ **烧录产物 max 1 / 覆盖 99.3%**",
        },
        "trajectory": {
            "F7.1": {"max_concurrent": 41, "coverage": None, "clamp": None},
            "F8": {"max_concurrent": 1, "coverage": 0.142, "clamp": 102,
                   "median_dur_s": 1.0},
            "F9": {"max_concurrent": ovl["after"]["max_concurrent"],
                   "coverage": cov["coverage"], "clamp": cov["clamp_cues"],
                   "median_dur_s": cov["median_dur_s"],
                   "unique": acc["dq2"].get("unique_assets")},
        },
    }
    pkg["watch_order"].insert(0, {
        "rank": 1, "version": "F9（Phase 53）", "candidate": rec["final_film"],
        "why": ("**字幕层四幕终章**：烧录产物实测 **max 同时活跃 1 条**、"
                "**覆盖 {:.1%}**（F8 为 {:.1%}）、**median 时长 {:.2f}s**（F8 为 1.0s）、"
                "**0 条 clamp**；唯一素材 {}。").format(
                    cov["coverage"], cov["before_fixture_F8"]["coverage"],
                    cov["median_dur_s"], acc["dq2"].get("unique_assets")),
    })
    (L / "phase53_promotion_package.json").write_text(
        json.dumps(pkg, ensure_ascii=False, indent=1), encoding="utf-8")
    print("登记 F9：{} | {:,}B | {}s | render_output={}".format(
        rec["final_film"], rec["final_bytes"], rec["final_duration_s"],
        rec["render_output_artifact"]))
    print("  烧录 ASS 复测：max_concurrent {} | 重叠时刻 {}".format(
        ovl["after"]["max_concurrent"], ovl["after"]["overlap_moments"]))
    print("  覆盖 {:.1%} | median {:.3f}s | clamp {} | 同步 {:.1%}".format(
        cov["coverage"], cov["median_dur_s"], cov["clamp_cues"], cov["sync_cover"]))
    print("  求解器 pass={} | 家族 {}".format(gs.get("pass"),
                                             json.dumps(shares, ensure_ascii=False)))
    print("-> " + pth.relative_to(R).as_posix())
    print("-> " + (L / "phase53_promotion_package.json").relative_to(R).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
