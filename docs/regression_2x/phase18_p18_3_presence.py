# -*- coding: utf-8 -*-
"""P18-3 VLM 在屏核验层评测（条件触发：v3 双门未全过）。

**任务边界（与 KNOWN_ISSUES #73 无关）**：只判「帧中是否出现该素材的任何部分」，
即**视觉存在性**验证，**不判**"配不配/合不合适"。

评测集（冻结，运行前写死）：
  · 正例 = P17 五景帧包（人工目视真值：**在屏**），每景 10%/50%/90% 三帧
  · 负例 = **构造错配**（同帧 vs 池内其它素材），抽固定子集（确定性抽样）
达标线（运行前写死）：
  · 与人工目视一致 ≥90%
  · 构造负例上 **false-present = 0**
  · `uncertain` 一律按"**不在屏**"处理（fail-closed）
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
from video_studio.core.env import load_env                                     # noqa: E402
load_env(R / ".env")
from video_studio.tools import vlm_judge as V                                   # noqa: E402

PACK = R / "output" / "phase17_attr_pack"
SCENES = ("S02", "S06", "S07", "S08", "S13")
FRAME_TAGS = ("10", "50", "90")
BUDGET = 0.50
GATE = {
    "min_agreement": 0.90,
    "max_false_present": 0,
    "uncertain_treated_as": "absent（fail-closed）",
    "note": "P18-3 达标线**运行前写死**；运行后不得调整",
}
# 负例抽样：确定性（每景取池内"最能骗过度量"的 2 个：bank48 最高分者）
NEG_PER_FRAME = 2

SRC = R / "projects" / "p_96efdc03e1aa"
POOL = {}
for d in (SRC / "media", SRC / "registered_materials", SRC / "acquired_materials"):
    if d.is_dir():
        for f in sorted(d.rglob("*")):
            if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
                POOL.setdefault(hashlib.sha256(f.read_bytes()).hexdigest(), f)

cfg, src = V.resolve_config(json.loads((R / "config" / "config.json").read_text(encoding="utf-8")),
                            root=R)
ok, why = V.available(cfg)
print("provider:", cfg.get("model"), "| available:", ok, why)
print("prompt:", V.PROMPT_VERSION_PRESENCE)
print("达标线:", json.dumps(GATE, ensure_ascii=False))
print()

# ---------------- 构造评测集 ----------------
items = []
for sid in SCENES:
    ap = next((PACK / sid).glob("asset.*"))
    asha = hashlib.sha256(ap.read_bytes()).hexdigest()
    for tag in FRAME_TAGS:
        fp = PACK / sid / "frame_{}.png".format(tag)
        if not fp.is_file():
            continue
        items.append({"kind": "POSITIVE", "scene_id": sid, "tag": tag,
                      "frame": fp, "asset": ap, "truth": "present",
                      "label": "人工目视：在屏"})
    # 负例：按冻结口径（bank48 分数最高）确定性挑 NEG_PER_FRAME 个其它素材
    from video_studio.core import corr_diagnostics as CD                        # noqa: E402
    ranked = []
    for sha, p in POOL.items():
        if sha == asha:
            continue
        try:
            ranked.append((CD.bank_score(CD._gray(PACK / sid / "frame_50.png", 48), p,
                                         res=48)["corr"], sha, p))
        except Exception:                                                       # noqa: BLE001
            continue
    ranked.sort(key=lambda x: -x[0])
    for _sc, sha, p in ranked[:NEG_PER_FRAME]:
        items.append({"kind": "NEGATIVE", "scene_id": sid, "tag": "50",
                      "frame": PACK / sid / "frame_50.png", "asset": p,
                      "truth": "absent", "label": "构造错配：帧 vs 无关素材",
                      "bank_score": _sc})
print("评测集: 正例 {} | 负例 {}".format(
    sum(1 for i in items if i["kind"] == "POSITIVE"),
    sum(1 for i in items if i["kind"] == "NEGATIVE")))

spent = 0.0
rows = []
for i, it in enumerate(items, 1):
    res = V.judge_presence(frame_path=it["frame"], asset_path=it["asset"], cfg=cfg,
                           root=R, budget_usd=BUDGET, spent_usd=spent)
    spent = round(spent + float(res.get("cost_usd") or 0.0), 8)
    pres = res.get("presence")
    # uncertain ⇒ 按"不在屏"处理（fail-closed）
    machine = "present" if pres == "present" else "absent"
    agree = (machine == it["truth"])
    rows.append({**{k: it[k] for k in ("kind", "scene_id", "tag", "truth", "label")},
                 "asset": it["asset"].name[:44],
                 "frame": str(it["frame"]),
                 "raw_presence": pres, "machine_treated": machine,
                 "agree": agree, "reason": res.get("reason"),
                 "error_code": res.get("error_code"), "cache_hit": res.get("cache_hit"),
                 "cost_usd": res.get("cost_usd"),
                 "bank_score": it.get("bank_score")})
    print("  [{:>2}/{}] {:8s} {} {} | 人工={} VLM={} => {} | {}".format(
        i, len(items), it["kind"], it["scene_id"], it["tag"], it["truth"], pres,
        "一致" if agree else "**不一致**", str(res.get("reason"))[:44]))

n = len(rows)
agree_n = sum(1 for r in rows if r["agree"])
agreement = round(agree_n / n, 4) if n else 0.0
neg = [r for r in rows if r["kind"] == "NEGATIVE"]
fp = [r for r in neg if r["machine_treated"] == "present"]
unc = [r for r in rows if r["raw_presence"] == "uncertain"]
c1 = agreement >= GATE["min_agreement"]
c2 = len(fp) <= GATE["max_false_present"]
report = {
    "schema": "phase18-p18-3-vlm-presence-eval-v1",
    "stage": "Phase 18 P18-3 VLM 在屏核验层评测",
    "task_boundary": ("视觉**存在性**验证（帧里在不在该素材）；**不判**语义相关性/配不配；"
                      "与 KNOWN_ISSUES #73（判据不同源）**无关**"),
    "prompt_version": V.PROMPT_VERSION_PRESENCE,
    "provider": {"model": cfg.get("model"), "base_url": cfg.get("base_url"),
                 "available": ok, "config_source": src},
    "gate_frozen_before_run": GATE,
    "eval_set": {"positives": sum(1 for r in rows if r["kind"] == "POSITIVE"),
                 "negatives": len(neg),
                 "frames": [t for t in FRAME_TAGS],
                 "neg_sampling": "每景取 bank48 分数最高的 {} 个其它素材（确定性）".format(
                     NEG_PER_FRAME)},
    "results": {"total": n, "agree": agree_n, "agreement": agreement,
                "false_present": len(fp), "uncertain": len(unc),
                "by_kind": {k: {"total": sum(1 for r in rows if r["kind"] == k),
                                "agree": sum(1 for r in rows if r["kind"] == k and r["agree"])}
                            for k in ("POSITIVE", "NEGATIVE")},
                "false_present_detail": [{"scene_id": r["scene_id"],
                                          "asset": r["asset"],
                                          "bank_score": r.get("bank_score")} for r in fp]},
    "gate": {"agreement_pass": bool(c1), "false_present_pass": bool(c2),
             "passed": bool(c1 and c2),
             "decision": ("达标 ⇒ 可接线为仲裁层（corr<0.30 → VLM 核验 → present 放行）"
                          if (c1 and c2) else
                          "未达标 ⇒ **不接线**，维持纯确定性度量现状")},
    "cost": {"budget_usd": BUDGET, "spent_usd": spent,
             "api_calls": sum(1 for r in rows if not r["cache_hit"]),
             "cache_hits": sum(1 for r in rows if r["cache_hit"])},
    "rows": rows,
    "zero_promotion": True,
}
(L / "phase18_p18_3_vlm_presence.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")

print()
print("=" * 78)
print("P18-3 结果")
print("=" * 78)
print("  一致: {}/{} = {:.2%}（阈值 ≥90%）".format(agree_n, n, agreement))
print("  按类型:", json.dumps(report["results"]["by_kind"], ensure_ascii=False))
print("  构造负例 false-present: {}（上限 0）".format(len(fp)))
print("  uncertain（按不在屏处理）: {}".format(len(unc)))
print("  成本: ${:.4f} | API {} | 缓存 {}".format(
    spent, report["cost"]["api_calls"], report["cost"]["cache_hits"]))
print("  门禁:", report["gate"]["decision"])
print("  ->", (L / "phase18_p18_3_vlm_presence.json").relative_to(R).as_posix())
