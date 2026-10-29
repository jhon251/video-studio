import json
import sys
sys.stdout.reconfigure(encoding="utf-8")
col = json.load(open("projects/_drafts/s5_dev_v2_collection.json", encoding="utf-8"))
seen = []
for s in col["samples"]:
    if s["claim_text"] not in seen:
        seen.append(s["claim_text"])
print("unique claims:", len(seen))
for i, c in enumerate(seen, 1):
    print(f"{i:2d}. {c}")
