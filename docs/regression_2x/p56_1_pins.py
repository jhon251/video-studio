# -*- coding: utf-8 -*-
"""Phase 56 / P56-2：**从 F9 抽取钉定分配表**（F10.1 单变量版输入）。

把 F9 渲染的 `material_timeline` 逐景已选素材导出为
`{scene_id: sha256}`，作为 F10.1 的**钉定绑定**输入 ——
F10.1 与 F9 的**唯一差异 = 字幕层**。
"""
from __future__ import annotations

import json
import pathlib
import sqlite3
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")


def main() -> int:
    f9 = [json.loads(x) for x in (L / "p53_2_delivery_candidate.jsonl")
          .read_text(encoding="utf-8").splitlines() if x.strip()][-1]
    pid = f9["sandbox_project_id"]
    con = sqlite3.connect("file:" + (R / "projects/video_studio.db").as_posix()
                          + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    p = json.loads(con.execute("select payload from events where project_id=? and "
                               "type='MATERIAL_TIMELINE'", (pid,)).fetchone()["payload"])
    con.close()
    pins, rows = {}, []
    for d in p["decisions"]:
        a = d.get("selected_asset") or {}
        sh = str(a.get("sha256") or "")
        if not sh:
            continue
        pins[d["scene_id"]] = sh
        rows.append({"scene_id": d["scene_id"], "sha256": sh,
                     "asset_id": a.get("asset_id"),
                     "name": str(a.get("name") or "")[:60]})
    # 指纹（与 P56-1 同算法，供确定性断言比对）
    sys.path.insert(0, str(R / "src"))
    from video_studio.core.allocation import assignment_fingerprint
    fp = assignment_fingerprint({k: v[:12] for k, v in pins.items()})
    art = {"schema": "p56-2-f9-pinned-assignment-v1",
           "source_candidate": "F9", "source_sandbox": pid,
           "scenes": len(pins), "pins": pins, "rows": rows,
           "fingerprint_sha12": fp,
           "note": ("F9 逐景已选素材 ⇒ F10.1 的**钉定绑定**输入；"
                    "F10.1 与 F9 的唯一差异应为**字幕层**")}
    out = L / "p56_2_f9_pins.json"
    out.write_text(json.dumps(art, ensure_ascii=False, indent=1), encoding="utf-8")
    print("F9 钉定分配表：{} 景 | 指纹 {}".format(len(pins), fp[:24]))
    print("样例：", json.dumps({k: v[:12] for k, v in list(pins.items())[:4]},
                               ensure_ascii=False))
    print("-> " + str(out.relative_to(R)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
