"""证据语义回归基准集 · 完整性测试（V2.1 阶段 0）。

当前版本只校验数据集本身（真实来源/结构/标注一致性），不调用生产判定逻辑——
语义判定函数（judge_support）在下一阶段实现后，本文件将追加"全 50 样本 truth_label 全中"
的回归断言，并作为全量回归的前置门槛。

数据：tests/data/evidence_regression_r1.json（第一轮 Tavily 真实运行产物，禁止编造）。
"""

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from video_studio.tools.search_provider import _claim_tokens  # noqa: E402

DATA = ROOT / "tests" / "data" / "evidence_regression_r1.json"
EXPECTED_CATS = {"TRUE_DIRECT": 10, "TRUE_PARTIAL": 10, "TRUE_IRRELEVANT": 10,
                 "TRUE_CONTRADICT": 5, "PSEUDO_CONTRADICT": 5, "CONTEXT_ONLY": 5,
                 "KEYWORD_OVERLAP_IRRELEVANT": 5}
VALID_TRUTH = {"DIRECT_SUPPORT", "PARTIAL_SUPPORT", "CONTEXT_ONLY",
               "CONTRADICTS", "IRRELEVANT"}


def overlap_count(claim_text: str, evidence_text: str) -> int:
    tokens = set(_claim_tokens({"text": claim_text}))
    return sum(1 for t in tokens if t in evidence_text)


def main() -> int:
    checks = []

    def check(name, cond, detail=""):
        checks.append((name, cond))
        print(f"{'PASS' if cond else 'FAIL'}  {name} {detail}")

    data = json.loads(DATA.read_text(encoding="utf-8"))
    samples = data["samples"]
    meta = data.get("_meta", {})

    # ---------- 结构与数量 ----------
    check("样本总数 = 50", len(samples) == 50, f"({len(samples)})")
    cats = {}
    for s in samples:
        cats[s["category"]] = cats.get(s["category"], 0) + 1
    check("7 类数量符合规格（10/10/10/5/5/5/5）",
          cats == EXPECTED_CATS, f"({cats})")
    check("样本 id 唯一", len({s["id"] for s in samples}) == 50)
    check("元信息标注来源轮次",
          meta.get("source_round", "").startswith("yongsheng-tavily-r1"))

    # ---------- 字段完整性 ----------
    check("全部样本 claim_text 非空", all(len(s.get("claim_text", "")) >= 4 for s in samples))
    check("全部样本 evidence.text 非空",
          all(len((s["evidence"].get("text") or "")) >= 40 for s in samples),
          f"({sum(1 for s in samples if len((s['evidence'].get('text') or '')) < 40)} 条过短)")
    check("全部样本 truth_label 合法",
          all(s["truth_label"] in VALID_TRUTH for s in samples))
    check("全部样本 provenance 合法",
          all(s["evidence"].get("provenance") in ("stored_round1", "refetch_same_query")
              for s in samples))
    check("全部样本含 rationale（标注理由可审计）",
          all(len(s.get("rationale", "")) >= 10 for s in samples))

    # ---------- 真实来源校验（非编造）：与第一轮数据库逐条比对 ----------
    db_path = ROOT / "projects" / "video_studio.db"
    if db_path.exists():
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        pid = "p_f2215875dd49"
        db_rows = {f"{r['source']}|{r['url']}" for r in conn.execute(
            "SELECT source, url FROM evidence WHERE project_id=?", (pid,))}
        stored = [s for s in samples if s["evidence"].get("provenance") == "stored_round1"]
        matched = sum(1 for s in stored
                      if f"{s['evidence']['source']}|{s['evidence']['url']}" in db_rows)
        check("stored_round1 样本全部可在第一轮数据库找到原文（非编造）",
              matched == len(stored), f"({matched}/{len(stored)})")
        conn.close()
    else:
        print("NOTE  数据库不存在，跳过真实来源比对")

    # ---------- 已知错误案例标注一致性 ----------
    pseudo = [s for s in samples if s["category"] == "PSEUDO_CONTRADICT"]
    check("伪 CONTRADICTS 样本的第一轮系统标签均为 CONTRADICTS",
          all(s["evidence"].get("system_label_r1") == "CONTRADICTS" for s in pseudo),
          f"({[s['evidence'].get('system_label_r1') for s in pseudo]})")
    cont = [s for s in samples if s["category"] == "TRUE_CONTRADICT"]
    check("真 CONTRADICTS 样本使用派生可验证命题（原句多为问句/定义句）",
          all(s["claim_source"] == "derived" for s in cont))
    check("PSEUDO 与 TRUE 样本在 truth_label 上全部区分（不存在'仍判 CONTRADICTS'的伪冲突）",
          all(s["truth_label"] != "CONTRADICTS" for s in pseudo))

    # ---------- 词面重叠性质（辅助校验，非语义判据；统计标题+摘要+正文） ----------
    def full_text(s) -> str:
        e = s["evidence"]
        return " ".join([e.get("title", ""), e.get("snippet", ""), e.get("text", "")])

    kw = [s for s in samples if s["category"] == "KEYWORD_OVERLAP_IRRELEVANT"]
    kw_scores = {s["id"]: overlap_count(s["claim_text"], full_text(s)) for s in kw}
    check("关键词高重叠样本至少 1 个词元字面重叠", all(v >= 1 for v in kw_scores.values()),
          f"({kw_scores})")
    ctx = [s for s in samples if s["category"] == "CONTEXT_ONLY"]
    ctx_scores = {s["id"]: overlap_count(s["claim_text"], full_text(s)) for s in ctx}
    check("CONTEXT_ONLY 样本词面重叠 ≤ 4（个别词出现，非高重叠）",
          all(v <= 4 for v in ctx_scores.values()), f"({ctx_scores})")

    # =====================================================================
    # V2.1 语义层核心断言（阶段 1）：全 50 样本 truth_label 全中，任何 1 条不符即失败。
    # =====================================================================
    from video_studio.tools.semantic_judge import judge_support
    per_cat_hits: dict = {}
    per_cat_total: dict = {}
    misses = []
    for s in samples:
        got = judge_support(s["claim_text"], s["evidence"])
        per_cat_total[s["category"]] = per_cat_total.get(s["category"], 0) + 1
        if got == s["truth_label"]:
            per_cat_hits[s["category"]] = per_cat_hits.get(s["category"], 0) + 1
        else:
            misses.append((s["id"], s["category"], s["truth_label"], got))
    check("语义判定：全 50 样本 truth_label 全中（任何 1 条不符不得合并）",
          len(misses) == 0,
          f"({len(misses)} 未命中: {misses[:5]})")
    for cat in ("TRUE_DIRECT", "TRUE_PARTIAL", "TRUE_IRRELEVANT", "TRUE_CONTRADICT",
                "PSEUDO_CONTRADICT", "CONTEXT_ONLY", "KEYWORD_OVERLAP_IRRELEVANT"):
        check(f"分类全中：{cat}",
              per_cat_hits.get(cat, 0) == per_cat_total.get(cat, 0),
              f"({per_cat_hits.get(cat, 0)}/{per_cat_total.get(cat, 0)})")

    failed = [c for c in checks if not c[1]]
    print(f"\n结果: {len(checks) - len(failed)}/{len(checks)} 通过")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
