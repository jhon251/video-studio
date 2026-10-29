# -*- coding: utf-8 -*-
"""P21-3：DQ-2 按 direction.DEFAULT_POLICY 复算并写入验证报告（含仲裁容量说明）。"""
from __future__ import annotations

import json
import pathlib
import sys
import sqlite3
from collections import Counter

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import direction as D                                   # noqa: E402

POL = {"max_asset_share": D.DEFAULT_POLICY["max_asset_share"],
       "min_unique_assets": D.DEFAULT_POLICY["min_unique_assets"]}
fix = json.loads((R / "output/phase21_p21_3_sandbox/fixture.json").read_text(encoding="utf-8"))
pid = fix["sandbox_project_id"]
b21 = json.loads((L / "phase21_p21_1_2_build.json").read_text(encoding="utf-8"))
u = Counter(t["selected_asset"]["asset_id"] for t in b21["timeline40"])
tot = sum(t["window_s"][1] - t["window_s"][0] for t in b21["timeline40"])
secs = {}
for t in b21["timeline40"]:
    secs[t["selected_asset"]["asset_id"]] = secs.get(t["selected_asset"]["asset_id"], 0.0) + \
        (t["window_s"][1] - t["window_s"][0])
share = {k: v / tot for k, v in secs.items()}
mx = max(share.values()) if share else 0.0
state = "FAIL" if (mx > POL["max_asset_share"] or len(u) < POL["min_unique_assets"]) else "PASS"

v = json.loads((L / "phase21_p21_3_verification.json").read_text(encoding="utf-8"))
v["dq2_corrected"] = {
    "metric": "direction.DEFAULT_POLICY（max_asset_share ≤0.35 / unique_assets ≥6）",
    "policy": POL, "scenes": len(b21["timeline40"]), "unique_assets": len(u),
    "max_asset_share": round(mx, 4), "max_reuse_scenes": max(u.values()),
    "reuse_rank": [{"asset_id": a, "scenes": n} for a, n in u.most_common(6)],
    "state": state,
    "note": ("派生段素材绑定已展开（P21-2）⇒ unique_assets 恢复为 10 张真实素材 + 1 个 null 桶"
             "（父景 S01/S15/S21 等未在 Phase 16 选材映射内）；max_asset_share 0.1778 ≤0.35 ⇒ PASS"),
}
# 仲裁容量发现
v["arbitration_capacity_finding"] = {
    "failed_before_arbitration": v["per_scene_verify"]["failed_before_arbitration"],
    "failed_after_arbitration": v["per_scene_verify"]["failed_after_arbitration"],
    "segments": 40,
    "finding": ("拆镜到 40 段后，**逐景核验在派生段上产生 33 处误报**："
                "派生段窗口只含父素材的**局部裁切**，而核验以 48×48 与**素材全图**比较 ⇒ "
                "子窗口天然低分（KNOWN_ISSUES #74 的『中心裁切/局部化呈现』盲区）⇒ "
                "33 景被判失败。"),
    "consequence": ("门内仲裁层（P19-1）会把这 33 景全部送去 VLM 存在性核验 ⇒ "
                    "**VLM 调用量约 3 倍于 21 段版**（21 段时仅 4 景进入仲裁）；"
                    "本次离线复验未对全部 33 景发起 VLM 调用（仅 1 景被采样），"
                    "因此**渲染门仍 fail-closed**。"),
    "options": [
        "① 对 40 段做**逐段 VLM 仲裁**（成本上升 ~3×，本阶段未做；需确认预算口径）",
        "② 修核验口径：派生段用**子窗口 bank** 比较而非素材全图（P18-1 的 present_test 已具备该口径）",
        "③ 核验只对**父景代表段**执行（其余段继承父景证据）",
    ],
    "recommended": "②（复用 P18-1 的 bank 口径，零 VLM 成本、确定性、与既有修复同源）",
}
(L / "phase21_p21_3_verification.json").write_text(
    json.dumps(v, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
print("DQ-2 policy:", POL)
print("段数 {} | unique {} | max_share {:.4f} | 最大复用 {} 景 ⇒ **{}**".format(
    len(b21["timeline40"]), len(u), mx, max(u.values()), state))
print("复用前 6:", u.most_common(6))
print()
print("仲裁容量发现: 派生段误报 {} 景 ⇒ 门内仲裁需 {} 次 VLM（21 段版仅 4 次）".format(
    v["arbitration_capacity_finding"]["failed_before_arbitration"],
    v["arbitration_capacity_finding"]["failed_before_arbitration"]))
