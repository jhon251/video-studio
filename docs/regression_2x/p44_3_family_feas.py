# -*- coding: utf-8 -*-
"""Phase 43 / P43-2 可行性验证：**家族份额 ≤33% 是否结构性可行**。

算术（授权书 §2 要求「不可行则如实报告」）：
  · 36 景；份额 ≤33% ⇒ 任一家族最多 `floor(36×0.33) = 11` 景；
  · 其余家族须承担 `36 − 11 = 25` 景；
  · 但**每素材 ≤3 景** ⇒ 其余家族的**素材位数上限** = (其素材数) × 3。
若 `其余素材数 × 3 < 25` ⇒ **结构性不可行**（与分配器优劣无关）。
"""
from __future__ import annotations

import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")
FAM = R / "config" / "family_map.json"
EXC = R / "config" / "content_exclusions.json"
SCENES, CAP, SHARE = 36, 3, 0.33


def main() -> int:
    fm = json.loads(FAM.read_text(encoding="utf-8"))["family_map"]
    exc = json.loads(EXC.read_text(encoding="utf-8"))["content_exclusions"]
    banned = [x["sha256_prefix"] for x in exc["excluded"]]
    fams = {}
    for fam, prefixes in fm["families"].items():
        alive = [p for p in prefixes if not any(b in p for b in banned)]
        fams[fam] = {"total": len(prefixes), "alive": len(alive),
                     "slot_capacity": len(alive) * CAP}
    print("=== 禁入后家族容量 ===")
    print("{:<14} {:>5} {:>6} {:>9}".format("家族", "标定", "在用", "景位上限"))
    for fam, v in fams.items():
        print("{:<14} {:>5} {:>6} {:>9}".format(fam, v["total"], v["alive"],
                                                v["slot_capacity"]))
    max_share_n = int(SCENES * SHARE)
    need_other = SCENES - max_share_n
    # 最有利情形：让**容量最大**的家族当"被限家族"，其余家族提供 25 景位
    best = None
    for fam in fams:
        others = sum(v["slot_capacity"] for f, v in fams.items() if f != fam)
        if best is None or others > best[1]:
            best = (fam, others)
    print()
    print("份额 ≤{:.0%} ⇒ 单一家族最多 {} 景；其余家族须承担 {} 景".format(
        SHARE, max_share_n, need_other))
    print("最有利情形（把「被限家族」设为让其余容量最大者 = {}）：".format(best[0]))
    print("  其余家族景位上限合计 = {}".format(best[1]))
    print("  {} {} ⇒ **结构性{}**".format(
        best[1], "≥" if best[1] >= need_other else "<", 
        "可行" if best[1] >= need_other else "不可行"))
    rep = {"schema": "p43-2-family-feasibility-v1", "scenes": SCENES, "cap": CAP,
           "share_limit": SHARE, "max_scenes_for_one_family": max_share_n,
           "others_must_cover": need_other,
           "families": fams, "best_case_other_capacity": best[1],
           "structurally_feasible": best[1] >= need_other,
           "conclusion": ("家族份额 ≤33% 在「每素材 ≤3 + 禁入后 16 张」下**结构性不可行**；"
                          "此为**容量算术**结论，与分配器优劣无关。")
           if best[1] < need_other else "可行"}
    (R / "docs/regression_2x/logs/p43_2_family_feasibility.json").write_text(
        json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print()
    print("-> docs/regression_2x/logs/p43_2_family_feasibility.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
