# -*- coding: utf-8 -*-
"""Phase 8 只读诊断（修正版）：DB 字节变化的性质 —— 是否在 Phase 8 窗口内产生过新记录。"""
import json
import pathlib
import sqlite3
import sys
import time

R = pathlib.Path(r"C:\mp4agent\video-studio")
DB = R / "projects" / "video_studio.db"
sys.stdout.reconfigure(encoding="utf-8")
con = sqlite3.connect("file:" + DB.as_posix() + "?mode=ro", uri=True)
con.row_factory = sqlite3.Row
con.execute("PRAGMA query_only=ON")
print("DB mtime:", time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(DB.stat().st_mtime)),
      "| now:", time.strftime("%Y-%m-%d %H:%M:%S"))
for t in ("events", "changelog", "tasks", "artifacts", "decisions"):
    cols = [r[1] for r in con.execute("PRAGMA table_info({})".format(t))]
    tcols = [c for c in cols if any(k in c.lower() for k in ("time", "at", "ts", "date"))]
    n = con.execute("select count(*) from '{}'".format(t)).fetchone()[0]
    print("\n== {} | 行数 {} | 时间列 {}".format(t, n, tcols))
    for c in tcols:
        try:
            mx = con.execute("select max({0}) from {1}".format(c, t)).fetchone()[0]
            mn = con.execute("select min({0}) from {1}".format(c, t)).fetchone()[0]
            mx_s = (time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(float(mx)))
                    if isinstance(mx, (int, float)) and mx and mx > 1e9 else mx)
            mn_s = (time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(float(mn)))
                    if isinstance(mn, (int, float)) and mn and mn > 1e9 else mn)
            print("   {}: min={} max={}".format(c, mn_s, mx_s))
        except sqlite3.Error as exc:
            print("   {}: 读取失败 {}".format(c, exc))
# Phase 8 窗口（本会话）：以 DB mtime 前 24h 为界，统计是否有该窗口内创建的行
cut = DB.stat().st_mtime - 86400
for t, c in (("events", "ts"), ("changelog", "at"), ("tasks", "created_at"),
             ("artifacts", "created_at")):
    cols = [r[1] for r in con.execute("PRAGMA table_info({})".format(t))]
    if c not in cols:
        print("\n{}: 无列 {}（跳过窗口统计）".format(t, c))
        continue
    try:
        n = con.execute("select count(*) from '{}' where {} >= ?".format(t, c),
                        (cut,)).fetchone()[0]
        print("\n{}: 窗口内(近 24h)新增 {} 行".format(t, n))
    except sqlite3.Error as exc:
        print("\n{}: 统计失败 {}".format(t, exc))
con.close()
