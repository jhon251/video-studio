"""Probe: which mechanical query reduction yields real Commons hits? (ASCII report)"""
import json
import sys
import urllib.request
from pathlib import Path
from urllib.parse import quote_plus

ROOT = Path(r"C:\mp4agent\video-studio")
UA = "video-studio-material/1.0 (local pipeline)"
OUT = ROOT / "docs" / "regression_2x" / "logs" / "query_shaping_probe.txt"

NARR = ("virtual reality headset device form factor and how it is worn. "
        "virtual reality headset hardware closeup")
FULL_PIPELINE = "{} {}".format(NARR, NARR)          # retrieval 会把依赖文本拼接
ZH = ("虚拟现实 头显 设备 外观 与 佩戴 形态。 虚拟现实 头显 设备 形态")


def terms(text, n):
    seen, out = set(), []
    for w in text.replace("。", " ").replace(".", " ").split():
        w = w.strip()
        if not w or w.lower() in seen:
            continue
        seen.add(w.lower())
        out.append(w)
        if len(out) >= n:
            break
    return " ".join(out)


CASES = {
    "full_pipeline_query": FULL_PIPELINE,
    "first_8_terms": terms(FULL_PIPELINE, 8),
    "first_5_terms": terms(FULL_PIPELINE, 5),
    "first_3_terms": terms(FULL_PIPELINE, 3),
    "zh_query": ZH,
    "zh_first_3": terms(ZH, 3),
}
lines = []
for name, q in CASES.items():
    url = ("https://commons.wikimedia.org/w/api.php?action=query&format=json&formatversion=2"
           "&generator=search&gsrnamespace=6&gsrlimit=5&prop=imageinfo&iiprop=url"
           "&gsrsearch=" + quote_plus(q))
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20) as r:      # noqa: S310
            d = json.loads(r.read().decode("utf-8"))
        pages = ((d.get("query") or {}).get("pages") or [])
        rec = {"case": name, "query": q[:80], "items": len(pages),
               "first_title": (pages[0].get("title") if pages else None)}
    except Exception as exc:                                     # noqa: BLE001
        rec = {"case": name, "query": q[:80], "error": "{}: {}".format(type(exc).__name__,
                                                                      str(exc)[:80])}
    lines.append(json.dumps(rec, ensure_ascii=False))
    print(lines[-1], flush=True)
OUT.write_text("\n".join(lines), encoding="utf-8")
print("\nwritten", OUT)
