"""JARVIS Style v2 只读对照测试（A/B）：Truth/Evidence 不变 + 文案表达差异。

- 不修改 2.x 架构/Production Entry；仅验证 style v2 的"表达层"变化。
- A（旧）：output/production_002/final_production_plan.json（style v1 产物）。
- B（新）：用同一 input.json 重新调用 run_production（style v2）。
"""
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from video_studio.production2x import run_production  # noqa: E402
from video_studio.tools.creator_style import style_qa  # noqa: E402

OLD = json.loads((ROOT / "output" / "production_002" / "final_production_plan.json").read_text(encoding="utf-8"))
payload = json.loads((ROOT / "output" / "production_002" / "input.json").read_text(encoding="utf-8"))
NEW = run_production(payload)

print("B 状态:", NEW["status"], "| 版本", NEW["production_version"], NEW["chain_version"])

# ---- Truth / Evidence / Claim 不变核验 ----
old_refs = [r["url"] for r in OLD["references"]]
new_refs = [r["url"] for r in NEW["references"]]
print("引用表不变:", old_refs == new_refs, f"({len(new_refs)} 条)")

old_scenes = OLD["plans"]["bilibili"]["plan"]["scenes"]
new_scenes = NEW["plans"]["bilibili"]["plan"]["scenes"]
print("场景数:", len(old_scenes), "->", len(new_scenes))
print("source_paragraphs 结构一致:",
      [s["source_paragraphs"] for s in old_scenes] == [s["source_paragraphs"] for s in new_scenes])

old_bal = OLD["balance"]["claim_covered"]
new_bal = NEW["balance"]["claim_covered"]
print("claim 覆盖不变:", old_bal == new_bal, old_bal, "->", new_bal)

old_ev = {s["scene_id"]: s["evidence_refs"] for s in old_scenes}
new_ev = {s["scene_id"]: s["evidence_refs"] for s in new_scenes}
print("逐镜 evidence_refs 不变:", old_ev == new_ev)

old_fact = {s["scene_id"]: [f["ref_index"] for f in s.get("fact_refs", [])] for s in old_scenes}
new_fact = {s["scene_id"]: [f["ref_index"] for f in s.get("fact_refs", [])] for s in new_scenes}
print("逐镜 fact_refs 不变:", old_fact == new_fact)

# ---- 文案表达差异 ----
def all_text(scenes):
    return "\n".join(s["script_text"] for s in scenes)

ot, nt = all_text(old_scenes), all_text(new_scenes)
TICS = ("咱们聊聊", "其实啊", "是不是有点意思", "你有没有想过", "你可能没想到",
        "综合现有证据", "进入下一部分", "没想过的答案", "离谱但真实", "值得注意",
        "你敢信", "慢慢讲", "呼应开场", "谨慎作答")
print("\n旧稿模板腔命中:", {t: ot.count(t) for t in TICS if ot.count(t)})
print("新稿模板腔命中:", {t: nt.count(t) for t in TICS if nt.count(t)})

print("\n--- 新旧正文抽样对比（前 3 个 body 镜） ---")
for sid in ("S02", "S07", "S11"):
    os_ = next((s["script_text"] for s in old_scenes if s["scene_id"] == sid), "?")
    ns_ = next((s["script_text"] for s in new_scenes if s["scene_id"] == sid), "?")
    print(f"[{sid}] 旧: {os_[:52]}")
    print(f"[{sid}] 新: {ns_[:52]}")

# ---- style_qa ----
qa_old = style_qa([{"text": s["script_text"]} for s in old_scenes])
qa_new = style_qa([{"text": s["script_text"]} for s in new_scenes])
print("\nstyle_qa 旧稿: score", qa_old["score"], "| 违规", [v["item"] for v in qa_old["violations"]][:8])
print("style_qa 新稿: score", qa_new["score"], "| 违规", [v["item"] for v in qa_new["violations"]][:8])

(ROOT / "output" / "production_002" / "style_v2_ab.json").write_text(
    json.dumps({"refs_unchanged": old_refs == new_refs,
                "fact_refs_unchanged": old_fact == new_fact,
                "evidence_unchanged": old_ev == new_ev,
                "qa_old": qa_old, "qa_new": qa_new,
                "tic_old": {t: ot.count(t) for t in TICS if ot.count(t)},
                "tic_new": {t: nt.count(t) for t in TICS if nt.count(t)}},
               ensure_ascii=False, indent=2), encoding="utf-8")
print("\nwritten: output/production_002/style_v2_ab.json")
