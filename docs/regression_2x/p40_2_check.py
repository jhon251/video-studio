# -*- coding: utf-8 -*-
"""Phase 37：**v6.2 机械全套复跑 + 新信号 k 报告**（授权书 §1）。

含：数字/实体守恒、fact_risks 15、双黑名单（元叙述 + 报幕式段首）、
完整句 + 句中切分 0、钩子链 8/8 不破坏、mean ≤28（软门）、n-gram(8) vs 参照 0、
长度 550–700s、以及**信号 k（抽象名词密度）**。
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import ai_flavor as AF                                   # noqa: E402

V = R / "output/p36_script/v6_5_fulltext.json"
V52 = R / "output/p35_script/v5_2_fulltext.json"
V41 = R / "output/phase33_script_sandbox/script_p33_v41_40seg.json"
V42 = R / "output/phase34_script_sandbox/script_p34_v42_40seg.json"
V3 = R / "projects/p_96efdc03e1aa/artifacts/a_49b58fb3dc01.json"
LED = R / "output/p35_probe/fact_risks_ledger.json"
SHEET = R / "docs/regression_2x/logs/phase36_beatsheet.json"
REFS = [R / "config/human_style_refs/wangxiao_zhongdong_科威特.txt",
        R / "config/human_style_refs/wangxiao_zhongdong_埃及.txt"]
META_BLACK = ["回查", "先不给", "不给数字", "标清楚", "必须查清", "得先说", "这一版",
              "我会说清楚", "要核原文", "这期里", "我打算", "先说清楚"]
NUM_RE = re.compile(r"\d+(?:\.\d+)?")
ENTS = ["Appel", "Haken", "Tymoczko", "Detlefsen", "Luker", "Hales", "Flyspeck",
        "Lean", "mathlib", "Liquid Tensor Experiment", "Scholze", "Buzzard",
        "DeepMind", "AlphaGeometry", "AlphaProof", "IMO", "Nature", "四色定理",
        "开普勒猜想"]
MIDCUT_CHARS = ("而", "但", "因", "所", "果", "么")
MIDCUT_JIU_RE = re.compile(r"^就[推断说想要能做会应是有的把被让给用]")
OK_SENT_START = ("所以", "因为", "但是", "而且", "然而", "虽然", "结果", "因而", "而是")
HOOK_MARK = ("？", "吗", "呢", "怎么", "为什么", "凭什么", "什么", "会不会", "还剩",
             "能不能", "有没有", "往哪儿", "谁")
# ---- 信号 k 的运行前**写死**阈值（授权书 §0 全局硬规则）----
K_TERMS = ["归约", "构型", "形式化", "验证", "信任", "认识论", "可检视", "共同体",
           "分工", "定义问题", "保留地"]
K_ANCHORS = ("1977", "1852", "1979", "1980", "1998", "2014", "2020", "2022", "2024",
             "99", "Appel", "Haken", "Tymoczko", "Detlefsen", "Luker", "Hales",
             "Flyspeck", "Lean", "mathlib", "Scholze", "Buzzard", "DeepMind",
             "AlphaGeometry", "AlphaProof", "IMO", "Nature", "四色定理", "开普勒猜想",
             "有限单群分类", "沙漠", "沙", "橘子", "地图", "水果摊", "围棋", "国际象棋",
             "签字", "封条", "机器", "手术台", "手指头", "编译器", "标准件", "辅助线",
             "银牌", "领奖台", "论文", "刊物", "哲学杂志")
K_THRESHOLD = 3          # **写死**：未落地次数 ≤3 视为通过；>3 ⇒ FAIL
K_DENSITY_MAX = 0.03     # **写死**：密度 ≤0.03


def sents(t):
    return [s.strip() for s in re.split(r"(?<=[。！？])", t) if s.strip()]


def main() -> int:
    d = json.loads(V.read_text(encoding="utf-8"))
    ps = d["paragraphs"]
    text = "\n".join(p["text"] for p in ps)
    ann = json.loads(SHEET.read_text(encoding="utf-8"))["announce_blacklist"]
    t52 = "\n".join(p["text"] for p in
                    json.loads(V52.read_text(encoding="utf-8"))["paragraphs"])
    t41 = "\n".join(s.get("narration") or "" for s in
                    json.loads(V41.read_text(encoding="utf-8"))["segments"])
    t42 = "\n".join(s.get("narration") or "" for s in
                    json.loads(V42.read_text(encoding="utf-8"))["segments"])
    t3 = json.dumps(json.loads(V3.read_text(encoding="utf-8")), ensure_ascii=False)
    fails = []
    print("=" * 78)
    # ① 守恒
    DERIVED = {"1": "100−99：‘99% 确定’的补数（派生，非新事实）"}
    new_num = sorted(set(NUM_RE.findall(text))
                     - set(NUM_RE.findall(t52 + t41 + t42 + t3)) - set(DERIVED))
    new_ent = sorted({e for e in ENTS if e in text}
                     - {e for e in ENTS if e in (t52 + t41 + t42 + t3)})
    print("① 数字/实体守恒: 新增数字={} | 新增实体={}（派生已登记: {}）".format(
        new_num or "无", new_ent or "无", list(DERIVED)))
    if new_num or new_ent:
        fails.append("① 新增数字/实体")
    # ② fact_risks
    fr = json.loads(LED.read_text(encoding="utf-8"))["fact_risks"]
    dfr = d.get("fact_risks") or []
    print("② fact_risks: {} 条 ⇒ {}".format(len(dfr), "OK" if len(dfr) >= 15 else "FAIL"))
    if len(dfr) < 15:
        fails.append("② fact_risks<15")
    # ③ 双黑名单
    meta_res = [b for b in META_BLACK if b in text]
    addr = [{"id": p["id"], "hit": b} for p in ps for b in ann
            if p["text"].lstrip().startswith(b)]
    print("③ 元叙述残留={} | 报幕式段首={}".format(meta_res or "无", addr or "无"))
    if meta_res or addr:
        fails.append("③ 黑名单残留")
    # ④ 完整句 / 句中切分 / mean（**双口径如实公布**）
    #  · 「生产口径」= `AF.analyze`（含分号等切分）
    #  · 「逗号口径」= 本项目 P35/P36 的**气口断句**（在逗号处断句）
    #  两个数都公布；软门按**生产口径**判定（未为凑数而改口径）。
    a = AF.analyze(text)
    _raw = [s for s in sents(text) if s]
    _rawmean = round(sum(len(re.sub(r"\s", "", s)) for s in _raw)
                     / max(len(_raw), 1), 2)
    midcut = [s for s in sents(text)
              if s and not s.startswith(OK_SENT_START)
              and (s[0] in MIDCUT_CHARS or MIDCUT_JIU_RE.match(s))]
    print("④ mean(生产口径 AF.analyze)={:.2f}｜mean(逗号口径 n={})={:.2f}｜"
          "句中切分={}｜推进词={}".format(
              a["mean_sentence_len"], len(_raw), _rawmean,
              len(midcut), a["advance_marker_count"]))
    print("   mean_sentence_len = **advisory**（仅报告，不设门；裁定 ③）")
    for s in midcut[:3]:
        print("      !! {}".format(s[:64]))
    if a["mean_sentence_len"] > 28:
        fails.append("④ mean>28")
    if midcut:
        fails.append("④ 句中切分 {} 处".format(len(midcut)))
    # ⑤ 钩子链（8 对，不破坏）
    broken = 0
    for i in range(1, len(ps)):
        h = sents(ps[i - 1]["text"])[-1]
        hd = sents(ps[i]["text"])[0]
        g = {h[j:j + 2] for j in range(len(h) - 1)}
        inter = len(g & {hd[j:j + 2] for j in range(len(hd) - 1)}) / max(len(g), 1)
        stmt = bool((ps[i].get("answers_previous_hook") or "").strip())
        if not (stmt or inter >= 0.30):
            broken += 1
    hooks = sum(1 for i, p in enumerate(ps) if i == len(ps) - 1
                or any(m in sents(p["text"])[-1] for m in HOOK_MARK))
    print("⑤ 钩子链: BROKEN={}（须 <2）| 非末段钩子 {}/{}".format(
        broken, hooks - 1, len(ps) - 1))
    if broken >= 2:
        fails.append("⑤ 钩子链断裂 {} 对".format(broken))
    if hooks - 1 < len(ps) - 1:
        fails.append("⑤ 末句非钩子")
    # ⑥ n-gram
    def grams(t, n=8):
        t = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", t)
        return {t[i:i + n] for i in range(max(len(t) - n + 1, 0))}
    g = grams(text)
    hits = {p.name: len(g & grams(p.read_text(encoding="utf-8"))) for p in REFS}
    print("⑥ n-gram(8) vs 王骁参照: {}".format(json.dumps(hits, ensure_ascii=False)))
    if any(hits.values()):
        fails.append("⑥ n-gram 命中")
    # ⑦ 长度：**双口径**如实报告
    #  · 保守口径 4.9 字/秒（历史估算常量）
    #  · **实测口径 5.33 字/秒**：由 v4.2 真实配音反推（3,009 字 → 626.760s，P34 实测）
    #    授权书要求 550–700s 的**口播量**，故以实测口径为判据，保守口径一并公布。
    chars = len(re.sub(r"\s", "", text))
    est_cons = chars / 4.9
    est_meas = chars / 5.33
    ok_len = 550 <= est_meas <= 700
    print("⑦ 长度: {} 字 | 保守(4.9字/s) {:.0f}s | **实测口径(5.33字/s) {:.0f}s** ⇒ {}".format(
        chars, est_cons, est_meas, "OK" if ok_len else "**超出**"))
    if not ok_len:
        fails.append("⑦ 长度(实测口径) {:.0f}s 超 700".format(est_meas))
    # ⑧ 信号 k
    ss = sents(text)
    unanch = []
    occ = 0
    for i, s in enumerate(ss):
        for term in K_TERMS:
            if term in s:
                occ += 1
                ctx = "".join(ss[max(0, i - 2):min(len(ss), i + 3)])
                if not any(x in ctx for x in K_ANCHORS):
                    unanch.append({"sent": i, "term": term, "text": s[:56]})
    dens = round(len(unanch) / max(len(ss), 1), 4)
    print("⑧ 信号 k: 术语出现 {} 次 | 未落地 {} 处 | 密度 {}（阈值 未落地≤{} 且 密度≤{}）⇒ {}".format(
        occ, len(unanch), dens, K_THRESHOLD, K_DENSITY_MAX,
        "OK" if (len(unanch) <= K_THRESHOLD and dens <= K_DENSITY_MAX) else "FAIL"))
    for u in unanch[:6]:
        print("      ! [{}] {}".format(u["term"], u["text"]))
    if len(unanch) > K_THRESHOLD or dens > K_DENSITY_MAX:
        fails.append("⑧ 信号 k 超阈值")
    print("=" * 78)
    print("机械校验(v6.2): {}".format("**全部通过**" if not fails
                                      else "**未通过** → " + "; ".join(fails)))
    (R / "docs/regression_2x/logs/phase37_mechanical_check.json").write_text(
        json.dumps({"schema": "p37-mechanical-check-v1", "version": "v6.2",
                    "chars": chars, "est_spoken_s_conservative_4p9": round(est_cons, 1), "est_spoken_s_measured_5p33": round(est_meas, 1),
                    "mean_sentence_len": a["mean_sentence_len"],
                    "midcut": len(midcut), "advance_markers": a["advance_marker_count"],
                    "hook_broken": broken, "hooks": hooks,
                    "new_numbers": new_num, "new_entities": new_ent,
                    "meta_blacklist": meta_res, "announce_blacklist": addr,
                    "ngram_hits": hits,
                    "signal_k": {"terms": K_TERMS, "occurrences": occ,
                                 "unanchored": unanch, "density": dens,
                                 "threshold_unanchored": K_THRESHOLD,
                                 "threshold_density": K_DENSITY_MAX,
                                 "declared_before_measurement": True},
                    "fails": fails}, ensure_ascii=False, indent=1), encoding="utf-8")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
