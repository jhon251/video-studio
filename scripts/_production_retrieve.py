"""第一次真实生产：证据检索（研究侧 8E 链；非生产入口，非测试数据）。

- 选题（真实生产输入，用户提供）：
  「刀剑神域的游戏世界现实中要什么时候才能开发出来？」
- 用 retrieve_with_fallback 联网检索真实来源，构建 production input.json。
- 本脚本只做证据采集 + 生成 input.json；随后用 bin/produce_2x.py 跑生产。
"""
import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from video_studio.core.env import load_env  # noqa: E402
load_env(ROOT / ".env")
from video_studio.tools.evidence_retrieval import retrieve_with_fallback  # noqa: E402
from video_studio.tools.evidence_retrieval import source_quality  # noqa: E402

CLAIM = "刀剑神域的游戏世界现实中要什么时候才能开发出来？"
QUERY = "刀剑神域 完全潜行 脑机接口 现实 什么时候实现"

t0 = time.perf_counter()
res = retrieve_with_fallback(QUERY, max_usable=6, per_provider=4)
dt = time.perf_counter() - t0

usable = res["usable"]
print(f"检索耗时 {dt:.1f}s | provider 链 {res['chain']} | 失败分布 {res['failures']}")
print(f"可用证据 {len(usable)} 条:")
for e in usable:
    sq = source_quality(e["url"], e["title"], e["body"])
    print(f"  [{sq['tier']:16s}] {e['title'][:40]} | {e['url'][:70]}")
    print(f"        正文 {e['body'][:80].replace(chr(10),' ')}")

# 组装 production input.json（claim 原文保留，evidence 用检索正文）
evidence = [{"url": e["url"], "title": e["title"], "snippet": e["snippet"], "body": e["body"]}
            for e in usable]
payload = {
    "video": {"title": "刀剑神域的游戏世界现实中要什么时候才能开发出来",
              "claims": [{"claim_text": CLAIM, "evidence": evidence}]},
    "style": "casual",
    "platforms": ["bilibili", "youtube", "shipinhao", "gongzhonghao"],
}
OUT = ROOT / "output" / "production_001"
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "input.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
(OUT / "retrieval.json").write_text(json.dumps({
    "claim": CLAIM, "query": QUERY, "elapsed_s": round(dt, 1),
    "usable_count": len(usable), "failures": res["failures"], "evidence": evidence,
}, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\ninput.json 已写入 {OUT/'input.json'}（{len(evidence)} 条证据）")
