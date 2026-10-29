# -*- coding: utf-8 -*-
"""Phase 10 / P10-1 产物：retention 评分器 **3 采样聚合**报告。

- 对 Phase 8 两稿（v2/v3）+ 生产正片稿各做 3 次独立 LLM 采样，输出 median / 全距 / agreement
  （全距 ≤1.0 ⇒ STABLE，否则 UNSTABLE）；缓存键含 sample 序号。
- **成本节省（如实登记）**：sample 0 由 Phase 9 的权威样本缓存**播种**（同一 prompt 版本 +
  同一 model 的真实独立样本，键格式差异仅在于 P10-1 新增 sample 序号）⇒ 仅 sample 1/2 为新调用。
- 判定：v3 median ≥ v2 median（各 rubric 项）。

产物：`docs/regression_2x/logs/phase10_retention_3sample.json`
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys
import time

ROOT = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.core.env import load_env                                          # noqa: E402
from video_studio.ops import retention as OPS                                       # noqa: E402

LOGS = ROOT / "docs" / "regression_2x" / "logs"
SAMPLES = 3
COST_LIMIT_USD = 0.20
FIXTURES = [("v2", LOGS / "phase8_ab_v2.json"), ("v3", LOGS / "phase8_ab_v3.json"),
            ("prod", ROOT / "projects" / "p_96efdc03e1aa" / "artifacts" / "a_49b58fb3dc01.json")]


def script_of(p: pathlib.Path) -> dict:
    j = json.loads(p.read_text(encoding="utf-8"))
    return j.get("script") if isinstance(j.get("script"), dict) else j


def old_key(sha: str, model: str) -> str:
    """Phase 9 缓存键格式（无 sample 序号）——仅用于**播种** sample 0。"""
    return hashlib.sha256("|".join([OPS.PROMPT_VERSION, model, sha]).encode("utf-8")).hexdigest()


def main() -> int:
    load_env(str(ROOT / ".env"))
    cfg = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8"))
    model = ((cfg.get("llm") or {}).get("tiers") or {}).get(OPS.JUDGE_TIER, {}).get(
        "model") or "deepseek-v4-pro"
    client = OPS.TemperatureZeroClient((cfg.get("llm") or {}).get("deepseek") or {})
    if not client.available:
        print("FAIL-CLOSED: API key 不可用", file=sys.stderr)
        return 2
    prior = json.loads((LOGS / "phase9_retention_cache.json").read_text(encoding="utf-8"))
    cache_path = LOGS / "phase10_retention_cache.json"
    cache = (json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.is_file() else {})
    seeded = []
    for label, path in FIXTURES:
        sha = OPS.script_sha256(script_of(path))
        new0 = OPS.cache_key(sha, model, sample_index=0)
        if new0 in cache:
            continue                                  # 已缓存（二次运行 ⇒ 零成本）
        ok = old_key(sha, model)
        if ok in prior:
            cache[new0] = prior[ok]
            seeded.append(label)
    print("模型 {} | prompt {} | 采样 {} | 缓存播种 sample0: {}".format(
        model, OPS.PROMPT_VERSION, SAMPLES, seeded))

    out = {"schema": "phase10-retention-3sample-v1",
           "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "model": model, "tier": OPS.JUDGE_TIER, "prompt_version": OPS.PROMPT_VERSION,
           "temperature": OPS.JUDGE_TEMPERATURE, "samples": SAMPLES,
           "sample0_seeded_from": "phase9_retention_cache.json（Phase 9 权威样本；如实登记）",
           "seeded_fixtures": seeded, "arms": {}, "spent_usd": 0.0}
    spent = 0.0
    for label, path in FIXTURES:
        rep = OPS.evaluate(script_of(path), source={"path": str(path.relative_to(ROOT))},
                           cache=cache, client=client, model=model, samples=SAMPLES,
                           taken_at="PHASE10_3SAMPLE")
        llm = rep["llm"]
        spent += float(llm.get("cost_usd_total") or 0.0)
        if spent > COST_LIMIT_USD:
            print("FAIL-CLOSED: 累计 ${:.4f} 超上限 ${:.2f}".format(spent, COST_LIMIT_USD),
                  file=sys.stderr)
            return 3
        out["arms"][label] = {
            "fixture": str(path.relative_to(ROOT)),
            "mechanical_score": rep["mechanical"]["mechanical_score"],
            "mechanical_cta_codes": rep["mechanical"]["dimensions"]["cta"]["codes"],
            "llm_status": llm.get("status"), "aggregation": llm.get("aggregation"),
            "rubric_median": {k: (v or {}).get("score")
                              for k, v in (llm.get("rubric") or {}).items()},
            "per_sample_scores": [{k: ((p.get("rubric") or {}).get(k) or {}).get("score")
                                   for k in OPS.RUBRIC_ITEMS} for p in (llm.get("per_sample")
                                                                        or [])],
            "cost_usd_total": llm.get("cost_usd_total"),
            "usage_total": llm.get("usage_total"),
            "report": rep,
        }
        print("[{:4s}] mech={} llm={} median={} cost=${}".format(
            label, rep["mechanical"]["mechanical_score"], llm.get("status"),
            out["arms"][label]["rubric_median"], llm.get("cost_usd_total")))
    out["spent_usd"] = round(spent, 6)
    cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=1, sort_keys=True),
                          encoding="utf-8")
    med = {k: out["arms"][k]["rubric_median"] for k in out["arms"]}
    verdict = {}
    for item in OPS.RUBRIC_ITEMS:
        v2m, v3m = med["v2"].get(item), med["v3"].get(item)
        verdict[item] = {"v2_median": v2m, "v3_median": v3m,
                         "v3_ge_v2": (None if None in (v2m, v3m) else v3m >= v2m)}
    out["median_comparison"] = verdict
    out["criterion_v3_median_ge_v2"] = all(v["v3_ge_v2"] for v in verdict.values()
                                           if v["v3_ge_v2"] is not None)
    out["agreement"] = {k: {i: (out["arms"][k]["aggregation"] or {}).get(i, {}).get("agreement")
                            for i in OPS.RUBRIC_ITEMS} for k in out["arms"]}
    (LOGS / "phase10_retention_3sample.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("median 比较:", json.dumps(verdict, ensure_ascii=False))
    print("判据 v3 median ≥ v2 median:", out["criterion_v3_median_ge_v2"],
          "| 本阶段花费 ${:.5f}".format(spent))
    return 0


if __name__ == "__main__":
    sys.exit(main())
