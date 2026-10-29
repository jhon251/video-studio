# -*- coding: utf-8 -*-
"""P14-2 真实评测门禁（只读 CLI 逻辑层）：VLM 判定 vs 冻结人工真值。

**达标线在运行前写死**（见 PHASE14_REPORT.md §4）：
  · overall agreement ≥ 90%
  · 「人工 IRRELEVANT → 机器 RELEVANT」= **0**
其余（正例误判 RELEVANT→IRRELEVANT）**只报告不阻断**。

**PASS/FAIL 归一规则（运行前写死）**：真值只有二值（RELEVANT / IRRELEVANT），
故机器 `PARTIAL` 与 `NOT_ASSESSABLE`（含调用失败）**一律计为与人工不一致**（保守口径，
不放宽、不把 PARTIAL 偷偷算对）。

成本：逐调用记账；超预算即停（不静默继续）；二次运行走文件缓存 ⇒ $0 且逐字节一致。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

from ..tools import vlm_judge as V

DEFAULT_TRUTH = pathlib.Path("tests") / "fixtures" / "vlm_relevance_truth_v1.json"
DEFAULT_OUT = pathlib.Path("docs") / "regression_2x" / "logs" / "phase14_eval_report.json"

#: 归一规则（写死；改它等于改门禁）
BINARY = ("RELEVANT", "IRRELEVANT")
NON_MATCHING = ("PARTIAL", V.NA)


def load_truth(path: str | pathlib.Path) -> dict:
    p = pathlib.Path(path)
    raw = p.read_bytes()
    doc = json.loads(raw.decode("utf-8"))
    doc["_file"] = str(p)
    doc["_sha256"] = hashlib.sha256(raw).hexdigest()
    return doc


def run_eval(*, root: str | pathlib.Path, config: dict | None = None,
             truth_path: str | pathlib.Path | None = None,
             budget_usd: float = 2.0, max_pairs: int | None = None,
             progress=None, cache_only: bool = False,
             prompt_variant: str = "main") -> dict:
    """跑真值集评测。返回完整报告 dict（不写文件）。"""
    r = pathlib.Path(root)
    doc = load_truth(truth_path or (r / DEFAULT_TRUTH))
    cfg, src = V.resolve_config(config, root=r)
    ok, why = V.available(cfg)
    rows, spent = [], 0.0
    pairs = doc.get("pairs") or []
    if max_pairs:
        pairs = pairs[:int(max_pairs)]
    for i, p in enumerate(pairs, 1):
        if not ok:
            res = {"schema": V.SCHEMA, "prompt_version": V.PROMPT_VERSION,
                   "label": V.NA, "reason": "", "confidence": None,
                   "error_code": why,
                   "error_detail": "provider 不可用（未启用或缺凭据）",
                   "model": cfg.get("model") or "", "cache_key": "", "cache_hit": False,
                   "tokens_in": 0, "tokens_out": 0, "image_tokens": 0,
                   "cost_usd": 0.0, "latency_ms": 0, "image": {},
                   "requirement_text_sha256": ""}
        else:
            res = V.judge_pair(requirement=p.get("requirement_snapshot") or {},
                               image_path=p["image_path"], cfg=cfg, root=r,
                               budget_usd=budget_usd, spent_usd=spent,
                               prompt_variant=prompt_variant)
        spent = round(spent + float(res.get("cost_usd") or 0.0), 8)
        human = p["human_label"]
        machine = res.get("label")
        agree = (machine == human)
        rows.append({
            "pair_id": p["pair_id"], "scene_id": p["scene_id"],
            "asset_key12": p["asset_key12"], "asset_id": p.get("asset_id"),
            "human_label": human, "machine_label": machine, "agree": bool(agree),
            "human_reason": p.get("human_reason"),
            "machine_reason": res.get("reason"),
            "confidence": res.get("confidence"),
            "error_code": res.get("error_code"), "error_detail": res.get("error_detail"),
            "cache_hit": res.get("cache_hit"), "cache_key": res.get("cache_key"),
            "tokens_in": res.get("tokens_in"), "tokens_out": res.get("tokens_out"),
            "image_tokens": res.get("image_tokens"), "cost_usd": res.get("cost_usd"),
            "latency_ms": res.get("latency_ms"),
            "image": {k: (res.get("image") or {}).get(k) for k in
                      ("source_sha256", "out_width", "out_height", "jpeg_quality",
                       "jpeg_bytes", "jpeg_sha256")},
            "truth_provenance": p.get("provenance"),
            "asset_origin": p.get("asset_origin"),
        })
        if progress is not None:
            progress(i, len(pairs), rows[-1], spent)
        if spent >= budget_usd:
            break

    n = len(rows)
    agree_n = sum(1 for x in rows if x["agree"])
    conf = {}
    for x in rows:
        conf.setdefault(x["human_label"], {})
        conf[x["human_label"]][str(x["machine_label"])] = \
            conf[x["human_label"]].get(str(x["machine_label"]), 0) + 1
    fp = [x for x in rows if x["human_label"] == "IRRELEVANT"
          and x["machine_label"] == "RELEVANT"]
    fn = [x for x in rows if x["human_label"] == "RELEVANT"
          and x["machine_label"] == "IRRELEVANT"]
    na = [x for x in rows if x["machine_label"] in NON_MATCHING]
    gate = doc.get("gate_frozen_before_run") or {}
    min_agr = float(gate.get("min_agreement", 0.90))
    max_fp = int(gate.get("max_human_irrelevant_to_machine_relevant", 0))
    agreement = (agree_n / n) if n else 0.0
    c1 = agreement >= min_agr
    c2 = len(fp) <= max_fp
    report = {
        "schema": "phase14-eval-report-v1",
        "stage": "Phase 14 P14-2 真实评测门禁",
        "truth": {"file": doc.get("_file"), "sha256": doc.get("_sha256"),
                  "pair_count": n, "declared_pair_count": doc.get("pair_count"),
                  "counts": doc.get("counts"),
                  "min_pairs_required": doc.get("min_pairs_required"),
                  "meets_min_pairs": bool(doc.get("meets_min_pairs")),
                  "shortfall_note": (
                      "**未达 ≥30 对**：全仓仅存在 %d 对带显式人工正/负证据的 (镜头, 素材) 对；"
                      "缺口已在运行前登记并保留，**未**用机器判定充数。" % n
                      if not doc.get("meets_min_pairs") else "")},
        "provider": {"enabled": cfg.get("enabled"), "model": cfg.get("model"),
                     "base_url": cfg.get("base_url"),
                     "api_key_env": cfg.get("api_key_env"),
                     "api_key_present": V.api_key(cfg) is not None,
                     "config_source": src, "available": ok,
                     "unavailable_reason": why},
        "policy": {k: v for k, v in V.POLICY.items()},
        "normalization": {
            "binary": list(BINARY), "non_matching_counts_as_disagree": list(NON_MATCHING),
            "note": "PARTIAL / NOT_ASSESSABLE（含调用失败）一律计为与真值不一致（保守口径）"},
        "gate_frozen_before_run": {"min_agreement": min_agr,
                                   "max_human_irrelevant_to_machine_relevant": max_fp},
        "results": {"pairs_total": n, "agree": agree_n,
                    "agreement": round(agreement, 4),
                    "confusion": conf,
                    "human_irrelevant_to_machine_relevant": [
                        {"pair_id": x["pair_id"], "scene_id": x["scene_id"],
                         "asset_key12": x["asset_key12"], "machine_reason": x["machine_reason"]}
                        for x in fp],
                    "human_relevant_to_machine_irrelevant": [
                        {"pair_id": x["pair_id"], "scene_id": x["scene_id"],
                         "asset_key12": x["asset_key12"], "machine_reason": x["machine_reason"]}
                        for x in fn],
                    "non_matching": [
                        {"pair_id": x["pair_id"], "machine_label": x["machine_label"],
                         "error_code": x["error_code"]} for x in na]},
        "gate": {"agreement_pass": bool(c1),
                 "no_human_irrelevant_to_machine_relevant_pass": bool(c2),
                 "passed": bool(c1 and c2),
                 "decision": ("PASS ⇒ 允许进入 P14-3 集成" if (c1 and c2)
                              else "FAIL ⇒ **不集成**（只报告，亦为合格交付）")},
        "cost": {"budget_usd": budget_usd, "spent_usd": round(spent, 8),
                 "within_budget": bool(spent <= budget_usd),
                 "cache_hits": sum(1 for x in rows if x["cache_hit"]),
                 "api_calls": sum(1 for x in rows if not x["cache_hit"]),
                 "pricing": V.pixel_cost_note()},
        "pairs": rows,
        "zero_promotion": True,
    }
    return report


def main(argv: list[str] | None = None) -> int:
    import argparse
    ROOT = pathlib.Path(__file__).resolve().parents[3]   # .../video-studio
    ap = argparse.ArgumentParser(prog="vlm-eval")
    ap.add_argument("--truth", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--budget-usd", type=float, default=2.0)
    ap.add_argument("--max-pairs", type=int, default=None)
    ap.add_argument("--json-only", action="store_true")
    ap.add_argument("--prompt-variant", default="main", choices=["main", "diag_anchor"],
                    help="main=门禁口径；diag_anchor=**诊断专用**变体（不参与门禁判定）")
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:                                                       # noqa: BLE001
        pass

    config = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8"))

    def prog(i, tot, row, spent):
        print("  [{:>2}/{}] {} {} | 人工={} 机器={} | {} | ${:.4f} (累计 ${:.4f})".format(
            i, tot, row["scene_id"], row["asset_key12"], row["human_label"],
            row["machine_label"], "一致" if row["agree"] else "**不一致**",
            float(row["cost_usd"] or 0), spent), flush=True)

    rep = run_eval(root=ROOT, config=config,
                   truth_path=(pathlib.Path(args.truth) if args.truth else None),
                   budget_usd=args.budget_usd, max_pairs=args.max_pairs, progress=prog,
                   prompt_variant=args.prompt_variant)
    if args.prompt_variant != "main":
        rep["report_kind"] = ("DIAGNOSTIC_ONLY（提示词变体 {}）——**不参与门禁判定**，"
                              "仅供失配根因诊断".format(args.prompt_variant))
    out = pathlib.Path(args.out) if args.out else (ROOT / DEFAULT_OUT)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, ensure_ascii=False, indent=1, sort_keys=True),
                   encoding="utf-8")

    if not args.json_only:
        r = rep["results"]
        print()
        print("=" * 78)
        print("真值集:", rep["truth"]["pair_count"], "对 | sha256",
              str(rep["truth"]["sha256"])[:16], "…")
        print("provider:", rep["provider"]["model"], "| available:",
              rep["provider"]["available"], rep["provider"]["unavailable_reason"] or "")
        print("agreement: {} / {} = {:.2%}  (阈值 {:.0%})".format(
            r["agree"], r["pairs_total"], r["agreement"],
            rep["gate_frozen_before_run"]["min_agreement"]))
        print("混淆矩阵:", json.dumps(r["confusion"], ensure_ascii=False))
        print("人工 IRRELEVANT→机器 RELEVANT:", len(r["human_irrelevant_to_machine_relevant"]),
              "(上限 {}）".format(
                  rep["gate_frozen_before_run"]["max_human_irrelevant_to_machine_relevant"]))
        print("正例误判 RELEVANT→IRRELEVANT:", len(r["human_relevant_to_machine_irrelevant"]),
              "（只报告不阻断）")
        print("非二值输出:", len(r["non_matching"]))
        print("成本: ${:.4f} / 上限 ${:.2f} | API 调用 {} | 缓存命中 {}".format(
            rep["cost"]["spent_usd"], rep["cost"]["budget_usd"],
            rep["cost"]["api_calls"], rep["cost"]["cache_hits"]))
        print("门禁:", rep["gate"]["decision"])
        print("报告 ->", out)
    return 0 if rep["gate"]["passed"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
