"""V2.1 Stage 8I：Script Planning / Script Agent Layer（隔离实现，未接生产链）。

- 输入：Content Plan（8H）+ Research Brief（8G）；输出：可审核 Script Blueprint 与 Draft Script。
- 不自动生成视频 / 不自动配音 / 不自动剪辑 / 不接生产发布；不改 Evidence 链 / truth 判断。
- 确定性：
  ① Hook 设计（由 Content Plan 的 HCQ 扩展）；
  ② 段落结构规划（Hook → 引入 → 主体段落[绑 Evidence] → 存疑/待补 → 结论）；
  ③ Evidence 绑定（每段标注支持来源）；
  ④ 事实引用映射（数字/限定词/实体 → 来源编号）；
  ⑤ 人工编辑友好输出（【段落】标题 + [n] 行内引用 + [EDIT] 可替换 + [待补] 缺口）。
"""

from __future__ import annotations

from .evidence_signal import _qualifier_present, _num_present
from .evidence_pool import normalize_text
from .evidence_retrieval import source_quality

# 平台脚本结构规格（段落数量/格式差异）
_PLATFORM_SCRIPT = {
    "shipinhao": {"max_body": 1, "format": "竖屏短口播（30-60 秒）", "label": "视频号"},
    "bilibili": {"max_body": 3, "format": "中长口播 + 画面/贴图提示（8-15 分钟）", "label": "B站"},
    "youtube": {"max_body": 4, "format": "长视频 + 章节导航（10-20 分钟）", "label": "YouTube"},
    "gongzhonghao": {"max_body": 5, "format": "图文长文 + 小标题（1500-3000 字）", "label": "公众号"},
}


def _evidence_element_map(struct: dict, evidence: list[dict]) -> list[dict]:
    """每条证据 → 覆盖的 Claim 元素（实体/限定词/数字）。"""
    out = []
    for e in evidence:
        hay = e.get("excerpt", "")
        covers = set()
        for ent in struct.get("entities", []):
            if normalize_text(ent) in hay:
                covers.add(f"entity:{ent}")
        for q in struct.get("qualifiers", []):
            if _qualifier_present(q, hay):
                covers.add(f"qualifier:{q}")
        for n in struct.get("numbers_years", []):
            if _num_present(n, hay):
                covers.add(f"number:{n}")
        out.append({**e, "covers": sorted(covers)})
    return out


def _relevant_to(ev: dict, sc: str) -> bool:
    """证据覆盖的任一元素是否出现在该子命题中。"""
    for elem in ev.get("covers", []):
        val = elem.split(":", 1)[1] if ":" in elem else elem
        if val and (normalize_text(val) in normalize_text(sc) or _num_present(val, sc)):
            return True
    return False


def build_script_blueprint(plan: dict, brief: dict) -> dict:
    """Content Plan + Research Brief → Script Blueprint（段落 + Evidence 绑定 + 事实引用映射）。"""
    struct = brief["structure"]
    hcq = plan["structure"]
    narrative = plan["narrative_direction"]
    ev_map = _evidence_element_map(struct, brief.get("evidence", []))
    refs = [{"index": i + 1, "url": e.get("url", ""), "title": e.get("title", ""),
             "source_tier": source_quality(e.get("url", ""), e.get("title", ""),
                                           e.get("excerpt", ""))["tier"]}
            for i, e in enumerate(ev_map)]
    url_to_idx = {r["url"]: r["index"] for r in refs}

    sections: list[dict] = []

    # ① Hook
    sections.append({"role": "hook", "title": "开场钩子",
                     "points": [hcq["hook"], hcq["conflict"]],
                     "evidence_refs": [], "facts": []})
    # ② 引入
    sections.append({"role": "intro", "title": "引入背景",
                     "points": [f"核心命题：{struct.get('claim_text', '')}",
                                f"叙事方向：{narrative['direction']}"],
                     "evidence_refs": [], "facts": []})
    # ③ 主体段落（每个子命题一段，绑定支持证据）
    sub_claims = struct.get("sub_claims", []) or [struct.get("claim_text", "")]
    for i, sc in enumerate(sub_claims, 1):
        bound_urls = []
        facts = []
        for e in ev_map:
            if not _relevant_to(e, sc):
                continue
            idx = url_to_idx.get(e.get("url", ""))
            bound_urls.append(e.get("url", ""))
            for n in struct.get("numbers_years", []):
                if _num_present(n, sc) and _num_present(n, e.get("excerpt", "")):
                    facts.append({"fact": f"数字/年份 {n}", "ref_index": idx})
        sections.append({"role": "body", "title": f"主体段落 {i}",
                         "points": [sc], "evidence_refs": bound_urls,
                         "facts": [f for f in facts if f["ref_index"]]})
    # ④ 存疑/待补
    if brief.get("gaps"):
        sections.append({"role": "gap", "title": "存疑/待补",
                         "points": brief["gaps"], "evidence_refs": [], "facts": []})
    # ⑤ 结论
    sections.append({"role": "conclusion", "title": "结论",
                     "points": [hcq["question"], "呼应开场钩子，落回核心命题"],
                     "evidence_refs": [], "facts": []})

    return {"claim": struct.get("claim_text", ""), "sections": sections,
            "references": refs, "url_to_index": url_to_idx,
            "narrative": narrative["direction"]}


def _render_draft(blueprint: dict, platform: str) -> str:
    """Blueprint → 平台 Draft Script 文本（可编辑，含 [n]/[EDIT]/[待补]）。"""
    cfg = _PLATFORM_SCRIPT[platform]
    url_to_idx = blueprint["url_to_index"]
    body_seen = 0
    lines = [f"【脚本草案 · {cfg['label']} · {cfg['format']}】",
             f"命题：{blueprint['claim']}", ""]
    for sec in blueprint["sections"]:
        if sec["role"] == "body":
            body_seen += 1
            if body_seen > cfg["max_body"]:
                continue
        lines.append(f"【{sec['title']}】")
        for pt in sec["points"]:
            lines.append(f"- {pt}")
        if sec["evidence_refs"]:
            cites = "、".join(f"[{url_to_idx.get(u, '?')}]" for u in sec["evidence_refs"])
            lines.append(f"  证据引用: {cites}")
        for f in sec["facts"]:
            lines.append(f"  事实引用: {f['fact']} → [{f['ref_index']}]")
        if sec["role"] == "hook":
            lines.append("  [EDIT: 此处可替换为更口语化的开场]")
        if sec["role"] == "gap":
            lines.append("  [待补: 以下元素需补调研，切勿凭空断言]")
        lines.append("")
    lines.append("【参考来源】")
    for r in blueprint["references"]:
        lines.append(f"[{r['index']}] ({r['source_tier'] or '?'}) {r['title'][:40]} {r['url'][:60]}")
    lines.append("\n[本稿为草案，供人工审核编辑；未自动生成视频/配音/剪辑。]")
    return "\n".join(lines)


def build_draft_script(plan: dict, brief: dict, platform: str) -> dict:
    """Blueprint → 平台 Draft Script。"""
    blueprint = build_script_blueprint(plan, brief)
    return {"platform": platform, "blueprint": blueprint,
            "script_text": _render_draft(blueprint, platform)}


def build_all_platform_scripts(plan: dict, brief: dict) -> dict:
    """生成四平台 Draft Script（结构差异）。"""
    return {p: build_draft_script(plan, brief, p) for p in _PLATFORM_SCRIPT}
