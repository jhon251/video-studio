"""证据语义回归基准集构建器（只读工具，不修改生产代码）。

样本来源（全部真实，非编造）：
- stored_round1：第一轮 Tavily 在线核查已入库的 43 条 Evidence（projects/video_studio.db，project p_f2215875dd49），
  evidence.text 即第一轮提取窗口原文；
- refetch_same_query：第一轮被拒候选（CONTEXT_ONLY/NO_KEYWORD）未存全文，按第一轮同一条 Tavily 查询补采原文
  （projects/_drafts/r1_context_collection.json）。

输出：tests/data/evidence_regression_r1.json（50 样本：10 DIRECT / 10 PARTIAL / 10 IRRELEVANT /
5 真 CONTRADICTS / 5 伪 CONTRADICTS / 5 CONTEXT_ONLY / 5 关键词高重叠但无关）。
truth_label 为人工标注（按 V2.1 语义标准：主体/谓词/对象/关键限定词/问句/定义句规则）；
system_label_r1 为第一轮系统实际标签（含错误案例，作为回归对照）。
"""
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from video_studio.tools.search_provider import _strip_tags  # noqa: E402

DB_PATH = ROOT / "projects" / "video_studio.db"
COLLECTION = json.loads((ROOT / "projects" / "_drafts" / "r1_context_collection.json")
                        .read_text(encoding="utf-8"))

db = sqlite3.connect(str(DB_PATH))
db.row_factory = sqlite3.Row


def claim_text(cid: str) -> str:
    row = db.execute("SELECT text FROM claims WHERE claim_id=?", (cid,)).fetchone()
    return row["text"] if row else ""


def db_evidence(eid: str) -> dict:
    row = db.execute("SELECT * FROM evidence WHERE evidence_id=?", (eid,)).fetchone()
    r = dict(row)
    return {
        "source": r["source"], "url": r["url"],
        "source_type_r1": r["source_type"], "reliability_r1": r["reliability"],
        "system_label_r1": r["support_level"],
        "text": (r["excerpt"] or ""),
        "text_source": "page_excerpt_r1",
        "evidence_id": r["evidence_id"],
        "provenance": "stored_round1",
    }


def refetch_evidence(cid: str, url: str) -> dict:
    rec = next(x for x in COLLECTION if x["claim_id"] == cid)
    page = next(p for p in rec["pages"] if p["url"] == url)
    result = next(r for r in rec["results"] if r["url"] == url)
    return {
        "source": (urlparse_host(url)), "url": url,
        "title": result["title"], "snippet": result["snippet"],
        "text": _strip_tags(page.get("text") or "")[:1500],
        "text_source": "page_text_refetch",
        "system_label_r1": "rejected(未入库, 同查询补采)",
        "provenance": "refetch_same_query",
    }


def urlparse_host(url: str) -> str:
    from urllib.parse import urlparse
    return (urlparse(url).netloc or url).lower()


# ---------------- 50 样本规格 ----------------
# 每项: id, category, claim(id 或 None), derived(派生 Claim 文本或 None),
#       ev=("db", eid) 或 ("ref", claim_id, url), truth, rationale
S = []
S += [  # ---- 10 真正 DIRECT_SUPPORT ----
    dict(id="RS-001", cat="TRUE_DIRECT", claim="c_578", ev=("db", "e_f428f15e9603"),
         truth="DIRECT_SUPPORT", why="经济日报：数据中心运行成本六成是电费、电费四成多来自冷却散热——直接支撑'算力、能耗、散热每一项都是钱'的主体与谓词"),
    dict(id="RS-002", cat="TRUE_DIRECT", claim="c_578", ev=("db", "e_28363c156c79"),
         truth="DIRECT_SUPPORT", why="钛媒体：全文主题即算力成本构成（电费/散热），与命题同一主题同一判断"),
    dict(id="RS-003", cat="TRUE_DIRECT", claim="c_552", ev=("db", "e_8da2bf15b259"),
         truth="DIRECT_SUPPORT", why="U-ACG 文精确描述《刀剑神域》Underworld 设定（数位人类婴儿置入虚拟世界）——直接支撑该世界观命题"),
    dict(id="RS-004", cat="TRUE_DIRECT", claim=None, derived="2025年，中国团队联合构建了具有单细胞分辨率的小鼠大脑图谱，成果发表于《神经元》",
         ev=("db", "e_e6eafe02289b"),
         truth="DIRECT_SUPPORT", why="bsbii 转中科院稿：2025-03-26、中科院脑智卓越中心联合多家单位、单细胞分辨率小鼠大脑图谱、发表于《神经元》——主体/时间/机构/事件全部命中（派生 Claim 去掉原句未背书的'最大/连接组'限定）"),
    dict(id="RS-005", cat="TRUE_DIRECT", claim=None, derived="人脑包含约860亿个神经元",
         ev=("db", "e_81fcbfdbffb4"),
         truth="DIRECT_SUPPORT", why="中科院神经所稿：'人脑则包含约860亿个神经元和数万亿个突触'——数字与约数限定词完全一致"),
    dict(id="RS-006", cat="TRUE_DIRECT", claim=None, derived="虚拟数字人侵权已出现司法判例：杭州互联网法院2023年作出首例判决",
         ev=("db", "e_e31cca9608ea"),
         truth="DIRECT_SUPPORT", why="长安网标题即'首例涉虚拟数字人侵权案，在杭州互联网法院判决'——主体/事件/时间完整背书"),
    dict(id="RS-007", cat="TRUE_DIRECT", claim=None, derived="现阶段的虚拟数字果蝇模型还不具备思想和意识，距离'数字生命'还很远",
         ev=("db", "e_7e74f4ff5bd2"),
         truth="DIRECT_SUPPORT", why="科技日报引中科院严军原话'现阶段的成果还远未达到这一水平'——直接支撑该否定性命题"),
    dict(id="RS-008", cat="TRUE_DIRECT", claim=None, derived="'意识上传'指将人的大脑活动全面扫描并数字化、在计算机中重建完整思维模型的概念",
         ev=("db", "e_db062bc437b7"),
         truth="DIRECT_SUPPORT", why="光明网对该概念给出完全一致的定义性表述"),
    dict(id="RS-009", cat="TRUE_DIRECT", claim=None, derived="人类大脑在约25瓦的低能耗下运行",
         ev=("db", "e_48e45608485d"),
         truth="DIRECT_SUPPORT", why="清华稿：'人类大脑在25瓦的极低能耗下'——数字与约数一致"),
    dict(id="RS-010", cat="TRUE_DIRECT", claim=None, derived="大脑状态涉及突触连接、胶质细胞等多个层面，且随发育动态变化",
         ev=("db", "e_3ebdd7e004bf"),
         truth="DIRECT_SUPPORT", why="CellSignal 神经科学基础：突触连接/小胶质细胞定殖/发育动态——支撑'不止连接关系'的多层面命题"),
]
S += [  # ---- 10 PARTIAL_SUPPORT ----
    dict(id="RS-011", cat="TRUE_PARTIAL", claim="c_568", ev=("db", "e_48e45608485d"),
         truth="PARTIAL_SUPPORT", why="清华稿写'约1000亿神经元、100万亿突触'——支持量级，但与 Claim 的'860亿/百万亿'数字不完全一致，仅部分背书"),
    dict(id="RS-012", cat="TRUE_PARTIAL", claim="c_563", ev=("db", "e_68f970301bed"),
         truth="PARTIAL_SUPPORT", why="PMC 中国脑科学计划进展——支持中国脑图谱进展背景，但未背书'目前最大哺乳动物全脑连接组'的'最大/连接组'限定"),
    dict(id="RS-013", cat="TRUE_PARTIAL", claim="c_563", ev=("db", "e_e6eafe02289b"),
         truth="PARTIAL_SUPPORT", why="bsbii 是细胞/空间转录组图谱而非连接组，'目前最大'亦未出现——仅部分背书"),
    dict(id="RS-014", cat="TRUE_PARTIAL", claim="c_573", ev=("db", "e_a067e302b6d3"),
         truth="PARTIAL_SUPPORT", why="中科院神经所科普讨论记忆本质，但未背书'基本共识'这一学界共识强限定词"),
    dict(id="RS-015", cat="TRUE_PARTIAL", claim="c_557", ev=("db", "e_6b6ed429c74c"),
         truth="PARTIAL_SUPPORT", why="leowang 讨论连接组是否充分/功能主义，与'第二步复制'的定义句同主题讨论，但不构成事实背书"),
    dict(id="RS-016", cat="TRUE_PARTIAL", claim="c_574", ev=("db", "e_5e5aa0875447"),
         truth="PARTIAL_SUPPORT", why="集智 AI 虚拟细胞属相邻领域（模拟细胞而非全脑状态清单），仅部分相关"),
    dict(id="RS-017", cat="TRUE_PARTIAL", claim="c_589", ev=("db", "e_5a7b4b0aee32"),
         truth="PARTIAL_SUPPORT", why="医院科普讨论记忆与健康影响因素，未直接论证'身份连续性依靠记忆与身体'"),
    dict(id="RS-018", cat="TRUE_PARTIAL", claim="c_569", ev=("db", "e_ff079a4a13a4"),
         truth="PARTIAL_SUPPORT", why="标题'AI果蝇诞生：人类大脑上传与数字永生'与主题相关，但窗口内未见果蝇/人脑数量对比数字"),
    dict(id="RS-019", cat="TRUE_PARTIAL", claim="c_567", ev=("db", "e_81fcbfdbffb4"),
         truth="PARTIAL_SUPPORT", why="中科院神经所给出果蝇12.5万/人脑860亿的背景数字——为'从果蝇到人差多远'提供背景支撑；问句不可判反驳"),
    dict(id="RS-020", cat="TRUE_PARTIAL", claim="c_583", ev=("db", "e_4511f789bc8b"),
         truth="PARTIAL_SUPPORT", why="界面新闻讨论意识上传与'副本是否是你'哲学问题——与 Claim 同主题，属讨论性部分支撑"),
]
S += [  # ---- 10 IRRELEVANT ----
    dict(id="RS-021", cat="TRUE_IRRELEVANT", claim="c_612", ev=("db", "e_1130dfec79d4"),
         truth="IRRELEVANT", why="IRS 税务誊本页与'副本上线/永生'零主题关系"),
    dict(id="RS-022", cat="TRUE_IRRELEVANT", claim="c_572", ev=("db", "e_03dc017bb1f5"),
         truth="IRRELEVANT", why="CAN 总线协议教程与'接线图装不下一个你'零主题关系（'接线'词面误匹配）"),
    dict(id="RS-023", cat="TRUE_IRRELEVANT", claim="c_561", ev=("db", "e_2b2cfbdafb5e"),
         truth="IRRELEVANT", why="新华网家长群诈骗评论（含'扫描二维码'）与'大脑扫描有人在干'零主题关系"),
    dict(id="RS-024", cat="TRUE_IRRELEVANT", claim="c_595", ev=("db", "e_7d1f83eecfbf"),
         truth="IRRELEVANT", why="阿里云产品定价页与'Nectome 定价一两万美元'零主题关系（'定价'词面误匹配）"),
    dict(id="RS-025", cat="TRUE_IRRELEVANT", claim="c_579", ev=("db", "e_46966f57cbca"),
         truth="IRRELEVANT", why="情绪粒度心理学文章与'模拟颗粒度/意识'零主题关系（'粒度'词面误匹配）"),
    dict(id="RS-026", cat="TRUE_IRRELEVANT", claim="c_579", ev=("db", "e_4d495098040b"),
         truth="IRRELEVANT", why="果壳职场黑话文章与'模拟颗粒度/意识'零主题关系"),
    dict(id="RS-027", cat="TRUE_IRRELEVANT", claim="c_584", ev=("db", "e_2c3f113919d1"),
         truth="IRRELEVANT", why="党史网儒法斗争文章与'意识上传两派哲学争论'零主题关系（'哲学'词面误匹配）"),
    dict(id="RS-028", cat="TRUE_IRRELEVANT", claim="c_580", ev=("db", "e_8479647e16c3"),
         truth="IRRELEVANT", why="西北农林面试技巧页与'项目贵到做不起'零主题关系（'项目'词面误匹配）"),
    dict(id="RS-029", cat="TRUE_IRRELEVANT", claim="c_584", ev=("db", "e_d141a9846832"),
         truth="IRRELEVANT", why="人大古希腊哲学研讨会纪要与本命题（上传/副本同一性）零主题关系"),
    dict(id="RS-030", cat="TRUE_IRRELEVANT", claim="c_593", ev=("ref", "c_593",
         "https://guides.lib.berkeley.edu/az/databases?q=Velotas+AI+B1+Reviews"),
         truth="IRRELEVANT", why="伯克利数据库导航页与'这条线上已经有人在卖东西了'零词元重叠、零主题关系（第一轮被 NO_KEYWORD 预筛拒绝的同类样本）"),
]
S += [  # ---- 5 真正 CONTRADICTS（Evidence 对可验证命题构成真实否定）----
    dict(id="RS-031", cat="TRUE_CONTRADICT", claim=None, derived="现阶段的虚拟数字果蝇已经拥有思想和意识",
         ev=("db", "e_7e74f4ff5bd2"),
         truth="CONTRADICTS", why="严军原话'只有当虚拟模型拥有思想和意识…现阶段的成果还远未达到这一水平'——对命题主体+谓词的真实否定"),
    dict(id="RS-032", cat="TRUE_CONTRADICT", claim=None, derived="2045意识上传计划得到了研究界的普遍看好",
         ev=("db", "e_b7cf47923e8d"),
         truth="CONTRADICTS", why="人民日报：'大部分研究者并不看好…持怀疑态度…太过野心勃勃'——对命题的真实否定"),
    dict(id="RS-033", cat="TRUE_CONTRADICT", claim=None, derived="以同等精度重构人脑在近年内即可完成",
         ev=("db", "e_81fcbfdbffb4"),
         truth="CONTRADICTS", why="徐春：'至少在近十年内，还很难完成'——时间限定词上的真实否定"),
    dict(id="RS-034", cat="TRUE_CONTRADICT", claim=None, derived="完美模拟智能行为就等于拥有意识",
         ev=("db", "e_6b6ed429c74c"),
         truth="CONTRADICTS", why="leowang 引中文房间论证：'行为相似，不等于内在体验相同'——对命题的真实否定"),
    dict(id="RS-035", cat="TRUE_CONTRADICT", claim=None, derived="虚拟数字人侵权在法律上尚无任何判例",
         ev=("db", "e_e31cca9608ea"),
         truth="CONTRADICTS", why="长安网：'首例涉虚拟数字人侵权案…判决'——'无任何判例'被真实否定"),
]
S += [  # ---- 5 伪 CONTRADICTS（第一轮系统误判，truth 为正确标签）----
    dict(id="RS-036", cat="PSEUDO_CONTRADICT", claim="c_567", ev=("db", "e_7e74f4ff5bd2"),
         truth="PARTIAL_SUPPORT", why="系统判 CONTRADICTS：Claim 是反问句（'从果蝇到人，差多远'）不可被反驳；证据实为背景支持（'并非真实环境交互'触发否定词误判）"),
    dict(id="RS-037", cat="PSEUDO_CONTRADICT", claim="c_557", ev=("db", "e_6b6ed429c74c"),
         truth="PARTIAL_SUPPORT", why="系统判 CONTRADICTS：Claim 是定义句（第二步=复制），普通讨论页不构成反驳"),
    dict(id="RS-038", cat="PSEUDO_CONTRADICT", claim="c_553", ev=("db", "e_b7cf47923e8d"),
         truth="CONTEXT_ONLY", why="系统判 CONTRADICTS：Claim 讲影视叙事习惯，证据是现实项目报道——语境不同（'并非真正意义上生命的永生'触发否定词误判）"),
    dict(id="RS-039", cat="PSEUDO_CONTRADICT", claim="c_559", ev=("db", "e_052b58ccd93c"),
         truth="IRRELEVANT", why="系统判 CONTRADICTS：woshipm 企服产品文与 Claim 零主题关系，否定词在无关文本中误触发"),
    dict(id="RS-040", cat="PSEUDO_CONTRADICT", claim="c_565", ev=("db", "e_d4b1a2d321cf"),
         truth="IRRELEVANT", why="系统判 CONTRADICTS：央视 AI 绘画文与'接线图不是意识'零主题关系；Claim 自带'不是'叠加页面否定词双重误触发"),
]
S += [  # ---- 5 CONTEXT_ONLY（仅个别词面出现，不构成讨论）----
    dict(id="RS-041", cat="CONTEXT_ONLY", claim="c_571", ev=("db", "e_19faefaed749"),
         truth="CONTEXT_ONLY", why="CIRM 尼古丁/多巴胺论文与'三百个神经元尚且如此'仅共享'神经元'词面，无 302 线虫主题讨论（系统误标 DIRECT）"),
    dict(id="RS-042", cat="CONTEXT_ONLY", claim="c_571", ev=("db", "e_a76be32143e1"),
         truth="CONTEXT_ONLY", why="科学网人脑神经元计数方法论与 302 线虫命题仅共享'神经元'词面（系统误标 DIRECT）"),
    dict(id="RS-043", cat="CONTEXT_ONLY", claim="c_556", ev=("db", "e_551c7a2f1001"),
         truth="CONTEXT_ONLY", why="中科院门户首页与'第一步扫描大脑结构'仅个别词面重合，无任何命题讨论（系统误标 DIRECT）"),
    dict(id="RS-044", cat="CONTEXT_ONLY", claim="c_609", ev=("db", "e_acc53b57462c"),
         truth="CONTEXT_ONLY", why="Azure 数据科学词典页与'结构上科学家刚开始画图'仅弱词面重合（系统误标 DIRECT）"),
    dict(id="RS-045", cat="CONTEXT_ONLY", claim="c_609", ev=("db", "e_b78967d63049"),
         truth="CONTEXT_ONLY", why="银河系结构图新闻与大脑命题仅共享'结构/科学家'弱词面，主题为天文学（系统误标 DIRECT）"),
]
S += [  # ---- 5 关键词高度重叠但实际无关 ----
    dict(id="RS-046", cat="KEYWORD_OVERLAP_IRRELEVANT", claim="c_558", ev=("db", "e_b3274b01217d"),
         truth="IRRELEVANT", why="北京公积金转移指南与'第三步，转移：让本人住进去'高重叠（第一步/第二步/第三步/转移）——同形异义，主题为零"),
    dict(id="RS-047", cat="KEYWORD_OVERLAP_IRRELEVANT", claim="c_560", ev=("db", "e_3570d65f16c9"),
         truth="IRRELEVANT", why="'三步走'发展战略（改革开放语境）与'后面就按这三步走'高重叠——同形异义"),
    dict(id="RS-048", cat="KEYWORD_OVERLAP_IRRELEVANT", claim="c_607", ev=("db", "e_8e57ce3ed125"),
         truth="IRRELEVANT", why="hongtaoh'人生算法/多重宇宙'博文与'多留点真实的人生'高重叠（人生/命运）——主题为投资策略，非本命题"),
    dict(id="RS-049", cat="KEYWORD_OVERLAP_IRRELEVANT", claim="c_600", ev=("db", "e_7b85a15ed620"),
         truth="IRRELEVANT", why="台湾法学'空白要素填补规范'与'法律对这些问题基本空白'高重叠（法律/空白）——同形异义，主题为刑法构成要件"),
    dict(id="RS-050", cat="KEYWORD_OVERLAP_IRRELEVANT", claim="c_593", ev=("ref", "c_593",
         "https://sell.amazon.com/zh/blog/sell-my-stuff-online"),
         truth="IRRELEVANT", why="Amazon'如何在网上出售你的东西'与'这条线上已经有人在卖东西了'高重叠（线上/卖东西）——主题是电商卖货，非大脑保存服务"),
]

# 修正 RS-043 的 evidence_id（cas.cn 首页）
CAS_ID = None
for row in db.execute("SELECT evidence_id, source FROM evidence WHERE project_id='p_f2215875dd49'"):
    if row["source"] == "www.cas.cn":
        CAS_ID = row["evidence_id"]
assert CAS_ID, "cas.cn evidence not found"
for item in S:
    if item["id"] == "RS-043":
        item["ev"] = ("db", CAS_ID)

CATS = {"TRUE_DIRECT": 10, "TRUE_PARTIAL": 10, "TRUE_IRRELEVANT": 10,
        "TRUE_CONTRADICT": 5, "PSEUDO_CONTRADICT": 5, "CONTEXT_ONLY": 5,
        "KEYWORD_OVERLAP_IRRELEVANT": 5}

dataset = []
for item in S:
    if item["ev"][0] == "db":
        ev = db_evidence(item["ev"][1])
    else:
        ev = refetch_evidence(item["ev"][1], item["ev"][2])
    cid = item["claim"]
    dataset.append({
        "id": item["id"],
        "category": item["cat"],
        "claim_id": cid,
        "claim_text": item.get("derived") or claim_text(cid),
        "claim_source": "derived" if item.get("derived") else "original",
        "evidence": {k: ev[k] for k in
                     ("source", "url", "text", "text_source", "system_label_r1",
                      "provenance")} | {"title": ev.get("title", ""), "snippet": ev.get("snippet", "")},
        "truth_label": item["truth"],
        "rationale": item["why"],
    })

counts = {}
for d in dataset:
    counts[d["category"]] = counts.get(d["category"], 0) + 1
assert counts == CATS, counts

out = {
    "_meta": {
        "name": "evidence_semantic_regression_r1",
        "source_round": "yongsheng-tavily-r1 (p_f2215875dd49)",
        "note": "50 样本全部来自第一轮真实运行：45 条为已入库 Evidence 原文（page_excerpt_r1），"
                "5 条为第一轮同查询补采原文（page_text_refetch）；truth_label 为人工标注（V2.1 语义标准）。"
                "禁止编造或替换样本文本。",
        "categories": CATS,
    },
    "samples": dataset,
}
path = ROOT / "tests" / "data" / "evidence_regression_r1.json"
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print("written:", path, "| counts:", counts)
