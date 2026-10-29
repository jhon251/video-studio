"""4.x Phase 4-E A/B 基准（离线、确定性、可复算）：固定测试集上的检索质量量化。

产出：
  logs/phase4e_ab_results.json   —— 指标定义 + A/B 完整结果 + 逐查询逐候选明细
  logs/phase4e_ab_summary.txt    —— 人类可读摘要（含中文/多语言案例与 FP/FN/UNKNOWN 分析）

用法：python docs/regression_2x/phase4e_ab_benchmark.py [--bench tests/retrieval_bench_v1.json]
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.core.retrieval_quality import (ab_compare, load_retrieval_lexicon,  # noqa: E402
                                                 lexicon_fingerprint)

LOGS = ROOT / "docs" / "regression_2x" / "logs"
LOGS.mkdir(parents=True, exist_ok=True)
LINES = []

# 指标定义（写进结果文件，保证"指标定义 + 完整结果"同时可查）
METRIC_DEFS = {
    "unit": "候选（query × asset）级与查询级两种粒度",
    "TP": "候选素材的语义域 ∈ 该查询的期望域集合（期望域由人工标注、可逐条核对 label_basis）",
    "FP": "候选素材的语义域 ∉ 期望域；或查询**期望无结果**却返回了候选（假匹配）",
    "UNKNOWN": "查询被标记为歧义（如 pico=品牌/地名）：命中一律记 UNKNOWN，**不计 TP**——『检索到候选 ≠ 语义正确』",
    "FN": "查询级：期望域中没有任何域被 TP 覆盖（FN_domains 逐条列出缺失的域）",
    "precision_strict": "TP / (TP + FP + UNKNOWN)",
    "precision_excl_unknown": "TP / (TP + FP)（把 UNKNOWN 排除在分母外，作为参考口径）",
    "unknown_rate": "UNKNOWN / (TP + FP + UNKNOWN)",
    "domain_hit_rate": "非歧义且期望域非空的查询中，至少命中 1 个 TP 的比例",
    "top1_correct_rate": "同上查询中，排名第 1 的候选为 TP 的比例",
    "empty_correct_rate": "期望无结果的查询中，确实返回空候选的比例",
    "weak_result": "期望域非空但一条候选都没有（检索过弱）",
    "note": "A = v1（既有 kw_tokens+score，冻结未改）；B = v2（4-E 新增：多语言归一 + 概念扩展 + 词边界匹配）。两侧由同一段代码计算。",
}


def say(s):
    print(s, flush=True)
    LINES.append(str(s))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bench", default=str(ROOT / "tests" / "retrieval_bench_v1.json"))
    args = ap.parse_args()
    bench_path = Path(args.bench)
    bench = json.loads(bench_path.read_text(encoding="utf-8"))
    lex = load_retrieval_lexicon()
    k = int(bench.get("k") or 5)
    res = ab_compare(bench["queries"], bench["corpus"], k=k, lex=lex)
    payload = {
        "phase": "4-E",
        "bench": {"path": str(bench_path), "version": bench.get("version"),
                  "sha256": hashlib.sha256(bench_path.read_bytes()).hexdigest(),
                  "queries": len(bench["queries"]), "corpus": len(bench["corpus"]), "k": k},
        "lexicon": {"version": lex.get("version"), "sha256": lex.get("sha256"),
                    "fingerprint": lexicon_fingerprint(lex)},
        "metric_definitions": METRIC_DEFS,
        "results": res,
    }
    (LOGS / "phase4e_ab_results.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    say("=== 4.x Phase 4-E 检索质量 A/B（固定测试集 {} / {} 查询 / {} 语料 / k={}）===".format(
        bench.get("version"), len(bench["queries"]), len(bench["corpus"]), k))
    say("词典 {} sha256={}…".format(lex.get("version"), str(lex.get("sha256"))[:16]))
    for side, label in (("A_v1_frozen", "A = v1（既有实现，冻结）"),
                        ("B_v2_improved", "B = v2（4-E 改进）")):
        s = res[side]["summary"]
        c, q = s["candidate_level"], s["query_level"]
        say("\n[{}]".format(label))
        say("  候选级：TP={} FP={} UNKNOWN={} | precision_strict={} precision_excl_unknown={} unknown_rate={}".format(
            c["TP"], c["FP"], c["UNKNOWN"], c["precision_strict"], c["precision_excl_unknown"],
            c["unknown_rate"]))
        say("  查询级：域命中 {}/{} = {} | top1 正确 {} | 空结果正确率 {} | FN 查询={} | 假匹配查询={}".format(
            q["domain_hit_queries"], q["domain_hit_queries"] + len(q["fn_queries"]),
            q["domain_hit_rate"], q["top1_correct_rate"], q["empty_correct_rate"],
            q["fn_queries"], q["fake_match_queries"]))
        say("  分组：{}".format(json.dumps(s["by_group"], ensure_ascii=False)))
    say("\n[改进幅度 B-A] {}".format(json.dumps(res["delta_B_minus_A"], ensure_ascii=False)))
    say("\n[逐查询明细] query | A(tp/fp/unk/n) | B(tp/fp/unk/n) | 期望域 | B 命中域顺序")
    rows_a = {r["query_id"]: r for r in res["A_v1_frozen"]["rows"]}
    for rb in res["B_v2_improved"]["rows"]:
        ra = rows_a[rb["query_id"]]
        say("  {:8s} {:26s} | {}/{}/{}/{} | {}/{}/{}/{} | {} | {}".format(
            rb["query_id"], rb["text"][:24], ra["TP"], ra["FP"], ra["UNKNOWN"], ra["retrieved_n"],
            rb["TP"], rb["FP"], rb["UNKNOWN"], rb["retrieved_n"],
            ",".join(rb["expected_domains"]) or "-",
            ",".join(c["domain"] for c in rb["retrieved"]) or "-"))
    say("\n[UNKNOWN 与假匹配（不得算作正确）]")
    for rb in res["B_v2_improved"]["rows"]:
        if rb["UNKNOWN"]:
            say("  {} 歧义查询：{} 个候选全部记 UNKNOWN（歧义形式 {}）".format(
                rb["query_id"], rb["UNKNOWN"],
                sorted({f for c in rb["retrieved"] for f in c["ambiguous_forms"]})))
    for rb in res["B_v2_improved"]["rows"]:
        if rb["empty_correct"]:
            say("  {} 期望无结果 → 空候选（正确）".format(rb["query_id"]))
    (LOGS / "phase4e_ab_summary.txt").write_text("\n".join(LINES) + "\n", encoding="utf-8")
    print("\nwritten", LOGS / "phase4e_ab_results.json")
    print("written", LOGS / "phase4e_ab_summary.txt")


if __name__ == "__main__":
    main()
