# -*- coding: utf-8 -*-
"""Phase 55 / P55-3：**黑板基底样片**（同一基底 × 3 种笔迹密度/明度变体，各 1 张，≤ ¥2）。

与 P55-1 **零耦合**（可并行/独立执行）。
产出：`output/phase55_bb/samples/<variant>.png` + `logs/p55_3_bb_samples.json`
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

OUT = R / "output" / "phase55_bb" / "samples"
CFG = R / "config" / "gen_style_blackboard.json"
L = R / "docs" / "regression_2x" / "logs"


def main() -> int:
    load_env(R / ".env")
    g = json.loads(CFG.read_text(encoding="utf-8"))["gen_style"]
    bb = g["blackboard_base"]
    neg = g.get("negative_prompt")
    print("黑板基底样片：{} 个变体 | 场景 {}".format(
        len(bb["variants"]), bb["sample_scene"]))
    rows = []
    for vid, spec in bb["variants"].items():
        prompt = "{}。{}".format(bb["base_suffix"], spec["delta"])
        dest = OUT / "{}.png".format(vid)
        r = PG.generate(prompt, dest, model=g["model"], size=g["size"], negative=neg)
        rows.append({"variant": vid, "label": spec["label"], "delta": spec["delta"],
                     "prompt": prompt, "ok": r.get("ok"), "error": r.get("error"),
                     "task_id": r.get("task_id"), "sha256": r.get("sha256"),
                     "width": r.get("width"), "height": r.get("height"),
                     "bytes": r.get("bytes"), "path": r.get("path")})
        print("  {:<16} {} {}".format(
            vid, "OK " if r.get("ok") else "FAIL",
            "{}x{} {:,}B".format(r["width"], r["height"], r["bytes"])
            if r.get("ok") else str(r.get("error"))[:70]))
    ok = [x for x in rows if x["ok"]]
    art = {"schema": "p55-3-blackboard-samples-v1",
           "base_suffix": bb["base_suffix"],
           "base_suffix_sha256": __import__("hashlib").sha256(
               bb["base_suffix"].encode("utf-8")).hexdigest(),
           "variants": rows, "ok_count": len(ok), "total": len(rows),
           "budget_cny_cap": bb["budget_cny_cap"],
           "note": "样片交项目所有者选定**基底**（同一构图 × 三种笔迹密度/明度）"}
    (L / "p55_3_bb_samples.json").write_text(
        json.dumps(art, ensure_ascii=False, indent=1), encoding="utf-8")
    print()
    print("样片 {}/{} 成功".format(len(ok), len(rows)))
    print("-> output/phase55_bb/samples/ 与 docs/regression_2x/logs/p55_3_bb_samples.json")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
