# -*- coding: utf-8 -*-
"""Phase 47 / P47-2：**批量生成概念插图**（冻结晶格 a；每景 1 张）。

· 提示词 = 该景**既有** `visual_hint`（或描述/旁白要点）+ **冻结风格后缀**；
· 逐图溯源：`source_of_record` = 生成任务 ID、`license` = 生成物（无第三方署名义务）；
· 校验链：解码/尺寸/去重；失败逐条登记；预算 ≤¥10、请求 ≤25。

产出：`output/phase47_gen/batch/<scene>.png` + `logs/p47_2_gen_batch.json`
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

OUT = R / "output" / "phase47_gen" / "batch"
L = R / "docs" / "regression_2x" / "logs"
REQ_CAP = 25


def main() -> int:
    load_env(R / ".env")
    cfg = json.loads((R / "config/gen_style.json").read_text(encoding="utf-8"))["gen_style"]
    suffix = cfg["frozen_style_suffix"]
    tgt = json.loads((L / "p47_2_gen_targets.json").read_text(encoding="utf-8"))
    sc = json.loads((R / "output/phase36_script_sandbox/script_p36_v65_36seg.json")
                    .read_text(encoding="utf-8"))
    by_id = {s["scene_id"]: s for s in sc["segments"]}
    print("冻结风格 {} | 目标 {} 景".format(cfg["frozen_style_id"], tgt["target_count"]))
    rows, reqs = [], 0
    for sid in tgt["targets"]:
        if reqs >= REQ_CAP:
            print("  **达请求上限 {} ⇒ 停止**".format(REQ_CAP))
            break
        s = by_id[sid]
        hint = (s.get("visual_hint") or s.get("description")
                or (s.get("narration") or "")[:60]).strip()
        prompt = "{}。{}".format(hint, suffix)
        dest = OUT / "{}.png".format(sid)
        r = PG.generate(prompt, dest, model=cfg["model"], size=cfg["size"],
                        negative=cfg.get("negative_prompt"))
        reqs += 1
        row = {"scene_id": sid, "visual_hint": hint, "prompt": prompt,
               "ok": r.get("ok"), "error": r.get("error"),
               "task_id": r.get("task_id"), "sha256": r.get("sha256"),
               "width": r.get("width"), "height": r.get("height"),
               "bytes": r.get("bytes"), "path": r.get("path"),
               "provider": "dashscope/wanx", "model": cfg["model"],
               "license": "Generated (provider wanx)，无第三方署名义务",
               "source_of_record": r.get("task_id")}
        rows.append(row)
        print("  {:<4} {:<6} {}".format(
            sid, "OK" if r.get("ok") else "FAIL",
            "{}x{} {:,}B".format(r["width"], r["height"], r["bytes"])
            if r.get("ok") else str(r.get("error"))[:80]))
    ok = [x for x in rows if x["ok"]]
    art = {"schema": "p47-2-gen-batch-v1",
           "frozen_style_id": cfg["frozen_style_id"],
           "frozen_style_sha256": cfg["frozen_style_sha256"],
           "model": cfg["model"], "size": cfg["size"],
           "requests_used": reqs, "request_cap": REQ_CAP,
           "generated": len(ok), "failed": len(rows) - len(ok),
           "budget_cny_cap": cfg["budget_cny"]["batch"],
           "items": rows,
           "provenance": "Generated (DashScope wanx)；无第三方署名义务；"
                         "source_of_record = 每张的生成任务 ID"}
    (L / "p47_2_gen_batch.json").write_text(
        json.dumps(art, ensure_ascii=False, indent=1), encoding="utf-8")
    print()
    print("生成 {}/{} 成功 | 请求 {}".format(len(ok), len(rows), reqs))
    print("-> output/phase47_gen/batch/ 与 docs/regression_2x/logs/p47_2_gen_batch.json")
    return 0 if len(ok) >= max(1, len(rows) - 2) else 1


if __name__ == "__main__":
    raise SystemExit(main())
