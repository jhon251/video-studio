# -*- coding: utf-8 -*-
"""Phase 43 / P43-2 可行性验证（v2，**基于真实候选域**）。

v1 只算了「素材位数」的容量算术 ⇒ 得出「可行」，但那忽略了**每景的真实候选域**：
若某景候选里只有家族 A 的素材，则该景**只能**落在 A ⇒ A 份额被结构性抬高。
本脚本按**每景实际可选家族**计算 A 份额的**下界**（乐观分配：把每景尽量分给非 A）。
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
from video_studio.core import allocation as AL                                   # noqa: E402

SCENES, CAP, SHARE = 36, 3, 0.33


def main() -> int:
    fm = json.loads((R / "config/family_map.json").read_text(encoding="utf-8"))["family_map"]
    fam_map = dict(fm["families"])
    script = json.loads((R / "output/phase36_script_sandbox/script_p36_v65_36seg.json")
                        .read_text(encoding="utf-8"))
    pool = json.loads((R / "docs/regression_2x/logs/phase33_retrieval_payload.json")
                      .read_text(encoding="utf-8"))
    cands = [c for c in pool["candidates"] if c.get("path")]
    tl = EA._build_material_timeline(script, [], cands,
                                     policy=MAT.policy_from_config(None),
                                     material_provided=True)
    # 逐景可选家族
    per = []
    for d in tl:
        fams = collections.Counter()
        for c in (d.get("candidates") or []):
            f = AL._family_of(c.get("asset_id"), fam_map)
            if f:
                fams[f] += 1
        per.append({"scene": d["scene_id"], "families": dict(fams)})
    only_a = [p["scene"] for p in per if set(p["families"]) == {"A_纸面符号"}]
    empty = [p["scene"] for p in per if not p["families"]]
    a_forced = len(only_a)
    print("景 {} | **只能落家族 A** 的景 = {} | 无候选 = {}".format(
        len(per), a_forced, len(empty)))
    print("  只能落 A 的景: {}".format(only_a[:10]))
    print()
    print("A 家族素材数 8 ⇒ A 景位上限 {}（cap={}）".format(8 * CAP, CAP))
    print("份额上限 33% ⇒ A 最多 {} 景".format(int(SCENES * SHARE)))
    print("  A **至少** {} 景（被迫）⇒ 下界份额 {:.1%}".format(
        a_forced, a_forced / SCENES))
    # 乐观求解：最大化非 A
    ids = [d["scene_id"] for d in tl]
    real = {d["scene_id"]: ((d.get("selected_asset") or {}).get("asset_id")) for d in tl}
    opts = {}
    for d in tl:
        sid = d["scene_id"]
        cs = [c.get("asset_id") for c in (d.get("candidates") or [])
              if c.get("asset_id") and c.get("usable", True) is not False]
        cur = real.get(sid)
        if cur and cur not in cs:
            cs = [cur] + cs
        # 优先把非 A 放前面（乐观）
        cs = sorted(cs, key=lambda a: 0 if AL._family_of(a, fam_map) != "A_纸面符号" else 1)
        opts[sid] = cs
    best = None
    for share in (0.33, 0.36, 0.40, 0.45, 0.50):
        r = AL.satisfy(ids, opts, initial=real, cap=CAP, gap=3,
                       fam_map=fam_map, max_family_share=share,
                       restarts=24, iters=900)
        fc = r["report"].get("family_counts") or {}
        a = fc.get("A_纸面符号", 0)
        print("  share 限 {:.0%} ⇒ pass={} A={} ({:.1%})".format(
            share, r["pass"], a, a / SCENES))
        if best is None:
            best = (share, r, a)
        if r["pass"]:
            best = (share, r, a)
            break
    print()
    ok = best[1]["pass"]
    print("结论：{}".format(
        "在份额限 {:.0%} 下**可满足**".format(best[0]) if ok
        else "在试过的份额限下**均不可满足** ⇒ 受**候选域**限制（非纯容量算术）"))
    (R / "docs/regression_2x/logs/p43_2_family_feasibility.json").write_text(
        json.dumps({"schema": "p43-2-family-feasibility-v2",
                    "scenes": SCENES, "cap": CAP,
                    "max_scenes_one_family_at_33pct": int(SCENES * SHARE),
                    "scenes_forced_to_family_A": a_forced,
                    "forced_A_scenes": only_a,
                    "empty_domain_scenes": empty,
                    "A_lower_bound_share": round(a_forced / SCENES, 4),
                    "tested_share_limits": "0.33/0.36/0.40/0.45/0.50",
                    "best_feasible_share_limit": best[0] if ok else None,
                    "pass_at_best": ok,
                    "A_count_at_best": best[2],
                    "conclusion": ("受**候选域**限制：部分景候选内只有家族 A 素材 ⇒ "
                                   "A 份额有**下界**；33% 不可达，实测最小可行份额见 "
                                   "`best_feasible_share_limit`。")},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print("-> docs/regression_2x/logs/p43_2_family_feasibility.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
