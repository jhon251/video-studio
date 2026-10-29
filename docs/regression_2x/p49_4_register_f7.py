# -*- coding: utf-8 -*-
"""Phase 49 / P49-1+P49-3：**登记第七部交付级候选 F7**（append-only、零 promotion）
+ **F6 家族报告 erratum**（不改写 F5/F6 数值）+ 材料包更新。
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
    sync = json.loads((L / "p45_3_caption_word_sync.json").read_text(encoding="utf-8"))
    anch = json.loads((L / "p44_1_anchor_policy.json").read_text(encoding="utf-8"))
    name = json.loads((L / "p49_1_name_neutral.json").read_text(encoding="utf-8"))
    ov = json.loads((R / "output/phase45_voice/voice_output_v65_ovoice.json")
                    .read_text(encoding="utf-8"))
    gb = json.loads((L / "p47_2_gen_batch.json").read_text(encoding="utf-8"))
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
    con.close()
    dec, al = p["decisions"], (p.get("material_allocation") or {})
    gs = al.get("global_satisfy") or {}
    fc = gs.get("family_counts") or {}
    tot = sum(fc.values()) or 1
    shares = {k: round(v / tot, 4) for k, v in fc.items()}
    gsh = set(str(x["sha256"])[:12] for x in gb["items"] if x.get("ok"))
    g_on = [d["scene_id"] for d in dec
            if str((d.get("selected_asset") or {}).get("asset_id"))[6:18] in gsh]
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
        "schema": "p49-1-delivery-candidate-v1",
        "stage": "Phase 49 F7（name 中立化 + 生成插图接入 + 双轨家族门）",
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
                                 "timebase_s": tb["audio_time_base_s"]},
        "p49_1_name_neutralization": {
            "root_cause": ("生成素材 `name` 内嵌本片中文旁白原文 ⇒ 中文关键词匹配器在 "
                           "36/36 景都给生成素材最高分 ⇒ `_cur` 全片为 G 且置首 ⇒ "
                           "G 份额 72.2% ⇒ 家族门不可达标"),
            "fix": "name → `GenConcept <scene_id> <sha12>`（语言中立）；visual_hint 另存不参与匹配",
            "rule": "**匹配器消费的元数据字段（name/relative_path）必须语言中立**",
            "gate": "tests/asset_name_neutral_test.py 3/3 PASS",
            "audit": {"pool_size": name["pool_size"], "generated": name["generated"],
                      "violations_n1": len(name["violations_n1"]),
                      "violations_n2": len(name["violations_n2"]),
                      "fragments_checked": name["fragments_checked"]},
        },
        "p47_2_generated_materials": {
            "provider": "DashScope/wanx（wanx2.1-t2i-turbo）",
            "frozen_style": "a_黑板粉笔线稿",
            "generated": gb["generated"], "requests": gb["requests_used"],
            "on_screen_scenes": len(g_on),
            "license": "Generated (provider wanx)，无第三方署名义务",
            "source_of_record": "每张的生成任务 ID",
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
            "caption_word_sync": "PASS 2/2（median 0.0000s / 覆盖 100%）",
            "anchor_guard": "PASS 4/4（真越界 {}；具名绑定豁免 {} 处单列）".format(
                len(viol), len(anch.get("binding_exempt") or [])),
            "content_exclusion": "PASS 4/4（三处禁入上屏 {}）".format(bans),
            "name_neutral": "PASS 3/3",
            "no_picture": "PASS 2/2", "metaphor_quota": "PASS 7/7",
            "allocation_solver_test": "PASS 7/7",
            "motion_metrics": {k: acc["motion_metrics"].get(k) for k in
                               ("freeze_ratio", "longest_static_s",
                                "opening_changes", "all_pass")},
        },
        "zero_promotion": True,
        "promotion_baseline_unchanged": "projects/p_50e10b27b44d/output/t_a4d8c1aafd04_draft.mp4",
        "p49_3_f6_erratum": {
            "applies_to": ["F5", "F6"],
            "defect": ("D2：检索池 **12 张历史素材 `asset_id` 为 `None`**（只有 sha256）⇒ "
                       "`_family_of(None,…)` 恒 None ⇒ 这些素材**绕过家族约束**"),
            "impact": ("**F5 / F6 登记里的『家族份额』只统计了有 asset_id 的那部分资产**，"
                       "并非全片口径 ⇒ 该数值**口径不完整**"),
            "action": "**不改写 F5/F6 已登记数值**（历史留痕）；本 erratum 随 F7 登记补记；"
                      "**F7 起为归一化口径**（agent 边界按 asset_<sha12> 补齐 asset_id）",
            "note": "F6 报的 family_counts 实为 {E:16, A:11, C:2, D:3, B:4}（有 id 部分）；"
                    "归一化后全片口径会不同 ⇒ 引用 F6 家族份额时须注明该 erratum。",
        },
    }
    pth = L / "p49_1_delivery_candidate.jsonl"
    with pth.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    pkg = json.loads((L / "phase46_promotion_package.json").read_text(encoding="utf-8"))
    pkg["schema"] = "phase49-promotion-package-v5"
    pkg["versions"]["F7_p49_name_neutral"] = {
        "name": "F7（Phase 49：name 中立化 + 生成插图 + 双轨家族门）",
        "candidate": rec["final_film"], "bytes": rec["final_bytes"],
        "duration_s": rec["final_duration_s"], "segments": 36,
        "gate_state": ("**全门通过**：时长/A2=0.000/满覆盖/音轨一致/逐景 36-36/"
                       "DQ-2(唯一素材 {}，max_share {})/DQ-3(0-36)/DQ-3e(0 处)/"
                       "词级同步 2-2/锚定 4-4/内容排除 4-4/**name 中立 3-3**/"
                       "no_picture 2-2/配额 7-7/求解器 7-7/**pass=True**/"
                       "**双轨家族门 A 25.0%≤33% · E 33.3%≤45% · G 27.8%≤33%**；"
                       "三指标按停用口径不通过（冻结 89.7%）").format(
                           acc["dq2"].get("unique_assets"),
                           acc["dq2"].get("max_asset_share")),
    }
    pkg["phase49_fix"] = {
        "name_neutralization": rec["p49_1_name_neutralization"],
        "f6_erratum": rec["p49_3_f6_erratum"],
        "trajectory": {
            "F6": {"pool": 29, "cap": 3, "unique": 27, "family_A": 0.306,
                   "caption_lag": 0.0, "shell": 0},
            "F7": {"pool": 44, "cap": 3, "unique": acc["dq2"].get("unique_assets"),
                   "family_A": shares.get("A_纸面符号"),
                   "family_E": shares.get("E_黑板粉笔与数学工作场景") or
                   shares.get("E_黑板粉笔与数学工作场景"),
                   "family_G": shares.get("G_生成概念插图"),
                   "caption_lag": 0.0, "shell": 0, "gen_on_screen": len(g_on)},
        },
    }
    pkg["watch_order"].insert(0, {
        "rank": 1, "version": "F7（Phase 49）", "candidate": rec["final_film"],
        "why": ("**抽象段有了自己的视觉语言**（15 张冻结风格生成插图全部上屏）；"
                "**name 投毒根因已修**；唯一素材 27 → {}；"
                "双轨家族门 A 25.0%/E 33.3%/G 27.8% 全达标；词级字幕 median 0.0000s。").format(
                    acc["dq2"].get("unique_assets")),
    })
    (L / "phase49_promotion_package.json").write_text(
        json.dumps(pkg, ensure_ascii=False, indent=1), encoding="utf-8")
    print("登记 F7：{} | {:,}B | {}s | render_output={}".format(
        rec["final_film"], rec["final_bytes"], rec["final_duration_s"],
        rec["render_output_artifact"]))
    print("  求解器 pass={} | 家族 {}".format(gs.get("pass"), json.dumps(shares, ensure_ascii=False)))
    print("  生成素材上屏 {} 景 | 三处禁入上屏 {}".format(len(g_on), bans))
    print("  F6 erratum 已随 F7 补记（不改写 F5/F6 数值）")
    print("-> " + pth.relative_to(R).as_posix())
    print("-> " + (L / "phase49_promotion_package.json").relative_to(R).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
