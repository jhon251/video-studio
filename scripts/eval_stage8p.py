"""V2.1 Stage 8P：Production Reality Calibration 一次性验收。

- 不修改 visual_planning.py / Truth / Evidence Layer；不新增 Agent；不接视频/素材库/TTS/发布。
- 校准层：production_constraints.calibrate（成本 2.0 + 平衡 + 素材约束）。
- 验证：8N 回归、8O 失败项重审计、三种成本、冲突报告。
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from video_studio.tools.claim_structuring import build_research_brief  # noqa: E402
from video_studio.tools.content_planning import build_content_plan  # noqa: E402
from video_studio.tools.script_planning import build_script_blueprint  # noqa: E402
from video_studio.tools.narrative_generation import build_narrative_draft  # noqa: E402
from video_studio.tools.creator_style import apply_style  # noqa: E402
from video_studio.tools.visual_planning import build_production_plan  # noqa: E402
from video_studio.tools.production_constraints import calibrate, COST_BY_VISUAL, REF_BAND, STD_FLOOR_H_PER_MIN  # noqa: E402

# ---------- 数据 ----------
stress = json.loads((ROOT / "projects" / "_drafts" / "s8m_stress_claims.json").read_text(encoding="utf-8"))["claims"]
STRESS_BY_ID = {c["id"]: c for c in stress}
col = json.loads((ROOT / "projects" / "_drafts" / "s5_dev_v2_collection.json").read_text(encoding="utf-8"))
base = json.loads((ROOT / "projects" / "_drafts" / "r1_stage8d_full.json").read_text(encoding="utf-8"))
e8 = json.loads((ROOT / "projects" / "_drafts" / "r1_stage8e_full.json").read_text(encoding="utf-8"))
base_usable = {k for k, v in base["per_id"].items() if v["status"] == "valid"}
id_meta = {s["id"]: s for s in col["samples"]}
existing_ev: dict[str, list[dict]] = {}
for s in col["samples"]:
    existing_ev.setdefault(s["claim_text"], [])
    if s["id"] in base_usable:
        v = base["per_id"][s["id"]]
        existing_ev[s["claim_text"]].append({"url": v["url"], "title": s["evidence"]["title"],
                                             "snippet": s["evidence"]["snippet"], "body": v["body"]})
for c, v in e8["per_claim"].items():
    if v.get("fallback"):
        for e in v["fallback"]["retrieval"]["usable"]:
            existing_ev.setdefault(c, []).append({"url": e["url"], "title": e["title"],
                                                  "snippet": e["snippet"], "body": e["body"]})


def styled_for(claim_text, ev):
    brief = build_research_brief(claim_text, ev)
    bp = build_script_blueprint(build_content_plan(brief), brief)
    return apply_style(build_narrative_draft(bp, brief, "bilibili"), brief, "casual"), brief


def claim_evidence(cid):
    if cid.startswith("SC-"):
        c = STRESS_BY_ID[cid]
        return c["claim_text"], c["evidence"], c
    return cid, existing_ev.get(cid, []), None


def assemble_video(claim_ids, target):
    blocks, global_urls = [], []
    me, mn, mq, md = set(), set(), set(), set()
    for cid in claim_ids:
        ct, ev, _ = claim_evidence(cid)
        st, brief = styled_for(ct, ev)
        s = brief["structure"]
        me |= set(s.get("entities", [])); mn |= set(s.get("numbers_years", []))
        mq |= set(s.get("qualifiers", [])); md |= set(s.get("domains", []))
        lix = {r["index"]: r["url"] for r in st["references"]}
        for r in st["references"]:
            if r["url"] not in global_urls:
                global_urls.append(r["url"])
        blocks.append({"claim": ct, "styled": st, "lix": lix})
    u2g = {u: i + 1 for i, u in enumerate(global_urls)}
    paras = []
    for i, b in enumerate(blocks):
        if i > 0:
            paras.append({"role": "transition", "beat": "转场", "emotion": "过渡", "intensity": 2,
                          "text": f"进入下一部分：{b['claim'][:26]}…", "claims": [], "evidence_refs": []})
        for p in b["styled"]["paragraphs"]:
            text = re.sub(r"\[(\d+)\]",
                          lambda m, _l=b["lix"], _ug=u2g: f"[{_ug.get(_l.get(int(m.group(1)), ''), '?')}]",
                          p["text"])
            paras.append({**p, "text": text, "evidence_refs": list(p.get("evidence_refs", []))})
    refs = [{"index": i + 1, "url": u, "title": "", "source_tier": None} for i, u in enumerate(global_urls)]
    merged_struct = {"claim_text": f"长视频（{len(claim_ids)} 条）", "entities": sorted(me),
                     "numbers_years": sorted(mn), "qualifiers": sorted(mq),
                     "domains": sorted(md), "sub_claims": [], "flags": {}}
    plan = build_production_plan({"paragraphs": paras, "references": refs},
                                 {"structure": merged_struct, "evidence": [], "gaps": []},
                                 "bilibili", target_seconds=target)
    return plan, merged_struct


VIDEO_10 = ["SC-TL", "SC-HD", "SC-MP",
            "2023年，科学家完成了成年果蝇的全脑连接组——十四万个神经元，每条连接都画了出来，发在《科学》上",
            "死后上传的法律地位是什么"]
VIDEO_15 = ["SC-MP", "SC-TL", "SC-HD", "SC-MS", "SC-ALL",
            "2025年，中国团队放出了毫米级的小鼠全脑图谱，这是目前最大的哺乳动物全脑连接组",
            "人脑大约八百六十亿个神经元，突触按百万亿算",
            "《黑镜》里有个地方叫圣朱尼佩罗，人死了，意识搬进服务器，永远活在1987年的海滩上"]

samples: list[tuple[str, dict, dict, int]] = []
p10, s10 = assemble_video(VIDEO_10, 600)
samples.append(("VIDEO-10", p10, s10, 10))
p15, s15 = assemble_video(VIDEO_15, 900)
samples.append(("VIDEO-15", p15, s15, 15))
for cid in ("SC-MP", "SC-TL", "SC-HD", "SC-MS", "SC-ALL"):
    ct, ev, _ = claim_evidence(cid)
    st, brief = styled_for(ct, ev)
    samples.append((f"stress-{cid}", build_production_plan(st, brief, "bilibili"),
                    brief["structure"], 0))
for i, c in enumerate(list(existing_ev.keys())[:5]):
    st, brief = styled_for(c, existing_ev.get(c, []))
    samples.append((f"existing-{i+1}", build_production_plan(st, brief, "bilibili"),
                    brief["structure"], 0))

print("==== Stage 8P 验收：Production Reality Calibration ====")
print("---- A. 成本模型 2.0 ----")
for name, plan, struct, mins in samples:
    cal = calibrate(plan, struct)
    scenes = cal["scenes"]
    hits = sum(1 for s in scenes
               if s["visual_target"] in REF_BAND
               and REF_BAND[s["visual_target"]][0] * 0.8 <= s["cost_est"] <= REF_BAND[s["visual_target"]][1] * 1.2)
    hr = hits / len(scenes)
    c = cal["cost"]
    print(f"  {name:16s} 场景 {len(scenes):2d} | variant成本命中率 {hr:.0%}（{hits}/{len(scenes)}，≥90%）| "
          f"content {c['content_min']}min")
    if mins:
        for std in ("个人创作者", "小团队", "专业媒体"):
            h = c["per_standard"][std]["hours"]
            floor = STD_FLOOR_H_PER_MIN[std] * mins
            print(f"      [{std}] 校准 {h}h vs 下限 {floor:.0f}h -> {'PASS' if h >= floor else 'FAIL'}")

print("---- B. 信息-视觉平衡 ----")
for name, plan, struct, mins in samples:
    cal = calibrate(plan, struct)
    b = cal["balance"]
    d_ok = b["data_coverage"] >= 0.6
    e_ok = 1.5 <= b["avg_density"] <= 6
    z_ok = b["zero_density_ratio"] <= 0.15
    print(f"  {name:16s} claim覆盖 {b['claim_covered']} | 数据表达覆盖 {b['data_coverage']:.0%}(≥60% {'PASS' if d_ok else 'FAIL'}) | "
          f"avg密度 {b['avg_density']}(1.5-6 {'PASS' if e_ok else 'FAIL'}) | 空元素 {b['zero_density_ratio']:.0%}(≤15% {'PASS' if z_ok else 'FAIL'})")

print("---- C. 素材可获得性约束 ----")
for name, plan, struct, mins in samples:
    cal = calibrate(plan, struct)
    m = cal["material"]
    hard_ok = m["hard_ratio"] <= 0.15
    mid_ok = m["midhard_ratio"] <= 0.30
    print(f"  {name:16s} difficulty标注 {m['difficulty_annotated']} | 困难 {m['hard_ratio']:.0%}(≤15% {'PASS' if hard_ok else 'FAIL'}) | "
          f"中+困难 {m['midhard_ratio']:.0%}(≤30% {'PASS' if mid_ok else 'FAIL'}) | 证据零漂移 {m['zero_drift']} | fallback {len(m['applied_fallback'])} 处")

print("---- Constraint Conflict Report ----")
for name, plan, struct, mins in samples:
    cal = calibrate(plan, struct)
    if cal["conflicts"]:
        print(f"  {name}:")
        for cf in cal["conflicts"]:
            print(f"    - {cf['type']}" + (f" ({cf.get('count')}处)" if 'count' in cf else "")
                  + (f" data_coverage={cf.get('data_coverage')}" if 'data_coverage' in cf else "")
                  + (f" midhard={cf.get('midhard_ratio')}" if 'midhard_ratio' in cf else ""))
    else:
        print(f"  {name}: 无冲突")

# 8N 回归（校准后结构完整性）
print("---- 8N 回归（校准后） ----")
reg_ok = 0
for name, plan, struct, mins in samples:
    cal = calibrate(plan, struct)
    scenes = cal["scenes"]
    # 覆盖完整性（source_paragraphs 仍保留） + 可执行性
    ok = all("source_paragraphs" in s and s["source_paragraphs"]
             and "visual_target" in s and "subtitle_emphasis" in s and "duration_hint" in s
             for s in scenes)
    reg_ok += int(ok)
print(f"  校准后结构完整（source_paragraphs/visual_target/emphasis/duration_hint）: {reg_ok}/{len(samples)}")

# 落盘
out = {"_meta": {"name": "r1_stage8p_full", "note": "Stage 8P 校准结果，可回放。"},
       "samples": {name: calibrate(plan, struct) for name, plan, struct, _ in samples}}
(ROOT / "projects" / "_drafts" / "r1_stage8p_full.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
print("\nwritten: projects/_drafts/r1_stage8p_full.json")
