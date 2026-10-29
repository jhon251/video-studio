"""V2.1 阶段 4：LLM Semantic Judge —— Rule Filter 之后的第二层语义判定（独立模块）。

- 输入：Claim 文本 + 单条 Evidence（title/snippet/text 窗口）；
- 输出：仅五类 support_level + 一句理由（JSON，Schema 校验 + 枚举白名单）；
- 不输出、不决定任何核查结论（Confirmed/Mostly/Disputed/Unsupported/False）；
- 双轨审计：rule_label / llm_label / model / prompt_version / fallback_reason 全部记录；
- 降级：LLM 未配置、调用失败、超时、限流、解析失败 → 回退规则层标签，绝不阻塞管线；
- 缓存：L1 内存 dict + L2 SQLite 表 llm_judge_cache（键含 PROMPT_VERSION 与 MODEL）；
- 本阶段未接入 fact_check 调用链（实现与验证隔离），仅由评估驱动脚本调用。

复用现有 Router/客户端通道（无新增网络依赖）：client 经 Router 构造；未配置密钥时
client.available=False → 直接回退规则层（行为=现状）。
"""

from __future__ import annotations

import hashlib
import json
import re
import time

from ..llm.router import SchemaError, validate_json

PROMPT_VERSION = "llm-semantic-judge-v1"
MODEL_DEFAULT = "deepseek-chat"
TIER = "F"

LEVELS = ("DIRECT_SUPPORT", "PARTIAL_SUPPORT", "CONTEXT_ONLY", "IRRELEVANT", "CONTRADICTS")

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "support_level": {"type": "string", "enum": list(LEVELS)},
        "reason": {"type": "string"},
    },
    "required": ["support_level", "reason"],
}

SYSTEM_PROMPT = (
    "你是事实核查系统中的语义判定模块。给定一条 Claim（待核查陈述）和一条 Evidence（网页证据，"
    "含标题/摘要/正文窗口），判断该 Evidence 对 Claim 的支持关系。\n\n"
    "支持关系五类定义（严格遵守）：\n"
    "1. DIRECT_SUPPORT：Evidence 完整背书 Claim 的主体、谓词、对象及关键限定词"
    "（第一/最大/唯一/首次/目前、约/大约、基本共识、数字/年份/机构名）；"
    "任何关键限定词缺失、数字不一致，都不得判 DIRECT_SUPPORT。\n"
    "2. PARTIAL_SUPPORT：Evidence 背书部分要素（主体相关但数字/限定词不一致或缺失、"
    "同主题讨论、相邻领域、问句/定义句 Claim 的主题相关证据）。\n"
    "3. CONTEXT_ONLY：仅个别词面出现，不构成对命题的讨论，不得参与结论计算。\n"
    "4. IRRELEVANT：与命题无主题关系，含关键词高度重叠但同形异义/不同对象的情况。\n"
    "5. CONTRADICTS：仅当 Evidence 对可验证断言命题构成真实否定。\n\n"
    "硬性规则：\n"
    "- 关键词重叠 ≠ 语义支持；同一主题 ≠ 支持该 Claim；官方来源 ≠ 自动相关。\n"
    "- 问句/反问句、定义句、影视叙事句不可被反驳（不要判 CONTRADICTS）。\n"
    "- \"不是A而是B\"、\"不是A是B\" 是对照构式，不是否定命题；"
    "Claim 或 Evidence 中的这类句子不构成反驳。\n"
    "- 否定词必须落在同一命题的谓词辖域内才可判 CONTRADICTS；"
    "否定对象不同（如否定另一件事）不算反驳。\n"
    "- 无关 Evidence 绝不判 DIRECT_SUPPORT 或 CONTRADICTS。\n"
    "- Evidence 缺失 Claim 关键数字/年份/机构/限定词时，最多 PARTIAL_SUPPORT。\n\n"
    "只输出 JSON，格式：{\"support_level\": \"五类之一\", \"reason\": \"一句中文理由(≤60字)\"}。"
)

# few-shot 示例全部取自 50 样本回归集真实文本（禁止使用盲测集与 CONTRADICTS 压力集文本）
FEW_SHOT = [
    ("Claim: 算力、能耗、散热，每一项都是钱",
     "Evidence: 经济日报：数据中心运行成本的六成是电费，电费里的四成多来自冷却散热。",
     "DIRECT_SUPPORT", "证据直接支撑算力/能耗/散热均为成本项，主体与谓词完整背书"),
    ("Claim: 人脑大约八百六十亿个神经元，突触按百万亿算",
     "Evidence: 清华稿件：人类大脑约有1000亿个神经元，100万亿个突触。",
     "PARTIAL_SUPPORT", "主体相关且同量级，但数字不完全一致，仅部分背书"),
    ("Claim: 三百个神经元尚且如此",
     "Evidence: CIRM 页面：尼古丁浓度减弱多巴胺能神经元中的蛋白质反应。",
     "CONTEXT_ONLY", "仅共享\"神经元\"词面，未讨论三百神经元线虫命题"),
    ("Claim: 假如有一天副本上线，对你说'我就是你'——你会觉得，自己永生了吗",
     "Evidence: IRS 税务誊本页面：申请报税表副本、纳税人身份信息。",
     "IRRELEVANT", "\"副本\"同形异义（税务文件副本≠数字副本），无主题关系"),
    ("Claim: 现阶段的虚拟数字果蝇已经拥有思想和意识",
     "Evidence: 科技日报：只有当虚拟模型拥有思想和意识才算数字生命，现阶段的成果还远未达到这一水平。",
     "CONTRADICTS", "证据对命题主体与谓词构成直接否定"),
    ("Claim: 从果蝇到人，差多远",
     "Evidence: 中科院神经所：果蝇大脑约12.5万个神经元，人脑约860亿个。",
     "PARTIAL_SUPPORT", "问句不可反驳；证据提供背景数字，部分支撑"),
    ("Claim: 注意，这三步的难度不在一个量级，而'永生'这个词，把三步打包卖成了一个产品",
     "Evidence: 人人都是产品经理：企业服务产品生命周期与PMF方法论。",
     "IRRELEVANT", "\"产品\"一词同形异义，页面主题为企业服务，与命题无关"),
    ("Claim: 第三步，转移：让'你'本人住进去",
     "Evidence: 北京住房公积金转移指南：第一步登录、第二步申请、第三步查询进度。",
     "IRRELEVANT", "\"第三步/转移\"为政务办事术语，与意识转移命题同形异义"),
]


def build_prompt(claim_text: str, evidence: dict) -> tuple[str, str]:
    """构造 system / user 提示词。evidence: {title, snippet, text, url}。"""
    lines = []
    for claim, ev, label, reason in FEW_SHOT:
        lines.append(f"Claim: {claim}\nEvidence: {ev}\n判定: {label}\n理由: {reason}\n")
    system = SYSTEM_PROMPT + "\n\n示例（来自真实核查样本）：\n" + "\n".join(lines)
    title = (evidence.get("title") or "")[:200]
    snippet = (evidence.get("snippet") or "")[:300]
    text = (evidence.get("text") or "")[:600]
    user = (f"Claim: {claim_text}\n"
            f"Evidence 标题: {title}\n"
            f"Evidence 摘要: {snippet}\n"
            f"Evidence 正文窗口: {text}\n"
            f"Evidence URL: {(evidence.get('url') or '')[:200]}")
    return system, user


def cache_key(claim_text: str, evidence: dict, model: str = MODEL_DEFAULT) -> str:
    def norm(s: str) -> str:
        return re.sub(r"\s+", "", s or "")

    raw = "\x00".join([norm(claim_text), norm(evidence.get("title", "")),
                       norm(evidence.get("snippet", "")),
                       norm((evidence.get("text") or "")[:600]),
                       PROMPT_VERSION, model])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


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


def judge_llm(claim_text: str, evidence: dict, router, rule_label: str,
              cache_db=None, l1_cache: dict | None = None) -> dict:
    """第二层判定。返回 {support_level, reason, rule_label, llm_label, model,
    prompt_version, fallback_reason, tokens_in, tokens_out, cost_usd, latency_ms,
    cache_hit, cache_key}。任何失败回退 rule_label，绝不抛出。"""
    key = cache_key(claim_text, evidence)
    base = {
        "cache_key": key,
        "rule_label": rule_label,
        "model": MODEL_DEFAULT,
        "prompt_version": PROMPT_VERSION,
        "fallback_reason": "",
        "tokens_in": 0,
        "tokens_out": 0,
        "cost_usd": 0.0,
        "latency_ms": 0,
        "cache_hit": False,
    }

    def cached(row: dict) -> dict:
        out = {**base, "cache_hit": True}
        out["llm_label"] = row.get("llm_label") or rule_label
        out["support_level"] = out["llm_label"]
        out["reason"] = row.get("reason") or ""
        out["model"] = row.get("model") or MODEL_DEFAULT
        out["fallback_reason"] = row.get("fallback_reason") or ""
        return out

    # L1 / L2 缓存
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
               "reason": f"回退规则判定：{reason}", "fallback_reason": reason,
               "model": model}
        if cache_db is not None:
            cache_db.put_llm_judge_row(out)
        if l1_cache is not None:
            l1_cache[key] = out
        return out

    if client is None or not getattr(client, "available", True):
        return fallback("LLM 未配置")

    system, user = build_prompt(claim_text, evidence)
    max_tokens = tier_cfg.get("max_tokens", 256)

    last_error = ""
    for attempt in (1, 2):
        t0 = time.perf_counter()
        try:
            result = client.complete(model, system, user, max_tokens)
            cost_usd = 0.0
            if hasattr(router, "account_direct_call"):     # 3.x Phase 1.1：直连调用也记账
                cost_usd = router.account_direct_call(model, result, tag="judge:semantic")[0]
            data = _extract_json(result.get("text", ""))
            validate_json(data, OUTPUT_SCHEMA)
            if data["support_level"] not in LEVELS:
                raise SchemaError("support_level 不在五类枚举中")
            reason = str(data.get("reason") or "")[:120]
            latency_ms = int((time.perf_counter() - t0) * 1000)
            tokens_total = int(result.get("tokens", 0) or 0)
            tokens_in = int(result.get("prompt_tokens", 0) or 0)
            out = {**base,
                   "support_level": data["support_level"],
                   "llm_label": data["support_level"],
                   "reason": reason,
                   "model": model,
                   "tokens_in": tokens_in,
                   "tokens_out": max(tokens_total - tokens_in, 0),
                   "cost_usd": cost_usd,
                   "latency_ms": latency_ms}
            if cache_db is not None:
                cache_db.put_llm_judge_row(out)
            if l1_cache is not None:
                l1_cache[key] = out
            return out
        except SchemaError as exc:
            last_error = f"解析/校验失败({attempt}): {exc}"
            continue
        except Exception as exc:  # 超时/限流/连接错误等
            last_error = f"调用失败({attempt}): {type(exc).__name__}"
            continue
    return fallback(last_error or "LLM 失败")
