# -*- coding: utf-8 -*-
"""更正 DQ-2 判定：**必须按 policy 阈值判定**，不得硬编码 PASS。

发现：P20-2 的 `dq2_corrected` 曾硬编码 `state="PASS"`，而生产 `direction.asset_reuse`
对 40 段候选实际给出 **FAIL**（`max_asset_share=0.9369 > 0.35`、`unique_assets=3 < 6`）——
根因是派生段未绑定素材（asset_id=null）导致复用极度集中。本脚本按 policy 重新判定并更正。
"""
from __future__ import annotations

import json
import pathlib
import sys
from collections import Counter

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import direction as D                                   # noqa: E402

POL = {"max_asset_share": D.DEFAULT_POLICY["max_asset_share"],
       "min_unique_assets": D.DEFAULT_POLICY["min_unique_assets"]}
print("DQ-2 policy:", POL)

for tag, fn in (("P19-21seg", "phase19_p19_4_verification.json"),
                ("P20-40seg", "phase20_p20_2_verification.json")):
    p = L / fn
    j = json.loads(p.read_text(encoding="utf-8"))
    dq2 = j.get("dq2") or {}
    share = dq2.get("max_asset_share")
    uniq = dq2.get("unique_assets")
    correct_state = ("FAIL" if (share is None or uniq is None
                                or share > POL["max_asset_share"]
                                or uniq < POL["min_unique_assets"]) else "PASS")
    old = (j.get("dq2_corrected") or {}).get("state")
    j["dq2_corrected"] = {
        **(j.get("dq2_corrected") or {}),
        "state": correct_state,
        "policy": POL,
        "max_asset_share": share, "unique_assets": uniq,
        "policy_basis": ("按 direction.DEFAULT_POLICY 判定："
                         "max_asset_share>{:.2f} 或 unique_assets<{} ⇒ FAIL".format(
                             POL["max_asset_share"], POL["min_unique_assets"])),
        "correction_note": ("更正此前硬编码 PASS 的错误" if old != correct_state
                            and old is not None else "确认"),
    }
    if correct_state == "FAIL" and j.get("dq2_corrected", {}).get("max_reuse_scenes", 0) >= 6:
        j["dq2_corrected"]["explanation"] = (
            "派生段未绑定素材（asset_id=null）导致素材集中度暴涨："
            "max_asset_share={} > {} ⇒ FAIL。"
            "修复路径见 KNOWN_ISSUES #75.3（把素材绑定展开到每个派生段 ID）。".format(
                share, POL["max_asset_share"]))
    p.write_text(json.dumps(j, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    print("  {}: DQ-2 = {} (此前记录 {}) | share={} uniq={}".format(
        tag, correct_state, old, share, uniq))

# 同步更正 promotion 材料包的判定与推荐
pp = L / "phase20_p20_3_promotion_package.json"
pk = json.loads(pp.read_text(encoding="utf-8"))
p20 = json.loads((L / "phase20_p20_2_verification.json").read_text(encoding="utf-8"))
p19 = json.loads((L / "phase19_p19_4_verification.json").read_text(encoding="utf-8"))
pk["candidates"]["A_21seg_p19"]["dq2"] = p19["dq2_corrected"]
pk["candidates"]["B_40seg_p20"]["dq2"] = p20["dq2_corrected"]
pk["candidates"]["B_40seg_p20"]["gates"] = (
    "响度/PI/字幕/运动 全 PASS；**时长契约 FAIL（992.88s）**；**逐景核验 checked 2/40 空转**；"
    "**DQ-2 FAIL**（max_asset_share {:.4f} > 0.35、unique_assets {} < 6）；DQ-3 FAIL 但显著改善".format(
        p20["dq2"].get("max_asset_share"), p20["dq2"].get("unique_assets")))
pk["comparison"]["dq2"] = (
    "unique_assets {} → {}；max_asset_share {:.4f} → {:.4f} ⇒ **PASS → FAIL**"
    "（40 段派生段未绑定素材导致集中度暴涨）".format(
        p19["dq2"].get("unique_assets"), p20["dq2"].get("unique_assets"),
        p19["dq2"].get("max_asset_share"), p20["dq2"].get("max_asset_share")))
pk["recommendation"]["reason"] = (
    "40 段候选（P20-2）**三处不通过**：① **时长契约 992.88s**（超 978.7±1s 达 +14.2s，"
    "根因见 #75.2）；② **DQ-2 FAIL**（max_asset_share 0.9369 > 0.35、unique_assets 3 < 6，"
    "因派生段未绑定素材）；③ **逐景核验 checked 2/40 空转**（#75.3）⇒ **不作为交付级候选**。"
    "21 景候选（P19-4）**全门通过 + DQ-2 PASS**，是当前唯一全门通过的候选（DQ-3 仍 FAIL，"
    "授权口径要求 DQ-2 PASS ⇒ 该候选满足 DQ 侧硬要求）。")
pk["known_limitations"].insert(
    1, "**DQ-2 FAIL（40 段）**：派生段 asset_id=null ⇒ max_asset_share 0.9369 > 0.35、unique_assets 3 < 6；"
       "需与 #75.3 一并修复（展开素材绑定到派生段）。")
pk["corrections"] = [
    "DQ-2 判定更正：此前 `dq2_corrected` 硬编码 PASS，实际按 direction.DEFAULT_POLICY 为 **FAIL**（40 段候选）。",
]
pk["one_page_summary"] = (
    "【Phase 20 一页摘要】P20-1 完成（40 段 voice 派生：零重合成、文本逐字 4927→4927、"
    "19/19 切点落在实测停顿、时基 978.634s）。P20-2 渲染 122.6s 后 **fail-closed**，**三处不通过**："
    "① 时长 992.88s（40 段 × 冻结 pause 0.75s ⇒ +14.2s，超 978.7±1s）；"
    "② **DQ-2 FAIL**（max_asset_share 0.9369 > 0.35、unique_assets 3 < 6，因派生段未绑定素材）；"
    "③ 逐景核验 **checked 2/40** 空转。响度/PI/字幕/运动 全 PASS；DQ-3 显著改善至 45.0%（max 36.836s）但未达 ≤20%。"
    "⇒ **不登记交付级候选**；**21 景版 p_50e10b27b44d 仍是唯一全门通过且 DQ-2 PASS 的候选**，交人工观看与 promotion 决策。")
pp.write_text(json.dumps(pk, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
print()
print("已更正 promotion 材料包（DQ-2 判定 + 推荐理由 + 一页摘要）")
print("  A_21seg DQ-2:", pk["candidates"]["A_21seg_p19"]["dq2"]["state"])
print("  B_40seg DQ-2:", pk["candidates"]["B_40seg_p20"]["dq2"]["state"])
