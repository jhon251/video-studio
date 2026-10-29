import sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, "src")
from video_studio.tools.evidence_readiness import (readiness, completeness,
                                                    source_quality_profile, balance)

claim = "人脑大约八百六十亿个神经元，突触按百万亿算"
ev_good = [
    {"url": "https://news.cn/a", "title": "人脑神经元", "snippet": "", "body": "人类大脑约有860亿个神经元，突触连接数量达百万亿级。"},
    {"url": "https://www.gov.cn/b", "title": "脑科学", "snippet": "", "body": "人脑包含约860亿神经元与百万亿突触。"},
]
ev_weak = [
    {"url": "https://www.reddit.com/r/x", "title": "帖子", "snippet": "", "body": "随便聊聊，今天天气不错。"},
]
print("readiness(good):")
r = readiness(claim, ev_good)
for k in ("n_evidence", "readiness_score", "grade", "decision_confidence"):
    print("  ", k, "=", r[k])
print("  balance =", r["balance"])
print("  source_quality =", {k: r["source_quality"][k] for k in ("high", "medium", "low", "quality_score")})
print("  completeness =", r["completeness"]["completeness_score"])

print("readiness(weak):")
r2 = readiness(claim, ev_weak)
print("  grade =", r2["grade"], "confidence =", r2["decision_confidence"], "score =", r2["readiness_score"])

# contradiction balance
claim2 = "人脑大约有一千亿个神经元"
ev_contra = [
    {"url": "https://news.cn/c", "title": "", "snippet": "", "body": "人脑约有860亿个神经元。"},
]
print("balance(contra):", balance(claim2, ev_contra))
print("ALL PASS")
