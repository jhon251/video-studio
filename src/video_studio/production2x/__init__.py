"""AI Video Agent 2.x 生产入口（Production Entry，2.x Final 冻结版）。

生产链（仅调用 2.x 已冻结模块，不修改任何核心行为）：
INPUT(claims+evidence) → Research Brief(8G) → Content Plan(8H) → Script Blueprint(8I)
→ Draft Script(8J) → Creator Style(8K) → Visual Planning(8N) → Production Constraints(8Q)
→ FINAL PRODUCTION PLAN / SCENE BLUEPRINT

- 确定性、无 LLM、无网络依赖（evidence 为输入正文，不在本入口内检索）。
- 不读取任何实验/诊断资产（scripts/、projects/_drafts/）；输入仅来自调用方。
- 输出带 provenance（输入指纹 + 链版本 + 全局证据引用 + source_paragraphs），可审计可回放。
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

PRODUCTION_VERSION = "2.0.0"
CHAIN_VERSION = "2x-final-8q"          # 2.x 最终冻结链（8G..8Q）
VALID_STYLES = ("academic", "casual", "sharp", "gentle")
VALID_PLATFORMS = ("bilibili", "youtube", "shipinhao", "gongzhonghao")
PLATFORM_TARGET_DEFAULT = "bilibili"   # target_seconds 作用于参考平台（8N/8Q 口径）

_log: list[str] = []


def _log_line(msg: str) -> None:
    _log.append(msg)


def get_log() -> list[str]:
    return list(_log)


def _validate(payload: dict) -> list[str]:
    errors = []
    video = payload.get("video")
    if not isinstance(video, dict):
        return ["input.video 缺失或非对象"]
    claims = video.get("claims")
    if not isinstance(claims, list) or not claims:
        errors.append("input.video.claims 缺失或为空（至少 1 条 claim）")
        return errors
    for i, c in enumerate(claims):
        if not isinstance(c, dict) or not c.get("claim_text"):
            errors.append(f"claims[{i}].claim_text 缺失或为空")
        ev = c.get("evidence")
        if not isinstance(ev, list) or not ev:
            errors.append(f"claims[{i}].evidence 缺失或为空（至少 1 条证据，含 url/title/snippet/body）")
    style = payload.get("style", "casual")
    if style not in VALID_STYLES:
        errors.append(f"style 非法（合法值: {VALID_STYLES}）")
    platforms = payload.get("platforms") or list(VALID_PLATFORMS)
    for p in platforms:
        if p not in VALID_PLATFORMS:
            errors.append(f"platform 非法: {p}（合法值: {VALID_PLATFORMS}）")
    tgt = payload.get("target_seconds")
    if tgt is not None and (not isinstance(tgt, (int, float)) or tgt <= 0):
        errors.append("target_seconds 必须为正数或省略")
    return errors


def _import_chain():
    from video_studio.tools.claim_structuring import build_research_brief
    from video_studio.tools.content_planning import build_content_plan
    from video_studio.tools.script_planning import build_script_blueprint
    from video_studio.tools.narrative_generation import build_narrative_draft
    from video_studio.tools.creator_style import apply_style
    from video_studio.tools.visual_planning import build_production_plan
    from video_studio.tools.production_constraints import calibrate
    return (build_research_brief, build_content_plan, build_script_blueprint,
            build_narrative_draft, apply_style, build_production_plan, calibrate)


def _assemble_claims(claims: list[dict], style: str, fns) -> tuple[list[dict], dict, dict, dict]:
    """逐 claim 走 8G→8K，得到风格化段落 + 全局引用；组装长视频结构。"""
    build_brief, build_plan, build_bp, build_draft, apply_style_fn, _, _ = fns
    blocks = []
    global_urls: list[str] = []
    merged_ent: set[str] = set()
    merged_num: set[str] = set()
    merged_qual: set[str] = set()
    merged_dom: set[str] = set()
    briefs = []
    for i, c in enumerate(claims):
        ct = c["claim_text"]
        ev = c["evidence"]
        brief = build_brief(ct, ev)
        plan = build_plan(brief)
        bp = build_bp(plan, brief)
        draft = build_draft(bp, brief, "bilibili")
        styled = apply_style_fn(draft, brief, style, final=(i == len(claims) - 1))
        st = brief["structure"]
        merged_ent |= set(st.get("entities", []))
        merged_num |= set(st.get("numbers_years", []))
        merged_qual |= set(st.get("qualifiers", []))
        merged_dom |= set(st.get("domains", []))
        lix = {r["index"]: r["url"] for r in styled["references"]}
        for r in styled["references"]:
            if r["url"] not in global_urls:
                global_urls.append(r["url"])
        blocks.append({"claim_text": ct, "styled": styled, "lix": lix})
        briefs.append(brief)
        _log_line(f"claim[{i}] brief+plan+blueprint+draft+style OK ({len(styled['paragraphs'])} 段)")
    u2g = {u: i + 1 for i, u in enumerate(global_urls)}
    paragraphs = []
    for i, b in enumerate(blocks):
        if i > 0:
            # v2 转场：按下一 claim 成熟度做逻辑过渡，不再"进入下一部分：…"机械章节化
            ct = b["claim_text"]
            ttext = f"接着往下——{ct[:26]}…"
            for marker, lead in (("已实现商业化", "先看一个已经落地的——"),
                                 ("已商业化", "先看一个已经落地的——"),
                                 ("接近商业化", "还有一个，就差一步的——"),
                                 ("工程化早期", "再往下，难度就上来了——"),
                                 ("实验到工程化", "真正难的，在后面——"),
                                 ("工程化阶段", "接着往下看——")):
                if marker in ct:
                    ttext = f"{lead}{ct[:26]}…"
                    break
            paragraphs.append({"role": "transition", "beat": "转场", "emotion": "过渡", "intensity": 2,
                               "text": ttext, "claims": [],
                               "evidence_refs": []})
        for p in b["styled"]["paragraphs"]:
            import re as _re
            text = _re.sub(r"\[(\d+)\]",
                           lambda m, _l=b["lix"], _ug=u2g: f"[{_ug.get(_l.get(int(m.group(1)), ''), '?')}]",
                           p["text"])
            paragraphs.append({**p, "text": text, "evidence_refs": list(p.get("evidence_refs", []))})
    refs = [{"index": i + 1, "url": u, "title": next(
        (r["title"] for b in blocks for r in b["styled"]["references"] if r["url"] == u), ""),
        "source_tier": next((r["source_tier"] for b in blocks for r in b["styled"]["references"]
                             if r["url"] == u), None)} for i, u in enumerate(global_urls)]
    merged_struct = {"claim_text": f"长视频（{len(claims)} 条 claim）",
                     "entities": sorted(merged_ent), "numbers_years": sorted(merged_num),
                     "qualifiers": sorted(merged_qual), "domains": sorted(merged_dom),
                     "sub_claims": [], "flags": {}}
    merged_brief = {"structure": merged_struct, "evidence": [], "gaps": []}
    long_styled = {"paragraphs": paragraphs, "references": refs}
    return briefs, long_styled, merged_brief, refs


def run_production(payload: dict) -> dict:
    """生产主入口。payload 见 README；返回 FINAL PRODUCTION PLAN 包。"""
    _log.clear()
    errors = _validate(payload)
    if errors:
        return {"status": "FAIL_INPUT", "production_version": PRODUCTION_VERSION,
                "chain_version": CHAIN_VERSION, "errors": errors, "log": get_log()}
    try:
        fns = _import_chain()
        build_brief, _, _, _, _, build_plan, calibrate = fns
        claims = payload["video"]["claims"]
        style = payload.get("style", "casual")
        platforms = payload.get("platforms") or list(VALID_PLATFORMS)
        target = payload.get("target_seconds")
        briefs, long_styled, merged_brief, refs = _assemble_claims(claims, style, fns)
        final_plans = {}
        for p in platforms:
            tgt = target if (p == PLATFORM_TARGET_DEFAULT and target) else None
            plan = build_plan(long_styled, merged_brief, p, target_seconds=tgt)
            cal = calibrate(plan, merged_brief["structure"])
            # 以校准后 scenes 为最终 Scene Blueprint，重渲染 plan_text 保持一致
            from video_studio.tools.visual_planning import _render_plan
            plan["plan_text"] = _render_plan(p, plan["pacing"], cal["scenes"], cal["references"])
            plan["scenes"] = cal["scenes"]
            final_plans[p] = {"plan": plan, "calibrated": cal}
            _log_line(f"platform[{p}] production plan OK ({len(cal['scenes'])} scenes, "
                      f"total {plan['total_duration_hint']}s)")
        inp = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        fp = hashlib.sha256(inp.encode("utf-8")).hexdigest()[:16]
        ref_plan = final_plans[PLATFORM_TARGET_DEFAULT if PLATFORM_TARGET_DEFAULT in final_plans
                               else platforms[0]]
        package = {
            "status": "OK",
            "production_version": PRODUCTION_VERSION,
            "chain_version": CHAIN_VERSION,
            "input_fingerprint": fp,
            "video_title": payload["video"].get("title", ""),
            "style": style,
            "claim_count": len(claims),
            "paragraph_count": len(long_styled["paragraphs"]),
            "platforms": platforms,
            "target_seconds": target,
            "references": refs,
            "reference_platform": platforms[0],
            "total_scenes": {p: len(v["plan"]["scenes"]) for p, v in final_plans.items()},
            "total_duration": {p: v["plan"]["total_duration_hint"] for p, v in final_plans.items()},
            "calibrated_cost": ref_plan["calibrated"]["cost"],
            "balance": ref_plan["calibrated"]["balance"],
            "material": ref_plan["calibrated"]["material"],
            "cost_base_check": ref_plan["calibrated"]["cost_base_check"],
            "plans": final_plans,
            "warnings": [],
            "log": get_log(),
        }
        return package
    except Exception as exc:  # noqa: BLE001
        return {"status": "FAIL_INTERNAL", "production_version": PRODUCTION_VERSION,
                "chain_version": CHAIN_VERSION, "error": f"{type(exc).__name__}: {exc}",
                "log": get_log()}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print("用法: python -m video_studio.production2x <input.json> [-o 输出目录]")
        print("输入格式见 docs/PRODUCTION_2X_README.md §2。")
        return 2
    input_path = Path(argv[0])
    out_dir = None
    if "-o" in argv:
        out_dir = Path(argv[argv.index("-o") + 1])
    if not input_path.exists():
        print(f"FAIL_INPUT: 输入文件不存在: {input_path}")
        return 3
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    package = run_production(payload)
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "final_production_plan.json").write_text(
            json.dumps(package, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        for p, v in package.get("plans", {}).items():
            (out_dir / f"plan_{p}.txt").write_text(v["plan"]["plan_text"], encoding="utf-8")
        (out_dir / "production.log").write_text("\n".join(package["log"]), encoding="utf-8")
    print(f"STATUS={package['status']} version={package['production_version']} "
          f"chain={package['chain_version']}")
    for line in package["log"]:
        print("  " + line)
    return 0 if package["status"] == "OK" else 1


if __name__ == "__main__":
    sys.exit(main())
