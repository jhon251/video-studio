# -*- coding: utf-8 -*-
"""Phase 14 §1.2 只读盘点：可用的**人工**视觉相关性真值来源（逐条记录出处与定位字段）。"""
import json
import pathlib
import sqlite3
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
DB = R / "projects" / "video_studio.db"
sys.stdout.reconfigure(encoding="utf-8")

print("== A) Phase 7 M2 台账（人工相关性判定）==")
m2 = L / "phase6b_m2_review_ledger_v9.jsonl"
if m2.is_file():
    recs = [json.loads(x) for x in m2.read_text(encoding="utf-8").splitlines() if x.strip()]
    print("  文件:", m2.name, "| 条数:", len(recs), "| keys:", sorted(recs[0].keys())[:14])
    from collections import Counter
    print("  decision 分布:", dict(Counter(str(r.get("decision") or r.get("state")) for r in recs)))
    r0 = recs[0]
    print("  定位字段示例:", json.dumps({k: r0.get(k) for k in
                                     ("finding_id", "scene_id", "asset_id", "decision",
                                      "kind", "evidence") if k in r0}, ensure_ascii=False)[:240])
else:
    print("  缺:", m2.name)

print("\n== B) mm 冻结真值中的人工 content_label（只读引用）==")
for name in ("mm_truth_set.json", "mm_truth_v1.json", "phase6g_mm_truth.json"):
    p = L / name
    if p.is_file():
        j = json.loads(p.read_text(encoding="utf-8"))
        items = j.get("items") or j.get("pairs") or j.get("scenes") or []
        print("  {}: {} 条 | keys={}".format(name, len(items), sorted(j.keys())[:10]))
        labs = {}
        for it in items:
            k = str(it.get("content_label") or it.get("label"))
            labs[k] = labs.get(k, 0) + 1
        print("   content_label 分布:", labs)
        break
else:
    cands = sorted(x.name for x in L.glob("*truth*"))
    print("  未命中固定名；候选:", cands[:8])

print("\n== C) 5 个 HITL 场景的人工 RELEVANT 记录（P7-4 relevance 报告）==")
rel = L / "visual_relevance.json"
if rel.is_file():
    j = json.loads(rel.read_text(encoding="utf-8"))
    print("  keys:", sorted(j.keys())[:12], "| counts:", json.dumps(j.get("counts"), ensure_ascii=False)[:200])
    sr = j.get("scene_results") or []
    print("  场景数:", len(sr))
    from collections import Counter
    c = Counter()
    for s in sr:
        for cr in (s.get("candidate_results") or []):
            c[str(cr.get("decision"))] += 1
    print("  候选判定分布:", dict(c))
    hitl = [s["scene_id"] for s in sr if any(str(cr.get("decision")) == "NOT_ASSESSABLE"
                                              for cr in (s.get("candidate_results") or []))]
    print("  含 NOT_ASSESSABLE 候选的场景数:", len(hitl), hitl[:8])

print("\n== D) H5/6-C 人工验收记录（Russell 页 ↔ S05 等）==")
h5 = L / "phase6g_exec_h5.json"
if h5.is_file():
    j = json.loads(h5.read_text(encoding="utf-8"))
    hd = j.get("human_decision") or {}
    print("  human_decision keys:", sorted(hd.keys())[:12] if isinstance(hd, dict) else type(hd).__name__)
    print("  摘要:", json.dumps(hd, ensure_ascii=False)[:260])
con = sqlite3.connect("file:" + DB.as_posix() + "?mode=ro", uri=True)
con.row_factory = sqlite3.Row
print("\n== E) decisions 表中的人工选材/相关性记录（只读计数）==")
for row in con.execute("select node, count(*) n from decisions group by node order by n desc limit 8"):
    print("  node={} n={}".format(row["node"], row["n"]))
for row in con.execute("select made_by, count(*) n from decisions group by made_by order by n desc limit 6"):
    print("  made_by={} n={}".format(row["made_by"], row["n"]))
con.close()
