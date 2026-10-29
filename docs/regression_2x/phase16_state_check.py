# -*- coding: utf-8 -*-
"""Phase 16 §1 开工前状态核对（只读）。

核对：Phase 14 产物 / Phase 12 许可覆盖层 / P7-5 获取治理路径（当前 DRY_RUN?）/
13-E 候选配方（final_state + 派生脚本）。现实冲突以现实为准并登记。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sqlite3
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")


def sh(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "MISSING"


print("=" * 78)
print("1. Phase 14 产物")
print("=" * 78)
for rel in ("src/video_studio/tools/vlm_judge.py",
            "src/video_studio/tools/vlm_eval.py",
            "tests/fixtures/vlm_relevance_truth_v1.json",
            "config/vlm_judge.json",
            "config/vlm_judge.example.json",
            "docs/regression_2x/PHASE14_REPORT.md"):
    p = R / rel
    print("  {:52s} {}".format(rel, (sh(p)[:16] + "…") if p.is_file() else "MISSING"))
truth = json.loads((R / "tests/fixtures/vlm_relevance_truth_v1.json")
                   .read_text(encoding="utf-8"))
print("  truth 对数:", truth["pair_count"], "| counts:", truth["counts"],
      "| meets_min_pairs:", truth["meets_min_pairs"])
print("  gate(冻结):", json.dumps(truth["gate_frozen_before_run"], ensure_ascii=False))
ki = (R / "docs" / "KNOWN_ISSUES.md").read_text(encoding="utf-8")
print("  KNOWN_ISSUES 含 #73:", "## 73." in ki)

print()
print("=" * 78)
print("2. Phase 12 许可覆盖层")
print("=" * 78)
for name in ("license_overlay_v1.json", "phase12_coverage_after.json"):
    p = L / name
    print("  {:38s} {}".format(name, (sh(p)[:16] + "…") if p.is_file() else "MISSING"))
p12 = L / "license_overlay_v1.json"
if p12.is_file():
    j = json.loads(p12.read_text(encoding="utf-8"))
    print("  keys:", sorted(j.keys())[:14])
    for k in ("schema", "policy", "overlay", "entries", "counts"):
        if k in j:
            print("  {} => {}".format(k, json.dumps(j[k], ensure_ascii=False)[:400]))

print()
print("=" * 78)
print("3. P7-5 获取治理路径（当前是否 DRY_RUN）")
print("=" * 78)
cfg = json.loads((R / "config" / "config.json").read_text(encoding="utf-8"))
print("  config.json tools:", json.dumps(cfg.get("tools"), ensure_ascii=False))
print("  config.json 含 execution/ops 段:",
      [k for k in cfg if k in ("execution", "ops", "governance")])
# material_provider 的 DRY_RUN / BOUND 语义
src = (R / "src" / "video_studio" / "core" / "execution.py")
if src.is_file():
    t = src.read_text(encoding="utf-8")
    for kw in ("DRY_RUN", "BOUND", "sandbox", "allow_write", "dry_run"):
        print("  execution.py 含 {:10s}: {}".format(kw, kw in t))
for rel in ("src/video_studio/tools/material_provider.py",
            "src/video_studio/ops/execution.py",
            "src/video_studio/core/execution.py",
            "src/video_studio/tools/provider_wikimedia.py"):
    p = R / rel
    print("  {:52s} {}".format(rel, "OK" if p.is_file() else "MISSING"))

print()
print("=" * 78)
print("4. 13-E 候选配方")
print("=" * 78)
fs = L / "phase13e_p13e3_final_state.json"
print("  final_state:", (sh(fs)[:16] + "…") if fs.is_file() else "MISSING")
if fs.is_file():
    st = json.loads(fs.read_text(encoding="utf-8"))
    ex = st.get("executed") or {}
    print("  status:", ex.get("status"))
    print("  sandbox:", json.dumps((ex.get("sandbox") or {}), ensure_ascii=False)[:300])
ds = R / "output" / "phase13e_script_sandbox" / "script_dcv2_derived_v1.json"
print("  派生脚本:", (sh(ds)[:16] + "…") if ds.is_file() else "MISSING")
if ds.is_file():
    d = json.loads(ds.read_text(encoding="utf-8"))
    print("    segments:", len(d.get("segments") or []),
          "| total_duration_s:", d.get("total_duration_s"))
print("  H5 底片:", sh(R / "output/phase6g_exec_h5/20260929_151026/out/H5_rp-0ebebb71f99c.mp4")[:16], "…")

print()
print("=" * 78)
print("5. 现有素材池（p_96efdc03e1aa/media）与 H5 候选素材")
print("=" * 78)
md = R / "projects" / "p_96efdc03e1aa" / "media"
imgs = [f for f in md.rglob("*") if f.is_file()
        and f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")]
print("  media 图像数:", len(imgs))
for f in sorted(imgs):
    print("    {:70s} {:>9,}B".format(f.relative_to(md).as_posix(), f.stat().st_size))
h5 = R.parent / "h5_asset_candidates"
print("  H5 候选根:", h5, "exists:", h5.is_dir())
if h5.is_dir():
    for f in sorted(h5.rglob("*")):
        if f.is_file():
            print("    {:70s} {:>9,}B".format(
                f.relative_to(h5).as_posix(), f.stat().st_size))

print()
print("=" * 78)
print("6. DB 素材登记现状（asset_index / 检索候选）")
print("=" * 78)
con = sqlite3.connect("file:" + (R / "projects" / "video_studio.db").as_posix() + "?mode=ro",
                      uri=True)
con.row_factory = sqlite3.Row
for r in con.execute("select type, count(*) n from artifacts where project_id='p_96efdc03e1aa' "
                     "group by type order by n desc"):
    print("  {:28s} {}".format(r["type"], r["n"]))
con.close()
