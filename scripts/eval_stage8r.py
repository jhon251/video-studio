"""V2.1 Stage 8R Final Execution：最终审计证据收集（R1/R2 + 8N 关键回归）。

- 不进入 3.x；不新增 Stage/Agent；不改阈值；不允许负 lifecycle；不改 Truth/Evidence；
- 不接视频/TTS/发布/素材库；非核心边界只登记不修复。
"""
import json
import re
import sys
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
from video_studio.tools.production_constraints import (calibrate, density_band,  # noqa: E402
                                                        STD_BAND_H_PER_MIN, HARD_BUDGET, SOFT_MIDHARD_BUDGET)

stress = json.loads((ROOT / "projects" / "_drafts" / "s8m_stress_claims.json").read_text(encoding="utf-8"))["claims"]
STRESS = {c["id"]: c for c in stress}
col = json.loads((ROOT / "projects" / "_drafts" / "s5_dev_v2_collection.json").read_text(encoding="utf-8"))
base = json.loads((ROOT / "projects" / "_drafts" / "r1_stage8d_full.json").read_text(encoding="utf-8"))
e8 = json.loads((ROOT / "projects" / "_drafts" / "r1_stage8e_full.json").read_text(encoding="utf-8"))
bu = {k for k, v in base["per_id"].items() if v["status"] == "valid"}
evd = {}
for s in col["samples"]:
    evd.setdefault(s["claim_text"], [])
    if s["id"] in bu:
        v = base["per_id"][s["id"]]
        evd[s["claim_text"]].append({"url": v["url"], "title": s["evidence"]["title"], "snippet": s["evidence"]["snippet"], "body": v["body"]})
for c, v in e8["per_claim"].items():
    if v.get("fallback"):
        for e in v["fallback"]["retrieval"]["usable"]:
            evd.setdefault(c, []).append({"url": e["url"], "title": e["title"], "snippet": e["snippet"], "body": e["body"]})


def styled_for(ct, ev):
    b = build_research_brief(ct, ev)
    bp = build_script_blueprint(build_content_plan(b), b)
    return apply_style(build_narrative_draft(bp, b, "bilibili"), b, "casual"), b


def cev(cid):
    if cid.startswith("SC-"):
        return STRESS[cid]["claim_text"], STRESS[cid]["evidence"]
    return cid, evd.get(cid, [])


def assemble(cids, target):
    blocks, gu = [], []
    me, mn, mq, md = set(), set(), set(), set()
    for cid in cids:
        ct, ev = cev(cid)
        st, b = styled_for(ct, ev)
        s = b["structure"]
        me |= set(s.get("entities", [])); mn |= set(s.get("numbers_years", []))
        mq |= set(s.get("qualifiers", [])); md |= set(s.get("domains", []))
        lix = {r["index"]: r["url"] for r in st["references"]}
        for r in st["references"]:
            if r["url"] not in gu: gu.append(r["url"])
        blocks.append((ct, st, lix))
    u2g = {u: i + 1 for i, u in enumerate(gu)}
    paras = []
    for i, (ct, st, lix) in enumerate(blocks):
        if i > 0:
            paras.append({"role": "transition", "beat": "转场", "emotion": "过渡", "intensity": 2, "text": f"进入下一部分：{ct[:26]}…", "claims": [], "evidence_refs": []})
        for p in st["paragraphs"]:
            txt = re.sub(r"\[(\d+)\]", lambda m, _l=lix, _u=u2g: f"[{_u.get(_l.get(int(m.group(1)), ''), '?')}]", p["text"])
            paras.append({**p, "text": txt, "evidence_refs": list(p.get("evidence_refs", []))})
    refs = [{"index": i + 1, "url": u, "title": "", "source_tier": None} for i, u in enumerate(gu)]
    ms = {"claim_text": "长视频", "entities": sorted(me), "numbers_years": sorted(mn), "qualifiers": sorted(mq), "domains": sorted(md), "sub_claims": [], "flags": {}}
    return build_production_plan({"paragraphs": paras, "references": refs}, {"structure": ms, "evidence": [], "gaps": []}, "bilibili", target_seconds=target), ms


V10 = ["SC-TL", "SC-HD", "SC-MP", "2023年，科学家完成了成年果蝇的全脑连接组——十四万个神经元，每条连接都画了出来，发在《科学》上", "死后上传的法律地位是什么"]
V15 = ["SC-MP", "SC-TL", "SC-HD", "SC-MS", "SC-ALL", "2025年，中国团队放出了毫米级的小鼠全脑图谱，这是目前最大的哺乳动物全脑连接组", "人脑大约八百六十亿个神经元，突触按百万亿算", "《黑镜》里有个地方叫圣朱尼佩罗，人死了，意识搬进服务器，永远活在1987年的海滩上"]

print("==== R1 Final Verification：三标准成本 ====")
for name, cids, target, mins in (("VIDEO-10", V10, 600, 10), ("VIDEO-15", V15, 900, 15)):
    plan, ms = assemble(cids, target)
    cal = calibrate(plan, ms)
    print(f"  {name}:")
    for std in ("个人创作者", "小团队", "专业媒体"):
        h = cal["cost"]["per_standard"][std]["hours"]
        lo, hi = STD_BAND_H_PER_MIN[std]
        ok = lo * mins <= h <= hi * mins
        print(f"    {std}: {h:.1f}h vs [{lo*mins:.0f},{hi*mins:.0f}]h -> {'PASS' if ok else 'FAIL'}")

print("==== R2 Final Verification：密度三档 ====")
samples = []
for i, c in enumerate(list(evd.keys())[:5]):
    st, b = styled_for(c, evd.get(c, []))
    samples.append((f"普通-{i+1}", build_production_plan(st, b, "bilibili"), b["structure"]))
for cid in ("SC-HD", "SC-ALL", "SC-TL"):
    ct, ev = cev(cid)
    st, b = styled_for(ct, ev)
    samples.append((f"{'高密度' if cid != 'SC-TL' else '极端'}-{cid}", build_production_plan(st, b, "bilibili"), b["structure"]))
for name, plan, struct in samples:
    cal = calibrate(plan, struct)
    b = cal["balance"]
    band = density_band(len(struct.get("numbers_years", [])))
    ok = band[0] <= b["avg_density"] <= band[1]
    print(f"  {name:14s} 数字{len(struct.get('numbers_years', []))} 实体{len(struct.get('entities', []))} | "
          f"avg密度 {b['avg_density']} 带{band} -> {'PASS' if ok else 'FAIL'}")
# SC-TL 重复伪影证据
ct, ev = cev("SC-TL")
st, b = styled_for(ct, ev)
cal = calibrate(build_production_plan(st, b, "bilibili"), b["structure"])
occ = sum(len(s["subtitle_emphasis"]) for s in cal["scenes"])
uniq = set()
for s in cal["scenes"]:
    uniq.update(s["subtitle_emphasis"])
n_facts = sum(len(s.get("fact_refs", [])) for s in cal["scenes"])
print(f"  SC-TL 证据: emphasis 总出现 {occ} 次 / 唯一元素 {len(uniq)} 个 / fact 引用 {n_facts} 条（6 数字 × 多源）")

print("==== 8N 关键回归（时长/视觉/预算/零漂移） ====")
for name, cids, target, lo, hi in (("VIDEO-10", V10, 600, 540, 660), ("VIDEO-15", V15, 900, 810, 990)):
    plan, ms = assemble(cids, target)
    scenes = plan["scenes"]
    dur_ok = lo <= plan["total_duration_hint"] <= hi
    runs, cur, cur_len = [], None, 0
    for s in scenes:
        v = s["visual_target"]
        if v == cur:
            cur_len += 1
        else:
            if cur_len: runs.append(cur_len)
            cur, cur_len = v, 1
    runs.append(cur_len)
    print(f"  {name}: 时长 {plan['total_duration_hint']}s {'PASS' if dur_ok else 'FAIL'} | "
          f"最大视觉连串 {max(runs)} (≤3 {'PASS' if max(runs)<=3 else 'FAIL'}) | scenes {len(scenes)}")

print("\n[审计证据收集完成；15 套件回归 + SHA256 见独立校验。]")
