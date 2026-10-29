# -*- coding: utf-8 -*-
"""P19-2 素材误导倾向标记（同 crop_safety 模式）。

`discriminative_score` = 该素材在 48×48 灰度下与**池内其它素材**的最大 corr。
高值（≥0.35）⇒ 该素材容易被别的景误匹配（如 `301ff850be9c`）⇒ 标记 `low_discriminative`、短名单降权。
12 张全量补算并登记（与 `phase17_crop_safety_registry.json` 并列，供短名单联合降权）。
"""
from __future__ import annotations

import hashlib
import itertools
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
SRC = R / "projects" / "p_96efdc03e1aa"
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core.materials import frame_corr, gray48                      # noqa: E402
from PIL import Image                                                          # noqa: E402

THRESH = 0.35

POOL: dict[str, pathlib.Path] = {}
for d in (SRC / "media", SRC / "registered_materials", SRC / "acquired_materials"):
    if d.is_dir():
        for f in sorted(d.rglob("*")):
            if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
                POOL.setdefault(hashlib.sha256(f.read_bytes()).hexdigest(), f)

# 来源标注（沿用 P16 台账）
reg = json.loads((L / "phase16_local_registry.json").read_text(encoding="utf-8"))
acq = json.loads((L / "phase16_acquired_registry.json").read_text(encoding="utf-8"))
ORIGIN = {x["sha256"]: "P16-2 registered" for x in (reg.get("registered") or [])}
ORIGIN.update({x["sha256"]: "P16-3 acquired" for x in (acq.get("registered") or [])})
# crop_safety（P17-3）
cs = json.loads((L / "phase17_crop_safety_registry.json").read_text(encoding="utf-8"))
CROPS = {r["sha256"]: r for r in cs["assets"]}

grays = {}
for sha, p in POOL.items():
    try:
        grays[sha] = gray48(p)
    except Exception as exc:                                                    # noqa: BLE001
        print("!! gray48 失败", p.name, exc)

rows = []
for sha, p in sorted(POOL.items()):
    best, worst_peer = -2.0, None
    pair_rows = []
    for other, op in POOL.items():
        if other == sha or other not in grays or sha not in grays:
            continue
        c = round(float(frame_corr(grays[sha], grays[other])), 4)
        pair_rows.append({"peer_sha12": other[:12], "peer_name": op.name[:44], "corr": c})
        if c > best:
            best, worst_peer = c, op.name
    pair_rows.sort(key=lambda x: -x["corr"])
    with Image.open(p) as im:
        wh = "{}x{}".format(*im.size)
    rows.append({
        "sha256": sha, "sha12": sha[:12], "name": p.name, "size": wh,
        "path": str(p), "origin": ORIGIN.get(sha, "pre-existing pool"),
        "discriminative_score": round(best, 4),
        "most_similar_peer": (worst_peer[:44] if worst_peer else None),
        "top3_similar": pair_rows[:3],
        "low_discriminative": bool(best >= THRESH),
        "crop_safety": (CROPS.get(sha) or {}).get("crop_safety"),
        "low_crop_safety": bool((CROPS.get(sha) or {}).get("low_crop_safety")),
        "action": ("短名单降权（low_discriminative；不硬拒，人工仍可选）"
                   if best >= THRESH else "正常"),
    })

print("=" * 100)
print("P19-2 素材误导倾向标记")
print("=" * 100)
print("{:>14} {:>10} {:>10} {:>6} {:>8}  {}".format(
    "sha12", "尺寸", "discrim", "低判", "crop安全", "最相似素材"))
for r in rows:
    print("{:>14} {:>10} {:>10} {:>6} {:>8}  {}".format(
        r["sha12"], r["size"], r["discriminative_score"],
        "是" if r["low_discriminative"] else "", r["crop_safety"],
        (r["most_similar_peer"] or "-")[:34]))
low = [r for r in rows if r["low_discriminative"]]
print()
print("  标记 low_discriminative: {} / {}".format(len(low), len(rows)))
for r in low:
    print("    {} {} (discrim={}) 最相似={}".format(
        r["sha12"], r["name"][:40], r["discriminative_score"],
        r["most_similar_peer"]))
# 双重标记
both = [r for r in rows if r["low_discriminative"] and r["low_crop_safety"]]
print("  同时 low_crop_safety + low_discriminative:", [r["sha12"] for r in both] or "无")

out = {
    "schema": "phase19-discriminative-registry-v1",
    "method": ("discriminative_score = max over 池内其它素材 of corr_48(该素材, 其它素材)"
               "（冻结口径 gray48 48×48 灰度 Pearson）"),
    "threshold": THRESH,
    "policy": ("≥0.35 ⇒ 标记 low_discriminative 并在短名单**降权**；**不硬拒**（人工仍可选）。"
               "与 P17-3 的 crop_safety 并列，共同构成短名单降权依据。"),
    "assets": rows,
    "low_discriminative_count": len(low),
    "dual_flagged": [r["sha12"] for r in both],
    "note": ("Phase 18 P18-2 实测：`301ff850be9c` 是 v3 反门仅有的 2 条误通过来源"
             "（对 S02=0.3542、对 S07=0.352），本表按同一机理给出全池标记。"),
}
p = L / "phase19_discriminative_registry.json"
p.write_text(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
print()
print("  ->", p.relative_to(R).as_posix())
