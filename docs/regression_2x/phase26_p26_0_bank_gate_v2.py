# -*- coding: utf-8 -*-
"""P26 §0 复检：用**正确期望素材**重做 bank 双门（上一版用错绑定 ⇒ 测试无效）。

背景：上一版把 Phase 20 的 `fixture.binding` 当作期望素材，但实测
`_frame_S10p1.png` 与 **Postal** 全图 corr = **0.9304**（该帧**就是** Postal），
说明 Phase 20 渲染时的实际素材 ≠ fixture 记录的绑定 ⇒ 上一版测试**期望值错误，结论无效**。

正确做法：从**帧本身**反推"该帧实际在屏的素材"（全图 corr argmax），
再对该素材做 bank 打分（正门），并对**其它**素材做 bank 打分（反门）。
这才是"同口径"的双门检验。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import corr_diagnostics as CD                            # noqa: E402
from video_studio.core.materials import gray48, frame_corr                       # noqa: E402

THRESH = 0.30
fx = json.loads((R / "output/phase20_p20_2_sandbox/fixture.json").read_text(encoding="utf-8"))
proj = R / "projects" / fx["sandbox_project_id"]
SRC = R / "projects" / "p_96efdc03e1aa"
POOL = {}
for d in (SRC / "media", SRC / "registered_materials", SRC / "acquired_materials"):
    if d.is_dir():
        for f in sorted(d.rglob("*")):
            if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
                POOL.setdefault(hashlib.sha256(f.read_bytes()).hexdigest(), f)

frames = sorted((proj / "artifacts").glob("_frame_*.png"))
print("=" * 92)
print("P26 §0 复检：正确期望素材下的 bank 双门（帧数 {}）".format(len(frames)))
print("=" * 92)

rows, pos_old, pos_new, pos_n = [], 0, 0, 0
neg_bad, neg_n = [], 0
pos_scores, neg_scores = [], []
for fp in frames:
    g = gray48(fp)
    full = {sha: round(float(frame_corr(g, gray48(p))), 4) for sha, p in POOL.items()}
    # 该帧**实际在屏**的素材 = 全图 argmax（并集：它至少明显像一个素材）
    actual_sha = max(full, key=lambda k: full[k])
    if full[actual_sha] < 0.50:
        continue                                    # 不像任何素材 ⇒ 跳过（无法确证在屏）
    pos_n += 1
    b_act = CD.bank_score(g, POOL[actual_sha], res=48)["corr"]
    pos_scores.append(b_act)
    pos_old += 1 if full[actual_sha] >= THRESH else 0
    pos_new += 1 if b_act >= THRESH else 0
    rows.append({"frame": fp.name, "actual_full": full[actual_sha],
                 "actual_bank": b_act,
                 "asset": POOL[actual_sha].name[:40]})
    for sha, p in POOL.items():
        if sha == actual_sha:
            continue
        neg_n += 1
        b = CD.bank_score(g, p, res=48)["corr"]
        neg_scores.append(b)
        if b >= THRESH and b >= b_act - 0.15:       # 误通过 = 无关素材过阈**且**逼近在屏素材
            neg_bad.append({"frame": fp.name, "other": p.name[:34], "bank": b,
                            "actual_bank": b_act})

print("正门（帧 vs **实际在屏**素材）：样本 {} | 全图口径通过 {}/{} = {:.1%} | "
      "**bank 口径通过 {}/{} = {:.1%}**".format(
          pos_n, pos_old, pos_n, pos_old / max(pos_n, 1), pos_new, pos_n,
          pos_new / max(pos_n, 1)))
print("  在屏素材 bank 分布: min {:.4f} 中位 {:.4f} max {:.4f}".format(
    min(pos_scores), sorted(pos_scores)[len(pos_scores) // 2], max(pos_scores)))
print()
print("反门（帧 vs 其它素材，bank 口径）：对数 {} | **误通过 {}**".format(neg_n, len(neg_bad)))
if neg_scores:
    print("  无关素材 bank 分布: min {:.4f} 中位 {:.4f} p95 {:.4f} max {:.4f}".format(
        min(neg_scores), sorted(neg_scores)[len(neg_scores) // 2],
        sorted(neg_scores)[int(len(neg_scores) * 0.95)], max(neg_scores)))
for b in sorted(neg_bad, key=lambda x: -x["bank"])[:5]:
    print("    {} vs {} bank={} (在屏 {})".format(b["frame"], b["other"], b["bank"],
                                                b["actual_bank"]))

# 判别力：在屏 vs 无关的分数间隔
sep = (sorted(pos_scores)[0] - sorted(neg_scores)[int(len(neg_scores) * 0.95)]) \
    if pos_scores and neg_scores else None
print()
print("判别间隔（在屏最低 − 无关 p95）: {}".format(
    "N/A" if sep is None else round(sep, 4)))
out = {
    "schema": "phase26-p26-0-bank-dual-gate-v2",
    "stage": "P26 §0 bank 双门**复检**（修正期望素材）",
    "correction_of": "phase26_p26_0_bank_dual_gate.json（上一版期望素材错误 ⇒ 结论无效）",
    "method": "期望素材 = 帧的全图 argmax（且 ≥0.50 才计入），保证\"实际在屏\"",
    "threshold": THRESH, "positive_samples": pos_n,
    "positive_pass_full": pos_old, "positive_pass_bank": pos_new,
    "positive_rate_bank": round(pos_new / max(pos_n, 1), 4),
    "in_screen_scores": {"min": min(pos_scores) if pos_scores else None,
                         "max": max(pos_scores) if pos_scores else None},
    "negative_pairs": neg_n, "negative_false_pass": len(neg_bad),
    "negative_scores": {"min": min(neg_scores) if neg_scores else None,
                        "p95": (sorted(neg_scores)[int(len(neg_scores) * 0.95)]
                                if neg_scores else None),
                        "max": max(neg_scores) if neg_scores else None},
    "separation": sep,
    "positive_gate_met": bool(pos_new == pos_n and pos_n > 0),
    "negative_gate_met": bool(len(neg_bad) == 0),
    "dual_gate_pass": bool(pos_new == pos_n and pos_n > 0 and not neg_bad),
    "rows": rows,
}
p = L / "phase26_p26_0_bank_dual_gate_v2.json"
p.write_text(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
print("双门: 正门 {} | 反门 {} ⇒ **{}**".format(
    "过" if out["positive_gate_met"] else "不过",
    "过" if out["negative_gate_met"] else "不过",
    "双门全过 ✔" if out["dual_gate_pass"] else "未全过 ✘"))
print("->", p.relative_to(R).as_posix())
