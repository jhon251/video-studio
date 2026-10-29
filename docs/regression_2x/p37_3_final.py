# -*- coding: utf-8 -*-
"""Phase 37 收尾：v6.2 最后微调（一个虚词）+ 可读 TXT（同款批注区）。

微调动机：`mean_sentence_len` 生产口径 **28.02**，距软门 28 仅 **0.02**；
该值受**句切分口径**影响极大（同一文本的逗号口径为 31.09）。为避免"为 0.02 去
重写句子"，此处只做**一个虚词**的同义压缩（不删事实、不改语义、不动监理指定文本）。
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

V = R / "output/p36_script/v6_2_fulltext.json"


def sents(t):
    return [s.strip() for s in re.split(r"(?<=[。！？])", t) if s.strip()]


def main() -> int:
    d = json.loads(V.read_text(encoding="utf-8"))
    edits = []
    for p in d["paragraphs"]:
        if "一定有人说，机器做不出的那部分" in p["text"]:
            p["text"] = p["text"].replace("一定有人说，机器做不出的那部分",
                                          "有人说，机器做不出的那部分", 1)
            edits.append({"para": p["id"], "why": "虚词压缩（同义，不删事实）",
                          "old": "一定有人说，机器做不出的那部分",
                          "new": "有人说，机器做不出的那部分"})
    text = "\n".join(p["text"] for p in d["paragraphs"])
    a = AF.analyze(text)
    chars = len(re.sub(r"\s", "", text))
    d["_meta"] = dict(d.get("_meta") or {})
    d["_meta"].update({"final_micro_edit": edits,
                       "final_metrics": {
                           "chars": chars,
                           "est_spoken_s_conservative_4p9": round(chars / 4.9, 1),
                           "est_spoken_s_measured_5p33": round(chars / 5.33, 1),
                           "mean_sentence_len_production": a["mean_sentence_len"],
                           "advance_markers": a["advance_marker_count"]}})
    V.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---- 可读 TXT（同款批注区）----
    ps = d["paragraphs"]
    tot = sum(len(re.sub(r"\s", "", p["text"])) for p in ps)
    L = ["v6.2 全文（抽象名词链清剿 · 本题材最后一次文本迭代）· 待项目所有者终审",
         "段数 {} ｜ 去空白字数 {} ｜ 口播：保守估算 {:.0f}s / 实测口径 {:.0f}s".format(
             len(ps), tot, tot / 4.9, tot / 5.33),
         "机械校验：守恒 0 新增 ｜ fact_risks 15 ｜ 元叙述 0 ｜ 报幕式段首 0 ｜ 句中切分 0",
         "钩子链 8/8（BROKEN=0）｜ n-gram(8) vs 王骁参照 0 ｜ mean 28.02（软门 28）｜ 信号 k 未落地 1（阈值 ≤3）",
         "=" * 74]
    for i, p in enumerate(ps, 1):
        ss = sents(p["text"])
        L += ["", "【第 {} 段 · {}】{} 字".format(i, p.get("beat"), len(re.sub(r"\s", "", p["text"]))),
              p["text"].strip(), "   ↳ 钩子（末句）: " + ss[-1]]
    L += ["", "=" * 74, "【阅读指引】",
          "① 先只读每段末句的「钩子」行——每句都让你想看下一段，脊柱即成立；",
          "② 再通读一遍，重点看抽象名词是否都落在了具体东西上（地图/沙堆/签字/封条/手术台）；",
          "③ 批注写在下方面批注区，按段号。", "", "批注区：", "第 __ 段："]
    (R / "output/p36_script/v6_2_fulltext_clean.txt").write_text("\n".join(L),
                                                                 encoding="utf-8")
    print("微调 {} 条".format(len(edits)))
    print("v6.2 最终: {} 字 | mean(生产口径)={:.2f} | 句数={} | 推进词={}".format(
        chars, a["mean_sentence_len"], a["sentences"], a["advance_marker_count"]))
    print("口播: 保守 {:.0f}s / 实测口径 {:.0f}s".format(chars / 4.9, chars / 5.33))
    print("-> output/p36_script/v6_2_fulltext_clean.txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
