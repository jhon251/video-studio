# -*- coding: utf-8 -*-
"""Phase 12 只读核实：两处「UNKNOWN ⇒ FREE_ATTRIBUTION」join 的匹配键与记录原文。"""
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")
ov = json.loads((L / "license_overlay_v1.json").read_text(encoding="utf-8"))
idx = {c["asset_id"]: c for c in json.loads((L / "asset_index.json").read_text(
    encoding="utf-8"))["candidates"]}
for aid in ("ast-c6168344b7567dea", "ast-f9743df609846f24", "ast-0c365d5195d50bba"):
    e = next(x for x in ov["entries"] if x["asset_id"] == aid)
    c = idx[aid]
    print("==", aid, "==")
    print("  索引: provider={} source_id={} sha={} url={}".format(
        c.get("provider"), c.get("source_id"), str(c.get("sha256"))[:12],
        str(c.get("source_url"))[:60]))
    print("  匹配键:", json.dumps(e["match_keys"], ensure_ascii=False)[:200])
    for r in e["records"][:4]:
        print("  记录: type={} loc={}".format(r["source_type"], r["locator"]))
        print("        license={!r} class={} attribution={!r}".format(
            r["license_text"], r["license_class"], str(r["attribution"])[:50]))
        print("        记录内 provider/source_id={}/{} | asset_sha={} | scene={} | url={}".format(
            r["extra"].get("provider"), r["extra"].get("source_id"),
            str(r.get("asset_sha256"))[:12], r.get("scene_id"), str(r.get("source_url"))[:52]))
