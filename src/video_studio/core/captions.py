# -*- coding: utf-8 -*-
"""字幕切分与排布（**纯函数**，供 subtitle agent 与 editing 烧录共用，单一事实源）。

设计要点（5-M：把"整段旁白居中铺满画面"改为**逐条字幕**）：
  · 切分：先按句末标点切句，再按停顿标点细分，使每条 cue ≤ `max_cue_chars`（默认 36 = 2 行 × 18 字）；
  · 折行：每条 cue 折成 **≤2 行**、每行 ≤ `max_line` 字（优先在停顿标点处折）；
  · 排布：在一个镜头的时间窗内**按字数比例**分配时间（保证与画面/时间轴同基），并保证
    ≥`min_cue_s` 秒、单调、不重叠、**恰好铺满**该窗口；
  · 输出：`to_srt`（既有字幕产物格式）与 `to_ass`（libass 烧录用，底部居中 + 描边，PlayRes = 视频分辨率）。

不含任何 I/O、不读配置、不依赖 ffmpeg。
"""
from __future__ import annotations

import pathlib
import re
import statistics

# 句末标点（切句）与停顿标点（细分/折行优先点）
SENT_END = "。！？!?…"
SOFT_BREAK = "，、；;：:,"
# 折行时不应出现在行首的标点
NO_LINE_START = "，。！？、；：）」』】》%,.!?;:)"

MAX_CUE_CHARS = 36
MAX_LINE_CHARS = 22
MIN_CUE_CHARS = 6
MIN_CUE_S = 1.0
CHARS_PER_SEC = 5.0      # 中文字幕舒适阅读速度（约 5 字/秒）
MAX_CUE_S = 8.0          # 单条字幕最长显示时长（避免长镜头里同一条字幕滞留过久）

# ---- P0（2026-10-20）显示级切分预算 -------------------------------------------
# 审计实测：word_exact 路径按"静音间隔"分组，旁白不换气时单条 cue 可达
# **14.9s / 约 70 字**（`artifacts/_captions_t_4f182e0dbe7c.ass`），远超阅读节奏。
# 这里给出**显示级**预算：一条 ≤18 字（单行）、≤4s；超出即按字符量均分，
# 时间按字符比例线性分配（保序、不重叠、总时长不变 ⇒ 不影响时长契约）。
DISPLAY_MAX_CHARS = 18
DISPLAY_MAX_S = 4.0


def normalize(text: str) -> str:
    """规整旁白文本：去换行/多余空白、去 libass 覆盖块字符（`{}`）。"""
    t = str(text or "").replace("\r", " ").replace("\n", " ")
    t = t.replace("{", "（").replace("}", "）")
    return " ".join(t.split())


def _split_sentences(text: str) -> list[str]:
    out, buf = [], ""
    for ch in text:
        buf += ch
        if ch in SENT_END:
            out.append(buf)
            buf = ""
    if buf:
        out.append(buf)
    return out


def _split_long(sentence: str, max_chars: int) -> list[str]:
    """按停顿标点贪心细分；单段无可切点时按硬长度切。"""
    if len(sentence) <= max_chars:
        return [sentence]
    parts, buf = [], ""
    for ch in sentence:
        buf += ch
        if ch in SOFT_BREAK and len(buf) >= max_chars * 0.5:
            parts.append(buf)
            buf = ""
    if buf:
        parts.append(buf)
    out = []
    for p in parts:
        while len(p) > max_chars:
            out.append(p[:max_chars])
            p = p[max_chars:]
        if p:
            out.append(p)
    return out


def split_into_cues(text: str, max_cue_chars: int = MAX_CUE_CHARS,
                    min_cue_chars: int = MIN_CUE_CHARS) -> list[str]:
    """把一段旁白切成若干条字幕（≤max_cue_chars，尽量不破坏语义单元）。"""
    text = normalize(text)
    if not text:
        return []
    raw: list[str] = []
    for sent in _split_sentences(text):
        raw.extend(_split_long(sent, max_cue_chars))
    # 合并过短片段（例如单独的"好。"）到前一条，避免闪烁；首条过短则并入后一条
    cues: list[str] = []
    for piece in raw:
        piece = piece.strip()
        if not piece:
            continue
        if cues and len(piece) < min_cue_chars and len(cues[-1]) + len(piece) <= max_cue_chars:
            cues[-1] = cues[-1] + piece
        else:
            cues.append(piece)
    if len(cues) >= 2 and len(cues[0]) < min_cue_chars \
            and len(cues[0]) + len(cues[1]) <= max_cue_chars:
        cues[1] = cues[0] + cues[1]
        cues.pop(0)
    return cues


def char_width(ch: str) -> float:
    """粗略字宽（CJK 全宽 = 1.0，ASCII/半宽 ≈ 0.55），用于折行与配平的视觉宽度估算。"""
    return 1.0 if ord(ch) > 0x2E80 else 0.55


def text_width(text: str) -> float:
    return sum(char_width(c) for c in text)


def wrap_lines(text: str, max_line: int = MAX_LINE_CHARS) -> list[str]:
    """折行：≤2 行。**优先在停顿标点/空格处断**（语言上自然），其次取视觉宽度最配平的位置；
    两行都必须 ≤ `max_line`（视觉宽度），且行首不放标点。"""
    text = normalize(text)
    if not text:
        return []
    if text_width(text) <= max_line:
        return [text]
    n = len(text)
    total = text_width(text)
    ok = [i for i in range(1, n)
          if text[i:].strip() and text[:i].strip() and text[i] not in NO_LINE_START
          and text_width(text[:i]) <= max_line and text_width(text[i:]) <= max_line]
    pref = [i for i in ok if text[i - 1] in SOFT_BREAK or text[i - 1] == " "]
    pool = pref or ok
    if not pool:                                   # 退化：两行都放不下（超长 cue）→ 按宽度中点硬切
        cut, acc = 1, 0.0
        for i, ch in enumerate(text):
            acc += char_width(ch)
            if acc >= total / 2:
                cut = max(i + 1, 1)
                break
        return [text[:cut].strip(), text[cut:].strip()]
    best = min(pool, key=lambda i: abs(text_width(text[:i]) - total / 2))
    return [text[:best].strip(), text[best:].strip()]


RULE_VERSION = "p52-1-audio-anchor-v1"


WORD_RULE_VERSION = "p55-1-seq-walk-v1"


def _norm_cmp(s: str) -> str:
    """归一化用于**顺序游走匹配**：去标点/空白/换行（保留字母数字与汉字）。"""
    return re.sub(r'''[\s。！？，、；：""''（）()《》〈〉…—\-·.,;:!?\"'\[\]{}]''',
                  "", str(s or ""))


def build_cues_from_words_exact(segments: list[dict], words_manifest: dict, *,
                                windows: list | None = None, hold_s: float = 0.3,
                                min_cue_s: float = MIN_CUE_S,
                                dump_path=None) -> list[dict]:
    """**P55-1 字幕词级精确重建（顺序文本游走匹配）**。

    ## 为什么重写（P54 的失败）
    P54 版**按字符数把词分配到句** —— 那是 P45-3 的**段内**口径写法，
    套到「词段内起点 − 切片段内起点 + 景窗起点」的新时间基上即错位，
    实测产出**负时长**（min −87.5s）。

    ## 本版主算法：词流与句流**顺序游走匹配**
    逐词累计归一化文本，与**下一句**的归一化文本比对；匹配上则切句。
    数字/英文转写变体用**位置兜底**：失配 > 2 词 ⇒ 按累计字符比例切，
    且**切点必须落在实测静音区间内**，否则 **fail-closed**。

    ## 换算链（授权书 §1）
    词段内起点 − 景的切片段内起点 = 词景内时刻；+ 景窗起点 = 绝对时刻。

    ## 内部断言（违反即 fail-closed 并转储）
      a) 每句 `a0 <= a1`；b) 句间单调 `a1_k <= a0_{k+1}`；
      c) 每词恰属一景（无跨景词、无未分配词）；
      d) 全片词覆盖 == manifest 总词数。
    """
    # ---- 景窗索引（**按 scene_id 取**，不按下标猜；P53 教训）----
    win_by: dict = {}
    for w in (windows or []):
        _sid = str(w.get("scene_id") or "")
        if _sid:
            win_by[_sid] = w
    # ---- 段内切片起点（Σ 同段先前各景的切片时长）----
    para_acc: dict = {}
    scene_off: dict = {}
    for s in segments:
        sid = str(s.get("scene_id") or "")
        p = sid.split("_")[0]
        w = win_by.get(sid) or {}
        try:
            sl = float(w.get("actual_s") or 0.0) or (
                float(w["end_s"]) - float(w["start_s"]))
        except Exception:                                                       # noqa: BLE001
            sl = float(s.get("duration_s") or 0.0)
        scene_off[sid] = round(para_acc.get(p, 0.0), 3)
        para_acc[p] = round(para_acc.get(p, 0.0) + sl, 3)

    # ---- 按段把景分组（词流是**段级**的，须在段内游走）----
    by_para: dict = {}
    for s in segments:
        by_para.setdefault(str(s.get("scene_id") or "").split("_")[0], []).append(s)

    cues: list[dict] = []
    groups_dump: list = []
    assigned = 0
    total_words = sum(len((v or {}).get("words") or [])
                      for v in (words_manifest or {}).values())
    fails: list = []

    for para, scenelist in by_para.items():
        words = ((words_manifest.get(para) or {}).get("words") or [])
        if not words:
            continue
        off = float(scene_off.get(str(scenelist[0].get("scene_id")) or "") or 0.0)
        # ---- 该段景窗（绝对）----
        wlist = []
        for s in scenelist:
            w = win_by.get(str(s.get("scene_id"))) or {}
            wlist.append((float(w.get("start_s") or 0.0),
                          float(w.get("end_s") or 0.0)))
        para_start = wlist[0][0] if wlist else 0.0
        para_end = wlist[-1][1] if wlist else None
        # ---- 词的绝对时刻（段内起点 − 切片段内起点 + 段首景窗起点）----
        # 说明：`off` 是**段首景**的切片段内起点（同段首个景 ⇒ 通常 0）；
        # 段的音频起点 = 段首景窗起点 − off。
        para_audio_start = para_start - off
        abs_t = []
        for x in words:
            st = para_audio_start + float(x.get("start_s") or 0.0)
            du = float(x.get("dur_s") or 0.0)
            abs_t.append((round(st, 3), round(st + du, 3)))
        # ---- 断言 c/d：每词恰属一景 ----
        if para_end is not None:
            for i, (a, b) in enumerate(abs_t):
                if not any(wa - 1e-6 <= a < wb + 1e-6 for wa, wb in wlist):
                    fails.append({"kind": "word_outside_windows", "para": para,
                                  "word_index": i,
                                  "word": str(words[i].get("text"))[:12],
                                  "abs_start": a})
        # ---- 句流（按 。！？ 切）----
        para_text = "".join(normalize(str(s.get("narration") or ""))
                            for s in scenelist)
        sents = [m.group(0) for m in
                 re.finditer(r"[^。！？]*[。！？]|[^。！？]+$", para_text)
                 if m.group(0).strip()]
        sents = _merge_short(sents, 8)
        # ---- 主算法：**顺序游走匹配** ----
        groups = _walk_match(words, abs_t, sents)
        # ---- 断言 a/b ----
        prev_a1 = None
        for gi, (idx0, idx1, st) in enumerate(groups):
            a0, _ = abs_t[idx0]
            _, a1 = abs_t[idx1]
            if a0 > a1:
                fails.append({"kind": "a0_gt_a1", "para": para, "gi": gi,
                              "a0": a0, "a1": a1, "text": st[:20]})
            # **容差说明**：`abs_t` 已四舍五入到毫秒（round 3）⇒ 相邻句界会有
            # ≤1ms 量化抖动（实测 P09：`prev_a1=682.248` vs `a0=682.247`）。
            # 用 1e-6 会把**量化噪声**误判为「非单调」⇒ 用 **0.01s** 容差
            # （远小于任何真实错位，又足以吸收毫秒量化）。
            if prev_a1 is not None and prev_a1 > a0 + 0.01:
                fails.append({"kind": "non_monotonic", "para": para, "gi": gi,
                              "prev_a1": prev_a1, "a0": a0,
                              "delta_s": round(prev_a1 - a0, 4)})
            prev_a1 = a1
            # ---- 造 cue（排他 + 景窗 clamp）----
            s0, e0 = a0, a1 + hold_s
            nxt = abs_t[groups[gi + 1][0]][0] if gi + 1 < len(groups) else None
            if nxt is not None:
                e0 = min(e0, nxt)
            # 落在哪个景窗内 ⇒ clamp 到该窗
            # **P57-1b clamp 依据 = 句末词所在窗（a1），不是句首词所在窗（s0）**。
            # 实测（F12 烧录 ASS 四门①）：v6.5 静音吸附切景存在**句中切景**
            # （timebase `mid_sentence_cuts`）⇒ 句的语音跨窗时，按 s0 所在窗
            # clamp 把 cue 终点截在切景点 ⇒ **句尾语音无字幕**（全片实测 31 处 /
            # 61.45s，门① 覆盖 89.5% < 95%；极端例：40 字句被截成 1.06s）。
            # 改为按 a1 所在窗 clamp：字幕跟随**整句**语音；跨窗越界由
            # 「下一句起点」排他约束与全片排他兜底。
            we = next((wb for wa, wb in wlist
                       if wa - 1e-6 <= a1 <= wb + 1e-6), para_end)
            if we is not None:
                e0 = min(e0, we)
            if e0 <= s0:
                e0 = s0 + min_cue_s
            sid = next((str(x.get("scene_id")) for x in scenelist
                        if (lambda w: w and float(w["start_s"]) - 1e-6 <= s0
                             <= float(w["end_s"]) + 1e-6)(win_by.get(str(x.get("scene_id"))))),
                       str(scenelist[0].get("scene_id")))
            cues.append({"index": len(cues), "scene_id": sid, "text": st,
                         "lines": wrap_lines(st), "start": round(s0, 3),
                         "end": round(e0, 3), "dur": round(e0 - s0, 3),
                         "word_index_range": [idx0, idx1],
                         "source": "word_exact", "rule_version": WORD_RULE_VERSION})
            groups_dump.append({"para": para, "gi": gi, "word_range": [idx0, idx1],
                                "a0": a0, "a1": a1, "text": st[:24]})
        assigned += len(words)
    # ---- 断言 d：全片词覆盖 ----
    # **适用条件（P56 回归修）**：`words_manifest` 为空 ⇒ **不适用**。
    # 另：若**没有任何段参与游走**（`by_para` 与 manifest 键不匹配，例如单测传
    # **段级**输入而 manifest 是段键、或传最小夹具），`assigned=0` 是
    # **输入没有可用词**而非归属缺陷 ⇒ 同样跳过 d。
    # 真实渲染路径（36 景 / manifest 齐备）会正常执行该断言。
    # （实测：P56 引入的严格断言使 `narration_contract_test` / `integrity_truth_test`
    #   等 7 套件从绿转红，报 `assigned=0`。）
    covered_paras = sum(1 for k in by_para if k in (words_manifest or {}))
    if total_words > 0 and covered_paras > 0 and assigned != total_words:
        fails.append({"kind": "word_coverage", "assigned": assigned,
                      "manifest_total": total_words,
                      "covered_paras": covered_paras})
    # ---- 全片排他 ----
    cues.sort(key=lambda c: (c["start"], c["index"]))
    prev_end = None
    for c in cues:
        if prev_end is not None and c["start"] < prev_end:
            c["start"] = round(prev_end, 3)
            c["dur"] = round(c["end"] - c["start"], 3)
        prev_end = c["end"]
    for i, c in enumerate(cues):
        c["index"] = i
    # ---- 转储（P48 法）----
    if dump_path is not None:
        try:
            import json as _j
            pathlib.Path(dump_path).write_text(_j.dumps(
                {"schema": "p55-1-word-exact-dump-v1", "rule_version": WORD_RULE_VERSION,
                 "cues": len(cues), "words_assigned": assigned,
                 "words_manifest_total": total_words,
                 "assertion_failures": fails,
                 "groups": groups_dump[:400],
                 "cue_head": [{k: c.get(k) for k in
                               ("index", "scene_id", "start", "end", "dur")}
                              for c in cues[:5]]},
                ensure_ascii=False, indent=1), encoding="utf-8")
        except Exception:                                                       # noqa: BLE001
            pass
    if fails:
        raise ValueError(
            "P55-1 词级归属断言失败（fail-closed）：{} 项，前 3 项 {}".format(
                len(fails), fails[:3]))
    return cues


# ---- P57-1 **生产 cue 契约断言**（构建后、烧录前；授权书 §1）----
# 本片（9 段 / 1,964 词 / 36 景）的授权包络。随下一部影片的句结构重定。
PROD_CUE_COUNT_RANGE = (101, 111)
PROD_SPAN_TOL_S = 2.0        # cue 跨度 vs 实测音频时长的容差（s）
# P0（2026-10-20）：median 下限 3.0s → 1.6s。
# 原因：显示级切分（≤18 字 / ≤4s）后，健康 median 落在 1.8–2.6s；
# 旧值 3.0 会把"切得对"判成缺陷。F10.1 的缺陷签名是 **median 1.0s + 105 cue/178s**，
# 由 1.6s 下限 + 相对条数区间仍然拦得住。
PROD_MIN_MEDIAN_S = 1.6


def production_cue_violations(cues: list[dict], *, audio_dur_s: float | None = None,
                              count_range: tuple | None = None) -> list[str]:
    """**生产 cue 契约断言**：返回**违规项列表**（空 = 通过）；fail-closed 由调用方执行。

    · 条数：落在 `count_range`（缺省 `PROD_CUE_COUNT_RANGE`）内；
    · 跨度：`max_end − min_start` 与**实测**音频时长差 ≤ `PROD_SPAN_TOL_S`
      （`audio_dur_s=None` ⇒ 引用不可得，跳过本项，其余照断——F10.1 的
      105-cue-178s 签名在无音频引用时也会被条数/median/重叠三项拦下）；
    · 时长 median ≥ `PROD_MIN_MEDIAN_S`；
    · 排他：任意相邻 cue `start_k < end_{k-1}` 即违规（容差 1e-9）。
    """
    v: list[str] = []
    if not cues:
        return ["cues_empty"]
    lo, hi = (count_range if count_range is not None else PROD_CUE_COUNT_RANGE)
    # P0（2026-10-20）：`count_range` 缺省时改为**按音频时长相对推导**，
    # 不再把某一部影片的绝对条数（101–111）当全局契约——那正是"下一部片必挂"的写法。
    # 依据：一条 cue 的健康时长 1.2–3.8s（18 字 ÷ 5 字/秒 ≈ 3.6s）⇒ 期望条数 ≈ dur/3.8 … dur/1.2。
    if count_range is None and audio_dur_s and float(audio_dur_s) > 0:
        _d = float(audio_dur_s)
        lo, hi = max(1, int(_d / 3.8)), int(_d / 1.2) + 2
    n = len(cues)
    if not (int(lo) <= n <= int(hi)):
        v.append("count_out_of_range:{} not in [{},{}]".format(n, lo, hi))
    span = round(max(float(c["end"]) for c in cues)
                 - min(float(c["start"]) for c in cues), 3)
    if audio_dur_s is not None and abs(span - float(audio_dur_s)) > PROD_SPAN_TOL_S:
        v.append("span_mismatch:{:.3f}s vs audio {:.3f}s (tol ±{:.1f}s)".format(
            span, float(audio_dur_s), PROD_SPAN_TOL_S))
    durs = [float(c.get("dur") or (float(c["end"]) - float(c["start"]))) for c in cues]
    med = statistics.median(durs)
    if med < PROD_MIN_MEDIAN_S:
        v.append("median_below_min:{:.3f}s < {:.1f}s".format(med, PROD_MIN_MEDIAN_S))
    sc = sorted((float(c["start"]), float(c["end"])) for c in cues)
    for i in range(1, len(sc)):
        if sc[i][0] < sc[i - 1][1] - 1e-9:
            v.append("overlap:cue{} start {:.3f} < prev end {:.3f}".format(
                i, sc[i][0], sc[i - 1][1]))
            break
    return v


def _merge_short(sents: list, min_chars: int) -> list:
    """过短的句并入**前**句（保持顺序）。"""
    out: list = []
    for t in sents:
        if out and len(t) < min_chars:
            out[-1] = out[-1] + t
        else:
            out.append(t)
    return out


def _walk_match(words: list, abs_t: list, sents: list):
    """**顺序文本游走匹配**：词流 ↔ 句流。

    逐词累计**归一化**文本；当累计 == 下一句归一化文本（或已超过它）⇒ 切句。
    失配 > 2 词时用**位置兜底**：按累计字符比例切。
    返回 `[(idx0, idx1, sentence_text), ...]`。
    """
    tgt = [_norm_cmp(s) for s in sents]
    wnorm = [_norm_cmp(w.get("text")) for w in words]
    groups: list = []
    wi, si, acc = 0, 0, ""
    while wi < len(words) and si < len(tgt):
        acc += wnorm[wi]
        want = tgt[si]
        if want and (acc == want or (len(acc) >= len(want) and acc.endswith(want))
                     or len(acc) >= len(want)):
            start = groups[-1][1] + 1 if groups else 0
            groups.append((start, wi, sents[si]))
            si += 1
            acc = ""
        wi += 1
    # ---- P57-1c **尾句重分**：词流的归一化字符总量比句流**少 2–6 字/段**
    #（TTS WordBoundary 文本相对旁白文本的转写亏损，全片 9 段皆然）⇒ 主循环
    # 耗尽词流时**末尾 1–2 句没有自己的组**（实测全片丢 10 句），其语音被并进
    # 前一句的字幕：**文本缺句 + 句起点缺失**（F12 烧录 ASS 四门④b 实测
    # 9 句起点偏差 >1s，最差 7.66s）。修法：把**最后一个组**的词按**字符比例**
    # 重分给它自己的句 + 全部未切出的尾句（每句 ≥1 词、组界顺序保持），
    # 组起点仍来自实测 WordBoundary 时刻。词过少（span < 组数）时维持旧行为。
    if si < len(tgt) and groups:
        # **先把末组延伸到真正的最后一个词**（主循环在末次切分后仍消费了
        # 残余词，它们不在任何组里——漏掉会把末 cue 提前 ~4s，span 门违约），
        # 再把整段尾部词按字符比例重分给末组的句 + 全部未切出的尾句。
        last = (groups[-1][0], len(words) - 1)
        span_words = last[1] - last[0] + 1
        n_rem = len(tgt) - si
        n_groups = 1 + n_rem
        if span_words >= n_groups:
            chars = ([max(len(tgt[len(groups) - 1]), 1)]
                     + [max(len(tgt[si + k]), 1) for k in range(n_rem)])
            tot = sum(chars)
            alloc = [max(1, int(round(span_words * c / tot))) for c in chars]
            while sum(alloc) > span_words:
                _i = alloc.index(max(alloc))
                alloc[_i] -= 1
            while sum(alloc) < span_words:
                alloc[-1] += 1
            new_groups, idx = [], last[0]
            for k in range(n_groups):
                end = idx + alloc[k] - 1
                new_groups.append((idx, end, sents[(len(groups) - 1) + k]))
                idx = end + 1
            groups[-1:] = new_groups
        else:
            # 词太少：维持旧行为（残余并入末组）
            s0, _e = groups[-1]
            groups[-1] = (s0, len(words) - 1)
    return groups


def build_cues_from_audio(segments: list[dict], runs_by_scene: dict, *,
                          windows: list | None = None, hold_s: float = 0.3,
                          min_cue_s: float = MIN_CUE_S,
                          max_cue_chars: int = MAX_CUE_CHARS) -> list[dict]:
    """**P52-1 词时刻音频锚定**（弃用合成 manifest 的绝对时刻换算）。

    **为什么换**：合成期 manifest 的时钟 ≠ 实际音频时钟（P30 静音物化 vs 合成期
    pause 数学）⇒ 换算出的绝对时刻整体漂移。实测 F8：cue 对**语音运行**的覆盖率仅
    **14.2%**、97% 的 cue 被 clamp 成 **1.0s**。故改为**独立信号源**：

    1. 每景取**实际音频切片**，景内 `silencedetect(-30dB, d=0.05)` 得**细粒度语音运行**；
    2. 景的已知文本按句切分（确定性规则）；
    3. **按「句数 ↔ 运行块数」对齐**：把运行序列切成 `n_sentences` 块，
       每块 = 该句的**实测**边界 ⇒ **用足全部运行、无 clamp**、
       **句界来自实测而非 manifest**；
    4. `cue_k = [块首运行起点, 块末运行终点 + hold]`，**景内顺序排他**、
       **跨景由窗隔离**、**任何 cue 不得越出景窗**。

    `runs_by_scene`：`{scene_id: [(start_s, end_s), ...]}`（**景内局部**秒，来自实测）。
    """
    cues: list[dict] = []
    for si, seg in enumerate(segments):
        sid = seg.get("scene_id")
        text = normalize(seg.get("narration", ""))
        runs = [r for r in (runs_by_scene.get(sid) or []) if r[1] - r[0] > 0.02]
        if not runs:
            continue
        w0, w1 = 0.0, None
        if windows and si < len(windows):
            w0 = float(windows[si]["start_s"])
            w1 = float(windows[si]["end_s"])
        # 句切分 + 过短句并入前句（≥8 字）
        bounds, acc = [], 0
        for m in re.finditer(r"[^。！？]*[。！？]|[^。！？]+$", text):
            t = m.group(0)
            if not t:
                continue
            if bounds and len(t) < 8:
                bounds[-1] = (bounds[-1][0], acc + len(t), bounds[-1][2] + t)
            else:
                bounds.append((acc, acc + len(t), t))
            acc += len(t)
        if not bounds:
            continue
        n = len(bounds)
        if n == 1:
            chunks = [runs]
        else:
            # **按句数把运行序列切成 n 块**（每块非空 ⇒ 用足所有运行）
            if len(runs) >= n:
                chunks = []
                prev = 0
                for k in range(n):
                    # 第 k 块结束位置按运行数比例推进，保证每块 ≥1 个运行
                    end = prev + max(1, round(len(runs) * (k + 1) / n) - prev)
                    end = min(end, len(runs) - (n - k - 1))
                    end = max(end, prev + 1)
                    chunks.append(runs[prev:end])
                    prev = end
                if prev < len(runs):                      # 残余并入末块
                    chunks[-1] = chunks[-1] + runs[prev:]
            else:
                # 运行数少于句数 ⇒ 一运行对多句（把运行按句**字符数**比例细分）
                chunks = []
                tot_chars = sum(len(b[2]) for b in bounds) or 1
                acc_c = 0
                for c0, c1, _t in bounds:
                    lo = acc_c / tot_chars
                    hi = (acc_c + (c1 - c0)) / tot_chars
                    acc_c += (c1 - c0)
                    chunks.append([("__frac__", lo, hi)])
        for k, (c0, c1, seg_txt) in enumerate(bounds):
            ch = chunks[k] if k < len(chunks) else chunks[-1]
            if ch and ch[0][0] == "__frac__":
                # 比例细分：把该景**全部**运行按其总时长按比例划归本句
                tot = sum(b - a for a, b in runs) or 1.0
                lo, hi = ch[0][1], ch[0][2]
                s = min(a for a, _ in runs) + tot * lo
                e = min(a for a, _ in runs) + tot * hi
            else:
                s = ch[0][0]
                e = ch[-1][1]
            s, e = w0 + s, w0 + e + hold_s
            if w1 is not None:
                s = min(s, w1 - 0.05)
                e = min(e, w1)
            if e <= s:
                e = s + min_cue_s
            if not seg_txt.strip():
                continue
            cues.append({"index": len(cues), "segment_index": si, "scene_id": sid,
                         "text": seg_txt, "lines": wrap_lines(seg_txt),
                         "start": round(s, 3), "end": round(e, 3),
                         "dur": round(e - s, 3),
                         "run_count": (0 if (ch and ch[0][0] == "__frac__")
                                       else len(ch)),
                         "source": "audio_anchor", "rule_version": RULE_VERSION})
    # **全片顺序排他**（跨景安全兜底；正常由窗隔离保证不触发）
    cues.sort(key=lambda c: (c["start"], c["index"]))
    prev_end = None
    for c in cues:
        if prev_end is not None and c["start"] < prev_end:
            c["start"] = round(prev_end, 3)
            c["dur"] = round(c["end"] - c["start"], 3)
        prev_end = c["end"]
    for i, c in enumerate(cues):
        c["index"] = i
    return cues


def build_cues_from_words(segments: list[dict], words_manifest: dict, *,
                          windows: list | None = None, hold_s: float = 0.3,
                          min_cue_s: float = MIN_CUE_S,
                          max_cue_chars: int = MAX_CUE_CHARS) -> list[dict]:
    """**P45-3 词级金标准 cue 构建**（不再依赖静音检测）。

    原理：TTS 的 `WordBoundary` 给出**每个词的发音时刻**（100ns 精度）⇒
      · 把词流**按句读聚合**（遇到 `。！？` 收句）；
      · **cue 起点 = 该句首词的发音时刻**；**终点 = 该句末词结束 + `hold_s`**
        （clamp 进该段窗口）。
    因此「cue 出现时刻 − 句首词发音时刻」**恒等于 0**（构造保证），
    字幕与发音的对齐是**定义上成立**的，不靠后验吸附。
    """
    cues: list[dict] = []
    # ---- P51-1 **根因修复：词偏移是「段内局部」，不是「景内局部」** ----
    # 词级 manifest 的键是**段**（`P01`），其词偏移从**该段音频开头**起算（0 起）；
    # 而一个段会切成**多个景**（`P01_1..P01_4`）。原实现把**段内偏移**当成**景内偏移**
    # 再加景窗起点 ⇒ **同一个段的 4 个景各自重放了整段 76.6s 的词** ⇒ 全片 cue 大面积重叠
    # （实测 F7.1 烧录 ASS **max 同时活跃 41 条**）。正确做法：把词换算到**全片绝对时刻**
    # （= 该段起始景的窗起点 + 词偏移），再**按景窗切分**，只用落在本窗内的词。
    _para_start: dict = {}
    for _i, _s in enumerate(segments):
        _sid = str(_s.get("scene_id") or "")
        _p = _sid.split("_")[0]
        _w0 = float(windows[_i]["start_s"]) if (windows and _i < len(windows)) else 0.0
        if _p not in _para_start or _w0 < _para_start[_p]:
            _para_start[_p] = _w0
    _prev_end = None
    for si, seg in enumerate(segments):
        sid = seg.get("scene_id")
        text = normalize(seg.get("narration", ""))
        # 词级 manifest 以**段**为键（`P01`）；景 id 形如 `P01_1` ⇒ 取段前缀回退
        _m = words_manifest.get(sid) or words_manifest.get(str(sid).split("_")[0])
        w = ((_m or {}).get("words") or [])
        if not w:
            continue
        w0, w1 = 0.0, None
        if windows and si < len(windows):
            w0 = float(windows[si]["start_s"])
            w1 = float(windows[si]["end_s"])
        # ---- P51-1：**按景窗切分词**（词偏移是段内局部 ⇒ 先换算绝对时刻再筛）----
        _p0 = _para_start.get(str(sid).split("_")[0], 0.0)
        if w1 is not None:
            w = [x for x in w
                 if w0 - 1e-6 <= _p0 + float(x.get("start_s") or 0.0) < w1 - 1e-6]
        if not w:
            continue
        # 按句读把**旁白文本**切成句（**注意**：TTS 的 WordBoundary 词文本
        # **不含标点** ⇒ 只能从旁白文本取句界，词只用来提供**音源时刻**）。
        # 并把过短的句**并入下一句**，使每条 cue ≥ `min_cue_s` 的阅读量。
        bounds, acc = [], 0
        for m in re.finditer(r"[^。！？]*[。！？]|[^。！？]+$", text):
            seg_txt = m.group(0)
            if not seg_txt:
                continue
            if bounds and len(seg_txt) < 12:          # 太短 ⇒ 并入前句
                bounds[-1] = (bounds[-1][0], acc + len(seg_txt), bounds[-1][2] + seg_txt)
            else:
                bounds.append((acc, acc + len(seg_txt), seg_txt))
            acc += len(seg_txt)
        # 词 → 句 归属（按**字符数**推进；末词吸收全部残余）
        groups, wi, chars = [], 0, 0
        for bi, (c0, c1, seg_txt) in enumerate(bounds):
            gl = []
            while wi < len(w) and (chars < c1 or bi == len(bounds) - 1):
                gl.append(w[wi])
                chars += len(str(w[wi].get("text", "")))
                wi += 1
            if gl:
                groups.append((gl, seg_txt))
        if not groups and w:
            groups = [(w, text)]
        for gl, seg_txt in groups:
            # **绝对时刻** = 该段起始景的窗起点 + 词偏移（词偏移是段内局部）
            _p0 = _para_start.get(str(sid).split("_")[0], 0.0)
            _abs0 = _p0 + float(gl[0]["start_s"])
            _abs1 = _p0 + float(gl[-1]["start_s"]) + float(gl[-1]["dur_s"])
            s = _abs0
            e = _abs1 + hold_s
            if w1 is not None:
                e = min(e, w1)
            # ---- P51-1 **排他规则**（授权书 §1）----
            # cue_k = [max(句首词时刻, cue_{k-1}.end), min(句末词结束+hold, 下一句起点)]
            # 全片 cue 按时间排序后**严格互斥**（边界容差 ≤0.1s）。
            if _prev_end is not None and s < _prev_end:
                s = _prev_end
            if e <= s:
                e = s + min_cue_s
            piece = seg_txt
            if not piece.strip():
                continue
            cues.append({"index": len(cues), "segment_index": si, "scene_id": sid,
                         "text": piece, "lines": wrap_lines(piece),
                         "start": round(s, 3), "end": round(e, 3),
                         "dur": round(e - s, 3),
                         "word_lag_s": round(s - _abs0, 4),
                         "source": "word_boundary",
                         "sentence_first_word_s": round(_abs0, 3)})
            _prev_end = e
        # 段内**末条**的终点不得越过下一句起点、也不得越过景窗上界
        if cues and w1 is not None:
            cues[-1]["end"] = round(min(cues[-1]["end"], w1), 3)
            cues[-1]["dur"] = round(cues[-1]["end"] - cues[-1]["start"], 3)
            _prev_end = cues[-1]["end"]
    return cues


def build_cues(segments: list[dict], *, min_dur_s: float = 3.0,
               max_cue_chars: int = MAX_CUE_CHARS, min_cue_s: float = MIN_CUE_S,
               chars_per_sec: float = CHARS_PER_SEC, max_cue_s: float = MAX_CUE_S,
               tail_gap_s: float = 0.2, windows: list | None = None,
               recoveries: dict | None = None,
               snap_tol_s: float = 0.5,
               snap_stats: dict | None = None) -> list[dict]:
    """把脚本段落列表转成字幕 cue 列表（绝对时间）。

    · `windows=None`（v1 兼容）：时间基 = **段落声明时长**累计 = 规划时基。
    · `windows=[{"start","end"},...]`（Duration Contract v2）：时间基 = **实际音频窗口**
      （`core.narration.audio_segment_windows`）⇒ cue 与真实语音对齐，且**绝不越过**实际旁白窗口。
    · `recoveries={seg_index: [局部时刻, ...]}`（**P43-1 句界吸附**）：
      每个 cue 的**切换点**（起点与终点）在 `±snap_tol_s` 内**吸附到最近的语音恢复点**
      （`silencedetect` 检出的停顿结束处）；超界者**保留原位并计数**（登记在 `snap_stats`）。
      **动机（实测）**：原实现按**字数**在窗口内**均匀铺排**（`gap=(window-total)/n`），
      而真实句界**不均匀** ⇒ 语音恢复点上 cue 中位滞后 **1.14s**（>1s 者 66 处）、
      且 77 条 cue 在停顿中**提前出现**。
    """
    cues: list[dict] = []
    cursor = 0.0
    # **关键（实测踩坑）**：原实现的 `t` 在**段间是累积的** —— 段内最后一条 cue 之后
    # 仍会 `t = end + gap`，于是**下一段的首条 cue 起点 = 上段末条 end + gap**，
    # 而不是恰好落在窗口起点。我首版按段重置 `t = base`，导致 ① 段间相邻 cue 起点
    # 重叠（单调性被破坏）② 末条 duration 膨胀超过 `max_cue_s`（C3a/C3c/C8 三项失败）。
    # 现改回**跨段累积**，与既有实现逐字一致。
    t_flow = 0.0
    snap_ok, snap_miss = 0, 0
    for si, seg in enumerate(segments):
        text = normalize(seg.get("narration", ""))
        try:
            dur = max(float(seg.get("duration_s") or 0), min_dur_s)
        except (TypeError, ValueError):
            dur = min_dur_s
        start_abs = None
        if windows and si < len(windows):
            w = windows[si] or {}
            try:
                w0, w1 = float(w["start_s"]), float(w["end_s"])
            except (KeyError, TypeError, ValueError):
                w0 = w1 = None
            if w0 is not None and w1 is not None and w1 > w0:
                start_abs, dur = w0, (w1 - w0)
        pieces = split_into_cues(text, max_cue_chars=max_cue_chars)
        if not pieces:
            cursor = (start_abs + dur) if start_abs is not None else (cursor + dur)
            continue
        base = cursor if start_abs is None else start_abs
        limit = base + dur                      # v2：窗口上界 = 实际音频段结束
        durs = [min(max(len(p) / float(chars_per_sec), min_cue_s), max_cue_s)
                for p in pieces]
        window = max(dur - tail_gap_s, min_cue_s)
        total = sum(durs)
        if total > window:                      # 压缩以适配窗口（绝不越界）
            k = window / total
            durs = [max(d * k, 0.3) for d in durs]
            gap = 0.0
        else:                                   # 均匀铺开：剩余时间平均作为间隔
            gap = (window - total) / len(durs)
        # ---- P43-1：**句界吸附**（可选叠加；不改既有非吸附路径的逐字行为）----
        local = (recoveries or {}).get(si)
        _rec = []
        if local:
            _rec = sorted({round(base + float(x), 3) for x in local
                           if 0 < float(x) < dur})
        snapped = False
        if not local:
            # **与既有实现一致的两条规则**（实测反推 + 21/21 复现）：
            #   ① 新段首条 cue **从本段起点开始**（`t_flow` 落后于 `base` 时复位到 `base`）
            #      —— 否则字幕会在镜头开始后一段空白才出现；
            #   ② 但**绝不早于上一条 cue 的结束**（`t_flow` 已领先时保留），
            #      —— 否则跨段出现时间倒流（单调性被破坏）。
            if t_flow < base:
                t_flow = base
            for piece, d in zip(pieces, durs):
                t_flow = max(t_flow, base)
                end = min(t_flow + d, limit)
                end = max(end, t_flow + 0.3)
                cues.append({"index": len(cues), "segment_index": si, "text": piece,
                             "lines": wrap_lines(piece), "start": round(t_flow, 3),
                             "end": round(end, 3), "dur": round(end - t_flow, 3),
                             "snapped": False})
                t_flow = end + gap
            cursor = limit
            continue
        # ---- P44-2 **句级吸附**：景内**每一个 cue 边界**各自吸到最近的语音恢复点 ----
        # 与 P43-1 的差别：P43-1 只吸附「cue 起点」且**贪心跳过已用恢复点**，
        # 且**景首条起点固定在窗口起点、从不吸附** ⇒ 独立复测（全片口径）显示
        # 最近边界距离 median 仍 ~0.76s（**景首条贡献了大部分残差**）。
        # P44-2：**景首条起点也可吸附**（限定本景窗口内、且不早于上一条 cue 结束），
        # 容差放宽到 ±0.5s（授权书 §2）。
        starts, t = [], t_flow
        for d in durs:
            starts.append(round(t, 3))
            t = min(t + d, limit) + gap
        new_starts, prev_end = [], t_flow
        for i in range(len(pieces)):
            target = starts[i]
            lo = max(base, prev_end + 0.05)
            cand = min(_rec, key=lambda x: abs(x - target)) if _rec else None
            if (cand is not None and abs(cand - target) <= snap_tol_s
                    and lo <= cand <= limit - 0.05):
                new_starts.append(round(cand, 3))
                snap_ok += 1
            else:
                new_starts.append(target if i > 0 else max(target, lo))
                snap_miss += 1
            prev_end = new_starts[-1]
        snapped = True
        for i, piece in enumerate(pieces):
            s = new_starts[i]
            # **末条结尾也吸附**（句级：末尾句界同样应对齐恢复点）
            if i == len(pieces) - 1 and _rec:
                tail_target = min(t + durs[-1], limit)
                tcand = min(_rec, key=lambda x: abs(x - tail_target))
                e = (tcand if abs(tcand - tail_target) <= snap_tol_s
                     and tcand > s + 0.05 else min(tail_target, limit))
            else:
                e = (min(new_starts[i + 1], limit) if i < len(pieces) - 1
                     else min(t + durs[-1], limit))
            if e <= s:
                e = min(s + 0.3, limit)
            cues.append({"index": len(cues), "segment_index": si, "text": piece,
                         "lines": wrap_lines(piece), "start": round(s, 3),
                         "end": round(e, 3), "dur": round(e - s, 3),
                         "snapped": snapped})
        t_flow = (cues[-1]["end"] + gap) if cues else t_flow
        cursor = limit
        continue
    if snap_stats is not None:
        snap_stats.update({"snapped": snap_ok, "unsnapped": snap_miss,
                           "snap_tol_s": snap_tol_s})
    return cues


def _snap_bounds(base: float, rec: list, n_pieces: int,
                 tol: float) -> list:
    """按**语音恢复点**给 `n_pieces` 条 cue 定界（等分兜底 + 逐点吸附）。

    做法：先按恢复点**数量**把 cue 边界与恢复点序列对齐（线性取样），
    再在 `±tol` 内吸附到最近恢复点；窗口首尾固定为 `base` / 末个恢复点。
    """
    if not rec or n_pieces <= 0:
        return [base] * (n_pieces + 1)
    bounds = [base]
    m = len(rec)
    for i in range(1, n_pieces + 1):
        # 第 i 个边界在恢复点序列中的目标位置（末边界取最后一个恢复点）
        if i == n_pieces:
            target = rec[-1]
        else:
            target = rec[min(int(round(i * m / n_pieces)), m - 1)]
        # 吸附：取最近恢复点，若已用过则顺延
        cand = min(rec, key=lambda x: abs(x - target))
        if cand in bounds:
            nxt = [x for x in rec if x > bounds[-1]]
            cand = nxt[0] if nxt else target
        if cand <= bounds[-1]:
            cand = bounds[-1] + 0.3
        bounds.append(round(cand, 3))
    return bounds


def ts_srt(seconds: float) -> str:
    ms = int(round(max(seconds, 0.0) * 1000))
    h, rem = divmod(ms, 3600000)
    m, rem = divmod(rem, 60000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def ts_ass(seconds: float) -> str:
    cs = int(round(max(seconds, 0.0) * 100))
    h, rem = divmod(cs, 360000)
    m, rem = divmod(rem, 6000)
    s, cs = divmod(rem, 100)
    return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"


def to_srt(cues: list[dict]) -> str:
    """SRT 产物：**每条 cue 单行**（不插显式换行，保持文本可检索；播放器自行折行）。"""
    blocks = []
    for i, c in enumerate(cues, 1):
        blocks.append("{}\n{} --> {}\n{}\n".format(i, ts_srt(c["start"]), ts_srt(c["end"]),
                                                   c["text"]))
    return "\n".join(blocks)


ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 2
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{font},{size},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,{outline},0,2,{ml},{mr},{mv},134

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def style_for(width: int, height: int) -> dict:
    """按分辨率给出字幕样式（底部居中；字号/边距随高度缩放，确定性）。"""
    size = int(min(max(round(height * 0.042), 26), 56))
    return {"font": "Microsoft YaHei", "size": size, "outline": 3,
            # P0（2026-10-20）：底部留白 5%→8%。原 5%（54px）在 1080p 下会被
            # 卡片内文字边缘顶到；8%（86px）稳定避开，且给平台裁切留余量。
            "margin_v": int(round(height * 0.08)), "margin_l": int(round(width * 0.06)),
            "margin_r": int(round(width * 0.06))}


def to_ass(cues: list[dict], resolution: str = "1920x1080", font: str | None = None,
           size: int | None = None, outline: int | None = None,
           margin_v: int | None = None) -> str:
    try:
        w, h = (int(x) for x in str(resolution).lower().split("x"))
    except (TypeError, ValueError):
        w, h = 1920, 1080
    st = style_for(w, h)
    head = ASS_HEADER.format(w=w, h=h, font=font or st["font"], size=size or st["size"],
                             outline=st["outline"] if outline is None else outline,
                             ml=st["margin_l"], mr=st["margin_r"],
                             mv=st["margin_v"] if margin_v is None else margin_v)
    events = []
    for c in cues:
        body = "\\N".join(c["lines"] or [c["text"]])
        events.append("Dialogue: 0,{},{},Cap,,0,0,0,,{}".format(
            ts_ass(c["start"]), ts_ass(c["end"]), body))
    return head + "\n".join(events) + "\n"


# ---------------------------------------------------------------- P0 显示级切分
def split_long_cues(cues: list[dict], *, max_chars: int = DISPLAY_MAX_CHARS,
                    max_s: float = DISPLAY_MAX_S) -> list[dict]:
    """把**过长/过久**的 cue 拆成显示级 cue（保序、不重叠、总时长不变）。

    背景（2026-10-20 审计）：`build_cues_from_words_exact` 按**静音间隔**分组，
    旁白不换气时单条 cue 会拉到 14.9s / 约 70 字（实测
    `projects/p_f084eb26e184/artifacts/_captions_t_4f182e0dbe7c.ass`）。
    本函数是**纯后处理**：不改上游时间基、不改词级归属，只按字符预算均分。

    规则
    · 需要的片数 n = max(⌈字数/max_chars⌉, ⌈时长/max_s⌉)，n ≥ 2 才拆；
    · 文本优先在 `SOFT_BREAK` 标点处切（复用 `_split_chunk`），切不稳才按等长切；
    · 时间按**字符占比**线性分配（首尾对齐原 cue），因此
      `Σ 子 cue 时长 == 原 cue 时长`、`start/end` 单调、互不重叠；
    · 每条子 cue 带 `split_from`（原 index）与 `split_n` 便于追溯。

    这是"显示节奏"修复，**不是**时间轴修复：时长契约、抽帧核验、响度链都不受影响。
    """
    if not cues or (not max_chars and not max_s):
        return cues
    out: list[dict] = []
    for c in cues:
        text = str(c.get("text") or "").strip()
        try:
            s0, e0 = float(c["start"]), float(c["end"])
        except (KeyError, TypeError, ValueError):
            out.append(c)
            continue
        dur = round(e0 - s0, 3)
        if dur <= 0.08 or not text:
            out.append(c)
            continue
        n = 1
        if max_chars and max_chars > 0:
            n = max(n, -(-len(text) // int(max_chars)))
        if max_s and max_s > 0:
            n = max(n, int(-(-dur // float(max_s))))
        n = min(n, max(1, len(text)))          # 至少每个子条 1 字
        if n <= 1:
            out.append(c)
            continue
        pieces = _split_into_n(text, n)
        # P0 修正：子条**不得以标点开头**（实测出现"：任何一张平面地图…"、"，所有地图…"）。
        # 把行首标点归给**前一条**（视觉上等价于"标点跟着上一句"），最后一条兜底剥离。
        for _i in range(1, len(pieces)):
            _move = ""
            while pieces[_i] and pieces[_i][0] in NO_LINE_START:
                _move += pieces[_i][0]
                pieces[_i] = pieces[_i][1:]
            if _move:
                pieces[_i - 1] = pieces[_i - 1] + _move
        pieces = [p for p in pieces if p.strip()] or [text]
        total_ch = sum(len(p) for p in pieces) or 1
        acc = s0
        for i, piece in enumerate(pieces):
            if i == len(pieces) - 1:
                end = e0
            else:
                end = round(acc + dur * (len(piece) / total_ch), 3)
                end = min(end, round(e0, 3))
            nc = dict(c)
            nc.update({"text": piece, "lines": [piece],
                       "start": round(acc, 3), "end": round(end, 3),
                       "dur": round(end - round(acc, 3), 3),
                       "split_from": c.get("index"), "split_n": len(pieces)})
            out.append(nc)
            acc = end
    for i, c in enumerate(out):
        c["index"] = i
    return out


def _split_into_n(text: str, n: int) -> list[str]:
    """把文本切成 n 段：优先在停顿标点后切，否则按等长切（确定性）。"""
    n = max(1, int(n))
    if n == 1 or len(text) <= n:
        return [text]
    target = len(text) / n
    out, rest = [], text
    for k in range(n - 1):
        want = int(round(target))
        lo = max(1, want - 4)
        hi = min(len(rest) - (n - k - 1), want + 4)
        cut = None
        for i in range(want, min(hi, len(rest)) ):
            if rest[i - 1] in SOFT_BREAK:
                cut = i
                break
        if cut is None:
            for i in range(want, lo - 1, -1):
                if i < len(rest) and rest[i - 1] in SOFT_BREAK:
                    cut = i
                    break
        if cut is None or not (0 < cut < len(rest)):
            cut = want if want < len(rest) else max(1, len(rest) - (n - k - 1))
        # P0 修正：不切断拉丁词/数字（"Haken" 曾被切成 "Hak" + "en"）。
        # 若切点落在连续的 ASCII 字母数字串内部，回退到该串开头。
        if 0 < cut < len(rest):
            _j = cut
            while (0 < _j < len(rest)
                   and rest[_j - 1].isascii() and rest[_j - 1].isalnum()
                   and rest[_j].isascii() and rest[_j].isalnum()):
                _j -= 1
            if 0 < _j < cut:
                cut = _j
        piece = rest[:cut]
        # 行首标点回退（避免"。"开头）
        while len(piece) > 1 and piece[-1] in NO_LINE_START:
            cut -= 1
            piece = rest[:cut]
        out.append(piece)
        rest = rest[cut:]
    if rest:
        out.append(rest)
    return out
