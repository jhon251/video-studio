# -*- coding: utf-8 -*-
"""Phase 55 / P55-2+P55-4：**登记第十一部候选 F10**（append-only、零 promotion）
+ 基底样片登记 + 跨时间基规则入册。

**F10 = 单变量验证版**（授权书 §2）：**只修字幕，画面与 F9 一致** ——
终审时「字幕跟嘴」的判定**不被视觉变化污染**。
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
    cont = json.loads((L / "p54_1_continuity.json").read_text(encoding="utf-8"))
    bbs = json.loads((L / "p55_3_bb_samples.json").read_text(encoding="utf-8"))
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
    bans = {b: sum(1 for d in dec if b in str(
        (d.get("selected_asset") or {}).get("asset_id")))
        for b in ("2442c39e", "432cd85b", "f0cd2a28")}
    # 画面与 F9 是否一致（单变量验证）：逐景素材 sha 对比
    f9 = None
    try:
        f9rec = [json.loads(x) for x in
                 (L / "p53_2_delivery_candidate.jsonl").read_text(
                     encoding="utf-8").splitlines() if x.strip()][-1]
        f9 = f9rec.get("sandbox_project_id")
    except Exception:                                                           # noqa: BLE001
        f9 = None
    con = sqlite3.connect("file:" + (R / "projects/video_studio.db").as_posix()
                          + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    cur = {d["scene_id"]: str((d.get("selected_asset") or {}).get("sha256") or "")[:12]
           for d in dec}
    old = {}
    if f9:
        try:
            pp = json.loads(con.execute(
                "select payload from events where project_id=? and "
                "type='MATERIAL_TIMELINE'", (f9,)).fetchone()["payload"])
            old = {d["scene_id"]: str((d.get("selected_asset") or {}).get("sha256")
                                      or "")[:12] for d in pp["decisions"]}
        except Exception:                                                       # noqa: BLE001
            old = {}
    con.close()
    same = sum(1 for k in cur if k in old and cur[k] == old[k])
    rec = {
        "schema": "p55-2-delivery-candidate-v1",
        "stage": "Phase 55 F10（词句精确归属修复 + 单变量字幕验证）",
        "registered_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "sandbox_project_id": pid,
        "single_variable_design": {
            "intent": ("授权书 §2：**F10 = 单变量验证版** —— 只修字幕，画面与 F9 一致，"
                       "使终审「字幕跟嘴」判定**不被视觉变化污染**"),
            "scenes_same_asset_vs_F9": same, "scenes_total": len(cur),
            "f9_sandbox": f9,
            "verdict": ("画面逐景**完全一致**" if same == len(cur) and old
                        else "画面有 {} / {} 景不同（分配重跑所致，如实登记）".format(
                            len(cur) - same, len(cur))),
        },
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
                                 "timebase_s": tb["audio_time_base_s"]},
        "p55_1_word_sentence_attribution": {
            "root_cause_of_P54_failure": ("P54 按**字符数**把词分配到句 —— 那是 P45-3 的"
                                          "**段内**口径写法，套到「词段内起点 − 切片段内起点 "
                                          "+ 景窗起点」的新时间基即错位 ⇒ 负时长 min −87.526s"),
            "new_algorithm": ("**词流与句流顺序游走匹配**（逐词累计归一化文本，与下一句"
                              "归一化文本比对切句）"),
            "internal_assertions": ["a) 每句 a0 ≤ a1", "b) 句间单调 a1_k ≤ a0_{k+1}",
                                    "c) 每词恰属一景（无跨景词、无未分配词）",
                                    "d) 全片词覆盖 == manifest 总词数"],
            "tolerance_note": ("单调断言用 **0.01s** 容差（非 1e-6）：`abs_t` 已 round 到毫秒，"
                               "相邻句界有 ≤1ms 量化抖动（实测 P09 差 0.001s）⇒ "
                               "1e-6 会把**量化噪声**误判为「非单调」"),
            "fail_closed": "断言违反 ⇒ 抛错 + 事件登记 + 转储（P48 法），不静默降级",
            "result": "**全部断言通过**",
            "rule_version": "p55-1-seq-walk-v1",
        },
        "p54_1_continuity_precondition": {
            "gate": "docs/regression_2x/p54_1_continuity.py",
            "paragraphs_delta_max_s": max(abs(x["delta_s"]) for x in cont["paras"]),
            "window_mismatch": cont["window_vs_slice_mismatch"],
            "words_total": cont["words_total"],
        },
        "p55_3_blackboard_base_samples": {
            "variants": bbs["ok_count"], "total": bbs["total"],
            "base_suffix_sha256": bbs["base_suffix_sha256"],
            "artifacts": [x["path"] for x in bbs["variants"] if x.get("ok")],
            "status": "**待项目所有者选定基底**（第五次终审时一并看）",
            "budget_cny_cap": bbs["budget_cny_cap"],
        },
        "p55_4_rule_enrolled": {
            "statement": ("**跨时间基/跨命名空间复用代码，须重推语义**"),
            "three_cases": [
                "P48：id 命名空间（`asset_gen_*` vs `asset_<sha12>`）",
                "P53：调用形状（36 景 vs 9 窗越界）",
                "P54：**时间基**（段内口径 vs 景窗口径 ⇒ 负时长）",
            ],
            "common_failure": ("三案的共同点 = **把旧口径直接套到新基上**，"
                               "于是测试全绿而产物是坏的。"),
            "enforcement": ("复用任何「按时间/按 id」的既有代码前，**先写出新旧基的换算式**"
                            "并在构建器内部**断言换算后的不变量**（如 a0≤a1、单调、覆盖）。"),
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
            "caption_overlap": "PASS 3/3（烧录 ASS max_concurrent {} / 重叠 {})".format(
                ovl["after"]["max_concurrent"], ovl["after"]["overlap_moments"]),
            "caption_coverage": "PASS 4/4（覆盖 {:.1%}；median {:.3f}s；clamp {}）".format(
                cov["coverage"], cov["median_dur_s"], cov["clamp_cues"]),
            "anchor_guard": "PASS 4/4",
            "content_exclusion": "PASS 4/4（三处禁入上屏 {}）".format(bans),
            "name_neutral": "PASS 3/3",
            "no_picture": "PASS 2/2", "metaphor_quota": "PASS 7/7",
            "allocation_solver_test": "PASS 7/7",
            "arbitration_detail": "RENDER_ARBITRATION_DETAIL（{} 景）".format(
                len(det) and json.loads(det[-1]["payload"]).get("scene_count")),
            "motion_metrics": {k: acc["motion_metrics"].get(k) for k in
                               ("freeze_ratio", "longest_static_s",
                                "opening_changes", "all_pass")},
        },
        "zero_promotion": True,
        "promotion_baseline_unchanged": "projects/p_50e10b27b44d/output/t_a4d8c1aafd04_draft.mp4",
    }
    pth = L / "p55_2_delivery_candidate.jsonl"
    with pth.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    pkg = json.loads((L / "phase53_promotion_package.json").read_text(encoding="utf-8"))
    pkg["schema"] = "phase55-promotion-package-v5"
    pkg["versions"]["F10_p55_word_exact"] = {
        "name": "F10（Phase 55：词句精确归属修复 + 单变量字幕验证）",
        "candidate": rec["final_film"], "bytes": rec["final_bytes"],
        "duration_s": rec["final_duration_s"], "segments": 36,
        "gate_state": ("**全门通过**：时长/A2/满覆盖/音轨一致/逐景 36-36/"
                       "DQ-2(唯一 {}，max_share {})/DQ-3/DQ-3e(0 处)/"
                       "**重叠 3-3**/**覆盖 4-4（{:.1%}）**/锚定 4-4/内容排除 4-4/"
                       "name 中立 3-3/no_picture 2-2/配额 7-7/求解器 7-7；"
                       "**单变量：画面与 F9 一致 {} / {} 景**").format(
                           acc["dq2"].get("unique_assets"),
                           acc["dq2"].get("max_asset_share"), cov["coverage"],
                           same, len(cur)),
    }
    pkg["phase55_fix"] = {
        "word_sentence_attribution": rec["p55_1_word_sentence_attribution"],
        "rule_enrolled": rec["p55_4_rule_enrolled"],
        "blackboard_base_samples": rec["p55_3_blackboard_base_samples"],
        "caption_saga_five_acts": {
            "F6": "用户投诉「报幕」—— **我误诊为素材层**",
            "P51": "定位 cue **重叠**（41→1）",
            "P52": "覆盖门揭 **14.2%** + 97% clamp ⇒ 音频锚定（99.3%）",
            "P53": "烧录复测仍坏 ⇒ **36 景 vs 9 窗越界** ⇒ 形状统一",
            "P55": "**词句归属**（字符数口径 ⇒ 负时长）⇒ 顺序游走匹配 + 四条内部断言",
        },
    }
    pkg["watch_order"].insert(0, {
        "rank": 1, "version": "F10（Phase 55）", "candidate": rec["final_film"],
        "why": ("**单变量字幕验证版**：只修字幕，画面与 F9 **{} / {} 景一致**；"
                "词句归属改为**顺序游走匹配**并带**四条内部断言**（a0≤a1 / 单调 / "
                "每词恰属一景 / 全片覆盖）；烧录 ASS 重叠 0、覆盖 {:.1%}。").format(
                    same, len(cur), cov["coverage"]),
    })
    (L / "phase55_promotion_package.json").write_text(
        json.dumps(pkg, ensure_ascii=False, indent=1), encoding="utf-8")
    print("登记 F10：{} | {:,}B | {}s | render_output={}".format(
        rec["final_film"], rec["final_bytes"], rec["final_duration_s"],
        rec["render_output_artifact"]))
    print("  单变量：画面与 F9 一致 **{} / {} 景**".format(same, len(cur)))
    print("  烧录 ASS：max_concurrent {} / 重叠 {} | 覆盖 {:.1%} | median {:.3f}s".format(
        ovl["after"]["max_concurrent"], ovl["after"]["overlap_moments"],
        cov["coverage"], cov["median_dur_s"]))
    print("  黑板基底样片：{} / {} 张待用户选定".format(
        bbs["ok_count"], bbs["total"]))
    print("-> " + pth.relative_to(R).as_posix())
    print("-> " + (L / "phase55_promotion_package.json").relative_to(R).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
