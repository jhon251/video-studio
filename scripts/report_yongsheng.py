import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
p = Path(r"C:\mp4agent\video-studio\projects\_drafts\yongsheng-check_核查报告.json")
d = json.loads(p.read_text(encoding="utf-8"))

print("=== NEEDS_HUMAN 清单（风险|类型|表述）===")
for c in d["needs_human"]:
    print(f"{c['id']} [{c['risk']}/{c['type']}] {c['text'][:60]}")

print()
print("=== Skeptic 攻击明细 ===")
for a in d["skeptic_attacks"]:
    print(f"[{a['category']}/{a['severity']}] {a.get('claim_ids')} :: "
          f"{a['claim'][:40]} | {a['challenge'][:66]}")

print()
print("=== fact_check 逻辑跳跃/矛盾类 reasoning 摘录 ===")
seen = set()
for r in d["factcheck"]:
    if ("逻辑跳跃" in r["reasoning"] or "矛盾" in r["reasoning"]) and r["claim_id"] not in seen:
        seen.add(r["claim_id"])
        print(f"{r['claim_id']} [{r['conclusion']}] {r['reasoning'][:100]}")

print()
print("=== CRITICAL/HIGH claim 的核查结论 ===")
by_id = {r["claim_id"]: r for r in d["factcheck"]}
for c in d["needs_human"]:
    if c["risk"] in ("CRITICAL", "HIGH"):
        r = by_id.get(c["id"], {})
        print(f"{c['id']} [{c['risk']}] {c['text'][:44]} -> {r.get('conclusion')} | {r.get('reasoning', '')[:70]}")
