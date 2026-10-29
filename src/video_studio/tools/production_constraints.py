"""V2.1 Stage 8Q：Final Calibration（Production Constraint Layer 最终版）。

- 8Q 设计：cost_base 口径校验 + complexity 收窄[1.0,1.4] + lifecycle 求解冻结 +
  Adaptive Constraint Policy（密度带自适应 / fact 拆分 / 数据表达扩展 / 素材分档）。
- 不修改 visual_planning.py / Truth / Evidence Layer；不新增 Agent；不接视频/素材库/TTS/发布。
"""

from __future__ import annotations

COST_BY_VISUAL = {
    "口播 + 大字标题卡": 8, "口播 + 全屏数字卡": 8, "快切素材 + 大字标题卡": 22,
    "结论大字卡": 6, "结论大字卡 + 落版": 6,
    "结论口播 + 关键数字卡": 12, "结论口播 + 呼应画面": 15,
    "事实核查字幕卡": 12, "来源截图 + 引注": 12, "核查清单卡": 12,
    "待补提示卡（黄底警示）": 4, "转场字幕卡": 4,
    "数据可视化 + 证据截图": 45, "概念动画 + 口播": 90, "实拍素材 + 数据角标": 30,
}
REF_BAND = {
    "口播 + 大字标题卡": (5, 10), "口播 + 全屏数字卡": (5, 10),
    "快切素材 + 大字标题卡": (15, 30),
    "结论大字卡": (5, 8), "结论大字卡 + 落版": (5, 8),
    "结论口播 + 关键数字卡": (8, 15), "结论口播 + 呼应画面": (10, 20),
    "事实核查字幕卡": (10, 15), "来源截图 + 引注": (10, 15), "核查清单卡": (10, 15),
    "待补提示卡（黄底警示）": (3, 5), "转场字幕卡": (3, 5),
    "数据可视化 + 证据截图": (30, 60), "概念动画 + 口播": (60, 120),
    "实拍素材 + 数据角标": (20, 40),
}
# 8Q 求解冻结的生命周期开销（见 STAGE_8Q_DESIGN.md §B3；由 VIDEO-10/15 参照求解）
# 个人 1.05 / 小团队 0.26 为求解有效值；专业媒体求解为负值（-0.21，见 8Q 报告），置 0.0 下界仍超带。
LIFECYCLE_OVERHEAD = {"个人创作者": 1.05, "小团队": 0.26, "专业媒体": 0.0}
STD_BAND_H_PER_MIN = {"个人创作者": (2.5, 4.0), "小团队": (1.5, 2.5), "专业媒体": (1.0, 1.5)}

DIFFICULTY = {
    "口播 + 大字标题卡": "高", "口播 + 全屏数字卡": "高",
    "结论大字卡": "高", "结论大字卡 + 落版": "高", "结论口播 + 关键数字卡": "高",
    "事实核查字幕卡": "高", "来源截图 + 引注": "中", "核查清单卡": "高",
    "待补提示卡（黄底警示）": "高", "转场字幕卡": "高",
    "数据可视化 + 证据截图": "中", "概念动画 + 口播": "中", "实拍素材 + 数据角标": "困难",
    "快切素材 + 大字标题卡": "困难", "结论口播 + 呼应画面": "中",
}
FALLBACK = {
    "快切素材 + 大字标题卡": "口播 + 大字标题卡",
    "实拍素材 + 数据角标": "数据可视化 + 证据截图",
    "概念动画 + 口播": "数据可视化 + 证据截图",
    "结论口播 + 呼应画面": "结论大字卡 + 落版",
}
HARD_BUDGET = 0.15          # 困难（硬）
SOFT_MIDHARD_BUDGET = 0.45  # 中+困难（软，报告不 FAIL）
# 数据表达范围（8Q 扩展：含事实核查/来源截图/核查清单卡）
DATA_EXPRESSION_VISUALS = ("数据可视化 + 证据截图", "口播 + 全屏数字卡",
                           "事实核查字幕卡", "来源截图 + 引注", "核查清单卡")
MAX_FACTS_PER_SCENE = 4


def complexity_factor(scene: dict) -> float:
    """8Q 收窄：clamp(1 + 0.08×字幕重点 + 0.003×文本长, 1.0, 1.4)。"""
    c = 1 + 0.08 * len(scene.get("subtitle_emphasis", [])) + 0.003 * len(scene.get("script_text", ""))
    return max(1.0, min(1.4, c))


def density_band(num_count: int) -> tuple[float, float]:
    """C1 密度带自适应：按 claim 数字数。"""
    if num_count == 0:
        return (0.5, 4.0)
    if 1 <= num_count <= 3:
        return (1.0, 5.0)
    return (2.0, 8.0)


def check_cost_base(scenes: list[dict]) -> dict:
    """B1 口径修正：cost_base ∈ 8O 参考带（应 100%）。"""
    n = len(scenes) or 1
    hits = sum(1 for s in scenes
               if s["visual_target"] in REF_BAND
               and REF_BAND[s["visual_target"]][0] <= s.get("cost_base", COST_BY_VISUAL.get(s["visual_target"], 8))
               <= REF_BAND[s["visual_target"]][1])
    return {"cost_base_hits": f"{hits}/{n}", "cost_base_hit_rate": hits / n}


def split_dense_facts(scenes: list[dict], struct: dict) -> list[dict]:
    """C2 fact 密度拆分：单 fact scene fact>4 或密度超带上限时拆为 2 镜。"""
    band = density_band(len(struct.get("numbers_years", [])))
    out: list[dict] = []
    for s in scenes:
        facts = s.get("fact_refs", [])
        density = len(s.get("subtitle_emphasis", []))
        if s["role"] == "fact" and facts and (len(facts) > MAX_FACTS_PER_SCENE or density > band[1]):
            half = (len(facts) + 1) // 2
            for part in (facts[:half], facts[half:]):
                out.append({**s, "fact_refs": part,
                            "subtitle_emphasis": sorted({t for t in s["subtitle_emphasis"]
                                                         if any(t in f["fact"] for f in part)}),
                            "fact_split": True})
        else:
            out.append(s)
    for i, s in enumerate(out, 1):
        s["scene_id"] = f"S{i:02d}"
    return out


def calibrate_cost(scenes: list[dict]) -> dict:
    content_min = 0.0
    for s in scenes:
        base = COST_BY_VISUAL.get(s["visual_target"], 8)
        cplx = complexity_factor(s)
        s["cost_base"] = base
        s["complexity_factor"] = round(cplx, 3)
        s["cost_est"] = round(base * cplx, 1)
        content_min += s["cost_est"]
    per_standard = {}
    for std, lo in LIFECYCLE_OVERHEAD.items():
        per_standard[std] = {"hours": round(content_min / 60 * (1 + lo), 2), "overhead": lo}
    return {"content_min": round(content_min, 1), "per_standard": per_standard}


def info_visual_balance(scenes: list[dict], struct: dict) -> dict:
    claim_nums = struct.get("numbers_years", [])
    claim_ents = struct.get("entities", [])
    all_emph, data_emph = set(), set()
    for s in scenes:
        all_emph.update(s.get("subtitle_emphasis", []))
        if s["visual_target"] in DATA_EXPRESSION_VISUALS:
            data_emph.update(s.get("subtitle_emphasis", []))
    nums_cov = [n for n in claim_nums if n in all_emph]
    ents_cov = [e for e in claim_ents if e in all_emph]
    data_nums = [n for n in claim_nums if n in data_emph]
    counts = [len(s.get("subtitle_emphasis", [])) for s in scenes]
    n = len(scenes) or 1
    band = density_band(len(claim_nums))
    return {
        "claim_covered": {"numbers": f"{len(nums_cov)}/{len(claim_nums)}",
                          "entities": f"{len(ents_cov)}/{len(claim_ents)}"},
        "data_coverage": round(len(data_nums) / len(claim_nums), 3) if claim_nums else 1.0,
        "avg_density": round(sum(counts) / n, 3),
        "density_band": band,
        "zero_density_ratio": round(sum(1 for c in counts if c == 0) / n, 3),
    }


def apply_material_constraints(scenes: list[dict]) -> dict:
    for s in scenes:
        s["difficulty"] = DIFFICULTY.get(s["visual_target"], "高")
        s["fallback_applied"] = False
    n = len(scenes) or 1
    hard_limit = int(n * HARD_BUDGET)
    before_ev = [set(s.get("evidence_refs", [])) for s in scenes]
    hard_count = sum(1 for s in scenes if s["difficulty"] == "困难")
    applied = []
    for s in scenes:
        if s["difficulty"] == "困难" and hard_count > hard_limit:
            fb = FALLBACK.get(s["visual_target"])
            if fb:
                s["visual_target_original"] = s["visual_target"]
                s["visual_target"] = fb
                s["difficulty"] = DIFFICULTY.get(fb, "高")
                s["fallback_applied"] = True
                applied.append({"scene_id": s["scene_id"], "from": s["visual_target_original"], "to": fb})
                hard_count -= 1
    after_ev = [set(s.get("evidence_refs", [])) for s in scenes]
    hard = sum(1 for s in scenes if s["difficulty"] == "困难")
    midhard = sum(1 for s in scenes if s["difficulty"] in ("中", "困难"))
    return {"hard_ratio": round(hard / n, 3), "midhard_ratio": round(midhard / n, 3),
            "applied_fallback": applied, "zero_drift": all(a == b for a, b in zip(before_ev, after_ev)),
            "difficulty_annotated": all("difficulty" in s for s in scenes)}


def calibrate(plan: dict, struct: dict) -> dict:
    scenes = split_dense_facts(plan["scenes"], struct)
    cost = calibrate_cost(scenes)
    balance = info_visual_balance(scenes, struct)
    material = apply_material_constraints(scenes)
    base_check = check_cost_base(scenes)
    return {"scenes": scenes, "references": plan.get("references", []),
            "cost": cost, "balance": balance, "material": material, "cost_base_check": base_check}
