"""V2.1 Stage 8H：Content Planning Layer（隔离实现，未接生产链）。

- 输入：Research Brief（8G build_research_brief 输出）；输出：Content Plan（非最终脚本）。
- 只读复用 8G/8F 产物与冻结组件，不改 Evidence 链 / truth 判断 / Evidence Readiness 语义。
- 确定性规则：
  ① 受众角度生成：claim_type + 领域 + readiness + 矛盾 → 2-3 个差异化角度。
  ② 叙事方向规划：claim_type / 步骤 / 置信度 → 方向。
  ③ Hook/Conflict/Question 结构：从 claim 最醒目元素（数字/最高级/矛盾/虚构）派生。
  ④ 平台适配：B站 / YouTube / 视频号 / 公众号（时长/风格/钩子/互动）。
"""

from __future__ import annotations

_ANGLE_BY_TYPE = {
    "QUESTION": "解惑向", "ASSERTION": "验证向", "DEFINITION": "科普向",
    "NARRATIVE": "故事向", "CONTRAST": "对比向", "RHETORICAL": "思辨向",
}

_DOMAIN_ANGLE = {
    "LAW": "法律视角", "CRIMINAL": "法律视角", "GOV": "办事指南", "TAX": "办事指南",
    "ECON": "成本视角", "MONEY": "成本视角", "BIZ": "商业视角", "INVEST": "投资视角",
    "PHIL": "哲学思辨", "PHIL_IDENTITY": "身份哲思", "PHIL_HISTORY": "思想史视角",
    "ACAD": "学术前沿", "BRAIN": "硬核科普", "UPLOAD": "未来科技", "LIFE": "生命科学",
    "SCIFI": "影视解构", "TECHBUS": "技术拆解", "CLOUD": "云技术", "ASTRO": "天文科普",
    "PSY": "心理视角", "QR": "生活指南", "ECOMMERCE": "消费视角",
}

_SUPERLATIVE = {"第一", "首次", "首例", "最大", "唯一", "最早"}

_PLATFORMS = {
    "bilibili": {"时长": "8-15 分钟", "风格": "中长深度科普 / 二次元梗", "钩子": "开场 3 秒悬念 + 进度条预告",
                 "互动": "弹幕互动 + 评论区投票"},
    "youtube": {"时长": "10-20 分钟", "风格": "国际视角 / 中英双语字幕", "钩子": "前 5 秒结论冲击 + 章节导航",
                "互动": "章节信息卡 + 订阅引导"},
    "shipinhao": {"时长": "30-60 秒", "风格": "强钩子短平快 / 竖屏", "钩子": "第 1 秒抛出反常识结论",
                  "互动": "点赞转发 + 评论区置顶"},
    "gongzhonghao": {"时长": "1500-3000 字图文", "风格": "深度长文 + 小标题分层", "钩子": "标题悬念 + 首段抛出问题",
                     "互动": "文末提问 + 关注引导"},
}

_NARRATIVE_BY_TYPE = {
    "QUESTION": "问题切入", "CONTRAST": "对立展开", "RHETORICAL": "思辨推进",
    "DEFINITION": "三步递进", "NARRATIVE": "故事线",
}


def generate_angles(struct: dict, readiness: dict, balance: dict) -> list[dict]:
    """① 受众角度：类型基准 + 领域 + readiness/矛盾，去重后取 2-3 个。"""
    angles: list[dict] = []
    seen: set[str] = set()
    base = _ANGLE_BY_TYPE.get(struct["claim_type"], "验证向")
    angles.append({"angle": base, "audience": "泛科技/科普受众",
                   "rationale": f"claim_type={struct['claim_type']}"})
    seen.add(base)
    for d in struct.get("domains", []):
        a = _DOMAIN_ANGLE.get(d)
        if a and a not in seen:
            angles.append({"angle": a, "audience": "垂直领域受众", "rationale": f"领域 {d}"})
            seen.add(a)
            break
    if balance.get("contradiction") or struct.get("flags", {}).get("negation"):
        if "争议拆解" not in seen:
            angles.append({"angle": "争议拆解", "audience": "关心争议/辟谣的受众",
                           "rationale": "存在否定/矛盾信号"})
            seen.add("争议拆解")
    elif readiness.get("grade") != "ready":
        if "开放探索" not in seen:
            angles.append({"angle": "开放探索", "audience": "对结论持开放态度的受众",
                           "rationale": f"readiness={readiness.get('grade')}"})
            seen.add("开放探索")
    if len(angles) < 2 and struct.get("entities"):
        if "案例拆解" not in seen:
            angles.append({"angle": "案例拆解", "audience": "喜欢具象案例的受众",
                           "rationale": "以实体为锚点展开"})
    return angles[:3]


def plan_narrative(struct: dict, readiness: dict) -> dict:
    """② 叙事方向规划。"""
    ct = struct["claim_type"]
    if ct in _NARRATIVE_BY_TYPE:
        return {"direction": _NARRATIVE_BY_TYPE[ct], "rationale": f"claim_type={ct}"}
    if readiness.get("decision_confidence") == "high":
        return {"direction": "结论前置", "rationale": "高置信度，先抛结论再论证"}
    if struct.get("sub_claims") and len(struct["sub_claims"]) > 1:
        return {"direction": "分点推进", "rationale": f"多子命题（{len(struct['sub_claims'])} 段）"}
    return {"direction": "问题切入", "rationale": "默认以问题引发好奇"}


def plan_hcq(struct: dict, balance: dict) -> dict:
    """③ Hook / Conflict / Question 结构。"""
    entities = struct.get("entities", [])
    nums = struct.get("numbers_years", [])
    quals = struct.get("qualifiers", [])
    entity = entities[0] if entities else "这个命题"
    number = nums[0] if nums else None

    if balance.get("contradiction") or struct.get("flags", {}).get("negation"):
        conflict = f"常识认知 vs 该命题的否定/矛盾信号"
    elif quals and any(q in {"最大", "第一", "首次", "唯一"} for q in quals):
        conflict = f"「{entity}」被贴上「{quals[0]}」标签，是否名副其实"
    else:
        conflict = f"「{entity}」这个说法，与你以为的并不一样"

    if number:
        hook = f"先看一个数字：{number}"
    elif quals and any(q in _SUPERLATIVE for q in quals):
        sup = next(q for q in quals if q in _SUPERLATIVE)
        hook = f"{sup}的{entity}，凭什么？"
    elif struct.get("claim_type") == "QUESTION":
        hook = f"{entity}，今天到底走到哪一步了？"
    else:
        hook = f"先从{entity}说起。"

    # v2：有信息价值的提问（聚焦成熟度，而非"改变你的判断"式机械反问）
    question = f"{entity}，离真正的 JARVIS 还差什么？"
    return {"hook": hook, "conflict": conflict, "question": question}


def platform_plans(angles: list[dict], narrative: dict, hcq: dict) -> dict:
    """④ 平台适配规划。"""
    out = {}
    for name, cfg in _PLATFORMS.items():
        out[name] = {
            "duration_style": f"{cfg['时长']} / {cfg['风格']}",
            "hook_strategy": cfg["钩子"],
            "interaction": cfg["互动"],
            "lead_angle": angles[0]["angle"],
            "narrative": narrative["direction"],
        }
    return out


def build_content_plan(brief: dict) -> dict:
    """Research Brief → Content Plan（引用 brief 的证据与缺口，不生成脚本）。"""
    struct = brief["structure"]
    readiness = brief["readiness"]
    balance = brief["balance"]
    angles = generate_angles(struct, readiness, balance)
    narrative = plan_narrative(struct, readiness)
    hcq = plan_hcq(struct, balance)
    platforms = platform_plans(angles, narrative, hcq)

    citations = []
    for e in brief.get("evidence", []):
        citations.append({"url": e.get("url", ""), "title": e.get("title", ""),
                          "source_tier": e.get("source_tier")})
    gaps = brief.get("gaps", [])

    return {
        "claim": struct.get("claim_text", ""),
        "angles": angles,
        "narrative_direction": narrative,
        "structure": hcq,
        "platform_plans": platforms,
        "brief_citations": {"sources": citations, "gaps": gaps,
                            "cited_source_count": len(citations),
                            "cited_gap_count": len(gaps)},
        "plan_text": _render_plan(struct, angles, narrative, hcq, platforms, citations, gaps),
    }


def _render_plan(struct, angles, narrative, hcq, platforms, citations, gaps) -> str:
    lines = [f"【内容规划】{struct.get('claim_text', '')}",
             f"受众角度：{' / '.join(a['angle'] for a in angles)}",
             f"叙事方向：{narrative['direction']}（{narrative['rationale']}）",
             f"Hook：{hcq['hook']}",
             f"Conflict：{hcq['conflict']}",
             f"Question：{hcq['question']}",
             "平台适配："]
    for name, p in platforms.items():
        lines.append(f"- {name}: {p['duration_style']} | 钩子={p['hook_strategy']} | {p['interaction']}")
    lines.append(f"引用来源 {len(citations)} 条；未覆盖元素 {len(gaps)} 个（需补调研）")
    return "\n".join(lines)
