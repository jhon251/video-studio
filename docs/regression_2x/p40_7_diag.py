# -*- coding: utf-8 -*-
"""Phase 40 / P40-1 诊断：F 实盘的**固定景**内部约束结构（可动余量分析）。

目的：定量回答「cap=3 + 间距≥3 + 相邻禁同」在 17 张池下是否**结构性不可行**。
"""
from __future__ import annotations

import collections
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
SB = R / "output" / "phase36_p36_4_sandbox"
sys.stdout.reconfigure(encoding="utf-8")
CAP, GAP = 3, 3


def main() -> int:
    tl = json.loads((SB / "material_timeline.json").read_text(encoding="utf-8"))["decisions"]
    ids = [d["scene_id"] for d in tl]
    real = {d["scene_id"]: ((d.get("selected_asset") or {}).get("asset_id")) for d in tl}
    why = {d["scene_id"]: str(d.get("fallback_reason"))[:26] for d in tl}
    kind = {}
    for d in tl:
        r = str(d.get("fallback_reason"))
        kind[d["scene_id"]] = ("binding" if "具名绑定" in r else
                               ("parent_fallback" if "父景绑定回退" in r else "auto"))
    cnt = collections.Counter(v for v in real.values() if v)
    print("总景 {} | 素材种类 {}".format(len(ids), len(cnt)))
    print("类别: {}".format(dict(collections.Counter(kind.values()))))
    print("用量: max={} | 分布={}".format(max(cnt.values()),
                                        dict(collections.Counter(cnt.values()))))
    print()
    # 相邻同素材（全部 + 按类别）
    adj = [(ids[i - 1], ids[i], real[ids[i]]) for i in range(1, len(ids))
           if real[ids[i]] and real[ids[i - 1]] == real[ids[i]]]
    print("相邻同素材 {} 处:".format(len(adj)))
    for a, b, x in adj:
        print("   {} → {} | {} | {} | {}".format(a, b, x[:18], kind[a], kind[b]))
    print()
    # 父景回退造成重复的痕迹
    rep = collections.defaultdict(list)
    for s in ids:
        if real.get(s):
            rep[real[s]].append(s)
    print("每个素材的景序（≥2 的）:")
    for a, ss in sorted(rep.items(), key=lambda x: -len(x[1])):
        if len(ss) >= 2:
            idxs = [ids.index(s) for s in ss]
            print("   {:<22} n={} 位置{} 类别{}".format(
                a[:22], len(ss), idxs, [kind[s][:5] for s in ss]))
    print()
    # 理论可行性：36 景、cap=3、gap=3
    print("=== 可行性算术 ===")
    print("  cap=3 ⇒ 需 ≥ ceil(36/3) = {} 张等效可用".format(-(-36 // 3)))
    print("  gap=3 ⇒ 同素材两次出现间隔 ≥4 位；36 景下每张最多 {} 次".format(
        (36 + GAP) // (GAP + 1)))
    print("  实际池 {} 张 ⇒ 上限 {} 景位（≥36 ⇒ **cap 单独可行**）".format(
        len(cnt), len(cnt) * CAP))
    print("  但**父景回退**把同一素材强制绑到同一父段的多个派生景 ⇒ 与「间距≥3」直接冲突")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
