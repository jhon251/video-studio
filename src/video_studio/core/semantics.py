"""4.x Phase 4-B：离线、只读、三态语义验证器（`MATCH` / `MISMATCH` / `UNKNOWN`）。

用途：核验"每个镜头**实际选中的素材**与"该镜头旁白/镜头描述"在**语义域**上是否一致，并把
判定所依据的**信号**逐条记录下来，供人工复核（4-C 的人审候选替换以本模块输出为输入）。

设计约束（授权边界）：
  · **离线**：不访问网络；不调用 LLM；不读数据库（调用方以只读方式取数后传入）；
  · **只读**：不修改任何状态/产物/数据库；本模块只做纯函数计算并返回结果；
  · **可解释/可复算**：判定由**类别式规则**给出（域交集 / 域不相交 / 同形词义冲突），
    **没有可调数值阈值**；同一输入必然得到同一输出（无随机、无时间戳）；
  · **不猜测**：无法判断时必须给 `UNKNOWN`，**绝不当作 `MATCH`**。

判定规则 v1（按顺序，先命中先返回；规则 ID 写入结果）：
  R0 `NO_ASSET`           镜头没有选中素材（占位/纯色底）→ `UNKNOWN`
  R1 `MISSING_INPUT`      旁白文本或素材名为空 → `UNKNOWN`
  R2 `SENSE_CONFLICT`     双方共享的**同形词**在两侧被解析为**不同词义** → `MISMATCH`
  R3 `DOMAIN_DISJOINT`    双方都识别出语义域、两域集合**不相交**、且**没有词级（≥3 字符整词）桥** → `MISMATCH`
  R4 `DOMAIN_SUPPORT`     双方语义域**有交集** → `MATCH`
  R5 `NO_POSITIVE_SUPPORT` 其余情形（覆盖不足等）→ `UNKNOWN`

词级桥 vs 字面碎片：匹配器使用的是"CJK 二元组 + 单字 + 拉丁词"的混合词表，其中**纯拉丁 2 字符
碎片**（如 `es`/`qu`）会落进无关单词内部（实测 `Azores` 命中 `es`）——本模块把这类记为
`fragment_bridge`（噪声），**不作为语义支持**，并在证据里显式列出。
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

LEXICON_PATH = Path(__file__).with_name("lexicons") / "semantics_v1.json"

# 匹配口径与生产链保持一致（只读导入；不修改该模块）
from ..agents.retrieval.agent import kw_tokens  # noqa: E402


# ---------------- 词典加载 ----------------
def load_lexicon(path: str | Path | None = None) -> dict:
    """加载语义词典（v1）；返回 dict，并附带 `sha256` 与 `path` 以便版本化追溯。"""
    p = Path(path) if path else LEXICON_PATH
    raw = p.read_bytes()
    data = json.loads(raw.decode("utf-8"))
    data["sha256"] = hashlib.sha256(raw).hexdigest()
    data["path"] = str(p)
    ambiguous = {k.lower() for k in (data.get("ambiguous") or {})}
    # 同形词本身不计入任何域（避免"pico 给地理域投票"这类自相矛盾）
    domains: dict[str, dict[str, list[str]]] = {}
    for dom, spec in (data.get("domains") or {}).items():
        zh = [k for k in (spec.get("zh") or []) if k.strip()]
        latin = [k.lower() for k in (spec.get("latin") or [])
                 if k.strip() and k.lower() not in ambiguous]
        domains[dom] = {"zh": zh, "latin": latin}
    data["domains_resolved"] = domains
    return data


def _has_latin_word(text: str, needle: str) -> bool:
    """整词/整短语匹配（大小写不敏感；两侧不允许再接字母）。"""
    return re.search(r"(?<![a-z]){}(?![a-z])".format(re.escape(needle.lower())),
                     text.lower()) is not None


def domain_votes(text: str, lexicon: dict) -> dict[str, list[str]]:
    """按域统计命中关键词（zh 子串 / latin 整词）；返回 {domain: [命中的关键词...]}。

    **可解释**：命中的具体关键词全部返回，便于人工核对"为什么给了这个域"。
    """
    t = str(text or "")
    tl = t.lower()
    out: dict[str, list[str]] = {}
    for dom, spec in (lexicon.get("domains_resolved") or {}).items():
        hits = [k for k in spec["zh"] if k in t]
        hits += [k for k in spec["latin"] if _has_latin_word(tl, k)]
        if hits:
            out[dom] = hits
    return out


def resolve_sense(token: str, text: str, lexicon: dict) -> dict:
    """解析同形词在给定文本中的词义（凭 sense markers）。

    返回 {"sense": str|None, "markers": [...], "scores": {sense: n}}；无标记或并列最高 → sense=None
    （**不猜**：解析不出就不参与冲突判定）。
    """
    spec = (lexicon.get("ambiguous") or {}).get(token.lower())
    if not spec:
        return {"sense": None, "markers": [], "scores": {}}
    tl = str(text or "").lower()
    scores: dict[str, int] = {}
    markers: dict[str, list[str]] = {}
    for sense, body in spec.items():
        ms = [m for m in (body.get("markers") or [])
              if m.strip() and m.lower() != token.lower()
              and (_has_latin_word(tl, m) if re.search(r"[a-z]", m, re.I) else m in str(text or ""))]
        if ms:
            scores[sense] = len(ms)
            markers[sense] = ms
    if not scores:
        return {"sense": None, "markers": [], "scores": {}}
    best = max(scores.values())
    top = sorted([s for s, v in scores.items() if v == best])
    if len(top) != 1:
        return {"sense": None, "markers": [], "scores": scores}      # 并列 → 不判定
    return {"sense": top[0], "markers": markers[top[0]], "scores": scores}


# ---------------- 桥（共享词）分类 ----------------
def classify_bridge(query_text: str, asset_name: str, lexicon: dict) -> dict:
    """把"匹配器用到的共享词"分成：词级桥（语义支持）与字面碎片（噪声）。"""
    qt = kw_tokens(query_text)
    at = kw_tokens(asset_name)
    shared = sorted(qt & at)
    words, fragments, cjk = [], [], []
    for tok in shared:
        if len(tok) >= 3 and re.fullmatch(r"[a-z0-9]+", tok):
            words.append(tok)                       # 拉丁整词（kw_tokens 的拉丁词 ≥3 字符）
        elif len(tok) == 2 and re.fullmatch(r"[a-z]{2}", tok):
            fragments.append(tok)                   # 纯拉丁 2 字符碎片（可落在无关单词内部）
        else:
            cjk.append(tok)                          # CJK 二元组/单字
    ambiguous_shared = [t for t in shared if t in (lexicon.get("ambiguous") or {})]
    return {"shared_tokens": shared, "word_bridge": words, "fragment_bridge": fragments,
            "cjk_bridge": cjk, "ambiguous_bridge": ambiguous_shared}


# ---------------- 单镜头判定 ----------------
def verify_scene(scene_id: str, query_text: str, asset_name: str | None,
                 lexicon: dict, narration_text: str | None = None) -> dict:
    """对一个镜头给出三态判定 + 完整证据（纯函数）。"""
    base = {"scene_id": scene_id, "verdict": "UNKNOWN", "rule": None, "reason": "",
            "signals": {}}
    if not asset_name:
        return {**base, "rule": "R0_NO_ASSET", "reason": "该镜头没有选中素材（占位/纯色底），无语义可比"}
    q = str(query_text or "").strip()
    a = str(asset_name).strip()
    if not q or not a:
        return {**base, "rule": "R1_MISSING_INPUT", "reason": "旁白/素材名为空，无法判定"}

    bridge = classify_bridge(q, a, lexicon)
    nar_domains = domain_votes(q, lexicon)
    ast_domains = domain_votes(a, lexicon)
    senses = []
    for tok in bridge["ambiguous_bridge"]:
        n = resolve_sense(tok, q, lexicon)
        s = resolve_sense(tok, a, lexicon)
        senses.append({"token": tok, "query_sense": n["sense"], "asset_sense": s["sense"],
                       "query_markers": n["markers"], "asset_markers": s["markers"]})
    conflict = [x for x in senses
                if x["query_sense"] and x["asset_sense"] and x["query_sense"] != x["asset_sense"]]
    signals = {
        "word_bridge": bridge["word_bridge"],
        "fragment_bridge": bridge["fragment_bridge"],
        "cjk_bridge": bridge["cjk_bridge"][:12],
        "ambiguous_bridge": bridge["ambiguous_bridge"],
        "query_domains": {k: v for k, v in sorted(nar_domains.items())},
        "asset_domains": {k: v for k, v in sorted(ast_domains.items())},
        "domain_intersection": sorted(set(nar_domains) & set(ast_domains)),
        "domain_disjoint": bool(nar_domains and ast_domains
                                and not (set(nar_domains) & set(ast_domains))),
        "senses": senses,
        "lexicon_version": lexicon.get("version"), "lexicon_sha256": lexicon.get("sha256"),
        "inputs": {"query_chars": len(q), "asset_chars": len(a),
                   "narration_chars": (len(str(narration_text)) if narration_text else None)},
    }
    if conflict:
        c = conflict[0]
        return {**base, "verdict": "MISMATCH", "rule": "R2_SENSE_CONFLICT",
                "reason": "共享同形词 {!r} 两侧词义不同：旁白侧 {}（标记 {}）vs 素材侧 {}（标记 {}）"
                          .format(c["token"], c["query_sense"], c["query_markers"][:3],
                                  c["asset_sense"], c["asset_markers"][:3]),
                "signals": signals}
    if signals["domain_disjoint"] and not bridge["word_bridge"]:
        return {**base, "verdict": "MISMATCH", "rule": "R3_DOMAIN_DISJOINT",
                "reason": "双方语义域不相交（旁白 {} vs 素材 {}），且没有词级桥"
                          "（共享词只有字面碎片 {}）".format(
                              sorted(nar_domains), sorted(ast_domains),
                              bridge["fragment_bridge"][:6] or "无"),
                "signals": signals}
    if signals["domain_intersection"]:
        return {**base, "verdict": "MATCH", "rule": "R4_DOMAIN_SUPPORT",
                "reason": "双方语义域有交集 {}（旁白命中 {} / 素材命中 {}）".format(
                    signals["domain_intersection"], sorted(nar_domains), sorted(ast_domains)),
                "signals": signals}
    return {**base, "verdict": "UNKNOWN", "rule": "R5_NO_POSITIVE_SUPPORT",
            "reason": "覆盖不足或无正向支持（旁白域 {} / 素材域 {} / 词级桥 {}）——不猜".format(
                sorted(nar_domains), sorted(ast_domains), bridge["word_bridge"] or "无"),
            "signals": signals}


# ---------------- 项目级装配（调用方传入只读取到的数据） ----------------
def verify_scenes(items: list[dict], lexicon: dict | None = None) -> dict:
    """items: [{"scene_id", "query_text", "asset_name", "narration", "asset": {...}}] → 汇总结果。"""
    lex = lexicon or load_lexicon()
    scenes = []
    for it in items:
        v = verify_scene(it.get("scene_id") or "?", it.get("query_text") or "",
                         it.get("asset_name"), lex, narration_text=it.get("narration"))
        v["asset"] = it.get("asset") or {}
        scenes.append(v)
    counts = {"MATCH": 0, "MISMATCH": 0, "UNKNOWN": 0}
    for s in scenes:
        counts[s["verdict"]] = counts.get(s["verdict"], 0) + 1
    return {
        "version": lex.get("version"), "lexicon_sha256": lex.get("sha256"),
        "policy": "offline-deterministic-v1（类别式规则，无数值阈值）",
        "scene_count": len(scenes), "counts": counts,
        "scenes": scenes,
        "summary": "MATCH={MATCH} MISMATCH={MISMATCH} UNKNOWN={UNKNOWN}".format(**counts),
    }
