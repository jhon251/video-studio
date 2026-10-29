# -*- coding: utf-8 -*-
"""Phase 38：**v6.3 = 监理逐句处方套用**（纯机械替换，无生成、LLM $0）。

八个处方跨度（第 4 条含两处：正文替换 + 段7 去重）。**每条只做字面替换**，
不做任何自由发挥；未命中的跨度**如实报告**（不猜测改写）。
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

V62 = R / "output/p36_script/v6_2_fulltext.json"
V63 = R / "output/p36_script/v6_3_fulltext.json"
L = R / "docs" / "regression_2x" / "logs"

# ---- 处方（按监理 §0，逐条字面）----
RX = [
    ("1", "P01",
     "——天底下所有地图，都能塞进这么几类花样",
     "——说白了，天底下所有地图，不管多花，都能归进这么几类"),
    ("1b", "P01",
     "像把一整片沙漠筛成几堆沙",
     "像把一整片沙漠筛成几堆沙"),          # 保留在句内（黑名单词条「沙漠筛沙」另论）
    ("2", "P01",
     "一百二十多年悬在那儿，几代数学家从年轻干到退休，它还在墙上挂着。",
     "一百二十多年没人搞定，几代数学家从年轻干到退休。"),
    ("3", "P03",
     "你写一步，我看一步，看完了点头，这条链子才算合拢。",
     "你写一步，我看一步，看完了点头，这才算数。"),
    ("4", "P06",
     "翻的过程会不断碰到同一件事，人写证明时省下的字，全堆在机器这一关等着还。",
     "翻的过程会不断碰到同一件事：人写证明时一句「显然」带过去的地方，"
     "到机器这儿都得一步一步摊开算清楚。"),
    ("4b", "P07",          # 与段7 去重：只留「那句『显然』背后，可能藏着一整页纸」
     "翻译的过程会暴露一件事：人写的证明里，有多少步是靠一句「显然」跳过去的；那句「显然」背后，可能藏着一整页纸。",
     "翻译的过程会暴露一件事：那句「显然」背后，可能藏着一整页纸。"),
    ("5", "P08", "自己写证明这件事，2024 年来了两个样本。",
     "自己写证明这件事，2024 年来了两件。"),
    ("6", "P09", "我们能看到的只是一个方向，看不到终点。",
     "后面会走到哪儿，现在谁也说不准。"),
]


def main() -> int:
    d = json.loads(V62.read_text(encoding="utf-8"))
    ps = {p["id"]: p for p in d["paragraphs"]}
    applied, missed = [], []
    for tag, pid, old, new in RX:
        t = ps[pid]["text"]
        if old in t:
            if old != new:
                ps[pid]["text"] = t.replace(old, new, 1)
            applied.append({"rx": tag, "para": pid, "old": old[:46], "new": new[:46],
                            "changed": old != new})
        else:
            missed.append({"rx": tag, "para": pid, "old": old[:60]})
    d["schema"] = "script-output-v4-p38-v63"
    d["_meta"] = dict(d.get("_meta") or {})
    d["_meta"].update({
        "version": "v6.3",
        "revision_basis": "Phase 38 授权书：监理逐句处方套用（纯机械替换）+ 比喻配额门",
        "prescriptions_applied": applied, "prescriptions_missed": missed,
        "zero_llm": True,
        "metaphor_whitelist": ["封条（段9，论点承重）", "公共标准件（段7）",
                               "请机器挑刺（段7）", "水果摊橘子（段5）",
                               "割肉级别（段3）", "手指头酸（段1，虚拟语气）"],
    })
    V63.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")

    text = "\n".join(p["text"] for p in d["paragraphs"])
    a = AF.analyze(text)
    chars = len(re.sub(r"\s", "", text))
    print("处方套用 {} 条 | **未命中 {} 条**".format(len(applied), len(missed)))
    for x in applied:
        print("  OK  {} {} changed={} | {}".format(
            x["rx"], x["para"], x["changed"], x["old"][:44]))
    for x in missed:
        print("  MISS {} {} | {}".format(x["rx"], x["para"], x["old"][:66]))
    print()
    print("v6.3: {} 字 | 保守 {:.0f}s / 实测口径 {:.0f}s | mean={:.2f} | 推进词={}".format(
        chars, chars / 4.9, chars / 5.33, a["mean_sentence_len"],
        a["advance_marker_count"]))
    print("-> " + str(V63.relative_to(R)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
