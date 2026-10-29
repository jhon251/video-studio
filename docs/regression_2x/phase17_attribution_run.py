# -*- coding: utf-8 -*-
"""P17-1 五景归因执行 + 目视帧包（确定性、零 LLM、零网络）。

产出：
  · logs/phase17_attribution.json      —— 逐景归因 + 全部数值证据
  · output/phase17_attr_pack/<scene>/{frame_10,frame_50,frame_90,asset}.png —— 人工目视帧包
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
import sqlite3
import subprocess
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import corr_diagnostics as CD                            # noqa: E402

FF = str(R / "bin" / "ffmpeg.exe")
SB = R / "output" / "phase16_p16_5_sandbox"
PACK = R / "output" / "phase17_attr_pack"
TARGETS = ("S02", "S06", "S07", "S08", "S13")

fix = json.loads((SB / "fixture.json").read_text(encoding="utf-8"))
pid = fix["sandbox_project_id"]
proj = R / "projects" / pid
film = next((proj / "output").glob("*.mp4"))

con = sqlite3.connect("file:" + (R / "projects" / "video_studio.db").as_posix() + "?mode=ro",
                      uri=True)
con.row_factory = sqlite3.Row
sel = {}
for r in con.execute("select payload from events where project_id=? and type='MATERIAL_TIMELINE'",
                     (pid,)):
    for d in json.loads(r["payload"]).get("decisions") or []:
        sel[d["scene_id"]] = d.get("selected_asset") or {}
con.close()

motion = {}
mp = proj / "render" / "motion_evidence.json"
if mp.is_file():
    mj = json.loads(mp.read_text(encoding="utf-8"))
    for e in mj.get("applied") or []:
        motion[e["scene_id"]] = e

# 素材定位：渲染后登记件被迁出 media/（Phase 16 §7.1 位置修正）⇒ 记录路径可能已失效。
# 以 sha256 为准，在三个物料目录里解析（确定性；找不到则如实报 NOT_ASSESSABLE）。
SRC_PROJ = R / "projects" / "p_96efdc03e1aa"
MAT_DIRS = [SRC_PROJ / "media", SRC_PROJ / "registered_materials",
            SRC_PROJ / "acquired_materials"]
_by_sha: dict[str, pathlib.Path] = {}
for d in MAT_DIRS:
    if not d.is_dir():
        continue
    for f in sorted(d.rglob("*")):
        if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
            _by_sha.setdefault(hashlib.sha256(f.read_bytes()).hexdigest(), f)
POOL = {p.name: p for p in _by_sha.values()}
print("物料目录解析到唯一素材:", len(POOL))


def resolve_asset(sa: dict):
    """优先记录路径；否则按 sha256 在物料目录解析；返回 (path, how)。"""
    p = pathlib.Path(str(sa.get("path") or ""))
    if p.is_file():
        return p, "recorded_path"
    s = str(sa.get("sha256") or "")
    if s and s in _by_sha:
        return _by_sha[s], "sha256_lookup（记录路径已失效：登记件迁移）"
    return None, "UNRESOLVED"


script = json.loads((R / "output/phase13e_script_sandbox/script_dcv2_derived_v1.json")
                    .read_text(encoding="utf-8"))
dur = {s["scene_id"]: float(s["duration_s"]) for s in script["segments"]}
cursor, win = 0.0, {}
for s in script["segments"]:
    d = max(dur[s["scene_id"]], 3.0)
    win[s["scene_id"]] = (round(cursor, 3), round(cursor + d, 3))
    cursor += d
last = script["segments"][-1]["scene_id"]
win[last] = (win[last][0], round(max(win[last][1], cursor + 2.0), 3))

PACK.mkdir(parents=True, exist_ok=True)
print("成片:", film.name, "| 目标景:", TARGETS)
results = []
for sid in TARGETS:
    d = PACK / sid
    d.mkdir(parents=True, exist_ok=True)
    t0, t1 = win[sid]
    frames = {}
    for tag, frac in (("10", 0.10), ("50", 0.50), ("90", 0.90)):
        out = d / "frame_{}.png".format(tag)
        ts = t0 + (t1 - t0) * frac
        subprocess.run([FF, "-v", "error", "-y", "-ss", "{:.3f}".format(ts), "-i", str(film),
                        "-frames:v", "1", str(out)], capture_output=True, text=True)
        if out.is_file():
            frames[tag] = (out, round(ts, 3))
    asset, how = resolve_asset(sel.get(sid) or {})
    if asset is not None:
        shutil.copy2(asset, d / ("asset" + asset.suffix))
    fp = frames.get("50", (None, None))[0]
    if fp and asset is not None:
        res = CD.attribute_scene(scene_id=sid, frame_path=fp, asset_path=asset,
                                 motion_evidence=motion, pool=POOL)
    else:
        res = {"scene_id": sid, "verdict": "NOT_ASSESSABLE",
               "reasons": ["缺少帧（{}）或素材文件（{}）".format(bool(fp), how)]}
    res["window_s"] = [t0, t1]
    res["duration_s"] = round(t1 - t0, 3)
    res["assigned_asset"] = {"name": asset.name if asset else None,
                             "path": str(asset) if asset else None,
                             "resolved_by": how,
                             "asset_id": (sel.get(sid) or {}).get("asset_id")}
    res["pack_dir"] = str(d)
    res["pack_frames"] = {k: {"path": str(v[0]), "t_s": v[1]} for k, v in frames.items()}
    results.append(res)
    print("  {} -> {} | {}".format(sid, res.get("verdict"),
                                   (res.get("reasons") or [""])[0][:110]))

rep = {
    "schema": "phase17-attribution-report-v1",
    "stage": "Phase 17 P17-1 五景归因（渲染后核验度量专项）",
    "film": str(film.relative_to(R)).replace("\\", "/"),
    "sandbox_project_id": pid,
    "frozen_gate": CD.FROZEN_MIN_CORR,
    "res_ladder": list(CD.RES_LADDER),
    "crop_scales": list(CD.CROP_SCALES),
    "verdict_definitions": {
        "crop_artifact": "多尺度/多偏移中心裁切后 corr 达冻结阈值",
        "density_artifact": "提高重采样分辨率后 corr 达冻结阈值（稀疏图 48x48 塌陷）",
        "subtitle_artifact": "剔除字幕带后 corr 达冻结阈值",
        "region_artifact": "素材内滑窗最佳 corr 达阈值（画面只对上素材局部）",
        "motion_artifact": "运动裁切窗口几何不自洽",
        "sampling_artifact": "素材在屏（同分辨率 argmax）但未命中细分假设 ⇒ 分辨率/取样伪影",
        "possible_real_mismatch": "素材非 argmax 且各假设不成立 ⇒ 可能真实错配，不得裁定为在屏",
    },
    "scenes": results,
    "verdict_counts": {v: sum(1 for r in results if r.get("verdict") == v)
                       for v in ("crop_artifact", "density_artifact", "subtitle_artifact",
                                 "motion_artifact", "region_artifact", "sampling_artifact",
                                 "possible_real_mismatch", "NOT_ASSESSABLE")},
    "zero_llm": True, "zero_vlm": True, "zero_network": True, "rendered": False,
}
out = L / "phase17_attribution.json"
out.write_text(json.dumps(rep, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
print()
print("归因分布:", json.dumps(rep["verdict_counts"], ensure_ascii=False))
print("报告 ->", out.relative_to(R).as_posix())
print("帧包 ->", PACK.relative_to(R).as_posix())
