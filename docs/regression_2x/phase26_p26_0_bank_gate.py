# -*- coding: utf-8 -*-
"""P26 §0：**bank-derived 核验接入的双门验证**（Phase 22 要求）+ 误报消除实测。

正门：Phase 20 的 40 段派生段帧（父景素材确实在屏）在 bank 口径下 **100% 通过**
      —— 对照旧的"全图口径"（P20 实测 33/40 误报）。
反门：画面 vs **无关素材** 在 bank 口径下 **0 误通过**（与 P18-2 的 55 条构造负例口径一致）。
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
from video_studio.core.materials import frame_corr, gray48                      # noqa: E402

THRESH = 0.30
MARGIN = 0.15

# 素材池（sha256 → path）
SRC = R / "projects" / "p_96efdc03e1aa"
POOL = {}
for d in (SRC / "media", SRC / "registered_materials", SRC / "acquired_materials"):
    if d.is_dir():
        for f in sorted(d.rglob("*")):
            if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
                POOL.setdefault(hashlib.sha256(f.read_bytes()).hexdigest(), f)

# Phase 20 的 40 段帧（父景素材在屏；派生段窗口=局部裁切）
FIX = json.loads((R / "output/phase20_p20_2_sandbox/fixture.json")
                 .read_text(encoding="utf-8"))
proj = R / "projects" / FIX["sandbox_project_id"]
frames = sorted((proj / "artifacts").glob("_frame_*.png"))
bind = FIX.get("binding") or {}
parent_of = {}
for s in json.loads((R / "output/phase20_script_sandbox/script_dcv2_p20_40seg.json")
                    .read_text(encoding="utf-8"))["segments"]:
    parent_of[s["scene_id"]] = s["parent_scene_id"]

print("=" * 92)
print("P26 §0 bank-derived 核验：双门验证（正门=在屏须通过；反门=无关素材须 0 误通过）")
print("=" * 92)

# ---------- 正门：派生段帧 vs 其父景素材 ----------
rows, pass_old, pass_new, total = [], 0, 0, 0
for fp in frames:
    sid = fp.stem.replace("_frame_", "")
    parent = parent_of.get(sid)
    sha = (bind or {}).get(sid) or (bind or {}).get(parent)
    if not sha or sha not in POOL:
        continue
    ap = POOL[sha]
    g = gray48(fp)
    old = round(float(frame_corr(g, gray48(ap))), 4)          # 旧口径：帧 vs 素材全图
    bank = CD.bank_score(g, ap, res=48)["corr"]               # 新口径：子窗口 bank 最大
    total += 1
    pass_old += 1 if old >= THRESH else 0
    pass_new += 1 if bank >= THRESH else 0
    rows.append({"scene_id": sid, "parent": parent, "corr_full": old, "corr_bank": bank,
                 "pass_full": old >= THRESH, "pass_bank": bank >= THRESH})
print("正门（派生段帧 vs 父景素材，阈值 {}）：".format(THRESH))
print("  样本 {} | 旧口径(全图) 通过 {}/{} = {:.1%} | **bank 口径通过 {}/{} = {:.1%}**".format(
    total, pass_old, total, pass_old / max(total, 1), pass_new, total,
    pass_new / max(total, 1)))
print("  误报消除：{} → {}（{} 处）".format(total - pass_old, total - pass_new,
                                          pass_new - pass_old))
for r in rows:
    if r["pass_bank"] and not r["pass_full"]:
        print("    修复 {:<8s} full={:<7} → bank={}".format(r["scene_id"], r["corr_full"],
                                                          r["corr_bank"]))

# ---------- 反门：帧 vs 无关素材 ----------
neg_bad, neg_n = [], 0
for r in rows:
    sid = r["scene_id"]
    parent = r["parent"]
    sha = (bind or {}).get(sid) or (bind or {}).get(parent)
    fp = next(p for p in frames if p.stem == "_frame_{}".format(sid))
    g = gray48(fp)
    for osha, op in POOL.items():
        if osha == sha:
            continue
        neg_n += 1
        b = CD.bank_score(g, op, res=48)["corr"]
        if b >= THRESH:
            neg_bad.append({"scene_id": sid, "other": op.name[:34], "corr_bank": b})
print()
print("反门（帧 vs 无关素材，bank 口径）：")
print("  对数 {} | **误通过 {}** ⇒ {}".format(
    neg_n, len(neg_bad), "0 误通过 ✔" if not neg_bad else "有误通过 ✘"))
for b in sorted(neg_bad, key=lambda x: -x["corr_bank"])[:6]:
    print("    {} vs {} = {}".format(b["scene_id"], b["other"], b["corr_bank"]))

positive_pass = (pass_new == total and total > 0)
negative_pass = (len(neg_bad) == 0)
out = {
    "schema": "phase26-p26-0-bank-dual-gate-v1",
    "stage": "P26 §0 bank-derived 核验接入的双门验证",
    "threshold": THRESH, "argmax_margin": MARGIN, "resolution": 48,
    "positive_gate": {"samples": total, "pass_full_image": pass_old,
                      "pass_bank": pass_new,
                      "pass_rate_full": round(pass_old / max(total, 1), 4),
                      "pass_rate_bank": round(pass_new / max(total, 1), 4),
                      "false_failures_removed": pass_new - pass_old,
                      "required": "100% PASS", "met": bool(positive_pass)},
    "negative_gate": {"pairs": neg_n, "false_pass": len(neg_bad),
                      "required": "0 false pass", "met": bool(negative_pass),
                      "detail": neg_bad[:20]},
    "dual_gate_pass": bool(positive_pass and negative_pass),
    "wiring": ("agents/editing/agent.py::_verify_scene_frames 新增 `bank_derived` 门控"
               "（读取 config.tools.frame_match.bank_derived，**默认 false** ⇒ 关闭时行为与既有逐字节一致）："
               "期望素材改用 `corr_diagnostics.bank_score` 的子窗口最大 corr，"
               "对照上限取池内**其它**素材的最大全图 corr（避免自比恒等）。"),
    "rows": rows,
    "zero_llm": True, "zero_vlm": True, "zero_network": True,
}
p = L / "phase26_p26_0_bank_dual_gate.json"
p.write_text(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
print()
print("双门结论: 正门 {} | 反门 {} ⇒ **{}**".format(
    "过" if positive_pass else "不过", "过" if negative_pass else "不过",
    "双门全过 ✔" if out["dual_gate_pass"] else "未全过 ✘"))
print("->", p.relative_to(R).as_posix())
