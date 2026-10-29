# -*- coding: utf-8 -*-
"""Phase 47 / P47-1：**三种候选风格样片**（同一场景，每风格 1 张，≤ ¥2）。

场景 = `P06_4`（「把证明翻译成机器能检查的语言」），提示词 = 该景既有 `visual_hint`
+ `config/gen_style.json` 里各候选风格后缀。
产出：`output/phase47_gen/samples/<风格>.jpg` + 样片台账。
"""
from __future__ import annotations

import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core.env import load_env                                      # noqa: E402
from video_studio.tools import provider_gen as PG                               # noqa: E402

OUT = R / "output" / "phase47_gen" / "samples"
CFG = R / "config" / "gen_style.json"
L = R / "docs" / "regression_2x" / "logs"


def main() -> int:
    load_env(R / ".env")
    cfg = json.loads(CFG.read_text(encoding="utf-8"))["gen_style"]
    hint = cfg["sample_visual_hint"]
    neg = cfg.get("negative_prompt")
    print("样片场景 {}｜visual_hint: {}".format(cfg["sample_scene"], hint))
    print("模型 {}｜尺寸 {}".format(cfg["model"], cfg["size"]))
    print()
    rows = []
    for sid, spec in cfg["candidates"].items():
        prompt = "{}。{}".format(hint, spec["suffix"])
        dest = OUT / "{}.jpg".format(sid)
        r = PG.generate(prompt, dest, model=cfg["model"], size=cfg["size"],
                        negative=neg)
        row = {"style_id": sid, "label": spec["label"], "suffix": spec["suffix"],
               "prompt": prompt, "ok": r.get("ok"), "error": r.get("error"),
               "task_id": r.get("task_id"), "sha256": r.get("sha256"),
               "width": r.get("width"), "height": r.get("height"),
               "bytes": r.get("bytes"), "path": r.get("path")}
        rows.append(row)
        if r.get("ok"):
            print("  OK   {:<18} {}x{} {:,}B  task={}".format(
                sid, r["width"], r["height"], r["bytes"], str(r["task_id"])[:12]))
        else:
            print("  FAIL {:<18} {}".format(sid, r.get("error")))
    ok = [x for x in rows if x["ok"]]
    art = {"schema": "p47-1-gen-samples-v1",
           "scene": cfg["sample_scene"], "visual_hint": hint,
           "model": cfg["model"], "size": cfg["size"],
           "negative_prompt": neg, "samples": rows,
           "ok_count": len(ok), "total": len(rows),
           "budget_cny_cap": cfg["budget_cny"]["samples"],
           "provenance": cfg["provenance"],
           "note": "样片交项目所有者选定风格；选定后写入 frozen_style_suffix + sha256"}
    (L / "p47_1_gen_samples.json").write_text(
        json.dumps(art, ensure_ascii=False, indent=1), encoding="utf-8")
    print()
    print("样片 {}/{} 成功".format(len(ok), len(rows)))
    print("-> output/phase47_gen/samples/ 与 docs/regression_2x/logs/p47_1_gen_samples.json")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
