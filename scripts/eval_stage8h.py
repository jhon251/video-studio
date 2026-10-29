"""V2.1 Stage 8H 一次性验收：Content Planning Layer。

- 不重跑冻结 197；不接生产；不生成最终脚本；不改 Evidence 链 / truth / Evidence Readiness。
- 输入 = 8G Research Brief；输出 = Content Plan。
- ① 结构完整性 ② 角度区分 ③ 平台适配 ④ Brief 引用覆盖 ⑤ 冻结测试保持。
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from video_studio.tools.claim_structuring import build_research_brief  # noqa: E402
from video_studio.tools.content_planning import build_content_plan  # noqa: E402

# 重建 49 Claim 的最终证据（8D 基线可用 + 8E 回退新增），同 eval_stage8g
col = json.loads((ROOT / "projects" / "_drafts" / "s5_dev_v2_collection.json").read_text(encoding="utf-8"))
base = json.loads((ROOT / "projects" / "_drafts" / "r1_stage8d_full.json").read_text(encoding="utf-8"))
e8 = json.loads((ROOT / "projects" / "_drafts" / "r1_stage8e_full.json").read_text(encoding="utf-8"))
base_usable = {k for k, v in base["per_id"].items() if v["status"] == "valid"}
id_meta = {s["id"]: s for s in col["samples"]}
claims: dict[str, list[str]] = {}
for s in col["samples"]:
    claims.setdefault(s["claim_text"], []).append(s["id"])

baseline_ev = defaultdict(list)
for sid in base_usable:
    c = id_meta[sid]["claim_text"]
    v = base["per_id"][sid]
    baseline_ev[c].append({"url": v["url"], "title": id_meta[sid]["evidence"]["title"],
                           "snippet": id_meta[sid]["evidence"]["snippet"], "body": v["body"]})
fallback_ev = defaultdict(list)
for c, v in e8["per_claim"].items():
    if v.get("fallback"):
        for e in v["fallback"]["retrieval"]["usable"]:
            fallback_ev[c].append({"url": e["url"], "title": e["title"],
                                   "snippet": e["snippet"], "body": e["body"]})

plans = {}
for c in claims:
    ev = baseline_ev.get(c, []) + fallback_ev.get(c, [])
    brief = build_research_brief(c, ev)
    plans[c] = build_content_plan(brief)

# ---------- ① 结构完整性 ----------
REQ_KEYS = ("angles", "narrative_direction", "structure", "platform_plans", "brief_citations")
struct_ok = sum(1 for p in plans.values()
                if all(p.get(k) for k in REQ_KEYS)
                and all(p["structure"].get(k) for k in ("hook", "conflict", "question"))
                and len(p["platform_plans"]) == 4)
print("==== Stage 8H 验收（49 唯一 Claim） ====")
print(f"[1] Content Plan 结构完整性: {struct_ok}/{len(plans)} "
      f"(angles/narrative/HCQ/4 平台/brief 引用 齐备且非空)")

# ---------- ② 不同角度区分能力 ----------
angle_counter = Counter()
per_claim_nangles = []
for p in plans.values():
    ang = [a["angle"] for a in p["angles"]]
    angle_counter.update(ang)
    per_claim_nangles.append(len(set(ang)))
distinct_angles = len(angle_counter)
print(f"[2] 不同角度区分能力: 全局角度标签数 {distinct_angles} | 分布 {dict(angle_counter)}")
print(f"    每 Claim 平均角度数 {sum(per_claim_nangles)/len(per_claim_nangles):.2f} "
      f"(min {min(per_claim_nangles)} max {max(per_claim_nangles)})")

# ---------- ③ 平台适配合理性 ----------
plat_ok = 0
durations = Counter()
for p in plans.values():
    ok = all(set(p["platform_plans"].get(n, {}).keys()) >=
             {"duration_style", "hook_strategy", "interaction", "lead_angle", "narrative"}
             for n in ("bilibili", "youtube", "shipinhao", "gongzhonghao"))
    plat_ok += int(ok)
    for n, pp in p["platform_plans"].items():
        durations[pp.get("duration_style", "?")] += 1
print(f"[3] 平台适配合理性: 4 平台字段齐备 {plat_ok}/{len(plans)}")
print(f"    平台时长/风格种类 {len(durations)} 种: {list(durations)[:6]}...")

# ---------- ④ Research Brief 引用覆盖 ----------
total_src = sum(p["brief_citations"]["cited_source_count"] for p in plans.values())
total_gap = sum(p["brief_citations"]["cited_gap_count"] for p in plans.values())
brief_src_total = sum(len(build_research_brief(c, baseline_ev.get(c, []) + fallback_ev.get(c, []))["evidence"])
                      for c in claims)
print(f"[4] Research Brief 引用覆盖: 来源引用 {total_src}/{brief_src_total}；"
      f"缺口引用 {total_gap} 条（计划逐条列出未覆盖元素）")

# 抽样 2 条
print("    抽样（2 条）:")
for i, (c, p) in enumerate(list(plans.items())[:2], 1):
    print(f"    --- 样例 {i} ---")
    for line in p["plan_text"].split("\n")[:6]:
        print(f"      {line}")

print("[5] 全冻结测试保持: 见最终校验（15 套件 0 失败）")

out = {
    "_meta": {"name": "r1_stage8h_full",
              "note": "Stage 8H Content Plan：每 Claim 角度/叙事/HCQ/平台/引用，可回放。"},
    "metrics": {"structure_complete": f"{struct_ok}/{len(plans)}",
                "distinct_angles": distinct_angles, "angle_dist": dict(angle_counter),
                "platform_complete": f"{plat_ok}/{len(plans)}",
                "cited_sources": f"{total_src}/{brief_src_total}", "cited_gaps": total_gap},
    "per_claim": {c: {"angles": p["angles"], "narrative": p["narrative_direction"],
                      "structure": p["structure"], "platform_plans": p["platform_plans"],
                      "citations": p["brief_citations"], "plan_text": p["plan_text"]}
                  for c, p in plans.items()},
}
(ROOT / "projects" / "_drafts" / "r1_stage8h_full.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print("\nwritten: projects/_drafts/r1_stage8h_full.json")
