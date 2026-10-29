# -*- coding: utf-8 -*-
"""P36-2 修订轮 → v6.1：① 气口断句（mean ≤27、零内容损失、不破语法）；
② 每段末句**收紧为钩子**（以「——」引出未决/反常，或保持问句）；③ 重跑机械校验。

**不新增任何数字/实体**；不动九拍结构与钩子承接第一句。
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

V6 = R / "output/p36_script/v6_fulltext.json"
V61 = R / "output/p36_script/v6_1_fulltext.json"


def split_long(s: str, target: int = 14) -> str:
    """在**既有**逗号处按气口断句（判据同 P35 定稿）。

    `NO_SPLIT_NEXT` 追加 **它/这/那/其**：这些都是**回指上文的代词**，第二版把它们
    断成句首 ⇒ 出现「……是满分级别的说法，它才够得着。／学术毅力故事，它逼出一个…」
    这类**动宾被切**的断裂句。代词起句一律不许断。
    """
    VERB_TAIL = set("了的过出来去着好完错掉啊吧呢吗是有")
    LOC_TAIL = set("里上中下内外后前面边间")
    NO_SPLIT_NEXT = tuple("就而且但因所果如虽当要于另不这同时以及只它其")
    # 放宽一级（**仍保语法**）：`了/是/有` 等本身就是小句收束，在其后可用更低长度阈值断句。
    STRONG_TAIL = set("了是有完错掉")
    out, buf, since = [], "", 0
    for i, ch in enumerate(s):
        if ch in "。！？":
            buf += ch
            out.append(buf)
            buf, since = "", 0
            continue
        if ch == "，":
            body = buf.rstrip()
            nxt = s[i + 1] if i + 1 < len(s) else ""
            base = (len(body) >= 2 and body[-1] in VERB_TAIL
                    and body[-1] not in LOC_TAIL
                    and not (nxt and nxt in NO_SPLIT_NEXT))
            # 三档断句（**均保语法**；只改标点，不动字）：
            #   档1 已达 target，且尾字为谓词收束 ⇒ 断
            #   档2 尾字为强收束（了/是/有/完/错/掉）且 ≥8 字 ⇒ 断
            #   档3 **兜底**（防长尾）：≥20 字且下一字非禁止起句词 ⇒ 断（避免平均被长句拉高）
            if base and (since >= target
                         or (since >= 8 and body[-1] in STRONG_TAIL)
                         or since >= 20):
                out.append(body + "。")
                buf, since = "", 0
                continue
            buf += "，"
            since += 1
            continue
        buf += ch
        since += 1
    if buf:
        out.append(buf)
    return "".join(out)


def tighten_hook(t: str) -> str:
    """把末句收紧为**明确钩子**。

    两版演进（实测）：
      · 首版只要含「——」就判为钩子 ⇒ 生成稿出现「……程序跑完没报错——从头到尾，
        没有一个人类签过字。」这种**陈述性收尾**（有破折号但没提问，钩子力度不足）；
      · 定稿：末句必须含**疑问**线索（？/吗/呢/怎么/为什么/凭什么/什么/会不会/还剩/
        能不能/有没有）**或**明确的未决措辞；否则在最后一个逗号处改为「——」并**补一个
        显式追问**（追问内容取该句已陈述的核心，**不引入新事实**）。
    """
    Q = ("？", "吗", "呢", "怎么", "为什么", "凭什么", "什么", "会不会", "还剩",
         "能不能", "有没有", "往哪儿", "谁")
    if any(m in t for m in Q):
        return t
    core = t.rstrip("。！")
    idx = core.rfind("，")
    head = core[:idx] if idx > 0 else core
    tail = core[idx + 1:] if idx > 0 else ""
    if tail:
        return head + "——" + tail + "，那这一步算什么？"
    return core + "——这算什么？"


def main() -> int:
    d = json.loads(V6.read_text(encoding="utf-8"))
    ps = d["paragraphs"]
    before = AF.analyze("\n".join(p["text"] for p in ps))
    for i, p in enumerate(ps):
        t = p["text"]
        if i < len(ps) - 1:                      # 非末段：末句收紧为钩子
            sents = [s for s in re.split(r"(?<=[。！？])", t) if s]
            if sents:
                sents[-1] = tighten_hook(sents[-1])
                t = "".join(sents)
        p["text"] = split_long(t)
    d["paragraphs"] = ps
    d["schema"] = "script-output-v4-p36-v61"
    d["_meta"] = dict(d.get("_meta") or {})
    d["_meta"].update({"version": "v6.1",
                       "revision": "气口断句 + 末句钩子收紧",
                       "mean_before": before["mean_sentence_len"],
                       "mean_after": AF.analyze(
                           "\n".join(p["text"] for p in ps))["mean_sentence_len"]})
    V61.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    a = AF.analyze("\n".join(p["text"] for p in ps))
    chars = sum(len(re.sub(r"\s", "", p["text"])) for p in ps)
    print("v6  : mean={:.2f} | 句数={}".format(before["mean_sentence_len"],
                                              before["sentences"]))
    print("v6.1: mean={:.2f} | 句数={} | {} 字 | 预估 {:.0f}s".format(
        a["mean_sentence_len"], a["sentences"], chars, chars / 4.9))
    for p in ps:
        s = [x.strip() for x in re.split(r"(?<=[。！？])", p["text"]) if x.strip()]
        print("  {} 末句: {}".format(p["id"], s[-1][-40:]))
    print("-> " + str(V61.relative_to(R)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
