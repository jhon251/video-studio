import json
import sys
sys.stdout.reconfigure(encoding="utf-8")
d = json.load(open("output/production_002/final_production_plan.json", encoding="utf-8"))
sc = d["plans"]["bilibili"]["plan"]["scenes"]
print("总 scene:", len(sc))
for s in sc:
    if s["role"] in ("hook", "transition", "conclusion", "gap", "conclusion_first"):
        print(f"{s['scene_id']} [{s['role']:12s}] {s['script_text'][:50]}")
