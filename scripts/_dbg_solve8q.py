import json
import re
import sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, "src")
ROOT = __import__("pathlib").Path(".").resolve()
sys.path.insert(0, str(ROOT / "src"))
from pathlib import Path
ROOT = Path(".").resolve()
sys.path.insert(0, str(ROOT / "src"))

from video_studio.tools.claim_structuring import build_research_brief
from video_studio.tools.content_planning import build_content_plan
from video_studio.tools.script_planning import build_script_blueprint
from video_studio.tools.narrative_generation import build_narrative_draft
from video_studio.tools.creator_style import apply_style
from video_studio.tools.visual_planning import build_production_plan
from video_studio.tools.production_constraints import calibrate_cost, STD_BAND_H_PER_MIN

stress = json.loads((ROOT / "projects" / "_drafts" / "s8m_stress_claims.json").read_text(encoding="utf-8"))["claims"]
STRESS = {c["id"]: c for c in stress}
col = json.loads((ROOT / "projects" / "_drafts" / "s5_dev_v2_collection.json").read_text(encoding="utf-8"))
base = json.loads((ROOT / "projects" / "_drafts" / "r1_stage8d_full.json").read_text(encoding="utf-8"))
e8 = json.loads((ROOT / "projects" / "_drafts" / "r1_stage8e_full.json").read_text(encoding="utf-8"))
bu = {k for k, v in base["per_id"].items() if v["status"] == "valid"}
im = {s["id"]: s for s in col["samples"]}
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
    return build_production_plan({"paragraphs": paras, "references": refs}, {"structure": ms, "evidence": [], "gaps": []}, "bilibili", target_seconds=target)


V10 = ["SC-TL", "SC-HD", "SC-MP", "2023年，科学家完成了成年果蝇的全脑连接组——十四万个神经元，每条连接都画了出来，发在《科学》上", "死后上传的法律地位是什么"]
V15 = ["SC-MP", "SC-TL", "SC-HD", "SC-MS", "SC-ALL", "2025年，中国团队放出了毫米级的小鼠全脑图谱，这是目前最大的哺乳动物全脑连接组", "人脑大约八百六十亿个神经元，突触按百万亿算", "《黑镜》里有个地方叫圣朱尼佩罗，人死了，意识搬进服务器，永远活在1987年的海滩上"]

for name, cids, target, mins in (("VIDEO-10", V10, 600, 10), ("VIDEO-15", V15, 900, 15)):
    plan = assemble(cids, target)
    cost = calibrate_cost(plan["scenes"])
    cm = cost["content_min"]
    print(f"{name}: content_min={cm}min -> content/分钟 = {cm/mins:.2f}min/分钟")
    for std, (lo, hi) in STD_BAND_H_PER_MIN.items():
        mid = (lo + hi) / 2
        # calibrated = cm/60 × (1+overhead) = mid × mins -> 1+overhead = mid×mins×60/cm
        ov = mid * mins * 60 / cm - 1
        print(f"  [{std}] band [{lo},{hi}] mid={mid} -> 求解 lifecycle_overhead = {ov:.3f}")
