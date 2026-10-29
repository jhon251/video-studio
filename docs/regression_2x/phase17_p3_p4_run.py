# -*- coding: utf-8 -*-
"""P17-3 裁切安全预筛 + P17-4 拆长镜提案批量生成（只备不改，确定性）。

P17-3：对全部池素材计算 crop_safety = corr(全图, 中心 16:9 裁切)（冻结口径 48x48）；
       <0.30 ⇒ 标记 low_crop_safety（短名单降权，不硬拒）并登记进 asset registry。
P17-4：按 DQ-3 口径对 >35s 的场景生成 6-B split_scene 格式提案（拆分点取旁白句边界），
       只登记提案清单，不执行、不渲染。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import subprocess
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
SRC = R / "projects" / "p_96efdc03e1aa"
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core.materials import frame_corr, gray48                      # noqa: E402
from PIL import Image                                                          # noqa: E402

FF = str(R / "bin" / "ffmpeg.exe")
WORK = R / "output" / "phase17_crop_safety"
WORK.mkdir(parents=True, exist_ok=True)
THRESH = 0.30

POOL: dict[str, pathlib.Path] = {}
for d in (SRC / "media", SRC / "registered_materials", SRC / "acquired_materials"):
    if d.is_dir():
        for f in sorted(d.rglob("*")):
            if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
                POOL.setdefault(hashlib.sha256(f.read_bytes()).hexdigest(), f)

reg = json.loads((L / "phase16_local_registry.json").read_text(encoding="utf-8"))
acq = json.loads((L / "phase16_acquired_registry.json").read_text(encoding="utf-8"))
ORIGIN = {}
for x in reg.get("registered") or []:
    ORIGIN[x["sha256"]] = "P16-2 registered"
for x in acq.get("registered") or []:
    ORIGIN[x["sha256"]] = "P16-3 acquired"

rows = []
for sha, src in sorted(POOL.items()):
    out = WORK / (sha[:12] + ".png")
    vf = "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,setsar=1"
    subprocess.run([FF, "-v", "error", "-y", "-i", str(src), "-vf", vf, "-frames:v", "1",
                    str(out)], capture_output=True, text=True)
    cs = round(float(frame_corr(gray48(src), gray48(out))), 4) if out.is_file() else None
    rows.append({
        "sha256": sha, "sha12": sha[:12], "name": src.name,
        "path": str(src), "origin": ORIGIN.get(sha, "pre-existing pool"),
        "crop_safety": cs,
        "low_crop_safety": (cs is not None and cs < THRESH),
        "action": ("短名单降权（low_crop_safety；不硬拒，人工仍可选）"
                   if (cs is not None and cs < THRESH) else "正常"),
    })
print("=" * 78)
print("P17-3 裁切安全预筛")
print("=" * 78)
print("{:>14} {:>10} {:>8} {:>6}  {}".format("sha12", "尺寸", "safety", "低安全", "来源"))
for r in rows:
    with Image.open(r["path"]) as im:
        wh = "{}x{}".format(*im.size)
    print("{:>14} {:>10} {:>8} {:>6}  {}".format(r["sha12"], wh, r["crop_safety"],
                                                 "是" if r["low_crop_safety"] else "",
                                                 r["origin"]))
low = [r for r in rows if r["low_crop_safety"]]
print("\n  标记 low_crop_safety: {} / {}".format(len(low), len(rows)))
for r in low:
    print("    {} {} ({})".format(r["sha12"], r["name"][:44], r["origin"]))

p173 = {
    "schema": "phase17-crop-safety-registry-v1",
    "method": ("crop_safety = corr_48(全图, scale=1920:1080:force_original_aspect_ratio=increase,"
               "crop=1920:1080)（冻结口径 gray48 48x48）"),
    "threshold": THRESH,
    "policy": ("<0.30 ⇒ 标记 low_crop_safety 并在短名单降权；不硬拒（人工仍可选）。"
               "该标记只影响短名单排序，不构成门禁。"),
    "assets": rows,
    "low_crop_safety_count": len(low),
    "phase16_distorted_two": [r["sha12"] for r in low
                              if r["origin"] == "P16-3 acquired"],
    "note": "Phase 16 两张失真素材（S02/S08 来源）已随本表标记留档。",
}
(L / "phase17_crop_safety_registry.json").write_text(
    json.dumps(p173, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")

# ---------------- P17-4 ----------------
import sqlite3                                                                 # noqa: E402
script = json.loads((R / "output/phase13e_script_sandbox/script_dcv2_derived_v1.json")
                    .read_text(encoding="utf-8"))
fix = json.loads((R / "output/phase16_p16_5_sandbox/fixture.json").read_text(encoding="utf-8"))
con = sqlite3.connect("file:" + (R / "projects" / "video_studio.db").as_posix() + "?mode=ro",
                      uri=True)
con.row_factory = sqlite3.Row
sel16 = {}
for r in con.execute("select payload from events where project_id=? "
                     "and type='MATERIAL_TIMELINE'", (fix["sandbox_project_id"],)):
    for d in json.loads(r["payload"]).get("decisions") or []:
        sa = d.get("selected_asset") or {}
        sel16[d["scene_id"]] = {"asset_id": sa.get("asset_id"), "name": sa.get("name")}
con.close()

TARGET_MAX = 35.0
SENT_END = re.compile(r"[。！？!?；;]")
proposals = []
cursor = 0.0
for s in script["segments"]:
    sid = s["scene_id"]
    d = max(float(s["duration_s"]), 3.0)
    t0, t1 = round(cursor, 3), round(cursor + d, 3)
    cursor += d
    if d <= TARGET_MAX:
        continue
    nar = str(s.get("narration") or "")
    bounds = [m.end() for m in SENT_END.finditer(nar)]
    n_split = max(2, int(d // TARGET_MAX) + (1 if d % TARGET_MAX else 0))
    cuts = []
    if bounds and len(bounds) >= n_split - 1:
        step = len(bounds) / n_split
        for k in range(1, n_split):
            idx = min(len(bounds) - 1, int(round(step * k)) - 1)
            frac = bounds[idx] / max(len(nar), 1)
            cuts.append(round(t0 + (t1 - t0) * frac, 3))
    else:
        cuts = [round(t0 + (t1 - t0) * k / n_split, 3) for k in range(1, n_split)]
    cuts = sorted(set(c for c in cuts if t0 + 5.0 < c < t1 - 5.0))
    if not cuts:
        continue
    windows, prev = [], t0
    for c in cuts + [t1]:
        windows.append([prev, c])
        prev = c
    proposals.append({
        "schema": "revision-proposal-v1", "label": "P17-split-long-scene",
        "kind": "over_hold_share_exceeds", "metric": "DQ-3", "severity": "FAIL",
        "finding_id": "p17-split-{}".format(sid),
        "action": "split_scene",
        "scene_id": sid,
        "target": {"scenes": [sid], "window": [t0, t1]},
        "proposed_change": {
            "what": "把该长镜按旁白句边界拆成 {} 个子镜（目标 <={}s）".format(
                len(windows), TARGET_MAX),
            "how": "6-B split_scene：保留旁白/字幕/总时长/音轨，仅重切画面窗口",
            "params": {"scene_id": sid, "orig_window_s": [t0, t1], "orig_hold_s": round(d, 3),
                       "target_hold_s": TARGET_MAX, "keep_audio": True,
                       "keep_total_duration": True,
                       "new_windows_s": windows,
                       "cut_basis": "narration sentence boundary（旁白句边界；无边界时均分）",
                       "cut_times_s": cuts},
        },
        "asset_inheritance": {
            "policy": "两侧子镜继承原子镜素材（不改 DQ-2 复用关系）",
            "asset_id": (sel16.get(sid) or {}).get("asset_id"),
            "asset_name": (sel16.get(sid) or {}).get("name"),
        },
        "expected_effect": {
            "DQ-3": "子镜 hold 由 {:.1f}s 降至 <={:.1f}s（超限景数减少 1）".format(d, TARGET_MAX),
            "DQ-2": "不变（素材继承；复用景数不增减）",
        },
        "execution": {"executed": False, "rendered": False,
                      "note": "只登记提案；执行与全片重渲染授权归下一阶段"},
    })

p174 = {
    "schema": "phase17-split-proposals-v1",
    "stage": "Phase 17 P17-4 拆长镜提案（只备不改）",
    "basis": "DQ-3 口径（core/direction.py static_hold：max_hold_s=25s）；目标 <=35s/子镜",
    "source_script": "output/phase13e_script_sandbox/script_dcv2_derived_v1.json",
    "target_max_s": TARGET_MAX,
    "proposal_count": len(proposals),
    "proposals": proposals,
    "executed": False, "rendered": False,
    "note": "只登记提案清单（proposal register）；不执行、不渲染。",
}
(L / "phase17_split_proposals.json").write_text(
    json.dumps(p174, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")

print()
print("=" * 78)
print("P17-4 拆长镜提案")
print("=" * 78)
print("  目标 <={}s | 提案数: {}".format(TARGET_MAX, len(proposals)))
for p in proposals:
    pc = p["proposed_change"]["params"]
    print("   {} {:.1f}s -> {} 窗 {} 素材={}".format(
        p["scene_id"], pc["orig_hold_s"], len(pc["new_windows_s"]),
        [[round(a, 1), round(b, 1)] for a, b in pc["new_windows_s"]][:3],
        (p["asset_inheritance"]["asset_name"] or "-")[:22]))
print()
print("  P17-3 登记 ->", (L / "phase17_crop_safety_registry.json").relative_to(R).as_posix())
print("  P17-4 登记 ->", (L / "phase17_split_proposals.json").relative_to(R).as_posix())
