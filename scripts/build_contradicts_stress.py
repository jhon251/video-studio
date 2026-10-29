"""构建 CONTRADICTS 压力测试集（V2.1 阶段 4）。

覆盖场景：真实反驳 / "不是A而是B"对照构式 / 否定词辖域 / Claim 自带否定 /
问句·反问句 / 不同对象的否定 / 时间限定词冲突。
- 全部 Evidence 文本为真实检索文本（盲测集合 r1_blind_collection.json 与
  第一轮数据库 evidence 表），禁止编造；Claim 为原文或派生可验证命题（标记 claim_source）。
- 本集合冻结，仅用于阶段 4 验收评估，**不得用于 prompt 调参**。
"""

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
col = json.loads((ROOT / "projects" / "_drafts" / "r1_blind_collection.json").read_text(encoding="utf-8"))
db = sqlite3.connect(str(ROOT / "projects" / "video_studio.db"))
db.row_factory = sqlite3.Row


def blind(cid: str, url_part: str) -> dict:
    for rec in col["claims"]:
        if rec["claim_id"] != cid:
            continue
        for r in rec["results"]:
            if url_part in r["url"]:
                return {"title": r["title"], "snippet": r["snippet"],
                        "text": r["page"].get("text", ""), "url": r["url"]}
    raise KeyError((cid, url_part))


def db_ev(eid: str) -> dict:
    r = dict(db.execute("SELECT * FROM evidence WHERE evidence_id=?", (eid,)).fetchone())
    return {"title": "", "snippet": "", "text": r["excerpt"] or "", "url": r["url"] or ""}


S = []
S += [  # ---- 真实反驳（Evidence 对可验证命题构成真实否定）----
    dict(id="CT-01", scenario="true_contradict", claim_source="derived",
         claim="人类大脑的神经元数量不足100亿",
         ev=blind("c_568", "huxiu.com/article/4837546"),
         truth="CONTRADICTS", why="虎嗅文明确写'大脑有860亿个神经元'，直接否定命题数字"),
    dict(id="CT-02", scenario="true_contradict", claim_source="derived",
         claim="OpenWorm项目从未建立过302个神经元的线虫模型",
         ev=blind("c_570", "zh.wikipedia.org/wiki/%E5%BC%80%E6%94%BE%E8%A0%95%E8%99%AB"),
         truth="CONTRADICTS", why="维基明确'第一阶段的计划是建立包含302个神经元和95个肌肉细胞的模型'"),
    dict(id="CT-03", scenario="true_contradict", claim_source="derived",
         claim="成年果蝇大脑连接组的神经元数量远少于十万个",
         ev=blind("c_562", "mittrchina.com/news/detail/16047"),
         truth="CONTRADICTS", why="MIT科技评论明确'约139,255个神经元…完整映射'，直接否定"),
    dict(id="CT-04", scenario="true_contradict", claim_source="derived",
         claim="目前还没有任何哺乳动物大脑连接图谱",
         ev=blind("c_563", "news.cn/world/20250410"),
         truth="CONTRADICTS", why="新华网标题即'最大、最详细哺乳动物大脑连接图谱绘成'（2025-04）"),
    dict(id="CT-05", scenario="true_contradict", claim_source="derived",
         claim="记忆一旦存储就不会改变，回忆只是读取",
         ev=blind("c_573", "blog.leowang.net/mt0uj89j-qy"),
         truth="CONTRADICTS", why="文章明确'记忆不是读取，是重写。每一次回忆，都是一次重新编译'"),
    dict(id="CT-06", scenario="true_contradict", claim_source="derived",
         claim="虚拟数字人领域至今没有任何管理办法出台",
         ev=blind("c_599", "chinalawtranslate.com/digital-humans-draft"),
         truth="CONTRADICTS", why="页面即《数字虚拟人信息服务管理办法（征求意见稿）》，直接否定'没有任何'"),
    dict(id="CT-07", scenario="true_contradict", claim_source="derived",
         claim="成年果蝇大脑连接组在2018年就已完成绘制",
         ev=blind("c_562", "mittrchina.com/news/detail/16047"),
         truth="CONTRADICTS", why="时间限定词冲突：2018年只是项目起源/成像，文章称'最终完成了…映射'在数年后"),
]
S += [  # ---- "不是A而是B" 对照构式（不得判 CONTRADICTS）----
    dict(id="CT-08", scenario="contrast_construction", claim_source="original",
         claim="神经科学现在的基本共识是，记忆不是存在脑子里的文件，而是每次回忆时重新组装出来的",
         ev=blind("c_573", "blog.leowang.net/mt0uj89j-qy"),
         truth="PARTIAL_SUPPORT", why="证据与 Claim 同构式共识（记忆是重写不是读取），非反驳"),
    dict(id="CT-09", scenario="contrast_construction", claim_source="original",
         claim="技术可以慢，社会规则必须提前想，否则等第一例真做出来那天，吵的就不是哲学，是官司",
         ev=blind("c_601", "zh.wikipedia.org/wiki/%E8%BE%A9%E8%AF%81%E6%B3%95"),
         truth="IRRELEVANT", why="'不是A是B'构式+无关辩证法页面，构式否定不构成反驳"),
    dict(id="CT-10", scenario="contrast_construction", claim_source="original",
         claim="影视作品里，这一步经常一笔带过：扫描，上传，永生",
         ev=blind("c_553", "sohu.com/a/1052964186"),
         truth="CONTEXT_ONLY", why="Evidence'数字永生不是科幻'是对命题的肯定式表达（不是科幻=是真的），语境不同非反驳"),
    dict(id="CT-11", scenario="contrast_construction", claim_source="original",
         claim="它画的是一张接线图，不是意识",
         ev=blind("c_565", "news.cn/tech/20230109"),
         truth="IRRELEVANT", why="Claim 自带'不是'但证据为 AI 绘画主题无关页，不构成反驳"),
]
S += [  # ---- 否定词辖域（否定对象不同，不得判 CONTRADICTS）----
    dict(id="CT-12", scenario="negation_scope", claim_source="original",
         claim="日常里靠的是记忆和身体的连续",
         ev=blind("c_589", "zh.wikipedia.org/zh-hans/%E8%A8%98%E6%86%B6"),
         truth="IRRELEVANT", why="'并没有特定局限的记忆中心区'否定的对象是解剖结构，与命题谓词无关"),
    dict(id="CT-13", scenario="negation_scope", claim_source="original",
         claim="扫描：刚起步，图谱越来越细，几十年内还会有大进展",
         ev=blind("c_603", "pmc.ncbi.nlm.nih.gov/articles/PMC10408928"),
         truth="CONTEXT_ONLY", why="病理切片扫描的'分辨率还受到…影响'否定对象不同，仅词面相邻"),
    dict(id="CT-14", scenario="negation_scope", claim_source="original",
         claim="把三层收拢，给一个冷静的判断",
         ev=blind("c_602", "bilibili.com/video/BV1MWKh6SEEB"),
         truth="IRRELEVANT", why="'真正的情绪稳定，不是忍住'否定对象为情绪管理，与命题无关"),
]
S += [  # ---- Claim 自带否定（含'没有/不是'但证据不背书反驳）----
    dict(id="CT-15", scenario="claim_internal_neg", claim_source="original",
         claim="神经科学现在的基本共识是，记忆不是存在脑子里的文件，而是每次回忆时重新组装出来的",
         ev=blind("c_573", "threads.com/@incrediville_tw/post/DO8N_mQDz6W"),
         truth="PARTIAL_SUPPORT", why="Threads 帖同构式共识（回忆是改编版），非反驳"),
    dict(id="CT-16", scenario="claim_internal_neg", claim_source="original",
         claim="它画的是一张接线图，不是意识",
         ev=blind("c_565", "html.rhhz.net/XNSYDXXBSKB/HTML/2017-5-91.htm"),
         truth="IRRELEVANT", why="审美哲学论文与命题无关，Claim 自带否定不构成反驳资格"),
    dict(id="CT-17", scenario="claim_internal_neg", claim_source="original",
         claim="技术可以慢，社会规则必须提前想，否则等第一例真做出来那天，吵的就不是哲学，是官司",
         ev=blind("c_601", "ea.sinica.edu.tw/QDown.ashx?ID=6975"),
         truth="PARTIAL_SUPPORT", why="法哲学论文与'技术/法律/哲学'主题相邻，但'不是A是B'构式非反驳"),
]
S += [  # ---- 问句 / 反问句（不可判 CONTRADICTS）----
    dict(id="CT-18", scenario="question", claim_source="original",
         claim="从果蝇到人，差多远",
         ev=blind("c_567", "news.cn/tech/20260324"),
         truth="PARTIAL_SUPPORT", why="问句不可反驳；证据提供果蝇/人脑对比背景"),
    dict(id="CT-19", scenario="question", claim_source="original",
         claim="死后上传的法律地位是什么",
         ev=blind("c_598", "zh.wikipedia.org/wiki/%E6%84%8F%E8%AF%86%E4%B8%8A%E4%BC%A0"),
         truth="PARTIAL_SUPPORT", why="问句不可反驳；维基专节讨论仿真品法律地位"),
    dict(id="CT-20", scenario="question", claim_source="original",
         claim="谁有权删除一个'数字人'",
         ev=blind("c_599", "chinalawtranslate.com/digital-humans-draft"),
         truth="PARTIAL_SUPPORT", why="问句不可反驳；管理办法直接规定数字人权益保护"),
    dict(id="CT-21", scenario="question", claim_source="original",
         claim="还有一串现实问题排队等着：副本算人吗",
         ev=blind("c_597", "forum.gamer.com.tw/C.php?bsn=17608"),
         truth="IRRELEVANT", why="问句+游戏'副本'同形异义，无主题关系"),
]
S += [  # ---- 不同对象的否定（同形词/他域否定，不得判 CONTRADICTS）----
    dict(id="CT-22", scenario="different_object", claim_source="original",
         claim="定价一两万美元，一次付清",
         ev=db_ev("e_7d1f83eecfbf"),
         truth="IRRELEVANT", why="阿里云定价页（对象不同），不构成对 Nectome 定价的任何关系"),
    dict(id="CT-23", scenario="different_object", claim_source="original",
         claim="先说扫描，这一步真有人在干",
         ev=blind("c_561", "ccdi.gov.cn/2026/01/14"),
         truth="IRRELEVANT", why="'技术扫描之下漏洞百出'的对象是审查扫描，与脑扫描不同对象"),
    dict(id="CT-24", scenario="different_object", claim_source="original",
         claim="第二步，复制：在电脑里重建一个功能一样的脑",
         ev=blind("c_557", "shuzhiduo.com/topic/%E6%80%8E%E4%B9%88%E6%8A%8A%E8%99%9A%E6%8B%9F%E6%9C%BA"),
         truth="IRRELEVANT", why="虚拟机复制教程（对象为 IT 虚拟机），同形词非否定"),
    dict(id="CT-25", scenario="different_object", claim_source="original",
         claim="今天的法律对这些问题基本空白",
         ev=blind("c_600", "court.gov.mo/sentence/zh/18717"),
         truth="IRRELEVANT", why="澳门法院空白支票罪判决（刑法对象不同），'空白'同形异义"),
    dict(id="CT-26", scenario="different_object", claim_source="original",
         claim="2025年，中国团队放出了毫米级的小鼠全脑图谱，这是目前最大的哺乳动物全脑连接组",
         ev=blind("c_563", "news.cn/world/20250410"),
         truth="PARTIAL_SUPPORT", why="主体/时间/最大背书，但'中国团队'与'连接组'限定未完全背书（英国《自然》国际成果）"),
]

out = {
    "_meta": {
        "name": "contradicts_stress_set",
        "note": "CONTRADICTS 压力测试集：26 样本，Evidence 全部为真实检索文本（盲测集合/第一轮数据库），"
                "Claim 为原文或派生可验证命题（claim_source 标记）；本集合冻结，仅用于阶段 4 验收评估，"
                "禁止用于 prompt 调参。",
        "scenarios": {
            "true_contradict": 7, "contrast_construction": 4, "negation_scope": 3,
            "claim_internal_neg": 3, "question": 4, "different_object": 5,
        },
    },
    "samples": [{
        "id": s["id"], "scenario": s["scenario"], "claim_source": s["claim_source"],
        "claim_text": s["claim"], "truth_label": s["truth"], "rationale": s["why"],
        "evidence": {"title": s["ev"]["title"], "snippet": s["ev"]["snippet"],
                     "text": s["ev"]["text"], "url": s["ev"]["url"]},
    } for s in S],
}
path = ROOT / "tests" / "data" / "contradicts_stress.json"
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
from collections import Counter
print("written:", path, "| samples:", len(S), "| truth:", dict(Counter(s["truth"] for s in S)))
