# -*- coding: utf-8 -*-
"""Phase 40 / P40-1 验证：用 **F 的真实时间轴** + 复算候选，跑约束满足，看能否归零。

若归零 ⇒ 生产分配器修复有据；若不能 ⇒ 输出最小违例解 + 卡死景（触发 §1b 判断）。
"""
from __future__ import annotations

import collections
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import allocation as AL                                    # noqa: E402

SB = R / "output" / "phase36_p36_4_sandbox"
CPP = R / "output" / "p40_probe" / "candidates_per_scene.json"
L = R / "docs" / "regression_2x" / "logs"


def main() -> int:
    tl = json.loads((SB / "material_timeline.json").read_text(encoding="utf-8"))["decisions"]
    ids = [d["scene_id"] for d in tl]
    real = {d["scene_id"]: ((d.get("selected_asset") or {}).get("asset_id")) for d in tl}
    cpp = {r["scene_id"]: [c["asset_id"] for c in (r.get("candidates") or [])
                           if c.get("asset_id") and c.get("usable", True) is not False]
           for r in json.loads(CPP.read_text(encoding="utf-8"))}
    # 候选表命名空间是 asset_p33_*（与实盘 asset_<sha12> 不同）⇒ 不可直接用。
    # 因此本验证**只用实盘真实候选**：从实盘 MATERIAL_TIMELINE 的决策里取
    # `selected_asset` + **pool 全量**作为可选（保守：允许换到池内任意素材）。
    pool = json.loads((L / "phase33_retrieval_payload.json").read_text(encoding="utf-8"))
    all_assets = ["asset_" + str(c["sha256"])[:12] for c in pool["candidates"]
                  if c.get("path")]
    print("池素材 {} 张 | 景 {}".format(len(all_assets), len(ids)))
    # 可选集：实盘已选（首选）+ 池内其余（按当前用量升序，鼓励分散）
    usage = collections.Counter(v for v in real.values() if v)
    options = {}
    for s in ids:
        cur = real.get(s)
        rest = sorted(all_assets, key=lambda a: (usage.get(a, 0), a))
        opts = ([cur] if cur else []) + [a for a in rest if a != cur]
        options[s] = opts
    res = AL.satisfy(ids, options, initial=real, cap=3, gap=3)
    r = res["report"]
    print()
    print("=== 约束满足结果（局部搜索，仅用实盘已选 + 池内其余）===")
    print("  相邻违例 {} | 间距违例 {} | cap 违例 {} | max 景/素材 {}".format(
        r["adjacent_violations"], r["gap_violations"], r["cap_violations"] or "无",
        r["max_scenes_per_asset"]))
    print("  可动景 {} | 固定景 {}".format(r["movable_scenes"], r["fixed_scenes"]))
    print("  PASS = {}".format(res["pass"]))
    print()
    print("  用量: {}".format(json.dumps(
        {k[:14]: v for k, v in sorted(res["usage"].items(), key=lambda x: -x[1])[:8]},
        ensure_ascii=False)))
    ch = [s for s in ids if res["assignment"].get(s) != real.get(s)]
    print("  改选 {} 景".format(len(ch)))
    (L / "p40_solver_validation.json").write_text(json.dumps(
        {"schema": "p40-solver-validation-v1", "report": r, "pass": res["pass"],
         "changed_scenes": ch, "usage": res["usage"],
         "note": ("候选表 `asset_p33_*` 与实盘 `asset_<sha12>` **命名空间不同** ⇒ "
                  "本验证以实盘已选 + 池内全量为可选集（保守），仅验证**约束求解能力**，"
                  "不代表生产候选集。")}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("-> docs/regression_2x/logs/p40_solver_validation.json")
    return 0 if res["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
