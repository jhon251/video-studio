"""3.x Phase 1 Part A driver: ONE real-API run with full evidence collection.

- uses config/config.real.json (MockLLM disabled; mock config untouched)
- per round: record claim statuses BEFORE approving (claim-gate evidence), record NEEDS_REVIEW
  (HITL evidence), print running cost from DB, approve, run
- after settle: per-task model/tokens/cost/retry/error + LLM_CALL event aggregation + content checks
- never fabricates success: FAILED/BLOCKED/PENDING are reported as such

Usage:
  python docs/regression_2x/run_real_test.py A          # run prompt A (black hole)
  python docs/regression_2x/run_real_test.py --report <project_id>
"""
import json
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
LOGS = ROOT / "docs" / "regression_2x" / "logs"
LOGS.mkdir(parents=True, exist_ok=True)
REAL_CFG = "config/config.real.json"
PROMPTS = json.loads((ROOT / "docs" / "regression_2x" / "prompts.json").read_text(encoding="utf-8"))


def clog(prefix, m):
    line = str(m)
    print(line, flush=True)
    with (LOGS / "real_{}.log".format(prefix)).open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def cli(*args, real=True):
    cmd = [sys.executable, "run.py"]
    if real:
        cmd += ["--config", REAL_CFG]
    cmd += list(args)
    p = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def rows(text, ch):
    return [[c.strip() for c in ln.split("|")] for ln in text.splitlines()
            if re.match(r"^\|\s*" + ch, ln)]


def db():
    con = sqlite3.connect(str(ROOT / "projects" / "video_studio.db"))
    con.row_factory = sqlite3.Row
    return con


def spent(pid):
    con = db()
    r = con.execute("select coalesce(sum(cost_usd),0) s, count(*) n from tasks where project_id=?",
                    (pid,)).fetchone()
    con.close()
    return float(r["s"]), int(r["n"])


def claim_gate_round(pid, prefix, i, claim_evidence):
    """Claim 闸门：只有全部 claim ∈ {VERIFIED, REJECTED} 才放行生产。

    注意：CLI 的"待人工"列只标注子集，但 claim_gate_open() 要求**全部** claim 已裁决，
    因此这里对任何非终态 claim 都执行人工裁决（否则生产任务永不派发）。
    """
    rc, cl = cli("claims", pid)
    for f in rows(cl, "c_"):
        if len(f) < 9:
            continue
        cid, status, verdict, nex = f[1], f[4], f[5], f[6]
        if status in ("VERIFIED", "REJECTED"):
            continue
        claim_evidence.append({"round": i, "claim_id": cid, "status": status,
                               "verdict": verdict, "evidence": nex, "flagged": bool(f[7])})
        cli("approve-claim", cid, "--comment", "3.x Phase1 A real run")
        clog(prefix, "  claim {} status={} verdict={} 待人工={} -> approve".format(
            cid, status, verdict, f[7] or "否"))


def run_prompt(key):
    spec = PROMPTS[key]
    prefix = "A_real" if key == "A" else "{}_real".format(key)
    rc, out = cli("init", spec["prompt"], "--name", spec["name"] + "_real")
    clog(prefix, "init -> " + out.strip())
    m = re.search(r"p_[0-9a-f]+", out)
    if not m:
        clog(prefix, "!! no project id")
        return None
    pid = m.group(0)
    rc, out = cli("plan", pid)
    clog(prefix, "plan -> " + out.strip())

    claim_evidence, hitl_evidence, errors = [], [], []
    redone_ids, redone_types = set(), set()
    for i in range(1, 41):
        claim_gate_round(pid, prefix, i, claim_evidence)
        rc, st = cli("status", pid)
        (LOGS / "{}_status_r{}.log".format(prefix, i)).write_text(st, encoding="utf-8")
        review, blocked, active, ok = [], [], 0, 0
        for f in rows(st, "t_"):
            if len(f) < 6:
                continue
            if f[4] == "NEEDS_REVIEW":
                review.append((f[1], f[2]))
            elif f[4] in ("PENDING", "READY", "RUNNING", "DISPATCHED"):
                active += 1
            elif f[4] == "SUCCEEDED":
                ok += 1
            elif f[4] in ("BLOCKED", "FAILED"):
                blocked.append((f[1], f[2], f[4], f[8] if len(f) > 8 else ""))
        s, _ = spent(pid)
        clog(prefix, "[round {}] ok={} review={} active={} blocked={} spent=${:.4f}".format(
            i, ok, len(review), active, len(blocked), s))
        for t, typ in review:
            hitl_evidence.append({"round": i, "task": t, "type": typ})
            cli("approve", t, "approve", "--comment", "3.x Phase1 A real run")
        if blocked:
            stop = False
            for t, typ, stt, err in blocked:
                errors.append({"task": t, "type": typ, "status": stt, "error": err})
                clog(prefix, "  BLOCKED {} {} {}: {}".format(t, typ, stt, err[:120]))
                key2 = (typ, stt)
                if key2 not in redone:
                    redone.add(key2)
                    cli("redo", t)
                    clog(prefix, "  redo {} (first time for type={})".format(t, typ))
                else:
                    clog(prefix, "  已重做过同类型任务仍失败 → 停止，交由人工")
                    stop = True
            if stop:
                clog(prefix, "  STOPPED: 存在无法自动恢复的失败")
                break
            continue
        if review:
            continue
        if active == 0:
            clog(prefix, "  settled")
            break
        rc, o2 = cli("run", pid)
        clog(prefix, "  run -> " + o2.strip().splitlines()[-1][:60])
    report(pid, prefix, claim_evidence, hitl_evidence, errors)
    return pid


def report(pid, prefix, claim_evidence=None, hitl_evidence=None, errors=None):
    con = db()
    tasks = [dict(r) for r in con.execute(
        "select task_id,task_type,agent_role,status,model_used,cost_usd,retry_count,max_retries,error"
        " from tasks where project_id=?", (pid,))]
    evs = [dict(r) for r in con.execute(
        "select type as event_type, actor as agent_role, task_id, payload, ts as created_at"
        " from events where project_id=? order by ts", (pid,))]
    con.close()
    calls = []
    for e in evs:
        if e["event_type"] == "LLM_CALL":
            try:
                calls.append(json.loads(e["payload"]) if isinstance(e["payload"], str) else e["payload"])
            except (json.JSONDecodeError, TypeError):
                pass
    tot_cost = sum(float(t["cost_usd"] or 0) for t in tasks)
    tot_tokens = sum(int(c.get("total_tokens") or 0) for c in calls)
    lat = [int(c.get("latency_ms") or 0) for c in calls]
    retries = [e for e in evs if e["event_type"] == "TASK_RETRYING"]
    failed = [e for e in evs if e["event_type"] in ("TASK_FAILED", "TASK_BLOCKED")]
    models = sorted({c.get("model") for c in calls if c.get("model")})
    mock_calls = [c for c in calls if c.get("mock")]
    rep = {"project": pid, "tasks": len(tasks), "llm_calls": len(calls),
           "models": models, "total_tokens": tot_tokens,
           "mock_calls": len(mock_calls),
           "total_cost_usd": round(tot_cost, 6),
           "latency_ms": {"min": min(lat) if lat else None, "max": max(lat) if lat else None,
                          "sum": sum(lat)},
           "attempts_gt1": [c for c in calls if int(c.get("attempts") or 1) > 1],
           "task_retries": len(retries), "task_failures": len(failed),
           "failed_tasks": [{"task": t["task_id"], "type": t["task_type"], "status": t["status"],
                             "error": (t["error"] or "")[:200]}
                            for t in tasks if t["status"] in ("FAILED", "BLOCKED")],
           "tasks_detail": [{"type": t["task_type"], "status": t["status"],
                             "model": t["model_used"], "cost": round(float(t["cost_usd"] or 0), 6),
                             "retry": t["retry_count"]} for t in tasks],
           "claim_gate_evidence": claim_evidence or [], "hitl_gate_evidence": hitl_evidence or [],
           "errors": errors or []}
    (LOGS / "real_{}_report.json".format(prefix)).write_text(
        json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    clog(prefix, "\n=== 汇总 ===")
    clog(prefix, "任务 {} | LLM 调用 {} | 模型 {} | 总 token {} | 总费用 ${:.4f}".format(
        rep["tasks"], rep["llm_calls"], models, tot_tokens, tot_cost))
    clog(prefix, "MockLLM 调用数 = {}（必须为 0，证明走的是真实 API）".format(rep["mock_calls"]))
    clog(prefix, "延迟 ms: min={} max={} sum={}".format(
        rep["latency_ms"]["min"], rep["latency_ms"]["max"], rep["latency_ms"]["sum"]))
    clog(prefix, "重试次数>1 的调用: {} | 任务级重试 {} | 任务级失败 {}".format(
        len(rep["attempts_gt1"]), rep["task_retries"], rep["task_failures"]))
    clog(prefix, "Claim 闸门证据 {} 条 | HITL 闸门证据 {} 条".format(
        len(rep["claim_gate_evidence"]), len(rep["hitl_gate_evidence"])))
    if rep["failed_tasks"]:
        clog(prefix, "失败任务: " + json.dumps(rep["failed_tasks"], ensure_ascii=False))
    return rep


def continue_project(pid, prefix="A_real_cont"):
    """Resume the approval/run loop for an existing project (no new init/plan; saves API cost)."""
    claim_evidence, hitl_evidence, errors = [], [], []
    redone_ids, redone_types = set(), set()
    for i in range(1, 41):
        claim_gate_round(pid, prefix, i, claim_evidence)
        rc, st = cli("status", pid)
        (LOGS / "{}_status_r{}.log".format(prefix, i)).write_text(st, encoding="utf-8")
        review, blocked, active, ok = [], [], 0, 0
        for f in rows(st, "t_"):
            if len(f) < 6:
                continue
            if f[4] == "NEEDS_REVIEW":
                review.append((f[1], f[2]))
            elif f[4] in ("PENDING", "READY", "RUNNING", "DISPATCHED"):
                active += 1
            elif f[4] == "SUCCEEDED":
                ok += 1
            elif f[4] in ("BLOCKED", "FAILED"):
                blocked.append((f[1], f[2], f[4], f[8] if len(f) > 8 else ""))
        s, _ = spent(pid)
        clog(prefix, "[round {}] ok={} review={} active={} blocked={} spent=${:.4f}".format(
            i, ok, len(review), active, len(blocked), s))
        for t, typ in review:
            hitl_evidence.append({"round": i, "task": t, "type": typ})
            cli("approve", t, "approve", "--comment", "3.x Phase1 A real run")
        if blocked:
            stop, need_run = False, False
            for t, typ, stt, err in blocked:
                errors.append({"task": t, "type": typ, "status": stt, "error": err})
                clog(prefix, "  BLOCKED {} {} {}: {}".format(t, typ, stt, err[:140]))
                if t in redone_ids:
                    continue                       # 已被 redo 取代的旧任务，忽略
                if typ in redone_types:
                    clog(prefix, "  同类型任务重做后仍失败 → 停止，交由人工（{}）".format(typ))
                    stop = True
                    continue
                redone_ids.add(t)
                redone_types.add(typ)
                cli("redo", t)
                clog(prefix, "  redo {} (type={} 首次重做)".format(t, typ))
                need_run = True
            if stop:
                clog(prefix, "  STOPPED: 存在无法自动恢复的失败")
                break
            # 重做后继续往下走，让新版本任务被执行
        if review:
            continue
        if active == 0:
            clog(prefix, "  settled")
            break
        rc, o2 = cli("run", pid)
        clog(prefix, "  run -> " + o2.strip().splitlines()[-1][:60])
    return report(pid, prefix, claim_evidence, hitl_evidence, errors)


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--report":
        report(sys.argv[2], "manual")
    elif len(sys.argv) >= 3 and sys.argv[1] == "--continue":
        continue_project(sys.argv[2])
    else:
        key = sys.argv[1] if len(sys.argv) > 1 else "A"
        run_prompt(key)
