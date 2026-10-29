# -*- coding: utf-8 -*-
"""诊断：把真值集前几对的**实际提示词**与模型回答打出来，判断输入是否足够。"""
from __future__ import annotations

import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core.env import load_env                                # noqa: E402
load_env(R / ".env")
from video_studio.tools import vlm_judge as V                             # noqa: E402

truth = json.loads((R / "tests/fixtures/vlm_relevance_truth_v1.json")
                   .read_text(encoding="utf-8"))
cfg, src = V.resolve_config(json.loads((R / "config/config.json").read_text(encoding="utf-8")),
                            root=R)
print("provider:", cfg["model"], "| available:", V.available(cfg))
print()

for p in truth["pairs"][:3]:
    req = p["requirement_snapshot"]
    print("=" * 78)
    print("pair:", p["pair_id"], "| 人工 =", p["human_label"])
    print("scene:", p["scene_id"], "| asset:", p["asset_key12"], "|", p["asset_origin"])
    print("人工理由:", p["human_reason"])
    print("-" * 78)
    print("渲染后的需求文本（模型实际看到的需求）:")
    print(V.requirement_text(req))
    print("-" * 78)
    print("requirement_snapshot 原始字段:")
    print(json.dumps(req, ensure_ascii=False, indent=1))
    res = V.judge_pair(requirement=req, image_path=p["image_path"], cfg=cfg, root=R)
    print("-" * 78)
    print("模型判定:", res["label"], "| conf:", res["confidence"])
    print("模型理由:", res["reason"])
    print("图像:", json.dumps(res.get("image"), ensure_ascii=False))
    print("成本: ${:.6f} | tokens in/out: {}/{}".format(
        res["cost_usd"], res["tokens_in"], res["tokens_out"]))
