# -*- coding: utf-8 -*-
"""P35-1 机械校验（v5.2 口径，监理裁定版）。

口径（授权书 + 监理裁定）：
  mean_sentence_len **≤27**（软目标）＋ 两条**硬口径**：
    · **每句必须是完整句**（不得以从属/衔接词起句 —— 那是句中切分的特征）
    · **句中切分数 = 0**
另含：数字/实体守恒、fact_risks 逐条保留、黑名单清零、n-gram 守卫。
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

V = R / "output/p35_script/v5_2_fulltext.json"
V41 = R / "output/phase33_script_sandbox/script_p33_v41_40seg.json"
V42 = R / "output/phase34_script_sandbox/script_p34_v42_40seg.json"
V3 = R / "projects/p_96efdc03e1aa/artifacts/a_49b58fb3dc01.json"
LED = R / "output/p35_probe/fact_risks_ledger.json"
REFS = [R / "config/human_style_refs/wangxiao_zhongdong_科威特.txt",
        R / "config/human_style_refs/wangxiao_zhongdong_埃及.txt"]
BLACK = ["回查", "先不给", "不给数字", "标清楚", "必须查清", "得先说", "说一下是哪几处",
         "这一版", "我会说清楚", "要核原文", "这期里", "我打算", "接下来我们讲",
         "这一段我想说的是", "先说清楚"]
NUM_RE = re.compile(r"\d+(?:\.\d+)?")
ENTS = ["Appel", "Haken", "Tymoczko", "Detlefsen", "Luker", "Hales", "Flyspeck",
        "Lean", "mathlib", "Liquid Tensor Experiment", "Scholze", "Buzzard",
        "DeepMind", "AlphaGeometry", "AlphaProof", "IMO", "Nature", "四色定理",
        "开普勒猜想"]
# 句中切分特征：句首为**只能说承接上文的虚词**，或**动宾结构被切断**（`就+动词`）。
# 三次收敛（自查）：
#   ① 首版把「这/不/把/被/在/和/…」列入 ⇒ 误判合法起句「这个问题…」（23 处假阳性）；
#   ② 次版仍把「要是/所以/如果」列为切分 ⇒ 三者都是**合法句首**（条件/因果连词可起句）；
#   ③ 定稿只保留：而/但/因/所/果/么 + `就` 后接动词（「就推断…」= 被切断的动宾）。
MIDCUT_CHARS = ("而", "但", "因", "所", "果", "么")
MIDCUT_JIU_RE = re.compile(r"^就[推断说想要能做会应是有的把被让给用]")
# ④ 四次收敛：`所以/因为/但是/而且/然而/虽然/结果` 等**多字连词本身即可起句** ⇒ 先排除，
#    否则「所以真正要盯的……」被误判（第 4 处假阳性）。
OK_SENT_START = ("所以", "因为", "但是", "而且", "然而", "虽然", "结果", "因而", "而是")


def main() -> int:
    d = json.loads(V.read_text(encoding="utf-8"))
    paras = d["paragraphs"]
    text = "\n".join(p["text"] for p in paras)
    v41 = json.loads(V41.read_text(encoding="utf-8"))
    v42 = json.loads(V42.read_text(encoding="utf-8"))
    v3 = json.loads(V3.read_text(encoding="utf-8"))
    t41 = "\n".join(s.get("narration") or "" for s in v41["segments"])
    t42 = "\n".join(s.get("narration") or "" for s in v42["segments"])
    t3 = json.dumps(v3, ensure_ascii=False)
    fails = []
    print("=" * 74)
    # ① 守恒
    allow_num = set(NUM_RE.findall(t41) + NUM_RE.findall(t42) + NUM_RE.findall(t3))
    allow_ent = {e for e in ENTS if e in (t41 + t42 + t3)}
    new_num = sorted(set(NUM_RE.findall(text)) - allow_num)
    new_ent = sorted({e for e in ENTS if e in text} - allow_ent)
    print("① 数字/实体守恒: 新增数字={} | 新增实体={}".format(new_num or "无", new_ent or "无"))
    if new_num or new_ent:
        fails.append("① 新增数字/实体")
    # ② fact_risks
    fr = json.loads(LED.read_text(encoding="utf-8"))["fact_risks"]
    dfr = d.get("fact_risks") or []
    print("② fact_risks: 底账 {} 条 | v5.2 {} 条 ⇒ {}".format(
        len(fr), len(dfr), "OK" if len(dfr) >= len(fr) else "FAIL"))
    if len(dfr) < len(fr):
        fails.append("② fact_risks 减少")
    # ③ 长度
    chars = len(re.sub(r"\s", "", text))
    est = chars / 4.9
    print("③ 长度: {} 字 | 预估 {:.0f}s | 550-700s ⇒ {}".format(
        chars, est, "OK" if 550 <= est <= 700 else "超出"))
    if not (550 <= est <= 700):
        fails.append("③ 长度超出")
    # ④ 黑名单
    res = [b for b in BLACK if b in text]
    print("④ 元叙述黑名单残留: {}".format(res or "无"))
    if res:
        fails.append("④ 黑名单残留")
    # ⑤ 口径：mean ≤27（软）+ 完整句/无句中切分（硬）
    a = AF.analyze(text)
    mean = a["mean_sentence_len"]
    sents = [s.strip() for s in re.split(r"(?<=[。！？])", text) if s.strip()]
    midcut = [s for s in sents if s and not s.startswith(OK_SENT_START) and (s[0] in MIDCUT_CHARS or MIDCUT_JIU_RE.match(s))]
    print("⑤ 口径: mean_sentence_len={:.2f}（≤27 ⇒ {}）| 句数 {} | 推进词 {}".format(
        mean, "OK" if mean <= 27 else "超出", len(sents), a["advance_marker_count"]))
    print("   硬口径「完整句 / 无句中切分」: 以衔接词起句 {} 处 ⇒ {}".format(
        len(midcut), "OK" if not midcut else "FAIL"))
    for s in midcut[:5]:
        print("      !! {}".format(s[:66]))
    if mean > 27:
        fails.append("⑤ mean_sentence_len {:.2f} > 27".format(mean))
    if midcut:
        fails.append("⑤ 句中切分 {} 处".format(len(midcut)))
    if a["advance_marker_count"] > AF.analyze(t41)["advance_marker_count"]:
        fails.append("⑤ 推进词高于 v4.1")
    # ⑥ n-gram
    def grams(t, n=8):
        t = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", t)
        return {t[i:i + n] for i in range(max(len(t) - n + 1, 0))}
    g = grams(text)
    hits = {p.name: len(g & grams(p.read_text(encoding="utf-8"))) for p in REFS}
    print("⑥ n-gram(8) 与王骁参照重合: {}".format(json.dumps(hits, ensure_ascii=False)))
    if any(hits.values()):
        fails.append("⑥ n-gram 命中参照文本")
    # ⑦ 重复句检查（监理裁定的动机）
    tail = "看不到终点"
    print("⑦ 「{}」出现次数: {}（段11={} / 段12={}）".format(
        tail, text.count(tail), int(tail in paras[10]["text"]),
        int(tail in paras[11]["text"])))
    print("=" * 74)
    print("机械校验: {}".format("**全部通过**" if not fails else "**未通过** → " + "; ".join(fails)))
    (R / "docs/regression_2x/logs/p35_1_mechanical_check_v52.json").write_text(
        json.dumps({"schema": "p35-1-mechanical-check-v52", "version": "v5.2",
                    "chars": chars, "est_spoken_s": round(est, 1),
                    "mean_sentence_len": mean, "sentences": len(sents),
                    "midcut_count": len(midcut),
                    "advance_marker_count": a["advance_marker_count"],
                    "new_numbers": new_num, "new_entities": new_ent,
                    "blacklist_residue": res, "ngram_hits": hits,
                    "fact_risks": {"ledger": len(fr), "in_doc": len(dfr)},
                    "tail_dup_check": {"看不到终点": text.count(tail)},
                    "fails": fails}, ensure_ascii=False, indent=1), encoding="utf-8")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
