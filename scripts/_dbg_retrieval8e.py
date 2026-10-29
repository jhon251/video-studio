import sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, "src")
from video_studio.tools.evidence_retrieval import source_quality, retrieval_coverage

# ① 来源可靠性分层
cases = [
    ("https://www.nature.com/articles/foo", "论文"),
    ("https://www.gov.cn/x", "官方"),
    ("https://www.tsinghua.edu.cn/a", "学术"),
    ("https://news.cn/a", "主流媒体"),
    ("https://www.tmtpost.com/a", "专业媒体"),
    ("https://baike.baidu.com/item/x", "百科"),
    ("https://www.sohu.com/a/1", "聚合"),
    ("https://www.reddit.com/r/x", "论坛"),
    ("https://www.unknown-xyz-abc.com/a", "未知"),
]
for url, label in cases:
    q = source_quality(url, "", "这是一段用于测试的正文内容。")
    print(f"{label:8s} {url[:40]:42s} -> tier={q['tier']:16s} level={q['reliability_level']} band={q['band']}")

# ② coverage 统计（离线）
ev = [{"url": "https://news.cn/a", "title": "t", "body": "人脑约有八百六十亿个神经元。", "usable": True,
       "status": "valid", "salvaged": False, "source_quality": source_quality("https://news.cn/a", "t", "x")}]
cov = retrieval_coverage("人脑大约八百六十亿个神经元", ev, {"timeout": 1})
print("\ncoverage:", cov)
print("ALL PASS")
