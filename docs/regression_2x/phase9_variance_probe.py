# -*- coding: utf-8 -*-
"""Phase 9 附加诊断：LLM 评审层**采样方差**（零 LLM 成本：读取已归档的同版本缓存）。

背景：判据②（v3 hook 强度分 ≥ v2）在各次真实采样中出现过达成与未达成两种结果
⇒ 单样本 LLM rubric 存在不可忽略的采样波动。本脚本从 `phase9_retention_cache_sampling*.json`
（均为 `retention-judge-v2` + 同 model + 同 temperature 的独立真实采样）汇总分布，
作为下一阶段是否改用多采样聚合的依据。**不改变判据②口径**。

产物：`docs/regression_2x/logs/phase9_retention_variance.json`
"""
from __future__ import annotations

import json
import pathlib
import statistics
import sys

ROOT = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.ops import retention as OPS                                       # noqa: E402

LOGS = ROOT / "docs" / "regression_2x" / "logs"
FIXTURES = {"v2": LOGS / "phase8_ab_v2.json", "v3": LOGS / "phase8_ab_v3.json"}
CACHES = sorted(LOGS.glob("phase9_retention_cache_sampling*.json")) + \
    ([LOGS / "phase9_retention_cache.json"] if (LOGS / "phase9_retention_cache.json").is_file()
     else [])


def script_of(p: pathlib.Path) -> dict:
    j = json.loads(p.read_text(encoding="utf-8"))
    return j.get("script") if isinstance(j.get("script"), dict) else j


def main() -> int:
    out = {"schema": "phase9-retention-variance-v1", "prompt_version": OPS.PROMPT_VERSION,
           "model": "deepseek-v4-pro", "temperature": OPS.JUDGE_TEMPERATURE,
           "source": "归档缓存（独立真实采样，零新增 LLM 调用）",
           "caches": [c.name for c in CACHES], "arms": {},
           "note": "同一 prompt 版本 + 同 model + 同 temperature 的独立采样分布；"
                   "判据②仍以权威回测的单样本为准"}
    for arm, fixture in FIXTURES.items():
        script = script_of(fixture)
        key = OPS.cache_key(OPS.script_sha256(script), "deepseek-v4-pro")
        samples = []
        for c in CACHES:
            cache = json.loads(c.read_text(encoding="utf-8"))
            entry = cache.get(key)
            if not entry:
                continue
            rub = entry.get("rubric") or {}
            samples.append({"cache": c.name,
                            "hook_strength": (rub.get("hook_strength") or {}).get("score"),
                            "cta_naturalness": (rub.get("cta_naturalness") or {}).get("score"),
                            "tension_curve": (rub.get("tension_curve") or {}).get("score"),
                            "suggestions": len(entry.get("suggestions") or [])})
        hooks = [s["hook_strength"] for s in samples
                 if isinstance(s["hook_strength"], (int, float))]
        out["arms"][arm] = {
            "fixture": fixture.name, "cache_key": key, "samples": samples,
            "n": len(hooks), "hook_scores": hooks,
            "hook_mean": round(statistics.fmean(hooks), 3) if hooks else None,
            "hook_pstdev": round(statistics.pstdev(hooks), 3) if len(hooks) > 1 else None,
            "hook_range": [min(hooks), max(hooks)] if hooks else None,
        }
    v2, v3 = out["arms"]["v2"], out["arms"]["v3"]
    pairs = []
    for s2 in v2["samples"]:
        for s3 in v3["samples"]:
            if s2["cache"] == s3["cache"]:
                pairs.append({"cache": s2["cache"], "v2": s2["hook_strength"],
                              "v3": s3["hook_strength"],
                              "v3_ge_v2": (None if None in (s2["hook_strength"], s3["hook_strength"])
                                           else s3["hook_strength"] >= s2["hook_strength"])})
    out["paired_comparison"] = pairs
    met = [p["v3_ge_v2"] for p in pairs if p["v3_ge_v2"] is not None]
    out["criterion2_met_rate"] = (round(sum(1 for m in met if m) / len(met), 3) if met else None)
    out["conclusion"] = ("判据② 的达成与否在独立采样间不稳定（见 paired_comparison）："
                        "机械层完全确定性，LLM rubric 层为**单样本估计**；"
                        "下一阶段若要用 rubric 分做决策依据，建议多采样聚合（本阶段未实施）")
    (LOGS / "phase9_retention_variance.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("缓存样本数: v2={} v3={}".format(v2["n"], v3["n"]))
    print("hook 分布: v2={} (mean {}, σ {})".format(v2["hook_scores"], v2["hook_mean"],
                                                  v2["hook_pstdev"]))
    print("            v3={} (mean {}, σ {})".format(v3["hook_scores"], v3["hook_mean"],
                                                   v3["hook_pstdev"]))
    print("逐采样配对 v3≥v2 达成率:", out["criterion2_met_rate"], pairs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
