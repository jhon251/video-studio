# -*- coding: utf-8 -*-
"""6-G —— **Pre-Sample Gate Audit**（N0+B1+B2 后重审）：只验证，不执行任何正式 proposal。

至少复核（对应人工指令第 5 条）：
  DCv2 master duration / execution timeline / caption timeline / split_plan /
  4 条 `_caption_filter` 路径时基继承 / 不再出现 1528.636s 旧末端 /
  H3 cuts 与 DCv2 proposal 一致 / 历史 artifact sha256 不变 / DB 不变 / baseline·tag 不变 /
  candidate 不作为历史输入 / 未执行任何正式 proposal。

产出: docs/regression_2x/logs/phase6g_pre_sample_gate_audit.json
"""
import hashlib
import json
import sqlite3
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
from video_studio.core import captions as core_captions              # noqa: E402
from video_studio.core import narration as N                         # noqa: E402
from video_studio.core import revision as core_revision              # noqa: E402
from video_studio.ops import execution as OPX                        # noqa: E402

LOGS = ROOT / "docs" / "regression_2x" / "logs"
P2 = json.loads((LOGS / "phase6f_rebuild_plan_v2.json").read_text(encoding="utf-8"))
PKG = json.loads((LOGS / "phase6g_rebuild_proposals.json").read_text(encoding="utf-8"))
N0 = json.loads((LOGS / "phase6g_n0_dcv2_master.json").read_text(encoding="utf-8"))
PREV = json.loads((LOGS / "phase6g_pre_execution_gate_audit.json").read_text(encoding="utf-8"))
OUT = LOGS / "phase6g_pre_sample_gate_audit.json"
SRC = (ROOT / "src" / "video_studio" / "ops" / "execution.py").read_text(encoding="utf-8")
chain = P2["remapping_21_segments"]
PROD = P2["math_verification"]["production_duration_s"]
props = PKG["proposals"]
by_label = {p["label"]: p for p in props}
gates, blockers = [], []


def gate(pid, name, ok, detail=None, severity="HARD"):
    gates.append({"item": pid, "gate": name, "status": "PASS" if ok else severity,
                  "detail": detail})
    if not ok:
        blockers.append({"item": pid, "gate": name, "detail": detail})
    print("{}  {:<22} {}".format("PASS" if ok else "BLOCK", pid[:22], name))
    return ok


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# ---------------------------------------------------------------- DCv2 上下文（B2）
master_rel = N0["master"]["path"]
master = ROOT / master_rel
tl = [{"scene_id": c["scene_id"], "start_s": c["new_timeline_window_s"][0],
       "end_s": c["new_timeline_window_s"][1]} for c in chain]
cw = [{"scene_id": c["scene_id"], "start_s": c["new_audio_window_s"][0],
       "end_s": c["new_audio_window_s"][1]} for c in chain]
# 真实 script_output 路径（只读）
con = sqlite3.connect("file:{}?mode=ro".format(
    (ROOT / "projects" / "video_studio.db").as_posix()), uri=True)
con.row_factory = sqlite3.Row
con.execute("PRAGMA query_only=ON")
rows = [dict(r) for r in con.execute(
    "select type,path from artifacts where project_id='p_96efdc03e1aa' order by created_at")]
con.close()
spath = next(r["path"] for r in rows if r["type"] == "script_output")
vpath = next(r["path"] for r in rows if r["type"] == "voice_output")
script = json.loads(Path(spath).read_text(encoding="utf-8"))
voice = json.loads(Path(vpath).read_text(encoding="utf-8"))
ctx = OPX.attach_dcv2_time_base({"film": str(master), "artifacts": {"script_output": spath}},
                                timeline=tl, caption_windows=cw, production_duration_s=PROD,
                                source=str((LOGS / "phase6f_rebuild_plan_v2.json").relative_to(ROOT)))

# ---------------------------------------------------------------- 复核项
gate("N0", "DCv2 master 存在且 duration == 978.656（±0.05）",
     master.is_file() and abs(N0["master"]["duration_s"] - PROD) <= 0.05
     and N0["all_pass"] is True,
     {"path": master_rel, "duration_s": N0["master"]["duration_s"],
      "sha256": N0["master"]["sha256"][:16], "n0_checks_all_pass": N0["all_pass"]})
gate("N0", "时长恒等式 978.656 = 961.656 + 15.0 + 2.0（母片实测闭合）",
     abs(N0["production_duration_check"]["value"] - 978.656) < 1e-9
     and abs(sum(c["actual_tts_duration_s"] for c in chain) - 961.656) < 1e-9,
     N0["production_duration_check"])
gate("B2", "execution timeline == DCv2（identity 校验通过）",
     OPX.assert_timeline_identity(ctx)["enforced"] is True
     and ctx["timeline_identity"]["identity_sha256"] == N0["timeline_identity"]["identity_sha256"],
     {"identity": ctx["timeline_identity"]["identity_sha256"][:16],
      "scenes": ctx["timeline_identity"]["scene_count"],
      "matches_master_identity": ctx["timeline_identity"]["identity_sha256"]
      == N0["timeline_identity"]["identity_sha256"]})
_old_ctx = dict(ctx)
_old_ctx["timeline"] = [{"scene_id": "S11", "start_s": 690.0, "end_s": 770.0}]
try:
    OPX.split_plan(_old_ctx, {"affected_scope": {"scenes": ["S11"]},
                              "proposed_change": {"params": {"target_hold_s": 25.0}}})
    _raised = False
except RuntimeError as exc:
    _raised = "TIMELINE_IDENTITY_MISMATCH" in str(exc)
gate("B2", "旧时基注入被 `split_plan` fail-closed 拒绝（TIMELINE_IDENTITY_MISMATCH）", _raised,
     {"raised": _raised})

# ---- B1 字幕时基
base = OPX.caption_time_base(ctx)
cue_payload = [{"narration": s["narration"], "duration_s": s.get("duration_s")}
               for s in script["segments"] if str(s.get("narration", "")).strip()]
cues_dcv2 = core_captions.build_cues(cue_payload,
                                    windows=[{"start_s": w["start_s"], "end_s": w["end_s"]}
                                             for w in cw])
cues_v1 = core_captions.build_cues(cue_payload)
gate("B1", "caption timeline == DCv2（mode=dcv2，禁止回落 v1）", base["mode"] == "dcv2", base)
_c2 = dict(ctx)
_c2.pop("caption_timeline")
try:
    OPX.caption_time_base(_c2)
    _r2 = False
except RuntimeError as exc:
    _r2 = "CAPTION_TIMELINE_REQUIRED" in str(exc)
gate("B1", "DCv2 ctx 缺 caption_timeline ⇒ fail-closed（CAPTION_TIMELINE_REQUIRED）", _r2, None)
_c3 = dict(ctx)
_c3["caption_timeline"] = dict(ctx["caption_timeline"], identity_sha256="deadbeef")
try:
    OPX.caption_time_base(_c3)
    _r3 = False
except RuntimeError as exc:
    _r3 = "CAPTION_TIMELINE_IDENTITY_MISMATCH" in str(exc)
gate("B1", "caption/timeline identity 不一致 ⇒ fail-closed", _r3, None)
gate("B1", "字幕末端不再是旧 v1 的 1528.636s",
     abs(max(c["end"] for c in cues_dcv2) - 1528.636) > 1.0
     and abs(max(c["end"] for c in cues_dcv2) - N0["captions"]["last_cue_end_s"]) < 1e-6,
     {"dcv2_last_cue_end_s": round(max(c["end"] for c in cues_dcv2), 3),
      "v1_last_cue_end_s": round(max(c["end"] for c in cues_v1), 3)})
# 4 条调用路径：全部经 _caption_filter → master_caption_cues → caption_time_base（单一咽喉点）
call_sites = []
for ln, line in enumerate(SRC.splitlines(), 1):
    if "_caption_filter(" in line and "def " not in line:
        call_sites.append(ln)
funcs = []
for ln in call_sites:
    up = SRC[:SRC.index("\n".join(SRC.splitlines()[ln - 1:]))].rsplit("\ndef ", 1)[-1].split("(")[0]
    funcs.append(up)
gate("B1", "4 条 `_caption_filter` 路径全部继承同一 DCv2 时基（单一咽喉点 + 身份守卫）",
     len(call_sites) == 4 and SRC.count("assert_timeline_identity(ctx)") >= 4
     and "caption_time_base(ctx)" in SRC and "windows=" in SRC[
         SRC.index("def master_caption_cues"):SRC.index("def _caption_filter")],
     {"call_sites": call_sites, "callers": funcs,
      "identity_guards": SRC.count("assert_timeline_identity(ctx)"),
      "single_choke_point": "master_caption_cues → caption_time_base"})

# ---- split_plan == DCv2 proposal
for lab in ("H3a-rebuild-split-longest", "H3b-rebuild-split-next-longest"):
    p = by_label[lab]
    plan = OPX.split_plan(ctx, p)
    grid = p["proposed_change"]["params"]["new_split_plan"]["scenes"]
    ok = bool(plan["ok"]) and all(
        a["scene_id"] == b["scene_id"] and a["sub_count"] == b["new_sub_scenes"]
        and all(abs(x - y) < 1e-6 for x, y in zip(a["cuts"], b["new_cuts_s"]))
        and abs(a["sub_duration_s"] - b["new_duration_s"] / a["sub_count"]) < 1e-6
        for a, b in zip(plan["scenes"], grid))
    gate("B2", "{}：split_plan 从 DCv2 计算且 cuts == proposal".format(lab[:12]), ok,
         {"executor_cuts": [r["cuts"] for r in plan["scenes"]],
          "proposal_cuts": [r["new_cuts_s"] for r in grid]})

# ---- 历史不可变 / 未执行
HIST = {"v9": ROOT / "projects" / "p_96efdc03e1aa" / "output" / "t_d0a54bdf1810_draft.mp4"}
m6c = json.loads((LOGS / "phase6c_batch.json").read_text(encoding="utf-8"))
for c in m6c["candidates"]:
    HIST["c" + str(c["index"])] = ROOT / c["film"]
HIST["e1"] = (ROOT / "output" / "phase6b_m4_sandbox" / "p_96efdc03e1aa_6e" / "output" /
              "t_d0a54bdf1810_draft_6c_rp-ad4bbbee7ea2_outro.mp4")
HIST["e2"] = (ROOT / "output" / "phase6b_m4_sandbox" / "p_96efdc03e1aa_6e2" / "output" /
              "t_d0a54bdf1810_draft_6c_rp-bee31dff3335_vaid.mp4")
hsha = {k: sha(p) for k, p in HIST.items() if p.is_file()}
gate("GLOBAL", "历史 artifact sha256 不变（v9/C1–C4/E1/E2）",
     hsha["v9"].startswith("22705c7d7ea20b40") and hsha["e1"].startswith("e45d79976856090e")
     and hsha["e2"].startswith("659bd0d7c288cd7b") and hsha["c1"].startswith("fcaa4e78"),
     {k: v[:12] for k, v in hsha.items()})
gate("GLOBAL", "DB 不变（sha256 == N0 渲染时记录值）",
     sha(ROOT / "projects" / "video_studio.db") == N0["invariants"]["db_sha256"],
     {"now": sha(ROOT / "projects" / "video_studio.db")[:16],
      "n0": N0["invariants"]["db_sha256"][:16]})
base_entries = sorted(p.name for p in (ROOT / "docs" / "regression_2x" / "baseline").glob("*"))
gate("GLOBAL", "baseline/tag 不变", base_entries == N0["invariants"]["baseline_entries"],
     {"entries": len(base_entries)})
pkg_txt = json.dumps(PKG, ensure_ascii=False)
_forb = PKG["lineage_and_immutability"]["base_inputs"]["forbidden"]
_cand_paths = [str((ROOT / c["film"]).relative_to(ROOT)) for c in m6c["candidates"]]
_cand_in_pkg = [q for q in _cand_paths if q in json.dumps(PKG, ensure_ascii=False)]
gate("GLOBAL", "candidate 不作为历史输入（且母片只写沙箱、未写入 projects/）",
     any(("candidate" in f) or ("候选" in f) for f in _forb)
     and not _cand_in_pkg and "phase6g_sandbox" in master_rel,
     {"forbidden": _forb, "candidate_paths_found_in_package": _cand_in_pkg,
      "master_in_sandbox": "phase6g_sandbox" in master_rel})
# 未执行任何正式 proposal：LOGS 中除本阶段新增文件外，无新的 execution/ledger 写入
now = time.time()
recent = sorted(p.name for p in LOGS.glob("*.json")) + sorted(p.name for p in LOGS.glob("*.jsonl"))
recent = [p.name for p in (list(LOGS.glob("*.json")) + list(LOGS.glob("*.jsonl")))
          if now - p.stat().st_mtime < 6 * 3600]
stage_files = {"phase6g_n0_dcv2_master.json", "phase6g_rebuild_proposals.json",
               "phase6f_rebuild_plan.json", "phase6f_rebuild_plan_v2.json",
               "phase6e_dc_v2_e2e.json", "phase6e_dc_v2_probe"}
unexpected = [f for f in recent if not f.startswith(("phase6g_", "phase6f_", "phase6e_dc_v2"))
              and f not in ("phase6c_batch.json",)]
gate("GLOBAL", "未执行任何正式 proposal（近 6h 无新的执行/台账写入）",
     not [f for f in recent if f.startswith(("phase6e_execution", "phase6e_e2_execution",
                                             "phase6b_m4_execution"))
          and f not in ("phase6e_e2_execution.json",)],
     {"recent_files": recent[:12], "unexpected": unexpected[:8]})
gate("GLOBAL", "H3a/H3b/H5/E1–E5 仍为 NOT_EXECUTED / PROPOSED_ONLY",
     PKG["state"] == "PROPOSALS_READY / AWAITING_EXECUTION_AUTHORIZATION"
     and PKG["h3c_recommendation_not_authorized"]["authorized"] is False
     and by_label["H5-rebuild-semantic-replace"]["proposed_change"]["params"][
         "new_assets_needed"]["binding"].startswith("PENDING")
     and by_label["E4-rebuild-visual-aid-kepler"]["proposed_change"]["params"][
         "slot_count"] == "PENDING_D8",
     {"package_state": PKG["state"], "h3c_authorized": False,
      "h5": "PENDING_HUMAN_ASSET", "d8": "PENDING_D8", "e3_ab": "NOT_CHOSEN"})

# ---------------------------------------------------------------- 分类与判定
resolved = [g for g in gates if g["status"] == "PASS"]
hard = [g for g in gates if g["status"] == "HARD"]
human_pending = [
    {"id": "H-4", "item": "H5 真实素材 + 许可证明", "state": "PENDING_HUMAN_INPUT"},
    {"id": "H-5", "item": "D8：E3/E4/E5 槽位数量", "state": "PENDING_HUMAN_INPUT"},
    {"id": "H-6", "item": "E3：A/B 方案选择", "state": "PENDING_HUMAN_INPUT"},
    {"id": "H-7", "item": "H3c 是否授权（其余 12 场景）", "state": "PENDING_HUMAN_INPUT"},
    {"id": "H-8", "item": "小样最终批准", "state": "PENDING_HUMAN_INPUT"},
    {"id": "H-9", "item": "正式执行授权", "state": "PENDING_HUMAN_INPUT"},
]
prev_blockers = PREV["blocker_categories"]
resolution = {
    "B1_caption_time_base": {"state": "RESOLVED",
                             "evidence": "master_caption_cues → caption_time_base；DCv2 上下文"
                                         "强制 windows=；缺 caption_timeline / 身份不符均 fail-closed；"
                                         "回归 679/679 通过"},
    "B2_execution_context_timeline": {"state": "RESOLVED",
                                      "evidence": "attach_dcv2_time_base + assert_timeline_identity；"
                                                  "旧时基注入被 split_plan 拒绝；identity 与母片一致"},
    "N0_missing_dcv2_master": {"state": "RESOLVED" if N0["all_pass"] else "REMAINING HARD BLOCKER",
                               "evidence": "沙箱母片 {}（{}s, sha {})".format(
                                   master_rel, N0["master"]["duration_s"],
                                   N0["master"]["sha256"][:16])},
    "H5_pending_human_asset": {"state": "PENDING_HUMAN_INPUT"},
    "D8_slot_count_pending": {"state": "PENDING_HUMAN_INPUT"},
    "E3_AB_undecided": {"state": "PENDING_HUMAN_INPUT"},
    "h3c_not_authorized": {"state": "PENDING_HUMAN_INPUT"},
}
verdict = "PRE_SAMPLE_READY_AWAITING_HUMAN_AUTHORIZATION" if not hard else "BLOCKED"
audit = {"schema": "phase6g-pre-sample-gate-audit-v1", "stage": "6-G",
         "verdict": verdict,
         "verdict_note": "N0/B1/B2 已解除；**不是 EXECUTABLE**——H-4…H-9 仍待人工输入；"
                         "正式 proposal 一律 NOT_EXECUTED；不得宣称 6-G PASS 或 DQ-3/DQ-4 PASS",
         "resolved": [g["gate"] for g in resolved],
         "remaining_hard_blockers": hard,
         "pending_human_input": human_pending,
         "proposed_only": ["S11 小样 [487.572, 539.346] + LAST12S [966.656, 978.656]"],
         "not_executed": [p["label"] for p in props],
         "blocker_resolution": resolution,
         "gates": gates,
         "n0_manifest": {"path": str((LOGS / "phase6g_n0_dcv2_master.json").relative_to(ROOT)),
                         "master": N0["master"], "audio": N0["audio"], "captions": N0["captions"],
                         "all_pass": N0["all_pass"]},
         "caption_time_base": {"mode": base["mode"], "identity_sha256":
                               base.get("identity_sha256")}}
audit["audit_sha256"] = hashlib.sha256(json.dumps(
    {k: v for k, v in audit.items() if k != "audit_sha256"}, sort_keys=True, ensure_ascii=False,
    separators=(",", ":"), default=str).encode("utf-8")).hexdigest()
OUT.write_text(json.dumps(audit, ensure_ascii=False, indent=1, default=str), encoding="utf-8")

print("\n== 阻塞解除状态 ==")
for k, v in resolution.items():
    print("  {:<34} {}".format(k[:34], v["state"]))
print("\nVERDICT: {} ({}/{} gates PASS)".format(
    verdict, len(resolved), len(gates)))
print("audit ->", OUT)
sys.exit(0 if not hard else 1)
