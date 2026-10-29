"""阶段 2 盲测集收集（第二轮独立检索，工具脚本，非生产代码）。

- 对第一轮 FACT Claim（p_f2215875dd49）按第一轮同一条 query 重新发起 Tavily 独立检索；
- 每个 Claim 至多 3 条结果，抓取原文（硬超时），保存原始 url/title/snippet/正文；
- 排除：(a) 已进入 50 样本回归集的 (claim,url)；(b) 第一轮已入库 Evidence 的 url；
- 不改任何生产代码、不改语义规则、不改《永生》文案与 Claim。
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FTimeout
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from video_studio.core.env import load_env  # noqa: E402
load_env(ROOT / ".env")
from video_studio.tools.search_provider import TavilySearchProvider  # noqa: E402

import sqlite3  # noqa: E402

PID = "p_f2215875dd49"
db = sqlite3.connect(str(ROOT / "projects" / "video_studio.db"))
db.row_factory = sqlite3.Row
claims = [dict(c) for c in db.execute(
    "SELECT claim_id, text FROM claims WHERE project_id=? AND type='FACT' ORDER BY claim_id", (PID,))]
report_file = sorted((ROOT / "projects" / "_drafts").glob("yongsheng-tavily-r1_*在线核查报告.json"))[-1]
report = json.loads(report_file.read_text(encoding="utf-8"))
rows = {r["claim_id"]: r for r in report["rows"]}

# 排除集合：50 样本回归集 url + 第一轮入库 Evidence url
exclude_urls = set()
reg = json.loads((ROOT / "tests" / "data" / "evidence_regression_r1.json").read_text(encoding="utf-8"))
for s in reg["samples"]:
    exclude_urls.add(s["evidence"].get("url", ""))
for r in db.execute("SELECT url FROM evidence WHERE project_id=?", (PID,)):
    if r["url"]:
        exclude_urls.add(r["url"])

tav = TavilySearchProvider()
sess = requests.Session()
sess.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
})


def fetch(url: str) -> dict:
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


def collect(c):
    q = rows.get(c["claim_id"], {}).get("query") or c["text"]
    rec = {"claim_id": c["claim_id"], "claim_text": c["text"], "query": q, "results": []}
    try:
        results = tav.search(q, max_results=3)
    except Exception as e:
        rec["search_error"] = type(e).__name__
        return rec
    picked = []
    for r in results:
        if r.url in exclude_urls:
            continue
        picked.append(r)
        if len(picked) >= 3:
            break
    pages = {}
    with ThreadPoolExecutor(max_workers=3) as ex:
        futs = {ex.submit(fetch, r.url): r for r in picked}
        for fut in futs:
            r = futs[fut]
            try:
                pages[r.url] = fut.result(timeout=20)
            except FTimeout:
                pages[r.url] = {"status": "ERR:WholeTimeout", "text": ""}
            except Exception as e:
                pages[r.url] = {"status": "ERR:" + type(e).__name__, "text": ""}
    for r in picked:
        rec["results"].append({
            "url": r.url, "title": r.title or "", "snippet": (r.snippet or "")[:300],
            "page": pages[r.url],
        })
    return rec


out = []
path = ROOT / "projects" / "_drafts" / "r1_blind_collection.json"
path.write_text(json.dumps({"provenance": "Tavily 第二轮独立检索（与第一轮同查询），用于 V2.1 阶段 2 盲测；"
                                         "未修改任何 Evidence 文本", "excluded_urls_note": "已排除回归集与第一轮入库 url",
                            "claims": []}, ensure_ascii=False, indent=2), encoding="utf-8")
for c in claims:
    rec = collect(c)
    out.append(rec)
    path.write_text(json.dumps({"provenance": "Tavily 第二轮独立检索（与第一轮同查询），用于 V2.1 阶段 2 盲测；"
                                             "未修改任何 Evidence 文本",
                                "excluded_urls_note": "已排除回归集与第一轮入库 url",
                                "claims": out}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{c['claim_id']} -> {len(rec['results'])} candidates", flush=True)
    if len(out) >= 50:
        break
print("written:", path, flush=True)
