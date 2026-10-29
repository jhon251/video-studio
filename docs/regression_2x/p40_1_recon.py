# -*- coding: utf-8 -*-
"""Phase 40 / P40-1 侦察：F 候选的**逐景候选结构** + 已声明的 low_discriminative 素材。

用途：判定「cap=3 + 间距≥3」在 17 张池下是否**结构性可行**（决定是否需 §1b 破局获取）。
"""
from __future__ import annotations

import collections
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
SB = R / "output" / "phase36_p36_4_sandbox"
sys.stdout.reconfigure(encoding="utf-8")


def main() -> int:
    dec = json.loads((SB / "material_timeline.json").read_text(encoding="utf-8"))["decisions"]
    pool = json.loads((L / "phase33_retrieval_payload.json").read_text(encoding="utf-8"))
    cand = {str(c["sha256"]): c for c in pool["candidates"] if c.get("path")}
    print("景数 {} | 池 {} 张".format(len(dec), len(cand)))
    print()
    # 候选广度
    widths = collections.Counter(len(d.get("candidates") or []) for d in dec)
    print("逐景候选数分布: {}".format(dict(sorted(widths.items()))))
    print()
    # low_discriminative 标记
    low = {h: c.get("name") for h, c in cand.items()
           if c.get("low_discriminative") or c.get("discriminative") is False
           or "low_discriminative" in json.dumps(c, ensure_ascii=False)}
    print("池内 low_discriminative 标记素材: {}".format(
        json.dumps({k[:14]: v for k, v in low.items()}, ensure_ascii=False) or "无"))
    # 逐景候选
    print()
    print("{:<8} {:<16} {:>4}  {}".format("scene", "selected", "cands", "候选(前6)"))
    for d in dec:
        sel = ((d.get("selected_asset") or {}).get("asset_id") or "-")
        cs = [(c.get("asset_id") or "")[:14] for c in (d.get("candidates") or [])]
        print("{:<8} {:<16} {:>4}  {}".format(
            d["scene_id"], sel[:14], len(cs), ",".join(cs[:6])))
    # 每景候选是否覆盖全部池
    full = sum(1 for d in dec if len(d.get("candidates") or []) >= len(cand))
    print()
    print("候选表覆盖整池的景: {} / {}".format(full, len(dec)))
    # 301ff 的 4 个景
    t = "301ff850be9c"
    hit = [d["scene_id"] for d in dec
           if str(((d.get("selected_asset") or {}).get("asset_id")) or "").startswith("asset_" + t)
           or t in str((d.get("selected_asset") or {}).get("sha256") or "")]
    print("301ff 上屏景: {}".format(hit))
    for d in dec:
        if d["scene_id"] in hit:
            print("   {} 候选数 {} ⇒ 有替代: {}".format(
                d["scene_id"], len(d.get("candidates") or []),
                len(d.get("candidates") or []) > 1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
