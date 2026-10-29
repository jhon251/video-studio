# -*- coding: utf-8 -*-
"""Phase 13-D / P13-4：S05 REPLACE 修订候选（走 6-B/6-C **真实执行器**，沙箱 copy-on-write）。

- 批准：`logs/phase13c_approvals.jsonl`（`ap-0850dfa8c52f`，绑定 P7-6 提案 `bp-6320bf486a082901`）。
- **派生执行提案（设计决定，如实登记）**：6-B 执行器契约要求 `affected_scope.scenes` +
  `proposed_change.params.asset_id`，而 P7-6 提案**不含**这两个字段；其 `proposal_sha256` 已被批准绑定
  ⇒ **不得改动其内容**。故按 6-B 格式派生执行提案并把 `derived_from`（P7-6 id + sha256 + deterministic_hash）
  写入提案与批准记录，使两条绑定都可校验、可追溯。
- 输出：修订候选（沙箱内，**不覆盖母片/既有候选**）+ `asset_replacement_evidence`（replaced=true / 抽帧 corr）
  + PI 复核结果 + DQ 只读投影；产物 `logs/phase13d_p13_4.json`、`logs/phase13d_execution_ledger.jsonl`。
- 零 LLM、零网络；不改 DB 项目数据（执行器在沙箱内 copy-on-write）。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sqlite3
import sys
import time

ROOT = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.core import captions as core_captions                            # noqa: E402
from video_studio.core import execution as EX                                      # noqa: E402
from video_studio.ops import direction as ops_direction                            # noqa: E402
from video_studio.ops import execution as ops_exec                                 # noqa: E402

LOGS = ROOT / "docs" / "regression_2x" / "logs"
DB = ROOT / "projects" / "video_studio.db"
PID = "p_96efdc03e1aa"
FILM_TASK = "t_d0a54bdf1810"
FILM = ROOT / "projects" / PID / "output" / "{}_draft.mp4".format(FILM_TASK)
EVIDENCE = "docs/regression_2x/logs/audit_p96efdc_mm.json"
TARGET_76 = "bp-6320bf486a082901"
NEW_ASSET = "ast-92ca33138ffe64f4"
SCENE = "S05"
APPROVALS_76 = LOGS / "phase13c_approvals.jsonl"
APPROVALS_D = LOGS / "phase13d_approvals.jsonl"
LEDGER_D = LOGS / "phase13d_execution_ledger.jsonl"
OUT = LOGS / "phase13d_p13_4.json"
CFG = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8"))


def payload(atype, task=None):
    con = sqlite3.connect("file:" + DB.as_posix() + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    rows = [dict(r) for r in con.execute(
        "select type,task_id,path,artifact_id from artifacts where project_id=? and type=? "
        "order by created_at", (PID, atype))]
    con.close()
    rec = next((x for x in rows if task and x["task_id"] == task), rows[-1] if rows else None)
    if not rec:
        return {}, None
    return json.loads(pathlib.Path(rec["path"]).read_text(encoding="utf-8")), rec


script, _ = payload("script_output")
voice, _ = payload("voice_output")
render, _ = payload("render_output", FILM_TASK)
timeline = render.get("material_timeline") or []
timeline_total = float((render.get("duration_contract") or {}).get("timeline_duration_s") or 1532.0)
print("script/voice/render 就绪 | 场景:", len(timeline), "| timeline_total:", timeline_total,
      "| FILM 存在:", FILM.is_file(), FILM.stat().st_size // 1024 // 1024 if FILM.is_file() else 0, "MB")

real_index, cand_of_scene = {}, {}
for e in timeline:
    for c in (e.get("candidates") or []):
        real_index.setdefault(c["asset_id"], c)
        cand_of_scene.setdefault(str(e.get("scene_id")), []).append(c)
for e in timeline:
    sa = e.get("selected_asset") or {}
    if sa.get("asset_id"):
        real_index.setdefault(sa["asset_id"], sa)
# **补全素材注册表**：并入 P7-2 权威索引（含 ast-* 宇宙），并套用 Phase 12 许可覆盖层
p72 = json.loads((LOGS / "asset_index.json").read_text(encoding="utf-8"))
overlay = json.loads((LOGS / "license_overlay_v1.json").read_text(encoding="utf-8"))
ov_by_id = {e["asset_id"]: e for e in overlay["entries"]}
for c in p72.get("candidates") or []:
    row = dict(c)
    ov = ov_by_id.get(row["asset_id"]) or {}
    if ov.get("state") == "HAS_RECORD":
        row["license"] = ov["license"]
        row["license_class"] = ov["license_class"]
        row["license_provenance"] = {"source_of_record": ov.get("source_of_record"),
                                     "overlay_artifact_hash": overlay.get("artifact_hash")}
    real_index.setdefault(row["asset_id"], row)
print("asset_index:", len(real_index), "（含 P7-2 索引并入）| 索引中有新素材:",
      NEW_ASSET in real_index)
new_asset = real_index.get(NEW_ASSET) or {}
print("新素材:", json.dumps({k: new_asset.get(k) for k in ("asset_id", "path", "sha256",
                                                          "license", "license_class")},
                            ensure_ascii=False)[:200])

# ---- 派生执行提案（不改 P7-6 内容）----
p76 = next(p for p in json.loads((LOGS / "visual_binding_proposals.json").read_text(
    encoding="utf-8"))["proposals"] if p["proposal_id"] == TARGET_76)
p76_sha = EX.proposal_sha256(p76)
exec_prop = {
    "schema": "revision-proposal-v1",
    "proposal_id": "bp-" + hashlib.sha256("|".join([TARGET_76, SCENE, NEW_ASSET]).encode()).hexdigest()[:16],
    "label": "13D-S05-replace-russell",
    "action": "replace_asset",
    "affected_scope": {"scenes": [SCENE], "assets": [NEW_ASSET]},
    "target": {"windows": []},
    "proposed_change": {"type": "replace_asset", "params": {"asset_id": NEW_ASSET}},
    "derived_from": {"proposal_id": TARGET_76, "proposal_sha256": p76_sha,
                     "deterministic_hash": p76.get("deterministic_hash"),
                     "note": "P7-6 提案内容**未改动**；本提案补足 6-B 执行器所需 affected_scope/proposed_change"},
    "finding_id": None, "decision_ref": None,
}
print("派生执行提案:", exec_prop["proposal_id"], "| derived_from:", TARGET_76)

box = ops_exec.prepare_sandbox(ROOT, PID, "13d", FILM,
                               artifacts={"script_output": script, "voice_output": voice})
print("沙箱:", box["box"], "| 母片 sha256:", box["source_film_sha256"][:16],
      "| 沙箱副本:", box["film_sha256"][:16])


def build_ctx(film: pathlib.Path, tl: list, bindings: dict) -> dict:
    return {"root": ROOT, "box": box["box"], "film": film, "artifacts": box["artifacts"],
            "files": box["files"], "ffmpeg": CFG["tools"]["ffmpeg"]["path"],
            "ffprobe": CFG["tools"]["ffmpeg"]["ffprobe"], "config": CFG,
            "timeline": tl, "timeline_duration_s": timeline_total,
            "evidence": ops_direction.load_evidence(EVIDENCE, ROOT),
            "cues": core_captions.build_cues(
                [{"narration": s.get("narration", ""), "duration_s": s.get("duration_s")}
                 for s in (script.get("segments") or [])]),
            "asset_index": real_index, "asset_bindings": bindings}


BINDINGS = {exec_prop["proposal_id"]: {"S05": NEW_ASSET}}
_ap = EX.make_approval(
    exec_prop, "APPROVE", "human:project-owner",
    "批准 S05 修订执行（派生自 " + TARGET_76 + "）：以 Russell 页替换 S05 素材，时长/字幕/响度守恒",
    "Phase 13-C 授权书 §0 + 用户消息（human:project-owner 签发；授权 Agent 经 6-B 链转录登记）; "
    "派生自 " + TARGET_76 + "（sha256 " + p76_sha[:16] + "…，批准 ap-0850dfa8c52f）",
    at="2026-09-30T03:05:00Z")
_ap["approval_document"] = "Phase 13-C 授权书 §0 + 本消息（human:project-owner 签发）"
_ap["recorded_by"] = "agent:transcription（人工书面授权转录；非代写）"
approvals_d = [EX.append_approval(APPROVALS_D, _ap)]
chk = EX.verify_approval(exec_prop, approvals_d[0])
print("派生批准:", approvals_d[0]["approval_id"], "| 绑定校验:", json.dumps(chk, ensure_ascii=False))

ctx = build_ctx(box["film"], timeline, BINDINGS)
t0 = time.time()
res = EX.execute_batch([exec_prop], approvals_d, ops_exec.EXECUTORS, ctx,
                       recheck=ops_exec.pi_recheck, ledger=LEDGER_D, ledger_entries=[])
rec = res["records"][0]
print("执行状态:", rec.get("state"), "| 耗时 %.1fs" % (time.time() - t0))
cand = (rec.get("outputs") or {}).get("candidate") or rec.get("candidate")
ev = rec.get("exec_evidence") or {}
summary = {
    "schema": "phase13d-p13-4-v1",
    "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "approval_of_record": "logs/phase13c_approvals.jsonl#ap-0850dfa8c52f（绑定 P7-6 提案 " + TARGET_76 + "）",
    "executor_proposal": {k: exec_prop[k] for k in ("proposal_id", "label", "action",
                                                    "affected_scope", "proposed_change",
                                                    "derived_from")},
    "execution_state": rec.get("state"),
    "executor_invoked": rec.get("executor_invoked"),
    "blocking": rec.get("blocking") if "blocking" in rec else None,
    "pi_gate_outcome": rec.get("pi_gate_outcome"),
    "recheck": rec.get("recheck"),
    "sandbox": {"box": str(box["box"]), "source_film_sha256": box["source_film_sha256"]},
    "candidate": cand,
    "asset_evidence": (ev.get("asset_evidence") if isinstance(ev, dict) else None) or ev,
    "record": rec,
}
OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=1, sort_keys=True, default=str),
               encoding="utf-8")
print("产物:", OUT.name)
print("PI:", json.dumps(rec.get("pi_gate_outcome"), ensure_ascii=False)[:200])
ae = summary["asset_evidence"] or {}
if isinstance(ae, dict):
    print("replaced:", ae.get("replaced"), "| 素材:", ae.get("asset_id"),
          "| corr:", json.dumps({k: v for k, v in ae.items() if "corr" in k}, ensure_ascii=False)[:160])
print("候选:", json.dumps(cand, ensure_ascii=False, default=str)[:220])
