# -*- coding: utf-8 -*-
"""Phase 7 只读审计（续）：需求形状 / 候选统计 / 外部素材请求实况 / 遗留模块接线情况。"""
import json
import pathlib
import sqlite3
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
con = sqlite3.connect("file:{}?mode=ro".format((R / "projects/video_studio.db").as_posix()), uri=True)
con.row_factory = sqlite3.Row
con.execute("PRAGMA query_only=ON")
ro = next(dict(r) for r in con.execute(
    "select path from artifacts where type='render_output' and task_id='t_d0a54bdf1810'"))
rc = next((dict(r) for r in con.execute(
    "select path from artifacts where type='retrieval_candidates' and task_id='t_d0a54bdf1810' "
    "order by created_at desc limit 1")), None)
d = json.loads(pathlib.Path(ro["path"]).read_text(encoding="utf-8"))
tl = d["material_timeline"]
print("=== original_requirement（S01 实际形状）===")
print(json.dumps(tl[0].get("original_requirement"), ensure_ascii=False)[:800])
print()
print("=== candidates[0]（S01）===")
c0 = (tl[0].get("candidates") or [])
print("n_candidates =", len(c0))
if c0:
    print("keys:", sorted(c0[0].keys()))
    print(json.dumps(c0[0], ensure_ascii=False)[:520])
print()
print("=== 全片 21 场景统计 ===")
import collections                                                         # noqa: E402
ins = collections.Counter(s.get("insufficiency_class") for s in tl)
fb = collections.Counter(s.get("fallback_state") for s in tl)
sel = collections.Counter((s.get("selected_asset") or {}).get("asset_id") for s in tl)
print("insufficiency_class:", dict(ins))
print("fallback_state    :", dict(fb))
print("selected_asset 计数:", dict(sel))
print("candidates_total  :", [s.get("candidates_total") for s in tl])
print("needs_hitl        :", sum(1 for s in tl if s.get("needs_hitl")),
      "| license_pending:", sum(1 for s in tl if s.get("license_pending")))
print("selection_source  :", dict(collections.Counter(s.get("selection_source") for s in tl)))
print("human_selection   :", dict(collections.Counter(str(s.get("human_selection")) for s in tl)))
print("retrieval_query 长度(字符):", [len(str(s.get("retrieval_query") or "")) for s in tl])
print()
print("=== retrieval_candidates（v9 任务）===")
if rc:
    r = json.loads(pathlib.Path(rc["path"]).read_text(encoding="utf-8"))
    print({k: r.get(k) for k in ("material_mode", "material_mode_reason", "material_provided",
                                 "external_requested", "external_provider", "external_verified",
                                 "external_rejected", "external_no_candidate", "external_error",
                                 "index_source", "indexed_files", "query_source",
                                 "candidates_total")})
    print("candidates[0] keys:", sorted((r.get("candidates") or [{}])[0].keys())
          if r.get("candidates") else "（空列表）")
print()
print("=== 当前运行时是否引用遗留模块（stage31/stage33/orchestration）===")
con.close()
import re                                                                 # noqa: E402
SRC = R / "src/video_studio"
runtime_files = list((SRC / "agents").rglob("*.py")) + list((SRC / "ops").rglob("*.py")) \
    + list((SRC / "core").rglob("*.py")) + list((SRC / "pipeline").rglob("*.py")) \
    + list((SRC / "production2x").rglob("*.py")) + [SRC / "cli.py"]
pat = re.compile(r"^\s*(?:from|import)\s+.*(stage31|stage33|orchestration|stage32b)")
hits = []
for f in runtime_files:
    for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
        if pat.match(line):
            hits.append("{}:{}  {}".format(f.relative_to(SRC).as_posix(), i, line.strip()[:90]))
print("命中数:", len(hits))
for h in hits[:15]:
    print("  ", h)
print()
print("=== orchestration/stage31/stage33 被谁引用（全 src）===")
for mod in ("stage31", "stage33", "orchestration", "stage32b"):
    users = []
    for f in SRC.rglob("*.py"):
        if mod in f.parts:
            continue
        if re.search(r"(from|import)\s+.*\b{}\b".format(mod),
                     f.read_text(encoding="utf-8")):
            users.append(f.relative_to(SRC).as_posix())
    print("  {:<14} 被引用于: {}".format(mod, users[:8] or "（无）"))
