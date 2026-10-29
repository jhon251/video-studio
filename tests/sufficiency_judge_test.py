"""V2.1 Stage 6：Support Sufficiency 判定管道测试（MockLLM）。

覆盖：S1–S7 确定性清单、①反驳解耦（LLM 单信号+ASSERTION 资格，规则辖域仅审计）、
②S4/S5 原文存在性复核（LLM 自报不可绕过）、③claim_type 细化（影视事实句/gloss 定义
可 DIRECT；过渡叙事句/问句/第X步定义/对照构式不可）、④繁简归一、缓存/回退。
不调用真实 LLM；不修改任何冻结集；不接生产链。
"""

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from video_studio.db.schema import Database  # noqa: E402
from video_studio.llm.router import MockLLM, Router  # noqa: E402
from video_studio.tools.sufficiency_judge import judge_v2  # noqa: E402

CONFIG = {"llm": {"tiers": {"F": {"model": "deepseek-chat", "max_tokens": 512, "budget_usd": 0.05}}}}

FULL_TRUE = {"relevance": "RELEVANT", "claim_type": "ASSERTION",
             "contradiction_candidate": False, "subject_match": True, "object_match": True,
             "predicate_match": True, "conjunction_covered": True,
             "qualifiers": {}, "numbers_years": {}, "evidence_quote": "证据完整背书"}


class CountingMock(MockLLM):
    def __init__(self, responses, default=None):
        super().__init__(responses, default or {})
        self.calls = 0

    def complete(self, model, system, user, max_tokens):
        self.calls += 1
        return super().complete(model, system, user, max_tokens)


def router_for(responses, default=None):
    return Router(CONFIG["llm"], CountingMock(responses, default))


def main() -> int:
    checks = []

    def check(name, cond, detail=""):
        checks.append((name, cond))
        print(f"{'PASS' if cond else 'FAIL'}  {name} {detail}")

    ws = Path(tempfile.mkdtemp(prefix="vs_s6_"))
    db = Database(ws / "state.db")
    ev = {"title": "T", "snippet": "S", "text": "正文", "url": "https://e.com/1"}

    # T1 S1–S7 全过 → DIRECT
    r = judge_v2("某公司发布了某产品", ev, router_for({"某公司发布了某产品": FULL_TRUE}),
                 "PARTIAL_SUPPORT", cache_db=db)
    check("S1–S7 全过 → DIRECT", r["support_level"] == "DIRECT_SUPPORT"
          and all(r["checklist"][k] for k in ("s1", "s2", "s3", "s4", "s5", "s6", "s7")))

    # T2 问句 → 永不 DIRECT
    r2 = judge_v2("人能永生吗？某公司发布了产品吗", ev,
                  router_for({"某公司发布了产品吗": {**FULL_TRUE, "claim_type": "ASSERTION"}}),
                  "PARTIAL_SUPPORT", cache_db=db)
    check("问句 → 永不 DIRECT", r2["support_level"] == "PARTIAL_SUPPORT"
          and r2["claim_type"] == "QUESTION")

    # T3 第X步定义句 → 永不 DIRECT
    r3 = judge_v2("第一步，扫描：把大脑的结构完整读出来", ev,
                  router_for({"把大脑的结构": {**FULL_TRUE, "claim_type": "ASSERTION"}}),
                  "PARTIAL_SUPPORT", cache_db=db)
    check("第X步定义句 → 永不 DIRECT", r3["support_level"] == "PARTIAL_SUPPORT"
          and r3["claim_type"] == "DEFINITION")

    # T4 对照构式 → 永不 DIRECT
    r4 = judge_v2("记忆不是文件，而是每次回忆时重新组装出来的", ev,
                  router_for({"记忆不是文件": {**FULL_TRUE, "claim_type": "ASSERTION"}}),
                  "PARTIAL_SUPPORT", cache_db=db)
    check("'不是A而是B' → 永不 DIRECT", r4["support_level"] == "PARTIAL_SUPPORT"
          and r4["claim_type"] == "CONTRAST")

    # T5 ①反驳解耦：LLM 单信号（无规则辖域否定）→ CONTRADICTS；规则辖域仅审计
    r5 = judge_v2("现阶段的虚拟数字果蝇已经拥有思想和意识",
                  {"title": "T", "snippet": "S", "text": "现阶段的成果还远未达到这一水平。",
                   "url": "https://e.com/2"},
                  router_for({"数字果蝇已经拥有": {**FULL_TRUE, "contradiction_candidate": True}}),
                  "PARTIAL_SUPPORT", cache_db=db)
    check("①反驳解耦：LLM 单信号 → CONTRADICTS（规则辖域不设门槛）",
          r5["support_level"] == "CONTRADICTS"
          and "negation_rule_signal" in r5["checklist"])

    # T5b 问句 + 反驳候选 → 不判 CONTRADICTS（资格限制）
    r5b = judge_v2("数字果蝇已经拥有思想和意识吗",
                   {"title": "T", "snippet": "S", "text": "现阶段的成果还远未达到这一水平。",
                    "url": "https://e.com/2b"},
                   router_for({"数字果蝇已经拥有": {**FULL_TRUE, "contradiction_candidate": True}}),
                   "PARTIAL_SUPPORT", cache_db=db)
    check("①反驳资格：问句即使有反驳候选也不判 CONTRADICTS",
          r5b["support_level"] != "CONTRADICTS")

    # T7 限定词未背书 → 最多 PARTIAL（②确定性：LLM 自报 true 不可绕过）
    r7 = judge_v2("2025年，中国团队放出了目前最大的小鼠全脑图谱",
                  ev, router_for({"目前最大的小鼠": {**FULL_TRUE,
                    "qualifiers": {"目前": True, "最大": True},
                    "numbers_years": {"2025": True}}}), "PARTIAL_SUPPORT", cache_db=db)
    check("②限定词原文缺失 → 确定性复核拦下，LLM 自报不可绕过",
          r7["support_level"] == "PARTIAL_SUPPORT" and r7["checklist"]["s4"] is False)

    # T8 数字缺失 → 最多 PARTIAL
    r8 = judge_v2("人脑大约860亿个神经元", ev,
                  router_for({"860亿个神经元": {**FULL_TRUE, "numbers_years": {"860亿": True}}}),
                  "PARTIAL_SUPPORT", cache_db=db)
    check("②数字原文缺失 → 确定性复核拦下", r8["support_level"] == "PARTIAL_SUPPORT"
          and r8["checklist"]["s5"] is False)

    # T9 CONTEXT_ONLY + 零重叠 → IRRELEVANT
    r9 = judge_v2("某机构完成首例人体植入", ev,
                  router_for({"首例人体植入": {**FULL_TRUE, "relevance": "CONTEXT_ONLY"}}),
                  "IRRELEVANT", cache_db=db)
    check("CONTEXT_ONLY 且零重叠 → 保守判 IRRELEVANT", r9["support_level"] == "IRRELEVANT")

    # T12 ③gloss 定义断言可 DIRECT（不再被"定义"封死）
    r12 = judge_v2("'意识上传'指将人的大脑活动全面扫描并数字化",
                   ev, router_for({"意识上传": FULL_TRUE}), "PARTIAL_SUPPORT", cache_db=db)
    check("③gloss 定义断言（指…）不封死 DIRECT", r12["support_level"] == "DIRECT_SUPPORT")

    # T13 ③影视事实句（含"故事"但无过渡语）不自动 NARRATIVE → 可 DIRECT
    r13 = judge_v2("《刀剑神域》的Underworld也是一个把人脑塞进机器的故事",
                   ev, router_for({"把人脑塞进机器": FULL_TRUE}), "PARTIAL_SUPPORT", cache_db=db)
    check("③影视事实句不自动 NARRATIVE", r13["support_level"] == "DIRECT_SUPPORT")

    # T14 ③过渡叙事句 → NARRATIVE 帽子生效
    r14 = judge_v2("影视作品里，这一步经常一笔带过：扫描，上传，永生",
                   ev, router_for({"一笔带过": FULL_TRUE}), "PARTIAL_SUPPORT", cache_db=db)
    check("③过渡叙事句 → NARRATIVE 永不 DIRECT", r14["support_level"] == "PARTIAL_SUPPORT"
          and r14["claim_type"] == "NARRATIVE")

    # T15 ④繁简归一：繁体证据中的数字/限定词可被确定性复核命中
    r15 = judge_v2("人脑大约八百六十亿个神经元",
                   {"title": "要論能效還看大腦", "snippet": "人類大腦約有860億個神經元",
                    "text": "人類大腦約有860億個神經元", "url": "https://e.com/3"},
                   router_for({"八百六十亿": {**FULL_TRUE,
                     "numbers_years": {"八百六十亿": True}}}), "PARTIAL_SUPPORT", cache_db=db)
    check("④繁简归一：繁体证据数字被确定性复核命中 → DIRECT",
          r15["support_level"] == "DIRECT_SUPPORT")

    # T10 解析失败 → 回退规则层
    mock_bad = CountingMock({"某公司于2023年": "not json"})
    r10 = judge_v2("某公司于2023年发布了产品", ev, Router(CONFIG["llm"], mock_bad),
                   "CONTEXT_ONLY", cache_db=db)
    check("解析失败重试后回退规则层", mock_bad.calls == 2
          and r10["support_level"] == "CONTEXT_ONLY" and "解析" in r10["fallback_reason"])

    # T11 缓存命中
    mock11 = CountingMock({"某企业推出了某产品": FULL_TRUE})
    rt = Router(CONFIG["llm"], mock11)
    l1: dict = {}
    a = judge_v2("某企业推出了某产品", ev, rt, "PARTIAL_SUPPORT", cache_db=db, l1_cache=l1)
    b = judge_v2("某企业推出了某产品", ev, rt, "PARTIAL_SUPPORT", cache_db=db, l1_cache=l1)
    check("缓存命中且不再调用", a["support_level"] == "DIRECT_SUPPORT"
          and b["cache_hit"] is True and mock11.calls == 1)

    db.close()
    failed = [c for c in checks if not c[1]]
    print(f"\n结果: {len(checks) - len(failed)}/{len(checks)} 通过")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
