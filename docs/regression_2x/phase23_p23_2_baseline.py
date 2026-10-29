# -*- coding: utf-8 -*-
"""P23-2 基线：对 v2/v3 稿 + 参照文本跑 AI 味信号（产出 logs/phase23_flavor_baseline.json）。"""
from __future__ import annotations

import json
import pathlib
import re
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import ai_flavor as AF                                    # noqa: E402


def arm_text(p: pathlib.Path) -> str:
    j = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(j.get("script"), dict):
        return AF.script_text(j["script"])
    if isinstance(j.get("segments"), list):
        return AF.script_text(j)
    return str(j.get("raw_text") or "")


cands = {
    "v2": L / "phase8_ab_v2.json",
    "v3": L / "phase8_ab_v3.json",
}
for extra in ("phase8_ab_v4.json",):
    if (L / extra).is_file():
        cands["v4"] = L / extra
refs = sorted((R / "config" / "human_style_refs").glob("*.txt"))
paths = {k: arm_text(p) for k, p in cands.items() if p.is_file()}
ref_txts = [p.read_text(encoding="utf-8") for p in refs]

rep = AF.baseline(paths, [str(p) for p in refs])
rep["arm_meta"] = {k: {"path": str(p.relative_to(R)).replace("\\", "/"),
                       "exists": p.is_file()} for k, p in cands.items()}
# reference 文本也给 n-gram 自查（对照之间允许重合，仅用于标定阈值）
rep["reference_pair_ngram"] = AF.longest_common_ngram(ref_txts[0], ref_txts[1], n=8) \
    if len(ref_txts) > 1 else None
p = L / "phase23_flavor_baseline.json"
p.write_text(json.dumps(rep, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")

print("=" * 96)
print("P23-2 AI 味信号基线（越低越人味；ai_flavor_score 为综合分）")
print("=" * 96)
keys = ("chars", "advance_marker_density", "not_a_but_b_rate", "rhetorical_qa_density",
        "sentence_len_cv", "colon_expand_rate", "dash_aside_rate", "hedge_stack_rate",
        "para_symmetry")
print("{:10s}".format("来源") + "".join("{:>12s}".format(k[:11]) for k in keys)
      + "{:>14s}".format("ai_flavor"))
refsig = rep["references"]["signals"]
print("{:10s}".format("参照均值")
      + "".join("{:>12}".format(round(sum(r[k] for r in refsig) / len(refsig), 4))
                for k in keys) + "{:>14}".format("—(基准)"))
for name, v in rep["arms"].items():
    sc = v["vs_ref"]["ai_flavor_score"]
    v["ai_flavor_score"] = sc
    print("{:10s}".format(name) + "".join("{:>12}".format(v[k]) for k in keys)
          + "{:>14}".format(sc))
rep["arms"] = {k: v for k, v in rep["arms"].items()}
p.write_text(json.dumps(rep, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
print()
for name, v in rep["arms"].items():
    d = v["vs_ref"]
    print("  {} vs 参照: ai_flavor 分 {:.4f} | 正向偏离 {}".format(
        name, d["ai_flavor_score"],
        {k: x for k, x in d["positive_deviation"].items() if x > 0}))
    print("       命中推进词: {}".format(v["advance_marker_hits"][:8]))
print()
print("目标 = v4 向参照靠拢且低于 v3 ⇒ **v3 基线 ai_flavor_score = {:.4f}**".format(
    rep["arms"].get("v3", {}).get("ai_flavor_score", -1)))
print("->", p.relative_to(R).as_posix())
