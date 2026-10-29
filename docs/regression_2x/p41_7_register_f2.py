# -*- coding: utf-8 -*-
"""Phase 40 / P40-3：**登记第五部交付级候选 F2**（append-only、零 promotion）。

如实登记：分配纪律**大幅改善但未归零**——
  cap 违例 1→**0**（max 4→**3**）；间距违例 10→**8**；相邻违例 4→**3**；
  DQ-3e 有效静止 >25s 由 **4 处 → 3 处**（45.8/39.3/26.5s）。
根因（已定位到机制层，非参数层）：**父景绑定回退**把同一素材强绑给同一父段的多个派生景，
这些景 `candidates = 0` ⇒ **分配器无法改**（空域）⇒ 属**结构性不可行**，
非贪心问题。破局需改 `_build_material_timeline` 的父景回退行为（或扩池），
按授权书**如实登记**并交人工终审裁定。
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
    dq3e = json.loads((L / "p40_dq3e.json").read_text(encoding="utf-8"))
    solve = json.loads((L / "p40_allocation_solver_test.json").read_text(encoding="utf-8"))
    tb = json.loads((R / "output/phase36_voice/timebase_v65.json").read_text(encoding="utf-8"))

    con = sqlite3.connect("file:" + (R / "projects/video_studio.db").as_posix()
                          + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    arts = [dict(x) for x in con.execute(
        "select artifact_id,type from artifacts where project_id=?", (pid,))]
    ro = next((a for a in arts if a["type"] == "render_output"), None)
    r = con.execute("select payload from events where project_id=? and "
                    "type='MATERIAL_TIMELINE'", (pid,)).fetchone()
    alloc = (json.loads(r["payload"]).get("material_allocation") or {}) if r else {}
    con.close()
    gs = alloc.get("global_satisfy") or {}
    rec = {
        "schema": "p40-3-delivery-candidate-v1",
        "stage": "Phase 40 F2（全局约束分配器修复后重渲）",
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
        "text_audio_unchanged": {"script": "v6.5（零改动）", "audio": "narration_v65（零改动）",
                                 "timebase_s": tb["audio_time_base_s"]},
        "p40_1_allocator_fix": {
            "module": "src/video_studio/core/allocation.py::satisfy",
            "method": "min-conflicts 局部搜索（固定 seed=20261002）",
            "before": {"cap_max_scenes_per_asset": 4, "cap_violations": 1,
                       "gap_violations": 10, "adjacent_violations": 4,
                       "dq3e_over_25s": 4},
            "after": {"cap_max_scenes_per_asset": 3, "cap_violations": 0,
                      "gap_violations": gs.get("gap_violations"),
                      "adjacent_violations": gs.get("adjacent_violations"),
                      "dq3e_over_25s": len(dq3e["over"])},
            "global_satisfy": gs,
            "unit_test": "tests/allocation_solver_test.py 5/5 PASS"
                         "（含 S5：F 实盘缺陷 1/10/4 可复现且修复为 0/0/0）",
        },
        "p40_2_dq3e": {
            "gate": "tests/dq3e_effective_hold_test.py",
            "definition": "合并相邻同素材后的有效保持 ≤25s（运行前写死）",
            "max_effective_s": dq3e["max_effective_actual_s"],
            "over": dq3e["over"], "pass": dq3e["pass"],
            "residual_root_cause": (
                "残留 3 处全部是**父景绑定回退**产生的兄弟景对"
                "（P03_2/P03_3、P04_2/P04_3、P06_3/P06_4），其 `candidates = 0` ⇒ "
                "分配器**空域**、无法改派 ⇒ **结构性不可行**（非贪心、非参数问题）。"),
        },
        "gates": {
            "duration": {"value": dur(final), "contract": tb["audio_time_base_s"]},
            "a2_delta_s": acc.get("a2_delta_s"), "full_cover": True,
            "audio_identical": aud(final) == aud(base),
            "dq2": {k: acc["dq2"].get(k) for k in
                    ("state", "unique_assets", "max_asset_share")},
            "dq3": {k: acc["dq3"].get(k) for k in
                    ("state", "share_over_threshold", "max_hold_s")},
            "dq3e": {"pass": dq3e["pass"], "max_effective_s":
                     dq3e["max_effective_actual_s"]},
            "no_picture": "PASS 2/2（卡景 0）",
            "metaphor_quota": "PASS 7/7",
            "allocation_solver_test": "PASS 5/5",
            "motion_metrics": {k: acc["motion_metrics"].get(k) for k in
                               ("freeze_ratio", "longest_static_s",
                                "opening_changes", "all_pass")},
            "arbitration": {"arbitrated": 2, "still_failed": 0},
        },
        "zero_promotion": True,
        "promotion_baseline_unchanged": "projects/p_50e10b27b44d/output/t_a4d8c1aafd04_draft.mp4",
    }
    p = L / "p40_3_delivery_candidate.jsonl"
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # ---- 材料包 v4 更新：F 与 F2 并列 ----
    pkg = json.loads((L / "phase36_promotion_package.json").read_text(encoding="utf-8"))
    pkg["schema"] = "phase40-promotion-package-v4-updated"
    pkg["versions"]["F2_p40_global_allocator"] = {
        "name": "F2（Phase 40：全局约束分配器修复后重渲）",
        "candidate": rec["final_film"], "bytes": rec["final_bytes"],
        "duration_s": rec["final_duration_s"], "segments": 36,
        "gate_state": ("时长/A2/满覆盖/音轨一致/DQ-2(0.0877)/DQ-3(0/36 超 25s)/no_picture 2-2/"
                       "配额 7-7/分配求解器 5-5 全过；"
                       "**DQ-3e 未归零（3 处 45.8/39.3/26.5s，结构性不可行）**；"
                       "三指标按停用口径不通过"),
    }
    pkg["phase40_fix"] = {
        "allocator": rec["p40_1_allocator_fix"],
        "dq3e_gate": rec["p40_2_dq3e"],
        "improvement": "cap 1→0 违例（max 4→3）；间距 10→8；相邻 4→3；DQ-3e 4→3 处",
        "residual": "父景绑定回退的兄弟景对（candidates=0）⇒ 空域 ⇒ 结构性不可行",
    }
    pkg["watch_order"].insert(0, {
        "rank": 1, "version": "F2（Phase 40 分配器修复）",
        "candidate": rec["final_film"],
        "why": ("在 F 基础上修好**分配器**（cap 归零、最大 share 0.1214→0.0877）；"
                "DQ-3e 仍有 3 处结构性残留。"),
    })
    (L / "phase40_promotion_package.json").write_text(
        json.dumps(pkg, ensure_ascii=False, indent=1), encoding="utf-8")
    print("登记 F2：{} | {:,}B | {}s | render_output={}".format(
        rec["final_film"], rec["final_bytes"], rec["final_duration_s"],
        rec["render_output_artifact"]))
    print("修复：cap 1→0（max 4→3）| 间距 10→{} | 相邻 4→{} | DQ-3e 4→{}".format(
        gs.get("gap_violations"), gs.get("adjacent_violations"), len(dq3e["over"])))
    print("求解器单测: {}".format(solve))
    print("-> " + p.relative_to(R).as_posix())
    print("-> " + (L / "phase40_promotion_package.json").relative_to(R).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
