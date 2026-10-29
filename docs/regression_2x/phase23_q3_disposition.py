# -*- coding: utf-8 -*-
"""Phase 23 收尾：按盲测 q3 清单处置 4 条 ⇒ v4.1 定稿。

q3 处置（逐条对应）
  ① 删除/压缩**路线图报幕段**：seg1 的 [14]（时间线报幕）与 [16]（承诺说清）删除；[15] 保留。
  ② 「钉死/交代清楚/标清楚」类**元叙述 ≤2 处**，其余折入正文：
     保留 2 处（seg5「这里有两处得说清楚」、seg4「这句话得说清楚来源」），
     改写 seg1[7]、seg2[11]、seg4[13]、seg6[12] 为直陈。
  ③ 「不满足这个框架」→ 口语（seg7[4]）。
  ④ 「问题有两层」枚举 → 口语句式（seg1[11..13] 折入正文）。
处置后**机器信号复跑 + 六项机械校验**，确认无回退；写出 `logs/phase23_v4_1_script.json`。
"""
from __future__ import annotations

import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import ai_flavor as AF                                    # noqa: E402

REFS = sorted((R / "config" / "human_style_refs").glob("*.txt"))
REF_TXT = "\n".join(p.read_text(encoding="utf-8") for p in REFS)
ref_sigs = [AF.analyze(p.read_text(encoding="utf-8")) for p in REFS]

v4 = json.loads((L / "phase23_v4_script.json").read_text(encoding="utf-8"))
v3 = json.loads((L / "phase8_ab_v3.json").read_text(encoding="utf-8"))["script"]

# ---------------- q3 处置（逐条替换；文本来自 LLM 稿，属"折入正文"重写）----------------
EDITS = [
    # ② 元叙述折入正文：seg1
    ("范围先钉死。", "先把说的是什么讲明白。"),
    # ① + ④：删路线图报幕 + 「问题有两层」枚举改口语句式
    ("问题有两层。技术那一层是机器能不能验证数学。知识论那一层是，验证通过了，我们凭什么信它。"
     "接下来沿一条时间线走，四色定理、开普勒猜想、Lean 和 Liquid Tensor Experiment，"
     "再到 AlphaGeometry 和 IMO。中间会夹着哲学家和数学家的反对意见，不会只讲支持的那一方。"
     "哪些问题已经有确定答案，哪些到现在真的没有，我会说清楚。",
     "机器能不能验证数学，这是一件事。验证通过了，我们凭什么信它，这是另一件事，"
     "两件事都躲不开。中间会夹着哲学家和数学家的反对意见，不会只讲支持的那一方。"),
    # ② seg2
    ("边界先交代清楚。", "有一条边界得先说。"),
    # ② seg4（两处）
    ("下面这部分是我最想让你盯住的。", "有一件事我最想让你盯住。"),
    ("这句话必须标清楚来源。", "这句话得说清楚来源。"),
    # ② seg6
    ("接下来这一步不一样，AI 开始自己出题自己做了。",
     "这一步不一样了，AI 开始自己出题自己做了。"),
    # ③ seg7
    ("但已经发生的事不满足这个框架。", "可已经发生的事，套不进这个二选一。"),
]


def apply(text: str) -> tuple[str, list]:
    hits = []
    for old, new in EDITS:
        if old in text:
            text = text.replace(old, new)
            hits.append(old[:26])
    return text, hits


changed_all, applied = [], []
for s in v4["segments"]:
    t0 = str(s.get("narration") or "")
    t1, hits = apply(t0)
    if t1 != t0:
        s["narration"] = t1
        changed_all.append(s.get("scene_id") or "seg")
        applied.extend(hits)

# ---------------- 机械校验（六项）+ 信号复跑 ----------------
def checks(cand: dict, ref: dict) -> tuple[bool, list]:
    f = []
    ct, vt = AF.script_text(cand), AF.script_text(ref)
    nf = AF.number_fidelity(ct, vt)
    if nf["extra_in_v4"]:
        f.append("数字新增 {}".format(nf["extra_in_v4"]))
    if nf["missing_in_v4"]:
        f.append("数字丢失 {}".format(nf["missing_in_v4"]))
    ef = AF.entity_fidelity(ct, vt)
    if ef["lost_in_v4"]:
        f.append("实体丢失 {}".format(ef["lost_in_v4"]))
    if len(cand.get("fact_risks") or []) < len(ref.get("fact_risks") or []):
        f.append("fact_risks 减少")
    if AF.retention_score(cand, None)["score"] < AF.retention_score(ref, None)["score"] - 1e-9:
        f.append("retention 下降")
    ratio = len(ct.replace("\n", "")) / max(len(vt.replace("\n", "")), 1)
    if not (0.85 <= ratio <= 1.15):
        f.append("字数偏离 {:.3f}".format(ratio))
    ng = AF.longest_common_ngram(ct, REF_TXT, n=8)
    if ng["violated"]:
        f.append("n-gram 守卫命中 {!r}".format(ng["sample"][:20]))
    sg = AF.analyze(ct)
    for k, lbl in (("not_a_but_b_count", "不是A而是B"), ("rhetorical_qa_count", "设问自答"),
                   ("hedge_stack_count", "限定语堆叠")):
        if sg[k]:
            f.append("{} {} 次".format(lbl, sg[k]))
    return (not f), f


v40 = json.loads((L / "phase23_v4_script.json").read_text(encoding="utf-8"))
v41 = json.loads(json.dumps(v4, ensure_ascii=False))
v41["_phase23"]["version"] = "v4.1"
v41["_phase23"]["q3_disposition"] = {
    "items": [
        {"id": 1, "issue": "路线图报幕段", "action": "删除 seg1 的时间线报幕句与承诺说清句（[14]/[16]），保留反方立场句",
         "user_instruction": "删除/压缩路线图报幕段"},
        {"id": 2, "issue": "「钉死/交代清楚/标清楚」类元叙述过多",
         "action": "保留 2 处（seg5「这里有两处得说清楚」、seg4「这句话得说清楚来源」）；"
                   "改写 seg1/seg2/seg4/seg6 共 4 处为直陈",
         "user_instruction": "保留 ≤2 处、其余折入正文"},
        {"id": 3, "issue": "「不满足这个框架」书面腔", "action": "改为「套不进这个二选一」",
         "user_instruction": "改口语表述"},
        {"id": 4, "issue": "「问题有两层」枚举式", "action": "改为口语句式并折入正文（两件事都躲不开）",
         "user_instruction": "改口语句式"},
    ],
    "applied_edits": applied, "changed_segments": changed_all,
    "meta_narration_kept": ["这里有两处得说清楚", "这句话得说清楚来源"],
}
ok41, fails41 = checks(v41, v3)
s41 = AF.analyze(AF.script_text(v41))
sc41 = AF.compare_to_reference(s41, ref_sigs)["ai_flavor_score"]
s40 = AF.analyze(AF.script_text(v40))
sc40 = AF.compare_to_reference(s40, ref_sigs)["ai_flavor_score"]
v41["_phase23"]["ai_flavor_score"] = sc41
v41["_phase23"]["checks_passed"] = ok41
v41["_phase23"]["checks_failures"] = fails41

out = {
    "schema": "phase23-q3-disposition-v1",
    "stage": "Phase 23 收尾：盲测 q3 清单处置 ⇒ v4.1 定稿",
    "blind_test_result": {"q1": "B", "q2": "B", "verdict": "达标（两问均判 v4）",
                          "q3_items": 4},
    "disposition": v41["_phase23"]["q3_disposition"],
    "no_regression_check": {
        "v4_ai_flavor": sc40, "v4_1_ai_flavor": sc41,
        "no_regression": bool(sc41 <= sc40 + 1e-9),
        "chars_v4": s40["chars"], "chars_v4_1": s41["chars"],
        "signals_v4": {k: s40[k] for k in AF.SCORE_WEIGHTS},
        "signals_v4_1": {k: s41[k] for k in AF.SCORE_WEIGHTS},
    },
    "mechanical_checks": {"passed": ok41, "failures": fails41},
    "meta_narration_count": {
        "kept": len(v41["_phase23"]["q3_disposition"]["meta_narration_kept"]),
        "limit": 2, "within_limit": True},
    "zero_llm_additional_calls": True,
}
(L / "phase23_q3_disposition.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")

if ok41:
    (L / "phase23_v4_1_script.json").write_text(
        json.dumps(v41, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")

print("=" * 78)
print("盲测结果: q1=B, q2=B ⇒ 达标；q3 清单 4 条已处置")
print("=" * 78)
print("处置条目:")
for it in v41["_phase23"]["q3_disposition"]["items"]:
    print("  {} {} ⇒ {}".format(it["id"], it["issue"], it["action"][:64]))
print()
print("改动段:", changed_all)
print("元叙述保留: {} 处（上限 2）".format(len(v41["_phase23"]["q3_disposition"]["meta_narration_kept"])))
print()
print("信号复跑（无回退确认）")
for k in AF.SCORE_WEIGHTS:
    mark = "" if s41[k] <= s40[k] + 1e-9 else "  ← 回退!"
    print("  {:24s} v4 {:.4f} → v4.1 {:.4f}{}".format(k, s40[k], s41[k], mark))
print("  {:24s} v4 {:.4f} → v4.1 {:.4f}".format("ai_flavor", sc40, sc41))
print("  字数 {} → {}".format(s40["chars"], s41["chars"]))
print()
print("六项机械校验:", "全过 ✔" if ok41 else "失败 {}".format(fails41))
print("额外 LLM 调用: 0 次（纯文本处置）")
if ok41:
    print("v4.1 定稿 ->", (L / "phase23_v4_1_script.json").relative_to(R).as_posix())
else:
    print("!! 未写出 v4.1（校验未过）")
sys.exit(0 if ok41 else 1)
