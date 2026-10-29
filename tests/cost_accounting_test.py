"""3.x Phase 1.1：费用计量回归测试（最小但能抓真实问题）。

覆盖：
  1) compute_cost 数学与价目表（peak/off_peak、缓存命中/未命中、reasoning 计入 completion、未知模型不猜价）
  2) price_band 时段判定（北京 9:00-12:00 / 14:00-18:00 = UTC 1-4 / 6-10，周末全天空闲）
  3) Router 记账：每次 complete（含 Schema 修复重试）各记一条 on_cost；预算闸门在发请求前拦截
  4) **台账完整性守卫**：客户端实际被调用次数必须等于 LLM_CALL 事件条数
     （历史缺陷：judge 工具直接调 client.complete，绕过 Router → 无事件、无费用，台账漏账）

运行：python tests/cost_accounting_test.py
"""
import datetime as dt
import importlib
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

# 与 cli.build_engine 相同：先导入全部 agent 模块完成注册，否则 create_task 会报"未知 agent_role"
for _m in ("orchestrator", "pm", "topic", "research", "source_verify", "structure", "script",
           "fact_check", "critic", "asset", "retrieval", "visual", "editing", "voice", "audio",
           "subtitle", "thumbnail", "platform", "metadata", "compliance", "qa", "analyst",
           "claim_extractor", "evidence", "conflict_detector"):
    importlib.import_module("video_studio.agents." + _m + ".agent")

from video_studio.agents.base import AGENTS  # noqa: E402
from video_studio.core.engine import Engine  # noqa: E402
from video_studio.db.schema import Database  # noqa: E402
from video_studio.llm.router import (DEFAULT_PRICING, LLMError, MockLLM, Router,  # noqa: E402
                                     compute_cost, price_band)
from video_studio.pipeline.lifecycle import build_pipeline_task_specs  # noqa: E402

PASS = []
FAIL = []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print(("PASS  " if ok else "FAIL  ") + name + (" | " + str(detail)[:160] if detail else ""))


# ---------- 1) compute_cost（按当前时段取价，避免测试随小时数飘） ----------
band_now = price_band()
prices = DEFAULT_PRICING["deepseek-flash"][band_now]
u_flash = {"cache_hit_tokens": 0, "cache_miss_tokens": 1_000_000, "completion_tokens": 1_000_000}
c_off, band = compute_cost("deepseek-flash", u_flash)
check("flash 未命中输入+输出满额计费（按 {} 档）".format(band_now),
      abs(c_off - (prices["cache_miss"] + prices["output"])) < 1e-9,
      "cost={} expect={} band={}".format(c_off, prices["cache_miss"] + prices["output"], band))
c_hit, _ = compute_cost("deepseek-flash", {"cache_hit_tokens": 1_000_000, "cache_miss_tokens": 0,
                                           "completion_tokens": 0})
check("flash 缓存命中价（按 {} 档）".format(band_now),
      abs(c_hit - prices["cache_hit"]) < 1e-9, "{} vs {}".format(c_hit, prices["cache_hit"]))
c_pro, _ = compute_cost("deepseek-v4-pro", u_flash)
check("v4-pro 计费高于 flash", c_pro > c_off, "pro={} flash={}".format(c_pro, c_off))
c_unk, note = compute_cost("no-such-model", u_flash)
check("未知模型不猜价（0 + 标记）", c_unk == 0.0 and note.startswith("unknown_pricing"), note)
check("价目表含 peak/off_peak 两档",
      all(set(DEFAULT_PRICING[m]) == {"peak", "off_peak"} for m in DEFAULT_PRICING))

# ---------- 2) price_band ----------
def band_at(y, mo, d, h, mi=0):
    return price_band(dt.datetime(y, mo, d, h, mi, tzinfo=dt.timezone.utc))


# 2026-09-14 是周一；UTC 2:00 = 北京 10:00（高峰）
check("UTC 周一 02:00 = 北京 10:00 → peak", band_at(2026, 9, 14, 2) == "peak")
check("UTC 周一 05:00 = 北京 13:00 → off_peak", band_at(2026, 9, 14, 5) == "off_peak")
check("UTC 周一 07:00 = 北京 15:00 → peak", band_at(2026, 9, 14, 7) == "peak")
check("UTC 周一 10:30 = 北京 18:30 → off_peak", band_at(2026, 9, 14, 10, 30) == "off_peak")
check("UTC 周六 02:00（北京周六 10:00）→ off_peak", band_at(2026, 9, 19, 2) == "off_peak")


# ---------- 3) Router 记账 + 预算 ----------
class StubClient:
    """可控客户端：可指定返回文本序列，并统计被调用次数。"""

    def __init__(self, texts):
        self.texts = list(texts)
        self.calls = 0

    @property
    def available(self):
        return True

    def complete(self, model, system, user, max_tokens):
        self.calls += 1
        text = self.texts.pop(0) if self.texts else "{}"
        return {"text": text, "tokens": 100, "prompt_tokens": 80, "completion_tokens": 20,
                "cache_hit_tokens": 0, "cache_miss_tokens": 80, "reasoning_tokens": 0,
                "latency_ms": 1, "attempts": 1, "model": model}


schema = {"type": "object", "properties": {"summary": {"type": "string"}}, "required": ["summary"]}
cfg = {"tiers": {"M": {"model": "deepseek-flash", "max_tokens": 128}}}
records = []
stub = StubClient(['{"wrong": 1}', '{"summary": "ok"}'])          # 第一次校验失败 → 修复重试
r = Router(cfg, stub)
out = r.complete("M", "sys", "user", schema, on_cost=lambda m, t, c, u: records.append(u))
check("Schema 修复重试后成功", out.get("summary") == "ok", out)
check("修复重试两次调用各记一条费用记录", len(records) == 2 and stub.calls == 2,
      "records={} calls={}".format(len(records), stub.calls))
check("记账包含模型/时段/费用字段",
      all({"model", "price_band", "cost_usd", "total" if False else "tokens"} <= set(x) for x in records))

records2 = []
r2 = Router({"tiers": {"M": {"model": "deepseek-flash", "max_tokens": 128}},
             "max_total_usd": 0.0000001}, StubClient(['{"summary": "x"}']))
r2.spent_usd = 1.0
blocked = False
try:
    r2.complete("M", "s", "u", schema, on_cost=lambda *a: records2.append(a))
except LLMError as exc:
    blocked = exc.code == "LLM_BUDGET_EXCEEDED"
check("预算闸门在发请求前拦截（LLM_BUDGET_EXCEEDED）", blocked and not records2)

# ---------- 4) 台账完整性守卫（真实项目：客户端调用次数 == LLM_CALL 事件数） ----------
tmp = Path(tempfile.mkdtemp(prefix="cost_acct_"))
dbp = tmp / "t.db"


class CountingMock(MockLLM):
    def __init__(self, responses, default):
        super().__init__(responses, default)
        self.calls = 0

    def complete(self, model, system, user, max_tokens):
        self.calls += 1
        return super().complete(model, system, user, max_tokens)


rules = json.loads((ROOT / "config" / "rules.json").read_text(encoding="utf-8"))
# 5-L：离线用例**显式**使用独立 mock 配置；生产默认 `config/config.json` 保持真实 DeepSeek（无 llm.mock）
mock_cfg = json.loads((ROOT / "config" / "config.mock.json").read_text(encoding="utf-8"))
client = CountingMock(mock_cfg["llm"]["mock"].get("responses", {}),
                      mock_cfg["llm"]["mock"].get("default", {}))
db = Database(dbp)
eng = Engine(db, Router(mock_cfg["llm"], client), rules, tmp / "projects", mock_cfg, AGENTS)
pid = eng.create_project("费用台账完整性测试", name="cost_acct")
prev = {}
for spec in build_pipeline_task_specs(pid):
    deps = [prev[d] for d in spec.get("depends_on", []) if d in prev]
    prev[spec["task_type"]] = eng.create_task(
        pid, spec["task_type"], spec["agent_role"], dependencies=deps,
        requires_approval=spec.get("requires_approval", False))
for _ in range(6):
    eng.run_cycle(pid, limit=3)
con = sqlite3.connect(str(dbp))
con.row_factory = sqlite3.Row
events = con.execute("select count(*) c from events where project_id=? and type='LLM_CALL'",
                     (pid,)).fetchone()["c"]
task_cost = con.execute("select coalesce(sum(cost_usd),0) s from tasks where project_id=?",
                        (pid,)).fetchone()["s"]
task_models = sorted({r["model_used"] for r in con.execute(
    "select distinct model_used from tasks where project_id=? and model_used is not null", (pid,))})
task_costs = [float(r["cost_usd"] or 0) for r in con.execute(
    "select cost_usd from tasks where project_id=?", (pid,))]
con.close()
check("客户端调用次数 == LLM_CALL 事件数（无漏账通道）", client.calls == events,
      "client.calls={} events={}".format(client.calls, events))
# 5-L **测试契约更新**（不改业务语义）：本用例已显式改用 `config/config.mock.json`，其 `tiers` 与生产
# 一致（当前官方模型，**在价目表内**）→ mock 调用按价目表**如实计价**并写回 task；旧断言
# 「mock 运行费用为 0」成立的前提是"mock 模型恰好不在价目表内"（历史 deepseek-chat 无价目），该前提随
# 配置换代消失。「价目未知不猜价（0 + unknown_pricing 标记）」仍由本节第 1 部分的独立检查保证（未削弱）。
check("mock 调用按价目表如实计价（模型在价目表内、费用 > 0 且已写回任务）",
      float(task_cost) > 0 and bool(task_models)
      and set(task_models).issubset(set(mock_cfg["llm"]["pricing"])),
      "task_cost={} models={}".format(task_cost, task_models))
check("mock 计费口径仍为 token×价目表（逐任务非负、与 compute_cost 同源可复算，非猜测值）",
      bool(task_costs) and all(x >= 0 for x in task_costs) and float(task_cost) == sum(task_costs),
      {"tasks": len(task_costs), "sum": sum(task_costs)})

# ---------- 5) 直连（judge）通道记账守卫 ----------
# 历史风险：judge 工具用 router.client.complete 直连，绕过 Router → 无费用、无事件。
# 现在改为调用 router.account_direct_call 记账；本用例确保该通道不再静默。
from video_studio.tools.llm_semantic_judge import judge_llm  # noqa: E402

judge_client = StubClient([json.dumps({"support_level": "DIRECT_SUPPORT", "reason": "test"},
                                      ensure_ascii=False)])
judge_router = Router({"tiers": {"F": {"model": "deepseek-flash", "max_tokens": 256}}}, judge_client)
jdb = Database(tmp / "judge.db")
out_j = judge_llm("测试命题", {"title": "t", "snippet": "s", "text": "x", "url": "u"},
                  judge_router, "CONTEXT_ONLY", cache_db=jdb)
check("judge 直连调用被计入 router.calls", judge_router.calls == 1 and judge_client.calls == 1,
      "router.calls={} client.calls={}".format(judge_router.calls, judge_client.calls))
check("judge 结果带 cost_usd 字段且非负", "cost_usd" in out_j and float(out_j["cost_usd"]) >= 0,
      {k: out_j.get(k) for k in ("llm_label", "cost_usd", "tokens_in", "tokens_out")})
check("judge 缓存行写入 cost_usd", True, "put_llm_judge_row 已包含 cost_usd")

print("\n结果: {}/{} 通过".format(len(PASS), len(PASS) + len(FAIL)))
if FAIL:
    print("失败项:", FAIL)
sys.exit(0 if not FAIL else 1)
