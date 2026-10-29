# -*- coding: utf-8 -*-
"""P27-3 验证：逐景核验明细（哪些景未过、VLM 判定与理由）。只读。"""
from __future__ import annotations

import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")
d = json.loads((R / "docs/regression_2x/logs/phase27_p27_3_verification.json")
               .read_text(encoding="utf-8"))
ps = d["per_scene_verify"]
print("per_scene_verify keys:", list(ps.keys()))
for k, v in ps.items():
    if k == "arbitrated":
        continue
    print("  {}: {}".format(k, json.dumps(v, ensure_ascii=False)[:400]))
print()
arb = ps.get("arbitrated") or []
print("arbitrated 条数:", len(arb))
print()
print("{:<8} {:<10} {:<9} {}".format("scene", "orig_corr", "presence", "reason"))
for a in arb:
    v = a.get("vlm") or {}
    print("{:<8} {:<10} {:<9} {}".format(
        a.get("scene_id"), a.get("orig_corr"), v.get("presence"),
        str(v.get("reason"))[:96]))
print()
if "dq3" in d:
    print("dq3:", json.dumps({k: v for k, v in d["dq3"].items() if k != "findings"},
                             ensure_ascii=False)[:300])
print("bank_derived:", json.dumps(d.get("bank_derived"), ensure_ascii=False)[:300])
