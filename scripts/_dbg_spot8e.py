import json
import sys
sys.stdout.reconfigure(encoding="utf-8")
d = json.load(open("projects/_drafts/r1_stage8e_full.json", encoding="utf-8"))
recovered = [c for c, v in d["per_claim"].items()
             if v.get("fallback") and v["fallback"]["retrieval"]["usable"]]
print("recovered claims:", len(recovered), "of", len(d["per_claim"]))
shown = 0
for c, v in d["per_claim"].items():
    if not (v.get("fallback") and v["fallback"]["retrieval"]["usable"]):
        continue
    if shown >= 8:
        break
    shown += 1
    print("---", c[:30])
    for e in v["fallback"]["retrieval"]["usable"][:2]:
        body = e["body"].replace("\n", " ").replace("\r", " ")[:50]
        print("   ", e["url"][:66], "|", e["status"], "|", e["source_quality"]["tier"], "|", body)
