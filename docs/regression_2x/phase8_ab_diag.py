# -*- coding: utf-8 -*-
"""Phase 8 只读诊断：查看 A/B 两臂 raw_text 的头尾与结构特征。"""
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")
for name in ("phase8_ab_v2.json", "phase8_ab_v3.json",
             "phase8_ab_attempt1_truncated_v2.json", "phase8_ab_attempt1_truncated_v3.json"):
    p = R / "docs" / "regression_2x" / "logs" / name
    j = json.loads(p.read_text(encoding="utf-8"))
    t = j.get("raw_text") or ""
    print("==", name)
    print("   usage:", j.get("usage"), "| truncated:", j.get("output_truncated"),
          "| json_valid:", j.get("json_valid"), "| len(raw):", len(t))
    print("   head:", repr(t[:220]))
    print("   tail:", repr(t[-220:]))
    print("   含围栏:", "```" in t, "| 含 '{':", "{" in t, "| 末尾 '}':", t.rstrip().endswith("}"))
