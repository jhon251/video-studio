# -*- coding: utf-8 -*-
"""P35-1 侦察：定位 `fact_risks`（13 条）与 v3/v4.1 的 claims 事实底账。只读。"""
from __future__ import annotations

import json
import pathlib
import sqlite3
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")


def main() -> int:
    con = sqlite3.connect("file:" + (R / "projects/video_studio.db").as_posix()
                          + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    # 库里搜 fact_risks
    print("=== DB artifacts 含 fact_risks ===")
    hits = 0
    for r in con.execute("select artifact_id, project_id, type, path from artifacts"):
        p = pathlib.Path(r["path"])
        if not p.is_file():
            continue
        try:
            t = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:                                                   # noqa: BLE001
            continue
        if "fact_risks" in t:
            print("  ", r["artifact_id"], r["type"], p.name)
            hits += 1
            if hits >= 8:
                break
    print("  命中", hits)
    print()
    print("=== claims 表 ===")
    try:
        cols = [d[1] for d in con.execute("pragma table_info(claims)")]
        print("  cols:", cols)
        for r in con.execute("select count(*) n from claims"):
            print("  claims 行数:", r["n"])
        for r in con.execute("select * from claims limit 3"):
            d = dict(r)
            print("  样例:", json.dumps({k: str(v)[:70] for k, v in d.items()},
                                        ensure_ascii=False)[:400])
    except Exception as exc:                                                # noqa: BLE001
        print("  claims 读取失败:", exc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
