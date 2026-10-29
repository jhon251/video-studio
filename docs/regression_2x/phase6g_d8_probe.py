# -*- coding: utf-8 -*-
"""D8 只读分析（1/2）：面板类型映射、两案可编译性、冻结文本量与窗口/子镜结构。"""
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import captions as core_captions              # noqa: E402
from video_studio.core import visual_aid as VA                        # noqa: E402
from video_studio.ops import execution as OPX                         # noqa: E402

L = R / "docs" / "regression_2x" / "logs"
MP = R / "docs" / "regression_2x" / "phase6e_materials" / "phase6e_material_plan.json"
mp = json.loads(MP.read_text(encoding="utf-8"))
P2 = json.loads((L / "phase6f_rebuild_plan_v2.json").read_text(encoding="utf-8"))
P6 = json.loads((L / "phase6e_round2.json").read_text(encoding="utf-8"))
B1 = json.loads((L / "phase6g_exec_batch1.json").read_text(encoding="utf-8"))
REG = json.loads((L / "phase6g_rebuild_proposal_register.jsonl").read_text(
    encoding="utf-8")) if False else None
regs = [json.loads(x) for x in (L / "phase6g_rebuild_proposal_register.jsonl").read_text(
    encoding="utf-8").splitlines() if x.strip()]

print("_PANEL_KIND =", json.dumps(getattr(VA, "_PANEL_KIND", None), ensure_ascii=False))
print("SCHEMA:", VA.SCHEMA, "| CHARS_PER_SEC:", core_captions.CHARS_PER_SEC)
print()
for lab in ("E3", "E4", "E5"):
    item = mp["items"][lab]
    try:
        spec = VA.compile_from_plan_item(item)
        vr = VA.verify_spec(spec)
        print("{}: compile OK | panels={} | kinds={} | spec_sha={}".format(
            lab, [p["id"] for p in spec["panels"]],
            [p["kind"] for p in spec["panels"]], VA.spec_sha256(spec)[:16]))
    except Exception as exc:                                             # noqa: BLE001
        print("{}: compile FAILED -> {}: {}".format(lab, type(exc).__name__, str(exc)[:160]))
print()
# 当前 DCv2 窗口与子镜结构（已接受链路：H3a/H3b + H3c-1/H3c-2）
TL = [{"scene_id": c["scene_id"], "start_s": c["new_timeline_window_s"][0],
       "end_s": c["new_timeline_window_s"][1]} for c in P2["remapping_21_segments"]]
proj = [dict(e) for e in TL]


def apply(entries, sp):
    for r in sp.get("scenes", []):
        b = next(e for e in entries if e["scene_id"] == r["scene_id"])
        d = r["sub_duration_s"]
        new = [{"scene_id": "{}.{}".format(r["scene_id"], j + 1),
                "start_s": round(r["window"][0] + d * j, 3),
                "end_s": round(r["window"][0] + d * (j + 1), 3)} for j in range(r["sub_count"])]
        i = entries.index(b)
        entries[i:i + 1] = new
    return entries


for st in ("H3a", "H3b"):
    apply(proj, next(s["exec"]["exec_evidence"]["split_plan"] for s in B1["stages"]
                     if s["stage"] == st))
for lab in ("H3c-1", "H3c-2"):
    p = next(x for x in regs if x.get("label") == lab)
    apply(proj, OPX.split_plan({"timeline": [dict(e) for e in TL], "timeline_identity": None,
                                "caption_timeline": None}, p))
print("已接受链路投影条目:", len(proj))
for lab, scenes in (("E4", ["S08", "S09", "S10"]), ("E5", ["S13", "S14"])):
    subs = [e for e in proj if e["scene_id"].split(".")[0] in scenes]
    w0 = min(e["start_s"] for e in subs if "." not in e["scene_id"]) if any(
        "." not in e["scene_id"] for e in subs) else min(e["start_s"] for e in subs)
    w1 = max(e["end_s"] for e in subs)
    print("{}: 场景 {} | 子镜 {} 个 {} | 窗口 {:.3f}–{:.3f} = {:.3f}s".format(
        lab, scenes, len(subs), [e["scene_id"] for e in subs], w0, w1, round(w1 - w0, 3)))
print()
for lab in ("E3", "E4", "E5"):
    item = mp["items"][lab]
    c = item["C_self_made_spec"]
    p6 = next(p for p in P6["proposals"] if p["label"].startswith(lab))
    slots = (p6["proposed_change"]["params"].get("content_slots")
             or p6["proposed_change"]["params"].get("panels"))
    chars = sum(len(p.get("title") or "") + sum(len(str(x)) for x in (p.get("content") or []))
                for p in c["panels"])
    print("{}: 冻结面板 {} | 6-E content_slots {} | 文本 {} 字 | 阅读需求 {:.1f}s | 窗口 {:.3f}s".format(
        lab, [p["id"] for p in c["panels"]], (len(slots) if slots else None), chars,
        round(chars / float(core_captions.CHARS_PER_SEC), 1),
        {"E3": 51.774, "E4": 131.850, "E5": 86.100}[lab]))
    if slots:
        for i, s in enumerate(slots, 1):
            print("      slot{}: {}".format(i, s))
    for p in c["panels"]:
        print("      panel {} ({}): {} 字 | fact_sources={}".format(
            p["id"], p.get("title"), sum(len(str(x)) for x in (p.get("content") or [])),
            len(p.get("fact_sources") or [])))
