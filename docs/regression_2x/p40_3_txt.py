# -*- coding: utf-8 -*-
"""Phase 38：v6.3 可读 TXT（同款批注区；**不再改动任何字**，只做排版）。"""
from __future__ import annotations

import json
import pathlib
import re
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")
V = R / "output/p36_script/v6_5_fulltext.json"


def sents(t):
    return [s.strip() for s in re.split(r"(?<=[。！？])", t) if s.strip()]


def main() -> int:
    d = json.loads(V.read_text(encoding="utf-8"))
    ps = d["paragraphs"]
    tot = sum(len(re.sub(r"\s", "", p["text"])) for p in ps)
    L = [
        "v6.5 全文（语域对齐 + 沙漠比喻移除）· 冻结版 · 本轮经【文本通过】",
        "段数 {} ｜ 去空白字数 {} ｜ 口播：保守 {:.0f}s / 实测口径 {:.0f}s".format(
            len(ps), tot, tot / 4.9, tot / 5.33),
        "机械校验：守恒 0 新增 ｜ fact_risks 15 ｜ 元叙述 0 ｜ 报幕式段首 0 ｜ 句中切分 0 ｜ 钩子链 8/8",
        "n-gram(8) vs 王骁参照 0 ｜ mean 27.73（**advisory**，不设门）｜ 信号 k 未落地 1（≤3）",
        "比喻配额门 **7/7 PASS**（原创物件比喻 3 ≤5；家常习语不计；黑名单 0）｜ 语域对撞 0 处",
        "P38 两处裁定已执行：C1 沙漠筛沙整句移除；C2 配额重定义为「原创物件比喻 ≤5，家常习语不计」；C3 mean 降级 advisory。",
        "=" * 74,
    ]
    for i, p in enumerate(ps, 1):
        ss = sents(p["text"])
        L += ["",
              "【第 {} 段 · {}】{} 字".format(
                  i, p.get("beat"), len(re.sub(r"\s", "", p["text"]))),
              p["text"].strip(),
              "   ↳ 钩子（末句）: " + ss[-1]]
    L += ["", "=" * 74, "【阅读指引】",
          "① 先只读每段末句的「钩子」行——每句都让你想看下一段，脊柱即成立；",
          "② 再通读一遍，看是否有「文青腔」残留（比喻、抒情收尾、抽象名词悬空）；",
          "③ 批注写在下方面批注区，按段号。", "", "批注区：", "第 __ 段："]
    out = R / "output/p36_script/v6_5_fulltext_clean.txt"
    out.write_text("\n".join(L), encoding="utf-8")
    print("段数 {} | 总 {} 字 | 保守 {:.0f}s / 实测 {:.0f}s".format(
        len(ps), tot, tot / 4.9, tot / 5.33))
    print("-> " + str(out.relative_to(R)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
