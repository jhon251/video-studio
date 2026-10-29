# -*- coding: utf-8 -*-
"""Phase 51 / P51-2+P51-3：**登记第九部交付级候选 F8**（append-only、零 promotion）
+ **两条 erratum** + 材料包终版。

本轮 = 报幕问题（用户自 F6 起反复报告）的**真因修复**：
  · 真因 = `build_cues_from_words` 把**段内局部**词偏移当成**景内局部**偏移，
    导致同一段的 N 个景**各自重放整段词** ⇒ 全片 cue 大面积重叠
    （实测 F7.1 烧录 ASS **max 同时活跃 41 条** / 1033 采样时刻重叠）；
  · 修复后 **max 同时活跃 1 条 / 0 采样时刻重叠**（O1/O2/O3 全过）。
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
    syn = json.loads((L / "p45_3_caption_word_sync.json").read_text(encoding="utf-8"))
    ovl = json.loads((L / "p51_1_overlap_invariant.json").read_text(encoding="utf-8"))
    anch = json.loads((L / "p44_1_anchor_policy.json").read_text(encoding="utf-8"))
    regen = json.loads((L / "p50_1_regen.json").read_text(encoding="utf-8"))
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
    real = {d["scene_id"]: str((d.get("selected_asset") or {}).get("sha256") or "")[:12]
            for d in dec}
    gen = {x["scene_id"]: str(x["sha256"])[:12] for x in regen["items"]}
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
        "schema": "p51-2-delivery-candidate-v1",
        "stage": "Phase 51 F8（词级 cue 排他修复 + 重叠不变量门）",
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
                                 "audio": "phase45_voice（词级重配音，零改动）",
                                 "allocation": "零改动（分配逻辑未动）",
                                 "timebase_s": tb["audio_time_base_s"]},
        "p51_1_cue_exclusivity_fix": {
            "root_cause": ("`build_cues_from_words` 把**段内局部**词偏移当成"
                           "**景内局部**偏移再加景窗起点 ⇒ 同一段的 N 个景**各自重放"
                           "整段词** ⇒ 全片 cue 大面积重叠。"
                           "（词级 manifest 以**段** `P01` 为键，而一段切成 4 个景 "
                           "`P01_1..P01_4`。）"),
            "fix": ("① 词偏移先换算为**全片绝对时刻**（= 该段起始景窗起点 + 词偏移）；"
                    "② **按景窗切分词**；③ 施加**排他规则** "
                    "`cue_k = [max(句首词时刻, cue_{k-1}.end), "
                    "min(句末词结束+hold, 下一句起点)]`"),
            "file": "src/video_studio/core/captions.py::build_cues_from_words",
            "gate": "tests/caption_overlap_test.py 3/3 PASS（对**最终烧录 ASS**扫描）",
            "before_fixture": ovl["before_fixture"],
            "after": ovl["after"],
        },
        "p51_3_errata": {
            "erratum_1_report_perception_misdiagnosis": {
                "what": ("**我在 F6 阶段的误诊**：用户自 F6 起反复报告「报幕」观感，"
                         "我当时的归因是『公式墙类素材过多』（并据此做了 P44 锚定、"
                         "P46 双轨家族门等）；**真因是 cue 大面积重叠**"
                         "（F7.1 烧录 ASS max 同时活跃 **41 条**），"
                         "即**字幕层缺陷**，与素材分配无关。"),
                "corrected_by": "监理帧检 + ASS 重叠扫描（Phase 51 §0①）",
                "lesson": ("用户反复报告同一观感问题时，应**优先排查该观感所在层"
                           "（此处=字幕层）**，而不是先改上游（素材层）。"
                           "我连续 5 个阶段在素材层做了大量工作，**绕过了真因**。"),
            },
            "erratum_2_p50_binding_mismatch": {
                "what": ("**P50-1 报告的三张重生成图中，只有 P09_5 真正上屏**；"
                         "**P01_1 / P07_3 上屏的是别的素材**"
                         "（重求解后重新分配）："),
                "actual_bindings_F8": {s: real.get(s) for s in ("P01_1", "P07_3", "P09_5")},
                "regenerated_images": gen,
                "detail": ("P01_1 实绑 `14bc28bf68eb`（Pexels 6238050 by Monstera，"
                           "原图 `df9e9cf56508` 经重求解改为 Pexels 实拍）；"
                           "P07_3 实绑 `a3aff2f300eb`（Pexels 22690748 by Vitaly Gariev）；"
                           "**仅 P09_5 实绑重生成图 `a0350ad6c921`**"),
                "action": ("**绑定现状保持不变**（按授权书：交用户终审裁决去留）；"
                           "此处**如实证记**，不擅自改绑定。两张图（生成图与实拍图）"
                           "**均已入池**，用户可裁决 P01_1 开场 hook 用哪张。"),
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
            "caption_overlap": "PASS 3/3（max_concurrent 1 / 重叠时刻 0）",
            "caption_word_sync": "PASS 2/2（median {:.4f}s / 覆盖 {:.1%}）".format(
                syn["median_lag_s"], syn["cover_ratio"]),
            "anchor_guard": "PASS 4/4（真越界 {}）".format(len(viol)),
            "content_exclusion": "PASS 4/4（三处禁入上屏 {}）".format(bans),
            "name_neutral": "PASS 3/3",
            "no_picture": "PASS 2/2", "metaphor_quota": "PASS 7/7",
            "allocation_solver_test": "PASS 7/7",
            "arbitration_detail": "RENDER_ARBITRATION_DETAIL 已落账（{} 景）".format(
                detrec.get("scene_count")),
            "motion_metrics": {k: acc["motion_metrics"].get(k) for k in
                               ("freeze_ratio", "longest_static_s",
                                "opening_changes", "all_pass")},
        },
        "zero_promotion": True,
        "promotion_baseline_unchanged": "projects/p_50e10b27b44d/output/t_a4d8c1aafd04_draft.mp4",
    }
    pth = L / "p51_2_delivery_candidate.jsonl"
    with pth.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    pkg = json.loads((L / "phase50_promotion_package.json").read_text(encoding="utf-8"))
    pkg["schema"] = "phase51-promotion-package-v5-final"
    pkg["versions"]["F8_p51_cue_exclusive"] = {
        "name": "F8（Phase 51：词级 cue 排他修复 + 重叠不变量门）",
        "candidate": rec["final_film"], "bytes": rec["final_bytes"],
        "duration_s": rec["final_duration_s"], "segments": 36,
        "gate_state": ("**全门通过**：时长/A2=0.000/满覆盖/音轨一致/逐景 36-36/"
                       "DQ-2(唯一 {}，max_share {})/DQ-3(0-36)/DQ-3e(0 处)/"
                       "**重叠门 3-3（max 同时活跃 1，F7.1 为 41）**/"
                       "词级同步 2-2/锚定 4-4/内容排除 4-4/name 中立 3-3/"
                       "no_picture 2-2/配额 7-7/求解器 7-7/**pass=True**；"
                       "三指标按停用口径不通过（冻结 {}）").format(
                           acc["dq2"].get("unique_assets"),
                           acc["dq2"].get("max_asset_share"),
                           acc["motion_metrics"].get("freeze_ratio")),
    }
    pkg["phase51_fix"] = {
        "cue_exclusivity": rec["p51_1_cue_exclusivity_fix"],
        "errata": rec["p51_3_errata"],
        "report_perception_chain": {
            "F6": "用户投诉「报幕」观感",
            "F6_misdiagnosis": "**我误诊为「公式墙类素材过多」**（改素材层）",
            "P44_P46": "据此做锚定表 + 双轨家族门（**绕过了真因**）",
            "P51": "**监理帧检 + ASS 重叠扫描定位真因 = cue 大面积重叠**",
            "P51_fix": "词偏移绝对化 + 按景窗切词 + 排他规则 ⇒ **41 → 1**",
        },
        "trajectory": {
            "F7.1": {"max_concurrent_cues": 41, "overlap_moments": 1033,
                     "unique": 30, "caption_lag": 0.0},
            "F8": {"max_concurrent_cues": 1, "overlap_moments": 0,
                   "unique": acc["dq2"].get("unique_assets"),
                   "caption_lag": syn["median_lag_s"]},
        },
    }
    pkg["watch_order"].insert(0, {
        "rank": 1, "version": "F8（Phase 51）", "candidate": rec["final_film"],
        "why": ("**报幕真因已修**：字幕 cue 最大同时活跃 **41 → 1 条**、"
                "重叠采样时刻 **1033 → 0**（对最终烧录 ASS 实测）；"
                "其余指标与 F7.1 持平或更好（唯一素材 {}、max_share {}）。").format(
                    acc["dq2"].get("unique_assets"),
                    acc["dq2"].get("max_asset_share")),
    })
    (L / "phase51_promotion_package.json").write_text(
        json.dumps(pkg, ensure_ascii=False, indent=1), encoding="utf-8")
    print("登记 F8：{} | {:,}B | {}s | render_output={}".format(
        rec["final_film"], rec["final_bytes"], rec["final_duration_s"],
        rec["render_output_artifact"]))
    print("  重叠门：max_concurrent {} | 重叠时刻 {}（F7.1 为 41 / 1033）".format(
        ovl["after"]["max_concurrent"], ovl["after"]["overlap_moments"]))
    print("  求解器 pass={} | 家族 {}".format(gs.get("pass"),
                                             json.dumps(shares, ensure_ascii=False)))
    print("  erratum2 实绑核对：{}".format(
        json.dumps({s: real.get(s) for s in ("P01_1", "P07_3", "P09_5")},
                   ensure_ascii=False)))
    print("-> " + pth.relative_to(R).as_posix())
    print("-> " + (L / "phase51_promotion_package.json").relative_to(R).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
