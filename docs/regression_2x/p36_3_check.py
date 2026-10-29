# -*- coding: utf-8 -*-
"""P36-2 **机械校验全套**（v6，授权书 §2）。

① 数字/实体守恒（⊆ v5.2 ∪ 历史并集）
② fact_risks **15 条**保留
③ 元叙述黑名单 **+ 报幕式段首黑名单** = 0
④ 完整句 + 句中切分 = 0（硬口径）＋ mean_sentence_len ≤27
⑤ n-gram(8) vs 王骁参照 = 0
⑥ 长度 550–700s
⑦ 每段末句必须是**钩子**（问题/反常/未决）；**末段除外**（冷收 + CTA）
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

V = R / "output/p36_script/v6_fulltext.json"
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
HOOK_MARK = ("？", "?", "吗", "呢", "怎么", "为什么", "凭什么", "什么", "会不会",
             "还剩", "还没有", "能不能", "有没有", "吗？")


def sents(t):
    return [s.strip() for s in re.split(r"(?<=[。！？])", t) if s.strip()]


def main() -> int:
    d = json.loads(V.read_text(encoding="utf-8"))
    ps = d["paragraphs"]
    text = "\n".join(p["text"] for p in ps)
    sheet = json.loads(SHEET.read_text(encoding="utf-8"))
    ANN = sheet["announce_blacklist"]
    v52 = json.loads(V52.read_text(encoding="utf-8"))
    t52 = "\n".join(p["text"] for p in v52["paragraphs"])
    t41 = "\n".join(s.get("narration") or "" for s in
                    json.loads(V41.read_text(encoding="utf-8"))["segments"])
    t42 = "\n".join(s.get("narration") or "" for s in
                    json.loads(V42.read_text(encoding="utf-8"))["segments"])
    t3 = json.dumps(json.loads(V3.read_text(encoding="utf-8")), ensure_ascii=False)
    fails = []
    print("=" * 76)
    # ① 数字/实体守恒（v5.2 ∪ 历史并集）
    # **登记一处派生数字**：v6 的「剩下的 1%」是底账「99%」的**补数派生**（100−99），
    # 不引入任何新事实主张，故按**授权书 §2 的并集口径**显式登记为允许来源（而非默默放行）。
    DERIVED_NUMBERS = {"1": "100−99：‘99% 确定’的补数（派生，非新事实）"}
    allow_num = (set(NUM_RE.findall(t52 + t41 + t42 + t3))
                 | set(DERIVED_NUMBERS))
    allow_ent = {e for e in ENTS if e in (t52 + t41 + t42 + t3)}
    new_num = sorted(set(NUM_RE.findall(text)) - allow_num)
    new_ent = sorted({e for e in ENTS if e in text} - allow_ent)
    print("① 数字/实体守恒(v5.2∪历史): 新增数字={} | 新增实体={}".format(
        new_num or "无", new_ent or "无"))
    print("   已登记派生数字: {}".format(json.dumps(DERIVED_NUMBERS, ensure_ascii=False)))
    if new_num or new_ent:
        fails.append("① 新增数字/实体")
    # ②
    fr = json.loads(LED.read_text(encoding="utf-8"))["fact_risks"]
    dfr = d.get("fact_risks") or []
    print("② fact_risks: 底账 {} 条 | v6 {} 条 ⇒ {}".format(
        len(fr), len(dfr), "OK" if len(dfr) >= 15 else "FAIL"))
    if len(dfr) < 15:
        fails.append("② fact_risks < 15")
    # ③ 双黑名单
    meta_res = [b for b in META_BLACK if b in text]
    addr = [{"id": q["id"], "hit": b} for q in ps for b in ANN
            if q["text"].lstrip().startswith(b)]
    print("③ 元叙述残留: {} | 报幕式段首: {}".format(meta_res or "无", addr or "无"))
    if meta_res or addr:
        fails.append("③ 黑名单残留")
    # ④ 口径
    a = AF.analyze(text)
    midcut = [s for s in sents(text)
              if s and not s.startswith(OK_SENT_START)
              and (s[0] in MIDCUT_CHARS or MIDCUT_JIU_RE.match(s))]
    print("④ mean_sentence_len={:.2f}（≤27 ⇒ {}）| 句中切分 {} | 推进词 {}".format(
        a["mean_sentence_len"], "OK" if a["mean_sentence_len"] <= 27 else "超",
        len(midcut), a["advance_marker_count"]))
    for s in midcut[:4]:
        print("      !! {}".format(s[:64]))
    if a["mean_sentence_len"] > 27:
        fails.append("④ mean>27")
    if midcut:
        fails.append("④ 句中切分 {} 处".format(len(midcut)))
    # ⑤ n-gram
    def grams(t, n=8):
        t = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", t)
        return {t[i:i + n] for i in range(max(len(t) - n + 1, 0))}
    g = grams(text)
    hits = {p.name: len(g & grams(p.read_text(encoding="utf-8"))) for p in REFS}
    print("⑤ n-gram(8) vs 王骁参照: {}".format(json.dumps(hits, ensure_ascii=False)))
    if any(hits.values()):
        fails.append("⑤ n-gram 命中")
    # ⑥ 长度
    chars = len(re.sub(r"\s", "", text))
    est = chars / 4.9
    print("⑥ 长度: {} 字 | 预估 {:.0f}s ⇒ {}".format(
        chars, est, "OK" if 550 <= est <= 700 else "超出"))
    if not (550 <= est <= 700):
        fails.append("⑥ 长度超出")
    # ⑦ 钩子：每段末句（末段除外）
    hook_bad = []
    for i, p in enumerate(ps):
        last = sents(p["text"])[-1]
        if i == len(ps) - 1:
            break
        if not any(m in last for m in HOOK_MARK):
            hook_bad.append({"id": p["id"], "last": last[-46:]})
    print("⑦ 非末段末句为钩子: {}/{} ⇒ {}".format(
        len(ps) - 1 - len(hook_bad), len(ps) - 1, "OK" if not hook_bad else "FAIL"))
    for h in hook_bad:
        print("      !! {} {}".format(h["id"], h["last"]))
    if hook_bad:
        fails.append("⑦ 末句非钩子 {} 处".format(len(hook_bad)))
    cta = "比点赞有用"
    print("   末段冷收 + CTA: {} ⇒ {}".format(
        cta, "OK" if ps[-1]["text"].rstrip().endswith("。") and cta in ps[-1]["text"]
        else "FAIL"))
    if cta not in ps[-1]["text"]:
        fails.append("⑦ 末段缺 CTA")
    print("=" * 76)
    print("机械校验(v6): {}".format("**全部通过**" if not fails
                                    else "**未通过** → " + "; ".join(fails)))
    (R / "docs/regression_2x/logs/phase36_mechanical_check.json").write_text(
        json.dumps({"schema": "p36-mechanical-check-v1", "chars": chars,
                    "est_spoken_s": round(est, 1), "paragraphs": len(ps),
                    "mean_sentence_len": a["mean_sentence_len"],
                    "midcut": len(midcut), "advance_markers": a["advance_marker_count"],
                    "new_numbers": new_num, "new_entities": new_ent,
                    "meta_blacklist": meta_res, "announce_blacklist": addr,
                    "ngram_hits": hits, "hook_bad": hook_bad,
                    "fact_risks": {"ledger": len(fr), "in_doc": len(dfr)},
                    "cta_present": cta in ps[-1]["text"], "fails": fails},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
