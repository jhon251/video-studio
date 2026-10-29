# -*- coding: utf-8 -*-
"""Phase 38：v6.3 可读 TXT（同款批注区；**不再改动任何字**，只做排版）。"""
from __future__ import annotations

import json
import pathlib
import re
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")
V = R / "output/p36_script/v6_3_fulltext.json"


def sents(t):
    return [s.strip() for s in re.split(r"(?<=[。！？])", t) if s.strip()]


def main() -> int:
    d = json.loads(V.read_text(encoding="utf-8"))
    ps = d["paragraphs"]
    tot = sum(len(re.sub(r"\s", "", p["text"])) for p in ps)
    L = [
        "v6.3 全文（去文青 · 监理逐句处方套用）· 待项目所有者终审",
        "段数 {} ｜ 去空白字数 {} ｜ 口播：保守 {:.0f}s / 实测口径 {:.0f}s".format(
            len(ps), tot, tot / 4.9, tot / 5.33),
        "机械校验：守恒 0 新增 ｜ fact_risks 15 ｜ 元叙述 0 ｜ 报幕式段首 0 ｜ 句中切分 0 ｜ 钩子链 8/8",
        "n-gram(8) vs 王骁参照 0 ｜ mean 28.07（软门 28，超 0.07）｜ 信号 k 未落地 1（≤3）",
        "比喻配额门：**3 FAIL**（M1b 沙漠筛沙残留 / M2 白名单名目 6>5 / M4 非白名单明喻 1）",
        "  → 三项均源于**处方自身**的冲突，详见报告；未擅自改字。",
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
    out = R / "output/p36_script/v6_3_fulltext_clean.txt"
    out.write_text("\n".join(L), encoding="utf-8")
    print("段数 {} | 总 {} 字 | 保守 {:.0f}s / 实测 {:.0f}s".format(
        len(ps), tot, tot / 4.9, tot / 5.33))
    print("-> " + str(out.relative_to(R)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
