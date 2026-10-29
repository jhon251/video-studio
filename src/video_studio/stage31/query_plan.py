"""Stage 3.1.4 语义查询规划层 v2（修复版）。

A. 内容词提取：逐字停用词过滤 → 连续内容串（≤6字整段保留，更长则切 2-4 字 n-gram）；
   删除 discourse filler；拉丁词保留完整 token；禁止整句作主查询。
B. 本地 zh→en 翻译：Helsinki-NLP/opus-mt-zh-en（离线、懒加载、缓存；失败不阻塞其他路由；
   query 记录原文+译文）。
C. 每条 query 记录来源（source/type/priority）。
"""
from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

import requests

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "120")

WIKIDATA_API = "https://www.wikidata.org/w/api.php"
UA = {"User-Agent": "video-studio-3.1.4/0.2 (material research; contact: local)"}

# 多字停用短语（整词替换，避免单字误伤"自由/自学"等）
STOPWORDS_MULTI = ["自己", "没有", "不是", "就是", "什么", "怎么", "为什么", "这么", "那么",
                   "这个", "那个", "一个", "一种", "一些", "一直", "已经", "开始", "最后",
                   "然后", "其实", "只是", "可能", "可以", "应该", "越来越", "变成", "甚至",
                   "终于", "真的", "一点", "一下", "整个", "剩下", "真正", "别人", "每个",
                   "任何", "如果", "因为", "所以", "但是", "然而", "而且", "并且", "虽然",
                   "于是", "问题", "事情", "东西", "时候", "还有", "还有", "其实", "而且"]

# 单字纯功能字（仅这些允许逐字删除）
CHAR_STOP = set("的了在你我他她它这就都也还把被让从到和与或而但如因所怎么什上下里外前后左右中内外")

EMOTION_POOL = {
    "en": ["city skyline night", "silhouette person window", "lonely street lamp night"],
    "zh": ["城市 夜景", "孤独 背影"],
}

MT_DIR = Path(__file__).resolve().parents[3] / "models" / "mt" / "opus-mt-zh-en"
_mt_model = None
_mt_tok = None


def extract_phrases(narration: str, top: int = 6) -> list[dict]:
    """内容词/短语提取。返回 [{text, source: 'content_phrase'|'latin', priority}]。"""
    parts = re.split(r"[，。！？；：、\s—…]+", narration or "")
    out, seen = [], set()
    for p in parts:
        p = p.strip()
        if not p:
            continue
        for l in re.findall(r"[A-Za-z][A-Za-z0-9\-\.]{1,}", p):
            if l.lower() not in seen:
                seen.add(l.lower())
                out.append({"text": l, "source": "latin", "priority": 1})
        s = p
        for w in sorted(STOPWORDS_MULTI, key=len, reverse=True):
            s = s.replace(w, "")
        content = "".join(ch for ch in s if "\u4e00" <= ch <= "\u9fff" and ch not in CHAR_STOP)
        if len(content) < 2:
            continue
        # 连续内容串：≤6 字整段保留；更长则切 2-4 字 n-gram（步长 2）
        if len(content) <= 6:
            cands = [content]
        else:
            cands = [content[i:i + 4] for i in range(0, len(content) - 1, 2)
                     if len(content[i:i + 4]) >= 2]
        for c in cands:
            if c in seen:
                continue
            # 子串包含去重（保留更长者优先）
            if any(c != q and c in q for q in seen if isinstance(q, str)):
                continue
            seen.add(c)
            out.append({"text": c, "source": "content_phrase",
                        "priority": 0 if len(c) >= 4 else 1})
    out.sort(key=lambda x: (x["priority"], -len(x["text"])))
    return out[:top]


def _get_mt():
    global _mt_model, _mt_tok
    if _mt_model is None and (MT_DIR / "config.json").exists():
        from transformers import MarianMTModel, MarianTokenizer
        _mt_tok = MarianTokenizer.from_pretrained(str(MT_DIR), local_files_only=True)
        _mt_model = MarianMTModel.from_pretrained(str(MT_DIR), local_files_only=True)
    return _mt_model


def translate_zh_en(texts: list[str]) -> dict:
    """本地 zh→en 翻译；模型缺失/失败时返回空 dict（不阻塞其他路由）。"""
    try:
        model = _get_mt()
        if model is None:
            return {}
    except Exception:  # noqa: BLE001
        return {}
    out = {}
    try:
        import torch
        batch = [_mt_tok(t, return_tensors="pt", padding=True, truncation=True) for t in texts]
        for t, inp in zip(texts, batch):
            with torch.no_grad():
                gen = model.generate(**inp, max_new_tokens=40)
            out[t] = _mt_tok.batch_decode(gen, skip_special_tokens=True)[0]
    except Exception:  # noqa: BLE001
        return {}
    return out


def _backoff_get(url: str, params: dict, tries: int = 2) -> tuple[int, dict | None, str]:
    """工程级退避重试：429/5xx/超时分类处理，记录重试与等待。"""
    import random
    import time
    note_parts, waited = [], 0.0
    for i in range(tries):
        try:
            r = requests.get(url, params=params, headers=UA, timeout=15)
            if r.status_code == 429 or r.status_code >= 500:
                wait = (2 ** i) * 1.5 + random.uniform(0, 0.8)
                note_parts.append(f"HTTP{r.status_code} retry{i + 1} wait{wait:.1f}s")
                waited += wait
                time.sleep(wait)
                continue
            return r.status_code, r.json(), "; ".join(note_parts)
        except Exception as e:  # noqa: BLE001
            wait = (2 ** i) * 1.2 + random.uniform(0, 0.8)
            note_parts.append(f"{type(e).__name__} retry{i + 1} wait{wait:.1f}s")
            waited += wait
            time.sleep(wait)
    return 429, None, "; ".join(note_parts)


def wikidata_search(phrase: str, lang: str = "zh", limit: int = 2) -> list[dict]:
    status, data, note = _backoff_get(WIKIDATA_API, {
        "action": "wbsearchentities", "search": phrase, "language": lang,
        "format": "json", "limit": limit})
    if not data:
        return []
    out = []
    for it in data.get("search", [])[:limit]:
        ent = {"id": it.get("id"), "label": it.get("label"),
               "description": it.get("description", "")}
        st, edata, _ = _backoff_get(WIKIDATA_API, {
            "action": "wbgetentities", "ids": ent["id"], "props": "sitelinks",
            "format": "json"})
        if edata:
            ent_data = edata.get("entities", {}).get(ent["id"], {})
            sl = {k: v.get("title", "") for k, v in ent_data.get("sitelinks", {}).items()
                  if k in ("enwiki", "commonswiki")}
            ent["en_label"] = sl.get("enwiki", "") or ent["label"]
            ent["commons_title"] = sl.get("commonswiki", "")
        out.append(ent)
    return out


def plan_queries(intent) -> dict:
    narration = intent.narration or intent.subject
    phrases = extract_phrases(narration)
    plan = {"phrases": [p["text"] for p in phrases], "phrase_detail": phrases,
            "translation": {}, "routes": {}}

    # 本地翻译（失败不阻塞）
    zh_phrases = [p["text"] for p in phrases if p["source"] == "content_phrase"]
    plan["translation"] = translate_zh_en(zh_phrases[:6])

    def en_of(ph: str) -> str:
        t = plan["translation"].get(ph, "")
        return t if t and len(t) >= 2 and re.search(r"[A-Za-z]", t) else ""

    # R1 实体路由
    r1 = []
    for ph in phrases[:3]:
        for ent in wikidata_search(ph["text"]):
            qs = []
            if ent.get("en_label"):
                qs.append({"type": "entity_en", "query": ent["en_label"],
                           "entity": ent["id"], "source": "wikidata",
                           "priority": 0, "zh": ph["text"]})
            if ent.get("commons_title"):
                qs.append({"type": "commons_category", "query": ent["commons_title"],
                           "entity": ent["id"], "source": "wikidata",
                           "priority": 0, "zh": ph["text"]})
            r1 += qs
            break
    plan["routes"]["R1_entity"] = r1

    # R2 分类路由：实体英文 + 翻译英文 + 中文（含翻译结果，无整句）
    r2 = []
    seen_r2 = set()
    for q in r1:
        key = q["query"].lower()
        if key not in seen_r2:
            seen_r2.add(key)
            r2.append({"type": "category_search", "query": q["query"],
                       "source": q["source"], "priority": 0})
    for ph in phrases:
        en = en_of(ph["text"])
        if en and en.lower() not in seen_r2:
            seen_r2.add(en.lower())
            r2.append({"type": "category_search", "query": en,
                       "source": "mt_zh_en", "priority": 1, "zh": ph["text"]})
    for ph in phrases[:3]:
        if ph["text"] not in seen_r2:
            seen_r2.add(ph["text"])
            r2.append({"type": "category_search", "query": ph["text"],
                       "source": "content_phrase", "priority": 2})
    plan["routes"]["R2_category"] = r2

    # R3 全文本：中文短语 + 翻译英文（禁止整句）
    r3 = []
    seen_r3 = set()
    for ph in phrases:
        if ph["text"] not in seen_r3:
            seen_r3.add(ph["text"])
            r3.append({"type": "fulltext", "query": ph["text"],
                       "source": ph["source"], "priority": ph["priority"]})
        en = en_of(ph["text"])
        if en and en not in seen_r3:
            seen_r3.add(en)
            r3.append({"type": "fulltext", "query": en,
                       "source": "mt_zh_en", "priority": 1, "zh": ph["text"]})
    plan["routes"]["R3_fulltext"] = r3

    # R4 旧词库阶梯（保留为 fallback，永不删除）
    ladder = intent.query_ladder or []
    plan["routes"]["R4_legacy"] = [
        {"type": "legacy", "query": q, "source": "lexicon", "priority": 2}
        for _, qs in ladder[:2] for q in qs[:2]]

    # R5 情绪
    plan["routes"]["R5_emotion"] = (
        [{"type": "emotion", "query": q, "source": "emotion_pool", "priority": 2}
         for q in EMOTION_POOL["en"][:2]] if intent.match_type == "EMOTIONAL" else [])
    return plan
