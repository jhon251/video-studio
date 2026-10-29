# -*- coding: utf-8 -*-
"""P32-2 必答项：P31 渲染中仲裁层是否被调用、判定如何。只读。"""
from __future__ import annotations

import json
import pathlib
import sqlite3
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")


def main() -> int:
    con = sqlite3.connect("file:" + (R / "projects" / "video_studio.db").as_posix()
                          + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    print("=== 最近 RENDER_ARBITRATION / TASK_BLOCKED 事件 ===")
    for r in con.execute("select project_id, type, payload, ts from events "
                         "where type in ('RENDER_ARBITRATION','TASK_BLOCKED') "
                         "order by ts desc limit 8"):
        print("  {} | {} | {}".format(r["project_id"], r["type"],
                                      str(r["payload"])[:300]))
    print()
    print("=== P31 沙箱事件全览 ===")
    for r in con.execute("select type, count(*) n from events where project_id=? "
                         "group by type", ("p_aafdd21cbb9d",)):
        print("  {:<26} {}".format(r["type"], r["n"]))
    print()
    # 仲裁配置解析
    from video_studio.core import render_arbitration as ARB
    cfg = json.loads((R / "config" / "config.json").read_text(encoding="utf-8"))
    try:
        resolved = ARB.resolve_config(cfg, root=R)
        print("=== 仲裁配置解析 ===")
        print("  ", json.dumps(resolved, ensure_ascii=False, default=str)[:500])
    except Exception as exc:                                                # noqa: BLE001
        print("  resolve_config 不可用:", type(exc).__name__, exc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
