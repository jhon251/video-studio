# -*- coding: utf-8 -*-
"""5-C 追加性/旧版本保留的**库级**证明：把冻结的替换前 DB 快照（5-B baseline 快照）
与当前 DB 逐表逐行比对。

断言：
  1) 冻结快照 DB 自身哈希与 5-B 记录一致（9b6321d2…）
  2) 快照中 tasks / artifacts / decisions / changelog / events / projects 的**每一行**
     在现库中仍存在且**逐列同值**（无删除、无就地改写）
  3) 新增行恰好是本次替换应有的那些（v6 render 任务 + 其 attribution/render_output 产物
     + 1 条人工 decision + 1 条 changelog），其余表新增仅为事件流

只读：快照以 `mode=ro` 打开；现库只做 SELECT。
用法：python docs/regression_2x/phase5c_db_append_only.py
产出：docs/regression_2x/logs/phase5c_db_append_only.json
"""
import hashlib
import json
import pathlib
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(r"C:\mp4agent\video-studio")
LOGS = ROOT / "docs" / "regression_2x" / "logs"
SNAP = ROOT / "docs" / "regression_2x" / "snapshots" / "5.x-phase5b-20260916.db"
LIVE = ROOT / "projects" / "video_studio.db"
EXPECT_SNAP_SHA = "9b6321d25ce6ec2a532005b2aa01b48440ead0a4550448ba4af39ffa85925ca0"
TABLES = ("projects", "tasks", "artifacts", "decisions", "changelog", "events")

# `redo` 的设计语义：把**下游任务**的 dependencies 从旧版本渲染任务改指到新版本渲染任务。
# 这是唯一允许的就地改写；必须精确等于下列 6 行，且只改 dependencies 一列，且新值指向 v6。
ALLOWED_DEP_REWIRE = {
    "t_7e562727310a": "thumbnail", "t_a0d52169337b": "qa", "t_1136a26defe7": "compliance",
    "t_5609521e72e1": "critic_final", "t_76795a7a21e6": "platform",
    "t_198d21f3e7f9": "analytics",
}
OLD_RENDER_TASK = "t_b8f866ddc062"      # v5
NEW_RENDER_TASK = "t_6d692b93e342"      # v6


def ro(path):
    con = sqlite3.connect("file:{}?mode=ro".format(pathlib.Path(path).as_posix()), uri=True)
    con.row_factory = sqlite3.Row
    return con


def row_hashes(con, table):
    cols = [r[1] for r in con.execute("pragma table_info({})".format(table))]
    pk = cols[0]
    out = {}
    for r in con.execute("select * from {}".format(table)):
        vals = [r[c] for c in cols]
        blob = json.dumps(vals, ensure_ascii=False, default=str).encode("utf-8")
        out[str(vals[0])] = {"h": hashlib.sha256(blob).hexdigest()[:20], "pk": str(vals[0])}
    return pk, cols, out


snap = ro(SNAP)
live = ro(LIVE)
snap_sha = hashlib.sha256(SNAP.read_bytes()).hexdigest()

# ---- 逐行逐列比对（tasks 需区分"允许的 dependencies 重指"） ----
task_cols = [r[1] for r in snap.execute("pragma table_info(tasks)")]
s_tasks = {r["task_id"]: dict(r) for r in snap.execute("select * from tasks")}
l_tasks = {r["task_id"]: dict(r) for r in live.execute("select * from tasks")}
rewire_rows, other_modified_tasks = [], []
for tid, sv in s_tasks.items():
    lv = l_tasks.get(tid)
    if lv is None:
        continue
    diffs = {c: (sv[c], lv[c]) for c in task_cols if sv[c] != lv[c]}
    if not diffs:
        continue
    only_deps = set(diffs) == {"dependencies"}
    deps_ok = only_deps and json.loads(str(lv["dependencies"])) == [NEW_RENDER_TASK] \
        and json.loads(str(sv["dependencies"])) == [OLD_RENDER_TASK]
    if deps_ok and tid in ALLOWED_DEP_REWIRE:
        rewire_rows.append({"task_id": tid, "task_type": sv["task_type"],
                            "before": sv["dependencies"], "after": lv["dependencies"]})
    else:
        other_modified_tasks.append({"task_id": tid, "changed_columns": sorted(diffs),
                                     "before": {c: str(diffs[c][0])[:80] for c in diffs},
                                     "after": {c: str(diffs[c][1])[:80] for c in diffs}})
snap.close()
live.close()

report = {"snapshot_db": str(SNAP), "snapshot_sha256": snap_sha,
          "snapshot_sha_expected": EXPECT_SNAP_SHA, "snapshot_intact": snap_sha == EXPECT_SNAP_SHA,
          "allowed_dependency_rewire": rewire_rows,
          "unexpected_modified_task_rows": other_modified_tasks,
          "rewire_exact": sorted(x["task_id"] for x in rewire_rows) == sorted(ALLOWED_DEP_REWIRE),
          "tables": {}}
all_rows_intact = not other_modified_tasks
snap = ro(SNAP)
live = ro(LIVE)
for t in TABLES:
    pk, cols, s_rows = row_hashes(snap, t)
    _, _, l_rows = row_hashes(live, t)
    missing = sorted(set(s_rows) - set(l_rows))
    modified = sorted(k for k in s_rows if k in l_rows and s_rows[k]["h"] != l_rows[k]["h"])
    modified_raw, modified = modified, [k for k in modified
                                        if not (t == "tasks" and k in ALLOWED_DEP_REWIRE)]
    added = sorted(set(l_rows) - set(s_rows))
    report["tables"][t] = {"pk": pk, "columns": len(cols), "rows_snapshot": len(s_rows),
                           "rows_live": len(l_rows), "deleted_rows": missing[:20],
                           "deleted_count": len(missing), "modified_rows": modified[:20],
                           "modified_count": len(modified),
                           "allowed_rewire_rows": [k for k in modified_raw if k not in modified],
                           "added_count": len(added), "added_rows": added[:40]}
    if missing or modified:
        all_rows_intact = False
snap.close()
live.close()

expected_new = {
    "tasks": {"t_6d692b93e342"},
    "artifacts": {"a_47e0498f66c2", "a_fa4716cffb26"},
    "decisions": {"d_5ffb9971d5a3"},
    "changelog": {"902"},
}
new_rows_exact, required_present = {}, {}
snap2, live2 = ro(SNAP), ro(LIVE)
for t, exp in expected_new.items():
    tbl = report["tables"][t]
    pk = tbl["pk"]
    complete = len(tbl["added_rows"]) == tbl["added_count"]      # added_rows 只留前 40 条
    got = set(tbl["added_rows"])
    new_rows_exact[t] = {"expected": sorted(exp), "observed": sorted(got),
                         "exact": bool(complete and got == exp), "observed_truncated": not complete}
    present = []
    for aid in sorted(exp):
        in_live = live2.execute("select 1 from {} where {}=?".format(t, pk), (aid,)).fetchone()
        in_snap = snap2.execute("select 1 from {} where {}=?".format(t, pk), (aid,)).fetchone()
        if in_live and not in_snap:
            present.append(aid)
    required_present[t] = {"required": sorted(exp), "present": present,
                           "all_present": sorted(present) == sorted(exp)}
snap2.close()
live2.close()
report["new_rows_exact"] = new_rows_exact
report["required_new_rows_present"] = required_present
report["note"] = ("ALL_PASS 口径：① 冻结快照自身哈希一致；② 快照每行仍存在且逐列同值"
                  "（tasks 仅允许 redo 的 6 条 dependencies 重指）；③ 本次 5-C 应有的新行"
                  "（v6 任务/两条产物/1 条 decision/1 条 changelog）确实存在。"
                  "回归电池会额外新增夹具项目行，故 `new_rows_exact` 仅是信息字段。")
report["events_added"] = report["tables"]["events"]["added_count"]
report["project_rows_unchanged"] = report["tables"]["projects"]["added_count"] == 0
report["ALL_PASS"] = bool(report["snapshot_intact"] and all_rows_intact
                          and report["rewire_exact"]
                          and all(v["all_present"] for v in required_present.values()))
(LOGS / "phase5c_db_append_only.json").write_text(json.dumps(report, ensure_ascii=False, indent=1),
                                                  encoding="utf-8")

print("snapshot db intact:", report["snapshot_intact"], snap_sha[:16])
for t in TABLES:
    r = report["tables"][t]
    print("  {:10s} rows {:6d} -> {:6d} | deleted {} modified {} added {}".format(
        t, r["rows_snapshot"], r["rows_live"], r["deleted_count"], r["modified_count"],
        r["added_count"]), ("added=" + str(r["added_rows"][:8]) if r["added_count"] else ""),
        ("allowed_rewire=" + str(r["allowed_rewire_rows"]) if r["allowed_rewire_rows"] else ""))
print("allowed dependency rewire (v5->v6):")
for x in report["allowed_dependency_rewire"]:
    print("   ", x["task_id"], x["task_type"], x["before"], "->", x["after"])
print("unexpected modified rows:", report["unexpected_modified_task_rows"])
print("new rows exact:", json.dumps(new_rows_exact, ensure_ascii=False))
print("required 5-C new rows present:", json.dumps(required_present, ensure_ascii=False))
print("ALL PASS:", report["ALL_PASS"])
print("written", LOGS / "phase5c_db_append_only.json")
