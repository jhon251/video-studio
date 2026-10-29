import json
import sys
sys.stdout.reconfigure(encoding="utf-8")
d = json.load(open("output/final_regression/S2-高事实密度.json", encoding="utf-8"))
claim = None
# 找 claim 文本与场景文本差异
for s in d["plans"]["bilibili"]["plan"]["scenes"]:
    print(s["scene_id"], s["role"], "| text:", s["script_text"][:80].replace("\n", " "))
print("---- S3 material ----")
d3 = json.load(open("output/final_regression/S3-多人物多时间线.json", encoding="utf-8"))
m = d3["plans"]["bilibili"]["calibrated"]["material"]
print("material:", m)
for s in d3["plans"]["bilibili"]["plan"]["scenes"]:
    if s.get("difficulty") in ("中", "困难"):
        print(s["scene_id"], s["role"], s["visual_target"], "->", s.get("difficulty"),
              "fallback:", s.get("fallback_applied"))
