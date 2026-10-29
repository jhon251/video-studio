# -*- coding: utf-8 -*-
"""Phase 50 / P50-1：**重生成含文字伪影的三张**（P01_1 / P07_3 / P09_5，≤ ¥2）。

监理帧检结论：10 张生成插图风格统一 ✔；但 **P01_1（开场 hook，乱码文字墙）必须重生成**，
**P07_3（乱码标注）/ P09_5（伪公式）一并重生成**；其余 7 张接受为纹理。

做法：提示词 = 该景 `visual_hint` + **冻结的 `no_text` 风格变体后缀**；
负向提示词用**强化版**（显式列 text/letters/numbers/formula/gibberish…）。
每图**最多生成 2 次**；仍含文字伪影 ⇒ **换用抽象段安全集素材并登记**（不硬造）。

产出：覆盖 `output/phase47_gen/batch/<scene>.png`（保留旧图为 `.v1.png` 以便对照）
+ `logs/p50_1_regen.json`
"""
from __future__ import annotations

import json
import pathlib
import shutil
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core.env import load_env                                      # noqa: E402
from video_studio.tools import provider_gen as PG                               # noqa: E402

OUT = R / "output" / "phase47_gen" / "batch"
L = R / "docs" / "regression_2x" / "logs"
TARGETS = ("P01_1", "P07_3", "P09_5")
MAX_ATTEMPTS = 2


def main() -> int:
    load_env(R / ".env")
    cfg = json.loads((R / "config/gen_style.json").read_text(encoding="utf-8"))["gen_style"]
    suffix = cfg["frozen_style_variants"]["no_text"]["suffix"]
    neg = cfg["negative_prompt_strong"]
    sc = json.loads((R / "output/phase36_script_sandbox/script_p36_v65_36seg.json")
                    .read_text(encoding="utf-8"))
    by_id = {s["scene_id"]: s for s in sc["segments"]}
    gb = json.loads((L / "p47_2_gen_batch.json").read_text(encoding="utf-8"))
    by_scene = {it["scene_id"]: it for it in (gb.get("items") or [])}
    rows = []
    print("重生成目标：{}".format(", ".join(TARGETS)))
    for sid in TARGETS:
        s = by_id[sid]
        hint = (s.get("visual_hint") or s.get("description")
                or (s.get("narration") or "")[:60]).strip()
        prompt = "{}。{}".format(hint, suffix)
        dest = OUT / "{}.png".format(sid)
        # 保留旧图对照
        if dest.is_file():
            shutil.copy2(dest, OUT / "{}.v1.png".format(sid))
        tries, ok, last = 0, None, None
        while tries < MAX_ATTEMPTS:
            tries += 1
            r = PG.generate(prompt, dest, model=cfg["model"], size=cfg["size"],
                            negative=neg)
            if r.get("ok"):
                ok = r
                break
            last = r.get("error")
        row = {"scene_id": sid, "visual_hint": hint, "prompt": prompt,
               "attempts": tries, "ok": bool(ok),
               "error": (None if ok else last),
               "task_id": (ok or {}).get("task_id"),
               "sha256": (ok or {}).get("sha256"),
               "width": (ok or {}).get("width"),
               "height": (ok or {}).get("height"),
               "bytes": (ok or {}).get("bytes"),
               "old_sha256": (by_scene.get(sid) or {}).get("sha256"),
               "style_variant": "no_text",
               "negative_prompt": neg,
               "provider": "dashscope/wanx"}
        rows.append(row)
        print("  {:<6} {} 尝试 {} 次 {}".format(
            sid, "OK  " if ok else "FAIL", tries,
            "sha={}".format(str(row["sha256"])[:12]) if ok else str(last)[:70]))
    okn = sum(1 for x in rows if x["ok"])
    art = {"schema": "p50-1-regen-v1",
           "targets": list(TARGETS), "max_attempts": MAX_ATTEMPTS,
           "regenerated": okn, "total": len(rows),
           "style_variant": "no_text",
           "style_variant_sha256": cfg["frozen_style_variants"]["no_text"]["sha256"],
           "negative_prompt_strong": neg,
           "budget_cny_cap": 2.0,
           "items": rows,
           "fallback_policy": "仍含文字伪影 ⇒ 换用抽象段安全集素材并登记（不硬造）"}
    (L / "p50_1_regen.json").write_text(
        json.dumps(art, ensure_ascii=False, indent=1), encoding="utf-8")
    print()
    print("重生成 {}/{} 成功".format(okn, len(rows)))
    print("-> output/phase47_gen/batch/*.png（旧图存为 *.v1.png）")
    print("-> docs/regression_2x/logs/p50_1_regen.json")
    return 0 if okn == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
