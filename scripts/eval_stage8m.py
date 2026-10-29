"""V2.1 Stage 8M：Visual Planning Layer Stress Test（一次性执行，只报告不修复）。

- 严格按 docs/STAGE_8M_DESIGN.md；不改任何生产代码 / visual_planning.py / Truth / Evidence Layer；
  不新增 Agent；不自动生成视频/剪辑/TTS/发布。
- 压力数据：s8m_stress_claims.json（5 类复杂度 × 6 条构造 evidence）。
- 长视频：VIDEO-10（5 claims，目标 540-660s）/ VIDEO-15（8 claims，目标 810-990s），
  test-side 全局引用重编号 + transition 拼接，喂给未修改的 8L planner。
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

# ---------- 加载压力数据 ----------
stress = json.loads((ROOT / "projects" / "_drafts" / "s8m_stress_claims.json").read_text(encoding="utf-8"))["claims"]
STRESS_BY_ID = {c["id"]: c for c in stress}

# 既有 claim 证据（8D 基线可用 + 8E 回退新增），复用回放数据
col = json.loads((ROOT / "projects" / "_drafts" / "s5_dev_v2_collection.json").read_text(encoding="utf-8"))
base = json.loads((ROOT / "projects" / "_drafts" / "r1_stage8d_full.json").read_text(encoding="utf-8"))
e8 = json.loads((ROOT / "projects" / "_drafts" / "r1_stage8e_full.json").read_text(encoding="utf-8"))
base_usable = {k for k, v in base["per_id"].items() if v["status"] == "valid"}
id_meta = {s["id"]: s for s in col["samples"]}
existing_ev: dict[str, list[dict]] = {}
for s in col["samples"]:
    c = s["claim_text"]
    if c not in existing_ev:
        existing_ev[c] = []
    if s["id"] in base_usable:
        v = base["per_id"][s["id"]]
        existing_ev[c].append({"url": v["url"], "title": s["evidence"]["title"],
                               "snippet": s["evidence"]["snippet"], "body": v["body"]})
for c, v in e8["per_claim"].items():
    if v.get("fallback"):
        for e in v["fallback"]["retrieval"]["usable"]:
            existing_ev.setdefault(c, []).append({"url": e["url"], "title": e["title"],
                                                  "snippet": e["snippet"], "body": e["body"]})


def claim_evidence(cid: str) -> tuple[str, list[dict]]:
    if cid.startswith("SC-"):
        c = STRESS_BY_ID[cid]
        return c["claim_text"], c["evidence"]
    return cid, existing_ev.get(cid, [])


def styled_for(claim_text: str, ev: list[dict]) -> tuple[dict, dict]:
    brief = build_research_brief(claim_text, ev)
    plan = build_content_plan(brief)
    bp = build_script_blueprint(plan, brief)
    draft = build_narrative_draft(bp, brief, "bilibili")
    styled = apply_style(draft, brief, "casual")
    return styled, brief


# ---------- ① 5 条 stress claims 逐条过 8G→8L ----------
stress_results = {}
subtitle_expected = {
    "SC-MP": ["1775", "从未"], "SC-TL": ["2013", "2023", "2025", "十四万"],
    "SC-HD": ["139,255", "860亿", "302", "1000"],
    "SC-MS": [], "SC-ALL": ["2013", "2025", "139,255", "860亿", "1000", "百万亿"],
}
subtitle_misses = {}
no_isbushi = True
for cid, c in STRESS_BY_ID.items():
    styled, brief = styled_for(c["claim_text"], c["evidence"])
    plans = build_all_platform_plans(styled, brief)
    p = plans["bilibili"]
    stress_results[cid] = {"styled": styled, "brief": brief, "plans": plans}
    # 字幕重点 must-contain 检查（B站 plan 全部 scene 的 emphasis 并集）
    all_emph = set()
    for s in p["scenes"]:
        all_emph.update(s["subtitle_emphasis"])
        if "不是" in s["subtitle_emphasis"]:
            no_isbushi = False
    miss = [t for t in subtitle_expected[cid] if t not in all_emph]
    subtitle_misses[cid] = miss

print("==== Stage 8M 验收 ====")
print("---- A. Stage 8L 五项（5 条 stress claims 逐条 + 两部长视频） ----")

# stress claims 的 8L 指标
map_ok = sum(1 for r in stress_results.values()
             if len(r["plans"]["bilibili"]["scenes"]) == len(r["styled"]["paragraphs"]))
print(f"A1. Script-Scene 映射完整性（stress 5）: {map_ok}/5")
ev_ok = 0
for r in stress_results.values():
    p = r["plans"]["bilibili"]
    par_refs = sum(1 for x in r["styled"]["paragraphs"] if x.get("evidence_refs"))
    scene_refs = sum(1 for s in p["scenes"] if s["evidence_refs"])
    ev_ok += int(scene_refs == par_refs and len(p["references"]) == len(r["styled"]["references"]))
print(f"A2. Evidence-Visual 引用保持（stress 5）: {ev_ok}/5")
exec_ok = exec_total = 0
for r in stress_results.values():
    for pp in r["plans"].values():
        for s in pp["scenes"]:
            exec_total += 1
            exec_ok += int(bool(s["visual_target"]) and isinstance(s["subtitle_emphasis"], list)
                           and "duration_hint" in s)
print(f"A3. Production Plan 可执行性（stress 5×4 平台）: {exec_ok}/{exec_total}")
print(f"A4. 字幕重点标注准确性（stress 5，must-contain）:")
for cid in STRESS_BY_ID:
    print(f"    {cid}: 漏标 {subtitle_misses[cid] or '无'}")
print(f"    '是不是'反问误标为否定: {'无' if no_isbushi else '有（FAIL）'}")

# ---------- ② 两部长视频组装 ----------
VIDEO_10 = ["SC-TL", "SC-HD", "SC-MP",
            "2023年，科学家完成了成年果蝇的全脑连接组——十四万个神经元，每条连接都画了出来，发在《科学》上",
            "死后上传的法律地位是什么"]
VIDEO_15 = ["SC-MP", "SC-TL", "SC-HD", "SC-MS", "SC-ALL",
            "2025年，中国团队放出了毫米级的小鼠全脑图谱，这是目前最大的哺乳动物全脑连接组",
            "人脑大约八百六十亿个神经元，突触按百万亿算",
            "《黑镜》里有个地方叫圣朱尼佩罗，人死了，意识搬进服务器，永远活在1987年的海滩上"]


def assemble_video(claim_ids: list[str]) -> dict:
    """test-side 拼接：逐 claim 8G→8K → 全局引用重编号 → transition → 合并 brief 结构。"""
    blocks = []
    global_urls: list[str] = []
    merged_ent: set[str] = set()
    merged_num: set[str] = set()
    merged_qual: set[str] = set()
    merged_dom: set[str] = set()
    for cid in claim_ids:
        claim_text, ev = claim_evidence(cid)
        styled, brief = styled_for(claim_text, ev)
        struct = brief["structure"]
        merged_ent |= set(struct.get("entities", []))
        merged_num |= set(struct.get("numbers_years", []))
        merged_qual |= set(struct.get("qualifiers", []))
        merged_dom |= set(struct.get("domains", []))
        local_idx_url = {r["index"]: r["url"] for r in styled["references"]}
        for r in styled["references"]:
            if r["url"] not in global_urls:
                global_urls.append(r["url"])
        blocks.append({"claim": claim_text, "styled": styled, "local_idx_url": local_idx_url})
    url_to_global = {u: i + 1 for i, u in enumerate(global_urls)}
    paragraphs = []
    for i, b in enumerate(blocks):
        if i > 0:
            paragraphs.append({"role": "transition", "beat": "转场", "emotion": "过渡",
                               "intensity": 2, "text": f"进入下一部分：{b['claim'][:26]}…",
                               "claims": [], "evidence_refs": []})
        for p in b["styled"]["paragraphs"]:
            text = p["text"]
            def repl(m, _lix=b["local_idx_url"], _ug=url_to_global):
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
    long_styled = {"platform": "bilibili", "paragraphs": paragraphs, "references": refs}
    return {"blocks": len(claim_ids), "paragraphs": len(paragraphs),
            "styled": long_styled, "brief": merged_brief,
            "url_count": len(global_urls)}


videos = {}
for name, cids in (("VIDEO-10", VIDEO_10), ("VIDEO-15", VIDEO_15)):
    v = assemble_video(cids)
    v["plans"] = {p: build_production_plan(v["styled"], v["brief"], p) for p in _PLATFORM_PACING}
    videos[name] = v
    d = v["plans"]["bilibili"]["total_duration_hint"]
    print(f"  [组装] {name}: {v['blocks']} claims / {v['paragraphs']} 段 / {v['url_count']} 全局引用 / "
          f"B站总时长 {d}s（目标 {'540-660' if name=='VIDEO-10' else '810-990'}）")

# 长视频 8L 指标
for name, v in videos.items():
    p = v["plans"]["bilibili"]
    ok_map = len(p["scenes"]) == v["paragraphs"]
    par_refs = sum(1 for x in v["styled"]["paragraphs"] if x.get("evidence_refs"))
    scene_refs = sum(1 for s in p["scenes"] if s["evidence_refs"])
    ok_ev = scene_refs == par_refs and len(p["references"]) == v["url_count"]
    ok_exec = all(bool(s["visual_target"]) and isinstance(s["subtitle_emphasis"], list)
                  and "duration_hint" in s for s in p["scenes"])
    print(f"A1-{name}. 映射完整 {ok_map} | A2-{name}. 引用保持 {ok_ev} "
          f"(scene_refs={scene_refs} par_refs={par_refs} refs={len(p['references'])}/{v['url_count']}) | "
          f"A3-{name}. 可执行 {ok_exec}")

# ---------- ③ 新增指标 ----------
print("\n---- B. Stage 8M 新增四项 ----")
for name, v in videos.items():
    p = v["plans"]["bilibili"]
    scenes = p["scenes"]
    # 6. 长视频 Scene 一致性
    ids = [s["scene_id"] for s in scenes]
    id_ok = ids == [f"S{i:02d}" for i in range(1, len(scenes) + 1)]
    ref_idx = [r["index"] for r in p["references"]]
    ref_ok = ref_idx == list(range(1, len(ref_idx) + 1))
    # 块内情绪连续性（transition 为块边界，跳过边界两侧）
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
    trans_ok = transitions == v["blocks"] - 1
    print(f"B6-{name}. Scene 一致性: id顺序={'PASS' if id_ok else 'FAIL'} | 全局编号={'PASS' if ref_ok else 'FAIL'} | "
          f"块内情绪跳变 {emo_viol} 处 | transition {transitions}/{v['blocks']-1}")

    # 7. 重复视觉风险
    runs = []
    cur = cur_len = 0
    for s in scenes:
        vv = s["visual_target"]
        if vv == cur:
            cur_len += 1
        else:
            if cur_len: runs.append(cur_len)
            cur, cur_len = vv, 1
    runs.append(cur_len)
    max_run = max(runs)
    in_long_runs = sum(r for r in runs if r >= 3)
    frac = in_long_runs / len(scenes)
    print(f"B7-{name}. 重复视觉风险: 最大同型连串 {max_run} | 连串≥3 占比 {frac:.2%}")

    # 8. 信息密度与镜头节奏匹配
    lens = [len(s["script_text"]) for s in scenes]
    emph_n = [len(s["subtitle_emphasis"]) for s in scenes]
    density = [e + l / 50 for e, l in zip(emph_n, lens)]
    durs = [float(s["duration_hint"].rstrip("s")) for s in scenes]
    hi_th = sorted(density)[int(len(density) * 0.75)] if len(density) >= 4 else 0
    lo_th = sorted(durs)[int(len(durs) * 0.25)] if len(durs) >= 4 else 0
    mism = []
    reverse = []
    for i, s in enumerate(scenes):
        if density[i] >= hi_th and durs[i] <= lo_th:
            mism.append(s["scene_id"])
        if density[i] <= sorted(density)[int(len(density) * 0.25)] and durs[i] >= sorted(durs)[int(len(durs) * 0.75)]:
            reverse.append(s["scene_id"])
    print(f"B8-{name}. 密度-节奏匹配: 高密度+短时长 {len(mism)} 处 {mism[:6]} | "
          f"低密度+长时长 {len(reverse)} 处 {reverse[:6]}")

    # 9. 人工制作成本估算
    cost_min = {"口播卡": 5, "结论大字卡": 5, "待补提示卡": 5, "事实核查字幕卡": 10,
                "数据可视化 + 证据截图": 30, "证据来源截图 + 概念动画": 0, "大字标题卡": 0}
    per_type = Counter()
    for s in scenes:
        vt = s["visual_target"]
        key = "口播 + 大字标题卡" if vt.startswith("口播") else vt
        per_type[key] += 1
    COST = {"口播 + 大字标题卡": 5, "结论大字卡": 5, "待补提示卡（黄底警示）": 5,
            "事实核查字幕卡": 10, "数据可视化 + 证据截图": 30, "证据来源截图 + 概念动画": 15,
            "结论大字卡 + 落版": 6, "备选开场口播卡": 5, "关键数字弹出动画": 20, "口播": 4}
    total_min = sum(COST.get(t, 5) * n for t, n in per_type.items())
    print(f"B9-{name}. 人工制作成本估算: 总 {total_min} 分钟 ≈ {total_min/60:.1f} 小时 "
          f"（每千秒视频 {total_min*60/(p['total_duration_hint'] or 1):.0f} 分钟）")

# 冻结回归说明
print("\n[5] 冻结回归: 见最终校验（15 套件 0 失败 + SHA256 不变）")

# ---------- 落盘回放 ----------
out = {
    "_meta": {"name": "r1_stage8m_full",
              "note": "Stage 8M stress test：5 类复杂度 claim + 2 部长视频的 Production Plan，可回放。"},
    "subtitle_misses": subtitle_misses,
    "no_isbushi_mislabel": no_isbushi,
    "videos": {name: {"blocks": v["blocks"], "paragraphs": v["paragraphs"],
                      "url_count": v["url_count"], "plans": v["plans"]} for name, v in videos.items()},
    "stress": {cid: {"plans": r["plans"]} for cid, r in stress_results.items()},
}
(ROOT / "projects" / "_drafts" / "r1_stage8m_full.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
print("\nwritten: projects/_drafts/r1_stage8m_full.json")
