"""V2.1 Stage 8N：Visual Planning Optimization 一次性验收。

- 不改 Truth/Evidence Layer；不新增 Agent；不接视频/素材库/TTS/发布；确定性规则。
- Part 1：Stage 8L 新口径回归（49 唯一 Claim，覆盖完整性/引用零漂移/可执行性）。
- Part 2：Stage 8M stress 重跑（5 stress + VIDEO-10/15 目标时长）+ 8N 全部阈值。
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from video_studio.tools.claim_structuring import build_research_brief  # noqa: E402
from video_studio.tools.content_planning import build_content_plan  # noqa: E402
from video_studio.tools.script_planning import build_script_blueprint  # noqa: E402
from video_studio.tools.narrative_generation import build_narrative_draft  # noqa: E402
from video_studio.tools.creator_style import apply_style  # noqa: E402
from video_studio.tools.visual_planning import (build_production_plan,  # noqa: E402
                                                build_all_platform_plans, _PLATFORM_PACING)

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
    c = s["claim_text"]
    existing_ev.setdefault(c, [])
    if s["id"] in base_usable:
        v = base["per_id"][s["id"]]
        existing_ev[c].append({"url": v["url"], "title": s["evidence"]["title"],
                               "snippet": s["evidence"]["snippet"], "body": v["body"]})
for c, v in e8["per_claim"].items():
    if v.get("fallback"):
        for e in v["fallback"]["retrieval"]["usable"]:
            existing_ev.setdefault(c, []).append({"url": e["url"], "title": e["title"],
                                                  "snippet": e["snippet"], "body": e["body"]})


def styled_for(claim_text, ev):
    brief = build_research_brief(claim_text, ev)
    plan = build_content_plan(brief)
    bp = build_script_blueprint(plan, brief)
    draft = build_narrative_draft(bp, brief, "bilibili")
    return apply_style(draft, brief, "casual"), brief


def check_plan(styled, brief, plan, platform="bilibili"):
    """新口径：覆盖完整性 / 引用零漂移 / 可执行性。"""
    paras = styled["paragraphs"]
    n = len(paras)
    cov = set()
    overlap = False
    ev_scene = set()
    ev_para = set()
    for s in plan["scenes"]:
        sp = set(s["source_paragraphs"])
        if sp & cov:
            overlap = True
        cov |= sp
        ev_scene.update(s["evidence_refs"])
    for p in paras:
        ev_para.update(p.get("evidence_refs", []))
    ref_ok = [r["url"] for r in plan["references"]] == [r["url"] for r in styled["references"]]
    exec_ok = all(bool(s["visual_target"]) and isinstance(s["subtitle_emphasis"], list)
                  and "duration_hint" in s and s["source_paragraphs"] for s in plan["scenes"])
    return {"coverage": cov == set(range(n)) and not overlap,
            "evidence_zero_drift": ev_scene == ev_para and ref_ok,
            "executable": exec_ok}


print("==== Stage 8N 验收 ====")
print("---- Part 1: Stage 8L 新口径回归（49 唯一 Claim × 4 平台） ----")
cov_ok = drift_ok = exec_n = exec_tot = 0
claim_ok = 0
for c in list(existing_ev.keys()):
    styled, brief = styled_for(c, existing_ev.get(c, []))
    plans = build_all_platform_plans(styled, brief)
    claim_good = True
    for p, plan in plans.items():
        chk = check_plan(styled, brief, plan, p)
        cov_ok += int(chk["coverage"])
        drift_ok += int(chk["evidence_zero_drift"])
        exec_n += int(chk["executable"])
        exec_tot += 1
        claim_good = claim_good and all(chk.values())
    claim_ok += int(claim_good)
print(f"1.1 覆盖完整性（每平台）: {cov_ok}/{len(existing_ev)*4}")
print(f"1.2 引用零漂移（每平台）: {drift_ok}/{len(existing_ev)*4}")
print(f"1.3 可执行性（每平台）: {exec_n}/{exec_tot}")
print(f"1.4 三项全过的 Claim: {claim_ok}/{len(existing_ev)}")

print("---- Part 2: Stage 8M stress 重跑（5 stress + VIDEO-10/15 目标时长） ----")
subtitle_expected = {
    "SC-MP": ["1775", "从未"], "SC-TL": ["2013", "2023", "2025", "十四万"],
    "SC-HD": ["139,255", "860亿", "302", "1000"],
    "SC-MS": [], "SC-ALL": ["2013", "2025", "139,255", "860亿", "1000", "百万亿"],
}
subtitle_fail = []
no_isbushi = True
budget_ok = True
run_fail = []
for cid, c in STRESS_BY_ID.items():
    styled, brief = styled_for(c["claim_text"], c["evidence"])
    plans = build_all_platform_plans(styled, brief)
    p = plans["bilibili"]
    chk = check_plan(styled, brief, p)
    if not all(chk.values()):
        print(f"  FAIL {cid}: {chk}")
    all_emph = set()
    maxrun = run = 0
    prev = None
    for s in p["scenes"]:
        all_emph.update(s["subtitle_emphasis"])
        if "不是" in s["subtitle_emphasis"]:
            no_isbushi = False
        v = s["visual_target"]
        run = run + 1 if v == prev else 1
        maxrun = max(maxrun, run)
        prev = v
    miss = [t for t in subtitle_expected[cid] if t not in all_emph]
    if miss:
        subtitle_fail.append((cid, miss))
    if len(p["scenes"]) > 8:
        budget_ok = False
    if maxrun > 3:
        run_fail.append((cid, maxrun))
print(f"2.1 字幕 must-contain 漏标: {subtitle_fail or '无'} | '是不是'误标: {'无' if no_isbushi else '有'}")
print(f"2.2 单 claim 块预算 ≤8: {'PASS' if budget_ok else 'FAIL'} | 最大视觉连串>3: {run_fail or '无'}")

# ---------- 长视频 ----------
VIDEO_10 = ["SC-TL", "SC-HD", "SC-MP",
            "2023年，科学家完成了成年果蝇的全脑连接组——十四万个神经元，每条连接都画了出来，发在《科学》上",
            "死后上传的法律地位是什么"]
VIDEO_15 = ["SC-MP", "SC-TL", "SC-HD", "SC-MS", "SC-ALL",
            "2025年，中国团队放出了毫米级的小鼠全脑图谱，这是目前最大的哺乳动物全脑连接组",
            "人脑大约八百六十亿个神经元，突触按百万亿算",
            "《黑镜》里有个地方叫圣朱尼佩罗，人死了，意识搬进服务器，永远活在1987年的海滩上"]


def claim_evidence(cid):
    if cid.startswith("SC-"):
        c = STRESS_BY_ID[cid]
        return c["claim_text"], c["evidence"]
    return cid, existing_ev.get(cid, [])


def assemble_video(claim_ids):
    blocks = []
    global_urls = []
    merged_ent = set()
    merged_num = set()
    merged_qual = set()
    merged_dom = set()
    for cid in claim_ids:
        claim_text, ev = claim_evidence(cid)
        styled, brief = styled_for(claim_text, ev)
        st = brief["structure"]
        merged_ent |= set(st.get("entities", []))
        merged_num |= set(st.get("numbers_years", []))
        merged_qual |= set(st.get("qualifiers", []))
        merged_dom |= set(st.get("domains", []))
        lix = {r["index"]: r["url"] for r in styled["references"]}
        for r in styled["references"]:
            if r["url"] not in global_urls:
                global_urls.append(r["url"])
        blocks.append({"claim": claim_text, "styled": styled, "lix": lix})
    u2g = {u: i + 1 for i, u in enumerate(global_urls)}
    paragraphs = []
    for i, b in enumerate(blocks):
        if i > 0:
            paragraphs.append({"role": "transition", "beat": "转场", "emotion": "过渡",
                               "intensity": 2, "text": f"进入下一部分：{b['claim'][:26]}…",
                               "claims": [], "evidence_refs": []})
        for p in b["styled"]["paragraphs"]:
            text = p["text"]
            def repl(m, _lix=b["lix"], _ug=u2g):
                k = int(m.group(1))
                u = _lix.get(k, "")
                g = _ug.get(u)
                return f"[{g}]" if g else m.group(0)
            text = re.sub(r"\[(\d+)\]", repl, text)
            paragraphs.append({**p, "text": text, "evidence_refs": list(p.get("evidence_refs", []))})
    refs = [{"index": i + 1, "url": u, "title": next(
        (r["title"] for b in blocks for r in b["styled"]["references"] if r["url"] == u), ""),
        "source_tier": next((r["source_tier"] for b in blocks for r in b["styled"]["references"]
                             if r["url"] == u), None)} for i, u in enumerate(global_urls)]
    merged_struct = {"claim_text": f"长视频（{len(claim_ids)} 条 Claim）",
                     "entities": sorted(merged_ent), "numbers_years": sorted(merged_num),
                     "qualifiers": sorted(merged_qual), "domains": sorted(merged_dom),
                     "sub_claims": [], "flags": {}}
    merged_brief = {"structure": merged_struct, "evidence": [], "gaps": []}
    return {"blocks": len(claim_ids), "styled": {"paragraphs": paragraphs, "references": refs},
            "brief": merged_brief, "url_count": len(global_urls)}


COST_BY_ROLE = {"hook": 5, "transition": 5, "conclusion_first": 6, "body": 30,
                "fact": 10, "gap": 5, "conclusion": 6}
for name, cids, target, lo, hi in (("VIDEO-10", VIDEO_10, 600, 540, 660),
                                   ("VIDEO-15", VIDEO_15, 900, 810, 990)):
    v = assemble_video(cids)
    plan = build_production_plan(v["styled"], v["brief"], "bilibili", target_seconds=target)
    scenes = plan["scenes"]
    chk = check_plan(v["styled"], v["brief"], plan)
    ids = [s["scene_id"] for s in scenes]
    id_ok = ids == [f"S{i:02d}" for i in range(1, len(scenes) + 1)]
    ref_idx = [r["index"] for r in plan["references"]]
    ref_ok = ref_idx == list(range(1, len(ref_idx) + 1))
    emo_viol = 0
    prev = None
    for s in scenes:
        if s["role"] == "transition":
            prev = None
            continue
        if prev is not None and abs(s["intensity"] - prev) > 2:
            emo_viol += 1
        prev = s["intensity"]
    transitions = sum(1 for s in scenes if s["role"] == "transition")
    # 视觉连串
    runs = []
    cur = cur_len = 0
    for s in scenes:
        vv = s["visual_target"]
        if vv == cur:
            cur_len += 1
        else:
            if cur_len:
                runs.append(cur_len)
            cur, cur_len = vv, 1
    runs.append(cur_len)
    maxrun = max(runs)
    frac3 = sum(r for r in runs if r >= 3) / len(scenes)
    # 密度-节奏
    density = [1 + len(s["subtitle_emphasis"]) + len(s["script_text"]) / 50 for s in scenes]
    durs = [float(s["duration_hint"].rstrip("s")) for s in scenes]
    hi_th = sorted(density)[int(len(density) * 0.75)]
    lo_th = sorted(durs)[int(len(durs) * 0.25)]
    mism = sum(1 for i, s in enumerate(scenes) if density[i] >= hi_th and durs[i] <= lo_th)
    cost = sum(COST_BY_ROLE.get(s["role"], 5) for s in scenes)
    total = plan["total_duration_hint"]
    dur_ok = lo <= total <= hi
    print(f"\n{name}: {v['blocks']} claims / {len(v['styled']['paragraphs'])} 段 -> {len(scenes)} scenes | "
          f"B站总时长 {total}s（目标 {lo}-{hi}s）{'PASS' if dur_ok else 'FAIL'}")
    print(f"  覆盖完整性 {chk['coverage']} | 引用零漂移 {chk['evidence_zero_drift']} | 可执行 {chk['executable']}")
    print(f"  Scene 一致性: id={id_ok} 全局编号={ref_ok} 情绪跳变={emo_viol} transition={transitions}/{v['blocks']-1}")
    print(f"  视觉重复: 最大连串 {maxrun}（≤3）| 连串≥3 占比 {frac3:.1%}（≤20%）")
    print(f"  密度-节奏失配: {mism}/{len(scenes)}（≤10%: {mism/len(scenes):.1%}）")
    print(f"  成本估算: {cost} 分钟 ≈ {cost/60:.1f} 小时（每千秒 {cost*60/(total or 1):.0f} 分钟）")

# ---------- 落盘 ----------
out = {
    "_meta": {"name": "r1_stage8n_full",
              "note": "Stage 8N 优化验收：8L 新口径回归 + stress/长视频阈值，可回放。"},
    "part1": {"coverage_ok": f"{cov_ok}/{len(existing_ev)*4}",
              "drift_ok": f"{drift_ok}/{len(existing_ev)*4}",
              "executable": f"{exec_n}/{exec_tot}", "claims_all_ok": f"{claim_ok}/{len(existing_ev)}"},
    "part2": {"subtitle_misses": subtitle_fail, "no_isbushi": no_isbushi,
              "budget_ok": budget_ok, "run_fail": run_fail},
}
(ROOT / "projects" / "_drafts" / "r1_stage8n_full.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
print("\nwritten: projects/_drafts/r1_stage8n_full.json")
