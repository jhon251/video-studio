# -*- coding: utf-8 -*-
"""Phase 38 裁定重发执行：**v6.5 = v6.4 + 段1 一句替换**（LLM $0，纯机械）。

① P38-C1 裁定：沙漠筛沙整句（前半+后半）一次给全 ⇒ 替换后段1 的
   「比喻 + 自评」冲突自动消解（无比喻可自评；「说白了」为跟随式落地，语域规则允许）。
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

V64 = R / "output/p36_script/v6_4_fulltext.json"
V65 = R / "output/p36_script/v6_5_fulltext.json"

OLD = ("他们就把无穷多种情况归约成有限多种构型，像把一整片沙漠筛成几堆沙——"
       "说白了，天底下所有地图，不管多花，都能归进这么几类，剩下那部分交给计算机，"
       "一种一种跑过去。")
NEW = ("他们就把无穷多种情况归约成有限多种构型——说白了，天底下所有地图，"
       "不管多花，都能归进这么几类，剩下那部分交给计算机，一种一种跑过去。")


def main() -> int:
    d = json.loads(V64.read_text(encoding="utf-8"))
    applied, missed = [], []
    for p in d["paragraphs"]:
        if OLD in p["text"]:
            p["text"] = p["text"].replace(OLD, NEW, 1)
            applied.append({"rx": "P38-C1", "para": p["id"],
                            "what": "沙漠筛沙整句替换（前半+后半一次给全）"})
        elif "沙漠" in p["text"]:
            missed.append({"rx": "P38-C1", "para": p["id"], "why": "跨度未命中但含「沙漠」"})
    d["schema"] = "script-output-v4-p38-ruling-v65"
    d["_meta"] = dict(d.get("_meta") or {})
    d["_meta"].update({
        "version": "v6.5",
        "revision_basis": "Phase 38 裁定重发：C1 沙漠筛沙整句替换 + C2 配额重定义 + C3 mean 降级 advisory",
        "prescriptions_applied": applied, "prescriptions_missed": missed,
        "quota_redefinition": {
            "原创物件比喻 ≤5": ["封条", "公共标准件", "橘子摊"],
            "家常习语（不计入配额）": ["请机器挑刺", "割肉级别", "手指头酸"],
            "whitelist_names_kept": 6,
            "note": "错在配额定义，不在白名单；6 名目全保留",
        },
        "mean_sentence_len_status": "advisory（仅报告，不设门）",
        "zero_llm": True,
    })
    V65.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")

    text = "\n".join(p["text"] for p in d["paragraphs"])
    a = AF.analyze(text)
    chars = len(re.sub(r"\s", "", text))
    print("替换 {} 条 | 未命中 {} 条".format(len(applied), len(missed)))
    for x in applied:
        print("  OK  {} {} | {}".format(x["rx"], x["para"], x["what"]))
    for x in missed:
        print("  MISS {} {}".format(x["rx"], x["why"]))
    print()
    print("『沙漠』残留：{}".format(
        [p["id"] for p in d["paragraphs"] if "沙漠" in p["text"]] or "无"))
    print("v6.5: {} 字 | 保守 {:.0f}s / 实测 {:.0f}s | mean={:.2f}(advisory) | 推进词={}".format(
        chars, chars / 4.9, chars / 5.33, a["mean_sentence_len"],
        a["advance_marker_count"]))
    print("-> " + str(V65.relative_to(R)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
