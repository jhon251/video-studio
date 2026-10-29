# -*- coding: utf-8 -*-
"""P35-1 微修 → **v5.2**（监理裁定）。

① 段 11 尾句微修：收在「每回该由谁点头这件事」，**删除**"接下来该谁点头……看不到终点"
   方向句（消除与段 12「看不到终点」的重复）；
② 口径变更登记：`mean_sentence_len` 目标由 ≤25 改为 **≤27**，并**新增两条硬口径**：
   **完整句**（每句为完整句子）、**无句中切分**（句中切分数 = 0）。

只改表达，不改事实（不新增/删除任何数字、实体）。
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

V51 = R / "output/p35_script/v5_1_fulltext.json"
V52 = R / "output/p35_script/v5_2_fulltext.json"
L = R / "docs/regression_2x/logs"

# 要删除的段 11 尾句（先长后短，兼容不同断句结果）
DROP = [
    "接下来该谁点头、点头要付多大代价，现在只能看到一个方向。看不到终点。",
    "接下来该谁点头、点头要付多大代价，现在只能看到一个方向，看不到终点。",
    "接下来该谁点头，点头要付多大代价，现在只能看到一个方向。看不到终点。",
    "接下来该谁点头，点头要付多大代价，现在只能看到一个方向，看不到终点。",
]


def main() -> int:
    doc = json.loads(V51.read_text(encoding="utf-8"))
    paras = doc["paragraphs"]
    edits = []
    for p in paras:
        if "该由谁点头" not in p["text"] or "接下来该谁点头" not in p["text"]:
            continue
        before = p["text"]
        for d in DROP:
            if d in p["text"]:
                p["text"] = p["text"].replace(d, "").rstrip()
                edits.append({"para": p["id"], "op": "段11 尾句删除", "dropped": d})
                break
        else:
            # 兜底：按句子删除任何含「接下来该谁点头」的句子
            sents = [s for s in re.split(r"(?<=[。！？])", p["text"]) if s]
            kept = [s for s in sents if "接下来该谁点头" not in s]
            if len(kept) != len(sents):
                p["text"] = "".join(kept).rstrip()
                edits.append({"para": p["id"], "op": "段11 尾句删除（按句兜底）",
                              "dropped": [s for s in sents if "接下来该谁点头" in s]})
        if not p["text"].endswith(("。", "！", "？")):
            p["text"] += "。"
        edits[-1]["before_tail"] = before[-40:]
        edits[-1]["after_tail"] = p["text"][-40:]
    out = dict(doc)
    out["paragraphs"] = paras
    out["schema"] = "script-output-v3-p35-v52"
    out["_meta"] = dict(doc.get("_meta") or {})
    out["_meta"].update({
        "version": "v5.2",
        "revision_basis": "Phase 35 监理裁定：段11 尾句微修 + 口径变更（mean ≤27 / 完整句 / 无句中切分）",
        "metric_ruling": {
            "mean_sentence_len_target": 27,
            "rationale": ("≤25 需切断语法或删减内容，两者均不可接受；"
                          "监理裁定接受 26.3 并改口径登记的**机制**为："
                          "以「完整句 + 无句中切分」为硬口径，mean ≤27 为软目标"),
            "hard_rules": ["每句必须是完整句", "句中切分数 = 0"],
            "registered_as": "metric_declaration_change",
        },
    })
    V52.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    t = "\n".join(p["text"] for p in paras)
    chars = len(re.sub(r"\s", "", t))
    a = AF.analyze(t)
    print("v5.2: {} 字 | mean_sent={:.2f} | advance={} | 句数={}".format(
        chars, a["mean_sentence_len"], a["advance_marker_count"], a["sentences"]))
    print("段11 尾部: …{}".format(paras[10]["text"][-46:]))
    print("段12 是否仍含『看不到终点』: {}".format("看不到终点" in paras[11]["text"]))
    print("段11 是否仍含『看不到终点』: {}".format("看不到终点" in paras[10]["text"]))
    print("修订 {} 条".format(len(edits)))

    # 可读 TXT
    txt = ["v5.2 全文（监理尾句微修后 · 待项目所有者终审）",
           "段数 {} ｜ 去空白字数 {} ｜ 预估口播 {:.0f}s".format(len(paras), chars, chars / 4.9),
           "口径（监理裁定）：完整句 + 句中切分=0 + mean_sentence_len ≤27（软）",
           "=" * 72]
    for i, p in enumerate(paras, 1):
        txt += ["", "【第 {} 段】{} 字".format(i, len(re.sub(r"\s", "", p["text"]))),
                p["text"].strip()]
    txt += ["", "=" * 72, "批注区（按段号）：", "第 __ 段："]
    (R / "output/p35_script/v5_2_fulltext_clean.txt").write_text("\n".join(txt),
                                                                 encoding="utf-8")
    (L / "p35_1_v52_edits.json").write_text(json.dumps(
        {"schema": "p35-1-v52-edits-v1", "edits": edits,
         "metric_declaration_change": out["_meta"]["metric_ruling"]},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print("-> output/p35_script/v5_2_fulltext.json / v5_2_fulltext_clean.txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
