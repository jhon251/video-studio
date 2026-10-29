"""plan_builder（v3-mvp）：编排 sanitizer → director(LLM|fallback) → 文本落地 →
realizer（statement→帧规格）→ validator → 冻结 visual_plan。

- Validator 是唯一执行大门；REJECTED 镜先 LLM 重试（≤2）→ 仍拒按镜规则回退；
- 幂等：input_fingerprint 不变且产物存在 → 跳过；
- 全部 LLM 原始输出落盘（SHA 记录）。
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from video_studio.stage33 import director, planner_fallback, realizer, sanitizer, schemas
from video_studio.stage33.validator import Validator

ROOT = Path(__file__).resolve().parents[3]


def _fingerprint(ctx: dict) -> str:
    caps = json.dumps(schemas.CAPS, sort_keys=True)
    style = json.dumps(schemas.STYLE_CONTRACT, sort_keys=True)
    s = (ctx["inputs"]["narration_sha"] + ctx["inputs"]["shotlist_sha"]
         + ctx["inputs"]["package_sha"] + ctx["inputs"].get("alignment_sha", "")
         + caps + style + director.LLM_TAG + "v3-mvp")
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def _build_beats(ctx: dict, director_out: dict, fp: str) -> list[dict]:
    timing = {s["shot_id"]: s["timing"] for s in ctx["shots"] if s.get("timing")}
    nar_by_id = {s["shot_id"]: s["narration"] for s in ctx["shots"]}
    seed = int(hashlib.sha256(fp.encode("utf-8")).hexdigest()[:8], 16)
    style = dict(schemas.STYLE_CONTRACT)
    beats, counter = [], [0]

    def intensity_of(types):
        if any(t in ("DATA", "CONCLUSION") for t in types):
            return "HIGH"
        if any(t in ("CONTRAST", "ACTION") for t in types):
            return "MED"
        return "LOW"

    for s in ctx["shots"]:
        sid = s["shot_id"]
        narration = nar_by_id.get(sid, "")
        t0 = timing.get(sid, {}).get("start", 0.0)
        dur = timing.get(sid, {}).get("duration") or 4.0
        statements = (director_out.get("shots", {}).get(sid, {}) or {}).get("beats", [])
        if not statements:
            fb = planner_fallback.decide_shot(
                sid, narration, s["shot_role"], s["whitelisted_candidates"],
                director_out.get("arc", {}), is_last_shot=(sid == ctx["shots"][-1]["shot_id"]))
            statements = fb["beats"]
        pieces = realizer.split_n(narration, len(statements), dur)
        total_chars = max(sum(len(p) for p in pieces), 1)
        cum = 0.0
        for i, piece in enumerate(pieces):
            counter[0] += 1
            bid = f"B{counter[0]:03d}"
            stmt = statements[i] if i < len(statements) else statements[-1]
            bd = dur * len(piece) / total_chars
            bd = min(max(bd, 0.4), dur - cum - 0.001 * (len(pieces) - i - 1))
            start = t0 + cum
            end = t0 + dur if i == len(pieces) - 1 else start + bd
            cum += bd
            types = planner_fallback.detect_beat_types(piece)
            beat = {
                "beat_id": bid, "shot_id": sid, "beat_text": piece,
                "start": round(start, 3), "end": round(end, 3),
                "duration": round(end - start, 3),
                "beat_types": types, "intensity": intensity_of(types),
                "emphasis_target": planner_fallback._target(piece),
                "statement": dict(stmt),
            }
            beat["spec"] = realizer.build_beat_spec(beat, stmt, ctx, style, seed)
            # 运动计划链：planned → capability_limit → actual（HOLD 降级必须留痕）
            m = stmt.setdefault("motion", {})
            m["planned_behavior"] = m.get("intent", "none")
            if beat["spec"].get("motion_note"):
                m["actual_behavior"] = "HOLD"
                m["capability_limit"] = beat["spec"]["motion_note"]
            else:
                m["actual_behavior"] = m["planned_behavior"]
                m["capability_limit"] = ""
            beats.append(beat)
    return beats


def _arc_of(ctx: dict, director_out: dict, beats: list[dict]) -> dict:
    arc = director_out.get("arc", {})
    flow = arc.get("flow", []) or []
    climax_shot = arc.get("climax_shot")
    climax_beat = None
    if climax_shot:
        cbs = [b for b in beats if b["shot_id"] == climax_shot]
        if cbs:
            order = {"LOW": 0, "MED": 1, "HIGH": 2}
            climax_beat = max(cbs, key=lambda b: order.get(b["intensity"], 0))["beat_id"]
    release_beats = []
    for s in arc.get("release_shots", []) or []:
        bs = [b for b in beats if b["shot_id"] == s]
        if bs:
            release_beats.append(bs[-1]["beat_id"])
    return {"flow": flow, "climax_shot": climax_shot, "climax_beat": climax_beat,
            "release_shots": arc.get("release_shots", []),
            "release_beats": release_beats,
            "pacing_note": arc.get("pacing_note", "")}


def _problem_shots(plan: dict, result: dict) -> set[str]:
    sids = {r["shot_id"] for r in result["rejects"]}
    beat2shot = {b["beat_id"]: b["shot_id"] for b in plan["beats"]}
    for r in result.get("junk", []):
        sid = beat2shot.get(r.get("beat_id"))
        if sid:
            sids.add(sid)
    return {s for s in sids if s}


def build_plan(pkg_dir: Path, alignment_path: Path, out_dir: Path,
               use_fallback: bool = False, force: bool = False) -> dict:
    narration = pkg_dir / "V2_FINAL_SCRIPT_JARVIS.md"
    shotlist = pkg_dir / "shotlist.json"
    all_shots = pkg_dir / "material_pkg_real" / "shot_mapping" / "all_shots.json"
    for p, tag in ((narration, "口播稿"), (shotlist, "shotlist"), (all_shots, "Material Package")):
        if not p.exists():
            raise SystemExit(f"缺少{tag}：{p}")
    ctx = sanitizer.build_context(narration, shotlist, all_shots, alignment_path)
    ctx["project"] = pkg_dir.name
    fp = _fingerprint(ctx)
    out_dir.mkdir(parents=True, exist_ok=True)
    plan_path = out_dir / "visual_plan.json"
    if plan_path.exists() and not force:
        old = json.loads(plan_path.read_text(encoding="utf-8"))
        if old.get("input_fingerprint") == fp:
            print(f"v3 visual_plan 已存在（指纹一致），跳过：{plan_path}")
            return {"skipped": True, "plan": old, "fingerprint": fp}

    if use_fallback:
        director_out = planner_fallback.run_fallback(ctx)
        meta_mode = "RULE_FALLBACK"
    else:
        try:
            director_out = director.run_director(ctx, out_dir)
            meta_mode = "LLM"
        except Exception as e:  # noqa: BLE001
            print(f"LLM Director 不可用（{type(e).__name__}: {e}）→ 规则回退")
            director_out = planner_fallback.run_fallback(ctx)
            meta_mode = "RULE_FALLBACK"

    beats = _build_beats(ctx, director_out, fp)
    plan = {"schema_version": "3.3-v3-mvp", "generator_version": "3.3-v3-mvp",
            "project": ctx["project"], "style_contract": dict(schemas.STYLE_CONTRACT),
            "narrative_arc": _arc_of(ctx, director_out, beats),
            "beats": beats, "motifs": []}
    result = Validator(plan, ctx).run()
    shot_fallback: list[str] = []

    if meta_mode == "LLM":
        arc_summary = {"flow": director_out["arc"].get("flow", []),
                       "climax_shot": director_out["arc"].get("climax_shot"),
                       "release_shots": director_out["arc"].get("release_shots", []),
                       "pacing_note": director_out["arc"].get("pacing_note", "")}
        for sid in sorted(_problem_shots(plan, result)):
            ok = False
            for attempt in range(2):
                try:
                    res = director._chat(
                        [{"role": "system", "content": director.SYSTEM},
                         {"role": "user", "content": director._shot_prompt(
                             ctx, arc_summary, "", sid)}],
                        director.SHOT_SCHEMA, f"retry_{sid}", 2400, temperature=0.7)
                    director_out["shots"][sid] = res["data"]
                    (out_dir / "llm_raw" / f"llm_raw_{sid}_retry{attempt}.json").write_text(
                        json.dumps(res["raw_text"], ensure_ascii=False, indent=2),
                        encoding="utf-8")
                    beats = _build_beats(ctx, director_out, fp)
                    plan = {"schema_version": "3.3-v3-mvp",
                            "generator_version": "3.3-v3-mvp", "project": ctx["project"],
                            "style_contract": dict(schemas.STYLE_CONTRACT),
                            "narrative_arc": _arc_of(ctx, director_out, beats),
                            "beats": beats, "motifs": []}
                    result = Validator(plan, ctx).run()
                    if sid not in _problem_shots(plan, result):
                        ok = True
                        break
                except Exception as e:  # noqa: BLE001
                    print(f"retry {sid} attempt {attempt}: {type(e).__name__}: {e}")
            if not ok:
                fb = planner_fallback.decide_shot(
                    sid,
                    next(s["narration"] for s in ctx["shots"] if s["shot_id"] == sid),
                    next(s["shot_role"] for s in ctx["shots"] if s["shot_id"] == sid),
                    next(s["whitelisted_candidates"] for s in ctx["shots"]
                        if s["shot_id"] == sid),
                    director_out["arc"], is_last_shot=(sid == ctx["shots"][-1]["shot_id"]))
                director_out["shots"][sid] = fb
                shot_fallback.append(sid)
                print(f"{sid}: LLM 重试失败 → 规则回退该镜")
        beats = _build_beats(ctx, director_out, fp)
        plan = {"schema_version": "3.3-v3-mvp", "generator_version": "3.3-v3-mvp",
                "project": ctx["project"], "style_contract": dict(schemas.STYLE_CONTRACT),
                "narrative_arc": _arc_of(ctx, director_out, beats),
                "beats": beats, "motifs": []}
        result = Validator(plan, ctx).run()
    if use_fallback or meta_mode == "RULE_FALLBACK":
        shot_fallback = [s["shot_id"] for s in ctx["shots"]]

    if result["gate"] == "REJECTED":
        (out_dir / "validator_log.json").write_text(
            json.dumps({"gate": "REJECTED", "rejects": result["rejects"],
                        "junk": result["junk"], "repairs": result["repairs"]},
                       ensure_ascii=False, indent=2), encoding="utf-8")
        raise SystemExit(f"Validator REJECTED（rejects={result['rejects']} "
                         f"junk={len(result['junk'])}）——计划停用，不进入执行。")

    plan["meta"] = {"director_mode": meta_mode,
                    "llm_model": director.LLM_TAG if meta_mode == "LLM" else None,
                    "fallback_used": meta_mode == "RULE_FALLBACK",
                    "shot_fallback": shot_fallback}
    plan["input_fingerprint"] = fp
    plan["inputs"] = ctx["inputs"]
    body = json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True)
    plan["plan_sha"] = hashlib.sha256(body.encode("utf-8")).hexdigest()
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "validator_log.json").write_text(
        json.dumps(plan["validator_log"], ensure_ascii=False, indent=2), encoding="utf-8")
    raw_shas = {}
    raw_dir = out_dir / "llm_raw"
    if raw_dir.exists():
        for f in sorted(raw_dir.glob("llm_raw_*.json")):
            raw_shas[f.name] = hashlib.sha256(f.read_bytes()).hexdigest()
    _write_report(plan, director_out, raw_shas, out_dir)
    print(f"v3 visual_plan 冻结：{plan_path}\nplan_sha={plan['plan_sha']}\n"
          f"gate={result['gate']}")
    return {"skipped": False, "plan": plan, "fingerprint": fp,
            "plan_sha": plan["plan_sha"], "gate": result["gate"],
            "director_stats": director_out.get("stats", {}), "llm_raw_shas": raw_shas}


def _write_report(plan: dict, director_out: dict, raw_shas: dict, out_dir: Path):
    beats = plan["beats"]
    n = len(beats)
    m_hist = {}
    for b in beats:
        m_hist[b["spec"]["motion_intent"]] = m_hist.get(b["spec"]["motion_intent"], 0) + 1
    anchor_missing = [b["beat_id"] for b in beats if not b["spec"]["anchor_text"]]
    hold_notes = [b["spec"]["motion_note"] for b in beats if b["spec"].get("motion_note")]
    # HOLD_reason_quality（人工可读：静止是否真的有充分理由）
    hold_buckets = {"static_by_design": [], "intent_but_capability_limited": [],
                    "rule_fallback_static": []}
    for b in beats:
        m = (b["statement"].get("motion") or {})
        if m.get("actual_behavior") in ("HOLD", "none"):
            if m.get("capability_limit"):
                hold_buckets["intent_but_capability_limited"].append(b["beat_id"])
            elif m.get("intent") == "none" and \
                    len((m.get("necessity") or "").strip()) >= 8:
                hold_buckets["static_by_design"].append(b["beat_id"])
            else:
                hold_buckets["rule_fallback_static"].append(b["beat_id"])
    release_note = ("LLM arc 未提供 release 镜；按纪律不人为填充，收束由末镜静止+锚点实现"
                    if not plan["narrative_arc"].get("release_beats")
                    else f"release_beats={plan['narrative_arc'].get('release_beats')}")
    L = ["# Coral v3 visual_plan 报告（V3-MVP）", "",
         f"- gate: **{plan['validator_log']['gate']}**"
         f"（修复 {plan['validator_log']['repairs_total']}，"
         f"junk {plan['validator_log'].get('repairs_junk', 0)}）",
         f"- director_mode: {plan['meta']['director_mode']}"
         f"（按镜回退: {plan['meta'].get('shot_fallback') or '无'}）",
         f"- plan_sha: `{plan['plan_sha']}`",
         f"- input_fingerprint: `{plan['input_fingerprint']}`",
         "", "## 视觉命题分布", f"- 总 beats: **{n}**",
         f"- motion intent: {m_hist}（none=绝对静止）",
         f"- 运动不可行→HOLD 留痕: {len(hold_notes)} 处",
         f"- 锚点词缺失: {anchor_missing}（应空）",
         f"- 反模板违规: {len(plan['validator_log']['structural_rejects'])} 处（应 0）",
         "", "## HOLD_reason_quality（静止理由质量，人工可读）",
         f"- 静止设计（intent=none 且理由 ≥8 字）: **{len(hold_buckets['static_by_design'])}** "
         f"{hold_buckets['static_by_design'][:8]}",
         f"- 意图运动但能力降级（记录 planned→capability_limit→actual=HOLD 链）: "
         f"**{len(hold_buckets['intent_but_capability_limited'])}** "
         f"{hold_buckets['intent_but_capability_limited'][:8]}",
         f"- 规则回退静止: **{len(hold_buckets['rule_fallback_static'])}** "
         f"{hold_buckets['rule_fallback_static'][:8]}",
         "", "## 叙事弧",
         f"- climax_beat: {plan['narrative_arc'].get('climax_beat')}"
         f"（climax_shot: {plan['narrative_arc'].get('climax_shot')}）",
         f"- release: {release_note}",
         f"- pacing: {plan['narrative_arc'].get('pacing_note','')}",
         "", "## 逐镜 statement（注意力命题）", "",
         "| beat | 镜 | 口播 | 焦点(attention_target) | 证据/隐喻 | 运动必要性(intent) | 关系(→prev) |", 
         "|---|---|---|---|---|---|---|"]
    for b in beats:
        st = b["statement"]
        ev = st.get("evidence_material") or ("隐喻:" + (st.get("visual_metaphor") or "")[:18])
        L.append(f"| {b['beat_id']} | {b['shot_id']} | {b['beat_text'][:16]}… | "
                 f"{st.get('attention_target','')[:12]} | {str(ev)[:26]} | "
                 f"{(st.get('motion') or {}).get('intent')} | "
                 f"{(st.get('relation_to_previous') or {}).get('type')} |")
    L += ["", "## 性能", f"- director stats: {director_out.get('stats', {})}",
          "", "## LLM 原始输出 SHA", "```"]
    L += [f"{k}  {v}" for k, v in raw_shas.items()]
    L += ["```"]
    (out_dir / "plan_report.md").write_text("\n".join(L), encoding="utf-8")
