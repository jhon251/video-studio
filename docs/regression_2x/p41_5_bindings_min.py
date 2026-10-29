# -*- coding: utf-8 -*-
"""Phase 36 / P36-4 前置（v2）：**最小具名绑定集**。

动机（实测踩坑）：首版对**全部 36 景**都声明了具名绑定 ⇒ 但 P34-1 机制**只在自动选材
未命中（纯色卡）时介入** ⇒ 22 个景其实由自动选材命中、绑定**未被使用**
⇒ no_picture 门 N2「声明 36 / 生效 14」**正确地报为 FAIL**（声明与生效不一致）。

处置：**只对「自动选材会失败」的景声明绑定** —— 用生产选材逻辑做一次**干跑**，
找出会落卡的景，再按语义给这些景具名绑定。这样「声明 == 生效」。
"""
from __future__ import annotations

import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.agents.editing.agent import EditingAgent as EA                 # noqa: E402
from video_studio.core import materials as MAT                                   # noqa: E402

L = R / "docs" / "regression_2x" / "logs"
VOICE = R / "output" / "phase36_voice"
SCRIPT = R / "output/phase36_script_sandbox/script_p36_v65_36seg.json"
POOL = L / "phase33_retrieval_payload.json"
OUT = VOICE / "bindings_proposal.json"

TOPIC = [
    (["四色", "地图", "上色", "区域"], "301ff850be9c"),
    (["归约", "构型", "有限多种", "无穷多"], "1d2fe4b325bd"),
    (["读完", "读一遍", "没有一个人", "没有人读"], "a3aff2f300eb"),
    (["审稿", "期刊", "背书", "拖"], "f0cd2a28016d"),
    (["Tymoczko", "哲学", "认识论", "地基", "标准"], "65377b888b77"),
    (["Detlefsen", "Luker", "反驳", "共同体"], "acaa16094c3b"),
    (["单群", "几百位", "接力", "分工"], "23e71bc8a864"),
    (["开普勒", "球", "橘子", "最密", "堆"], "a3f0e27204cd"),
    (["Hales", "99", "没有洞"], "bd383463dbb9"),
    (["Flyspeck", "形式化", "十六年", "编译器"], "1e9d2ab4e64e"),
    (["Lean", "mathlib", "代码", "标准件"], "1e9d2ab4e64e"),
    (["Scholze", "菲尔兹", "挑战", "Liquid", "挑刺"], "33b360a5363c"),
    (["AlphaGeometry", "IMO", "几何", "辅助线", "银牌", "奖牌"], "432cd85be6f1"),
    (["出题", "自己写", "三代", "封条", "机器"], "cfae038f6106"),
]


def main() -> int:
    script = json.loads(SCRIPT.read_text(encoding="utf-8"))
    pool = json.loads(POOL.read_text(encoding="utf-8"))
    cands = [c for c in pool["candidates"] if c.get("path")]
    by_sha = {str(c["sha256"]): c for c in cands}
    segs = script["segments"]
    # ---- 干跑生产选材（不带具名绑定）找出会落卡的景 ----
    tl = EA._build_material_timeline(
        script, [], cands, policy=MAT.policy_from_config(None),
        material_provided=True)
    would_card = [d["scene_id"] for d in tl
                  if not (d.get("selected_asset") or {}).get("asset_id")]
    print("干跑：{} 景 ⇒ 会落卡 {} 景".format(len(segs), len(would_card)))
    # ---- 只给这些景绑定 ----
    binds, used, reasons = {}, {}, {}
    seg_by_id = {s["scene_id"]: s for s in segs}
    for sid in would_card:
        text = seg_by_id[sid]["narration"]
        pick = None
        for kws, pre in TOPIC:
            if any(k in text for k in kws):
                hit = next((h for h in by_sha if h.startswith(pre)), None)
                if hit:
                    pick = hit
                    break
        if pick is None:
            order = sorted(by_sha, key=lambda h: (used.get(h, 0), h))
            pick = order[0]
        binds[sid] = pick
        used[pick] = used.get(pick, 0) + 1
        reasons[sid] = "自动选材无候选 ⇒ 具名绑定（{}）".format(
            (by_sha[pick].get("name") or "")[:34])
    detail = {sid: {"sha256": h, "name": by_sha[h].get("name"), "reason": reasons[sid],
                    "approval_document": "Phase 34 授权书 §1(a)（P36 逐景重映射）"}
              for sid, h in binds.items()}
    OUT.write_text(json.dumps({
        "schema": "p36-per-scene-bindings-v2",
        "method": "干跑生产选材找出会落卡的景 ⇒ 只对这些景声明绑定（声明==生效）",
        "scene_count": len(segs), "would_card": would_card,
        "bound": len(binds), "usage": used, "bindings": detail,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("最小绑定集：{} 景 ⇒ {}".format(len(binds), sorted(binds)))
    print("-> " + str(OUT.relative_to(R)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
