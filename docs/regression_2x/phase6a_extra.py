# -*- coding: utf-8 -*-
"""6-A 只读补充取证：片尾关键词命中、QA/合规/critic 裁决记录、多模态（4-B/5-A/5-D/Judge）汇总。"""
import json
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
PID = "p_96efdc03e1aa"
out = {}

# (a) 片尾关键词命中位置 + 最后两段文本
segs = None
for p in sorted((ROOT / "projects" / PID / "artifacts").glob("*.json")):
    d = json.loads(p.read_text(encoding="utf-8"))
    s = d.get("segments")
    if isinstance(s, list) and s and isinstance(s[0], dict) and "narration" in s[0] \
            and "duration_s" in s[0]:
        segs = s
        break
hits = []
for i, s in enumerate(segs, 1):
    for k in ("感谢", "订阅", "下期", "再见", "关注", "结束", "总结", "最后"):
        if k in s.get("narration", ""):
            hits.append({"scene": i, "kw": k, "text": s["narration"][:60]})
out["outro_keyword_hits"] = hits
out["last_two_segments"] = [{"scene": len(segs) - 1, "text": segs[-2]["narration"][:110]},
                            {"scene": len(segs), "text": segs[-1]["narration"][:110]}]
out["script_time_of_last_segments"] = {
    "start_of_last_scene_s": round(sum(float(x.get("duration_s") or 0) for x in segs[:-1]), 1),
    "sum_script_s": round(sum(float(x.get("duration_s") or 0) for x in segs), 1)}

# (b) 与质量/合规/批评相关的裁决
con = sqlite3.connect("file:{}?mode=ro".format((ROOT / "projects" / "video_studio.db").as_posix()),
                      uri=True)
con.row_factory = sqlite3.Row
rows = [dict(r) for r in con.execute(
    "select decision_id, node, made_by, state, substr(rationale,1,140) as rationale, created_at "
    "from decisions where project_id=? order by created_at", (PID,))]
out["decision_nodes"] = sorted({str(r["node"]) for r in rows})
out["quality_related_decisions"] = [r for r in rows
                                    if any(t in str(r["node"]) for t in
                                           ("critic", "qa", "compl", "final", "editing", "publish"))]
out["decision_count"] = len(rows)
# 任务级：critic/qa/compliance 的最终状态与错误
out["quality_tasks"] = [dict(r) for r in con.execute(
    "select task_id, task_type, status, retry_count, substr(error,1,120) as error, approval "
    "from tasks where project_id=? and task_type in ('critic_final','qa','compliance','analyst',"
    "'metadata','platform','thumbnail') order by created_at", (PID,))]
# 事件里是否有任何 BLOCKED/失败与本片音旁白/静音相关
out["blocked_events"] = [dict(r) for r in con.execute(
    "select event_id, type, actor, task_id, substr(payload,1,160) as payload from events "
    "where project_id=? and type in ('TASK_BLOCKED','TASK_FAILED') order by event_id", (PID,))]
con.close()

# (c) 多模态只读证据（2026-09-21 审计产物）
p = ROOT / "docs" / "regression_2x" / "logs" / "audit_p96efdc_mm.json"
if p.is_file():
    mm = json.loads(p.read_text(encoding="utf-8"))
    summ = {}
    for k, v in mm.items():
        if isinstance(v, dict) and any(t in k.lower() for t in ("4b", "5a", "5d", "judge",
                                                                "text", "frame", "temporal")):
            summ[k] = {kk: vv for kk, vv in list(v.items())[:8]
                       if not isinstance(vv, (list,)) or len(str(vv)) < 200}
    out["multimodal_keys"] = list(mm.keys())
    out["multimodal_summary"] = json.dumps(summ, ensure_ascii=False)[:1500]
    for k in ("summary", "counts", "aggregate"):
        if isinstance(mm.get(k), dict):
            out["multimodal_" + k] = mm[k]
(ROOT / "docs" / "regression_2x" / "logs" / "phase6a_extra.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print("outro keyword hits:", json.dumps(out["outro_keyword_hits"], ensure_ascii=False)[:400])
print("last scene text:", out["last_two_segments"][-1]["text"][:100])
print("script time of last scene start:", out["script_time_of_last_segments"])
print("decision nodes:", out["decision_nodes"][:12])
print("quality-related decisions:", json.dumps(out["quality_related_decisions"], ensure_ascii=False)[:700])
print("quality tasks:", json.dumps(out["quality_tasks"], ensure_ascii=False)[:600])
print("blocked/failed events:", len(out["blocked_events"]),
      json.dumps(out["blocked_events"][:2], ensure_ascii=False)[:300])
print("multimodal keys:", out["multimodal_keys"])
print("multimodal summary:", out.get("multimodal_summary", "")[:600])
print("json -> docs/regression_2x/logs/phase6a_extra.json")
