"""V2.1 Stage 5 dev 集收集（第三轮 Tavily 独立检索；标注先行，随后才用于 prompt/规则开发）。

排除：50 回归集 / 121 盲测集 / 26 压力集 / 第一轮入库 Evidence 的全部 URL。
不修改任何生产代码与冻结集。
"""
import json
import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FTimeout
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from video_studio.core.env import load_env  # noqa: E402
load_env(ROOT / ".env")
from video_studio.tools.search_provider import TavilySearchProvider  # noqa: E402

PID = "p_f2215875dd49"
db = sqlite3.connect(str(ROOT / "projects" / "video_studio.db"))
db.row_factory = sqlite3.Row
claims = [dict(c) for c in db.execute(
    "SELECT claim_id, text FROM claims WHERE project_id=? AND type='FACT' ORDER BY claim_id", (PID,))]
report = json.loads(sorted((ROOT / "projects" / "_drafts").glob(
    "yongsheng-tavily-r1_*在线核查报告.json"))[-1].read_text(encoding="utf-8"))
rows = {r["claim_id"]: r for r in report["rows"]}

exclude = set()
for s in json.loads((ROOT / "tests" / "data" / "evidence_regression_r1.json").read_text(encoding="utf-8"))["samples"]:
    exclude.add(s["evidence"].get("url", ""))
for rec in json.loads((ROOT / "projects" / "_drafts" / "r1_blind_collection.json").read_text(encoding="utf-8"))["claims"]:
    for r in rec["results"]:
        exclude.add(r["url"])
for s in json.loads((ROOT / "tests" / "data" / "contradicts_stress.json").read_text(encoding="utf-8"))["samples"]:
    exclude.add(s["evidence"].get("url", ""))
for r in db.execute("SELECT url FROM evidence WHERE project_id=?", (PID,)):
    if r["url"]:
        exclude.add(r["url"])

tav = TavilySearchProvider()
sess = requests.Session()
sess.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
})


def fetch(url):
    try:
        resp = sess.get(url, timeout=(5, 8), allow_redirects=True)
        text = ""
        try:
            for chunk in resp.iter_content(8192):
                text += chunk.decode(resp.encoding or "utf-8", errors="ignore")
                if len(text) > 4000:
                    break
        finally:
            resp.close()
        return {"status": resp.status_code, "text": text[:4000]}
    except Exception as e:
        return {"status": "ERR:" + type(e).__name__, "text": ""}


out = []
path = ROOT / "projects" / "_drafts" / "s5_dev_collection.json"
path.write_text(json.dumps({"provenance": "Tavily 第三轮独立检索（Stage 5 dev 集；与第一轮同查询）",
                            "claims": []}, ensure_ascii=False, indent=2), encoding="utf-8")
seen = set()
for c in claims:
    q = rows.get(c["claim_id"], {}).get("query") or c["text"]
    rec = {"claim_id": c["claim_id"], "claim_text": c["text"], "query": q, "results": []}
    try:
        results = tav.search(q, max_results=3)
    except Exception as e:
        rec["search_error"] = type(e).__name__
    else:
        picked = [r for r in results if r.url not in exclude and r.url not in seen][:3]
        seen |= {r.url for r in picked}
        pages = {}
        with ThreadPoolExecutor(max_workers=3) as ex:
            futs = {ex.submit(fetch, r.url): r for r in picked}
            for fut in futs:
                try:
                    pages[futs[fut].url] = fut.result(timeout=20)
                except FTimeout:
                    pages[futs[fut].url] = {"status": "ERR:WholeTimeout", "text": ""}
                except Exception as e:
                    pages[futs[fut].url] = {"status": "ERR:" + type(e).__name__, "text": ""}
        for r in picked:
            rec["results"].append({"url": r.url, "title": r.title or "",
                                   "snippet": (r.snippet or "")[:300], "page": pages[r.url]})
    out.append(rec)
    path.write_text(json.dumps({"provenance": "Tavily 第三轮独立检索（Stage 5 dev 集；与第一轮同查询）",
                                "claims": out}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{c['claim_id']} -> {len(rec['results'])}", flush=True)
    if len(out) >= 45:
        break
print("written:", path, flush=True)
