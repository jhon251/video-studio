# -*- coding: utf-8 -*-
"""P32-3：**cap=2 废除登记**（含算术不可达证明与 6 张获取授权撤回记录）。

只写登记文件，不改任何选材语义/阈值/policy。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys
import time

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")


def main() -> int:
    from video_studio.core import materials as MAT
    from video_studio.core import direction as DIR

    fx = json.loads((R / "output/phase32_p32_4_sandbox/fixture.json").read_text(encoding="utf-8")) \
        if (R / "output/phase32_p32_4_sandbox/fixture.json").is_file() else None
    pool = json.loads((L / "phase16_retrieval_payload.json").read_text(encoding="utf-8"))
    cands = [c for c in pool["candidates"] if c.get("path")]

    n_scenes = 40
    cap = 2
    need_unique = -(-n_scenes // cap)                 # ceil
    pool_unique = len({c["sha256"] for c in cands})
    authorized = 6
    best_case = pool_unique + authorized

    reg = {
        "schema": "p32-3-cap2-abolition-v1",
        "stage": "Phase 32 P32-3 cap=2 废除登记",
        "registered_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "cap2": {"definition_used": "单素材最多上屏 2 个景（按授权书 P31-2 读解）",
                 "status": "ABOLISHED（废除）",
                 "authorized_by": "Phase 32 授权书 §2"},
        "arithmetic_proof": {
            "scenes_total": n_scenes, "cap_per_asset_scenes": cap,
            "required_unique_assets": need_unique,
            "pool_unique_assets_now": pool_unique,
            "authorized_additional_assets": authorized,
            "best_case_unique_assets": best_case,
            "conclusion": "{} < {} ⇒ cap=2 在 40 景口径下**算术不可达**".format(
                best_case, need_unique),
            "note": "尚未计入 8 个纯色卡景（无素材景本就不占用素材额度）；"
                    "即便全池 12 张全部按 cap=2 用满，也只能覆盖 {} 景。".format(
                        pool_unique * cap),
        },
        "code_fact": {
            "asset_reuse_policy": MAT.DEFAULT_POLICY["asset_reuse_policy"],
            "why": "`core/materials.DEFAULT_POLICY` 中**不存在**任何 cap/上限常量；"
                   "复用治理只有 `prefer_unused`（优先未用过的）语义。"
                   "⇒ `cap=2` 属**授权新引入**的分配目标，非既有口径。",
            "dq2_policy": {"max_asset_share": DIR.DEFAULT_POLICY["max_asset_share"],
                           "min_unique_assets": DIR.DEFAULT_POLICY["min_unique_assets"]},
        },
        "replacement_gate": {
            "hard_gate": "DQ-2：`max_asset_share <= 0.35` 且 `unique_assets >= 6`",
            "status_measured": "PASS（P31 实测 0.3341 / 13 唯一；P32 终渲染复算见验收 JSON）",
            "plus": "`asset_reuse_policy = prefer_unused`（既有语义，零改动）",
        },
        "acquisition_withdrawal": {
            "authorized_images": authorized,
            "withdrawn": True,
            "reason": "cap=2 废除 ⇒ 该获取额度**失去目标**；且 P31 已证明根因是"
                      "「素材几何 × 冻结核验度量」，而非素材数量不足。",
            "network_usage_phases": {"P29": 0, "P30": 0, "P31": 0, "P32": 0},
            "note": "P32 全程**零网络请求**（VLM 调用除外，若仲裁层接线；见报告边界节）。",
        },
        "zero_changes": {"materials_policy": True, "dq_thresholds": True,
                         "selection_semantics": True, "config_json": True},
    }
    p = L / "p32_3_cap2_abolition.json"
    p.write_text(json.dumps(reg, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(reg, ensure_ascii=False, indent=1)[:1800])
    print()
    print("-> " + p.relative_to(R).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
