# -*- coding: utf-8 -*-
"""Phase 10 §1.3 只读探针：实测 bilibili popular 接口（单次请求，记录字段与编码）。"""
import json
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
URL = "https://api.bilibili.com/x/web-interface/popular?ps=50"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0 Safari/537.36")
req = urllib.request.Request(URL, headers={"User-Agent": UA, "Accept": "application/json"})
with urllib.request.urlopen(req, timeout=15) as resp:                  # noqa: S310 —— 固定 https
    raw = resp.read()
    print("HTTP", resp.status, "| Content-Type:", resp.headers.get("Content-Type"),
          "| bytes:", len(raw))
j = json.loads(raw.decode("utf-8"))
print("顶层 keys:", sorted(j.keys()), "| code:", j.get("code"))
data = j.get("data")
print("data 类型:", type(data).__name__)
if isinstance(data, dict):
    print("data keys:", sorted(data.keys()))
    lst = data.get("list")
    print("data.list 类型:", type(lst).__name__, "| 长度:",
          len(lst) if isinstance(lst, list) else None)
    data = lst if isinstance(lst, list) else []
else:
    data = data or []
print("条目数:", len(data))
if data:
    e = data[0]
    print("条目 keys:", sorted(e.keys()))
    print("样例:", json.dumps({k: e.get(k) for k in ("title", "tname", "tnamev2", "duration",
                                                     "pubdate", "bvid", "short_link_v2")},
                              ensure_ascii=False)[:220])
    print("stat:", json.dumps(e.get("stat"), ensure_ascii=False))
    print("owner:", json.dumps(e.get("owner"), ensure_ascii=False)[:80])
    print("rcmd_reason:", json.dumps(e.get("rcmd_reason"), ensure_ascii=False)[:160])
    print("tname 集合（前 8）:", sorted({str(x.get("tname")) for x in data})[:8])
    print("中文解码 OK:", any("\u4e00" <= c <= "\u9fff" for c in str(e.get("title"))))
