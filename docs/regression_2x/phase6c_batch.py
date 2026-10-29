# -*- coding: utf-8 -*-
"""6-C —— **Controlled Directorial Revision Batch**：首次用 M3→M5 执行链对 v9 做一批
人工批准、可回溯、可撤销的真实导演修订（每条修改只产生**新的 revision candidate**）。

守恒规则（本脚本自身不发明任何修改）：
  · 只执行**已登记**的 6-B/M3 方案（proposal_id/hash 必须与登记表一致）；
  · 每条执行前必须有**人工 APPROVE + proposal_sha256 绑定**（缺一即阻断）；
  · 优先级 H7 → H2 → H3a/H3b → H5；H4 遵守其对 H3a 的依赖（不单独执行，见 `h4_decision`）；
  · H5 采用**池内换用**（其注册 params 明确 `new_assets_needed.count=0`），素材由
    「人工选材绑定」指定 —— 规则写入绑定记录，不改动方案内容；
  · H2 需要 2 个**新**素材；本阶段可用真实素材不足 ⇒ 保持 `PENDING_HUMAN_ASSET`（量化取证）；
  · 每批执行后**强制** PI-1…PI-6 + DQ-1…DQ-8 复核；不做 promotion、不覆盖 v9、不改基线。

用法: python docs/regression_2x/phase6c_batch.py
产出: logs/phase6c_approvals.jsonl / logs/phase6c_execution_ledger.jsonl /
      logs/phase6c_batch.json / logs/phase6c_candidate_<n>.json
"""
import hashlib
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
LOGS = ROOT / "docs" / "regression_2x" / "logs"
DB = ROOT / "projects" / "video_studio.db"
PID, FILM_TASK = "p_96efdc03e1aa", "t_d0a54bdf1810"
FILM = ROOT / "projects" / PID / "output" / "{}_draft.mp4".format(FILM_TASK)
V9_SHA = "22705c7d7ea20b40d91120146066b89ab2b5fa5c1a1cab18f5346d4c66497651"
EVIDENCE = "docs/regression_2x/logs/audit_p96efdc_mm.json"
M3_REPORT = LOGS / "phase6b_m3_proposals_v9.json"
M2_LEDGER = LOGS / "phase6b_m2_review_ledger_v9.jsonl"
M5_EXEC = LOGS / "phase6b_m5_v9_execution.json"
APPROVALS = LOGS / "phase6c_approvals.jsonl"
LEDGER = LOGS / "phase6c_execution_ledger.jsonl"
OUT = LOGS / "phase6c_batch.json"

from video_studio.core import captions as core_captions            # noqa: E402
from video_studio.core import execution as EX                      # noqa: E402
from video_studio.ops import direction as ops_direction            # noqa: E402
from video_studio.ops import execution as ops_exec                 # noqa: E402

CFG = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8-sig"))


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def manifest(d: Path) -> dict:
    return {p.name: (p.stat().st_size, round(p.stat().st_mtime, 3))
            for p in sorted(d.rglob("*")) if p.is_file()}


def load_js(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


# ---- 0) 只读取证基线 ----
db_b, film_b, src_b = sha(DB), sha(FILM), manifest(FILM.parent)

# ---- 1) v9 上下文（只读）----
con = sqlite3.connect("file:{}?mode=ro".format(DB.as_posix()), uri=True)
con.row_factory = sqlite3.Row
con.execute("PRAGMA query_only=ON")
recs = [dict(r) for r in con.execute(
    "select artifact_id, task_id, type, path from artifacts where project_id=? order by created_at",
    (PID,))]
con.close()
by_type = {}
for r in recs:
    by_type.setdefault(r["type"], []).append(r)


def payload(t, task=None):
    lst = by_type.get(t) or []
    rec = next((x for x in lst if task and x["task_id"] == task), lst[-1] if lst else None)
    if not rec:
        return {}
    p = Path(rec["path"])
    return json.loads((p if p.is_absolute() else ROOT / p).read_text(encoding="utf-8"))


script = payload("script_output")
voice = payload("voice_output")
render = payload("render_output", FILM_TASK)
timeline = render.get("material_timeline") or []
timeline_total = float((render.get("duration_contract") or {}).get("timeline_duration_s") or 1532.0)
narr_s = voice.get("narration_duration_s")

# ---- 2) 真实素材索引（v9 候选 + 在用素材；全部**真实文件**）----
real_index, cand_of_scene = {}, {}
for e in timeline:
    for c in (e.get("candidates") or []):
        real_index.setdefault(c["asset_id"], c)
        cand_of_scene.setdefault(str(e.get("scene_id")), []).append(c)
for e in timeline:
    sa = e.get("selected_asset") or {}
    if sa.get("asset_id"):
        real_index.setdefault(sa["asset_id"], sa)
for aid, c in real_index.items():
    c["constructed"] = False

box = ops_exec.prepare_sandbox(ROOT, PID, "6c", FILM,
                               artifacts={"script_output": script, "voice_output": voice})


def build_ctx(film: Path, tl: list, bindings: dict | None = None) -> dict:
    return {"root": ROOT, "box": box["box"], "film": film,
            "artifacts": box["artifacts"], "files": box["files"],
            "ffmpeg": CFG["tools"]["ffmpeg"]["path"],
            "ffprobe": CFG["tools"]["ffmpeg"]["ffprobe"], "config": CFG,
            "timeline": tl, "timeline_duration_s": timeline_total,
            "evidence": ops_direction.load_evidence(EVIDENCE, ROOT),
            "cues": core_captions.build_cues(
                [{"narration": s.get("narration", ""), "duration_s": s.get("duration_s")}
                 for s in (script.get("segments") or [])]),
            "asset_index": real_index, "asset_bindings": bindings or {}}


# ---- 3) 登记方案 + 人工决策引用 ----
m3 = load_js(M3_REPORT)["proposals"]
by_label = {p["label"]: p for p in m3}
m2 = [json.loads(ln) for ln in M2_LEDGER.read_text(encoding="utf-8").splitlines() if ln.strip()]
m2_by_fid = {e.get("finding_id"): e for e in m2}

# ---- 4) 人工 APPROVE（绑定 proposal_id + proposal_sha256 + 身份 + 时间 + 理由/溯源）----
approvals = []


def approve(label, reason, prov, **extra):
    p = by_label[label]
    rec = EX.make_approval(p, "APPROVE", "human:director(6-C)", reason, prov,
                           at="2026-09-30T00:00:00Z")
    rec["human_note"] = extra or None
    rec = EX.append_approval(APPROVALS, rec)
    approvals.append(rec)
    return rec


approve("H7-outro-card", "同意在 S21 窗口内原地补片尾卡（时长不变、音轨与母版一致）",
        "human:6-A 审计 §2.7（缺片尾 VERIFIED）+ KNOWN_ISSUES #67 + M4 既有批准")
approve("H2-asset-pool-diversity",
        "同意补足素材多样性（4→≥6）；**但必须使用真实、许可明确的素材**，无合格素材则保持 PENDING",
        "human:6-A 审计 §2.2（素材重复 VERIFIED）")
approve("H3-batch1-split-longest", "同意对该批 4 个长镜加视觉切点（≤25s；保留旁白/字幕/总时长/音轨）",
        "human:6-A 审计 §2.4（单镜过长 VERIFIED）")
approve("H3-batch2-next-longest", "同意对次长一批 5 个镜头做同样切分（同守恒条件）",
        "human:6-A 审计 §2.4")
approve("H5-semantic-mismatch-replace",
        "同意**池内换用**（该方案注册 params 明确 count=0，不申请新素材）：逐镜按候选表选材",
        "human:6-A 审计 §2.3（语义不匹配 VERIFIED）+ 该镜候选表（match_score/matched_tokens）")

# H5 人工选材绑定（规则：该镜候选表中 match_score 最高、且**不等于当前在用素材**、
# 且文件真实存在 + sha256 一致 + 可解码；许可类别优先 PUBLIC_DOMAIN/FREE_ATTRIBUTION）
PRIORITY_LICENSE = {"PUBLIC_DOMAIN": 0, "FREE_ATTRIBUTION": 1, "UNKNOWN": 2}
used = {str(e.get("scene_id")): (e.get("selected_asset") or {}).get("asset_id") for e in timeline}
sel_rows, bindings_h5 = [], {}
for sid in ((by_label["H5-semantic-mismatch-replace"].get("affected_scope") or {})
            .get("scenes") or []):
    rows = []
    for c in cand_of_scene.get(str(sid), []):
        p = Path(c.get("path") or "")
        if not p.is_file() or c.get("asset_id") == used.get(str(sid)):
            continue
        if sha(p) != c.get("sha256"):
            continue
        rows.append(c)
    rows.sort(key=lambda c: (-(c.get("match_score") or 0),
                             PRIORITY_LICENSE.get(c.get("license_class") or "UNKNOWN", 3),
                             c.get("asset_id")))
    if rows:
        bindings_h5[str(sid)] = rows[0]["asset_id"]
        sel_rows.append({"scene_id": str(sid), "prev_asset_id": used.get(str(sid)),
                         "selected_asset_id": rows[0]["asset_id"],
                         "match_score": rows[0].get("match_score"),
                         "matched_tokens": rows[0].get("matched_tokens"),
                         "license": rows[0].get("license"),
                         "license_class": rows[0].get("license_class"),
                         "sha256": rows[0].get("sha256"), "path": rows[0].get("path"),
                         "candidates_considered": len(cand_of_scene.get(str(sid), []))})
    else:
        sel_rows.append({"scene_id": str(sid), "prev_asset_id": used.get(str(sid)),
                         "selected_asset_id": None, "why": "该镜候选表中无合格（真实+未在用）素材"})
BINDINGS = {by_label["H5-semantic-mismatch-replace"]["proposal_id"]: bindings_h5}
print("H5 选材绑定:", json.dumps(sel_rows, ensure_ascii=False)[:400])

# ---- 5) 批次执行（每条修改只产生新的 candidate；批次内按输入顺序链式推进）----
current_film, current_timeline = FILM, timeline
batches, candidates, idx = [], [], 0
# 优先级：H7 → H2 → H3a/H3b → H5
PLAN = [("C1", ["H7-outro-card"], "片尾收束（真实视频重编码 + 母版音轨流复制）"),
        ("C2", ["H2-asset-pool-diversity"], "素材池多样性（需真实新素材；不足则 PENDING）"),
        ("C3", ["H3-batch1-split-longest", "H3-batch2-next-longest"],
         "长镜切分（9 个镜头加构图切点；时长/音轨守恒）"),
        ("C4", ["H5-semantic-mismatch-replace"], "语义不匹配镜头的池内换用（人工选材绑定）")]

for name, labels, note in PLAN:
    props = [by_label[i] for i in labels]
    parent = current_film
    gate = EX.gate_batch(props, approvals, ledger_entries=EX.load_ledger(LEDGER))
    recs = []
    for p in props:
        pid = p["proposal_id"]
        d = gate["decisions"].get(pid) or {}
        if not d.get("allowed"):
            rec = EX.blocked_record(p, d.get("code") or "BLOCKED_UNAPPROVED", d.get("why") or "",
                                    {k: d[k] for k in ("conflict_with",
                                                       "requires_human_reapproval", "source")
                                     if k in d})
            rec = EX.append_execution(LEDGER, rec)
            recs.append(rec)
            print("[{}] {} -> {}".format(name, p["label"], rec["state"]))
            continue
        ctx = build_ctx(current_film, current_timeline, BINDINGS)
        res = EX.execute_batch([p], approvals, ops_exec.EXECUTORS, ctx,
                               recheck=ops_exec.pi_recheck, ledger=LEDGER,
                               ledger_entries=EX.load_ledger(LEDGER))
        rec = res["records"][0]
        recs.append(rec)
        print("[{}] {} -> {} {}".format(name, p["label"], rec["state"],
                                        (rec.get("why") or "")[:80]))
        if rec["state"] == "SUCCEEDED":
            current_film = ROOT / rec["outputs"][0]["path"]
            proj = ops_exec.project_timeline(build_ctx(current_film, current_timeline),
                                             p, rec.get("exec_evidence") or {})
            if proj[1]:
                current_timeline = proj[0]
            idx += 1
            cand = {"index": idx, "batch": name, "proposal_label": p["label"],
                    "proposal_id": pid, "proposal_sha256": rec["proposal_sha256"],
                    "parent_film": str(parent.relative_to(ROOT)),
                    "parent_sha256": sha(parent),
                    "film": str(current_film.relative_to(ROOT)),
                    "film_sha256": sha(current_film),
                    "bytes": current_film.stat().st_size,
                    "pi_metrics": (rec.get("recheck") or {}).get("pi_metrics"),
                    "pi_gate_outcome": (rec.get("recheck") or {}).get("pi_gate_outcome"),
                    "dq_metrics": (rec.get("recheck") or {}).get("dq_metrics"),
                    "dq_details": (rec.get("recheck") or {}).get("dq_details"),
                    "timeline_projection": (rec.get("recheck") or {}).get("timeline_projection"),
                    "exec_evidence": rec.get("exec_evidence"),
                    "steps": rec.get("steps"),
                    "outputs": rec.get("outputs")}
            candidates.append(cand)
            (LOGS / "phase6c_candidate_{}.json".format(idx)).write_text(
                json.dumps(cand, ensure_ascii=False, indent=1), encoding="utf-8")
    batches.append({"batch": name, "note": note, "labels": labels, "parent": str(parent.name),
                    "order": [r["proposal_label"] for r in recs],
                    "states": {r["proposal_label"]: r["state"] for r in recs},
                    "records": recs, "executed": [r["proposal_label"] for r in recs
                                                  if r["state"] == "SUCCEEDED"],
                    "executor_invocations": [r["proposal_label"] for r in recs
                                             if r.get("executor_invoked")]})

# ---- 6) 候选成片验证（可独立回放 / 音轨 / 时长 / 容器完整性）----
def verify_candidate(cand: dict) -> dict:
    film = ROOT / cand["film"]
    ffmpeg, ffprobe = CFG["tools"]["ffmpeg"]["path"], CFG["tools"]["ffmpeg"]["ffprobe"]
    probe = ops_exec.probe_media(ffprobe, film)
    dur = probe.get("duration_s") or 0.0
    head = subprocess.run([ffmpeg, "-v", "error", "-i", str(film), "-t", "90", "-f", "null", "-"],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    tail = subprocess.run([ffmpeg, "-v", "error", "-ss", "{:.3f}".format(max(dur - 90, 0)),
                           "-i", str(film), "-f", "null", "-"], capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    remux = subprocess.run([ffmpeg, "-v", "error", "-i", str(film), "-c", "copy", "-f", "null",
                            "-"], capture_output=True, text=True, encoding="utf-8",
                           errors="replace")
    return {"film": cand["film"], "probe": probe,
            "duration_delta_vs_master_s": round(dur - timeline_total, 3),
            "decode_head90_rc": head.returncode, "decode_tail90_rc": tail.returncode,
            "full_container_scan_rc": remux.returncode,
            "two_streams": bool(probe.get("has_audio")) and probe.get("width") is not None,
            "audio_identical_stream": (cand.get("exec_evidence") or {})
            .get("audio_check", {}).get("identical_stream"),
            "audio_check": (cand.get("exec_evidence") or {}).get("audio_check"),
            "duration_check": (cand.get("exec_evidence") or {}).get("duration_check")}


for c in candidates:
    c["verification"] = verify_candidate(c)
    print("[verify] cand{} {} 2streams={} decode={}/{} scan={} durΔ={}s audio_identical={}".format(
        c["index"], Path(c["film"]).name, c["verification"]["two_streams"],
        c["verification"]["decode_head90_rc"], c["verification"]["decode_tail90_rc"],
        c["verification"]["full_container_scan_rc"], c["verification"]["duration_delta_vs_master_s"],
        c["verification"]["audio_identical_stream"]))

# ---- 7) H4：依赖与重叠的**显式**处置（已知边界，不得静默绕过）----
h3a = by_label["H3-batch1-split-longest"]
h4 = by_label["H4-density-increase"]
h3a_rec = next((r for b in batches for r in b["records"]
                if r["proposal_label"] == "H3-batch1-split-longest"), None)
h3a_done = bool(h3a_rec and h3a_rec["state"] == "SUCCEEDED")
pair = EX.pair_conflict(h3a, h4)
# 诊断（**不写入台账**）：若 H4 也获人工批准并与 H3a 同批提交，M5 门禁会如何判定？
h4_probe_ap = EX.make_approval(h4, "APPROVE", "human:diagnostic(6-C)", "诊断用（不落盘）",
                               "diagnostic only", at="2026-09-30T00:00:00Z")
probe_gate = EX.gate_batch([h3a, h4], approvals + [h4_probe_ap],
                           ledger_entries=EX.load_ledger(LEDGER))
h4_decision = {
    "dependency": (h4["proposed_change"]["params"].get("dependency") or []),
    "dependency_satisfied": h3a_done,
    "h3a_execution": {"proposal_id": h3a["proposal_id"], "state": (h3a_rec or {}).get("state"),
                      "candidate": [c["film"] for c in candidates
                                    if c["proposal_label"] == "H3-batch1-split-longest"]},
    "registered_intent": h4["proposed_change"]["how"],
    "overlap_with_h3a": pair,
    "diagnostic_if_h4_approved_and_submitted_together": {
        "diagnostic_only": True, "not_appended_to_ledger": True,
        "blocked_conflict": probe_gate["blocked_conflict"],
        "decisions": {k: v["code"] for k, v in probe_gate["decisions"].items()},
        "note": "h4_probe_ap 只用于诊断（未 append 到审批台账）"},
    "decision": "NOT_EXECUTED_REQUIRES_HUMAN_REAPPROVAL",
    "why": "① 注册意图 = 『与 H3-batch1 **合并推进**（同一批切分同时提升密度）』⇒ 其 DQ-4 期望效果"
           "已由 C3 候选实测（见 before_after_diffs）；② 单独再次执行 H4 会**二次切分同一批镜头**"
           "（= 范围扩大，注册方案未授权）；③ 若与 H3a 同批提交，M5 门禁会**对称阻断**两者"
           "（诊断已记录）；④ M5 门禁按**批次**判定重叠 ⇒ 跨批次重叠是 M5 已声明的已知边界："
           "本阶段**不**用静默方式绕过，而是显式记录重叠对 + 要求人工重新批准。",
    "cross_batch_overlap_declared": True,
    "requires_human_reapproval": True,
}
print("H4 决策:", h4_decision["decision"], "| dependency_satisfied:", h3a_done,
      "| overlap kinds:", (pair or {}).get("kinds"),
      "| 同批诊断:", h4_decision["diagnostic_if_h4_approved_and_submitted_together"]["decisions"])

# ---- 8) H2 素材短缺量化取证（为何 PENDING）----
h2 = by_label["H2-asset-pool-diversity"]
in_film = sorted({(e.get("selected_asset") or {}).get("asset_id") for e in timeline} - {None})
pool = sorted(real_index)
unused = [a for a in pool if a not in in_film]
verified = []
for aid in pool:
    v = ops_exec.verify_asset_candidate(build_ctx(FILM, timeline), aid)
    rec = real_index[aid]
    verified.append({"asset_id": aid, "status": v["status"], "code": v["code"],
                     "in_film": aid in in_film, "license": rec.get("license"),
                     "license_class": rec.get("license_class"),
                     "gate_applies": (v["evidence"] or {}).get("license_gate_applies"),
                     "sha256": rec.get("sha256"),
                     "actual_sha256": (v["evidence"] or {}).get("actual_sha256"),
                     "sha_ok": rec.get("sha256") == (v["evidence"] or {}).get("actual_sha256")})
h2_shortfall = {
    "registered_target": h2["proposed_change"]["params"],
    "distinct_assets_in_film": len(in_film), "assets_in_film": in_film,
    "distinct_real_assets_available": len(pool), "pool": pool,
    "unused_verified_assets": [a for a in unused
                               if next(v for v in verified if v["asset_id"] == a)["status"] == "ok"],
    "verified": verified,
    "conclusion": "注册目标要求 **2 个新素材**（唯一素材 4→≥6）；本阶段材料池中真实素材共 {} 个，"
                  "其中未入片且校验通过的仅 {} 个 ⇒ 无法在不虚构素材的前提下满足注册目标，"
                  "按授权第 4 条保持 `PENDING_HUMAN_ASSET`。".format(
                      len(pool), len([a for a in unused
                                      if next(v for v in verified
                                              if v["asset_id"] == a)["status"] == "ok"])),
}
print("H2 短缺:", h2_shortfall["conclusion"])

# ---- 9) before/after 指标差异（v9 基线取自 M5 记录的 v9 复核；不新跑母版）----
m5 = load_js(M5_EXEC)
v9_rec = ((m5.get("batches") or [{}])[0].get("records") or [{}])[0]
v9_before = {"pi_metrics": (v9_rec.get("recheck") or {}).get("pi_metrics"),
             "pi_gate_outcome": (v9_rec.get("recheck") or {}).get("pi_gate_outcome"),
             "dq_metrics": (v9_rec.get("recheck") or {}).get("dq_metrics"),
             "dq_details": (v9_rec.get("recheck") or {}).get("dq_details"),
             "film": v9_rec.get("recheck", {}).get("film"),
             "source": "logs/phase6b_m5_v9_execution.json → batches[0].records[0].recheck"
                       "（对 v9 母版复制品的强制 PI/DQ 复核）"}
print("v9 基线:", json.dumps({"DQ": v9_before["dq_metrics"], "PI": v9_before["pi_gate_outcome"],
                             "detail_keys": sorted((v9_before["dq_details"] or {}))},
                            ensure_ascii=False))
diffs = []
parent_metrics = v9_before
for c in candidates:
    cur = {"pi_metrics": c["pi_metrics"], "dq_metrics": c["dq_metrics"],
           "dq_details": c["dq_details"]}
    dq_delta = {k: [ (parent_metrics.get("dq_metrics") or {}).get(k), (cur["dq_metrics"] or {}).get(k)]
                 for k in sorted(cur["dq_metrics"] or {})}
    dq_detail_delta = {}
    for k, det in (c["dq_details"] or {}).items():
        prev = (parent_metrics.get("dq_details") or {}).get(k) or {}
        dq_detail_delta[k] = {kk: [prev.get(kk), det.get(kk)]
                              for kk in det if kk not in ("state",) and prev.get(kk) != det.get(kk)}
    diffs.append({"candidate": c["film"], "batch": c["batch"],
                  "proposal_label": c["proposal_label"],
                  "pi_metrics": cur["pi_metrics"], "pi_gate_outcome": c["pi_gate_outcome"],
                  "dq_state_delta_vs_parent": dq_delta,
                  "dq_detail_delta_vs_parent": dq_detail_delta,
                  "dq_details": c["dq_details"]})
    parent_metrics = cur

# ---- 10) 只读取证 ----
db_a, film_a, src_a = sha(DB), sha(FILM), manifest(FILM.parent)
led = EX.load_ledger(LEDGER)
out = {
    "schema": "directorial-batch-run-v1", "stage": "6-C",
    "note": "首次使用 M3→M5 执行链对 v9 做人工批准的受控修订；每条修改只产生**新的 revision "
            "candidate**；v9 母版与项目目录零改动；不做 promotion；跨进程无锁与跨批次重叠按已知边界"
            "**显式**处置（不静默绕过）。",
    "inputs": {"project_id": PID, "film_task": FILM_TASK, "v9_film": str(FILM),
               "v9_sha256": film_b, "m3_register": str(M3_REPORT.relative_to(ROOT)),
               "sandbox": str(Path(box["box"]).relative_to(ROOT))},
    "registered_proposals": [{"label": p["label"], "proposal_id": p["proposal_id"],
                              "action": p["action"], "sha256": EX.proposal_sha256(p),
                              "scenes": (p["affected_scope"] or {}).get("scenes")}
                             for p in m3],
    "approvals": [{"approval_id": a["approval_id"], "proposal_label": a["proposal_label"],
                   "proposal_id": a["proposal_id"], "decision": a["decision"],
                   "approved_by": a["approved_by"], "reason": a["reason"],
                   "provenance": a["provenance"], "proposal_sha256": a["proposal_sha256"],
                   "seq": a["seq"], "auto_approved": a.get("auto_approved", False),
                   "human_note": a.get("human_note")} for a in approvals],
    "asset_bindings": {"rule": "该镜候选表中 match_score 最高、且≠当前在用素材、文件真实存在且 "
                               "sha256 一致、许可类别优先 PUBLIC_DOMAIN > FREE_ATTRIBUTION",
                       "proposal": by_label["H5-semantic-mismatch-replace"]["proposal_id"],
                       "bindings": BINDINGS.get(
                           by_label["H5-semantic-mismatch-replace"]["proposal_id"]),
                       "selection_evidence": sel_rows},
    "asset_pool": {"distinct_in_film": len(in_film), "pool_size": len(pool),
                   "records": {k: {kk: v.get(kk) for kk in
                                   ("name", "path", "sha256", "source", "provider", "license",
                                    "license_class", "license_cleared", "width", "height",
                                    "attribution")} for k, v in real_index.items()}},
    "batches": batches,
    "candidates": candidates,
    "candidate_count": len(candidates),
    "before_after_diffs": diffs,
    "v9_before": v9_before,
    "h4_decision": h4_decision,
    "h2_shortfall": h2_shortfall,
    "summary": {
        "planned_batches": [b[0] for b in PLAN],
        "executed_succeeded": [c["proposal_label"] for c in candidates],
        "candidate_films": [c["film"] for c in candidates],
        "state_counts": {s: sum(1 for b in batches for r in b["records"] if r["state"] == s)
                         for s in sorted({r["state"] for b in batches for r in b["records"]})},
        "promoted": [r["proposal_id"] for b in batches for r in b["records"] if r.get("promoted")],
        "auto_approved": any(a.get("auto_approved") for a in approvals),
        "ledger": {"path": str(LEDGER.relative_to(ROOT)), "entries": len(led),
                   "chain_ok": EX.verify_chain(led)["ok"],
                   "unique_seq": len({e["seq"] for e in led})},
        "approvals_ledger": {"path": str(APPROVALS.relative_to(ROOT)),
                             "entries": len(EX.load_ledger(APPROVALS)),
                             "chain_ok": EX.verify_chain(EX.load_ledger(APPROVALS))["ok"]},
        "all_candidates_two_streams": all(c["verification"]["two_streams"] for c in candidates),
        "all_candidates_decode_ok": all(c["verification"]["decode_head90_rc"] == 0
                                        and c["verification"]["decode_tail90_rc"] == 0
                                        for c in candidates),
        "all_candidates_container_ok": all(c["verification"]["full_container_scan_rc"] == 0
                                           for c in candidates),
        "all_candidates_audio_identical": all(c["verification"]["audio_identical_stream"]
                                              is True for c in candidates),
        "max_duration_delta_s": (max([abs(c["verification"]["duration_delta_vs_master_s"])
                                      for c in candidates]) if candidates else None),
        "pi_gate_outcomes": {c["proposal_label"]: c["pi_gate_outcome"] for c in candidates},
        "note": "候选成片仅用于人工观看；本阶段**不**做 promotion（PI 仍 BLOCKED 时尤其不得宣称全片 PASS）",
    },
    "read_only_evidence": {
        "db_sha256_before": db_b, "db_sha256_after": db_a, "db_unchanged": db_b == db_a,
        "v9_master_sha256_before": film_b, "v9_master_sha256_after": film_a,
        "v9_master_unchanged": film_b == film_a, "v9_master_matches_m1_record": film_b == V9_SHA,
        "v9_output_dir_unchanged": src_b == src_a, "project_files_touched": [],
        "candidates_outside_project_dir": all("projects" not in (ROOT / c["film"]).parts
                                              for c in candidates),
    },
}
OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

print("\n批次:", json.dumps({b["batch"]: b["states"] for b in batches}, ensure_ascii=False))
print("候选:", [(c["index"], c["proposal_label"], c["film"], c["film_sha256"][:12])
                for c in candidates])
print("台账:", out["summary"]["ledger"], "| 审批:", out["summary"]["approvals_ledger"])
print("只读: DB", out["read_only_evidence"]["db_unchanged"], "| v9 母版",
      out["read_only_evidence"]["v9_master_unchanged"],
      "| v9 output 目录", out["read_only_evidence"]["v9_output_dir_unchanged"])
print("json ->", OUT)
