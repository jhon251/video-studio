# -*- coding: utf-8 -*-
"""P33 诊断：① 分配纪律未改选的根因（asset_id 键口径）；
             ② `script_time_base_s` 的取数口径（用于生成匹配新时基的脚本）。"""
from __future__ import annotations

import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import narration as NAR                                    # noqa: E402

# ---- ② 脚本时基取数口径 ----
import inspect
print(inspect.getsource(NAR.script_time_base_s))
SCRIPT = R / "output/phase27_script_sandbox/script_p27_v41_40seg.json"
sc = json.loads(SCRIPT.read_text(encoding="utf-8"))
print("当前 total_duration_s =", sc.get("total_duration_s"))
print("script_time_base_s    =", NAR.script_time_base_s(sc))
tb = json.loads((R / "output/phase33_voice/timebase_v41.json").read_text(encoding="utf-8"))
print("新时基（应设为何值）  =", tb["audio_time_base_s"])
print("逐段 duration_s 合计  =", round(sum(float(s.get('duration_s') or 0)
                                            for s in sc['segments']), 3))

# ---- ① 键口径：production 里 candidates 与 selected_asset 的键 ----
print()
print("=== 产物里 scene 的键（取自 MATERIAL_TIMELINE 决策的候选）===")
VOICE = R / "output/phase33_voice/voice_output_v41.json"
dec_p = R / "output/phase33_p33_4_sandbox/material_timeline.json"
if dec_p.is_file():
    dec = json.loads(dec_p.read_text(encoding="utf-8"))["decisions"]
    print("decisions 键:", sorted(dec[0].keys()))
    sa = dec[0].get("selected_asset") or {}
    print("selected_asset 键:", sorted(sa.keys()))
    print("selected_asset.asset_id =", sa.get("asset_id"))
    print("selected_asset.sha256   =", str(sa.get("sha256"))[:12])
print()
print("注：`decisions` 事件只含 selected_asset（不含 candidates），")
print("    ⇒ 分配纪律若依赖 `scene['candidates'][i]['asset_id']`，")
print("      必须确认 candidates 里确有 asset_id；否则应改用 sha256 匹配。")
