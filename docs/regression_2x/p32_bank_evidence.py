# -*- coding: utf-8 -*-
"""P32-4：核查生产逐景核验的 bank v2 证据（corr_bank 是否真的产生、景级判定）。只读。"""
from __future__ import annotations

import json
import pathlib
import sqlite3
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
PID = sys.argv[1] if len(sys.argv) > 1 else "p_e0cda0a7d541"
sys.stdout.reconfigure(encoding="utf-8")
con = sqlite3.connect("file:" + (R / "projects" / "video_studio.db").as_posix()
                      + "?mode=ro", uri=True)
con.row_factory = sqlite3.Row
for r in con.execute("select path from artifacts where project_id=?", (PID,)):
    p = pathlib.Path(r["path"])
    if not p.is_file():
        continue
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:                                                       # noqa: BLE001
        continue
    if not isinstance(d, dict):
        continue
    mv = d.get("material_verification")
    if not mv:
        continue
    se = d.get("scene_evidence") or []
    print("artifact     :", p.name)
    print("bank_derived :", mv.get("bank_derived"), "| bank_version:",
          mv.get("bank_version"))
    print("bank_source  :", str(mv.get("bank_config_source"))[-70:])
    print("checked      :", len(mv.get("checked_scenes") or []),
          "| failed:", len(mv.get("failed_scenes") or []),
          "| placeholder:", len(mv.get("placeholder_verified") or []))
    wb = [x for x in se if x.get("corr_bank") is not None]
    errs = [x for x in se if x.get("bank_error")]
    print("含 corr_bank : {}/{} | bank_error: {}".format(len(wb), len(se), len(errs)))
    if errs:
        print("  首个错误:", errs[0].get("scene_id"), errs[0].get("bank_error"))
    print()
    print("{:<8} {:>8} {:>9} {:>9} {:>6} {}".format(
        "scene", "corr", "corr_bank", "best", "match", "window"))
    for x in se:
        bw = x.get("bank_window") or {}
        cb = x.get("corr_bank")
        print("{:<8} {:>8} {:>9} {:>9} {:>6} {}".format(
            str(x.get("scene_id")), str(x.get("corr")),
            (str(round(cb, 4)) if cb is not None else "-"),
            str(x.get("corr_best")), str(x.get("match")),
            ("scale {} x0 {} y0 {}".format(bw.get("scale"), bw.get("x0"), bw.get("y0"))
             if bw else "")))
    break
