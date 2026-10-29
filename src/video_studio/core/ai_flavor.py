# -*- coding: utf-8 -*-
"""Phase 23 / P23-2：**AI 味信号层**（`core/ai_flavor.py`）。

**定位**：机械、确定性、零 LLM。给任意中文解说稿打一组**可比的风格信号**，
用于 ① 给出 v2/v3 稿与人工参照文本的**基线分布**；② 每轮重写后的**机械验收**
（目标 = v4 分布**向参照文本靠拢、且低于 v3**）。

**POLICY 机理（每项信号为什么算 AI 味）**
| 信号 | 机理 |
|---|---|
| `advance_marker_density` | 「换句话说/也就是说/值得注意/更重要的是」是**论证骨架的外露路标**；人说话靠语气和停顿过渡，不靠路标 |
| `not_a_but_b_rate` | 「不是A而是B」对称构式是**书面修辞模板**，口语极少整篇复用同一模板 |
| `rhetorical_qa_density` | 「…吗？答案是…」设问自答是**讲义式**推进，故事叙述者不需要自问自答 |
| `sentence_len_cv` | 句长**变异系数过低**=节奏均一=机器特征；人有长短句起伏 |
| `colon_expand_rate` | 「冒号 + 展开」是**条目化/提纲化**痕迹，口语不用冒号组织 |
| `dash_aside_rate` | 破折号补充在书面说明里高频，口语用插入语代替 |
| `hedge_stack_rate` | 限定语堆叠（「严格来说…必须指出…」）是**免责式**表达，AI 为稳妥而堆叠 |
| `para_symmetry` | 段落结构**对称性**（段长/句数过于齐整）=模板化 |

**与 `mm_*` 冻结栈无关**：本模块只读文本、只算信号，不参与任何门禁判定。
"""
from __future__ import annotations

import pathlib
import re
import statistics

#: 推进词/路标（外露论证骨架）
ADVANCE_MARKERS = (
    "换句话说", "也就是说", "换言之", "值得注意", "值得注意的是", "更重要的是",
    "更重要的是", "更重要的是", "总而言之", "综上", "综上所述", "总的来说", "总结一下",
    "首先", "其次", "最后", "第一点", "第二点", "第三点", "一方面", "另一方面",
    "由此可见", "不难看出", "事实上", "实际上", "其实", "需要指出", "需要注意的是",
    "具体来说", "简而言之", "一言以蔽之",
)
#: 「不是A而是B」对称构式（含「并不是」「并非」「不在于」等变体）
NOT_A_BUT_B = re.compile(r"(?:并不是|不是|并非)[^。！？；，]{1,40}?(?:而是|而在于)|"
                         r"不在于[^。！？；，]{1,40}?而在于")
#: 设问自答（问号后紧跟「答案是/因为/原因」等）
RHET_QA = re.compile(r"[？?][^。！？]{0,12}?(答案|因为|原因|理由|本质|关键)")
#: 冒号 + 展开
COLON_EXPAND = re.compile(r"[：:]")
#: 破折号补充
DASH_ASIDE = re.compile(r"——|—{2,}")
#: 限定语（堆叠检测）
HEDGES = ("严格来说", "严格地讲", "必须指出", "必须打个记号", "需要指出", "需要注意的是",
          "至少在", "某种意义上", "在一定程度上", "就目前而言", "据现有材料", "不夸张地说")
SENT_SPLIT = re.compile(r"[。！？!?；;\n]+")

POLICY = {
    "version": "ai-flavor-signals-v1",
    "zero_llm": True,
    "scope": "只读文本、只算信号；不参与门禁判定",
    "signals": {
        "advance_marker_density": "推进词/路标密度（外露论证骨架）",
        "not_a_but_b_rate": "「不是A而是B」对称构式频率（书面修辞模板）",
        "rhetorical_qa_density": "设问自答对密度（讲义式推进）",
        "sentence_len_cv": "句长变异系数（越低=节奏越均一=越机器）",
        "colon_expand_rate": "冒号+展开频率（条目化痕迹）",
        "dash_aside_rate": "破折号补充频率（书面说明痕迹）",
        "hedge_stack_rate": "限定语堆叠率（免责式表达）",
        "para_symmetry": "段落结构对称性（模板化）",
    },
}


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in SENT_SPLIT.split(text or "") if s.strip()]


def _paras(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", (text or "").strip()) if p.strip()]


def analyze(text: str, *, policy: dict | None = None) -> dict:
    """对一段中文文本计算 AI 味信号（纯函数、确定性）。"""
    t = text or ""
    n_chars = len(re.sub(r"\s", "", t))
    sents = _sentences(t)
    paras = _paras(t)
    lens = [len(re.sub(r"\s", "", s)) for s in sents] or [0]
    mean_len = statistics.fmean(lens) if lens else 0.0
    cv = (statistics.pstdev(lens) / mean_len) if mean_len else 0.0
    per_1k = (lambda c: round(c / max(n_chars, 1) * 1000.0, 4))

    adv = sum(t.count(m) for m in ADVANCE_MARKERS)
    nab = len(NOT_A_BUT_B.findall(t))
    rqa = len(RHET_QA.findall(t))
    colon = len(COLON_EXPAND.findall(t))
    dash = len(DASH_ASIDE.findall(t))
    # 限定语堆叠：任一句内出现 >=2 个不同限定语
    stack = sum(1 for s in sents if sum(1 for h in HEDGES if h in s) >= 2)
    # 段落对称性：段落句数的归一化标准差（越低=越对称=越模板）
    pcounts = [len(_sentences(p)) for p in paras] or [0]
    pm = statistics.fmean(pcounts) if pcounts else 0.0
    psym = 1.0 - min((statistics.pstdev(pcounts) / pm) if pm else 0.0, 1.0)

    out = {
        "policy": (policy or POLICY)["version"],
        "chars": n_chars, "sentences": len(sents), "paragraphs": len(paras),
        "mean_sentence_len": round(mean_len, 3),
        "advance_marker_count": adv,
        "advance_marker_density": per_1k(adv),
        "not_a_but_b_count": nab, "not_a_but_b_rate": per_1k(nab),
        "rhetorical_qa_count": rqa, "rhetorical_qa_density": per_1k(rqa),
        "sentence_len_cv": round(cv, 4),
        "colon_count": colon, "colon_expand_rate": per_1k(colon),
        "dash_count": dash, "dash_aside_rate": per_1k(dash),
        "hedge_stack_count": stack, "hedge_stack_rate": per_1k(stack),
        "para_symmetry": round(psym, 4),
        "advance_marker_hits": sorted({m for m in ADVANCE_MARKERS if m in t}),
        "hedge_hits": sorted({h for h in HEDGES if h in t}),
    }
    # 综合 AI 味分（越低越"人味"）= **相对参照均值的正向偏离加权和**。
    # 设计纪律：① 只用**正向偏离**（比参照更"人味"不扣分，避免鼓励做怪）；
    # ② 每个信号的"阈值"为参照文本均值 ⇒ 分数是**可比的、不可自证的距离**。
    out["ai_flavor_score"] = None      # 需参照均值 ⇒ 由 compare_to_reference 填充
    return out


#: 综合分权重（正向偏离加权）
SCORE_WEIGHTS = {
    "advance_marker_density": 1.0, "not_a_but_b_rate": 1.0,
    "rhetorical_qa_density": 1.0, "hedge_stack_rate": 1.0,
    "colon_expand_rate": 0.5, "dash_aside_rate": 0.5,
    "para_symmetry": 4.0,
    # 句长 CV 是"越高越好"⇒ 用 (ref - sig) 的正向偏离
    "sentence_len_cv": 20.0,
}
#: "越高越好"的信号（其余为"越低越好"）
HIGHER_IS_BETTER = ("sentence_len_cv",)


def longest_common_ngram(a: str, b: str, *, n: int = 8) -> dict:
    """**n-gram 守卫**：两文本的最长公共子串（字符级，n 为上报阈值）。

    用于"防抄口头禅"：v4 稿与**参照文本**的长公共片段必须为 **0**（n≥8）。
    返回 `{"length": L, "sample": s, "hits": [...]}`。确定性、O(len(a)*len(b)) 上限保护。
    """
    sa, sb = re.sub(r"\s", "", a or ""), re.sub(r"\s", "", b or "")
    if not sa or not sb:
        return {"length": 0, "sample": "", "hits": [], "threshold": n, "violated": False}
    best, hits, seen = 0, [], set()
    # 以短文本切 n-gram 做包含测试（对 <8 的公共片段不关心）
    short, long_ = (sa, sb) if len(sa) <= len(sb) else (sb, sa)
    for i in range(len(short) - n + 1):
        g = short[i:i + n]
        if g in long_:
            # 尝试向右扩展
            L = n
            while (i + L < len(short)) and (g + short[i + n:i + L + 1]) in long_:
                L += 1
            frag = short[i:i + L]
            if L > best:
                best = L
            if frag not in seen and len(hits) < 20:
                seen.add(frag)
                hits.append(frag)
    hits.sort(key=lambda x: -len(x))
    return {"length": best, "sample": (hits[0] if hits else ""), "hits": hits[:10],
            "threshold": n, "violated": best >= n}


#: 中文数字归一（用于"数字保真"校验）
CN_DIGITS = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6,
             "七": 7, "八": 8, "九": 9}
CN_UNITS = {"十": 10, "百": 100, "千": 1000, "万": 10000, "亿": 100000000}


def _cn_num(s: str) -> int | None:
    """把「一百二十三」「十」「两千」等中文数字转 int；失败返回 None。"""
    if not s or any(c not in CN_DIGITS and c not in CN_UNITS for c in s):
        return None
    total, section, num = 0, 0, 0
    for c in s:
        if c in CN_DIGITS:
            num = CN_DIGITS[c]
        else:
            u = CN_UNITS[c]
            if u >= 10000:
                section = (section + num) * u
                total += section
                section = num = 0
            else:
                section += (num or 1) * u
                num = 0
    return total + section + num


def numbers(text: str) -> dict:
    """抽取文本中的数字（阿拉伯 + 中文归一），返回集合与频次（确定性）。"""
    t = text or ""
    ar = re.findall(r"[0-9]+(?:\.[0-9]+)?", t)
    cn = re.findall(r"[零一二两三四五六七八九十百千万亿]{2,}", t)
    cn_nums = []
    for c in cn:
        v = _cn_num(c)
        if v is not None:
            cn_nums.append(str(v))
    return {"arabic": sorted(set(ar)), "chinese_normalized": sorted(set(cn_nums)),
            "all": sorted(set(ar) | set(cn_nums))}


def number_fidelity(v4_text: str, v3_text: str) -> dict:
    """数字保真：v4 的数字集合必须 ⊆ v3（不得新增数字）。"""
    a, b = numbers(v4_text), numbers(v3_text)
    extra = sorted(set(a["all"]) - set(b["all"]))
    missing = sorted(set(b["all"]) - set(a["all"]))
    return {"v4_numbers": a["all"], "v3_numbers": b["all"],
            "extra_in_v4": extra, "missing_in_v4": missing,
            "preserved": not extra, "note": "extra_in_v4 非空 ⇒ 违反数字保真"}


def ner_entities(text: str) -> dict:
    """命名实体（轻量、确定性）：拉丁词串 + **专名性**引号内容 + 中文机构/定理后缀。

    **专名性判定（避免把中文描述性引语误当实体）**：引号/书名号内的内容**仅在**满足
    ① 含拉丁字母或数字，或 ② 长度为 2–8 且以机构/定理等后缀结尾 时，才计为实体。
    纯中文的长引语（如「被读完并被理解」）是**行文措辞**，不是命名实体。
    """
    t = text or ""
    latin = re.findall(r"[A-Za-z][A-Za-z.\-']{2,}", t)
    quoted_raw = re.findall(r"[《「“\"]([^》」”\"]{2,24})[》」”\"]", t)
    quoted = [q for q in quoted_raw
              if re.search(r"[A-Za-z0-9]", q)
              or re.search(r"(定理|猜想|杂志|期刊|学报|大学|学院|研究所|学会)$", q)]
    cjk_org = re.findall(r"[\u4e00-\u9fa5]{2,8}(?:定理|猜想|大学|学院|杂志|期刊|研究所|学会|学派)", t)
    return {"latin": sorted(set(latin)), "quoted": sorted(set(quoted)),
            "cjk_org": sorted(set(cjk_org)), "quoted_dropped_descriptive":
            sorted(set(quoted_raw) - set(quoted)),
            "all": sorted(set(latin) | set(quoted) | set(cjk_org))}


def entity_fidelity(v4_text: str, v3_text: str) -> dict:
    a, b = ner_entities(v4_text), ner_entities(v3_text)
    lost = sorted(set(b["all"]) - set(a["all"]))
    added = sorted(set(a["all"]) - set(b["all"]))
    return {"v3_entities": b["all"], "v4_entities": a["all"],
            "lost_in_v4": lost, "added_in_v4": added, "preserved": not lost}


def retention_score(script: dict, text_of) -> dict:
    """**留存机械层**：hook / emotion_beat / CTA 的覆盖率（与 v3 同口径比较）。"""
    segs = script.get("segments") or []
    hooks = script.get("hook_map") or []
    beats = [s.get("emotion_beat") for s in segs if s.get("emotion_beat")]
    cta = script.get("cta_plan") or []
    n = max(len(segs), 1)
    hook_ok = sum(1 for h in hooks if isinstance(h, dict)
                  and str(h.get("at_segment") or "").isdigit()
                  and 1 <= int(h["at_segment"]) <= len(segs))
    beat_ok = sum(1 for s in segs if s.get("emotion_beat"))
    cta_ok = sum(1 for c in cta if isinstance(c, dict) and str(c.get("at_segment") or "").isdigit()
                 and 1 <= int(c["at_segment"]) <= len(segs))
    score = round((hook_ok / max(len(hooks), 1) * 0.4
                   + beat_ok / n * 0.3
                   + cta_ok / max(len(cta), 1) * 0.3), 4)
    return {"segments": len(segs), "hooks": len(hooks), "hooks_in_range": hook_ok,
            "emotion_beats": beat_ok, "cta": len(cta), "cta_in_range": cta_ok,
            "score": score}


def script_text(script: dict) -> str:
    return "\n\n".join(str(s.get("narration") or "") for s in (script.get("segments") or []))


def compare_to_reference(sig: dict, ref_sigs: list[dict]) -> dict:
    """把一篇稿的信号与参照文本的**信号均值**比较：分数 = **正向偏离加权和**。

    - 对"越低越好"的信号：偏离 = `max(0, sig − ref_mean)`
    - 对"越高越好"的信号（`sentence_len_cv`）：偏离 = `max(0, ref_mean − sig)`
    ⇒ **优于参照不扣分**；分数越低越接近/超过参照的人味水平。
    """
    keys = tuple(SCORE_WEIGHTS)
    ref_mean = {k: round(statistics.fmean([r[k] for r in ref_sigs]), 4) for k in keys}
    dev, total = {}, 0.0
    for k in keys:
        d = (ref_mean[k] - sig[k]) if k in HIGHER_IS_BETTER else (sig[k] - ref_mean[k])
        dev[k] = round(max(0.0, d), 4)
        total += dev[k] * SCORE_WEIGHTS[k]
    return {"ref_mean": ref_mean, "positive_deviation": dev,
            "delta_vs_ref": {k: round(sig[k] - ref_mean[k], 4) for k in keys},
            "ai_flavor_score": round(total, 4)}


def score_against_reference(sig: dict, ref_sigs: list[dict]) -> dict:
    """`analyze` 之后补算综合分（`analyze` 本身不知参照均值）。"""
    return compare_to_reference(sig, ref_sigs)


def baseline(paths: dict[str, str], ref_paths: list[str]) -> dict:
    """给多篇稿 + 参照文本跑基线（路径 → 文本）。"""
    refs = [analyze(pathlib.Path(p).read_text(encoding="utf-8")) for p in ref_paths]
    arms = {k: analyze(v) for k, v in paths.items()}
    out = {"schema": "phase23-flavor-baseline-v1", "policy": POLICY,
           "references": {"paths": ref_paths, "signals": refs,
                          "mean": {k: round(statistics.fmean([r[k] for r in refs]), 4)
                                   for k in SCORE_WEIGHTS}},
           "arms": {k: {**v, "vs_ref": compare_to_reference(v, refs)}
                    for k, v in arms.items()},
           "score_weights": SCORE_WEIGHTS, "higher_is_better": list(HIGHER_IS_BETTER)}
    return out
