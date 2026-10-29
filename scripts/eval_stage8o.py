"""V2.1 Stage 8O：Production Plan Reality Audit（一次性静态审计）。

- 不修改任何代码 / Visual Planning Layer；不新增 Agent；不接视频/素材库/TTS/发布。
- 仅调用既有函数生成 Production Plan（输入数据），再对照 STAGE_8O_DESIGN.md 的
  现实参照基准（文档化 rubric）做静态核对；只报告，不修复。
- 额外区分：个人创作者 / 小团队 / 专业媒体 三种生产标准。
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
from video_studio.tools.script_planning import build_script_blueprint  # noqa: E402
from video_studio.tools.narrative_generation import build_narrative_draft  # noqa: E402
from video_studio.tools.creator_style import apply_style  # noqa: E402
from video_studio.tools.visual_planning import build_production_plan  # noqa: E402

# ---------- 现实参照基准（STAGE_8O_DESIGN.md §2，文档化 rubric） ----------
REF_COST = {  # visual_target -> (low, high) 分钟/场景
    "口播 + 大字标题卡": (5, 10), "口播 + 全屏数字卡": (5, 10),
    "快切素材 + 大字标题卡": (15, 30),
    "结论大字卡": (5, 8), "结论大字卡 + 落版": (5, 8),
    "结论口播 + 关键数字卡": (8, 15), "结论口播 + 呼应画面": (10, 20),
    "事实核查字幕卡": (10, 15), "来源截图 + 引注": (10, 15), "核查清单卡": (10, 15),
    "待补提示卡（黄底警示）": (3, 5), "转场字幕卡": (3, 5),
    "数据可视化 + 证据截图": (30, 60), "概念动画 + 口播": (60, 120),
    "实拍素材 + 数据角标": (20, 40),
}
OBTAIN = {  # visual_target -> 可获得性
    "口播 + 大字标题卡": "高", "口播 + 全屏数字卡": "高", "快切素材 + 大字标题卡": "困难",
    "结论大字卡": "高", "结论大字卡 + 落版": "高",
    "结论口播 + 关键数字卡": "高", "结论口播 + 呼应画面": "中",
    "事实核查字幕卡": "高", "来源截图 + 引注": "高", "核查清单卡": "高",
    "待补提示卡（黄底警示）": "高", "转场字幕卡": "高",
    "数据可视化 + 证据截图": "中", "概念动画 + 口播": "中", "实拍素材 + 数据角标": "困难",
}
COST8N = {"hook": 5, "transition": 5, "conclusion_first": 6, "body": 30,
          "fact": 10, "gap": 5, "conclusion": 6}  # 8N 角色级成本（分钟）
STD_FLOOR = {  # 三种生产标准：h/成品分钟 -> (low, high) 下限
    "个人创作者": (2.5, 4.0),
    "小团队": (1.5, 2.5),
    "专业媒体": (1.0, 1.5),
}

# ---------- 生成审计输入（调用既有函数，静态） ----------
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
        existing_ev[c := s["claim_text"]].append({"url": v["url"], "title": s["evidence"]["title"],
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
        return c["claim_text"], c["evidence"]
    return cid, existing_ev.get(cid, [])


def assemble_video(claim_ids, target):
    import re
    blocks, global_urls = [], []
    me, mn, mq, md = set(), set(), set(), set()
    for cid in claim_ids:
        ct, ev = claim_evidence(cid)
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
    merged = {"structure": {"claim_text": f"长视频（{len(claim_ids)} 条）", "entities": sorted(me),
                            "numbers_years": sorted(mn), "qualifiers": sorted(mq),
                            "domains": sorted(md), "sub_claims": [], "flags": {}},
              "evidence": [], "gaps": []}
    return build_production_plan({"paragraphs": paras, "references": refs}, merged, "bilibili",
                                 target_seconds=target), paras


VIDEO_10 = ["SC-TL", "SC-HD", "SC-MP",
            "2023年，科学家完成了成年果蝇的全脑连接组——十四万个神经元，每条连接都画了出来，发在《科学》上",
            "死后上传的法律地位是什么"]
VIDEO_15 = ["SC-MP", "SC-TL", "SC-HD", "SC-MS", "SC-ALL",
            "2025年，中国团队放出了毫米级的小鼠全脑图谱，这是目前最大的哺乳动物全脑连接组",
            "人脑大约八百六十亿个神经元，突触按百万亿算",
            "《黑镜》里有个地方叫圣朱尼佩罗，人死了，意识搬进服务器，永远活在1987年的海滩上"]

samples: list[tuple[str, dict]] = []
samples.append(("VIDEO-10", assemble_video(VIDEO_10, 600)[0]))
samples.append(("VIDEO-15", assemble_video(VIDEO_15, 900)[0]))
for cid in ("SC-MP", "SC-TL", "SC-HD", "SC-MS", "SC-ALL"):
    ct, ev = claim_evidence(cid)
    st, brief = styled_for(ct, ev)
    samples.append((f"stress-{cid}", build_production_plan(st, brief, "bilibili")))
for i, c in enumerate(list(existing_ev.keys())[:5]):
    st, brief = styled_for(c, existing_ev.get(c, []))
    samples.append((f"existing-{i+1}", build_production_plan(st, brief, "bilibili")))


def audit(plan: dict) -> dict:
    scenes = plan["scenes"]
    cost8n = sum(COST8N.get(s["role"], 5) for s in scenes)
    hits = 0
    in_band_low = in_band_high = 0
    per_type = Counter()
    obtain = Counter()
    out_of_band = []
    for s in scenes:
        vt = s["visual_target"]
        per_type[vt] += 1
        obtain[OBTAIN.get(vt, "高")] += 1
        lo, hi = REF_COST.get(vt, (5, 10))
        c = COST8N.get(s["role"], 5)
        in_band_low += lo
        in_band_high += hi
        if lo <= c <= hi:
            hits += 1
        else:
            out_of_band.append((s["scene_id"], vt, c, (lo, hi)))
    n = len(scenes)
    ratio = {
        "纯口播/字幕卡": sum(v for t, v in per_type.items() if t.startswith("口播") or "字幕卡" in t),
        "数据可视化+证据截图": sum(v for t, v in per_type.items() if "数据可视化" in t),
        "动画": sum(v for t, v in per_type.items() if "概念动画" in t),
        "B-roll/实拍/快切": sum(v for t, v in per_type.items() if "实拍" in t or "快切" in t),
    }
    return {"n": n, "cost8n": cost8n, "hit_rate": hits / n, "hits": hits,
            "band_low": in_band_low, "band_high": in_band_high,
            "ratio": ratio, "obtain": dict(obtain), "per_type": dict(per_type),
            "out_of_band": out_of_band}


print("==== Stage 8O：Production Plan Reality Audit ====")
print("---- ① 成本估算现实性 ----")
all_hit = []
for name, plan in samples:
    a = audit(plan)
    all_hit.append((name, a["hit_rate"]))
    print(f"  {name:16s} 场景 {a['n']:2d} | 8N成本 {a['cost8n']:3d}min | 命中率 {a['hit_rate']:.0%} "
          f"({a['hits']}/{a['n']}) | 参考带 [Σ{a['band_low']}, Σ{a['band_high']}]min | "
          f"带内整片 {'PASS' if a['band_low'] <= a['cost8n'] <= a['band_high'] else 'FAIL'}")
    for sid, vt, c, (lo, hi) in a["out_of_band"][:4]:
        print(f"      out-of-band: {sid} {vt} 8N={c}min vs 参考[{lo},{hi}]min")

print("---- ② Scene 类型分布 ----")
for name, plan in samples:
    a = audit(plan)
    r = a["ratio"]
    print(f"  {name:16s} 类型分布 {a['per_type']}")

print("---- ③ 素材可获得性 ----")
for name, plan in samples:
    a = audit(plan)
    o = a["obtain"]
    hard = o.get("困难", 0) + o.get("中", 0)
    print(f"  {name:16s} 高 {o.get('高',0)} / 中 {o.get('中',0)} / 困难 {o.get('困难',0)} | "
          f"中+困难占比 {hard/a['n']:.0%}（阈值 ≤30%）")

print("---- ④ 技术构成比例 ----")
for name, plan in samples:
    a = audit(plan)
    r = a["ratio"]
    n = a["n"]
    def pct(k): return r.get(k, 0) / n
    print(f"  {name:16s} 纯口播/字幕卡 {pct('纯口播/字幕卡'):.0%}(≤40%) | "
          f"数据可视化+证据 {pct('数据可视化+证据截图'):.0%}(≥25%) | "
          f"动画 {pct('动画'):.0%}(≤30%) | B-roll {pct('B-roll/实拍/快切'):.0%}(≤25%)")

print("---- ⑤ 10-15 分钟可行性（三种生产标准） ----")
for name, plan in samples:
    if not name.startswith("VIDEO"):
        continue
    a = audit(plan)
    h = a["cost8n"] / 60
    mins = 10 if name == "VIDEO-10" else 15
    print(f"  {name}: 8N 估算 {h:.1f}h（{mins} 分钟级成品）")
    for std, (lo, hi) in STD_FLOOR.items():
        floor_lo = lo * mins
        print(f"    [{std}] 下限 {floor_lo:.0f}h -> 缺口 {floor_lo/h:.1f}×")

print("\n[审计为静态核对，仅报告；未修改任何代码/层；未接视频/素材库/TTS/发布。]")

# 落盘审计明细
detail = {name: audit(plan) for name, plan in samples}
(ROOT / "projects" / "_drafts" / "r1_stage8o_full.json").write_text(
    json.dumps(detail, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
print("\nwritten: projects/_drafts/r1_stage8o_full.json")
