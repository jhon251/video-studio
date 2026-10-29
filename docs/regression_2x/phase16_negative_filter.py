# -*- coding: utf-8 -*-
"""P16-1 负例过滤器验证（硬门）。运行前写死的达标线见评测集 `gate_frozen_before_run`。

过滤器规则：机器 `IRRELEVANT` ⇒ **DENY**（出局 + 附一句理由供人工抽查）；
其余（RELEVANT / PARTIAL / NOT_ASSESSABLE）⇒ 进人工短名单（**不因机器 RELEVANT 放行任何绑定**）。

统计（授权书 §2）：
  · 负例捕获率 = 负例中机器判 IRRELEVANT 的比例，达标线 ≥ 60%
  · 误杀率     = 24 条人工正例中机器判 IRRELEVANT 的比例，达标线 ≤ 5%（≤1/24）
  · 每条 DENY 必附理由
人工负例与构造负例**分开统计**，不混为一谈。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core.env import load_env                                  # noqa: E402
load_env(R / ".env")
from video_studio.tools import vlm_judge as V                               # noqa: E402

FIX = R / "tests" / "fixtures"
LOGS = R / "docs" / "regression_2x" / "logs"
EVAL = FIX / "p16_negative_filter_eval_v1.json"
OUT = LOGS / "phase16_negative_filter_report.json"

doc = json.loads(EVAL.read_text(encoding="utf-8"))
doc_sha = hashlib.sha256(EVAL.read_bytes()).hexdigest()
cfg, src = V.resolve_config(json.loads((R / "config" / "config.json").read_text(encoding="utf-8")),
                            root=R)
ok, why = V.available(cfg)
print("provider:", cfg.get("model"), "| available:", ok, why)
print("prompt:", V.PROMPT_VERSION, "| 评测集 sha256:", doc_sha[:16], "…")
print("达标线:", json.dumps(doc["gate_frozen_before_run"], ensure_ascii=False))
print()

budget, spent = 1.0, 0.0


def judge(rec, tag):
    global spent
    res = V.judge_pair(requirement=rec["requirement_snapshot"], image_path=rec["image_path"],
                       cfg=cfg, root=R, budget_usd=budget, spent_usd=spent,
                       prompt_variant="main")
    spent = round(spent + float(res.get("cost_usd") or 0.0), 8)
    lab = res.get("label")
    row = {**{k: rec[k] for k in rec if k in
              ("neg_id", "pos_id", "kind", "scene_id", "asset_key12", "known_label", "why")},
           "role": tag, "machine_label": lab,
           "machine_reason": res.get("reason"),
           "deny": lab == "IRRELEVANT",
           "error_code": res.get("error_code"),
           "cache_hit": res.get("cache_hit"), "cost_usd": res.get("cost_usd"),
           "tokens_in": res.get("tokens_in"), "tokens_out": res.get("tokens_out"),
           "image_tokens": res.get("image_tokens"),
           "provenance": rec.get("provenance")}
    return row


negs = [judge(n, "NEGATIVE") for n in doc["negatives"]]
poss = [judge(p, "POSITIVE") for p in doc["positives"]]

g = doc["gate_frozen_before_run"]


def rate(nums, den):
    return round(nums / den, 4) if den else None


n_all = len(negs)
n_cap = sum(1 for x in negs if x["deny"])
by_kind = {}
for x in negs:
    k = x["kind"]
    by_kind.setdefault(k, {"total": 0, "captured": 0})
    by_kind[k]["total"] += 1
    by_kind[k]["captured"] += 1 if x["deny"] else 0
for k, v in by_kind.items():
    v["capture_rate"] = rate(v["captured"], v["total"])

p_all = len(poss)
p_kill = sum(1 for x in poss if x["deny"])
cap_rate = rate(n_cap, n_all)
kill_rate = rate(p_kill, p_all)
c1 = cap_rate is not None and cap_rate >= g["min_negative_capture_rate"]
c2 = (p_kill <= g["max_false_kill_count"]) and \
     (kill_rate is not None and kill_rate <= g["max_false_kill_rate"])
deny_missing_reason = [x["neg_id"] if x.get("neg_id") else x.get("pos_id")
                       for x in negs + poss if x["deny"] and not (x["machine_reason"] or "").strip()]

rep = {
    "schema": "phase16-negative-filter-report-v1",
    "stage": "Phase 16 P16-1 负例过滤器验证（硬门）",
    "eval_set": {"file": EVAL.relative_to(R).as_posix(), "sha256": doc_sha,
                 "counts": doc["counts"], "meets_min_negatives": doc["meets_min_negatives"]},
    "filter_rule": doc["filter_rule"],
    "provider": {"model": cfg.get("model"), "base_url": cfg.get("base_url"),
                 "available": ok, "config_source": src,
                 "prompt_version": V.PROMPT_VERSION},
    "gate_frozen_before_run": g,
    "results": {
        "negatives_total": n_all, "negatives_captured": n_cap,
        "negative_capture_rate": cap_rate,
        "negative_capture_by_kind": by_kind,
        "positives_total": p_all, "positives_falsely_killed": p_kill,
        "false_kill_rate": kill_rate,
        "deny_without_reason": deny_missing_reason,
        "machine_label_distribution": {
            "negatives": {k: sum(1 for x in negs if x["machine_label"] == k)
                          for k in ("RELEVANT", "PARTIAL", "IRRELEVANT", "NOT_ASSESSABLE")},
            "positives": {k: sum(1 for x in poss if x["machine_label"] == k)
                          for k in ("RELEVANT", "PARTIAL", "IRRELEVANT", "NOT_ASSESSABLE")},
        },
    },
    "gate": {
        "negative_capture_pass": bool(c1),
        "false_kill_pass": bool(c2),
        "every_deny_has_reason": not deny_missing_reason,
        "passed": bool(c1 and c2 and not deny_missing_reason),
        "decision": ("PASS ⇒ 过滤器可用于 P16-3 获取初筛（拒签出局+理由，其余进人工短名单）"
                     if (c1 and c2 and not deny_missing_reason)
                     else "FAIL ⇒ 获取预筛回退人工（provider 元数据短名单），过滤器不接线"),
    },
    "cost": {"budget_usd": budget, "spent_usd": spent,
             "api_calls": sum(1 for x in negs + poss if not x["cache_hit"]),
             "cache_hits": sum(1 for x in negs + poss if x["cache_hit"])},
    "negatives": negs, "positives": poss,
    "zero_promotion": True,
}
OUT.write_text(json.dumps(rep, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")

print("=" * 78)
print("P16-1 结果")
print("=" * 78)
print("  负例捕获: {}/{} = {}".format(n_cap, n_all, cap_rate))
for k, v in sorted(by_kind.items()):
    print("    {:24s} {}/{} = {}".format(k, v["captured"], v["total"], v["capture_rate"]))
print("  误杀:     {}/{} = {}  (阈值 ≤{})".format(p_kill, p_all, kill_rate,
                                                  g["max_false_kill_rate"]))
print("  DENY 缺理由:", deny_missing_reason or "无")
print("  成本: ${:.4f} | API {} | 缓存 {}".format(
    spent, rep["cost"]["api_calls"], rep["cost"]["cache_hits"]))
print("  门禁:", rep["gate"]["decision"])
print()
print("  负例逐条:")
for x in negs:
    print("   {} {:24s} {} {} | 机器={} | {}".format(
        "捕获" if x["deny"] else "漏检", x["kind"], x["scene_id"], x["asset_key12"],
        x["machine_label"], str(x["machine_reason"])[:56]))
print()
print("  正例误杀:", [x["pos_id"] for x in poss if x["deny"]] or "无")
print("  报告 ->", OUT.relative_to(R).as_posix())
sys.exit(0 if rep["gate"]["passed"] else 7)
