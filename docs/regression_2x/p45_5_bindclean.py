# -*- coding: utf-8 -*-
"""Phase 44 / P44-1：**具名绑定表 —— 锚定感知清理**。

P44 实测：既有 bindings_proposal（P40 生成）**不知道锚定表** ⇒ 把锚定素材绑到了
越界景（P02_3 / P03_4 / P05_1 / P05_3）⇒ 锚定门 A1 报 4 处越界。
本脚本：逐条检查现有绑定，凡**越出锚定**者**删除该绑定**（该景回落到自动选材/纯色卡，
如实登记），其余保留。**不新造绑定**。
"""
from __future__ import annotations

import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
V = R / "output" / "phase36_voice"
sys.stdout.reconfigure(encoding="utf-8")


def main() -> int:
    ce = json.loads((R / "config/content_exclusions.json")
                    .read_text(encoding="utf-8"))["content_exclusions"]
    sap = ce.get("scene_asset_policy") or {}
    anchored = sap.get("anchored") or {}
    p = V / "bindings_proposal.json"
    bp = json.loads(p.read_text(encoding="utf-8"))
    kept, dropped = {}, []
    for sid, spec in (bp.get("bindings") or {}).items():
        sh = str(spec.get("sha256") or "")
        bad = None
        for pfx, aspec in anchored.items():
            if pfx and pfx in sh:
                if sid not in (aspec.get("allowed_scenes") or []):
                    bad = pfx
                break
        if bad:
            dropped.append({"scene": sid, "asset": bad,
                            "allowed": anchored[bad].get("allowed_scenes")})
        else:
            kept[sid] = spec
    bp["bindings"] = kept
    bp["anchor_aware"] = {"cleaned_by": "Phase 44 P44-1",
                          "dropped_for_anchor": dropped,
                          "kept": len(kept)}
    p.write_text(json.dumps(bp, ensure_ascii=False, indent=1), encoding="utf-8")
    print("绑定表锚定清理：保留 {} 条 | **因锚定删除 {} 条**".format(len(kept), len(dropped)))
    for d in dropped:
        print("   删除 {} → {}（仅允许 {}）".format(
            d["scene"], d["asset"], ",".join(d["allowed"][:4])))
    print("-> " + str(p.relative_to(R)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
