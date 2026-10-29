# -*- coding: utf-8 -*-
"""P27-1 底片组装：40 景 v2.1 时间轴 + P20-1 voice 切片 + **v4.1 文本 ↔ 40 段窗口映射**。

映射规则（v4.1 为 8 段，40 段底片为 40 段 ⇒ 分段数不符，按**句界/窗口对齐**映射）：
  · v4.1 的 8 段与底片 21 个**父景**一一对应（同源同序）；
  · 每个父景被拆成 k 个子段（40 段底片已有该 k 与各子段时长），
    把该父景的 v4.1 文本按**子段时长比例**切分到句/子句边界（`[。！？!?；;，,]`），
    比例只用于**选切点**，切点在字符上 ⇒ **文本逐字保留**；
  · 逐段落 `text_sha256`，并断言 **Σ子段文本 == 父景 v4.1 文本**（零改动硬校验）。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")

SENT = re.compile(r"[。！？!?；;，,]")
base40 = json.loads((R / "output" / "phase20_script_sandbox" / "script_dcv2_p20_40seg.json")
                    .read_text(encoding="utf-8"))
v41 = json.loads((L / "phase23_v4_1_script.json").read_text(encoding="utf-8"))
voice = json.loads((R / "output/phase20_voice_sandbox/voice_output_40seg_v21.json")
                   .read_text(encoding="utf-8"))

v41_segs = v41["segments"]
# 底片的**父景**（保序）+ 各自子段
parents: list[str] = []
children: dict[str, list[dict]] = {}
for s in base40["segments"]:
    pid = s["parent_scene_id"]
    if pid not in children:
        parents.append(pid)
        children[pid] = []
    children[pid].append(s)
print("v4.1 段数 {} | 父景数 {} | 底片段数 {}".format(
    len(v41_segs), len(parents), len(base40["segments"])))

# ---- 映射：**按句界/窗口对齐**（分段数不符）----
# 规则：v4.1 的文本是**独立的散文段落**，与底片父景**不是一一对应**（8 vs 21）。
# 故按「累计时长比例」把 v4.1 的**拼接全文**切到 21 个父景，再切到 40 个子段。
# 切点**吸附在最接近的句/子句边界**（标点后），字符区间 ⇒ **逐字保留**。
v41_full = "".join(str(s.get("narration") or "") for s in v41_segs)
parent_dur = {pid: sum(float(k["duration_s"] or 0) for k in children[pid]) for pid in parents}
total_dur = sum(parent_dur.values()) or 1.0
bounds_all = [m.end() for m in SENT.finditer(v41_full)]


def snap(want: int, tol: int) -> int:
    if not bounds_all:
        return want
    c = min(bounds_all, key=lambda b: abs(b - want))
    return c if abs(c - want) <= tol else want


# 先切到父景
pcuts, acc = [], 0.0
for pid in parents[:-1]:
    acc += parent_dur[pid]
    want = int(round(len(v41_full) * acc / total_dur))
    pcuts.append(snap(want, max(8, int(0.20 * len(v41_full) / len(parents)))))
pcuts = sorted(set(c for c in pcuts if 0 < c < len(v41_full)))
ppts = [0] + pcuts + [len(v41_full)]
parent_text = {pid: v41_full[ppts[i]:ppts[i + 1]] for i, pid in enumerate(parents)}

rows, bad = [], []
for pid in parents:
    txt = parent_text[pid]
    kids = children[pid]
    td = sum(float(k["duration_s"] or 0) for k in kids) or 1.0
    bounds = [m.end() for m in SENT.finditer(txt)]
    kcuts, acc2 = [], 0.0
    for k in kids[:-1]:
        acc2 += float(k["duration_s"] or 0)
        want = int(round(len(txt) * acc2 / td))
        if bounds:
            c = min(bounds, key=lambda b: abs(b - want))
            kcuts.append(c if abs(c - want) <= max(4, int(0.25 * len(txt) / len(kids)))
                         else want)
        else:
            kcuts.append(want)
    kcuts = sorted(set(c for c in kcuts if 0 < c < len(txt)))
    kpts = [0] + kcuts + [len(txt)]
    for i, k in enumerate(kids):
        a, b = kpts[i], kpts[i + 1]
        frag = txt[a:b]
        rows.append({
            "scene_id": k["scene_id"], "parent_scene_id": pid,
            "parent_duration_s": round(td, 3),
            "duration_s": round(float(k["duration_s"] or 0), 3),
            "char_range": [a, b], "text": frag,
            "text_sha256": hashlib.sha256(frag.encode("utf-8")).hexdigest(),
            "parent_text_sha256": hashlib.sha256(txt.encode("utf-8")).hexdigest(),
            "parent_total_chars": len(txt),
            "rule": "sentence_boundary_by_duration_ratio",
        })
    if "".join(r["text"] for r in rows[-len(kids):]) != txt:
        bad.append("CHILD_CONSERVATION_FAIL:{}".format(pid))
if "".join(parent_text[pid] for pid in parents) != v41_full:
    bad.append("PARENT_CONSERVATION_FAIL")

# 全局守恒
orig_chars = sum(len(str(s.get("narration") or "")) for s in v41["segments"])
new_chars = sum(len(r["text"]) for r in rows)
print("映射段数 {} | 文本守恒 {} -> {} 字符（{}）".format(
    len(rows), orig_chars, new_chars, "相等 ✔" if orig_chars == new_chars else "不等 ✘"))
print("父景解析失败/守恒失败:", bad or "无")

# 40 段派生脚本（v4.1 文本 + 底片时基）
segs = []
for k, r in zip(base40["segments"], rows):
    seg = dict(k)
    seg["narration"] = r["text"]
    seg["narration_sha256"] = r["text_sha256"]
    seg["text_source"] = "phase23_v4_1"
    seg["parent_text_sha256"] = r["parent_text_sha256"]
    segs.append(seg)
out = dict(base40)
out["segments"] = segs
out["schema"] = "script-output-v3-p27-v41-40seg"
out["_p27"] = {
    "base": "phase20_script_sandbox/script_dcv2_p20_40seg.json",
    "text_source": "docs/regression_2x/logs/phase23_v4_1_script.json",
    "text_source_sha256": hashlib.sha256((L / "phase23_v4_1_script.json").read_bytes()).hexdigest(),
    "mapping_rule": "sentence_boundary_by_duration_ratio（按子段时长比例在句/子句边界选切点；字符区间 ⇒ 逐字保留）",
    "orig_chars": orig_chars, "new_chars": new_chars,
    "text_verbatim": orig_chars == new_chars,
    "narrations_edited": False,
    "time_base_s": base40["total_duration_s"],
}
sp = R / "output" / "phase27_script_sandbox"
sp.mkdir(parents=True, exist_ok=True)
fp = sp / "script_p27_v41_40seg.json"
fp.write_text(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")

# 映射表落盘 + assert_lineage
mapping = {
    "schema": "phase27-v41-40seg-mapping-v1",
    "v41_segments": len(v41["segments"]), "base_segments": len(base40["segments"]),
    "unique": len(rows),
    "rule": out["_p27"]["mapping_rule"],
    "text_zero_edit_check": {"orig_chars": orig_chars, "new_chars": new_chars,
                             "equal": orig_chars == new_chars},
    "rows": rows,
    "derived_script": str(fp.relative_to(R)).replace("\\", "/"),
    "derived_script_sha256": hashlib.sha256(fp.read_bytes()).hexdigest(),
    "voice_artifact": "output/phase20_voice_sandbox/voice_output_40seg_v21.json",
    "voice_time_base_s": voice.get("audio_time_base_s"),
    "script_time_base_s": out["total_duration_s"],
}
mp = L / "phase27_p27_1_mapping.json"
mp.write_text(json.dumps(mapping, ensure_ascii=False, indent=1, sort_keys=True),
              encoding="utf-8")

lineage_ok = (orig_chars == new_chars and not bad
              and abs(float(voice.get("audio_time_base_s") or 0)
                      - float(out["total_duration_s"] or 0)) < 1.0
              and len(rows) == len(base40["segments"]))
print()
print("时基: script {} vs voice {} | Δ {:.3f}".format(
    out["total_duration_s"], voice.get("audio_time_base_s"),
    float(out["total_duration_s"]) - float(voice.get("audio_time_base_s") or 0)))
print("assert_lineage:", "通过 ✔" if lineage_ok else "失败 ✘")
print("映射表 ->", mp.relative_to(R).as_posix())
print("派生脚本 ->", fp.relative_to(R).as_posix())
if not lineage_ok:
    sys.exit(1)
