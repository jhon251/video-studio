# -*- coding: utf-8 -*-
"""Phase 12 只读盘点（终）：五景阻塞码、retrieval/artifacts.license 是否记录许可、出处明细。"""
import json
import pathlib
import sqlite3
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
DB = R / "projects" / "video_studio.db"
sys.stdout.reconfigure(encoding="utf-8")

prop = json.loads((L / "visual_binding_proposals.json").read_text(encoding="utf-8"))
print("== 五景 HITL：逐候选阻塞码（决定 join 能否解锁）==")
for p in prop["proposals"]:
    if p.get("decision") != "HITL_REQUIRED":
        continue
    print("  {} scene={} reason={}".format(p["proposal_id"], p["scene_id"],
                                           str(p.get("decision_reason"))[:80]))
    for e in p.get("candidate_evaluations") or []:
        print("     {:26s} state={:14s} blocking={:28s} lic_class={:16s} rel={}".format(
            e.get("asset_id"), str(e.get("state")), str(e.get("blocking_code")),
            str(e.get("license_class")), e.get("relevance_decision")))

con = sqlite3.connect("file:" + DB.as_posix() + "?mode=ro", uri=True)
con.row_factory = sqlite3.Row
print("\n== retrieval_candidates 是否含许可字段 ==")
row = con.execute("select path from artifacts where type='retrieval_candidates' and "
                  "project_id='p_96efdc03e1aa' order by created_at desc limit 1").fetchone()
if row:
    j = json.loads(pathlib.Path(row["path"]).read_text(encoding="utf-8"))
    s = json.dumps(j, ensure_ascii=False)
    print("  keys:", sorted(j.keys())[:12], "| 含 license/attribution:",
          ("license" in s, "attribut" in s))
    print("  license 值示例:", sorted({str(c.get("license")) for c in
                                     (j.get("candidates") or []) if isinstance(c, dict)})[:6])
print("\n== artifacts.license 列取值分布（前 8）==")
for r in con.execute("select license, count(*) n from artifacts group by license order by n desc "
                     "limit 8"):
    print("  {!r}: {}".format(r["license"], r["n"]))
print("\n== S01 出处条目（attribution 产物逐字段）==")
att = con.execute("select path from artifacts where artifact_id='a_c0f078f6c710'").fetchone()
j = json.loads(pathlib.Path(att["path"]).read_text(encoding="utf-8"))
for e in j["entries"]:
    if e.get("scene_id") == "S01" or e.get("scope") == "external":
        print("  ", json.dumps({k: e.get(k) for k in
                               ("scene_id", "scope", "provider", "source_id", "license",
                                "license_class", "attribution", "source_url", "selected_asset")},
                              ensure_ascii=False)[:330])
print("\n== 6-G H5 报告素材记录（P7-2 已消费者）==")
h5 = R / "docs" / "regression_2x" / "logs" / "phase6g_exec_h5.json"
if h5.is_file():
    jj = json.loads(h5.read_text(encoding="utf-8"))
    ar = jj.get("asset_records") or (jj.get("h5") or {}).get("asset_records") or []
    print("  记录数:", len(ar), "| 首条:", json.dumps(ar[0], ensure_ascii=False)[:200] if ar else None)
con.close()
