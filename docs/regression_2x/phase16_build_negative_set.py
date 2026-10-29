# -*- coding: utf-8 -*-
"""P16-1 负例过滤器评测集构建（冻结，sha256 钉定）。

组成（授权书 §2）：
  · 负例 ≥20 条 = 3 条现有人工负例 + 已知陷阱（PICO/鲨鱼等）+ 构造负例（跨景配对）
  · 误杀测试集 = 现有 24 条人工正例

**构造负例的合理性边界（如实登记）**：
  取「人工为 A 景**选定/接受**的素材」配给「B 景需求」，provenance = 本段构造规则。
  · 这是**构造标签**，不是人工判定 —— 本报告将人工负例与构造负例**分开统计**，不混为一谈。
  · 为避免盲目随机配对引入假负例（两景话题相近时该素材可能对 B 景也切题），
    构造规则限定为**跨话题族**配对（数学/打印证明 ↔ 数学竞赛合影 / 代码界面 / 天文等），
    并逐条给出配对理由与人工原始选定理由。
  · 真实性来源：素材对 A 景的需求确为人工正例（有 provenance）；跨族到 B 景即为构造的负例。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
FIX = R / "tests" / "fixtures"
sys.stdout.reconfigure(encoding="utf-8")

GATE = {
    "min_negative_capture_rate": 0.60,
    "max_false_kill_rate": 0.05,
    "max_false_kill_count": 1,
    "note": "P16-1 达标线**运行前写死**（授权书 §2）；运行后不得调整",
}

truth = json.loads((FIX / "vlm_relevance_truth_v1.json").read_text(encoding="utf-8"))
pairs = truth["pairs"]
by_key = {(p["scene_id"], p["asset_key12"]): p for p in pairs}

positives = [p for p in pairs if p["human_label"] == "RELEVANT"]
human_negs = [p for p in pairs if p["human_label"] == "IRRELEVANT"]

# ---------------- 全局查表：需求（21 景）+ 素材（含扩展索引）----------------
# 陷阱/跨景负例需要「任意 (景, 素材)」组合，而真值集只含 27 条已标注对 ⇒ 需另建查表。
REQ: dict[str, dict] = {}
for p in pairs:
    sid = p["scene_id"]
    if sid not in REQ and p.get("requirement_snapshot"):
        REQ[sid] = p["requirement_snapshot"]
ASSET: dict[str, dict] = {}
for p in pairs:
    ak = p["asset_key12"]
    ASSET.setdefault(ak, {"asset_key12": ak, "image_path": p["image_path"],
                          "asset_id": p.get("asset_id"),
                          "asset_sha256": p.get("asset_sha256")})
# 补全 21 景需求（真值集未覆盖的景从 visual_requirements + 脚本旁白回填，
# 与 P14-2 构建真值集时同一来源、同一渲染逻辑）
if len(REQ) < 21:
    vrq = json.loads((L / "visual_requirements.json").read_text(encoding="utf-8"))
    ds = R / "output" / "phase13e_script_sandbox" / "script_dcv2_derived_v1.json"
    narr = {}
    if ds.is_file():
        d = json.loads(ds.read_text(encoding="utf-8"))
        narr = {s.get("scene_id"): (s.get("narration") or "") for s in (d.get("segments") or [])}
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_vd", R / "src" / "video_studio" / "tools" / "vlm_judge.py")
    _vd = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(R / "src"))
    spec.loader.exec_module(_vd)
    for r in vrq["requirements"]:
        sid = r["scene_id"]
        if sid in REQ:
            continue
        snap = {k: r.get(k) for k in ("scene_id", "visual_goal", "subject", "action", "object",
                                      "environment", "concept", "concepts_pos", "concepts_neg",
                                      "avoid_list", "expected_kind", "evidence_type", "status")}
        snap["narration"] = narr.get(sid) or ""
        REQ[sid] = snap
# 补全素材路径：从 asset_index.json 全量 8 个 + 真值集扩展素材
ai = json.loads((L / "asset_index.json").read_text(encoding="utf-8"))
for c in ai["candidates"]:
    ak = c["sha256"][:12]
    ASSET.setdefault(ak, {"asset_key12": ak, "image_path": c["path"].replace("\\", "/"),
                          "asset_id": c["asset_id"], "asset_sha256": c["sha256"]})

print("查表规模 —— 需求 {} 景 | 素材 {} 个".format(len(REQ), len(ASSET)))

# ---------------- 负例（人工）----------------
negatives = []
for p in human_negs:
    negatives.append({
        "neg_id": "H-" + p["pair_id"], "kind": "HUMAN",
        "scene_id": p["scene_id"], "asset_key12": p["asset_key12"],
        "requirement_snapshot": p["requirement_snapshot"], "image_path": p["image_path"],
        "known_label": "IRRELEVANT",
        "why": "人工明确否决（原真值集负例）",
        "provenance": p["provenance"],
    })

# ---------------- 负例（已知陷阱：把素材配给"话题族不同"的景）----------------
# 陷阱 A：鲨鱼照类"词法陷阱"在既有 P7 审计中被点名；本片无鲨鱼素材，
# 故用等价的"跨话题族"陷阱替换（并在报告中登记该现实差异）。
# 陷阱 B：PICO/VR 头显类（另一项目谱系）；本片同样无此素材 ⇒ 记为"素材缺失，未构造"。
TRAPS = [
    # (scene_id, asset_key12, why)
    ("S01", "be956d321050", "陷阱：开场要『证明不被读懂』的抽象/人物钩子，配『球体密堆积』几何图"),
    ("S02", "1e9d2ab4e64e", "陷阱：预告要打印证明堆叠/四色锚点，配 Lean 代码编辑界面"),
    ("S03", "65377b888b77", "陷阱：讲 1977 机器证明与『空椅子』，配 1912 年逻辑学排版页"),
    ("S06", "96a8c4dc359f", "陷阱：讲 1980 年哲学家回应与确认机制，配 Lean tactic 状态截图"),
    ("S08", "0c365d5195d5", "陷阱：开普勒球堆问题，配数学竞赛团队合影"),
    ("S11", "af59386ae68c", "陷阱：Lean/mathlib 形式化，配四色定理纪念邮资戳"),
    ("S13", "92ca33138ffe", "陷阱：AI 成为数学参与者，配 1912 年 Principia 排版页"),
    ("S16", "be956d321050", "陷阱：『IMO 银牌』表述辨析，配球体密堆积几何图"),
    ("S19", "1e9d2ab4e64e", "陷阱：Tymoczko 之问（证明的承认与理解），配 Lean 代码界面"),
    ("S21", "96a8c4dc359f", "陷阱：结语回查清单，配 Lean tactic 状态截图"),
]
def resolve(sid: str, ak: str):
    """返回 (requirement_snapshot, image_path)；任一缺失返回 None。"""
    req, a = REQ.get(sid), ASSET.get(ak)
    if not req or not a or not pathlib.Path(a["image_path"]).is_file():
        return None
    return req, a["image_path"]


for sid, ak, why in TRAPS:
    r = resolve(sid, ak)
    if r is None:
        print("!! 陷阱跳过（需求或素材未解析）:", sid, ak)
        continue
    req, img = r
    negatives.append({
        "neg_id": "T-{}-{}".format(sid, ak), "kind": "KNOWN_TRAP",
        "scene_id": sid, "asset_key12": ak,
        "requirement_snapshot": req,
        "image_path": img, "known_label": "IRRELEVANT",
        "why": why,
        "provenance": {"source": "P16-1 构造规则（已知陷阱：跨话题族配对）",
                       "rule": "把该素材配给话题族不同的镜头需求；素材本身真实存在",
                       "note": "**构造标签**，非人工判定"},
    })

# ---------------- 负例（跨景配对：把 A 景人工选定素材配给 B 景）----------------
# 严格"跨话题族"：素材在 A 景的人工理由明确指向 A 景特有内容（人名/年份/物件），
# 配到 B 景（话题族不同）即构成构造负例。
CROSS = [
    ("S05", "65377b888b77", "Russell 1912 排版页（人工为 S05 选定）配给 S05 之外的景"),
    ("S05", "1e9d2ab4e64e", "Lean 代码界面（人工为 S11 选定）配给 S05 佩戴/眼镜语境"),
]
# 上面第 2 条已在 TRAPS 里覆盖 S11 方向；这里按"目标景 ≠ 原景"生成 8 条跨景对
CROSS_RULE = [
    # (target_scene, source_scene_of_asset, asset_key12, why)
    ("S06", "S05", "65377b888b77", "Russell 排版页原为 S05（可检视性之争）选定；S06 讲 1980 年哲学回应"),
    ("S07", "S11", "1e9d2ab4e64e", "Lean 界面原为 S11 选定；S07 讲两种立场对照的四色定理案例"),
    ("S09", "S02", "6c3fc5af91ed", "四色着色图原为 S02/S03 选定；S09 讲 Hales 审稿与 99% 确定（球堆）"),
    ("S10", "S04", "af59386ae68c", "四色纪念邮资戳原为 S04 选定；S10 讲形式化验证导语"),
    ("S12", "S01", "0c365d5195d5", "IMO 队照原为 S01/S13–S16 选定；S12 讲 Liquid Tensor 形式化工程"),
    ("S14", "S05", "65377b888b77", "Russell 排版页原为 S05 选定；S14 讲 AlphaGeometry/Nature 奥赛级几何"),
    ("S17", "S11", "96a8c4dc359f", "Lean tactic 截图原为 S11 选定；S17 讲回到核心问题的过渡"),
    ("S20", "S08", "be956d321050", "球体密堆积原为 S08–S10 选定；S20 讲意义来源讨论"),
]
for sid, src_scene, ak, why in CROSS_RULE:
    r = resolve(sid, ak)
    if r is None:
        print("!! 跨景对跳过（需求或素材未解析）:", sid, ak)
        continue
    req, img = r
    origin = by_key.get((src_scene, ak))
    negatives.append({
        "neg_id": "C-{}-{}-from-{}".format(sid, ak, src_scene), "kind": "CONSTRUCTED_CROSSSCENE",
        "scene_id": sid, "asset_key12": ak,
        "requirement_snapshot": req,
        "image_path": img, "known_label": "IRRELEVANT",
        "why": why,
        "provenance": {
            "source": "P16-1 构造规则：跨景配对（cross-scene pairing）",
            "rule": ("取人工为 {} 景选定/接受的素材，配给 {} 景的需求；"
                     "限定跨话题族以避免假负例").format(src_scene, sid),
            "asset_positive_origin": (origin or {}).get("human_reason"),
            "constructor_note": "**构造标签**（非人工判定）；人工负例与构造负例分开统计",
        },
    })

# ---------------- 去重（同 (scene, asset) 只留一条，人工优先）----------------
seen, final_negs = set(), []
for n in sorted(negatives, key=lambda x: (x["kind"] != "HUMAN", x["neg_id"])):
    k = (n["scene_id"], n["asset_key12"])
    if k in seen:
        continue
    seen.add(k)
    final_negs.append(n)

# 负例不得与正例冲突（同 (scene,asset) 不能既是正例又是负例）
pos_keys = {(p["scene_id"], p["asset_key12"]) for p in positives}
conflict = [n["neg_id"] for n in final_negs if (n["scene_id"], n["asset_key12"]) in pos_keys]
if conflict:
    print("!! 与正例冲突，剔除:", conflict)
    final_negs = [n for n in final_negs
                  if (n["scene_id"], n["asset_key12"]) not in pos_keys]

doc = {
    "schema": "p16-negative-filter-eval-v1",
    "version": 1,
    "purpose": "P16-1 负例过滤器验证（VLM 仅作负例过滤器；KNOWN_ISSUES #73）",
    "filter_rule": {
        "deny_label": "IRRELEVANT",
        "pass_labels": ["RELEVANT", "PARTIAL", "NOT_ASSESSABLE"],
        "prompt_version": "vlm-relevance-judge-v2 (main)",
        "note": ("过滤器只信『拒签』：机器 IRRELEVANT ⇒ DENY（出局+理由）；"
                 "其余一律进人工短名单（不因机器 RELEVANT 放行任何绑定）"),
    },
    "gate_frozen_before_run": GATE,
    "negatives": final_negs,
    "positives": [{
        "pos_id": p["pair_id"], "scene_id": p["scene_id"], "asset_key12": p["asset_key12"],
        "requirement_snapshot": p["requirement_snapshot"], "image_path": p["image_path"],
        "known_label": "RELEVANT", "human_reason": p["human_reason"],
        "provenance": p["provenance"],
    } for p in positives],
    "counts": {
        "negatives_total": len(final_negs),
        "negatives_human": sum(1 for n in final_negs if n["kind"] == "HUMAN"),
        "negatives_known_trap": sum(1 for n in final_negs if n["kind"] == "KNOWN_TRAP"),
        "negatives_constructed": sum(1 for n in final_negs
                                     if n["kind"] == "CONSTRUCTED_CROSSSCENE"),
        "positives_total": len(positives),
    },
    "meets_min_negatives": len(final_negs) >= 20,
    "reality_conflicts": [
        "授权书举例『PICO/鲨鱼陷阱』来自另一项目谱系（VR/鲨鱼素材）；**本片素材池无该类素材**，"
        "故以等价的『跨话题族』陷阱替代，并在此如实登记（未伪造 PICO/鲨鱼对）。",
    ],
    "truth_set_reference": {
        "file": "tests/fixtures/vlm_relevance_truth_v1.json",
        "sha256": truth["_sha256"] if "_sha256" in truth else None,
        "usage": "**只读引用**（正例来自其 24 条 RELEVANT；人工负例来自其 3 条 IRRELEVANT）",
    },
}
FIX.mkdir(parents=True, exist_ok=True)
out = FIX / "p16_negative_filter_eval_v1.json"
raw = json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=True)
out.write_text(raw, encoding="utf-8")
h = hashlib.sha256(raw.encode("utf-8")).hexdigest()

print("=" * 78)
print("P16-1 评测集已冻结")
print("=" * 78)
print("  文件:", out.relative_to(R).as_posix())
print("  sha256:", h)
print("  计数:", json.dumps(doc["counts"], ensure_ascii=False))
print("  ≥20 负例:", doc["meets_min_negatives"])
print()
print("  负例明细:")
for n in final_negs:
    print("   [{:22s}] {} {} | {}".format(n["kind"], n["scene_id"], n["asset_key12"],
                                          n["why"][:56]))
print()
print("  正例（误杀测试集）:", len(doc["positives"]), "条")
