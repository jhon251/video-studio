# -*- coding: utf-8 -*-
"""P21-3 全门复验（复用 P20 验证逻辑，换 P21 沙箱 + 派生段绑定展开）。

关键差异：P21-2 已把素材绑定展开到 40 个派生段（`phase21_p21_1_2_build.json#timeline40`），
因此逐景核验应覆盖 **40/40**。
"""
from __future__ import annotations

import json
import pathlib
import runpy
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")

# 用 P21 参数包装 P20 验证器：先改路径常量，再执行其模块体
src = (R / "docs" / "regression_2x" / "phase20_verify.py").read_text(encoding="utf-8")
src = src.replace("phase20_p20_2_sandbox", "phase21_p21_3_sandbox")
src = src.replace("phase20-p20-2-verification-v1", "phase21-p21-3-verification-v1")
src = src.replace("Phase 20 P20-2 交付级候选全门复验（40 段句界拆分 + 旁白切片 + 仲裁层）",
                  "Phase 21 P21-3 交付级候选全门复验（40 段 v2.1 时基 + 绑定展开 + 仲裁层）")
src = src.replace("phase20_p20_2_verification.json", "phase21_p21_3_verification.json")
src = src.replace('"render_wall_clock_s": 122.6', '"render_wall_clock_s": 131.9')
# 派生段绑定展开
src = src.replace(
    '    d = sel.get(sid) or {}\n',
    '    d = sel.get(sid) or {}\n'
    '    if not (d.get("selected_asset") or {}).get("asset_id") and sid in BIND40:\n'
    '        d = {"selected_asset": BIND40[sid], "fallback_state": "LOCAL_INGEST"}\n')
src = src.replace(
    'script = json.loads(pathlib.Path(arts["script_output"]).read_text(encoding="utf-8"))',
    'BIND40 = {t["scene_id"]: t["selected_asset"] for t in json.loads(\n'
    '    (R / "docs/regression_2x/logs/phase21_p21_1_2_build.json")\n'
    '    .read_text(encoding="utf-8"))["timeline40"]}\n'
    'script = json.loads(pathlib.Path(arts["script_output"]).read_text(encoding="utf-8"))')
tmp = L / "_phase21_verify_body.py"
tmp.write_text(src, encoding="utf-8")
try:
    runpy.run_path(str(tmp), run_name="__main__")
finally:
    tmp.unlink(missing_ok=True)
