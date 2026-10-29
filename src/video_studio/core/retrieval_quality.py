"""4.x Phase 4-E：检索质量量化与改进（**纯函数、离线、确定性、默认不启用**）。

本模块只做两件事，且都**不改变既有判定**：

  1. **打分器 v2**（`score_v2`）：在既有 `kw_tokens` + `score`（v1，冻结不动）之外提供一套
     "多语言归一 + 概念扩展 + 词边界匹配"的打分，用于 A/B 对比与量化提升。
     · 中文：二元组 + 单字（去虚词），并可按词典把中文词映射到**概念**；
     · 拉丁：小写 + 简单复数归一，**按词边界匹配**（不允许子串桥接——4-B 已发现 `es`⊂`Azores` 这类碎片桥缺陷）；
     · 2 字符缩写（`vr`/`ar`/`xr`）在 v1 里被丢弃（要求 ≥3 字符），v2 只要命中词典就保留；
     · **不做翻译推理**：所有扩展都来自 `lexicons/retrieval_synonyms_v1.json` 这张可审计的表。
  2. **指标计算**（`evaluate`）：在**固定测试集**上按查询逐条给出 TP / FP / UNKNOWN / FN
     与查询级命中率，A/B 两侧用同一套代码计算，保证可复算。

**关键纪律**：命中候选 ≠ 语义正确。因此
  · 命中"歧义形式"（如 `pico` = 品牌/地名）的候选一律记 **UNKNOWN**，不计 TP；
  · 期望"无结果"的查询若返回了候选，一律记 **FP（假匹配）**；
  · 语义是否正确仍由 4-B 验证器与许可门禁决定，检索层只负责"候选质量"。
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

LEXICON_PATH = Path(__file__).resolve().parent / "lexicons" / "retrieval_synonyms_v1.json"

# 中文虚词/停用词：v1 会把"的/了/在"这类单字也算 1 分，产生噪声命中；
# v2 在**单字**层去掉它们（二元组保留，因为二元组已含上下文）。
CJK_STOPWORDS = frozenset(
    "的 了 是 在 和 与 及 或 也 都 就 而 并 被 把 从 到 对 为 以 之 其 中 上 下 个 些 一 二 三 时 后 前 里 外 "
    "我 你 他 她 它 们 这 那 有 无 不 很 更 最 会 能 可 要 将 已 正 又 还 只 但 因 所 如 若 则 且 等 各 该 此".split())

_LATIN_RE = re.compile(r"[A-Za-z][A-Za-z0-9._\-]*")
_CJK_RE = re.compile(r"[\u4e00-\u9fff]+")

_LEX_CACHE: dict = {}


def load_retrieval_lexicon(path: str | Path | None = None) -> dict:
    """加载词典（带 version/sha256/索引），进程内缓存；文件缺失 → 抛 FileNotFoundError（不静默降级）。"""
    p = Path(path) if path else LEXICON_PATH
    key = str(p)
    if key in _LEX_CACHE:
        return _LEX_CACHE[key]
    raw = p.read_bytes()
    data = json.loads(raw.decode("utf-8"))
    concepts = data.get("concepts") or []
    zh2c: dict[str, list[str]] = {}
    lat2c: dict[str, list[str]] = {}
    domain_of: dict[str, str] = {}
    for c in concepts:
        cid = str(c.get("id"))
        domain_of[cid] = str(c.get("domain") or cid)
        for form in c.get("zh") or []:
            zh2c.setdefault(str(form), []).append(cid)
        for form in c.get("latin") or []:
            lat2c.setdefault(str(form).lower(), []).append(cid)
    data["_index"] = {"zh": zh2c, "latin": lat2c, "domain_of": domain_of}
    data["sha256"] = hashlib.sha256(raw).hexdigest()
    data["path"] = str(p)
    _LEX_CACHE[key] = data
    return data


def lexicon_fingerprint(lex: dict) -> str:
    return "{}|{}".format(lex.get("version"), str(lex.get("sha256"))[:16])


# ---------------- 词形归一 ----------------
def normalize_latin(token: str) -> str:
    """小写 + 去首尾标点 + **简单复数归一**。

    规则（机械、保守）：
      · `…ies` → `…y`（policies→policy）
      · `…(s|x|z|ch|sh)es` → 去 `es`（boxes→box / watches→watch）
      · 其余 `…s`（非 `ss`）→ 去 `s`（headsets→headset / goggles→goggle）
    """
    t = str(token or "").strip().strip("._-").lower()
    if len(t) > 4 and t.endswith("ies"):
        return t[:-3] + "y"
    if len(t) > 3 and t.endswith("es") and t[:-2].endswith(("s", "x", "z", "ch", "sh")):
        return t[:-2]
    if len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
        return t[:-1]
    return t


def tokens_v2(text: str) -> dict:
    """v2 分词：CJK 二元组 + 非虚词单字；拉丁词（≥2 字符）归一化。"""
    raw = str(text or "")
    cjk_runs = _CJK_RE.findall(raw)
    bigrams: set[str] = set()
    chars: set[str] = set()
    for run in cjk_runs:
        for i in range(len(run) - 1):
            bigrams.add(run[i:i + 2])
        for ch in run:
            if ch not in CJK_STOPWORDS:
                chars.add(ch)
    latin = set()
    for m in _LATIN_RE.finditer(raw):
        tok = normalize_latin(m.group(0))
        if len(tok) >= 2:
            latin.add(tok)
    return {"cjk_bigrams": bigrams, "cjk_chars": chars, "latin": latin}


def _word_boundary_hit(form: str, hay: str) -> bool:
    """拉丁形式必须**按词边界**命中（防止 `es` 命中 `Azores` 这类碎片桥）。"""
    if not form:
        return False
    return re.search(r"(?<![a-z0-9]){}(?![a-z0-9])".format(re.escape(form)), hay) is not None


def concepts_for_text(text: str, lex: dict) -> dict:
    """把文本映射到概念：返回 {concept_id: {"zh_hits": [...], "latin_hits": [...], "ambiguous": [...]}}"""
    idx = lex["_index"]
    toks = tokens_v2(text)
    hay = str(text or "").lower()
    out: dict[str, dict] = {}
    for form, cids in idx["zh"].items():
        if form in str(text or ""):
            for cid in cids:
                out.setdefault(cid, {"zh_hits": [], "latin_hits": [], "ambiguous": []})
                out[cid]["zh_hits"].append(form)
    for tok in sorted(toks["latin"]):
        for cid in idx["latin"].get(tok, []):
            out.setdefault(cid, {"zh_hits": [], "latin_hits": [], "ambiguous": []})
            out[cid]["latin_hits"].append(tok)
    # 多词拉丁短语（如 "virtual reality"）单独匹配
    for form, cids in idx["latin"].items():
        if " " in form and _word_boundary_hit(form, hay):
            for cid in cids:
                out.setdefault(cid, {"zh_hits": [], "latin_hits": [], "ambiguous": []})
                out[cid]["latin_hits"].append(form)
    amb = lex.get("ambiguous_forms") or {}
    for cid, hits in out.items():
        for form in list(hits["zh_hits"]) + list(hits["latin_hits"]):
            if form in amb:
                hits["ambiguous"].append(form)
    return out


def score_v2(hay: str, query_text: str, lex: dict | None = None) -> dict:
    """v2 打分：返回 {score, concepts, matched, ambiguous}。

    权重（**固定、可审计，未做调参**）：
      中文二元组命中 +2；中文单字命中 +1；拉丁单词命中 +2；拉丁多词短语命中 +4；
      概念命中额外 +3（同一概念只加一次）。
    歧义形式正常计分，但会在 `ambiguous` 中列出（评测侧据此记 UNKNOWN）。
    """
    lx = lex or load_retrieval_lexicon()
    hay_l = str(hay or "").lower()
    qtoks = tokens_v2(query_text)
    q_concepts = concepts_for_text(query_text, lx)
    hay_concepts = concepts_for_text(hay, lx)
    score, matched, ambiguous = 0, [], []
    for bg in sorted(qtoks["cjk_bigrams"]):
        if bg in hay_l:
            score += 2
            matched.append(bg)
    for ch in sorted(qtoks["cjk_chars"]):
        if ch in hay_l:
            score += 1
            matched.append(ch)
    for tok in sorted(qtoks["latin"]):
        if _word_boundary_hit(tok, hay_l):
            score += 2
            matched.append(tok)
    for cid in sorted(q_concepts):
        hhits = hay_concepts.get(cid)
        if not hhits:
            continue
        score += 3                                   # 概念命中（同义/跨语言的主通道）
        if any(" " in f for f in hhits["latin_hits"]):
            score += 4                               # 命中多词短语：更具体
        matched.append("concept:" + cid)
        for form in list(q_concepts[cid]["latin_hits"]) + list(q_concepts[cid]["zh_hits"]):
            if form in (lx.get("ambiguous_forms") or {}):
                ambiguous.append(form)
        for form in list(hhits["latin_hits"]) + list(hhits["zh_hits"]):
            if form in (lx.get("ambiguous_forms") or {}):
                ambiguous.append(form)
    return {"score": score, "concepts": sorted(q_concepts), "matched": matched,
            "ambiguous": sorted(set(ambiguous)),
            "lexicon": lexicon_fingerprint(lx)}


def expand_query_latin(text: str, lex: dict | None = None, limit: int = 3) -> list[str]:
    """中文（或缺少拉丁词）的查询 → 由概念表给出**拉丁查询串**（供 provider 查询阶梯使用）。

    纯查表：概念 → 该概念的拉丁规范形式（多词优先，更精确）。**不做翻译推理**。
    返回按"具体程度"排序的查询串（多词短语优先），最多 `limit` 条。
    """
    lx = lex or load_retrieval_lexicon()
    concepts = concepts_for_text(text, lx)
    if not concepts:
        return []
    idx = lx["_index"]
    phrases: list[str] = []
    for cid in sorted(concepts):
        forms = [f for f in idx["latin"] if cid in idx["latin"][f]]
        multi = sorted([f for f in forms if " " in f], key=len, reverse=True)
        single = sorted([f for f in forms if " " not in f and f not in ("vr", "ar", "xr", "mr")])
        for f in (multi + single)[:2]:
            if f not in phrases:
                phrases.append(f)
    return phrases[:max(1, int(limit))]


# ---------------- v1（冻结）打分器引用 ----------------
def score_v1(hay: str, query_text: str) -> dict:
    """既有实现（`agents/retrieval/agent.py` 的 kw_tokens + score）：**原样调用，不改一行**。"""
    from ..agents.retrieval.agent import kw_tokens, score
    kw = kw_tokens(query_text)
    return {"score": int(score(hay, kw)), "matched": [], "concepts": [], "ambiguous": [],
            "lexicon": "v1-frozen", "keywords": sorted(kw)[:24]}


SCORERS = {"v1": score_v1, "v2": score_v2}


def retrieval_settings(config: dict | None) -> dict:
    """读 `tools.retrieval` 配置（**缺省 = v1 + 不扩展**，即既有行为）。

    未知 `scoring` 取值 → 保守回退 `v1`（不因拼写错误改变行为）。
    """
    rq = ((config or {}).get("tools") or {}).get("retrieval") or {}
    scoring = str(rq.get("scoring") or "v1")
    if scoring not in SCORERS:
        scoring = "v1"
    return {"scoring": scoring,
            "query_expansion": bool(rq.get("query_expansion")),
            "source": "tools.retrieval" if rq else "default(v1)",
            "known_scorers": sorted(SCORERS)}


# ---------------- 指标（TP / FP / UNKNOWN / FN）----------------
def classify_candidate(*, domain: str | None, expected: list[str], ambiguous: bool) -> str:
    """单个候选的判定：TP / FP / UNKNOWN（**UNKNOWN 不得算作 TP**）。"""
    if ambiguous:
        return "UNKNOWN"
    if not expected:
        return "FP"                      # 期望无结果却给出候选 = 假匹配
    if domain and domain in expected:
        return "TP"
    return "FP"                          # 域不符 = 假阳性


def evaluate(queries: list[dict], corpus: list[dict], *, scorer: str = "v1", k: int = 5,
             lex: dict | None = None) -> dict:
    """在固定测试集上计算指标（A/B 同一代码路径，结果可复算）。

    输出（逐查询明细 + 汇总）：TP/FP/UNKNOWN 计数、precision（含/不含 UNKNOWN）、
    查询级 `domain_hit`（期望域被命中）、`empty_correct`（期望空 → 确实空）、FN 查询清单。
    """
    fn = SCORERS[scorer]
    rows = []
    tp = fp = unk = 0
    for q in queries:
        expected = list(q.get("expected_domains") or [])
        scored = []
        for asset in corpus:
            hay = "{} {}".format(asset.get("name", ""), asset.get("ext", ""))
            r = fn(hay, q["text"]) if scorer == "v1" else fn(hay, q["text"], lex)
            if int(r.get("score") or 0) > 0:
                scored.append({"asset_id": asset["asset_id"], "name": asset.get("name"),
                               "domain": asset.get("domain"), "score": int(r["score"]),
                               "concepts": r.get("concepts") or [],
                               "ambiguous_forms": r.get("ambiguous") or [],
                               "verdict": classify_candidate(
                                   domain=asset.get("domain"), expected=expected,
                                   ambiguous=bool(q.get("ambiguous")))})
        scored.sort(key=lambda x: (-x["score"], x["asset_id"]))
        top = scored[:k]
        n_tp = sum(1 for c in top if c["verdict"] == "TP")
        n_fp = sum(1 for c in top if c["verdict"] == "FP")
        n_un = sum(1 for c in top if c["verdict"] == "UNKNOWN")
        tp += n_tp
        fp += n_fp
        unk += n_un
        covered = {c["domain"] for c in top if c["verdict"] == "TP"}
        missing = [d for d in expected if d not in covered]
        empty_correct = bool(not expected and not top)
        rows.append({"query_id": q["id"], "group": q.get("group"), "text": q["text"],
                     "expected_domains": expected, "ambiguous": bool(q.get("ambiguous")),
                     "retrieved": top, "retrieved_n": len(top),
                     "TP": n_tp, "FP": n_fp, "UNKNOWN": n_un,
                     "top1_verdict": (top[0]["verdict"] if top else None),
                     "FN_domains": missing, "domain_hit": bool(n_tp > 0),
                     "empty_correct": empty_correct,
                     "weak_result": bool(expected and n_tp == 0 and not top)})
    judged = [r for r in rows if not r["ambiguous"]]
    with_expected = [r for r in judged if r["expected_domains"]]
    empty_q = [r for r in judged if not r["expected_domains"]]
    summary = {
        "scorer": scorer, "k": k, "queries": len(rows),
        "candidate_level": {"TP": tp, "FP": fp, "UNKNOWN": unk,
                            "precision_strict": round(tp / (tp + fp + unk), 4) if (tp + fp + unk) else None,
                            "precision_excl_unknown": round(tp / (tp + fp), 4) if (tp + fp) else None,
                            "unknown_rate": round(unk / (tp + fp + unk), 4) if (tp + fp + unk) else None},
        "query_level": {
            "domain_hit_queries": sum(1 for r in with_expected if r["domain_hit"]),
            "domain_hit_rate": round(sum(1 for r in with_expected if r["domain_hit"])
                                     / len(with_expected), 4) if with_expected else None,
            "top1_correct_queries": sum(1 for r in with_expected if r["top1_verdict"] == "TP"),
            "top1_correct_rate": round(sum(1 for r in with_expected if r["top1_verdict"] == "TP")
                                       / len(with_expected), 4) if with_expected else None,
            "fn_queries": [r["query_id"] for r in with_expected if not r["domain_hit"]],
            "weak_result_queries": [r["query_id"] for r in judged if r["weak_result"]],
            "fake_match_queries": [r["query_id"] for r in empty_q if r["retrieved_n"] > 0],
            "empty_correct_rate": round(sum(1 for r in empty_q if r["empty_correct"])
                                        / len(empty_q), 4) if empty_q else None},
        "by_group": {},
    }
    for g in sorted({r["group"] for r in rows if r["group"]}):
        grp = [r for r in rows if r["group"] == g]
        summary["by_group"][g] = {
            "queries": len(grp),
            "TP": sum(r["TP"] for r in grp), "FP": sum(r["FP"] for r in grp),
            "UNKNOWN": sum(r["UNKNOWN"] for r in grp),
            "domain_hit_rate": round(sum(1 for r in grp if r["domain_hit"]) / len(grp), 4)}
    return {"summary": summary, "rows": rows}


def ab_compare(queries: list[dict], corpus: list[dict], *, k: int = 5,
               lex: dict | None = None) -> dict:
    """同一固定测试集上跑 A（v1 冻结）与 B（v2 改进），返回两侧结果与差值。"""
    lx = lex or load_retrieval_lexicon()
    a = evaluate(queries, corpus, scorer="v1", k=k, lex=lx)
    b = evaluate(queries, corpus, scorer="v2", k=k, lex=lx)
    sa, sb = a["summary"], b["summary"]
    delta = {
        "TP": sb["candidate_level"]["TP"] - sa["candidate_level"]["TP"],
        "FP": sb["candidate_level"]["FP"] - sa["candidate_level"]["FP"],
        "UNKNOWN": sb["candidate_level"]["UNKNOWN"] - sa["candidate_level"]["UNKNOWN"],
        "domain_hit_rate": (None if sa["query_level"]["domain_hit_rate"] is None
                            or sb["query_level"]["domain_hit_rate"] is None
                            else round(sb["query_level"]["domain_hit_rate"]
                                       - sa["query_level"]["domain_hit_rate"], 4)),
        "top1_correct_rate": (None if sa["query_level"]["top1_correct_rate"] is None
                              or sb["query_level"]["top1_correct_rate"] is None
                              else round(sb["query_level"]["top1_correct_rate"]
                                         - sa["query_level"]["top1_correct_rate"], 4)),
        "precision_strict": (None if sa["candidate_level"]["precision_strict"] is None
                             or sb["candidate_level"]["precision_strict"] is None
                             else round(sb["candidate_level"]["precision_strict"]
                                        - sa["candidate_level"]["precision_strict"], 4)),
        "empty_correct_rate": (None if sa["query_level"]["empty_correct_rate"] is None
                               or sb["query_level"]["empty_correct_rate"] is None
                               else round(sb["query_level"]["empty_correct_rate"]
                                          - sa["query_level"]["empty_correct_rate"], 4)),
    }
    return {"lexicon": {"version": lx.get("version"), "sha256": lx.get("sha256")},
            "A_v1_frozen": a, "B_v2_improved": b, "delta_B_minus_A": delta}
