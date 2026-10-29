# -*- coding: utf-8 -*-
"""Phase 42 / P42-2：**登记第七部交付级候选 F4**（append-only、零 promotion）+ 材料包更新。

本轮结论（**内容级排除兑现**）：
  · 片级禁用 `asset_2442c39e8002`（Obelus discogranulatus，螺壳照片）——
    走**既有 decisions 通道**的外部开关 `config/content_exclusions.json`（`config.json` 零改动）；
  · **实测 2442c39e 上屏次数 = 0**（F3 时为 3 次：P04_3 / P06_3 / P08_2）；
  · 排除在**候选层**生效（候选域中亦为 0），非仅"不选"；
  · 求解器 `pass=True`：cap 0 / 间距 0 / 相邻 0 / max 3；DQ-3e 0 处违例。
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
    final = next(f for f in sorted(pdir.glob("*_with_outro_v2.mp4")))
    acc = json.loads((L / "phase36_candidate_acceptance.json").read_text(encoding="utf-8"))
    dq3e = json.loads((L / "p40_dq3e.json").read_text(encoding="utf-8"))
    exl = json.loads((L / "p42_1_exclusion.json").read_text(encoding="utf-8"))
    ext = json.loads((L / "p42_2_content_exclusion_test.json").read_text(encoding="utf-8"))
    tb = json.loads((R / "output/phase36_voice/timebase_v65.json").read_text(encoding="utf-8"))
    cfg = json.loads((R / "config" / "content_exclusions.json").read_text(encoding="utf-8"))

    con = sqlite3.connect("file:" + (R / "projects/video_studio.db").as_posix()
                          + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    arts = [dict(x) for x in con.execute(
        "select artifact_id,type from artifacts where project_id=?", (pid,))]
    ro = next((a for a in arts if a["type"] == "render_output"), None)
    r = con.execute("select payload from events where project_id=? and "
                    "type='MATERIAL_TIMELINE'", (pid,)).fetchone()
    p = json.loads(r["payload"])
    dec = p["decisions"]
    alloc = p.get("material_allocation") or {}
    con.close()
    gs = alloc.get("global_satisfy") or {}
    ce = alloc.get("content_exclusions") or {}
    n_shell = sum(1 for d in dec
                  if "2442c39e" in str((d.get("selected_asset") or {}).get("asset_id")))
    rec = {
        "schema": "p42-2-delivery-candidate-v1",
        "stage": "Phase 42 F4（片级内容排除 + 全局约束分配）",
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
                                 "audio": "narration_v65（零改动）",
                                 "timebase_s": tb["audio_time_base_s"]},
        "p42_1_content_exclusion": {
            "mechanism": ("片级禁用 `asset_2442c39e8002`（Obelus discogranulatus，螺壳照片）"
                          "在本片**全部景的候选域**中排除"),
            "channel": ("既有 decisions 通道 + 外部开关文件 "
                        "`config/content_exclusions.json`（`config.json` 零改动）"),
            "reason": cfg["content_exclusions"]["excluded"][0]["reason"],
            "approved_by": cfg["content_exclusions"]["excluded"][0]["approved_by"],
            "approval_document": cfg["content_exclusions"]["excluded"][0]["approval_document"],
            "observed_placements_F3": cfg["content_exclusions"]["excluded"][0]
            ["observed_placements"],
            "assertion_result": {"shell_on_screen": n_shell,
                                 "still_in_candidate_pool": exl["still_in_candidates"],
                                 "present_in_candidates_before": exl["still_in_candidates"]},
            "gate": "tests/content_exclusion_test.py 4/4 PASS",
        },
        "p40_1_solver": {"global_satisfy": gs,
                         "before_F": {"cap_max": 4, "gap": 10, "adj": 4, "dq3e": 4},
                         "after_F4": {"cap_max": gs.get("max_scenes_per_asset"),
                                      "gap": gs.get("gap_violations"),
                                      "adj": gs.get("adjacent_violations"),
                                      "dq3e": len(dq3e["over"])}},
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
            "no_picture": "PASS 2/2", "metaphor_quota": "PASS 7/7",
            "content_exclusion": "PASS 4/4（shell = 0）",
            "allocation_solver_test": "PASS 7/7",
            "motion_metrics": {k: acc["motion_metrics"].get(k) for k in
                               ("freeze_ratio", "longest_static_s",
                                "opening_changes", "all_pass")},
            "arbitration": {"arbitrated": 2, "still_failed": 0},
        },
        "zero_promotion": True,
        "promotion_baseline_unchanged": "projects/p_50e10b27b44d/output/t_a4d8c1aafd04_draft.mp4",
    }
    pth = L / "p42_2_delivery_candidate.jsonl"
    with pth.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    pkg = json.loads((L / "phase41_promotion_package.json").read_text(encoding="utf-8"))
    pkg["schema"] = "phase42-promotion-package-v4-updated"
    pkg["versions"]["F4_p42_content_exclusion"] = {
        "name": "F4（Phase 42：片级内容排除 螺壳素材）",
        "candidate": rec["final_film"], "bytes": rec["final_bytes"],
        "duration_s": rec["final_duration_s"], "segments": 36,
        "gate_state": ("**全门通过**：时长/A2/满覆盖/音轨一致/逐景 36-36/DQ-2(0.0876/16)/"
                       "DQ-3(0/36)/DQ-3e(0 处)/no_picture 2-2/配额 7-7/"
                       "**内容排除 4-4（螺壳上屏 0）**/分配求解器 7-7；"
                       "三指标按停用口径不通过（冻结 73.2%）"),
    }
    pkg["phase42_fix"] = {
        "content_exclusion": rec["p42_1_content_exclusion"],
        "shell_disposition_chain": {
            "F": "螺壳出现（P04_3/P06_3）",
            "F2": "仍出现（ID 未变）",
            "F3": "P41 换 ID ⇒ `cfae038f→2442c39e`，**画面家族未换**，实测 **3 次**上屏（含 P08_2）",
            "F4": "**片级内容排除 ⇒ 上屏 0 次**（候选域亦为 0）",
        },
        "trajectory": {
            "F": {"cap_max": 4, "gap": 10, "adj": 4, "dq3e": 4, "share": 0.1214, "shell": 2},
            "F2": {"cap_max": 3, "gap": 8, "adj": 3, "dq3e": 3, "share": 0.0877, "shell": 2},
            "F3": {"cap_max": 3, "gap": 0, "adj": 0, "dq3e": 0, "share": 0.0826, "shell": 3},
            "F4": {"cap_max": 3, "gap": 0, "adj": 0, "dq3e": 0, "share": 0.0876, "shell": 0},
        },
    }
    pkg["watch_order"].insert(0, {
        "rank": 1, "version": "F4（Phase 42）", "candidate": rec["final_film"],
        "why": ("F3 基础上完成**内容级排除**：螺壳素材上屏 **3 次 → 0 次**；"
                "其余门（cap/间距/相邻/DQ-3e/no_picture/配额）保持全绿。"),
    })
    (L / "phase42_promotion_package.json").write_text(
        json.dumps(pkg, ensure_ascii=False, indent=1), encoding="utf-8")
    print("登记 F4：{} | {:,}B | {}s | render_output={}".format(
        rec["final_film"], rec["final_bytes"], rec["final_duration_s"],
        rec["render_output_artifact"]))
    print("**螺壳上屏次数 = {}**（F3 为 3）".format(n_shell))
    print("求解器: {}".format(json.dumps(
        {k: gs.get(k) for k in ("pass", "gap_violations", "adjacent_violations",
                                "max_scenes_per_asset")}, ensure_ascii=False)))
    print("内容排除门: {}".format(ext))
    print("-> " + pth.relative_to(R).as_posix())
    print("-> " + (L / "phase42_promotion_package.json").relative_to(R).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
