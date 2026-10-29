# -*- coding: utf-8 -*-
"""Phase 40 / P40-1 侦察（v3）：① 找 `low_discriminative` 标记来源；② 复算逐景候选。"""
from __future__ import annotations

import collections
import json
import pathlib
import re
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")

print("=== ① low_discriminative 标记来源 ===")
hits = []
for base in ("docs", "output", "src", "config"):
    for p in (R / base).rglob("*"):
        if p.is_file() and p.suffix.lower() in (".json", ".jsonl", ".py", ".md", ".txt"):
            try:
                t = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:                                               # noqa: BLE001
                continue
            if "low_discriminative" in t:
                hits.append(str(p.relative_to(R)))
print("命中文件 {} 个:".format(len(hits)))
for h in hits[:12]:
    print("   " + h)
if hits:
    p = R / hits[0]
    t = p.read_text(encoding="utf-8", errors="ignore")
    i = t.find("low_discriminative")
    print("   样例上下文:", t[max(0, i - 160):i + 120].replace("\n", " ")[:280])
print()
print("=== ② 复算逐景候选（生产 classify_scene）===")
from video_studio.agents.editing.agent import EditingAgent as EA                 # noqa: E402
from video_studio.core import materials as MAT                                   # noqa: E402
from video_studio.agents.retrieval.agent import kw_tokens                        # noqa: E402

L = R / "docs" / "regression_2x" / "logs"
script = json.loads((R / "output/phase36_script_sandbox/script_p36_v65_36seg.json")
                    .read_text(encoding="utf-8"))
pool = json.loads((L / "phase33_retrieval_payload.json").read_text(encoding="utf-8"))
cands = [c for c in pool["candidates"] if c.get("path")]
tl = EA._build_material_timeline(script, [], cands,
                                policy=MAT.policy_from_config(None),
                                material_provided=True)
widths = collections.Counter(len(d.get("candidates") or []) for d in tl)
print("逐景候选数分布: {}".format(dict(sorted(widths.items()))))
print("{:<8} {:<16} {:>5}  {}".format("scene", "selected", "cands", "候选"))
for d in tl[:14]:
    sel = ((d.get("selected_asset") or {}).get("asset_id") or "-")[:14]
    cs = [(c.get("asset_id") or "")[:12] for c in (d.get("candidates") or [])]
    print("{:<8} {:<16} {:>5}  {}".format(d["scene_id"], sel, len(cs), ",".join(cs[:7])))
out = R / "output" / "p40_probe"
out.mkdir(parents=True, exist_ok=True)
(out / "candidates_per_scene.json").write_text(json.dumps(
    [{"scene_id": d["scene_id"],
      "selected": ((d.get("selected_asset") or {}).get("asset_id")),
      "candidates": [{"asset_id": c.get("asset_id"), "sha256": c.get("sha256"),
                      "name": c.get("name"), "match_score": c.get("match_score"),
                      "usable": c.get("usable", True)}
                     for c in (d.get("candidates") or [])]}
     for d in tl], ensure_ascii=False, indent=1), encoding="utf-8")
print()
print("-> output/p40_probe/candidates_per_scene.json")
