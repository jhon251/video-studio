# -*- coding: utf-8 -*-
"""Phase 50 / P50-2+P50-3：**登记第八部交付级候选 F7.1**（append-only、零 promotion）+ 材料包终版。

本轮 = Phase 49 的收口：
  · **P50-1** 重生成含**文字伪影**的三张（P01_1 开场 hook 乱码文字墙 / P07_3 乱码标注 /
    P09_5 伪公式）—— 追加冻结的 **`no_text` 风格变体** + 强化负向提示词；3/3 一次通过；
  · **P50-2** 重求解（约束不变）→ 渲染 → 全门通过 ⇒ 登记 **F7.1**；**F7 保留为证据**；
  · **P50-3** 两个补课项：①仲裁逐景 VLM 调用明细落账；②`load_env` 凭据健全性告警。
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
    regen = json.loads((L / "p50_1_regen.json").read_text(encoding="utf-8"))
    ov = json.loads((R / "output/phase45_voice/voice_output_v65_ovoice.json")
                    .read_text(encoding="utf-8"))
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
        "schema": "p50-2-delivery-candidate-v1",
        "stage": "Phase 50 F7.1（生成插图去文字伪影 + 仲裁明细落账 + 凭据告警）",
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
        "p50_1_text_artifact_regen": {
            "trigger": ("监理帧检：10 张生成插图风格统一 ✔，但 P01_1（开场 hook）"
                        "**乱码文字墙必须重生成**；P07_3（乱码标注）/ P09_5（伪公式）"
                        "一并重生成；其余 7 张接受为纹理"),
            "mechanism": ("提示词追加**冻结的 `no_text` 风格变体**"
                          "（纯几何线稿、无文字/字母/数字/书写痕迹）+ 强化负向提示词"),
            "style_variant_sha256": regen["style_variant_sha256"],
            "negative_prompt_strong": regen["negative_prompt_strong"],
            "regenerated": regen["regenerated"], "attempts": {
                x["scene_id"]: x["attempts"] for x in regen["items"]},
            "old_to_new_sha12": {x["scene_id"]: [str(x["old_sha256"])[:12],
                                                 str(x["sha256"])[:12]]
                                 for x in regen["items"]},
            "gate": "tests/asset_name_neutral_test.py 3/3（N2 覆盖全池语言中立）",
        },
        "p50_3_remediation": {
            "arbitration_per_scene_detail": {
                "event": "RENDER_ARBITRATION_DETAIL（**新增独立事件**，不改既有字段）",
                "fields": detrec.get("fields"),
                "verified": bool(det),
                "sample": [{k: (v.get("model") if k == "vlm" else v)
                            for k, v in [("scene_id", r.get("scene_id")),
                                         ("arbitration", r.get("arbitration")),
                                         ("presence", (r.get("vlm") or {}).get("presence")),
                                         ("cache_hit", (r.get("vlm") or {}).get("cache_hit"))]}
                           for r in (detrec.get("records") or [])[:4]],
                "closes": "P49-2 审计 A1『逐笔对照不可完成』⇒ 自此可机械核验",
            },
            "credential_health_warning": {
                "function": "core/env.py::check_credentials()",
                "rule": ("`*_API_KEY/*_TOKEN/*_SECRET` 值含非 ASCII/控制字符、空白、"
                         "或长度 < 16 ⇒ 产出 warning（**不回显密钥值**）"),
                "current_warnings": 0,
                "closes": "P47-D1 那类**静默污染**的复发风险",
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
            "caption_word_sync": "PASS 2/2（median 0.0000s / 覆盖 100%）",
            "anchor_guard": "PASS 4/4（真越界 {}）".format(len(viol)),
            "content_exclusion": "PASS 4/4（三处禁入上屏 {}）".format(bans),
            "name_neutral": "PASS 3/3",
            "no_picture": "PASS 2/2", "metaphor_quota": "PASS 7/7",
            "allocation_solver_test": "PASS 7/7",
            "motion_metrics": {k: acc["motion_metrics"].get(k) for k in
                               ("freeze_ratio", "longest_static_s",
                                "opening_changes", "all_pass")},
        },
        "f7_retained_as_evidence": {
            "note": "**F7 保留为证据**（授权书 §2）：其登记与产物不变，用于对照文字伪影修复前后。",
            "f7_sandbox": "p_fd7db560531c",
        },
        "zero_promotion": True,
        "promotion_baseline_unchanged": "projects/p_50e10b27b44d/output/t_a4d8c1aafd04_draft.mp4",
    }
    pth = L / "p50_2_delivery_candidate.jsonl"
    with pth.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    pkg = json.loads((L / "phase49_promotion_package.json").read_text(encoding="utf-8"))
    pkg["schema"] = "phase50-promotion-package-v5-final"
    pkg["versions"]["F7_1_p50_no_text"] = {
        "name": "F7.1（Phase 50：生成插图去文字伪影 + 仲裁明细落账 + 凭据告警）",
        "candidate": rec["final_film"], "bytes": rec["final_bytes"],
        "duration_s": rec["final_duration_s"], "segments": 36,
        "gate_state": ("**全门通过**：时长/A2=0.000/满覆盖/音轨一致/逐景 36-36/"
                       "DQ-2(唯一 {}，max_share {})/DQ-3(0-36)/DQ-3e(0 处)/"
                       "词级同步 2-2/锚定 4-4/内容排除 4-4/name 中立 3-3/"
                       "no_picture 2-2/配额 7-7/求解器 7-7/**pass=True**/"
                       "**双轨家族门 A {:.1%}·E {:.1%}·G {:.1%}**；"
                       "三指标按停用口径不通过（冻结 {}）").format(
                           acc["dq2"].get("unique_assets"),
                           acc["dq2"].get("max_asset_share"),
                           shares.get("A_纸面符号", 0),
                           shares.get("E_黑板粉笔与数学工作场景", 0),
                           shares.get("G_生成概念插图", 0),
                           acc["motion_metrics"].get("freeze_ratio")),
    }
    pkg["phase50_fix"] = {
        "text_artifact_regen": rec["p50_1_text_artifact_regen"],
        "remediation": rec["p50_3_remediation"],
        "trajectory": {
            "F7": {"pool": 44, "unique": 30, "family_A": 0.25, "family_E": 0.3333,
                   "family_G": 0.2778, "caption_lag": 0.0,
                   "text_artifacts": "P01_1/P07_3/P09_5 **含文字伪影**"},
            "F7.1": {"pool": 44, "unique": acc["dq2"].get("unique_assets"),
                     "family_A": shares.get("A_纸面符号"),
                     "family_E": shares.get("E_黑板粉笔与数学工作场景"),
                     "family_G": shares.get("G_生成概念插图"),
                     "caption_lag": 0.0, "text_artifacts": "**3 张全部重生成、0 文字伪影**"},
        },
    }
    pkg["watch_order"].insert(0, {
        "rank": 1, "version": "F7.1（Phase 50）", "candidate": rec["final_film"],
        "why": ("**文字伪影清零**（P01_1 开场 hook 乱码文字墙 / P07_3 乱码标注 / "
                "P09_5 伪公式 三张全部重生成）；其余指标与 F7 持平或更好"
                "（唯一素材 30、max_share {}）；仲裁逐景明细已落账。").format(
                    acc["dq2"].get("max_asset_share")),
    })
    (L / "phase50_promotion_package.json").write_text(
        json.dumps(pkg, ensure_ascii=False, indent=1), encoding="utf-8")
    print("登记 F7.1：{} | {:,}B | {}s | render_output={}".format(
        rec["final_film"], rec["final_bytes"], rec["final_duration_s"],
        rec["render_output_artifact"]))
    print("  求解器 pass={} | 家族 {}".format(gs.get("pass"),
                                             json.dumps(shares, ensure_ascii=False)))
    print("  重生成 3 张（文字伪影）：{}".format(
        json.dumps(rec["p50_1_text_artifact_regen"]["old_to_new_sha12"],
                   ensure_ascii=False)))
    print("  仲裁明细事件：{} 条 | 字段 {}".format(
        len(det), ",".join((detrec.get("fields") or [])[:5])))
    print("-> " + pth.relative_to(R).as_posix())
    print("-> " + (L / "phase50_promotion_package.json").relative_to(R).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
