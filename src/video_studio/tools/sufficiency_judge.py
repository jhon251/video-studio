"""V2.1 Stage 6：Support Sufficiency 判定（四项结构性修复，隔离实现，未接生产链）。

① CONTRADICTS 与支持清单彻底解耦：LLM 单信号（contradiction_candidate + subject/object 一致 +
   仅 ASSERTION 资格）即输出 CONTRADICTS；规则层否定辖域只作审计信号，不作硬门槛；
   反驳判定先于 S4/S5 清单（数字不一致/限定词被否定恰是反驳证据本身）。
② S4/S5 确定性证据复核：限定词/数字/年份清单由规则层从 Claim 提取并注入 prompt，
   LLM 只打分；最终由确定性代码在 Evidence 原文（繁简归一后）中验证存在性，
   禁止以 LLM 自报字段绕过原文检查。
③ claim_type 细化：QUESTION/RHETORICAL/第X步定义句/对照构式 继续禁止 DIRECT；
   仅含"故事/影视"等词而无过渡语标记（这一步/经常/一笔带过/收拢等）的影视事实句
   不再自动 NARRATIVE；gloss 定义（指/指的是）陈述可验证事实时不封死 DIRECT。
④ 繁→简归一化：数据无关字符映射，仅用于规则侧匹配（重叠/存在性/辖域），不改原文。
全部改动为通用规范；无任何针对具体 Claim/URL/domain/Evidence 的特例。
"""

from __future__ import annotations

import hashlib
import json
import re
import time

from ..llm.router import SchemaError, validate_json
from .semantic_judge import (  # 只读复用规则层信号，不修改
    _claim_profile, _extract_numbers, _generic_overlap,
    _matched_core, _qualifier_requirements, _scoped_negation)

PROMPT_VERSION = "sufficiency-judge-v2"
MODEL_DEFAULT = "deepseek-chat"
TIER = "F"

# ④ 繁体→简体归一化（数据无关通用字符映射，仅规则侧匹配用；不改 Claim/Evidence 原文）
_T2S = str.maketrans({
    "億": "亿", "萬": "万", "個": "个", "條": "条", "隻": "只", "說": "说", "話": "话",
    "還": "还", "這": "这", "那": "那", "裡": "里", "裏": "里", "來": "来", "時": "时",
    "間": "间", "學": "学", "腦": "脑", "醫": "医", "療": "疗", "連": "连", "續": "续",
    "體": "体", "質": "质", "細": "细", "胞": "胞", "經": "经", "數": "数", "據": "据",
    "顯": "显", "微": "微", "鏡": "镜", "錄": "录", "實": "实", "現": "现", "無": "无",
    "沒": "没", "認": "认", "為": "为", "們": "们", "傳": "传", "機": "机", "組": "组",
    "裝": "装", "複": "复", "製": "制", "憶": "忆", "神": "神", "識": "识", "上": "上",
    "達": "达", "遠": "远", "與": "与", "於": "于", "關": "关", "鍵": "键", "點": "点",
    "現": "现", "種": "种", "類": "类", "圖": "图", "譜": "谱", "歸": "归", "納": "纳",
    "維": "维", "基": "基", "百": "百", "科": "科", "網": "网", "頁": "页", "內": "内",
    "容": "容", "電": "电", "話": "话", "視": "视", "頻": "频", "遊": "游", "戲": "戏",
    "隊": "队", "員": "员", "動": "动", "物": "物", "經": "经", "濟": "济", "龍": "龙",
    "醫": "医", "學": "学", "術": "术", "論": "论", "文": "文", "筆": "笔", "記": "记",
    "錄": "录", "應": "应", "用": "用", "軟": "软", "件": "件", "層": "层", "級": "级",
    "數": "数", "字": "字", "生": "生", "命": "命", "將": "将", "會": "会", "讓": "让",
    "從": "从", "開": "开", "始": "始", "結": "结", "構": "构", "閱": "阅", "讀": "读",
    "寫": "写", "觸": "触", "發": "发", "現": "现", "質": "质", "量": "量", "級": "级",
    "國": "国", "際": "际", "審": "审", "美": "美", "藝": "艺", "術": "术", "師": "师",
    "員": "员", "討": "讨", "論": "论", "認": "认", "識": "识", "權": "权", "刪": "删",
    "除": "除", "證": "证", "據": "据", "爭": "争", "議": "议", "決": "决", "擇": "择",
    "選": "选", "複": "复", "印": "印", "歐": "欧", "洲": "洲", "廠": "厂", "業": "业",
    "務": "务", "務": "务", "標": "标", "準": "准", "試": "试", "驗": "验", "環": "环",
    "境": "境", "樣": "样", "單": "单", "純": "纯", "簡": "简", "潔": "洁", "題": "题",
})


def t2s(text: str) -> str:
    return (text or "").translate(_T2S)


OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "relevance": {"type": "string", "enum": ["IRRELEVANT", "CONTEXT_ONLY", "RELEVANT"]},
        "claim_type": {"type": "string", "enum": ["ASSERTION", "QUESTION", "DEFINITION",
                                                 "RHETORICAL", "NARRATIVE", "CONTRAST"]},
        "contradiction_candidate": {"type": "boolean"},
        "subject_match": {"type": "boolean"},
        "object_match": {"type": "boolean"},
        "predicate_match": {"type": "boolean"},
        "conjunction_covered": {"type": "boolean"},
        "qualifiers": {"type": "object"},
        "numbers_years": {"type": "object"},
        "evidence_quote": {"type": "string"},
    },
    "required": ["relevance", "claim_type", "contradiction_candidate", "subject_match",
                 "object_match", "predicate_match", "conjunction_covered",
                 "qualifiers", "numbers_years", "evidence_quote"],
}

SYSTEM_PROMPT = (
    "你是事实核查系统的语义解析模块。给定 Claim 与 Evidence（标题/摘要/正文窗口），"
    "只做语义解析并输出 JSON 字段，不要输出任何结论。\n\n"
    "字段定义：\n"
    "1. relevance：IRRELEVANT=无主题关系（含同形异义/不同对象）；"
    "CONTEXT_ONLY=仅个别词面出现，不构成对命题的讨论；RELEVANT=真正讨论该命题主体。\n"
    "2. claim_type：QUESTION=问句/反问句；DEFINITION=第X步定义句；RHETORICAL=是…还是修辞句；"
    "CONTRAST=“不是A而是B/不是A是B”对照构式；NARRATIVE=纯过渡/叙事句；"
    "ASSERTION=其余可验证陈述（影视/故事背景的事实陈述也算 ASSERTION，不是 NARRATIVE）。\n"
    "3. contradiction_candidate：仅当 Claim 是可验证断言（ASSERTION）、且 Evidence 对同一"
    "主体/对象给出相反的结论/数字/年份/时间/判断（含否定词、数字不一致、时间冲突）时为 true；"
    "问句/定义句/修辞句/叙事句/对照构式一律 false；否定对象不同一律 false。\n"
    "4. subject_match / object_match：Evidence 与 Claim 主体/对象是否一致（同形异义词判 false）。\n"
    "5. predicate_match：Evidence 是否在讨论同一件事（注意：若 Evidence 是对该命题的否定反驳，"
    "仍属同一命题，应判 true——本字段不要求极性相同）。\n"
    "6. conjunction_covered：Claim 含多个并列断言时，Evidence 是否覆盖每一个。\n"
    "7. qualifiers：对象。键=下方给出的限定词清单原文，值=Evidence 是否明确背书该项。\n"
    "8. numbers_years：对象。键=下方给出的数字/年份清单原文，值=Evidence 是否给出同值同单位数字。\n"
    "9. evidence_quote：支撑判断的原文引用（≤80字）。\n\n"
    "只输出 JSON，不要解释。"
)

# few-shot 只允许来自重构后的 dev 集（Stage 6 纪律：禁止引用 197 冻结样本）
FEW_SHOT_V2: list[tuple] = [
    ("2024年10月，成年雌果蝇完整大脑神经图谱系列研究发表于《自然》期刊",
     "Evidence: 2024年10月，成年雌果蠅完整大腦神經圖譜系列研究，發表在《自然》期刊，辨識近14萬個神經元與5千萬個突觸。",
     {"relevance": "RELEVANT", "claim_type": "ASSERTION", "contradiction_candidate": False,
      "subject_match": True, "object_match": True, "predicate_match": True,
      "conjunction_covered": True, "qualifiers": {}, "numbers_years": {"2024": True},
      "evidence_quote": "2024年10月…發表在《自然》期刊"}),
    ("AI芯片的散热问题已经彻底解决",
     "Evidence: 當晶片的功耗突破1000瓦的時候，如果你不去解決散熱問題的話，AI的算力就無法釋放。",
     {"relevance": "RELEVANT", "claim_type": "ASSERTION", "contradiction_candidate": True,
      "subject_match": True, "object_match": True, "predicate_match": True,
      "conjunction_covered": True, "qualifiers": {}, "numbers_years": {},
      "evidence_quote": "功耗突破1000瓦…不解決散熱…算力無法釋放"}),
    ("注意，这三步的难度不在一个量级，而'永生'这个词，把三步打包卖成了一个产品",
     "Evidence: 稀土代价报道：中国主产区被污染的水源和伤痕累累的山丘。",
     {"relevance": "IRRELEVANT", "claim_type": "ASSERTION", "contradiction_candidate": False,
      "subject_match": False, "object_match": False, "predicate_match": False,
      "conjunction_covered": False, "qualifiers": {}, "numbers_years": {},
      "evidence_quote": "稀土…水源…山丘"}),
    ("2025年，中国团队放出了毫米级的小鼠全脑图谱，这是目前最大的哺乳动物全脑连接组",
     "Evidence: 全球最快小鼠全身成像，清晰可见单根神经纤维，用于神经退行性疾病结构变异定位与药物评估。",
     {"relevance": "CONTEXT_ONLY", "claim_type": "ASSERTION", "contradiction_candidate": False,
      "subject_match": False, "object_match": False, "predicate_match": False,
      "conjunction_covered": False, "qualifiers": {}, "numbers_years": {},
      "evidence_quote": "小鼠全身成像…單根神經纖維"}),
    ("2023年，科学家完成了成年果蝇的全脑连接组——十四万个神经元，每条连接都画了出来，发在《科学》上",
     "Evidence: 2024年10月，成年雌果蠅完整大腦神經圖譜系列研究發表在《自然》期刊，辨識近14萬個神經元。",
     {"relevance": "RELEVANT", "claim_type": "ASSERTION", "contradiction_candidate": False,
      "subject_match": True, "object_match": True, "predicate_match": True,
      "conjunction_covered": True, "qualifiers": {}, "numbers_years": {"2023": False},
      "evidence_quote": "2024年10月…《自然》期刊"}),
    ("有个老思想实验叫传送机：把你拆成原子，在火星重新组装，那个火星上的你，是你吗",
     "Evidence: 火星上的那個人走出了傳送艙，擁有你所有的記憶…問題來了：在火星上的那個人，真的是「你」嗎？",
     {"relevance": "RELEVANT", "claim_type": "QUESTION", "contradiction_candidate": False,
      "subject_match": True, "object_match": True, "predicate_match": True,
      "conjunction_covered": True, "qualifiers": {}, "numbers_years": {},
      "evidence_quote": "火星上的那個人…真的是「你」嗎"}),
]


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def build_prompt_v2(claim_text: str, evidence: dict,
                    qualifier_list: list[str], number_list: list[str]) -> tuple[str, str]:
    lines = []
    for claim, ev, fields in FEW_SHOT_V2:
        lines.append(f"Claim: {claim}\nEvidence: {ev}\nJSON: {json.dumps(fields, ensure_ascii=False)}\n")
    system = SYSTEM_PROMPT + ("\n\n示例：\n" + "\n".join(lines) if lines else "")
    title = (evidence.get("title") or "")[:200]
    snippet = (evidence.get("snippet") or "")[:300]
    text = (evidence.get("text") or "")[:600]
    user = (f"Claim: {claim_text}\n"
            f"Evidence 标题: {title}\nEvidence 摘要: {snippet}\nEvidence 正文窗口: {text}\n"
            f"Evidence URL: {(evidence.get('url') or '')[:200]}\n"
            f"限定词清单（对每项给 true/false）: {qualifier_list or '[]'}\n"
            f"数字/年份清单（对每项给 true/false）: {number_list or '[]'}")
    return system, user


def cache_key_v2(claim_text: str, evidence: dict, model: str = MODEL_DEFAULT) -> str:
    raw = "\x00".join([_norm(claim_text), _norm(evidence.get("title", "")),
                       _norm(evidence.get("snippet", "")),
                       _norm((evidence.get("text") or "")[:600]),
                       PROMPT_VERSION, model])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _contrast_construction(text: str) -> bool:
    return ("不是" in text) and (("而是" in text) or
                                 bool(re.search(r"不是.{1,15}[，,]?是", text)))


# ③ 细化后的规则层句式裁决（通用规范，非样本特例）
NARRATIVE_MARKERS = ("这一步", "经常", "往往", "一笔带过", "后面就", "先说", "再说",
                     "接下来", "收拢", "退一步说", "回到最初", "拉近一点", "三步走")


def rule_claim_type(claim_text: str) -> str | None:
    prof = _claim_profile(claim_text)
    if prof["question"]:
        return "QUESTION"
    if prof["step_def"]:
        return "DEFINITION"          # 仅第X步定义句封死 DIRECT
    if _contrast_construction(claim_text):
        return "CONTRAST"
    if prof["rhetorical"]:
        return "RHETORICAL"
    if prof["fiction"] and any(m in claim_text for m in NARRATIVE_MARKERS):
        return "NARRATIVE"           # 影视事实句（仅含"故事/电影"而无过渡语）不再自动 NARRATIVE
    return None                       # gloss 定义（指/指的是）不在此封死


def _extract_json(text: str) -> dict:
    text = (text or "").strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        text = text[start:end + 1]
    data = json.loads(text)
    if not isinstance(data, dict):
        raise SchemaError("LLM 输出顶层应为对象")
    return data


# ---------------- ② 确定性证据复核（规则层，原文验证） ----------------
# 注：semantic_judge 的数字解析器对"八百六十亿"类组合数存在十位进位缺陷且该模块冻结，
#     故 Stage 6 在本地实现修正版中文数字解析，仅用于本模块的确定性复核与键集注入。
def _parse_cn_num_corrected(s: str) -> float:
    section, num = 0.0, 0.0
    for ch in s:
        if ch in "零一二三四五六七八九":
            num = "零一二三四五六七八九".index(ch)
        elif ch == "两":
            num = 2
        elif ch == "十":
            section += (num if num else 1) * 10
            num = 0
        elif ch == "百":
            section += (num if num else 1) * 100
            num = 0
        elif ch == "千":
            section += (num if num else 1) * 1000
            num = 0
        elif ch == "万":
            section = (section + num) * 1e4
            num = 0
        elif ch == "亿":
            section = (section + num) * 1e8
            num = 0
    return section + num


_UNIT_MULT = {"万亿": 1e12, "亿": 1e8, "万": 1e4, "千": 1e3, "百": 1e2}
_CN_DIGITS = "零一二三四五六七八九十百千万两"
_CN_NUM_RE = re.compile(r"[零一二三四五六七八九十百千万两]+(?:[万亿千百])?(?:个|条|例|次|年|瓦|倍)?")


def _extract_numbers_corrected(text: str) -> list[tuple[float, str, str]]:
    out = []
    # 阿拉伯数字：支持千分位（139,255 / 5,000万 / 86,000,000,000）不拆分
    for m in re.finditer(r"(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)\s*(万亿|亿|万|千|百)?", text):
        unit = m.group(2) or ""
        val = float(m.group(1).replace(",", "")) * _UNIT_MULT.get(unit, 1.0)
        out.append((val, unit, m.group(0)))
    for m in _CN_NUM_RE.finditer(text):
        raw = m.group(0)
        if m.start() > 0 and text[m.start() - 1] == "数":
            continue
        body = re.sub(r"(个|条|例|次|年|瓦|倍)$", "", raw)
        if re.fullmatch(r"[十百千万亿]", body):
            continue                       # 十几年/几十年/数百 类近似数，不产出精确数字
        unit_m = re.search(r"([万亿千百])$", body)
        unit = unit_m.group(1) if unit_m else ""
        body2 = body[:-1] if unit else body
        if any(c in _CN_DIGITS for c in body2) and any(c in "十百千万亿" for c in body2):
            out.append((_parse_cn_num_corrected(body2) * _UNIT_MULT.get(unit, 1.0), unit, raw))
    return out


def _num_present_in_evidence(raw: str, ev_norm: str) -> bool:
    """Claim 数字/年份在 Evidence 原文（繁简归一后）中的确定性存在性验证（值+单位）。"""
    if re.fullmatch(r"(19|20)\d{2}", raw):
        return raw in ev_norm
    cn = _extract_numbers_corrected(raw)
    en = _extract_numbers_corrected(ev_norm)
    for cv, cu, _ in cn:
        for evv, eu, _ in en:
            if cu == eu and abs(cv - evv) < 1e-6:
                return True
    return False


def _qualifier_present_in_evidence(q: str, ev_norm: str) -> bool:
    """限定词在 Evidence 原文中的确定性存在性验证（含同义形）。"""
    from .semantic_judge import QUALIFIER_SYN
    forms = QUALIFIER_SYN.get(q, {q}) | {q}
    return any(f in ev_norm for f in forms)


def _decide_v6(claim_text: str, evidence: dict, rule_label: str, llm: dict,
               flags: dict) -> dict:
    """确定性决策层（flags 用于 dev 消融，生产默认全开）。"""
    prof = _claim_profile(claim_text)
    ev_plain = evidence.get("title", "") + evidence.get("snippet", "") + evidence.get("text", "")
    ev_norm = t2s(ev_plain) if flags.get("t2s") else ev_plain
    claim_norm = t2s(claim_text) if flags.get("t2s") else claim_text
    ev_text = evidence.get("text", "") or ev_plain
    ev_text_norm = t2s(ev_text) if flags.get("t2s") else ev_text
    matched, num_conflict = _matched_core(prof, {k: v for k, v in evidence.items()})
    neg_rule = _scoped_negation(ev_text_norm, matched, prof["feasible"])
    overlap = len(matched) + _generic_overlap(claim_norm, ev_norm)

    ct = rule_claim_type(claim_text) or llm.get("claim_type") or "ASSERTION"
    rel = llm.get("relevance")
    cand = bool(llm.get("contradiction_candidate"))

    checks = {"s1": ct == "ASSERTION", "s2": False, "s3": False, "s4": False,
              "s5": False, "s6": True, "s7": True, "claim_type": ct,
              "negation_dual": False, "negation_rule_signal": bool(neg_rule)}

    if rel == "IRRELEVANT":
        return {**checks, "level": "IRRELEVANT", "reason": "LLM 判定无关"}
    if rel == "CONTEXT_ONLY":
        if overlap == 0:
            return {**checks, "level": "IRRELEVANT", "reason": "词面零重叠，保守判无关"}
        return {**checks, "level": "CONTEXT_ONLY", "reason": "仅词面出现，不构成讨论"}

    # ① CONTRADICTS 与支持清单解耦：LLM 单信号 + ASSERTION 资格 + 主体/对象一致；
    #    规则辖域仅作审计信号（checks["negation_rule_signal"]），不作硬门槛。
    if flags.get("decouple_contradict", True):
        contradiction = (cand and ct == "ASSERTION"
                         and bool(llm.get("subject_match")) and bool(llm.get("object_match")))
        if contradiction:
            return {**checks, "level": "CONTRADICTS",
                    "reason": f"独立反驳信号确认（规则辖域审计信号={int(neg_rule)}）"}

    if ct != "ASSERTION":
        return {**checks, "level": "PARTIAL_SUPPORT", "reason": f"句式类型 {ct} 不得升级 DIRECT"}

    s2 = bool(llm.get("subject_match")) and bool(llm.get("object_match"))
    s3 = bool(llm.get("predicate_match"))

    # ② S4/S5 确定性证据复核（原文存在性；LLM 打分仅作审计）
    reqs = _qualifier_requirements(claim_norm)
    if flags.get("verify_s4s5", True):
        s4 = all(_qualifier_present_in_evidence(q, ev_norm) for q in reqs) if reqs else True
        cn = _extract_numbers_corrected(claim_norm)
        claim_nums = [raw for _, _, raw in cn] + re.findall(r"(19|20)\d{2}", claim_norm)
        s5 = (not num_conflict) and all(_num_present_in_evidence(raw, ev_norm)
                                        for raw in claim_nums)
    else:
        qual_map = llm.get("qualifiers") or {}
        s4 = all(any((q == k or q in k or k in q) and bool(qual_map[k]) for k in qual_map)
                 for q in reqs) if reqs else True
        num_map = llm.get("numbers_years") or {}
        cn = _extract_numbers_corrected(claim_norm)
        claim_nums = [raw for _, _, raw in cn] + re.findall(r"(19|20)\d{2}", claim_norm)
        s5 = (not num_conflict) and all(
            any((raw in k or k in raw) and bool(num_map[k]) for k in num_map if raw in k or k in raw)
            for raw in claim_nums)

    s6 = not cand
    s7 = bool(llm.get("conjunction_covered", True))
    checks.update({"s2": s2, "s3": s3, "s4": s4, "s5": s5, "s6": s6, "s7": s7})
    if s2 and s3 and s4 and s5 and s6 and s7:
        return {**checks, "level": "DIRECT_SUPPORT", "reason": "S1–S7 全部通过"}
    failed = [k for k in ("s2", "s3", "s4", "s5", "s6", "s7") if not checks[k]]
    return {**checks, "level": "PARTIAL_SUPPORT", "reason": f"清单未通过: {failed}"}


# 生产默认 flags（全部开启）；dev 消融只由评估脚本以同参数调用 _decide_v6，不改此处
DEFAULT_FLAGS = {"decouple_contradict": True, "verify_s4s5": True,
                 "refined_types": True, "t2s": True}


def judge_v2(claim_text: str, evidence: dict, router, rule_label: str,
             cache_db=None, l1_cache: dict | None = None) -> dict:
    """两级判定入口。任何失败回退 rule_label，绝不抛出。"""
    key = cache_key_v2(claim_text, evidence)
    base = {"cache_key": key, "rule_label": rule_label, "model": MODEL_DEFAULT,
            "prompt_version": PROMPT_VERSION, "fallback_reason": "",
            "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0, "latency_ms": 0,
            "cache_hit": False, "checklist": None, "llm_relevance": None,
            "claim_type": None, "reason": ""}

    def cached(row: dict) -> dict:
        return {**base, "cache_hit": True, "support_level": row.get("llm_label") or rule_label,
                "reason": row.get("reason") or "", "model": row.get("model") or MODEL_DEFAULT,
                "fallback_reason": row.get("fallback_reason") or ""}

    if l1_cache is not None and key in l1_cache:
        return cached(l1_cache[key])
    if cache_db is not None:
        row = cache_db.get_llm_judge_row(key)
        if row:
            if l1_cache is not None:
                l1_cache[key] = row
            return cached(row)

    client = getattr(router, "client", None)
    tier_cfg = (router.config.get("tiers", {}) or {}).get(TIER, {})
    model = tier_cfg.get("model", MODEL_DEFAULT)

    def fallback(reason: str) -> dict:
        out = {**base, "support_level": rule_label, "llm_label": rule_label,
               "reason": f"回退规则判定：{reason}", "fallback_reason": reason, "model": model}
        if cache_db is not None:
            cache_db.put_llm_judge_row({**out, "llm_label": rule_label})
        if l1_cache is not None:
            l1_cache[key] = {**out, "llm_label": rule_label}
        return out

    if client is None or not getattr(client, "available", True):
        return fallback("LLM 未配置")

    # ② 规则层提取键集注入 prompt
    qualifier_list = _qualifier_requirements(t2s(claim_text))
    cn = _extract_numbers_corrected(t2s(claim_text))
    number_list = [raw for _, _, raw in cn] + re.findall(r"(19|20)\d{2}", t2s(claim_text))
    system, user = build_prompt_v2(claim_text, evidence, qualifier_list, number_list)
    max_tokens = tier_cfg.get("max_tokens", 512)

    last_error = ""
    llm = None
    for attempt in (1, 2):
        t0 = time.perf_counter()
        try:
            result = client.complete(model, system, user, max_tokens)
            cost_usd = 0.0
            if hasattr(router, "account_direct_call"):     # 3.x Phase 1.1：直连调用也记账
                cost_usd = router.account_direct_call(model, result, tag="judge:sufficiency")[0]
            data = _extract_json(result.get("text", ""))
            validate_json(data, OUTPUT_SCHEMA)
            llm = data
            base.update({"latency_ms": int((time.perf_counter() - t0) * 1000),
                         "tokens_in": int(result.get("prompt_tokens", 0) or 0),
                         "tokens_out": max(int(result.get("tokens", 0) or 0)
                                           - int(result.get("prompt_tokens", 0) or 0), 0),
                         "cost_usd": cost_usd})
            break
        except SchemaError as exc:
            last_error = f"解析/校验失败({attempt}): {exc}"
            continue
        except Exception as exc:
            last_error = f"调用失败({attempt}): {type(exc).__name__}"
            continue
    if llm is None:
        return fallback(last_error or "LLM 失败")

    decision = _decide_v6(claim_text, evidence, rule_label, llm, DEFAULT_FLAGS)
    out = {**base, "support_level": decision["level"], "llm_label": decision["level"],
           "reason": decision["reason"], "model": model,
           "checklist": {k: v for k, v in decision.items() if k != "reason"},
           "llm_relevance": llm.get("relevance"), "claim_type": decision.get("claim_type")}
    if cache_db is not None:
        cache_db.put_llm_judge_row(out)
    if l1_cache is not None:
        l1_cache[key] = out
    return out
