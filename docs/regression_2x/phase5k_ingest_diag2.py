# -*- coding: utf-8 -*-
"""5-K 诊断（只读）：claim 闸门状态 + 最近 changelog（定位 run_ingest_test 停点）。

用法: python docs/regression_2x/phase5k_ingest_diag2.py <project_id>
产出: docs/regression_2x/logs/phase5k_ingest_diag2.json
"""
import json
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
DB = ROOT / "projects" / "video_studio.db"
LOGS = ROOT / "docs" / "regression_2x" / "logs"
pid = sys.argv[1] if len(sys.argv) > 1 else "p_943fff2250e5"

con = sqlite3.connect("file:{}?mode=ro".format(DB.as_posix()), uri=True)
out = {"project_id": pid}
ccols = [c[1] for c in con.execute("pragma table_info(claims)")]
print("claims cols:", ccols)
out["claims_cols"] = ccols
if "status" in ccols:
    out["claims_by_status"] = {r[0]: r[1] for r in con.execute(
        "select status, count(*) from claims where project_id=? group by status", (pid,))}
    print("claims by status:", out["claims_by_status"])
    notpass = [dict(zip(ccols, r)) for r in con.execute(
        "select * from claims where project_id=? and status not in ('VERIFIED','REJECTED')", (pid,))]
    out["claims_not_passed"] = [{k: str(v)[:120] for k, v in c.items()} for c in notpass]
    print("claims not passed:", len(notpass))
    for c in notpass[:10]:
        print("   ", {k: str(c.get(k))[:60] for k in ("claim_id", "status", "text", "kind") if k in c})
dcols = [c[1] for c in con.execute("pragma table_info(decisions)")]
print("decisions cols:", dcols)
sel = [c for c in ("decision_id", "scope", "subject", "decision", "decided_by", "reason", "created_at")
       if c in dcols]
if "project_id" in dcols and sel:
    d = [[str(x)[:120] for x in r] for r in con.execute(
        "select {} from decisions where project_id=? order by rowid desc limit 12".format(", ".join(sel)),
        (pid,))]
    out["recent_decisions"] = d
    print("recent decisions:", len(d))
    for r in d:
        print("   ", " | ".join(r))
lcols = [c[1] for c in con.execute("pragma table_info(changelog)")]
sel = [c for c in ("ts", "actor", "kind", "summary", "detail") if c in lcols]
if "project_id" in lcols and sel:
    lg = [[str(x)[:150] for x in r] for r in con.execute(
        "select {} from changelog where project_id=? order by rowid desc limit 12".format(", ".join(sel)),
        (pid,))]
    out["recent_changelog"] = lg
    print("recent changelog:", len(lg))
    for r in lg:
        print("   ", " | ".join(r))
con.close()
(LOGS / "phase5k_ingest_diag2.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                                encoding="utf-8")
print("json ->", LOGS / "phase5k_ingest_diag2.json")
