"""测量：Commons 上哪些机械查询变体能命中（为查询整形规则提供实测依据）。

只做只读搜索（ns=6 文件命名空间），逐条记录 hits，条目间礼貌间隔。
"""
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
OUT = ROOT / "docs" / "regression_2x" / "logs" / "phase3a_query_ladder.txt"
UA = "video-studio-material/1.0 (local pipeline)"
API = "https://commons.wikimedia.org/w/api.php"

CASES = [
    ("4_terms_union", "Quest PSVR2 PICO Valve"),
    ("3_terms", "Quest PSVR2 PICO"),
    ("2_terms", "Quest PSVR2"),
    ("1_term_Quest", "Quest"),
    ("1_term_PSVR2", "PSVR2"),
    ("1_term_PICO", "PICO"),
    ("2_terms_brand", "Meta Quest"),
    ("3_terms_brand", "Meta Quest 3"),
    ("generic_headset", "virtual reality headset"),
    ("generic_vr", "VR headset"),
    ("generic_worn", "virtual reality headset worn"),
]


def search(q: str, limit: int = 8) -> dict:
    params = {"action": "query", "format": "json", "formatversion": "2",
              "generator": "search", "gsrnamespace": "6", "gsrlimit": str(limit),
              "gsrsearch": q, "prop": "imageinfo", "iiprop": "url|mime"}
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=25) as r:            # noqa: S310
        d = json.loads(r.read().decode("utf-8"))
    pages = ((d.get("query") or {}).get("pages")) or []
    return {"hits": len(pages),
            "first": (pages[0].get("title") if pages else None),
            "mimes": sorted({(p.get("imageinfo") or [{}])[0].get("mime") for p in pages
                             if p.get("imageinfo")})}


lines = []
for name, q in CASES:
    try:
        rec = {"case": name, "query": q, **search(q)}
    except Exception as exc:                                       # noqa: BLE001
        rec = {"case": name, "query": q, "error": "{}: {}".format(type(exc).__name__,
                                                                  str(exc)[:70])}
    lines.append(json.dumps(rec, ensure_ascii=False))
    print(lines[-1], flush=True)
    time.sleep(1.2)
OUT.write_text("\n".join(lines), encoding="utf-8")
print("\nwritten", OUT)
