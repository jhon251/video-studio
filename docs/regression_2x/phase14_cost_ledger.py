# -*- coding: utf-8 -*-
"""恢复 P14-2/P14-2诊断 的**首次运行**成本（报告的 cost.spent_usd 被缓存复跑覆盖为 $0）。
逐对 cost_usd 是首次运行的值（缓存命中不改写 pair 记录），故按 pair 求和即首跑成本。"""
from __future__ import annotations

import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")

out = {}
for label, rel in (("gate", "docs/regression_2x/logs/phase14_eval_report.json"),
                   ("diag", "docs/regression_2x/logs/phase14_eval_diag_anchor.json")):
    p = R / rel
    rep = json.loads(p.read_text(encoding="utf-8"))
    pairs = rep["pairs"]
    first_run = round(sum(float(x.get("cost_usd") or 0.0) for x in pairs), 8)
    runs = {k: 0 for k in ("tokens_in", "tokens_out", "image_tokens")}
    for x in pairs:
        for k in runs:
            runs[k] += int(x.get(k) or 0)
    out[label] = {
        "file": rel,
        "pairs": len(pairs),
        "first_run_cost_usd": first_run,
        "tokens_in": runs["tokens_in"], "tokens_out": runs["tokens_out"],
        "image_tokens": runs["image_tokens"],
        "cache_hits_in_file": sum(1 for x in pairs if x.get("cache_hit")),
        "api_calls_in_file": sum(1 for x in pairs if not x.get("cache_hit")),
        "reported_spent_usd_in_file": rep["cost"]["spent_usd"],
        "agreement": rep["results"]["agreement"],
    }
    print("{}: {} 对 | 首跑成本 ${:.4f} | tokens in/out/img {}/{}/{} | "
          "agreement {:.2%} | 文件内 cache_hit {} api {} | 文件自报 spent ${:.4f}".format(
              label, len(pairs), first_run, runs["tokens_in"], runs["tokens_out"],
              runs["image_tokens"], rep["results"]["agreement"],
              out[label]["cache_hits_in_file"], out[label]["api_calls_in_file"],
              rep["cost"]["spent_usd"]))

probe = 0.0006
total = round(out["gate"]["first_run_cost_usd"] + out["diag"]["first_run_cost_usd"] + probe, 8)
out["connectivity_probe_usd"] = probe
out["total_api_cost_usd"] = total
p = R / "docs/regression_2x/logs/phase14_cost_ledger.json"
p.write_text(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
print()
print("总 API 花费 = ${:.4f}（上限 $2.00）".format(total))
print("ledger ->", p.relative_to(R).as_posix())
