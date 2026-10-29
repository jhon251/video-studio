# -*- coding: utf-8 -*-
"""D8 / E4–E5 slot_count **只读分析**（产出 D8 决策所需信息；不替人工决定，不执行、不修改）。

只引用已冻结材料：6-G package 记录、6-E round-2 proposal、6-E 冻结材料计划（C_self_made_spec）、
DCv2 remapping v2、已接受链路（Batch1 + H3c-1/H3c-2）的投影时间轴、冻结 visual-aid schema。

产出: docs/regression_2x/logs/phase6g_d8_slot_analysis.json
"""
import hashlib
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
OUT = L / "phase6g_d8_slot_analysis.json"
P2 = json.loads((L / "phase6f_rebuild_plan_v2.json").read_text(encoding="utf-8"))
PKG = json.loads((L / "phase6g_rebuild_proposals.json").read_text(encoding="utf-8"))
P6 = json.loads((L / "phase6e_round2.json").read_text(encoding="utf-8"))
B1 = json.loads((L / "phase6g_exec_batch1.json").read_text(encoding="utf-8"))
E3R = json.loads((L / "phase6g_exec_e3.json").read_text(encoding="utf-8"))
MPJ = json.loads(MP.read_text(encoding="utf-8"))
regs = [json.loads(x) for x in (L / "phase6g_rebuild_proposal_register.jsonl").read_text(
    encoding="utf-8").splitlines() if x.strip()]
CPS = float(core_captions.CHARS_PER_SEC)
AUD = L / "phase6g_status_audit.json"


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


SNAP = {"material_plan": sha(MP), "package": sha(L / "phase6g_rebuild_proposals.json"),
        "round2": sha(L / "phase6e_round2.json"), "dcv2_plan": sha(L / "phase6f_rebuild_plan_v2.json"),
        "register": sha(L / "phase6g_rebuild_proposal_register.jsonl"),
        "ledger": sha(L / "phase6g_exec_ledger.jsonl"),
        "db": sha(R / "projects/video_studio.db"),
        "baseline": sorted(p.name for p in (R / "docs/regression_2x/baseline").glob("*"))}

# ---- 已接受链路的时间轴投影（H3a/H3b + H3c-1/H3c-2）
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

items = {}
for lab, scenes in (("E4", ["S08", "S09", "S10"]), ("E5", ["S13", "S14"])):
    p6g = next(p for p in PKG["proposals"] if p["label"].startswith(lab))
    p6e = next(p for p in P6["proposals"] if p["label"].startswith(lab))
    mp_item = MPJ["items"][lab]
    panels = mp_item["C_self_made_spec"]["panels"]
    slots = (p6e["proposed_change"]["params"].get("content_slots")
             or p6e["proposed_change"]["params"].get("panels") or [])
    try:
        spec = VA.compile_from_plan_item(mp_item)
        comp = {"ok": True, "spec_sha256": VA.spec_sha256(spec),
                "kinds": [p["kind"] for p in spec["panels"]],
                "source_labels": [p.get("source_label") for p in spec["panels"]]}
    except Exception as exc:                                             # noqa: BLE001
        comp = {"ok": False, "error": "{}: {}".format(type(exc).__name__, str(exc))}
    subs = [e["scene_id"] for e in proj if e["scene_id"].split(".")[0] in scenes]
    w0, w1 = p6g["affected_scope"]["window"]
    chars = sum(len(p.get("title") or "") + sum(len(str(x)) for x in (p.get("content") or []))
                for p in panels)
    items[lab] = {
        "six_g_record": {"proposal_id": p6g["proposal_id"], "action": p6g["action"],
                         "window": [w0, w1], "share_of_film": p6g["affected_scope"]["share_of_film"],
                         "slot_count": p6g["proposed_change"]["params"].get("slot_count"),
                         "slot_note": p6g["proposed_change"]["params"].get("slot_note"),
                         "expected_direction": (p6g.get("expected_effect") or {}).get("direction"),
                         "overlay_form": p6g["proposed_change"]["params"].get("overlay_form")},
        "six_e_design_basis": {"proposal_id": p6e["proposal_id"], "action": p6e["action"],
                               "diagram": p6e["proposed_change"]["params"].get("diagram"),
                               "content_slots": slots, "slot_count_listed": len(slots),
                               "each_number_must_cite_source":
                                   p6e["proposed_change"]["params"].get(
                                       "each_number_must_cite_source"),
                               "punch_in_only_forbidden":
                                   p6e["proposed_change"]["params"].get(
                                       "punch_in_only_forbidden")},
        "material_plan": {"file": str(MP.relative_to(R)), "sha256": sha(MP), "title":
                          mp_item.get("title"),
                          "panels": [{"id": p["id"], "title": p.get("title"),
                                      "chars": sum(len(str(x)) for x in (p.get("content") or [])),
                                      "items": len(p.get("content") or []),
                                      "fact_sources": p.get("fact_sources")} for p in panels],
                          "panel_count": len(panels),
                          "must_not": mp_item["C_self_made_spec"].get("must_not")},
        "compile_result": comp,
        "window": {"start_s": w0, "end_s": w1, "duration_s": round(w1 - w0, 3),
                   "sub_scenes": subs, "sub_scene_count": len(subs),
                   "spans_sub_scenes": len(subs) > 1},
        "readability": {"chars": chars, "reading_need_s": round(chars / CPS, 1),
                        "window_s": round(w1 - w0, 3),
                        "fits_at_frozen_volume": (chars / CPS) <= (w1 - w0),
                        "headroom_share": round(1 - (chars / CPS) / (w1 - w0), 4),
                        "per_panel_mean_chars": round(chars / max(len(panels), 1), 1),
                        "advisory_only": True},
    }

# ---- 冻结算法的结构上限与映射
limits = {"MAX_PANELS": VA.MAX_PANELS, "KINDS_BY_PANEL_ID": VA._PANEL_KIND,
          "LAYOUTS": list(VA.LAYOUTS), "SAFE_BOTTOM_FRACTION": VA.SAFE_BOTTOM_FRACTION,
          "chars_per_sec": CPS,
          "implication": ("schema 允许 ≤{} 面板，但**计划条目编译器只映射 P1/P2/P3** ⇒ "
                          "4 面板的冻结设计无法由 compile_from_plan_item 产出"
                          ).format(VA.MAX_PANELS)}

# ---- 共享 / 必须不同（只陈述客观依据，不给结论）
e4, e5 = items["E4"], items["E5"]
shared = {
    "same_value_possible": {"value": 3, "grounds": [
        "E5 的冻结材料计划 3 面板**可编译**（spec {}）".format(
            e5["compile_result"].get("spec_sha256", "")[:16]),
        "E4 亦仅在 ≤3 面板时可编译（其 4 面板条目编译失败：{}）".format(
            e4["compile_result"].get("error", "")[:60]),
        "两者窗口均能容纳各自的冻结文本量（E4 {:.1f}s/{:.1f}s；E5 {:.1f}s/{:.1f}s）".format(
            e4["readability"]["reading_need_s"], e4["readability"]["window_s"],
            e5["readability"]["reading_need_s"], e5["readability"]["window_s"])]},
    "different_required_at_4": {"value": 4, "grounds": [
        "E4 第 4 面板 P4 在冻结 kind 映射中**不存在** ⇒ 需新增映射（代码）或人工选定 kind/标签（设计）",
        "E5 的 6-E 列出 4 个 content_slots，但冻结材料计划只有 3 面板 ⇒ 第 4 槽**无冻结版面**，"
        "补齐属新增设计内容"]},
    "factual_differences_at_equal_count": {
        "per_panel_mean_chars": {"E4": e4["readability"]["per_panel_mean_chars"],
                                 "E5": e5["readability"]["per_panel_mean_chars"]},
        "headroom_share": {"E4": e4["readability"]["headroom_share"],
                           "E5": e5["readability"]["headroom_share"]},
        "sub_scene_count": {"E4": e4["window"]["sub_scene_count"],
                            "E5": e5["window"]["sub_scene_count"]},
        "note": "E5 的每面板文本量更大、窗口更短 ⇒ 同等槽数下可读余量更小"},
}

# ---- 除 D8 之外仍需的人工输入（客观事实）
extra_inputs = {
    "overlay_form_A_or_B": {
        "E4": {"sub_scenes": e4["window"]["sub_scenes"], "count": e4["window"]["sub_scene_count"]},
        "E5": {"sub_scenes": e5["window"]["sub_scenes"], "count": e5["window"]["sub_scene_count"]},
        "why": "两者窗口均跨子镜；6-G 登记中**无 overlay_form 字段** ⇒ 与 E3 的 H-6 同类，需人工裁定 A（跨子镜 overlay）"
               "或 B（按子镜分别执行）后才能登记/执行"},
    "E4_fourth_panel_gap": {"frozen_kinds": list(VA._PANEL_KIND.values()),
                            "missing": "P4 的 kind 与 source_label 在冻结映射中不存在",
                            "options_for_human": ["授权把 E4 收敛为 3 面板（并指定合并/舍弃哪一个）",
                                                  "授权扩展冻结映射以支持 P4（代码变更）",
                                                  "授权人工为 P4 选定 kind/source_label（设计内容，需新登记）"]},
    "E5_fourth_slot_gap": {"slots_listed": e5["six_e_design_basis"]["content_slots"],
                           "panels_frozen": [p["id"] for p in e5["material_plan"]["panels"]],
                           "options_for_human": ["以冻结 3 面板为准（第 4 槽不单独上屏）",
                                                 "授权新增第 4 面板（新增设计内容，需新登记）"]},
    "E3_precedent_not_rule": {"form": E3R["overlay_form"], "slot_count": 3, "window_s": 51.774,
                              "chars": E3R["readability_advisory"]["chars"],
                              "note": "E3 已完成（形式 A、3 面板）；**仅作参考，不构成 E4/E5 的规则**"},
}

SNAP2 = {"material_plan": sha(MP), "package": sha(L / "phase6g_rebuild_proposals.json"),
         "round2": sha(L / "phase6e_round2.json"), "dcv2_plan": sha(L / "phase6f_rebuild_plan_v2.json"),
         "register": sha(L / "phase6g_rebuild_proposal_register.jsonl"),
         "ledger": sha(L / "phase6g_exec_ledger.jsonl"),
         "db": sha(R / "projects/video_studio.db"),
         "baseline": sorted(p.name for p in (R / "docs/regression_2x/baseline").glob("*"))}

out = {"schema": "phase6g-d8-slot-analysis-v1", "stage": "6-G / D8（只读）",
       "state": "ANALYSIS_ONLY / AWAITING_HUMAN_DECISION",
       "sources": {"six_g_package": {"path": "docs/regression_2x/logs/phase6g_rebuild_proposals.json",
                                     "sha256": SNAP["package"]},
                   "six_e_round2": {"path": "docs/regression_2x/logs/phase6e_round2.json",
                                    "sha256": SNAP["round2"]},
                   "six_e_material_plan": {"path": str(MP.relative_to(R)),
                                           "sha256": SNAP["material_plan"]},
                   "dcv2_plan_v2": {"path": "docs/regression_2x/logs/phase6f_rebuild_plan_v2.json",
                                    "sha256": SNAP["dcv2_plan"]},
                   "accepted_ledger": {"path": "docs/regression_2x/logs/"
                                               "phase6g_exec_ledger.jsonl",
                                       "sha256": SNAP["ledger"], "entries": 8}},
       "frozen_schema_limits": limits,
       "items": items, "shared_vs_different": shared,
       "additional_required_human_inputs": extra_inputs,
       "decision_not_made": True,
       "explicitly_not_decided": ["E4 slot_count", "E5 slot_count", "是否共用同一 slot_count",
                                 "E4/E5 的 overlay_form（A/B）", "E4 第 4 面板的去留",
                                 "E5 第 4 槽的去留"],
       "invariants": {"read_only": True, "code_modified": False, "proposal_modified": False,
                      "materials_modified": False, "db_written": False, "baseline_or_tag_changed":
                          False, "historical_artifact_changed": False, "e4_e5_executed": False,
                      "thresholds_changed": False, "snapshot_identical": SNAP == SNAP2}}
out["analysis_sha256"] = hashlib.sha256(json.dumps(
    out, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode()
).hexdigest()
OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")

print("== D8 只读分析 ==")
for lab in ("E4", "E5"):
    it = items[lab]
    print("{}: 6-G slot_count={} | 窗口 {}s | 子镜 {} 个".format(
        lab, it["six_g_record"]["slot_count"], it["window"]["duration_s"],
        it["window"]["sub_scene_count"]))
    print("     6-E 设计 {} | content_slots {} 项".format(
        it["six_e_design_basis"]["diagram"], it["six_e_design_basis"]["slot_count_listed"]))
    print("     冻结面板 {} | 编译 {} | 文本 {} 字 / 需 {:.1f}s / 窗口 {:.1f}s（余量 {:.0%}）".format(
        [p["id"] for p in it["material_plan"]["panels"]],
        "OK" if it["compile_result"]["ok"] else "FAILED",
        it["readability"]["chars"], it["readability"]["reading_need_s"],
        it["readability"]["window_s"], it["readability"]["headroom_share"]))
print()
print("可共用同值（客观依据）: 3（E5 已可编译；E4 需 ≤3 才可编译）")
print("4 面板不可共用（客观依据）: E4-P4 无 kind 映射；E5 第 4 槽无冻结版面")
print("快照未变（只读证明）:", SNAP == SNAP2)
print("analysis ->", OUT)
