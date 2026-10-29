# -*- coding: utf-8 -*-
"""Phase 13-E 续跑 / P13E-2 结论固化：权威底片上 **S05 替换已实现**（新拼接为 no-op）。

只写结论文件；不渲染、不改任何产物。证据全部来自既有 H5/DCv2 记录（只读）。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import lineage_guard as LG                                     # noqa: E402

guard = LG.check_lineage(LG.authoritative_film(R), root=R)
plan = json.loads((L / "phase6f_rebuild_plan_v2.json").read_text(encoding="utf-8"))
tl = plan["new_production_timeline"]
s05_tl = next(e for e in tl if str(e.get("scene_id")) == "S05")
timing_only = all(e.get("selected_asset") is None and e.get("asset_id") is None for e in tl)
h5 = json.loads((L / "phase6g_exec_h5.json").read_text(encoding="utf-8"))
ar = h5.get("asset_records") or {}
first = list(ar.values())[0] if ar else {}
binding = h5.get("binding") or {}
gates = h5.get("gates") or {}
gate_pass = gates.get("pass") or []
pi = h5.get("PI") or {}
p0_s05 = [g for g in gate_pass if "S05" in str(g)]
new_asset_id = first.get("asset_id")
conclusion = {
    "schema": "phase13e-p13e2-finding-v1",
    "finding": "NO_OP_ON_AUTHORITATIVE_BASE",
    "summary": "权威（DCv2/H5 978.7s）底片上 **S05 已经是 Russell 页**（H5 谱系已人工验收并绑定）⇒ "
               "在正确底片上再次执行同一 REPLACE 属 **no-op**；P13-4 的目标（S05=Russell）在权威底片上**已达成**，"
               "且该底片 PI 历史全 PASS。故本阶段**不做无意义的重复拼接渲染**，改为**核验既有绑定**（本文件即证据）。",
    "guard": guard,
    "authoritative_timeline": {
        "source": "logs/phase6f_rebuild_plan_v2.json#new_production_timeline",
        "scenes": len(tl),
        "s05_window": [s05_tl.get("start_s"), s05_tl.get("end_s")],
        "narrative_window_s": s05_tl.get("narrative_window_s"),
        "pause_after_s": s05_tl.get("pause_after_s"),
        "nature": "**纯时基计划**：21 条仅含 time 字段，**无素材绑定**（selected_asset/asset_id 全为 null）",
        "timing_only_no_asset_binding": timing_only,
    },
    "h5_lineage_binding_evidence": {
        "asset_record": {"asset_id": new_asset_id, "path": first.get("path"),
                         "sha256": first.get("sha256"), "license": first.get("license")},
        "binding": binding,
        "gate_pass_s05": p0_s05,
        "pi": {"pre": pi.get("pre"), "post": pi.get("post"), "frozen_recheck": pi.get("frozen_recheck")},
        "expected_asset_sha256": "65377b888b7782260c1cf3717a5eb9681b21e27d4d75473a95506bc397b9a6ff",
        "asset_sha256_verified": first.get("sha256")
        == "65377b888b7782260c1cf3717a5eb9681b21e27d4d75473a95506bc397b9a6ff",
    },
    "byproduct_notes": {
        "caption_time_base_in_h5_report": False,
        "note": "H5 报告顶层未持久化 `_caption_time_base`/`timeline_identity`（其门禁 'P6 DCv2 timeline identity 校验通过' "
                "为执行期校验）⇒ 若未来仍需在权威底片上做**真实拼接**，须先定位该时基的持久化来源，"
                "否则执行器 `assert_timeline_identity(ctx)` 无法满足。**本阶段未尝试绕过该门禁。**",
    },
    "why_no_splice_was_run": [
        "权威底片已含已批准替换（证据见上）⇒ 同操作 no-op，重跑不产生新信息",
        "若强行为之，只会产出与 H5 母片等价的重复文件（浪费算力，且违反'不做无意义动作'立场）",
        "13-D 的 PI BLOCKED 已被 P13E-1 定格为**底片谱系错误的度量伪影**（v9 1532s），与替换本身无关",
    ],
    "still_pending": {
        "P13E-3": "运动臂全片候选（S05 已替换 + 运动层 enabled，管线级端到端）**未执行**；"
                  "需一次全片渲染 + 全门复验（含 S06 corr 小裕度如实记录、不调阈值）+ DQ 双口径报告（DQ-3 不宣称 PASS）",
        "tests_suite": "守卫套件已加入 `tests/lineage_guard_test.py`（本阶段执行）；全量回归结果见 STATUS/报告",
    },
    "zero_render": True, "zero_llm": True, "zero_network": True,
    "no_threshold_touched": True, "no_promotion": True,
}
out = L / "phase13e_p13e2_finding.json"
out.write_text(json.dumps(conclusion, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
print("守卫:", guard["verdict"], "| 权威轴为纯时基计划:", timing_only,
      "| S05 窗口:", conclusion["authoritative_timeline"]["s05_window"])
print("H5 绑定 S05 =", binding.get("S05"), "| 素材 sha 校验:",
      conclusion["h5_lineage_binding_evidence"]["asset_sha256_verified"])
print("P0-S05 门禁:", p0_s05)
print("结论:", conclusion["finding"])
print("产物:", out.name)
