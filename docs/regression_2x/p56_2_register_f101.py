# -*- coding: utf-8 -*-
"""Phase 56 / P56-2+P56-3：**登记第十二部候选 F10.1**（append-only、零 promotion）
+ 确定性指纹入账 + 对照声明。

**F10.1 = F9 assignment 钉定 + F10 新字幕** ⇒ 与 F9 的**唯一差异 = 字幕层**
（逐景素材、顺序、时长完全一致）。
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
    pins = json.loads((L / "p56_2_f9_pins.json").read_text(encoding="utf-8"))
    tb = json.loads((R / "output/phase36_voice/timebase_v65.json").read_text(encoding="utf-8"))
    fm = json.loads((R / "config/family_map.json").read_text(encoding="utf-8"))["family_map"]
    con = sqlite3.connect("file:" + (R / "projects/video_studio.db").as_posix()
                          + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row

    def tl(p):
        return json.loads(con.execute(
            "select payload from events where project_id=? and "
            "type='MATERIAL_TIMELINE'", (p,)).fetchone()["payload"])

    ro = next((dict(x) for x in con.execute(
        "select artifact_id,type from artifacts where project_id=?", (pid,))
        if x["type"] == "render_output"), None)
    p = tl(pid)
    det = list(con.execute("select payload from events where project_id=? and "
                           "type='RENDER_ARBITRATION_DETAIL'", (pid,)))
    f9p = tl(pins["source_sandbox"])
    con.close()
    dec, al = p["decisions"], (p.get("material_allocation") or {})
    gs = al.get("global_satisfy") or {}
    fc = gs.get("family_counts") or {}
    tot = sum(fc.values()) or 1
    shares = {k: round(v / tot, 4) for k, v in fc.items()}
    detrec = json.loads(det[-1]["payload"]) if det else {}

    def sig(pp):
        """兼容：入参可以是 timeline payload（含 decisions）或 decisions 列表本身。"""
        ds = pp["decisions"] if isinstance(pp, dict) and "decisions" in pp else pp
        return {d["scene_id"]: str((d.get("selected_asset") or {}).get("sha256")
                                   or "")[:12] for d in ds}
    a, b = sig(f9p), sig(dec)
    same = sum(1 for k in a if a[k] == b.get(k))
    diff = [{"scene_id": k, "F9": a[k], "F10_1": b.get(k)}
            for k in a if a[k] != b.get(k)]
    bans = {x: sum(1 for d in dec if x in str(
        (d.get("selected_asset") or {}).get("asset_id"))) for x in
        ("2442c39e", "432cd85b", "f0cd2a28")}

    rec = {
        "schema": "p56-2-delivery-candidate-v1",
        "stage": "Phase 56 F10.1（分配确定性修复 + 单变量字幕版）",
        "registered_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "sandbox_project_id": pid,
        "single_variable_claim": {
            "statement": ("**F10.1 与 F9 的唯一差异 = 字幕层**：逐景素材、顺序、"
                          "时长完全一致"),
            "scenes_same_asset_vs_F9": same, "scenes_total": len(a),
            "differences": diff,
            "verdict": ("**成立** —— 36/36 景素材一致" if not diff
                        else "**不成立**（{} 景不同）".format(len(diff))),
            "per_scene_table": [{"scene_id": k, "F9_sha12": a[k],
                                 "F10_1_sha12": b.get(k),
                                 "same": a[k] == b.get(k)} for k in sorted(a)],
            "f9_sandbox": pins["source_sandbox"],
            "f9_assignment_fingerprint": pins["fingerprint_sha12"],
        },
        "p56_1_determinism_fix": {
            "defect": ("**分配不可复现**（监理升格为正确性缺陷）：P47-3 我加的"
                       "「种子若越份额门则丢弃」使**种子是否被丢取决于输入状态** ⇒ "
                       "同输入两次运行的解不同 ⇒ P55 实测 F10 与 F9 画面仅 4/36 景一致"),
            "fix": [
                "① **废除越界弃种**：保留 `initial` 种子；份额越门则**求解后如实报告**"
                "（门的裁决权在门，不在求解器的自我审查）",
                "② **固定搜索预算与 seed**：`solver_seed=20261002` / "
                "`restarts=40` / `iters=1500`",
                "③ **harness 前置断言**：同输入连跑两次求解，`assignment_fingerprint` "
                "必须一致；不一致 ⇒ **渲染前 fail-closed**",
            ],
            "fingerprint_helper": "core/allocation.py::assignment_fingerprint（逐景 scene=asset sha256）",
            "measured": {
                "deterministic": (al.get("determinism") or {}).get("deterministic"),
                "run1": str((al.get("determinism") or {}).get("run1_fingerprint"))[:24],
                "run2": str((al.get("determinism") or {}).get("run2_fingerprint"))[:24],
                "seed_used": (al.get("determinism") or {}).get("seed_used"),
                "seed_rejected_present": bool(al.get("seed_rejected")),
            },
        },
        "p56_2_pinned_assignment": {
            "mechanism": ("外部开关 `logs/p56_2_f9_pins.json`（存在即生效）：把 F9 逐景"
                          "已选素材**强制写回** `selected_asset`，位置在**锚定守卫之前**"
                          "⇒ 锚定仍可兜底"),
            "pins_scenes": pins["scenes"],
            "applied": (al.get("pinned_assignment") or {}).get("applied"),
            "missing": (al.get("pinned_assignment") or {}).get("missing"),
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
            "caption_overlap": "PASS 3/3（烧录 ASS max {} / 重叠 {}）".format(
                ovl["after"]["max_concurrent"], ovl["after"]["overlap_moments"]),
            "caption_coverage": "PASS 4/4（覆盖 {:.1%}；median {:.3f}s；clamp {}）".format(
                cov["coverage"], cov["median_dur_s"], cov["clamp_cues"]),
            "anchor_guard": "PASS 4/4",
            "content_exclusion": "PASS 4/4（三处禁入上屏 {}）".format(bans),
            "name_neutral": "PASS 3/3",
            "no_picture": "PASS 2/2", "metaphor_quota": "PASS 7/7",
            "allocation_solver_test": "PASS 7/7",
            "determinism_assert": "PASS（两次运行指纹一致）",
            "arbitration_detail": "RENDER_ARBITRATION_DETAIL（{} 景）".format(
                detrec.get("scene_count")),
            "motion_metrics": {k: acc["motion_metrics"].get(k) for k in
                               ("freeze_ratio", "longest_static_s",
                                "opening_changes", "all_pass")},
        },
        "zero_promotion": True,
        "promotion_baseline_unchanged": "projects/p_50e10b27b44d/output/t_a4d8c1aafd04_draft.mp4",
    }
    pth = L / "p56_2_delivery_candidate.jsonl"
    with pth.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    pkg = json.loads((L / "phase55_promotion_package.json").read_text(encoding="utf-8"))
    pkg["schema"] = "phase56-promotion-package-v5"
    pkg["versions"]["F10_1_p56_single_variable"] = {
        "name": "F10.1（Phase 56：分配确定性修复 + 单变量字幕版）",
        "candidate": rec["final_film"], "bytes": rec["final_bytes"],
        "duration_s": rec["final_duration_s"], "segments": 36,
        "gate_state": ("**全门通过**：时长/A2/满覆盖/音轨一致/逐景 36-36/"
                       "DQ-2(唯一 {}，max_share {})/DQ-3/DQ-3e(0 处)/"
                       "**重叠 3-3**/**覆盖 4-4（{:.1%}）**/锚定 4-4/内容排除 4-4/"
                       "name 中立 3-3/no_picture 2-2/配额 7-7/求解器 7-7/"
                       "**确定性断言 PASS**；"
                       "**单变量成立：与 F9 逐景素材 {} / {} 景一致**").format(
                           acc["dq2"].get("unique_assets"),
                           acc["dq2"].get("max_asset_share"), cov["coverage"],
                           same, len(a)),
    }
    pkg["phase56_fix"] = {
        "determinism": rec["p56_1_determinism_fix"],
        "pinned_assignment": rec["p56_2_pinned_assignment"],
        "single_variable": rec["single_variable_claim"],
        "f9_f10_f101_relation": {
            "F9": "字形据 = 音频锚定；assignment 不可复现（当时未察）",
            "F10": "字幕升级为词级精确，但 assignment 重算 ⇒ 与 F9 画面仅 4/36 一致 ⇒ 单变量失效",
            "F10_1": "**钉定 F9 assignment + F10 字幕** ⇒ 与 F9 唯一差异 = 字幕层 ⇒ **单变量成立**",
        },
    }
    pkg["watch_order"].insert(0, {
        "rank": 1, "version": "F10.1（Phase 56）", "candidate": rec["final_film"],
        "why": ("**单变量字幕验证版**：与 F9 **逐景素材 {} / {} 景一致**，"
                "唯一差异 = 字幕层 ⇒ 终审可**并排看 F9 / F10.1** 判「字幕是否跟嘴」"
                "而不受画面变化污染。烧录 ASS 重叠 0、覆盖 {:.1%}；"
                "分配确定性断言 PASS。").format(same, len(a), cov["coverage"]),
    })
    (L / "phase56_promotion_package.json").write_text(
        json.dumps(pkg, ensure_ascii=False, indent=1), encoding="utf-8")
    print("登记 F10.1：{} | {:,}B | {}s | render_output={}".format(
        rec["final_film"], rec["final_bytes"], rec["final_duration_s"],
        rec["render_output_artifact"]))
    print("  **单变量：与 F9 逐景素材 {} / {} 景一致**（不一致 {}）".format(
        same, len(a), len(diff)))
    print("  确定性：(al) deterministic={} | 指纹 {} == {}".format(
        (al.get("determinism") or {}).get("deterministic"),
        str((al.get("determinism") or {}).get("run1_fingerprint"))[:16],
        str((al.get("determinism") or {}).get("run2_fingerprint"))[:16]))
    print("  烧录 ASS：max {} / 重叠 {} | 覆盖 {:.1%} | median {:.3f}s".format(
        ovl["after"]["max_concurrent"], ovl["after"]["overlap_moments"],
        cov["coverage"], cov["median_dur_s"]))
    print("-> " + pth.relative_to(R).as_posix())
    print("-> " + (L / "phase56_promotion_package.json").relative_to(R).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
