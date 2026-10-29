"""验证查询阶梯：用真实项目 p_f4b466a4a024 的原始查询文本走 provider.search（只搜索、不下载）。

产出 logs/phase3a_query_ladder_live.txt：每次尝试的 query/hits/images + 候选标题与许可证类别。
"""
import json
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
from video_studio.agents.retrieval.agent import kw_tokens            # noqa: E402
from video_studio.tools.material_provider import MaterialQuery       # noqa: E402
from video_studio.tools.provider_wikimedia import WikimediaCommonsProvider  # noqa: E402

PID = sys.argv[1] if len(sys.argv) > 1 else "p_f4b466a4a024"
OUT = ROOT / "docs" / "regression_2x" / "logs" / "phase3a_query_ladder_live.txt"

con = sqlite3.connect(str(ROOT / "projects" / "video_studio.db"))
con.row_factory = sqlite3.Row
row = con.execute("select path from artifacts where project_id=? and type='retrieval_candidates' "
                  "order by created_at desc limit 1", (PID,)).fetchone()
con.close()
if row is None:
    print("no retrieval artifact for", PID)
    sys.exit(2)
payload = json.loads(Path(row["path"]).read_text(encoding="utf-8"))
text = str(payload.get("query") or "")
print("query chars =", len(text))

policy = {"provider": "wikimedia_commons", "search_limit": 8, "min_interval_s": 1.0,
          "max_requests": 12, "timeout_s": 25, "license_required": True,
          "query_term_limit": 4, "query_max_searches": 3, "auth": {"mode": "none"}}
p = WikimediaCommonsProvider(policy)
queries, meta = p.shape_queries(text, 4, 3)
print("mode =", meta["mode"], "| clusters =", meta["clusters"][:6])
print("queries =", queries)
cands = p.search(MaterialQuery(text=text[:500], keywords=kw_tokens(text)), None)

lines = ["实时查询阶梯验证（项目 {}）".format(PID),
         "原始查询长度: {} 字符".format(len(text)),
         "整形模式: {} | 词簇: {}".format(meta["mode"], json.dumps(meta["clusters"][:6],
                                                                  ensure_ascii=False)),
         "查询序列: {}".format(json.dumps(queries, ensure_ascii=False)),
         "逐次尝试: " + json.dumps(p.stats["query_shaping"]["attempts"], ensure_ascii=False),
         "候选数: {}".format(len(cands)), "请求数: {}".format(p.stats["requests"]),
         "许可证类别分布: {}".format(json.dumps(p.stats["license_classes"], ensure_ascii=False)),
         ""]
for c in cands:
    lines.append("  - [{}] {} | {} | {}x{} | score={}".format(
        c.license_class, c.name[:70], c.license, c.width, c.height, c.match_score))
print("\n".join(lines[3:]))
OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\nwritten", OUT)
