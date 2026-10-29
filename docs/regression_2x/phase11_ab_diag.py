# -*- coding: utf-8 -*-
"""Phase 11 只读诊断：回测中 title-check 的逐候选违规码与文本。"""
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")
j = json.loads((R / "docs/regression_2x/logs/phase11_title_ab.json").read_text(encoding="utf-8"))
tc = j["title_check"]
for c in tc["candidates"]:
    print("[{}] {} | {} 字 | tech={}".format(c["index"], c["status"], c["length"],
                                             c["technique"]))
    print("    text:", c["text"][:70])
    for v in c["codes"]:
        print("    违规:", json.dumps(v, ensure_ascii=False)[:160])
print("cover:", [(c["status"], c["text"], [v["code"] for v in c["codes"]])
                 for c in tc["cover_texts"]])
print("counts:", tc["counts"])
