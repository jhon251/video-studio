# -*- coding: utf-8 -*-
"""P32-4 诊断：生产逐景核验里 bank 分支为何**静默回落到全图口径**（corr_bank 全为 None）。

复现渲染链的调用方式：ctx.config + ROOT，然后按 agent 的同一分支调用 bank_score_of。
"""
from __future__ import annotations

import json
import pathlib
import sys
import traceback

import numpy as np
from PIL import Image

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import corr_diagnostics as CD                            # noqa: E402
from video_studio.agents.editing.agent import ROOT                             # noqa: E402

ASSET = None
for c in json.loads((R / "docs/regression_2x/logs/phase16_retrieval_payload.json")
                    .read_text(encoding="utf-8"))["candidates"]:
    if c.get("sha256", "").startswith("301ff850be9c"):
        ASSET = c["path"]
FRAME = R / "projects" / "p_b9a90ed75d67" / "artifacts" / "_frame_S11p2.png"


def main() -> int:
    cfg = json.loads((R / "config" / "config.json").read_text(encoding="utf-8"))
    print("ROOT =", ROOT)
    bcfg, src = CD.resolve_config(cfg, root=ROOT)
    print("resolve_config ->", bcfg, "| src =", src)
    ver = CD.bank_version_of(bcfg.get("bank_derived"))
    print("bank_version_of ->", repr(ver))
    print("frame 存在:", FRAME.is_file(), "| asset 存在:", pathlib.Path(ASSET).is_file())
    with Image.open(FRAME) as im:
        # 生产链用的是 gray48（48×48）
        g = np.asarray(im.convert("L").resize((48, 48)), dtype=np.float64)
    print("frame gray shape:", g.shape)
    try:
        bk = CD.bank_score_of(g, ASSET, ver)
        print("bank_score_of ->", json.dumps(bk, ensure_ascii=False)[:300])
    except Exception:                                                       # noqa: BLE001
        print("bank_score_of 抛异常：")
        traceback.print_exc()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
