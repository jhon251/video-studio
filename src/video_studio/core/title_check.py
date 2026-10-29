# -*- coding: utf-8 -*-
"""P11-3：**标题/封面候选只读机械校验器**（纯函数、离线、确定性、零 LLM、零 I/O）。

职能：把 `config/metadata_style_guide.md` 的**可机械判定部分**落成门禁 ——
长度 / 震惊体黑名单 / technique 枚举 / 引用越界与重复 / **数字可溯性**（反标题诈骗核心门）/
technique 多样性 / 与正文首句回声。

阈值纪律：所有阈值常量**注明 guide 出处**（`THRESHOLDS[...]["basis"]`），不发明新数。
诚实边界（写入报告与产物）：
  · 机械门是**必要不充分**条件 —— **语义级"不失实"仍需人工终审**，本模块不宣称已自动化；
  · 旧格式产物（无 `title_candidates`）输出**结构码 `OLD_FORMAT`**（能力增量对照用），
    并对**不依赖新字段**的门（长度/震惊体/回声/全脚本数字可溯）照常判定，标注 `capability=legacy`。

数字可溯性规则（guide §二.1）：标题中的每个数字（阿拉伯/中文/混合/近似写法）都要能在
`number_sources` 指向的**段落原文**里找到**同值**表达；两侧都先归一化：
  · 阿拉伯数字 + 可选 `万/亿` 与 `%` → `("num", 值[, "pct"])`
  · 中文数字（零一二三四五六七八九十百千万亿、两）→ 同值
  · 近似写法（十几/几十/几百/几千/几万）→ `("approx", 量级)`，与同量级数字匹配
"""
from __future__ import annotations

import re

from .visual_requirement import canonical, sha256_text

SCHEMA = "title-check-v1"
VERSION = 1
PASS, FAIL, NOT_ASSESSABLE = "PASS", "FAIL", "NOT_ASSESSABLE"

#: 吸睛手法白名单（guide §一）
TECHNIQUES = ("curiosity_gap", "specificity", "stakes", "expectation_break",
              "identity_callout", "process_promise")

#: 震惊体黑名单（guide §二.4，含变体）
SENSATIONALISM = ("震惊", "惊呆", "吓人", "吓尿", "99%的人不知道", "99％的人不知道", "细思极恐",
                  "不转不是", "速看", "删前速看", "万万没想到", "全网最", "史上最", "绝对",
                  "必看", "揭秘", "惊天", "炸裂", "封神", "看哭")

#: 阈值常量（**全部注明 guide 出处**）
THRESHOLDS = {
    "title_max_chars": {"value": 40, "basis": "metadata_style_guide §三（B 站主标 ≤40 字，硬限 80 取保守值）"},
    "cover_max_chars": {"value": 12, "basis": "metadata_style_guide §三（封面大字 ≤12 字）"},
    "min_technique_diversity": {"value": 3, "basis": "metadata_style_guide §一 多样性要求"},
    "echo_lcs_chars": {"value": 12, "basis": "metadata_style_guide §二.5（最长公共子串 ≥12 字）"},
    "echo_ngram_ratio": {"value": 0.5,
                         "basis": "metadata_style_guide §二.5（3-gram 重合率 >0.5；"
                                  "P11-3 实测标定：单字重合率对中文过度敏感，旧稿 6 条标题全部 >0.8，"
                                  "改用 3-gram 以区分「回声」与「同主题措辞」）"},
    "echo_min_title_chars": {"value": 8, "basis": "metadata_style_guide §二.5（标题 ≥8 字才判回声）"},
    "ab_min_variants": {"value": 2, "basis": "metadata_style_guide §三（A/B 变体 ≥2）"},
    "max_candidates": {"value": 8, "basis": "工程护栏（guide 未规定上限；候选数超此值不判违规，仅标注）"},
}
VIOLATION_CODES = (
    "TITLE_TOO_LONG", "TITLE_COVER_TOO_LONG", "TITLE_SENSATIONALISM",
    "TITLE_TECHNIQUE_INVALID", "TITLE_EVIDENCE_REF_OUT_OF_RANGE",
    "TITLE_EVIDENCE_REF_DUPLICATE", "TITLE_NUMBER_UNTRACEABLE",
    "TITLE_TECHNIQUE_DIVERSITY_LOW", "TITLE_ECHOES_OPENING",
    "TITLE_EMPTY", "TITLE_NOT_A_STRING", "TITLE_NO_NUMBER_SOURCES",
    "COVER_TEXT_TOO_LONG", "COVER_PAIRING_INVALID", "COVER_DUPLICATES_TITLE",
)
STRUCTURAL_CODES = ("OLD_FORMAT", "NO_TITLE_CANDIDATES")

CN_DIGITS = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6,
             "七": 7, "八": 8, "九": 9}
CN_UNITS = {"十": 10, "百": 100, "千": 1000}
CN_BIG = {"万": 10000, "亿": 100000000}
CN_CHARS = "".join(CN_DIGITS) + "".join(CN_UNITS) + "".join(CN_BIG)
CN_NUM_RE = re.compile("[{}{}]+".format(CN_CHARS, ""))
ARABIC_RE = re.compile(r"\d+(?:\.\d+)?\s*(?:万|亿)?\s*%?")
APPROX_RE = re.compile(r"(几|数)(十|百|千|万|亿)")
DIGITS_STR = "0123456789"
#: P11-3 实测 precision 修正：中文量词/习语里的「一/两」不构成**数字断言**
#: （实测误报：「一步」「一遍」「这一环」「一份」被抽成 num=1 ⇒ 误触 TITLE_NO_NUMBER_SOURCES）。
#: 规则：多位数字串（如 十六/三十/一百），或 单字数字 + **计量单位**（下表）方计为数字断言。
#: 非放宽：`十六年`/`三千页`/`20 年`/`99%` 等真实数量表达仍全部受门。
CN_MEASURE_UNITS = ("年", "月", "日", "天", "小时", "分钟", "秒", "页", "倍", "万", "亿", "％",
                    "米", "公里", "公斤", "吨", "人", "次" )


def cn_to_int(text: str) -> int | None:
    """中文数字 → 整数（支持 零一二…十百千万亿 与 '十二'/'二十'/'一百五十'/'三千'）。"""
    if not text:
        return None
    total, section, number = 0, 0, 0
    for ch in text:
        if ch in CN_DIGITS:
            number = CN_DIGITS[ch]
        elif ch in CN_UNITS:
            unit = CN_UNITS[ch]
            section += (number or 1) * unit
            number = 0
        elif ch in CN_BIG:
            big = CN_BIG[ch]
            section = (section + number) * big
            total += section
            section, number = 0, 0
        else:
            return None
    return total + section + number


def extract_numbers(text: str) -> list[tuple]:
    """抽取并归一化数字 token：('num', 值[, 'pct']) / ('approx', 量级)。"""
    out: list[tuple] = []
    s = str(text or "")
    for m in ARABIC_RE.finditer(s):
        raw = m.group(0).strip()
        pct = raw.endswith("%")
        raw = raw.rstrip("%").strip()
        mult = 1
        if raw.endswith("万"):
            mult, raw = 10000, raw[:-1].strip()
        elif raw.endswith("亿"):
            mult, raw = 100000000, raw[:-1].strip()
        try:
            val = float(raw) * mult
        except ValueError:
            continue
        val = int(val) if float(val).is_integer() else val
        out.append(("num", val, "pct") if pct else ("num", val))
    for m in APPROX_RE.finditer(s):
        unit = CN_UNITS.get(m.group(2)) or CN_BIG.get(m.group(2))
        nxt = s[m.end():m.end() + 1]                     # 「几十万」⇒ 十 × 万
        if nxt in CN_BIG and unit:
            unit = unit * CN_BIG[nxt]
        if unit:
            out.append(("approx", unit))
    for m in CN_NUM_RE.finditer(s):
        frag = m.group(0)
        if not frag:
            continue
        # 排除近似写法内部的单位字（「几千」的「千」、「数十」的「十」）——已由 APPROX_RE 处理
        prev = s[m.start() - 1] if m.start() > 0 else ""
        if prev in ("几", "数"):
            continue
        if len(frag) == 1 and frag in CN_UNITS and not (m.start() > 0 and s[m.start() - 1] in DIGITS_STR):
            continue                       # 裸「十/百/千」不成数（避免「千页」误抽）
        if len(frag) == 1:
            # 单字数字（一/二/…/九）：仅当紧接**计量单位**时视为数字断言（量词用法不计）
            tail = s[m.end():m.end() + 3]
            if not any(tail.startswith(u) for u in CN_MEASURE_UNITS):
                continue
        val = cn_to_int(frag)
        if val:
            out.append(("num", val))
    return out


def numbers_match(a: tuple, b: tuple) -> bool:
    """两个数字 token 是否视为同值（近似写法按量级匹配）。"""
    if a == b:
        return True
    if a[0] == "approx" and b[0] == "num" and isinstance(b[1], (int, float)):
        unit = a[1]
        v = b[1]
        return (unit <= v < unit * 10) if unit else False
    if b[0] == "approx" and a[0] == "num" and isinstance(a[1], (int, float)):
        unit = b[1]
        v = a[1]
        return (unit <= v < unit * 10) if unit else False
    return False


def longest_common_substring_len(a: str, b: str) -> int:
    a, b = str(a or ""), str(b or "")
    if not a or not b:
        return 0
    prev = [0] * (len(b) + 1)
    best = 0
    for i in range(1, len(a) + 1):
        cur = [0] * (len(b) + 1)
        for j in range(1, len(b) + 1):
            if a[i - 1] == b[j - 1]:
                cur[j] = prev[j - 1] + 1
                best = max(best, cur[j])
        prev = cur
    return best


def _strip_punct(s: str) -> str:
    return re.sub(r"[\s，。！？、；：「」『』（）()【】\[\]…—\-·,.!?;:\"'“”‘’%％]", "", str(s or ""))


def _ngrams(s: str, n: int = 3) -> set:
    t = _strip_punct(s)
    return {t[i:i + n] for i in range(max(0, len(t) - n + 1))}


def ngram_containment(title: str, opening: str, n: int = 3) -> float:
    """标题的 n-gram 有多少比例出现在首句里（P11-3 标定：比单字重合率更能区分回声与同主题）。"""
    g = _ngrams(title, n)
    if not g:
        return 0.0
    o = _ngrams(opening, n)
    return sum(1 for x in g if x in o) / len(g)


def _segments(script: dict | None) -> list[dict]:
    return list((script or {}).get("segments") or [])


def check_candidate(cand: dict, *, segments: list[dict], index: int, opening: str,
                    all_techniques: list[str], max_chars: int, is_cover: bool = False) -> dict:
    """单候选机械校验（纯函数）。"""
    codes: list[dict] = []
    text = cand.get("text")
    if not isinstance(text, str):
        codes.append({"code": "TITLE_NOT_A_STRING"})
        text = ""
    if not text.strip() and not is_cover:
        codes.append({"code": "TITLE_EMPTY"})
    n = len(text)
    if n > max_chars:
        codes.append({"code": "TITLE_COVER_TOO_LONG" if is_cover else "TITLE_TOO_LONG",
                      "length": n, "limit": max_chars})
    hit = [w for w in SENSATIONALISM if w in text]
    if hit:
        codes.append({"code": "TITLE_SENSATIONALISM", "hits": hit})
    tech = cand.get("technique")
    if not is_cover:
        if tech not in TECHNIQUES:
            codes.append({"code": "TITLE_TECHNIQUE_INVALID", "value": tech})
    # 引用校验
    refs = cand.get("evidence_refs")
    refs = refs if isinstance(refs, list) else []
    num_src = cand.get("number_sources")
    num_src = num_src if isinstance(num_src, list) else []
    for label, arr in (("evidence_refs", refs), ("number_sources", num_src)):
        bad = [r for r in arr if isinstance(r, bool) or not isinstance(r, int)
               or not (0 <= r < len(segments))]
        if bad:
            codes.append({"code": "TITLE_EVIDENCE_REF_OUT_OF_RANGE", "field": label,
                          "refs": bad, "segments": len(segments)})
        if len({r for r in arr if isinstance(r, int)}) != len([r for r in arr
                                                              if isinstance(r, int)]):
            codes.append({"code": "TITLE_EVIDENCE_REF_DUPLICATE", "field": label})
    # 数字可溯性（核心门）
    title_nums = extract_numbers(text)
    if title_nums:
        if is_cover and not num_src:
            # 封面候选 schema 无 number_sources 字段 ⇒ 退化为**全脚本口径**（如实标注，不伪造出处）
            pool = [x for s2 in segments for x in extract_numbers(str(s2.get("narration") or ""))]
            untraceable = [t for t in title_nums if not any(numbers_match(t, p) for p in pool)]
            if untraceable:
                codes.append({"code": "TITLE_NUMBER_UNTRACEABLE", "number": list(untraceable[0]),
                              "scope": "whole_script（封面候选无 number_sources 字段）"})
            num_scope = "whole_script（封面候选无 number_sources 字段，如实标注）"
        else:
            scope_refs = [r for r in num_src if isinstance(r, int) and 0 <= r < len(segments)]
            num_scope = "number_sources"
            if not scope_refs:
                codes.append({"code": "TITLE_NO_NUMBER_SOURCES",
                              "numbers": [list(x) for x in title_nums]})
            else:
                pool = []
                for r in scope_refs:
                    pool += extract_numbers(str(segments[r].get("narration") or ""))
                for t in title_nums:
                    if not any(numbers_match(t, p) for p in pool):
                        codes.append({"code": "TITLE_NUMBER_UNTRACEABLE", "number": list(t),
                                      "checked_segments": scope_refs})
    else:
        num_scope = None
    # 首句回声
    if not is_cover:
        lcs = longest_common_substring_len(text, opening)
        ratio = ngram_containment(text, opening)
        if lcs >= THRESHOLDS["echo_lcs_chars"]["value"] or (
                n >= THRESHOLDS["echo_min_title_chars"]["value"]
                and ratio > THRESHOLDS["echo_ngram_ratio"]["value"]):
            codes.append({"code": "TITLE_ECHOES_OPENING", "lcs": lcs,
                          "ngram3_containment": round(ratio, 3)})
    if is_cover:
        pairing = cand.get("cover_title_pairing")
        if pairing not in ("互补", "递进", "反差"):
            codes.append({"code": "COVER_PAIRING_INVALID", "value": pairing})
    hard = [c["code"] for c in codes]
    status = FAIL if hard else PASS
    return {"index": index, "kind": "cover_text" if is_cover else "title", "text": text,
            "length": n, "technique": tech, "status": status, "codes": codes,
            "evidence_refs": refs, "number_sources": num_src,
            "number_scope": num_scope if title_nums else None,
            "numbers_in_title": [list(x) for x in title_nums]}


def check_metadata(script: dict | None = None, metadata: dict | None = None, *,
                   source: dict | None = None) -> dict:
    """完整校验：标题候选 + 封面大字 + A/B 方案 + 结构码/能力标注（只读、确定性）。"""
    segments = _segments(script)
    opening = str((segments[0] or {}).get("narration") or "") if segments else ""
    meta = metadata or {}
    cands = meta.get("title_candidates")
    structural: list[str] = []
    legacy_candidates: list[dict] = []
    if not isinstance(cands, list) or not cands:
        structural.append("OLD_FORMAT")
        structural.append("NO_TITLE_CANDIDATES")
        for i, p in enumerate(meta.get("platforms") or []):
            t = p.get("title")
            if isinstance(t, str) and t.strip():
                legacy_candidates.append({"text": t, "technique": None,
                                          "evidence_refs": [], "number_sources": [],
                                          "legacy_platform": p.get("platform")})
            if len(legacy_candidates) >= 8:
                break
        if not cands and not legacy_candidates and isinstance(meta.get("titles"), list):
            for t in meta["titles"][:8]:
                legacy_candidates.append({"text": str(t), "technique": None,
                                          "evidence_refs": [], "number_sources": []})
        results = legacy_candidates
        capability = ("legacy（无 title_candidates ⇒ 仅可判不依赖新字段的门："
                      "长度/震惊体/首句回声/全脚本数字可溯）")
    else:
        results, capability = cands, "v1（含 technique/引用/数字出处）"
    max_title = THRESHOLDS["title_max_chars"]["value"]
    # legacy 模式：新字段（technique/evidence_refs/number_sources）**结构上不存在** ⇒
    # 相应门记为"不可评"（not_assessable_gates），**不判 FAIL**（能力差异 ≠ 违规）。
    legacy_gates = ("technique", "evidence_refs", "number_sources", "technique_diversity")
    checked = [check_candidate(c, segments=segments, index=i, opening=opening,
                               all_techniques=TECHNIQUES, max_chars=max_title, is_cover=False)
               for i, c in enumerate(results)]
    if structural:
        for r in checked:
            kept = []
            for v in r["codes"]:
                if v["code"] in ("TITLE_TECHNIQUE_INVALID", "TITLE_EVIDENCE_REF_OUT_OF_RANGE",
                                 "TITLE_EVIDENCE_REF_DUPLICATE", "TITLE_NO_NUMBER_SOURCES",
                                 "TITLE_EMPTY"):
                    continue
                if v["code"] == "TITLE_TECHNIQUE_DIVERSITY_LOW":
                    continue
                kept.append(v)
            r["codes"] = kept
            r["not_assessable_gates"] = list(legacy_gates)
            r["status"] = FAIL if kept else PASS
    # 旧格式：数字可溯性退化为"全脚本范围"（无 number_sources）
    if structural:
        pool = [extract_numbers(str(s.get("narration") or "")) for s in segments]
        flat = [x for sub in pool for x in sub]
        for r, c in zip(checked, results):
            if r["numbers_in_title"] and not (c.get("number_sources") or []):
                untraceable = [t for t in
                               [tuple(x) for x in r["numbers_in_title"]]
                               if not any(numbers_match(t, p) for p in flat)]
                r["codes"] = [x for x in r["codes"] if x["code"] != "TITLE_NO_NUMBER_SOURCES"]
                r["number_scope"] = "whole_script（legacy 退化口径，如实标注）"
                if untraceable:
                    r["codes"].append({"code": "TITLE_NUMBER_UNTRACEABLE",
                                       "number": list(untraceable[0]),
                                       "scope": "whole_script"})
                r["status"] = FAIL if [x for x in r["codes"]] else PASS
    used = sorted({c.get("technique") for c in results if c.get("technique") in TECHNIQUES})
    diversity_assessed = bool(results) and not structural and len(results) >= \
        THRESHOLDS["min_technique_diversity"]["value"]
    if diversity_assessed and len(used) < THRESHOLDS["min_technique_diversity"]["value"]:
        for r in checked:
            r["codes"].append({"code": "TITLE_TECHNIQUE_DIVERSITY_LOW",
                               "distinct": len(used), "required":
                                   THRESHOLDS["min_technique_diversity"]["value"]})
            r["status"] = FAIL
    covers = meta.get("cover_text_candidates")
    covers = covers if isinstance(covers, list) else []
    cover_checked = [check_candidate(c, segments=segments, index=i, opening=opening,
                                     all_techniques=TECHNIQUES,
                                     max_chars=THRESHOLDS["cover_max_chars"]["value"],
                                     is_cover=True) for i, c in enumerate(covers)]
    titles_norm = {_strip_punct(r["text"]) for r in checked if r["text"].strip()}
    for cr in cover_checked:
        if _strip_punct(cr["text"]) in titles_norm:
            cr["codes"].append({"code": "COVER_DUPLICATES_TITLE"})
            cr["status"] = FAIL
    ab = meta.get("ab_plan") or {}
    ab_report = {"present": bool(ab), "platform": ab.get("platform"),
                 "variants": len(ab.get("variants") or []),
                 "metric": ab.get("metric"), "execution": ab.get("execution"),
                 "execution_is_manual": ab.get("execution") == "manual",
                 "variants_ok": len(ab.get("variants") or [])
                 >= THRESHOLDS["ab_min_variants"]["value"],
                 "note": ab.get("note"),
                 "basis": THRESHOLDS["ab_min_variants"]["basis"]}
    body = {
        "schema": SCHEMA, "version": VERSION,
        "generation_method": "deterministic-offline（纯函数、零 LLM、零 I/O）",
        "capability": capability,
        "script_sha256": sha256_text(canonical(script)) if script is not None else None,
        "metadata_sha256": sha256_text(canonical(metadata)) if metadata is not None else None,
        "thresholds": THRESHOLDS, "techniques": list(TECHNIQUES),
        "violation_codes": list(VIOLATION_CODES), "structural_codes": structural,
        "candidates": checked, "cover_texts": cover_checked, "ab_plan": ab_report,
        "techniques_used": used, "diversity_assessed": diversity_assessed,
        "counts": {"candidates": len(checked),
                   "pass": sum(1 for c in checked if c["status"] == PASS),
                   "fail": sum(1 for c in checked if c["status"] == FAIL),
                   "cover_texts": len(cover_checked),
                   "cover_pass": sum(1 for c in cover_checked if c["status"] == PASS)},
        "all_pass": bool(checked) and all(c["status"] == PASS for c in checked)
                    and all(c["status"] == PASS for c in cover_checked),
        "honest_boundary": ["机械门为**必要不充分**条件：语义级不失实需人工终审",
                            "旧格式产物以结构码 OLD_FORMAT 呈现能力差异（非违规）"],
        "read_only": True, "zero_write": True, "applied": False, "executed": False,
        "source": source or {},
        "artifact_hash": "",
    }
    body["artifact_hash"] = report_hash(body)
    return body


def report_hash(rep: dict) -> str:
    return sha256_text(canonical({k: v for k, v in rep.items()
                                  if k not in ("artifact_hash", "source")}))


def validate(rep: dict) -> list[str]:
    errs = []
    if rep.get("schema") != SCHEMA:
        errs.append("schema 非法")
    if rep.get("artifact_hash") != report_hash(rep):
        errs.append("artifact_hash 不一致")
    for c in rep.get("candidates") or []:
        if c["status"] not in (PASS, FAIL):
            errs.append("candidate[{}] status 非法".format(c.get("index")))
        if c["status"] == FAIL and not c["codes"]:
            errs.append("candidate[{}] FAIL 无违规码".format(c.get("index")))
    for k, v in (rep.get("thresholds") or {}).items():
        if not v.get("basis"):
            errs.append("阈值 {} 缺 basis（不得发明新数）".format(k))
    return errs
