# -*- coding: utf-8 -*-
"""读取 P27/P30 验证与渲染证据中的门禁结果（DQ-2/DQ-3/逐景核验/三指标/时长）。只读。"""
from __future__ import annotations

import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")

FILES = ["phase27_p27_3_verification.json", "phase30_p30_1_acceptance.json",
         "phase19_p19_4_verification.json"]


def main() -> int:
    for f in FILES:
        p = L / f
        if not p.exists():
            print("[missing]", f)
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        print("=" * 78)
        print("FILE:", f)
        print("  schema:", d.get("schema"), "| stage:", d.get("stage"))
        print("  keys:", list(d.keys()))
        for k in ("gate_summary", "duration_contract", "loudness", "motion_metrics",
                  "subtitle", "pi_pre", "pi_post", "per_scene_verify"):
            if k in d:
                s = json.dumps(d[k], ensure_ascii=False)
                print("  {:<20} {}".format(k, s[:600]))
        if "dq2" in d:
            dq = d["dq2"]
            print("  dq2: state={} unique={} max_share={} thr={}".format(
                dq.get("state"), dq.get("unique_assets"), dq.get("max_asset_share"),
                dq.get("threshold")))
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
