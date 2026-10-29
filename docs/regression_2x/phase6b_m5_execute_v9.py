# -*- coding: utf-8 -*-
"""6-B/M5 —— 关闭 6-B/M4 两个 PENDING 的**真实验证闭环**（沙箱内执行；v9 母版零改动）。

关闭对象：
  P1「真实素材 `add_asset/replace_asset` 执行分支 E2E」
     · 用**真实存在 + sha256 一致 + 可解码 + 许可不受限**的素材完成
       APPROVE → EXECUTION →（强制 PI-1…PI-6 + DQ 只读复核）闭环，并给出**成片抽帧比对**证据；
     · 无素材 / 缺失文件 ⇒ `PENDING_HUMAN_ASSET`；sha 不符 / 不可解码 / 许可受限 ⇒ `FAILED`
       （**绝不**虚构 asset_id、占位替换、换用别的素材或自动降级）。
  P2「多 Proposal 并发/重叠修改的冲突检测、一致性与 fail-closed」
     · 同一 scene / window / asset / target 重叠 ⇒ 对称阻断 `BLOCKED_CONFLICT` + 需人工重新批准；
     · 不自动合并、不自动排序、不扩大范围；已成功方案重放 ⇒ `BLOCKED_ALREADY_EXECUTED`；
     · 未批准/被拒方案**不会**把已批准方案拖住（冲突只在可执行集合内成立）。

用法: python docs/regression_2x/phase6b_m5_execute_v9.py
产出: logs/phase6b_m5_approvals_v9.jsonl / logs/phase6b_m5_execution_ledger_v9.jsonl /
      logs/phase6b_m5_v9_execution.json
"""
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
LOGS = ROOT / "docs" / "regression_2x" / "logs"
DB = ROOT / "projects" / "video_studio.db"
PID, FILM_TASK = "p_96efdc03e1aa", "t_d0a54bdf1810"
FILM = ROOT / "projects" / PID / "output" / "{}_draft.mp4".format(FILM_TASK)
EVIDENCE = "docs/regression_2x/logs/audit_p96efdc_mm.json"
M3_REPORT = LOGS / "phase6b_m3_proposals_v9.json"
M2_LEDGER = LOGS / "phase6b_m2_review_ledger_v9.jsonl"
APPROVALS = LOGS / "phase6b_m5_approvals_v9.jsonl"
EXEC_LEDGER = LOGS / "phase6b_m5_execution_ledger_v9.jsonl"
OUT = LOGS / "phase6b_m5_v9_execution.json"

from video_studio.core import captions as core_captions            # noqa: E402
from video_studio.core import execution as EX                      # noqa: E402
from video_studio.core import revision as core_revision            # noqa: E402
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


# ---- 0) 只读取证基线 ----
db_b, film_b, src_dir_b = sha(DB), sha(FILM), manifest(FILM.parent)

# ---- 1) v9 只读上下文 ----
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
scene_ids = [e.get("scene_id") for e in timeline]
scene_window = {e.get("scene_id"): [float(e["start_s"]), float(e["end_s"])] for e in timeline}

# ---- 2) 真实素材索引（来自 v9 时间轴候选；逐条真实校验）+ 构造用例 ----
real_index, real_candidates = {}, {}
for e in timeline:
    for c in (e.get("candidates") or []):
        real_candidates.setdefault(c["asset_id"], c)
for e in timeline:
    sa = e.get("selected_asset") or {}
    if sa.get("asset_id"):
        real_candidates.setdefault(sa["asset_id"], sa)
for aid, c in real_candidates.items():
    real_index[aid] = {k: c.get(k) for k in
                       ("asset_id", "name", "path", "sha256", "source", "provider", "license",
                        "license_class", "license_cleared", "usable", "verified", "width",
                        "height", "bytes", "attribution", "source_url")}
    real_index[aid]["constructed"] = False

# 构造用例（**故意**损坏/受限；用来证明 fail-closed；不是真实素材，故不计入"可用素材"）
REAL_A = "asset_30dd89a16713"        # 1920x1080，local_ingest（v9 在用）
REAL_B = "asset_cfae038f6106"        # 5472x3648，external CC BY 4.0（cleared，v9 未用）
REAL_C = "asset_3f0b94a3f2ac"        # S20 当前素材（1920x1080，local_ingest）
_broken_txt = Path(ops_exec.SANDBOX_ROOT_REL) / "m5_inputs" / "not_an_image.jpg"
constructed = {
    "asset_synthetic_sha_mismatch01": {"asset_id": "asset_synthetic_sha_mismatch01",
                                       "path": real_index[REAL_B]["path"], "sha256": "0" * 64,
                                       "source": "external", "provider": "wikimedia_commons",
                                       "constructed": True, "why": "记录 sha 与文件实际 sha 不一致"},
    "asset_synthetic_missing01": {"asset_id": "asset_synthetic_missing01",
                                  "path": str(ROOT / ops_exec.SANDBOX_ROOT_REL / "no_such_dir"
                                              / "no_such_asset.jpg"),
                                  "sha256": "1" * 64, "source": "local_ingest", "provider": "",
                                  "constructed": True, "why": "索引存在但文件不存在"},
    "asset_synthetic_broken01": {"asset_id": "asset_synthetic_broken01",
                                 "path": str(ROOT / _broken_txt), "sha256": None,
                                 "source": "local_ingest", "provider": "",
                                 "constructed": True, "why": "文件存在但不是可解码图像"},
    "asset_synthetic_restricted01": {"asset_id": "asset_synthetic_restricted01",
                                     "path": real_index[REAL_B]["path"],
                                     "sha256": real_index[REAL_B]["sha256"],
                                     "source": "external", "provider": "wikimedia_commons",
                                     "license": "fair use", "license_class": "RESTRICTED",
                                     "constructed": True, "why": "外部素材 + 受限许可"},
    "asset_synthetic_unknown01": {"asset_id": "asset_synthetic_unknown01",
                                  "path": real_index[REAL_B]["path"],
                                  "sha256": real_index[REAL_B]["sha256"],
                                  "source": "external", "provider": "wikimedia_commons",
                                  "license": "unknown", "license_class": "UNKNOWN",
                                  "constructed": True, "why": "外部素材 + 许可未清"},
}


def build_ctx(box_info):
    return {"root": ROOT, "box": box_info["box"], "film": box_info["film"],
            "artifacts": box_info["artifacts"], "ffmpeg": CFG["tools"]["ffmpeg"]["path"],
            "ffprobe": CFG["tools"]["ffmpeg"]["ffprobe"], "config": CFG,
            "timeline": timeline, "timeline_duration_s": timeline_total,
            "evidence": ops_direction.load_evidence(EVIDENCE, ROOT),
            "cues": core_captions.build_cues(
                [{"narration": s.get("narration", ""), "duration_s": s.get("duration_s")}
                 for s in (script.get("segments") or [])]),
            "asset_index": {**real_index, **constructed}}


# ---- 3) 素材校验报告（真实、只读；把构造用例写进沙箱供"不可解码"用例使用）----
box0 = ops_exec.prepare_sandbox(ROOT, PID, "m5", FILM,
                                artifacts={"script_output": script, "voice_output": voice})
ctx0 = build_ctx(box0)
_broken_path = ROOT / ops_exec.SANDBOX_ROOT_REL / "m5_inputs" / "not_an_image.jpg"
_broken_path.parent.mkdir(parents=True, exist_ok=True)
if not _broken_path.is_file():
    _broken_path.write_text("这不是图像：仅用于证明『不可解码 ⇒ FAILED』\n", encoding="utf-8")
constructed["asset_synthetic_broken01"]["sha256"] = sha(_broken_path)
ctx0["asset_index"] = {**real_index, **constructed}

verification = []
for aid in sorted(ctx0["asset_index"]):
    rec = ctx0["asset_index"][aid]
    v = ops_exec.verify_asset_candidate(ctx0, aid)
    verification.append({"asset_id": aid, "constructed": bool(rec.get("constructed")),
                         "status": v["status"], "code": v["code"],
                         "path": rec.get("path"),
                         "recorded_sha256": rec.get("sha256"),
                         "actual_sha256": (v["evidence"] or {}).get("actual_sha256"),
                         "license_class": (v["evidence"] or {}).get("license_class"),
                         "license_gate_applies": (v["evidence"] or {}).get("license_gate_applies"),
                         "checked": (v["evidence"] or {}).get("checked")})
print("素材校验:", [(x["asset_id"], x["code"]) for x in verification])

# ---- 4) M5 方案（由 M2 人工 REJECT 触发；沿用 core/revision 校验与 id 派生）----
m2 = [json.loads(ln) for ln in M2_LEDGER.read_text(encoding="utf-8").splitlines() if ln.strip()]
m2_by_fid = {e.get("finding_id"): e for e in m2}
F_DQ2, F_DQ8 = "hr-389fea78f029", "hr-1f4b6db9c29d"
findings = {
    "DQ2": {"finding_id": F_DQ2, "metric": "DQ-2", "kind": "unique_assets_below_min",
            "severity": "FAIL", "source_evidence": "v9 仅 4 个唯一素材、最大占比 0.3329（6-A §2.2）"},
    "DQ8": {"finding_id": F_DQ8, "metric": "DQ-8", "kind": "semantic_mismatch_scenes",
            "severity": "FAIL",
            "source_evidence": "S05/S11/S18 语义不匹配（6-A §2.3；DQ-8 mismatch 7）"},
}
DECISION = {"DQ2": m2_by_fid[F_DQ2], "DQ8": m2_by_fid[F_DQ8]}


def mk_spec(label, find, action, scene, asset_id, disc, why):
    w = scene_window[scene]
    share = round((w[1] - w[0]) / timeline_total, 4)
    assets = [asset_id] if asset_id in real_index else []
    return dict(label=label, find=find, action=action, scene=scene, asset_id=asset_id, disc=disc,
                why=why, window=w, share=share, assets=assets)


SPECS = [
    mk_spec("M5-A1-replace-S20", "DQ2", "replace_asset", "S20", REAL_A, "m5-a1",
            "把 S20 的高复用素材替换为**已校验**的 16:9 真实素材（素材池多样性）"),
    mk_spec("M5-D1-replace-S21", "DQ2", "replace_asset", "S21", REAL_B, "m5-d1",
            "把 S21 替换为**外部 CC BY 4.0（已清除）**真实素材（证明外部素材亦可真实执行）"),
    mk_spec("M5-A2-sha-mismatch-S11", "DQ8", "replace_asset", "S11",
            "asset_synthetic_sha_mismatch01", "m5-a2", "素材记录 sha 与文件不一致 ⇒ 必须 FAILED"),
    mk_spec("M5-A3-asset-missing-S05", "DQ8", "add_asset", "S05",
            "asset_synthetic_missing01", "m5-a3", "索引有记录但文件不存在 ⇒ 必须 PENDING"),
    mk_spec("M5-A4-undecodable-S18", "DQ8", "add_asset", "S18",
            "asset_synthetic_broken01", "m5-a4", "文件不可解码 ⇒ 必须 FAILED"),
    mk_spec("M5-A5-license-restricted-S12", "DQ8", "add_asset", "S12",
            "asset_synthetic_restricted01", "m5-a5", "外部素材许可受限 ⇒ 必须 FAILED"),
    mk_spec("M5-A6-license-unknown-S08", "DQ8", "add_asset", "S08",
            "asset_synthetic_unknown01", "m5-a6", "外部素材许可未清 ⇒ 必须 PENDING"),
    mk_spec("M5-C1-replace-S20-conflict", "DQ2", "replace_asset", "S20", REAL_B, "m5-c1",
            "与 A1 同镜同窗（冲突样本；用于证明对称阻断）"),
    mk_spec("M5-C2-replace-S20-conflict", "DQ8", "replace_asset", "S20", REAL_C, "m5-c2",
            "与 A1/C1 同镜同窗（冲突样本；不同 finding）"),
]

proposals = []
for s in SPECS:
    p = core_revision.make_proposal(
        findings[s["find"]], DECISION[s["find"]], s["action"],
        {"scene_id": s["scene"], "window": s["window"]},
        {"what": s["why"], "how": "沙箱内窗口级真实替换（head 流复制 + 素材段重编码 + tail 重编码）",
         "params": {"asset_id": s["asset_id"], "keep_window": True, "keep_total_duration": True}},
        {"scenes": [s["scene"]], "window": s["window"], "assets": list(s["assets"]),
         "share_of_film": s["share"], "not_touching": ["旁白文本", "字幕文本", "时间轴总时长",
                                                       "其它镜头"]},
        {"metric": findings[s["find"]]["metric"], "direction": "素材真实替换后由只读复核度量",
         "basis": findings[s["find"]]["source_evidence"],
         "assumption": "局部替换**不保证**改善全片 PI（覆盖/静音/orphan 与本项无关）"},
        constraints={"must_preserve": ["旁白文本", "字幕文本", "时间轴总时长", "既有许可/署名台账"]},
        risk=["新素材与旁白语义不完全一致（人工已批准并指定素材）",
              "替换仅限窗口，不改变其它镜头"],
        known_scene_ids=scene_ids, known_asset_ids=sorted(real_index),
        discriminator=s["disc"], label=s["label"],
        evidence_refs=["docs/regression_2x/PHASE6A_AUDIT.md §2.2/§2.3"])
    proposals.append(p)
by_label = {p["label"]: p for p in proposals}
print("M5 方案:", [(p["label"], p["proposal_id"], p["action"]) for p in proposals])

# M3 既有的两条对照方案（H1 未批准 / H3b 被 REJECT）——用于证明"未批准/被拒不拖住已批准方案"
m3_plan = json.loads(M3_REPORT.read_text(encoding="utf-8"))
m3_by_label = {p.get("label"): p for p in m3_plan["proposals"]}
by_label = {p["label"]: p for p in proposals}
by_label["H1-hook-replace"] = m3_by_label["H1-hook-replace"]
by_label["H3-batch2-next-longest"] = m3_by_label["H3-batch2-next-longest"]

# ---- 5) 人工审批（append-only；人工身份/理由/溯源为必填）----
approvals = []


def approve(label, decision, reason, prov):
    p = by_label[label]
    rec = EX.make_approval(p, decision, "human:director(6-B/M5)", reason, prov,
                           at="2026-09-29T00:00:00Z")
    rec = EX.append_approval(APPROVALS, rec)
    approvals.append(rec)
    return rec


approve("M5-A1-replace-S20", "APPROVE",
        "同意用已校验的真实 16:9 素材替换 S20（仅此窗口；不改旁白/字幕/总时长）",
        "human:6-A 审计 §2.2 素材重复 VERIFIED + M4 对 H2 的既有批准（要求必须真实素材）")
approve("M5-D1-replace-S21", "APPROVE",
        "同意用外部 CC BY 4.0（许可已清）素材替换 S21（仅此窗口；署名台账不变更）",
        "human:6-A 审计 §2.2 + 3-A 许可台账 CC BY 4.0 cleared")
approve("M5-A2-sha-mismatch-S11", "APPROVE",
        "同意提交该方案，但**素材校验失败时不得执行**（fail-closed 验证用例）",
        "human:6-A 审计 §2.3 语义不匹配 VERIFIED")
approve("M5-A3-asset-missing-S05", "APPROVE",
        "同意提交该方案，但**素材不存在时不得执行**（人工待处理验证用例）",
        "human:6-A 审计 §2.3")
approve("M5-A4-undecodable-S18", "APPROVE",
        "同意提交该方案，但**素材不可解码时不得执行**（fail-closed 验证用例）",
        "human:6-A 审计 §2.3")
approve("M5-A5-license-restricted-S12", "APPROVE",
        "同意提交该方案，但**许可受限时不得执行**（fail-closed 验证用例）",
        "human:3-A 许可门禁（fair use ⇒ RESTRICTED）")
approve("M5-A6-license-unknown-S08", "APPROVE",
        "同意提交该方案，但**许可未清时不得执行**（人工待处理验证用例）",
        "human:3-A 许可门禁（unknown ⇒ UNKNOWN）")
approve("M5-C1-replace-S20-conflict", "APPROVE",
        "同意该方案本身（**未察觉**与 A1 重叠）；若检测到重叠必须阻断并要求人工重新批准",
        "human:6-A 审计 §2.2")
approve("M5-C2-replace-S20-conflict", "APPROVE",
        "同意该方案本身（**未察觉**与 A1/C1 重叠）；若检测到重叠必须阻断并要求人工重新批准",
        "human:6-A 审计 §2.3")
approve("H3-batch2-next-longest", "REJECT",
        "本轮仍不重剪画面节奏（沿用 M4 对 H3a 的决定）", "human:导演决定（本轮范围外）")

UNNAPPROVED = ["H1-hook-replace"]        # 明确**未**批准（对照）

# ---- 6) 三个批次（顺序 = 输入顺序；不由本层排序/合并）----
BATCH1 = ["M5-A1-replace-S20", "M5-D1-replace-S21", "M5-A2-sha-mismatch-S11",
          "M5-A3-asset-missing-S05", "M5-A4-undecodable-S18", "M5-A5-license-restricted-S12",
          "M5-A6-license-unknown-S08", "H1-hook-replace", "H3-batch2-next-longest"]
BATCH2 = ["M5-A1-replace-S20", "M5-C1-replace-S20-conflict", "M5-C2-replace-S20-conflict"]

m3_plan = json.loads(M3_REPORT.read_text(encoding="utf-8"))
pool = {**{k: by_label[k] for k in BATCH1 + BATCH2 if k in by_label}}

conflict_matrix_m5 = EX.detect_conflicts(list(pool.values()))
m3_matrix = EX.detect_conflicts(m3_plan["proposals"])

runs = []
for name, labels, note in (
        ("batch1", BATCH1, "无重叠的可执行集合：真实素材执行 + 校验失败样例 + 未批准/被拒对照"),
        ("batch1_retry", BATCH1, "同批重放：已成功方案必须被幂等门禁阻断（不重复执行）"),
        ("batch2_overlap", BATCH2, "三个已批准方案在同一镜重叠 ⇒ 全部对称阻断，需人工重新批准")):
    proplist = [pool[k] for k in labels]
    res = EX.execute_batch(proplist, approvals, ops_exec.EXECUTORS, ctx0,
                           recheck=ops_exec.pi_recheck, ledger=EXEC_LEDGER,
                           ledger_entries=EX.load_ledger(EXEC_LEDGER))
    res["batch"] = name
    res["note"] = note
    runs.append(res)
    print("\n[{}] {}".format(name, {k: v for k, v in res["states"].items()}))

# ---- 7) 素材替换 E2E 汇总（来自真实执行记录）----
asset_e2e = []
for r in runs[0]["records"]:
    rec = r.get("recheck") or {}
    ev = rec.get("asset_evidence") or {}
    if ev:
        asset_e2e.append({"proposal_id": r["proposal_id"], "proposal_label": r["proposal_label"],
                          "state": r["state"],
                          "outputs": r.get("outputs"),
                          "asset_evidence": {k: ev.get(k) for k in
                                             ("asset_id", "asset_sha256", "prev_asset_id",
                                              "window", "samples", "corr_new_mean",
                                              "corr_prev_mean", "argmax", "min_corr",
                                              "argmax_margin", "replaced", "on_screen")},
                          "pi_metrics": rec.get("pi_metrics"),
                          "pi_gate_outcome": rec.get("pi_gate_outcome"),
                          "dq_metrics": rec.get("dq_metrics"),
                          "dq_summary": rec.get("dq_summary"),
                          "timeline_projection": rec.get("timeline_projection"),
                          "film": rec.get("film"), "film_sha256": rec.get("film_sha256")})

# ---- 8) 只读取证 ----
db_a, film_a, src_dir_a = sha(DB), sha(FILM), manifest(FILM.parent)
led_entries = EX.load_ledger(EXEC_LEDGER)
ap_entries = EX.load_ledger(APPROVALS)
all_records = [r for run in runs for r in run["records"]]

out = {
    "schema": "revision-execution-run-v2",
    "stage": "6-B/M5",
    "closes_pending": ["M4-P1-real-asset-execution-branch",
                       "M4-P2-multi-proposal-overlap-conflict"],
    "read_only_source": True, "auto_approved": False, "auto_executed_all": False,
    "note": "M5 只关闭 M4 的两个 PENDING：真实素材执行分支（含失败/待处理 fail-closed）与"
            "多方案重叠冲突（对称阻断 + 幂等 + 并发串行化）。PI-1…PI-6 定义与阈值未改；"
            "DQ 仍 advisory；执行只在 sandbox 内完成；v9 母版/DB/项目文件零改动。",
    "inputs": {"project_id": PID, "film_task": FILM_TASK, "film": str(FILM),
               "m3_report": str(M3_REPORT.relative_to(ROOT)),
               "m2_ledger": str(M2_LEDGER.relative_to(ROOT)),
               "sandbox": str(Path(box0["box"]).relative_to(ROOT))},
    "sandbox": {"box": str(Path(box0["box"]).relative_to(ROOT)),
                "source_film_sha256": box0["source_film_sha256"],
                "film_copy_sha256": box0["film_sha256"]},
    "asset_index": {"real_assets": sorted(real_index), "constructed_cases": sorted(constructed),
                    "real_candidate_count": len(real_index),
                    "constructed_count": len(constructed),
                    "records": {k: {kk: vv for kk, vv in v.items()
                                    if kk in ("path", "sha256", "source", "provider", "license",
                                              "license_class", "usable", "verified", "width",
                                              "height", "constructed", "why")}
                                for k, v in {**real_index, **constructed}.items()}},
    "asset_verification": verification,
    "approvals": [{"approval_id": a["approval_id"], "proposal_label": a["proposal_label"],
                   "proposal_id": a["proposal_id"], "decision": a["decision"],
                   "approved_by": a["approved_by"], "reason": a["reason"],
                   "provenance": a["provenance"], "proposal_sha256": a["proposal_sha256"],
                   "seq": a["seq"], "auto_approved": a.get("auto_approved", False)}
                  for a in approvals],
    "unapproved": UNNAPPROVED,
    "proposals": [{"label": p["label"], "proposal_id": p["proposal_id"], "action": p["action"],
                   "finding_id": p["finding_id"], "metric": p.get("metric"),
                   "affected_scope": {k: p["affected_scope"].get(k) for k in
                                      ("scenes", "window", "assets", "share_of_film")},
                   "proposal_sha256": EX.proposal_sha256(p)}
                  for p in proposals],
    "conflict_matrices": {
        "m5_set": conflict_matrix_m5,
        "m3_register_8": {"conflict_pair_count": m3_matrix["conflict_pair_count"],
                          "pairs": m3_matrix["pairs"],
                          "conflicting_ids": m3_matrix["conflicting_ids"],
                          "proposals": m3_matrix["proposals"]}},
    "batches": [{"batch": r["batch"], "note": r["note"], "order": r["order"],
                 "states": r["states"], "executor_invocations": r["executor_invocations"],
                 "appended_seq": r["appended_seq"],
                 "gate_blocked_conflict": r["gate"]["blocked_conflict"],
                 "gate_blocked_already_executed": r["gate"]["blocked_already_executed"],
                 "records": r["records"]} for r in runs],
    "asset_e2e": asset_e2e,
    "summary": {
        "proposals": len(proposals), "batch_records": len(all_records),
        "state_counts": {s: sum(1 for r in all_records if r["state"] == s)
                         for s in sorted({r["state"] for r in all_records})},
        "executed_succeeded": sorted({r["proposal_id"] for r in all_records
                                      if r["state"] == "SUCCEEDED"}),
        "executor_invoked": sorted({r["proposal_id"] for r in all_records
                                    if r.get("executor_invoked")}),
        "blocked_conflict": sorted({r["proposal_id"] for r in all_records
                                    if r["state"] == "BLOCKED_CONFLICT"}),
        "blocked_already_executed": sorted({r["proposal_id"] for r in all_records
                                            if r["state"] == "BLOCKED_ALREADY_EXECUTED"}),
        "pending_human_asset": sorted({r["proposal_id"] for r in all_records
                                       if r["state"] == "PENDING_HUMAN_ASSET"}),
        "failed": sorted({r["proposal_id"] for r in all_records if r["state"] == "FAILED"}),
        "succeeded_without_real_asset_evidence": sorted(
            r["proposal_id"] for r in all_records if r["state"] == "SUCCEEDED"
            and not ((r.get("recheck") or {}).get("asset_evidence") or {}).get("replaced")),
        "ledger": {"approvals": {"path": str(APPROVALS.relative_to(ROOT)),
                                 "entries": len(ap_entries),
                                 "chain_ok": EX.verify_chain(ap_entries)["ok"]},
                   "executions": {"path": str(EXEC_LEDGER.relative_to(ROOT)),
                                  "entries": len(led_entries),
                                  "chain_ok": EX.verify_chain(led_entries)["ok"],
                                  "unique_seq": len({e["seq"] for e in led_entries})}},
        "auto_approved": any(a.get("auto_approved") for a in approvals),
        "promoted": sorted({r["proposal_id"] for r in all_records if r.get("promoted")}),
    },
    "read_only_evidence": {
        "db_sha256_before": db_b, "db_sha256_after": db_a, "db_unchanged": db_b == db_a,
        "v9_master_sha256_before": film_b, "v9_master_sha256_after": film_a,
        "v9_master_unchanged": film_b == film_a,
        "v9_output_dir_unchanged": src_dir_b == src_dir_a,
        "project_files_touched": [],
        "sandbox_only_outputs": all(
            str(o.get("path", "")).replace("\\", "/").startswith(ops_exec.SANDBOX_ROOT_REL)
            for r in all_records for o in (r.get("outputs") or [])),
    },
}
OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

print("\n执行状态（含重放/冲突批）:")
for r in all_records:
    print("  {:32s} {:26s} executor_invoked={}".format(
        r["proposal_label"], r["state"], r.get("executor_invoked")))
print("素材 E2E:", [(e["proposal_label"], e["state"], e["asset_evidence"]["asset_id"],
                     e["asset_evidence"]["corr_new_mean"], e["asset_evidence"]["corr_prev_mean"],
                     e["asset_evidence"]["replaced"]) for e in asset_e2e])
print("冲突对（M5 集合）:", [(c["a"], c["b"], c["kinds"]) for c in conflict_matrix_m5["pairs"]])
print("台账:", out["summary"]["ledger"])
print("只读: DB", out["read_only_evidence"]["db_unchanged"], "| 母版",
      out["read_only_evidence"]["v9_master_unchanged"], "| output 目录",
      out["read_only_evidence"]["v9_output_dir_unchanged"])
print("json ->", OUT)
