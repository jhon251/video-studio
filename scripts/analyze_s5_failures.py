"""Stage 5 失败归因数据抽取（只读分析；零代码/规则/Prompt/数据集修改；不调用任何 LLM/API）。

从 Stage 5 评估库（llm_judge_s5_frozen.db）读取 197 条双轨审计行：
rule_label / llm_label(=Stage5 final) / reason（内含未通过清单项或判定路径），
对照 4b 评估库（llm_judge_eval_real.db）读取 Stage 4b 标签；规则层 claim_type 本地确定性复算。
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from video_studio.db.schema import Database  # noqa: E402
from video_studio.tools.llm_semantic_judge import cache_key as key_v1  # noqa: E402
from video_studio.tools.sufficiency_judge import cache_key_v2 as key_v2, rule_claim_type  # noqa: E402

db5 = Database(ROOT / "projects" / "_drafts" / "llm_judge_s5_frozen.db")
db4 = Database(ROOT / "projects" / "_drafts" / "llm_judge_eval_real.db")

reg = json.loads((ROOT / "tests" / "data" / "evidence_regression_r1.json").read_text(encoding="utf-8"))["samples"]
col = json.loads((ROOT / "projects" / "_drafts" / "r1_blind_collection.json").read_text(encoding="utf-8"))
labels = json.loads((ROOT / "projects" / "_drafts" / "r1_blind_labels.json").read_text(encoding="utf-8"))["labels"]
stress = json.loads((ROOT / "tests" / "data" / "contradicts_stress.json").read_text(encoding="utf-8"))["samples"]

samples = []
for s in reg:
    samples.append({"id": s["id"], "claim": s["claim_text"], "truth": s["truth_label"], "ev": s["evidence"]})
i = 0
for rec in col["claims"]:
    for r in rec["results"]:
        i += 1
        samples.append({"id": f"B{i:03d}", "claim": rec["claim_text"], "truth": labels[str(i)],
                        "ev": {"title": r["title"], "snippet": r["snippet"],
                               "text": r["page"].get("text", ""), "url": r["url"]}})
for s in stress:
    samples.append({"id": s["id"], "claim": s["claim_text"], "truth": s["truth_label"], "ev": s["evidence"]})

misses = []
for s in samples:
    r5 = db5.get_llm_judge_row(key_v2(s["claim"], s["ev"]))
    r4 = db4.get_llm_judge_row(key_v1(s["claim"], s["ev"]))
    final = (r5 or {}).get("llm_label") or ""
    rule = (r5 or {}).get("rule_label") or ""
    v4b = (r4 or {}).get("llm_label") or ""
    reason = (r5 or {}).get("reason") or ""
    failed = []
    m = re.search(r"清单未通过: \[(.*?)\]", reason)
    if m:
        failed = [x.strip().strip("'") for x in m.group(1).split(",")]
    path = "DIRECT" if "全部通过" in reason else (
        "CONTRADICTS" if "双信号" in reason else
        "IRRELEVANT" if "无关" in reason else
        "CONTEXT_ONLY" if "词面" in reason or "讨论" in reason else
        (f"CAP({rule_claim_type(s['claim'])})" if reason.startswith("句式类型") else "PARTIAL"))
    if final != s["truth"]:
        misses.append({**s, "rule": rule, "v4b": v4b, "final": final, "failed": failed,
                       "path": path, "reason": reason})

print(f"未命中总数: {len(misses)}")
buckets = Counter()
for m in misses:
    if m["final"] == "DIRECT_SUPPORT" and m["truth"] != "DIRECT_SUPPORT":
        buckets["安全:非DIRECT→DIRECT"] += 1
    elif m["truth"] == "CONTRADICTS":
        buckets["CONTRADICTS漏判"] += 1
    elif m["truth"] == "IRRELEVANT" and m["final"] != "IRRELEVANT":
        buckets["IRRELEVANT漏放"] += 1
    elif m["truth"] == "CONTEXT_ONLY":
        buckets["CONTEXT_ONLY"] += 1
    else:
        buckets["其他"] += 1
print("分桶:", dict(buckets))

for m in misses:
    print("=" * 100)
    print(f"{m['id']} truth={m['truth']} rule={m['rule']} v4b={m['v4b']} final={m['final']}")
    print(f"  claim={m['claim'][:60]}")
    print(f"  title={(m['ev'].get('title') or '')[:50]} | url={(m['ev'].get('url') or '')[:55]}")
    print(f"  path={m['path']} failed={m['failed']}")
    print(f"  reason={m['reason'][:110]}")

(ROOT / "projects" / "_drafts" / "s5_failure_rows.json").write_text(
    json.dumps([{k: (v if not isinstance(v, dict) else v) for k, v in m.items()}
                for m in misses], ensure_ascii=False, indent=2), encoding="utf-8")
print("\nwritten: projects/_drafts/s5_failure_rows.json")
