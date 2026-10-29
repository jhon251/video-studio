import json
import sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, "src")
from video_studio.tools.evidence_readiness import _direction

d = json.load(open("projects/_drafts/r1_stage8f_full.json", encoding="utf-8"))
contra = [r for r in d["per_claim"] if r["balance"]["contradiction_present"]]
print("negation-contradiction claims:", len(contra))
# 需要原始证据来 spot-check 方向；重建证据
col = json.load(open("projects/_drafts/s5_dev_v2_collection.json", encoding="utf-8"))
e8 = json.load(open("projects/_drafts/r1_stage8e_full.json", encoding="utf-8"))
base = json.load(open("projects/_drafts/r1_stage8d_full.json", encoding="utf-8"))
base_usable = {k for k, v in base["per_id"].items() if v["status"] == "valid"}
id_meta = {s["id"]: s for s in col["samples"]}
from collections import defaultdict
claims = defaultdict(list)
for s in col["samples"]:
    claims[s["claim_text"]].append(s["id"])

shown = 0
for r in contra:
    if shown >= 6:
        break
    c = r["claim"]
    shown += 1
    print("---", c[:26], "| dirs:", {k: r["balance"][k] for k in ("supporting", "contradicting", "context")})
    for sid in claims[c]:
        if sid in base_usable:
            body = base["per_id"][sid]["body"]
            d_ = _direction(c, {"url": "", "title": "", "snippet": "", "body": body})
            if d_[0] == "contradicting":
                print("    [baseline]", body[:70].replace("\n", " "))
    if c in e8["per_claim"] and e8["per_claim"][c].get("fallback"):
        for e in e8["per_claim"][c]["fallback"]["retrieval"]["usable"]:
            d_ = _direction(c, e)
            if d_[0] == "contradicting":
                print("    [fallback]", e["body"][:70].replace("\n", " "))
