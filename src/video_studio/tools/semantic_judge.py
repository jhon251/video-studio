"""V2.1 阶段 1：Claim → Evidence 语义相关性 / support_level 判定（纯规则、零依赖、确定性）。

设计依据：docs/证据语义回归基准.md 与用户 V2.1 阶段 1 要求。

判定原则：
- 关键词重叠 ≠ 语义支持；同一主题 ≠ 支持该 Claim；官方来源 ≠ 自动相关；
  高质量来源 ≠ 自动 DIRECT；
- 必须判断主体/谓词/对象/时间/数字/范围等关键限定词是否一致；
- 缺少关键限定词时不得升级为 DIRECT；
- 问句/反问句、第 X 步定义句、影视叙事句不可被"反驳"；
- CONTRADICTS 仅作支持关系标签输出（语义层判定），本阶段不接入 fact_check 调用链，
  不改变任何生产裁决行为。

evidence 入参：dict，字段 title / snippet / text（title+snippet 参与词面定位，
text 参与否定词辖域判断）。
"""

from __future__ import annotations

import re

# ---------------- 词典 ----------------
DOMAINS: dict[str, set[str]] = {
    "BRAIN": {"神经元", "突触", "大脑", "人脑", "胶质", "神经", "连接组", "图谱",
              "全脑图谱", "脑图谱", "果蝇", "电子果蝇", "数字果蝇", "线虫", "小鼠",
              "扫描", "记忆", "意识", "脑科学", "神经科学", "脑机", "突触强度",
              "神经递质", "分子", "模拟", "脑组织", "小脑", "脑区", "皮层", "髓鞘",
              "神经发生", "虚拟模型", "数字生命", "接线图", "脑计划", "发育",
              "多巴胺能神经元", "神经细胞", "复制", "重构", "重建", "智能", "行为"},
    "UPLOAD": {"上传", "永生", "数字永生", "意识上传", "心灵上传", "副本", "数字人",
               "虚拟数字人", "思维模型", "数字化", "人格", "记忆上传", "上传者",
               "替身", "人工大脑", "全息", "2045", "阿凡达"},
    "LAW": {"法律", "判决", "判例", "侵权", "诉讼", "法院", "司法", "权利", "合规",
            "案例", "先例", "首例"},
    "SCIFI": {"黑镜", "刀剑神域", "圣朱尼佩罗", "Underworld", "影视", "小说", "电影",
              "剧情", "故事", "影片", "剧中", "科幻", "传送机", "轻小说"},
    "ACAD": {"中科院", "科学院", "大学", "研究所", "研究院", "期刊", "论文", "发表于",
             "作者", "研究员", "教授", "院士", "实验室", "课题组"},
    "ECON": {"算力", "能耗", "散热", "电费", "成本", "功耗", "电价", "数据中心",
             "冷却", "电力", "耗电", "电耗", "用电"},
    "MONEY": {"美元", "美金"},
    "GOV": {"公积金", "账户", "缴存", "医保", "社保", "转移接续", "办事", "住房公积金"},
    "POLITICS": {"战略", "改革开放", "小康", "邓小平", "三步走", "发展战略"},
    "INVEST": {"投资", "彩票", "多重宇宙", "暴富", "运气", "股票", "收益"},
    "TECHBUS": {"总线", "协议", "报文", "通信", "芯片", "物联网", "数据帧"},
    "HR": {"面试", "求职", "简历", "自我介绍"},
    "PSY": {"情绪", "心理", "焦虑", "压力", "抑郁", "幸福感"},
    "PHIL": {"哲学", "哲学家", "哲学史", "研讨会"},
    "PHIL_HISTORY": {"儒法", "孔子", "毛泽东", "古希腊", "文化大革命"},
    "PHIL_IDENTITY": {"信息一致", "连续性", "同一性", "身份连续"},
    "ASTRO": {"银河系", "天文", "星系", "宇宙"},
    "TAX": {"税务", "报税", "纳税人", "誊本", "IRS"},
    "ECOMMERCE": {"出售", "电商", "卖家", "买家", "商品", "亚马逊", "网上出售"},
    "CLOUD": {"云计算", "Azure", "阿里云", "云服务", "云解决方案"},
    "BIZ": {"企业服务", "产品经理", "营收", "PMF", "SaaS", "工业软件", "生命周期", "创业"},
    "CRIMINAL": {"刑法", "刑事", "罪名", "犯罪", "构成要件", "最高法院"},
    "QR": {"二维码", "扫码", "条形码", "家长群", "入学"},
    "LIFE": {"细胞", "生命科学", "生物", "活细胞", "组学"},
}

SYNONYMS: dict[str, set[str]] = {
    "能耗": {"耗电", "耗能", "电耗", "用电", "功耗", "电费"},
    "散热": {"冷却", "制冷", "散热"},
    "判例": {"判决", "案例", "先例", "首例"},
    "数字果蝇": {"电子果蝇"},
    "人脑": {"人类大脑", "人的大脑", "人類大腦"},
    "神经元": {"神经细胞"},
    "刀剑神域": {"刀劍神域"},
    "基本共识": {"共识", "公认", "普遍认为", "学界共识"},
    "目前": {"至今", "当前", "迄今为止", "现阶段"},
    "第一": {"首次", "首例", "第一例", "最早"},
}

QUALIFIERS: dict[str, set[str]] = {
    "superlative": {"第一", "首次", "首例", "最大", "唯一", "最早"},
    "current": {"目前", "至今", "当前", "现阶段", "迄今为止"},
    "consensus": {"基本共识", "共识", "公认"},
    "absolute": {"永远", "必然"},
}
QUALIFIER_SYN: dict[str, set[str]] = {
    "第一": {"首次", "首例", "第一例", "最早"},
    "首次": {"第一", "首例", "第一例", "最早"},
    "首例": {"第一", "首次", "第一例", "最早"},
    "最早": {"第一", "首次", "首例"},
    "最大": {"最"},
    "唯一": {"唯一"},
    "目前": {"至今", "当前", "现阶段", "迄今为止"},
    "至今": {"目前", "当前", "现阶段", "迄今为止"},
    "当前": {"目前", "至今", "现阶段"},
    "现阶段": {"目前", "至今", "当前"},
    "基本共识": {"共识", "公认", "普遍认为", "学界共识"},
    "共识": {"基本共识", "公认", "普遍认为"},
    "公认": {"基本共识", "共识", "普遍认为"},
    "永远": {"永远", "永久"},
    "必然": {"必然"},
}

# 否定词：按类型区分（事实否定 / 可行性否定）
FACT_NEG = ("不具备", "不是", "并非", "没有", "尚无", "尚未", "否认", "不看好",
            "不赞成", "未达到", "远未", "不等于", "并未", "未完成", "不存在")
FEASIBILITY_NEG = ("很难", "无法", "不能", "不会")
NEG_WORDS = FACT_NEG + FEASIBILITY_NEG
NEG_GUARD_AFTER = ("只", "仅", "止", "到")     # 不只是/不仅/不止/不到 → 非否定
NEG_GUARD_BEFORE = ("难道", "岂")
FEASIBILITY_CLAIM_WORDS = ("可以", "可能", "完成", "实现", "做到", "可行", "指日可待",
                           "近年内", "近十年内")

GENERIC_WORDS = {"结构", "项目", "答案", "问题", "步骤", "转移", "人生", "命运",
                 "产品", "东西", "故事", "画图", "科学家", "科学", "定价", "钱",
                 "贵", "第一步", "第二步", "第三步", "后面", "走", "空白", "身体",
                 "本人", "住", "粒度", "卖东西", "词", "接线"}

SCIENCE_FLAVOR_WORDS = {"科学", "科学家", "科研", "实验室", "论文", "实验"}

CN_DIGITS = "零一二三四五六七八九十百千万两"
NUMBER_RE = re.compile(r"(\d+(?:\.\d+)?)\s*([万亿千百]?)")
CN_NUM_RE = re.compile(r"[零一二三四五六七八九十百千万两]+(?:[万亿千百])?(?:个|条|例|次|年|瓦|倍)?")
LATIN_RE = re.compile(r"[A-Za-z][A-Za-z0-9\-\.]{2,}")
QUESTION_TAIL = ("吗", "呢", "？", "?")
QUESTION_MARKERS = ("凭什么", "是否", "多远", "多久", "多贵", "谁能", "谁会", "能不能",
                    "会不会", "算不算", "是不是")
STEP_DEF_MARKERS = ("第一步", "第二步", "第三步", "第四步")
GLOSS_DEF_MARKERS = ("指的是", "是指", "所谓", "叫做", "称为", "定义为", "意思是", "指")
FICTION_MARKERS = ("影视", "小说", "电影", "剧情", "故事", "影片", "剧中")
RHETORICAL_PAIR_RE = re.compile(r"是[^，。；]{1,40}还是")

# 领域共享可判 PARTIAL 的领域（排除指代风险大的 POLITICS 等）
SHARABLE_DOMAINS = {"BRAIN", "ACAD", "LIFE", "ASTRO", "UPLOAD", "LAW", "ECON",
                    "MONEY", "SCIFI"}


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", s or "").lower()


def _find_words(text: str, words: set[str]) -> set[str]:
    return {w for w in words if w.lower() in text.lower()}


def _domain_words(text: str) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for domain, words in DOMAINS.items():
        for w in _find_words(text, words):
            out.setdefault(w, set()).add(domain)
    return out


def _claim_domains(text: str) -> set[str]:
    doms: set[str] = set()
    for _w, ds in _domain_words(text).items():
        doms |= ds
    return doms


def _ev_domains(ev: dict) -> set[str]:
    doms: set[str] = set()
    for part in ("title", "snippet", "text"):
        doms |= _claim_domains(ev.get(part, ""))
    return doms


def _parse_cn_num(s: str) -> float:
    section, num = 0.0, 0.0
    for ch in s:
        if ch in "零一二三四五六七八九":
            num = "零一二三四五六七八九".index(ch)
        elif ch == "两":
            num = 2
        elif ch == "十":
            section += num if num else 1
            section *= 10
            num = 0
        elif ch == "百":
            section += num if num else 1
            section *= 100
            num = 0
        elif ch == "千":
            section += num if num else 1
            section *= 1000
            num = 0
        elif ch == "万":
            section = (section + num) * 1e4
            num = 0
        elif ch == "亿":
            section = (section + num) * 1e8
            num = 0
    return section + num


_UNIT_MULT = {"万亿": 1e12, "亿": 1e8, "万": 1e4, "千": 1e3, "百": 1e2}


def _extract_numbers(text: str) -> list[tuple[float, str, str]]:
    """返回 [(数值, 单位, 原始串)]；支持阿拉伯与中文数字。"""
    out = []
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*(万亿|亿|万|千|百)?", text):
        unit = m.group(2) or ""
        val = float(m.group(1)) * _UNIT_MULT.get(unit, 1.0)
        out.append((val, unit, m.group(0)))
    for m in CN_NUM_RE.finditer(text):
        raw = m.group(0)
        if m.start() > 0 and text[m.start() - 1] == "数":
            continue                       # 数万/数亿 → "若干"，不参与数值比较
        body = re.sub(r"(个|条|例|次|年|瓦|倍)$", "", raw)
        unit_match = re.search(r"([万亿千百])$", body)
        unit = unit_match.group(1) if unit_match else ""
        body2 = body[:-1] if unit else body
        if any(c in CN_DIGITS for c in body2) and any(c in "十百千万亿" for c in body2):
            val = _parse_cn_num(body2) * _UNIT_MULT.get(unit, 1.0)
            out.append((val, unit, raw))
    return out


def _extract_latin(text: str) -> set[str]:
    return {m.lower() for m in LATIN_RE.findall(text)}


def _has_claim_neg(text: str) -> bool:
    for w in NEG_WORDS:
        for m in re.finditer(re.escape(w), text):
            after = text[m.end():m.end() + 1]
            before = text[max(0, m.start() - 2):m.start()]
            if after in NEG_GUARD_AFTER or any(b in before for b in NEG_GUARD_BEFORE):
                continue
            return True
    return False


def _neg_positions(ev_text: str) -> list[int]:
    poss = []
    for w in NEG_WORDS:
        for m in re.finditer(re.escape(w), ev_text):
            after = ev_text[m.end():m.end() + 1]
            before = ev_text[max(0, m.start() - 2):m.start()]
            if after in NEG_GUARD_AFTER or any(b in before for b in NEG_GUARD_BEFORE):
                continue
            poss.append((m.start(), w))
    return poss


def _is_question(text: str) -> bool:
    t = text.strip()
    if t.endswith(QUESTION_TAIL):
        return True
    return any(w in t for w in QUESTION_MARKERS)


def _is_step_def(text: str) -> bool:
    return any(w in text for w in STEP_DEF_MARKERS)


def _is_gloss_def(text: str) -> bool:
    return any(w in text for w in GLOSS_DEF_MARKERS) and "指" in text


def _is_fiction(text: str) -> bool:
    return any(w in text for w in FICTION_MARKERS)


def _is_rhetorical(text: str) -> bool:
    return bool(RHETORICAL_PAIR_RE.search(text)) or _is_question(text)


def _claim_feasibility(text: str) -> bool:
    return any(w in text for w in FEASIBILITY_CLAIM_WORDS)


def _qualifier_requirements(text: str) -> list[str]:
    reqs = []
    for w in set(QUALIFIER_SYN):
        if w in text:
            reqs.append(w)
    return reqs


def _qualifier_confirmed(req: str, ev_text: str) -> bool:
    forms = QUALIFIER_SYN.get(req, {req}) | {req}
    return any(f in ev_text for f in forms)


def _number_conflict(claim_text: str, ev_text: str) -> bool:
    cn = _extract_numbers(claim_text)
    en = _extract_numbers(ev_text)
    if not cn or not en:
        return False
    for cv, cu, _ in cn:
        if not cu:
            continue
        for evv, eu, _ in en:
            if eu == cu and abs(cv - evv) > 1e-6:
                return True
    return False


def _has_cn_numeral(s: str) -> bool:
    return any(c in s for c in CN_DIGITS)


def _quantified_word_relation(claim_text: str, word: str) -> str:
    """word 与数字的邻接：before=数字在前（严格），after=数字在后（宽松），none=无。"""
    for m in re.finditer(re.escape(word), claim_text):
        head = claim_text[max(0, m.start() - 3): m.start()]
        tail = claim_text[m.end(): m.end() + 3]
        if re.search(r"\d", head) or _has_cn_numeral(head):
            return "before"
        if re.search(r"\d", tail) or _has_cn_numeral(tail):
            return "after"
    return "none"


def _scoped_negation(ev_text: str, matched_words: set[str], claim_feasible: bool) -> bool:
    """否定词辖域判断：否定落在命中核心词 ±60 字符内，且类型与 Claim 谓词兼容
    （可行性否定只对可行性谓词的 Claim 生效）。"""
    if not matched_words:
        return False
    poss = _neg_positions(ev_text)
    if not poss:
        return False
    word_positions = []
    for w in matched_words:
        for m in re.finditer(re.escape(w), ev_text):
            word_positions.append(m.start())
    if not word_positions:
        return False
    for q, neg_word in poss:
        if neg_word in FEASIBILITY_NEG and not claim_feasible:
            continue
        if any(abs(p - q) <= 60 for p in word_positions):
            return True
    return False


def _negated_span_affirmed(claim_text: str, ev_plain: str) -> bool:
    """Claim 否定式命题是否被 Evidence 肯定式背书（用于 claim_neg 的反驳资格）。"""
    for w in FACT_NEG:
        for m in re.finditer(re.escape(w), claim_text):
            span = claim_text[m.end(): m.end() + 12]
            span = re.sub(r"[，。；：、的了个了]", "", span)
            if len(span) < 2:
                continue
            for i in range(len(span) - 1):
                chunk = span[i:i + 2]
                forms = {chunk} | SYNONYMS.get(chunk, set())
                if any(f in ev_plain for f in forms):
                    return True
    return False


def _matched_core(profile: dict, ev: dict) -> tuple[set[str], bool]:
    ev_plain = ev.get("title", "") + ev.get("snippet", "") + ev.get("text", "")
    matched: set[str] = set()

    # 数字（含单位；中文数字与阿拉伯数字按数值比较）
    cn = _extract_numbers(profile["text"])
    en = _extract_numbers(ev_plain)
    for cv, cu, raw in cn:
        if cu:
            if any(abs(cv - evv) < 1e-6 for evv, eu, _ in en if eu == cu):
                matched.add(raw)
        else:
            if any(abs(cv - evv) < 1e-6 for evv, eu, _ in en if not eu):
                matched.add(raw)
    # 年份
    for year in re.findall(r"(19|20)\d{2}", profile["text"]):
        if year in ev_plain:
            matched.add(year)

    # 拉丁实体
    claim_latin = _extract_latin(profile["text"])
    ev_latin = _extract_latin(ev_plain)
    matched |= {l for l in claim_latin if l in ev_latin}

    # 领域词（含同义词）
    for w in _domain_words(profile["text"]):
        forms = {w} | SYNONYMS.get(w, set())
        if any(f.lower() in ev_plain.lower() for f in forms):
            matched.add(w)

    # 指代消解：这/那 + 领域词 → 指代性提及，不构成核心命中
    for w in list(matched):
        for m in re.finditer(re.escape(w), profile["text"]):
            head = profile["text"][max(0, m.start() - 2): m.start()]
            if "这" in head or "那" in head:
                matched.discard(w)
                break

    conflict = _number_conflict(profile["text"], ev_plain)
    return matched, conflict


def _claim_profile(text: str) -> dict:
    return {
        "text": text,
        "question": _is_question(text),
        "step_def": _is_step_def(text),
        "gloss_def": _is_gloss_def(text),
        "fiction": _is_fiction(text),
        "rhetorical": _is_rhetorical(text),
        "neg": _has_claim_neg(text),
        "feasible": _claim_feasibility(text),
        "domains": _claim_domains(text),
        "dom_words": _domain_words(text),
        "latin": _extract_latin(text),
        "qualifiers": _qualifier_requirements(text),
        "numbers": _extract_numbers(text),
    }


def _generic_overlap(claim_text: str, ev_plain: str) -> int:
    return sum(1 for w in _find_words(claim_text, GENERIC_WORDS) if w in ev_plain)


def _weak_science_adjacency(prof: dict, ev_domains: set[str], ev_plain: str) -> bool:
    claim_sci = bool({"BRAIN", "ACAD", "ASTRO", "LIFE"} & prof["domains"]) or \
        bool(_find_words(prof["text"], SCIENCE_FLAVOR_WORDS))
    ev_sci = bool({"BRAIN", "ACAD", "ASTRO", "LIFE"} & ev_domains) or \
        bool(_find_words(ev_plain, SCIENCE_FLAVOR_WORDS))
    return claim_sci and ev_sci


def judge_support(claim_text: str, evidence: dict) -> str:
    prof = _claim_profile(claim_text)
    ev_plain = evidence.get("title", "") + evidence.get("snippet", "") + evidence.get("text", "")
    ev_text = evidence.get("text", "") or ev_plain
    ev_domains = _ev_domains(evidence)

    # Claim 拉丁实体缺失 → 对象不一致 → 整体不相关
    if prof["latin"] and not (prof["latin"] & _extract_latin(ev_plain)):
        return "IRRELEVANT"

    matched, number_conflict = _matched_core(prof, evidence)
    core_matched = len(matched)

    # 对象错位/子领域冲突（同形异义）
    if "QR" in ev_domains and "扫描" in prof["dom_words"] and "扫描" in matched:
        return "IRRELEVANT"
    if "TAX" in ev_domains and prof["domains"] <= {"UPLOAD"} and (
            {"副本", "上传", "永生"} & set(prof["dom_words"])):
        return "IRRELEVANT"
    if "CRIMINAL" in ev_domains and "LAW" in prof["domains"]:
        return "IRRELEVANT"
    if "PHIL_HISTORY" in ev_domains and ("PHIL_IDENTITY" in prof["domains"]
                                        or "PHIL" in prof["domains"]):
        return "IRRELEVANT"

    # Claim 类型门槛：问句/第 X 步定义句不可判 DIRECT/CONTRADICTS
    if prof["question"] or prof["step_def"]:
        if core_matched >= 1:
            return "PARTIAL_SUPPORT"
        return "CONTEXT_ONLY" if _weak_science_adjacency(prof, ev_domains, ev_plain) else "IRRELEVANT"
    if prof["fiction"] and not ("SCIFI" in ev_domains):
        if core_matched >= 1 or _generic_overlap(claim_text, ev_plain) >= 1:
            return "CONTEXT_ONLY"
        return "IRRELEVANT"

    # 无核心命中 → 领域共享 PARTIAL / 弱词面
    if core_matched == 0:
        shared = prof["domains"] & ev_domains
        if shared & SHARABLE_DOMAINS:
            return "PARTIAL_SUPPORT"
        if "BRAIN" in prof["domains"] and "LIFE" in ev_domains:
            return "PARTIAL_SUPPORT"
        if _weak_science_adjacency(prof, ev_domains, ev_plain):
            return "CONTEXT_ONLY"
        return "IRRELEVANT"

    # 反驳资格（仅可验证断言命题；问句/定义句/叙事句已拦截）
    ev_neg_scoped = _scoped_negation(ev_text, matched, prof["feasible"])
    if prof["neg"]:
        if not ev_neg_scoped and _negated_span_affirmed(claim_text, ev_plain):
            return "CONTRADICTS"
    else:
        if ev_neg_scoped:
            return "CONTRADICTS"

    # 关键限定词确认
    quals_ok = all(_qualifier_confirmed(q, ev_plain) for q in prof["qualifiers"])

    # 数字冲突 → 最多 PARTIAL
    if number_conflict:
        return "PARTIAL_SUPPORT"

    # 量化严格：数字在前的领域词被命中但对应数字缺失 → 语境级
    #（若 Claim 的某个数字已命中，说明数字背书存在，不降级）
    claim_num_matched = any(raw in matched for _, _, raw in prof["numbers"])
    if not claim_num_matched:
        for w in prof["dom_words"]:
            if w in matched and _quantified_word_relation(claim_text, w) == "before":
                return "CONTEXT_ONLY"

    # 修辞句 → 最多 PARTIAL
    if prof["rhetorical"]:
        return "PARTIAL_SUPPORT"

    if core_matched >= 2 and quals_ok:
        return "DIRECT_SUPPORT"
    return "PARTIAL_SUPPORT"
