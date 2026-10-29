# -*- coding: utf-8 -*-
"""Phase 9 §3 **区分度回测**（核心验收）：对 Phase 8 两版稿件与生产正片稿各跑一次完整评分。

产物（唯一落盘点）：
  · `docs/regression_2x/logs/phase9_backtest_v2.json` / `_v3.json` / `_prod.json`
  · `docs/regression_2x/logs/phase9_retention_cache.json`（LLM 缓存；键=prompt_version+model+sha）

判定标准（授权书 §3）：
  ① 机械层：v3 各维度 ≥ v2（用 STATUS_RANK 比较；v2 缺元数据以结构码呈现、不计 FAIL）
  ② LLM 层：v3 的 hook 强度分 ≥ v2，且给出 ≥1 条 v2 可执行的 hook 改进建议
  ③ 评分器**不评事实对错**（out-of-scope，写进报告）
  ④ 生产正片稿基线分（后续改稿对照锚点）

纪律：真实 LLM 总花费 ≤ $0.30，逐调用记录 usage/成本；第二次运行必须命中缓存且输出一致；
LLM 失败/预算被推理吃满 ⇒ 如实记录 PARTIAL（**不编造分数**）。
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

ROOT = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.core import retention as RT                                       # noqa: E402
from video_studio.core.env import load_env                                          # noqa: E402
from video_studio.core.visual_requirement import canonical                          # noqa: E402
from video_studio.ops import retention as OPS                                       # noqa: E402

LOGS = ROOT / "docs" / "regression_2x" / "logs"
CACHE_PATH = LOGS / "phase9_retention_cache.json"
COST_LIMIT_USD = 0.30

FIXTURES = [
    ("v2", LOGS / "phase8_ab_v2.json", "Phase 8 A/B v2 臂（改动前 v2 规范）"),
    ("v3", LOGS / "phase8_ab_v3.json", "Phase 8 A/B v3 臂（Creator Style v3）"),
    ("prod", ROOT / "projects" / "p_96efdc03e1aa" / "artifacts" / "a_49b58fb3dc01.json",
     "生产正片稿（21 段 / v2 时代，基线锚点）"),
]


def load_script(p: pathlib.Path) -> dict:
    j = json.loads(p.read_text(encoding="utf-8"))
    return j.get("script") if isinstance(j.get("script"), dict) else j


def is_hook_suggestion(s: dict) -> bool:
    blob = "{} {} {}".format(s.get("target"), s.get("action"), s.get("why"))
    keys = ("hook", "opening", "开场", "首段", "开头", "前 40", "前40", "认知冲突", "hook_strength")
    return any(k.lower() in blob.lower() for k in keys)


def main() -> int:
    load_env(str(ROOT / ".env"))
    cfg = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8"))
    model = ((cfg.get("llm") or {}).get("tiers") or {}).get(OPS.JUDGE_TIER, {}).get(
        "model") or "deepseek-v4-pro"
    client = OPS.TemperatureZeroClient((cfg.get("llm") or {}).get("deepseek") or {})
    if not client.available:
        print("FAIL-CLOSED: DEEPSEEK_API_KEY 不可用 ⇒ 回测无法真实执行", file=sys.stderr)
        return 2
    cache = json.loads(CACHE_PATH.read_text(encoding="utf-8")) if CACHE_PATH.is_file() else {}
    print("模型: {}（tier {}）| temperature={} | max_tokens={} | 缓存键基数 {}"
          .format(model, OPS.JUDGE_TIER, OPS.JUDGE_TEMPERATURE, OPS.JUDGE_MAX_TOKENS, len(cache)))

    spent, results = 0.0, {}
    calls = []
    FIXED_TAKEN_AT = "PHASE9_BACKTEST_FIXED（固定值：使两次运行的比较为逐字节可比）"
    for label, path, desc in FIXTURES:
        script = load_script(path)
        t0 = time.time()
        rep1 = OPS.evaluate(script, source={"path": str(path.relative_to(ROOT)), "label": desc},
                            cache=cache, client=client, model=model,
                            taken_at=FIXED_TAKEN_AT)
        llm = rep1["llm"]
        cost = float(llm.get("cost_usd") or 0.0)
        spent += cost
        calls.append({"arm": label, "cache_hit": llm.get("cache_hit"), "status": llm.get("status"),
                      "reason_code": llm.get("reason_code"), "usage": llm.get("usage"),
                      "cost_usd": llm.get("cost_usd"),
                      "reasoning_tokens": llm.get("reasoning_tokens"),
                      "latency_ms": llm.get("latency_ms"),
                      "elapsed_s": round(time.time() - t0, 1)})
        if spent > COST_LIMIT_USD:
            print("FAIL-CLOSED: 累计成本 ${:.4f} 超上限 ${:.2f} ⇒ 中止".format(spent, COST_LIMIT_USD),
                  file=sys.stderr)
            return 3
        # 把新结果写入缓存（内存），再跑第二次 ⇒ 必须命中且输出一致
        if llm.get("status") == "OK":
            cache[llm["cache_key"]] = {"rubric": llm.get("rubric"),
                                       "suggestions": llm.get("suggestions") or []}
        rep2 = OPS.evaluate(script, source={"path": str(path.relative_to(ROOT)), "label": desc},
                            cache=cache, client=client, model=model,
                            taken_at=FIXED_TAKEN_AT)
        second_hit = bool(rep2["llm"].get("cache_hit"))
        # 一致性口径（明示）：比较**判定内容**——机械层全量 + rubric + 建议 + status/版本/缓存键。
        # 排除运行元数据（cache_hit / usage / cost_usd / latency_ms / tokens / raw_text_sha256）
        # 与**派生的 artifact_hash**：报告哈希按设计**覆盖**了这些成本证据字段，
        # 因此"新调用"与"缓存命中"的 artifact_hash 本就应该不同（这一点在下方显式登记）。
        def _judged(rep: dict) -> dict:
            llm = rep.get("llm") or {}
            return {
                "mechanical": rep.get("mechanical"),
                "script_sha256": rep.get("script_sha256"),
                "out_of_scope": rep.get("out_of_scope"),
                "responsibility_boundary": rep.get("responsibility_boundary"),
                "applied": rep.get("applied"), "executed": rep.get("executed"),
                "llm": {k: llm.get(k) for k in ("status", "prompt_version", "model", "temperature",
                                                "cache_key", "rubric", "suggestions")},
            }
        proj1, proj2 = _judged(rep1), _judged(rep2)
        identical = canonical(proj1) == canonical(proj2)
        results[label] = {"report": rep1,
                          "second_run": {"cache_hit": second_hit,
                                         "identical_to_first": identical,
                                         "compared": "判定内容（机械层+rubric+建议+status/版本/缓存键）",
                                         "excluded": "运行元数据（cache_hit/usage/cost/latency/"
                                                     "tokens/raw_text_sha256）与派生 artifact_hash",
                                         "artifact_hash_first": rep1["artifact_hash"],
                                         "artifact_hash_second": rep2["artifact_hash"],
                                         "artifact_hash_equals": (rep1["artifact_hash"]
                                                                  == rep2["artifact_hash"]),
                                         "fixed_timestamp": True},
                          "path": str(path.relative_to(ROOT)), "description": desc}
        art = {
            "schema": "phase9-backtest-arm-v1", "arm": label, "description": desc,
            "fixture": str(path.relative_to(ROOT)),
            "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "model": model, "tier": OPS.JUDGE_TIER, "prompt_version": OPS.PROMPT_VERSION,
            "temperature": OPS.JUDGE_TEMPERATURE, "max_tokens": OPS.JUDGE_MAX_TOKENS,
            "report": rep1, "second_run": results[label]["second_run"],
            "cumulative_cost_usd": round(spent, 6),
            "llm_attempts": [c for c in calls if c["arm"] == label],
        }
        (LOGS / "phase9_backtest_{}.json".format(label)).write_text(
            json.dumps(art, ensure_ascii=False, indent=1), encoding="utf-8")
        print("[{:4s}] llm={} score(mech)={} cost=${} cache2nd={} identical={}".format(
            label, llm.get("status"), rep1["mechanical"]["mechanical_score"],
            llm.get("cost_usd"), second_hit, identical))

    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=1, sort_keys=True),
                          encoding="utf-8")

    # ---------------- 判定 ----------------
    m2, m3 = results["v2"]["report"]["mechanical"], results["v3"]["report"]["mechanical"]
    crit1 = {d: {"v2": m2["dimensions"][d]["status"], "v3": m3["dimensions"][d]["status"],
                 "ok": RT.STATUS_RANK[m3["dimensions"][d]["status"]] >=
                       RT.STATUS_RANK[m2["dimensions"][d]["status"]]} for d in RT.DIMENSIONS}
    l2, l3 = results["v2"]["report"]["llm"], results["v3"]["report"]["llm"]
    hook2 = ((l2.get("rubric") or {}).get("hook_strength") or {}).get("score")
    hook3 = ((l3.get("rubric") or {}).get("hook_strength") or {}).get("score")
    sug2 = results["v2"]["report"]["top_suggestions"]
    hook_sug2 = [s for s in sug2 if is_hook_suggestion(s)]
    crit2 = {"v2_hook_score": hook2, "v3_hook_score": hook3,
             "hook_ge": (None if (hook2 is None or hook3 is None) else hook3 >= hook2),
             "v2_hook_suggestions": hook_sug2,
             "has_actionable_hook_suggestion": bool(hook_sug2),
             "evaluable": bool(hook2 is not None and hook3 is not None)}
    summary = {
        "schema": "phase9-backtest-summary-v1",
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "model": model, "prompt_version": OPS.PROMPT_VERSION,
        "temperature": OPS.JUDGE_TEMPERATURE, "max_tokens": OPS.JUDGE_MAX_TOKENS,
        "mechanical_scores": {k: results[k]["report"]["mechanical"]["mechanical_score"]
                              for k in results},
        "criterion_1_per_dimension_v3_ge_v2": crit1,
        "criterion_1_ok": all(v["ok"] for v in crit1.values()),
        "criterion_2": crit2,
        "criterion_2_ok": bool(crit2["evaluable"] and crit2["hook_ge"]
                               and crit2["has_actionable_hook_suggestion"]),
        "criterion_3_not_a_fact_check": results["v3"]["report"]["out_of_scope"],
        "criterion_4_prod_baseline": results["prod"]["report"]["mechanical"]["mechanical_score"],
        "second_run_all_cache_hit": all(results[k]["second_run"]["cache_hit"] for k in results),
        "second_run_all_identical": all(results[k]["second_run"]["identical_to_first"]
                                        for k in results),
        "total_cost_usd": round(spent, 6), "cost_limit_usd": COST_LIMIT_USD,
        "llm_attempts": calls,
        "responsibility_boundary": results["v3"]["report"]["responsibility_boundary"],
    }
    (LOGS / "phase9_backtest_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n机械层得分: v2={} v3={} prod={}".format(summary["mechanical_scores"]["v2"],
                                                     summary["mechanical_scores"]["v3"],
                                                     summary["mechanical_scores"]["prod"]))
    print("判据① 逐维度 v3≥v2:", summary["criterion_1_ok"],
          {d: (v["v2"], v["v3"]) for d, v in crit1.items()})
    print("判据② hook: v2={} v3={} ⇒ ≥:{} | v2 可执行 hook 建议 {} 条 ⇒ {}".format(
        hook2, hook3, crit2["hook_ge"], len(hook_sug2), summary["criterion_2_ok"]))
    print("判据④ 生产基线分:", summary["criterion_4_prod_baseline"])
    print("二次运行全部命中缓存/一致:", summary["second_run_all_cache_hit"],
          summary["second_run_all_identical"])
    print("累计成本 ${:.5f}（上限 ${:.2f}）".format(spent, COST_LIMIT_USD))
    return 0


if __name__ == "__main__":
    sys.exit(main())
