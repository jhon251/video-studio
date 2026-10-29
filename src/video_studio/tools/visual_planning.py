"""V2.1 Stage 8N：Visual Planning Layer 优化版（Scene Budget + Visual Diversity）。

- 输入：Creator Style Script（8K）；输出：可审核 Production Plan / Scene Blueprint。
- 不自动视频生成 / 剪辑 / 发布；不接 TTS / 素材库；不改 Evidence / Truth Layer；不新增 Agent。
- 确定性规则，无 LLM / 随机。
- A. Scene Budget Control：
  A1 块预算（transition 为块边界，每块 ≤8 scene：hook1/conclusion_first1/body≤3/fact≤1/gap1/conclusion1）；
  A2 高事实密度合并（块内全部 fact 合并为 1 scene，fact_refs 全量保持；body 超 3 段并入第 3 段）；
  A3 目标时长密度加权分配（无 target 时保持 8L 公式 shot_seconds×强度，向后兼容）。
- B. Visual Diversity Constraint：
  B1 MAX_VISUAL_RUN=3 + role 视觉变体轮换（跨块连续计数）；
  B2 fact 紧随本块最后 body；gap 在 conclusion 前；body≤1 且无 gap 时 conclusion_first 并入 conclusion；
  B3 transition 用"转场字幕卡"断串。
- 每 scene 记录 source_paragraphs（源段落索引），覆盖可审计；Evidence 引用零改写。
"""

from __future__ import annotations

_SCENE_VISUAL = {
    "hook": {"visual": "口播 + 大字标题卡", "broll": "悬念相关快切素材（2-3 镜）"},
    "conclusion_first": {"visual": "结论大字卡", "broll": "关键数字弹出动画"},
    "body": {"visual": "数据可视化 + 证据截图", "broll": "证据来源截图 + 概念动画"},
    "fact": {"visual": "事实核查字幕卡", "broll": "来源引用标注（页脚）"},
    "gap": {"visual": "待补提示卡（黄底警示）", "broll": ""},
    "conclusion": {"visual": "结论大字卡 + 落版", "broll": "呼应开场画面"},
    "transition": {"visual": "转场字幕卡", "broll": ""},
}

_VISUAL_VARIANTS = {
    "hook": ["口播 + 大字标题卡", "快切素材 + 大字标题卡", "口播 + 全屏数字卡"],
    "conclusion_first": ["结论大字卡", "结论口播 + 关键数字卡"],
    "body": ["数据可视化 + 证据截图", "概念动画 + 口播", "实拍素材 + 数据角标"],
    "fact": ["事实核查字幕卡", "来源截图 + 引注", "核查清单卡"],
    "conclusion": ["结论大字卡 + 落版", "结论口播 + 呼应画面"],
    "transition": ["转场字幕卡"],
}
MAX_VISUAL_RUN = 3
MAX_BODY_PER_BLOCK = 3
MAX_FACTS_PER_SCENE = 4
MAX_SCENES_PER_BLOCK = 8

_PLATFORM_PACING = {
    "shipinhao": {"shot_seconds": 1.5, "note": "竖屏快切 / 大字弹幕风 / 视觉密度高"},
    "bilibili": {"shot_seconds": 6, "note": "中长镜头 / 进度条 / 贴图梗"},
    "youtube": {"shot_seconds": 8, "note": "章节导航 / 信息卡 / 双语字幕"},
    "gongzhonghao": {"shot_seconds": None, "note": "图文 / 每节配图 + 小标题"},
}

_SUPERLATIVE = {"第一", "首次", "首例", "最大", "唯一", "最早"}
_NEG_WORDS = ("不是", "没有", "尚未", "从未", "无法", "不具备", "并非", "尚无")


def _subtitle_emphasis(text: str, struct: dict) -> list[str]:
    """字幕重点：数字/年份 + 实体 + 最高级限定词 + 否定词（排除"是不是"反问）。"""
    marks: set[str] = set()
    for n in struct.get("numbers_years", []):
        if n and n in text:
            marks.add(n)
    for e in struct.get("entities", []):
        if e and e in text:
            marks.add(e)
    for q in struct.get("qualifiers", []):
        if q in _SUPERLATIVE and q in text:
            marks.add(q)
    cleaned = text.replace("是不是", "\u3000")
    for w in _NEG_WORDS:
        if w in cleaned:
            marks.add(w)
    return sorted(marks)


def _split_blocks(paras: list[dict]) -> list[list[tuple[int, dict]]]:
    """按 transition 切块；transition 自身成独立单段块。"""
    blocks: list[list[tuple[int, dict]]] = []
    cur: list[tuple[int, dict]] = []
    for idx, p in enumerate(paras):
        if p["role"] == "transition":
            if cur:
                blocks.append(cur)
                cur = []
            blocks.append([(idx, p)])
        else:
            cur.append((idx, p))
    if cur:
        blocks.append(cur)
    return blocks


def _block_to_groups(block: list[tuple[int, dict]]) -> list[dict]:
    """块内段落 → scene 组（含预算压缩 + fact 合并 + conclusion_first 并入结论）。"""
    groups: list[dict] = []
    body_groups: list[dict] = []
    pending_facts: list[tuple[int, dict]] = []
    has_gap = False
    has_cf = False

    def flush_facts():
        if not pending_facts:
            return
        facts = []
        for _, p in pending_facts:
            text = p["text"]
            if text.startswith("事实核查："):
                body_part = text[len("事实核查："):]
                if " → [" in body_part:
                    fact, ref = body_part.rsplit(" → [", 1)
                    ref = ref.rstrip("]")
                    facts.append({"fact": fact, "ref_index": int(ref) if ref.isdigit() else None})
                else:
                    facts.append({"fact": body_part, "ref_index": None})
            else:
                facts.append({"fact": text, "ref_index": None})
        groups.append({"role": "fact", "source_idxs": [i for i, _ in pending_facts],
                       "texts": [p["text"] for _, p in pending_facts], "facts": facts,
                       "refs": []})
        pending_facts.clear()

    i = 0
    n = len(block)
    while i < n:
        idx, p = block[i]
        role = p["role"]
        if role in ("hook", "hook_alt"):
            texts = [p["text"]]
            idxs = [idx]
            j = i + 1
            while j < n and block[j][1]["role"] == "hook_alt":
                texts.append(block[j][1]["text"])
                idxs.append(block[j][0])
                j += 1
            groups.append({"role": "hook", "source_idxs": idxs, "texts": texts,
                           "refs": [], "hook_alternates": texts[1:]})
            i = j
            continue
        if role == "conclusion_first":
            has_cf = True
            groups.append({"role": "conclusion_first", "source_idxs": [idx],
                           "texts": [p["text"]], "refs": []})
            i += 1
            continue
        if role == "body":
            g = {"role": "body", "source_idxs": [idx], "texts": [p["text"]],
                 "refs": list(p.get("evidence_refs", []))}
            if len(body_groups) < MAX_BODY_PER_BLOCK:
                body_groups.append(g)
                groups.append(g)
            else:
                tgt = body_groups[-1]
                tgt["source_idxs"].append(idx)
                tgt["texts"].append(p["text"])
                tgt["refs"] = list(dict.fromkeys(tgt["refs"] + list(p.get("evidence_refs", []))))
            i += 1
            continue
        if role == "fact":
            pending_facts.append((idx, p))
            i += 1
            continue
        if role == "gap":
            flush_facts()
            has_gap = True
            groups.append({"role": "gap", "source_idxs": [idx], "texts": [p["text"]], "refs": []})
            i += 1
            continue
        if role == "conclusion":
            flush_facts()
            groups.append({"role": "conclusion", "source_idxs": [idx], "texts": [p["text"]],
                           "refs": []})
            i += 1
            continue
        groups.append({"role": role, "source_idxs": [idx], "texts": [p["text"]], "refs": []})
        i += 1
    flush_facts()

    # B2：body≤1 且无 gap 时，conclusion_first 并入 conclusion（省 1 镜）
    if has_cf and len(body_groups) <= 1 and not has_gap:
        cf = next((g for g in groups if g["role"] == "conclusion_first"), None)
        conc = next((g for g in groups if g["role"] == "conclusion"), None)
        if cf is not None and conc is not None:
            conc["source_idxs"] = cf["source_idxs"] + conc["source_idxs"]
            conc["texts"] = cf["texts"] + conc["texts"]
            groups.remove(cf)
    return groups


def build_scene_blueprint(styled_script: dict, brief: dict) -> dict:
    """段落 → Scene（块预算 + fact 合并 + 视觉变体轮换 + 跨块连串计数）。"""
    struct = brief["structure"]
    paras = styled_script["paragraphs"]
    blocks = _split_blocks(paras)

    scenes: list[dict] = []
    variant_pos: dict[str, int] = {}
    prev_visual: str | None = None
    run = 0

    def assign_visual(role: str) -> str:
        nonlocal prev_visual, run
        pool = _VISUAL_VARIANTS.get(role)
        if pool:
            v = pool[variant_pos.get(role, 0) % len(pool)]
            variant_pos[role] = variant_pos.get(role, 0) + 1
            guard = 0
            while v == prev_visual and guard < len(pool):
                v = pool[variant_pos[role] % len(pool)]
                variant_pos[role] += 1
                guard += 1
        else:
            v = _SCENE_VISUAL.get(role, {"visual": "口播", "broll": ""})["visual"]
        run = run + 1 if v == prev_visual else 1
        prev_visual = v
        return v

    for block in blocks:
        groups = _block_to_groups(block)
        for g in groups:
            role = g["role"]
            first_idx = g["source_idxs"][0] if g["source_idxs"] else None
            first = next((p for idx, p in block if idx == first_idx), {})
            refs = list(dict.fromkeys(g.get("refs", [])))
            texts = g["texts"]
            emph: set[str] = set()
            for t in texts:
                emph.update(_subtitle_emphasis(t, struct))
            vis = _SCENE_VISUAL.get(role, {"visual": "口播", "broll": ""})
            scene = {
                "role": role,
                "beat": (first.get("beat") if first else role) if role not in ("fact",) else "事实核查",
                "emotion": first.get("emotion", "专注") if first else "专注",
                "intensity": first.get("intensity", 2) if first else 2,
                "script_text": "；".join(texts) if role != "fact" else
                "；".join(texts)[:160],
                "visual_target": assign_visual(role),
                "visual_role": role,
                "broll_requirement": vis["broll"],
                "subtitle_emphasis": sorted(emph),
                "evidence_refs": refs,
                "source_paragraphs": list(g["source_idxs"]),
            }
            if role == "hook":
                scene["hook_alternates"] = g.get("hook_alternates", [])
            if role == "fact":
                facts = g.get("facts", [])
                scene["fact_refs"] = facts
                shown = facts[:MAX_FACTS_PER_SCENE]
                parts = [f"{f['fact']} → [{f['ref_index']}]" if f["ref_index"] else f["fact"]
                         for f in shown]
                if len(facts) > MAX_FACTS_PER_SCENE:
                    parts.append(f"…等 {len(facts) - MAX_FACTS_PER_SCENE} 项")
                scene["script_text"] = "；".join(parts)
                scene["fact_refs_all"] = facts
            scenes.append(scene)

    # 场景编号
    for i, s in enumerate(scenes, 1):
        s["scene_id"] = f"S{i:02d}"
    return {"claim": struct.get("claim_text", ""), "scenes": scenes,
            "references": styled_script.get("references", [])}


def build_production_plan(styled_script: dict, brief: dict, platform: str,
                          target_seconds: float | None = None) -> dict:
    """平台 Production Plan（A3：target_seconds 下密度加权分配；无 target 保持 8L 公式）。"""
    bp = build_scene_blueprint(styled_script, brief)
    pacing = _PLATFORM_PACING[platform]
    scenes = bp["scenes"]
    if pacing["shot_seconds"]:
        if target_seconds:
            weights = [1 + len(s["subtitle_emphasis"]) + len(s["script_text"]) / 50 for s in scenes]
            tw = sum(weights)
            durs = [target_seconds * w / tw for w in weights]
            durs = [max(4.0, min(30.0, d)) for d in durs]
            diff = target_seconds - sum(durs)
            guard = 0
            while abs(diff) > 1.0 and guard < 20:
                free = [i for i, d in enumerate(durs)
                        if (diff > 0 and d < 30.0) or (diff < 0 and d > 4.0)]
                if not free:
                    break
                adj = diff / len(free)
                for i in free:
                    durs[i] = max(4.0, min(30.0, durs[i] + adj))
                diff = target_seconds - sum(durs)
                guard += 1
            for s, d in zip(scenes, durs):
                s["duration_hint"] = f"{d:.0f}s"
            total = sum(durs)
        else:
            total = 0.0
            for s in scenes:
                dur = round(pacing["shot_seconds"] * max(1, s["intensity"]), 1)
                s["duration_hint"] = f"{dur:.0f}s"
                total += dur
    else:
        for s in scenes:
            s["duration_hint"] = "图文（每节配图）"
        total = 0.0
    return {"platform": platform, "pacing": pacing, "total_duration_hint": round(total, 1),
            **bp, "plan_text": _render_plan(platform, pacing, scenes, bp["references"])}


def _render_plan(platform: str, pacing: dict, scenes: list[dict], references: list[dict]) -> str:
    label = {"shipinhao": "视频号", "bilibili": "B站", "youtube": "YouTube",
             "gongzhonghao": "公众号"}[platform]
    lines = [f"【Production Plan · {label}】（{pacing['note']}）", ""]
    for s in scenes:
        emph = "、".join(s["subtitle_emphasis"]) or "（无）"
        lines.append(f"【{s['scene_id']}｜{s['beat']}｜{s['duration_hint']}】")
        lines.append(f"  脚本：{s['script_text']}")
        lines.append(f"  画面：{s['visual_target']}")
        if s["broll_requirement"]:
            lines.append(f"  B-roll：{s['broll_requirement']}")
        lines.append(f"  字幕重点：{emph}")
        if s.get("hook_alternates"):
            lines.append(f"  备选开场：{s['hook_alternates']}")
        if s.get("fact_refs"):
            fstr = "、".join(f"{f['fact']}→[{f['ref_index']}]" for f in s["fact_refs"])
            lines.append(f"  事实引用：{fstr}")
        if s["evidence_refs"]:
            lines.append(f"  证据引用：{'、'.join(s['evidence_refs'])}")
        lines.append(f"  源段落：{s['source_paragraphs']}")
        lines.append("")
    lines.append("【参考来源】")
    for r in references:
        lines.append(f"[{r['index']}] ({r['source_tier'] or '?'}) {r['title'][:40]} {r['url']}")
    lines.append("\n[本计划为视觉蓝本，供人工制作执行；未自动生成视频/剪辑/发布/接入 TTS。]")
    return "\n".join(lines)


def build_all_platform_plans(styled_script: dict, brief: dict) -> dict:
    """四平台 Production Plan。"""
    return {p: build_production_plan(styled_script, brief, p) for p in _PLATFORM_PACING}
