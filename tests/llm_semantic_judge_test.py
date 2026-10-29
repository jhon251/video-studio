"""V2.1 阶段 4：LLM Semantic Judge 管道测试（MockLLM，验证机制而非判定质量）。

覆盖：prompt 构造 / JSON 解析 / 枚举校验 / 重试与回退 / 缓存两级命中 / 审计字段 /
未配置降级 / 异常降级 / 缓存键稳定性。不接入生产链。
"""

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from video_studio.db.schema import Database  # noqa: E402
from video_studio.llm.router import MockLLM, Router  # noqa: E402
from video_studio.tools.llm_semantic_judge import (  # noqa: E402
    build_prompt, cache_key, judge_llm)

CONFIG = {"llm": {"tiers": {"F": {"model": "deepseek-chat", "max_tokens": 256, "budget_usd": 0.05}}}}
CLAIM = "人脑大约八百六十亿个神经元，突触按百万亿算"
EVIDENCE = {"title": "要论能效，还看大脑", "snippet": "人类大脑约有1000亿个神经元",
            "text": "人类大脑在25瓦的极低能耗下运行。", "url": "https://example.com/a"}


class CountingMock(MockLLM):
    def __init__(self, responses, default):
        super().__init__(responses, default)
        self.calls = 0

    def complete(self, model, system, user, max_tokens):
        self.calls += 1
        return super().complete(model, system, user, max_tokens)


class UnavailableMock:
    available = False
    calls = 0

    def complete(self, *a, **k):
        self.calls += 1
        raise AssertionError("不应被调用")


class BoomMock:
    available = True
    calls = 0

    def complete(self, *a, **k):
        self.calls += 1
        raise TimeoutError("boom")


def make_router(client):
    return Router(CONFIG["llm"], client)


def main() -> int:
    checks = []

    def check(name, cond, detail=""):
        checks.append((name, cond))
        print(f"{'PASS' if cond else 'FAIL'}  {name} {detail}")

    ws = Path(tempfile.mkdtemp(prefix="vs_llmj_"))
    db = Database(ws / "state.db")

    # ---------- prompt 构造 ----------
    system, user = build_prompt(CLAIM, EVIDENCE)
    check("system 含五类定义与硬性规则",
          all(x in system for x in ("DIRECT_SUPPORT", "CONTRADICTS", "同形异义", "不是A而是B")))
    check("user 含 Claim 与 Evidence 字段",
          CLAIM in user and "要论能效" in user and "https://example.com/a" in user)
    check("few-shot 示例数 = 8", system.count("判定: ") == 8)

    # ---------- 正常路径 + 缓存 ----------
    mock = CountingMock({CLAIM: {"support_level": "DIRECT_SUPPORT", "reason": "证据完整背书"}}, {})
    router = make_router(mock)
    l1: dict = {}
    r1 = judge_llm(CLAIM, EVIDENCE, router, "PARTIAL_SUPPORT", cache_db=db, l1_cache=l1)
    check("正常路径返回 LLM 标签", r1["support_level"] == "DIRECT_SUPPORT"
          and r1["llm_label"] == "DIRECT_SUPPORT" and r1["rule_label"] == "PARTIAL_SUPPORT")
    check("正常路径无回退且记录 tokens", r1["fallback_reason"] == "" and r1["tokens_in"] > 0)
    check("正常路径审计字段齐全", r1["model"] == "deepseek-chat"
          and r1["prompt_version"] and r1["reason"] == "证据完整背书")
    check("正常路径调用 1 次", mock.calls == 1)
    r2 = judge_llm(CLAIM, EVIDENCE, router, "PARTIAL_SUPPORT", cache_db=db, l1_cache=l1)
    check("L1 缓存命中且不再调用", r2["cache_hit"] is True and mock.calls == 1)
    row = db.get_llm_judge_row(cache_key(CLAIM, EVIDENCE))
    check("L2 审计行落盘（rule/llm/model/prompt_version 双轨）",
          row and row["rule_label"] == "PARTIAL_SUPPORT"
          and row["llm_label"] == "DIRECT_SUPPORT" and row["model"] == "deepseek-chat"
          and row["prompt_version"] and row["fallback_reason"] == "")

    # L2 命中（新 L1）
    r3 = judge_llm(CLAIM, EVIDENCE, router, "PARTIAL_SUPPORT", cache_db=db, l1_cache={})
    check("L2 持久缓存命中", r3["cache_hit"] is True and mock.calls == 1)

    # ---------- 解析失败 → 重试 → 回退规则层 ----------
    c_bad = CLAIM + " 场景-解析失败"
    mock_bad = CountingMock({c_bad: "这不是 JSON"}, {})
    r4 = judge_llm(c_bad, EVIDENCE, make_router(mock_bad), "CONTEXT_ONLY", cache_db=db)
    check("解析失败重试 2 次后回退规则层",
          mock_bad.calls == 2 and r4["support_level"] == "CONTEXT_ONLY"
          and "解析" in r4["fallback_reason"])
    row4 = db.get_llm_judge_row(cache_key(c_bad, EVIDENCE))
    check("回退审计行记录 fallback_reason", row4 and "解析" in (row4["fallback_reason"] or ""))

    # ---------- 枚举违规 → 回退 ----------
    c_enum = CLAIM + " 场景-枚举违规"
    mock_enum = CountingMock({c_enum: {"support_level": "MAYBE", "reason": "x"}}, {})
    r5 = judge_llm(c_enum, EVIDENCE, make_router(mock_enum), "IRRELEVANT", cache_db=db)
    check("枚举违规回退规则层", r5["support_level"] == "IRRELEVANT"
          and mock_enum.calls == 2 and r5["fallback_reason"])

    # ---------- 未配置降级 ----------
    c_off = CLAIM + " 场景-未配置"
    r6 = judge_llm(c_off, EVIDENCE, make_router(UnavailableMock()), "PARTIAL_SUPPORT", cache_db=db)
    check("LLM 未配置 → 回退且零调用", r6["support_level"] == "PARTIAL_SUPPORT"
          and r6["fallback_reason"] == "LLM 未配置")

    # ---------- 异常降级 ----------
    c_boom = CLAIM + " 场景-异常"
    boom = BoomMock()
    r7 = judge_llm(c_boom, EVIDENCE, make_router(boom), "PARTIAL_SUPPORT", cache_db=db)
    check("调用异常重试 2 次后回退", boom.calls == 2 and "调用失败" in r7["fallback_reason"])

    # ---------- 缓存键稳定性与区分度 ----------
    k1 = cache_key(CLAIM, EVIDENCE)
    k2 = cache_key(CLAIM + "X", EVIDENCE)
    k3 = cache_key(CLAIM, {**EVIDENCE, "text": EVIDENCE["text"] + " 更多正文"})
    check("缓存键：同输入稳定、异输入不同", k1 == cache_key(CLAIM, EVIDENCE)
          and k1 != k2 and k1 != k3)

    db.close()
    failed = [c for c in checks if not c[1]]
    print(f"\n结果: {len(checks) - len(failed)}/{len(checks)} 通过")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
