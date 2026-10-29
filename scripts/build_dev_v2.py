"""Stage 6 dev 集重构（类别配额 + 标注先行；Evidence 全部为真实文本）。

- 保留原 dev 61 条及其已冻结标签；新增派生命题配对（claim_source=derived）：
  DIRECT ×6、CONTRADICTS ×8、CONTEXT_ONLY ×2 —— Evidence 取自第三轮 dev 集合真实页面
  （与冻结 197 完全去重，URL 已排除）。
- truth label 在本脚本先行落盘，之后才允许用于 few-shot/开发。
"""
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
col = json.loads((ROOT / "projects" / "_drafts" / "s5_dev_collection.json").read_text(encoding="utf-8"))
old_labels = json.loads((ROOT / "projects" / "_drafts" / "s5_dev_labels.json").read_text(encoding="utf-8"))["labels"]

pages = {}
for rec in col["claims"]:
    for r in rec["results"]:
        pages[r["url"]] = {"title": r["title"], "snippet": r["snippet"],
                           "text": r["page"].get("text", ""), "url": r["url"]}


def page(url_part):
    for u, p in pages.items():
        if url_part in u:
            return p
    raise KeyError(url_part)


samples = []
i = 0
for rec in col["claims"]:
    for r in rec["results"]:
        i += 1
        did = f"D{i:03d}"
        samples.append({"id": did, "claim_text": rec["claim_text"], "claim_source": "original",
                        "truth": old_labels[did],
                        "evidence": {"title": r["title"], "snippet": r["snippet"],
                                     "text": r["page"].get("text", ""), "url": r["url"]}})

NEW = [
    # ---- DIRECT ×6（派生可验证命题，Evidence 完整背书）----
    ("DV-01", "DIRECT_SUPPORT", "AI芯片功耗突破1000瓦时若散热不佳，算力将无法释放",
     "youtube.com/watch?v=c-HZgiYCD84",
     "证据明确陈述功耗突破1000瓦、不解决散热算力无法释放"),
    ("DV-02", "DIRECT_SUPPORT",
     "2024年10月，成年雌果蝇完整大脑神经图谱系列研究发表于《自然》期刊",
     "micro-point.tw/2025/06/27/drosophila-connectome",
     "证据明确：2024年10月、Nature、完整大脑图谱、近14万神经元"),
    ("DV-03", "DIRECT_SUPPORT",
     "构建由人类细胞驱动的生物电脑包括三个步骤：皮肤细胞转化为干细胞、培养为神经元团块类器官、连接至电极",
     "bbc.com/zhongwen/articles/cdx2dp566p2o",
     "证据三步逐一对应（FinalSpark 图解）"),
    ("DV-04", "DIRECT_SUPPORT",
     "杭州互联网法院审理认为虚拟数字人不是自然人、不具有作者身份",
     "m.mp.oeeee.com/a/BAAFRD000020240425942468.html",
     "证据原文即该裁判观点"),
    ("DV-05", "DIRECT_SUPPORT",
     "1775年，苏格兰哲学家托马斯·里德提出了与传送机类似的思想实验问题",
     "m.guokr.com/article/442339",
     "证据明确：1775年、Thomas Reid、类似问题"),
    ("DV-06", "DIRECT_SUPPORT",
     "果蝇大脑的三维重建依靠AI自动追踪与人工校对合力完成",
     "sina.cn/news/detail/5275008776800200.html",
     "证据明确：AI自动追踪+人工校对修正"),
    # ---- CONTRADICTS ×8（派生命题被真实证据否定）----
    ("DC-01", "CONTRADICTS", "AI芯片的散热问题已经彻底解决",
     "youtube.com/watch?v=c-HZgiYCD84",
     "证据称功耗破千瓦后不解决散热算力无法释放——直接否定'已经解决'"),
    ("DC-02", "CONTRADICTS", "成年果蝇大脑连接组至今尚未完成绘制",
     "micro-point.tw/2025/06/27/drosophila-connectome",
     "证据称2024年10月已发表完整大脑神经图谱系列研究"),
    ("DC-03", "CONTRADICTS", "从未有团队把果蝇大脑复制到电脑中运行",
     "sina.cn/news/detail/5275008776800200.html",
     "证据称Eon Systems把果蝇大脑完整复制到电脑并让电路图在虚拟身体里运行"),
    ("DC-04", "CONTRADICTS", "虚拟数字人产业权属完全清晰、取证容易",
     "m.mp.oeeee.com/a/BAAFRD000020240425942468.html",
     "证据标题即'产业权属不清取证难'"),
    ("DC-05", "CONTRADICTS", "人类皮肤细胞无法转化为干细胞用于构建类器官",
     "bbc.com/zhongwen/articles/cdx2dp566p2o",
     "证据第一步即'将人类皮肤细胞转化为干细胞'"),
    ("DC-06", "CONTRADICTS", "果蝇大脑的复制在技术上无法实现",
     "youtube.com/watch?v=NqhyoElInDo",
     "证据称果蠅已在虛擬世界中持續運作大腦（人类首次上传生命）"),
    ("DC-07", "CONTRADICTS", "法律对往生者的权利与身后事务没有任何规定",
     "plainlaw.me/article/2022-6-27-2",
     "证据称民法第6条及刑法对往生者名誉权均有规定（不因死亡而差别）"),
    ("DC-08", "CONTRADICTS", "人类大脑的神经元数量不足一百亿",
     "pmc.ncbi.nlm.nih.gov/articles/PMC9927433",
     "证据称人脑由近千亿个神经元及其突触连接形成"),
    # ---- CONTEXT_ONLY ×2 ----
    ("DCX-01", "CONTEXT_ONLY", "人脑与计算机在能效上可以直接比较",
     "pmc.ncbi.nlm.nih.gov/articles/PMC9927433",
     "证据讨论类脑脉冲神经网络与芯片，仅词面相邻"),
    ("DCX-02", "CONTEXT_ONLY", "科学家已经开始绘制生物大脑的完整图谱",
     "news.sciencenet.cn/htmlnews/2025/7/547725.shtm",
     "证据为小鼠全身成像（相邻技术，未讨论全脑图谱命题）"),
]

for did, truth, claim, url_part, why in NEW:
    p = page(url_part)
    samples.append({"id": did, "claim_text": claim, "claim_source": "derived", "truth": truth,
                    "evidence": p, "rationale": why})

labels = {s["id"]: s["truth"] for s in samples}
out = {"_meta": {"name": "s5_dev_v2_labels",
                 "note": "Stage 6 dev 集（类别配额重构：DIRECT 6、PARTIAL 20、CONTEXT 6、"
                         "IRRELEVANT 36、CONTRADICTS 8，共 76；全部真实文本；与冻结 197 去重；"
                         "标注先行冻结，之后才用于 few-shot/开发）"},
       "labels": labels}
(ROOT / "projects" / "_drafts" / "s5_dev_v2_collection.json").write_text(
    json.dumps({"samples": samples}, ensure_ascii=False, indent=2), encoding="utf-8")
(ROOT / "projects" / "_drafts" / "s5_dev_v2_labels.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print("written. total:", len(samples), "| distribution:", dict(Counter(labels.values())))
