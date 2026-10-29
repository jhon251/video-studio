"""回归基准样本补采（工具脚本，非生产代码）：
第一轮被拒候选（CONTEXT_ONLY 等）未存全文，按第一轮同一条 Tavily 查询重新检索并抓取原文，
用于证据语义回归集。硬超时 + 保存原文，不触碰任何生产逻辑。"""
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

# 第一轮 rejected 中出现 CONTEXT_ONLY 的 Claim（取前 5 个做补采）
QUERIES = [
    ("c_558", "第三步 转移 本人住进去"),
    ("c_570", "再看一个参照物 OpenWorm 项目 模拟一条只有三百零二个神经元的线虫 跑了十几年 到现在也没人敢说那条虚拟线虫"),
    ("c_593", "这条线上已经有人在卖东西了"),
    ("c_597", "还有一串现实问题排队等着 副本算人吗"),
    ("c_598", "死后上传的法律地位是什么"),
]

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


def collect(claim_id, query):
    results = tav.search(query, max_results=3)
    rec = {"claim_id": claim_id, "query": query,
           "results": [{"title": r.title, "url": r.url,
                        "snippet": r.snippet[:200]} for r in results]}
    pages = []
    with ThreadPoolExecutor(max_workers=3) as ex:
        futs = {ex.submit(fetch, r.url): r for r in results}
        for fut in futs:
            try:
                pages.append({"url": futs[fut].url, **fut.result(timeout=20)})
            except FTimeout:
                pages.append({"url": futs[fut].url, "status": "ERR:WholeTimeout", "text": ""})
            except Exception as e:
                pages.append({"url": futs[fut].url, "status": "ERR:" + type(e).__name__, "text": ""})
    rec["pages"] = pages
    return rec


out = [collect(cid, q) for cid, q in QUERIES]
path = ROOT / "projects" / "_drafts" / "r1_context_collection.json"
path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print("written:", path)
for rec in out:
    print(rec["claim_id"], "->", [(p["status"], p["url"][:70]) for p in rec["pages"]])
