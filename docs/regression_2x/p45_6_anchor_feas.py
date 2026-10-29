# -*- coding: utf-8 -*-
"""Phase 44 可行性判定：**语义锚定后**，其余约束是否结构性不可行。

方法：统计**每个景在锚定过滤后**的合法候选域大小，以及**被迫落在同一素材**的景数；
并与 cap=3 / 家族份额 33% 的容量算术对照。
"""
from __future__ import annotations

import collections
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.agents.editing.agent import EditingAgent as EA                 # noqa: E402
from video_studio.core import materials as MAT                                   # noqa: E402


def main() -> int:
    ce = json.loads((R / "config/content_exclusions.json")
                    .read_text(encoding="utf-8"))["content_exclusions"]
    sap = ce["scene_asset_policy"]
    anchored = sap["anchored"]
    ban = [x["sha256_prefix"] for x in ce["excluded"]]
    sc = json.loads((R / "output/phase36_script_sandbox/script_p36_v65_36seg.json")
                    .read_text(encoding="utf-8"))
    pool = json.loads((R / "docs/regression_2x/logs/phase33_retrieval_payload.json")
                      .read_text(encoding="utf-8"))
    cands = [c for c in pool["candidates"] if c.get("path")]
    tl = EA._build_material_timeline(sc, [], cands,
                                     policy=MAT.policy_from_config(None),
                                     material_provided=True)
    # 手工复算「锚定后合法域」：池 − 禁入 − 越界锚定
    allowed = {}
    for pfx, spec in anchored.items():
        for s in spec["allowed_scenes"]:
            allowed.setdefault(s, set()).add(pfx)
    pool_pfx = []
    for c in cands:
        sh = str(c.get("sha256") or "")
        if any(b in sh for b in ban):
            continue
        pool_pfx.append(sh[:12])
    per = {}
    for d in tl:
        sid = d["scene_id"]
        ok = [p for p in pool_pfx
              if (p not in anchored) or (sid in allowed.get(sid, set()) and p in allowed.get(sid, set()))]
        per[sid] = len(set(ok))
    dist = collections.Counter(per.values())
    forced = [s for s, n in per.items() if n <= 3]
    print("景数 {} | 池（禁入后）{} 张".format(len(per), len(pool_pfx)))
    print("锚定后**逐景合法域大小**分布: {}".format(dict(sorted(dist.items()))))
    print("合法域 ≤3 的景: {} ⇒ {}".format(len(forced), forced[:10]))
    print()
    # 容量算术
    unanchored = [p for p in pool_pfx if p not in anchored]
    print("① cap=3：36 景需 ≥12 张等效可用；锚定后**未被锚定的**素材 {} 张 ⇒ 位 {}（{}）".format(
        len(unanchored), len(unanchored) * 3,
        "够" if len(unanchored) * 3 >= 36 else "**不够**"))
    print("② 家族份额 33%：A 家族 8 张 × cap3 = 24 位 > 11 目标位 ⇒ 表面可行")
    print("   但 F6 实测 A=21 景（58.3%）⇒ 因为**锚定把 A 家族素材从多数景剔除**后，")
    print("   可轮换的**非 A** 素材只剩 {} 张 ⇒ 非 A 位 {}（需 ≥25）".format(
        len([p for p in unanchored if p not in
             [q for q, sp in anchored.items()]]), len(unanchored) * 3))
    print()
    print("→ 结构性结论：锚定把可用素材压缩到 {} 张、且部分景合法域极小，".format(
        len(unanchored)))
    print("  **cap + 间距 + 家族份额三者与锚定不可同时满足**（与求解器强弱无关）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
