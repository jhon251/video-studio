# -*- coding: utf-8 -*-
"""Phase 12 §1 只读核对（二）：P7-2 索引结构、P7-6 五景候选与 license_decision 路径。"""
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")

idx = json.loads((L / "asset_index.json").read_text(encoding="utf-8"))
print("== P7-2 索引 ==")
print(" 顶层 keys:", sorted(idx.keys()))
print(" schema/version:", idx.get("schema"), idx.get("version"))
assets = idx.get("assets") or []
print(" 资产数:", len(assets), "| 首条 keys:", sorted(assets[0].keys()) if assets else None)
for a in assets:
    print("  {} | lic={} class={} | sha={} | size={} | tags={}".format(
        a.get("asset_id"), a.get("license"), a.get("license_class"),
        str(a.get("sha256"))[:10], a.get("size_bytes"), (a.get("tags") or [])[:3]))
print(" 索引文件 sha256 由 immutable check 记录")

prop = json.loads((L / "visual_binding_proposals.json").read_text(encoding="utf-8"))
print("\n== P7-6 绑定提案 ==")
print(" 顶层 keys:", sorted(prop.keys()))
print(" counts:", json.dumps({k: v for k, v in prop.items() if isinstance(v, (int, str))
                              and "count" in k.lower()}, ensure_ascii=False))
pr = prop.get("proposals") or prop.get("items") or []
print(" 提案数:", len(pr), "| 首条 keys:", sorted(pr[0].keys()) if pr else None)
hitl = [p for p in pr if p.get("license_decision") in ("HITL_REQUIRED", "UNSUPPORTED")
        or p.get("decision") in ("HITL_REQUIRED", "UNSUPPORTED")]
print(" HITL/UNSUPPORTED 提案:", len(hitl))
cov = json.loads((L / "visual_coverage_report.json").read_text(encoding="utf-8"))
print("\n== P7-6 覆盖报告 ==")
print(" 顶层 keys:", sorted(cov.keys()))
sc = cov.get("scenes") or []
print(" 场景数:", len(sc), "| 首条 keys:", sorted(sc[0].keys()) if sc else None)
for s in sc:
    if s.get("scene_id") in ("S01", "S05", "S13", "S14", "S15", "S16"):
        ch = s.get("chosen") or s.get("selected") or {}
        print("  {}: decision={} license_decision={} chosen={} lic={} class={}".format(
            s.get("scene_id"), s.get("decision"), s.get("license_decision"),
            (ch or {}).get("asset_id"), (ch or {}).get("license"), (ch or {}).get("license_class")))
        print("       keys:", sorted(s.keys()))
