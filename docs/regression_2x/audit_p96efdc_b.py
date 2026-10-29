# -*- coding: utf-8 -*-
"""审计 B：p_96efdc03e1aa 的人工选定合法性、素材编辑/删除痕迹、append-only、缺失文件（只读）。"""
import hashlib
import json
import pathlib
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(r"C:\mp4agent\video-studio")
DB = ROOT / "projects" / "video_studio.db"
PID = "p_96efdc03e1aa"
SNAP = ROOT / "docs" / "regression_2x" / "snapshots" / "5.x-phase5e-20260917.db"


def ro(path):
    con = sqlite3.connect("file:{}?mode=ro".format(pathlib.Path(path).as_posix()), uri=True)
    con.row_factory = sqlite3.Row
    return con


def sha(p):
    try:
        return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
    except OSError:
        return None


con = ro(DB)
q = lambda sql, args=(): [dict(r) for r in con.execute(sql, args)]

print("=== 6. 人工选定（decisions / changelog） ===")
dec = q("select decision_id, node, made_by, state, rationale, artifact_snapshot, created_at "
        "from decisions where project_id=? and node='selection_override' order by created_at", (PID,))
print("selection_override 决定数:", len(dec))
snaps = []
for d in dec:
    s = json.loads(d["artifact_snapshot"]) if isinstance(d["artifact_snapshot"], str) else d["artifact_snapshot"]
    snaps.append((d["decision_id"], s.get("scene_id"), s.get("after_asset_id") or s.get("asset_id"),
                  d["made_by"], d["state"], len(d["rationale"] or "")))
for x in snaps[:5]:
    print("   ", x)
print("   ... 共", len(snaps), "条；made_by 集合:", sorted({s[3] for s in snaps}),
      "| state 集合:", sorted({s[4] for s in snaps}),
      "| 理由长度 min/max:", min(s[5] for s in snaps), "/", max(s[5] for s in snaps))
print("   覆盖镜头数:", len({s[1] for s in snaps}), "（期望 21）")
chg = q("select change_id, target_type, target_id, changed_by, human_confirmed, created_at "
        "from changelog where project_id=? order by change_id", (PID,))
print("changelog 行数:", len(chg), "| target_type 分布:",
      {t: sum(1 for c in chg if c["target_type"] == t) for t in sorted({c["target_type"] for c in chg})})
print("   human_confirmed=1 的行数:", sum(1 for c in chg if c["human_confirmed"] == 1))

print("\n=== 7. 最新成片：人工选定是否都在候选池内、许可是否清 ===")
ro_art = q("select artifact_id, path, task_id from artifacts where project_id=? and "
           "type='render_output' order by created_at desc limit 1", (PID,))[0]
payload = json.loads(pathlib.Path(ro_art["path"]).read_text(encoding="utf-8"))
tl = payload.get("material_timeline") or []
not_in_pool, license_issue, no_human = [], [], []
for s in tl:
    sid = s.get("scene_id")
    a = s.get("selected_asset") or {}
    cands = {c.get("asset_id") for c in (s.get("candidates") or [])}
    if a.get("asset_id") not in cands:
        not_in_pool.append((sid, a.get("asset_id"), sorted(cands)))
    if a.get("source") == "external" and not a.get("license_cleared"):
        license_issue.append((sid, a.get("asset_id"), a.get("license_class")))
    if s.get("selection_source") != "human_review" or not s.get("human_selection"):
        no_human.append((sid, s.get("selection_source")))
print("时间轴镜头:", len(tl), "| 池内候选检查失败:", len(not_in_pool), not_in_pool[:3])
print("外部素材许可未清:", len(license_issue), license_issue[:3])
print("非人工选定 / 缺 human_selection:", len(no_human), no_human[:5])
print("每镜头候选数:", sorted({len(s.get('candidates') or []) for s in tl}))
print("human_selection 示例:", json.dumps((tl[0].get("human_selection") or {}), ensure_ascii=False)[:220])

print("\n=== 8. 素材编辑/删除痕迹（GLM 声明：预裁剪 + 删除哈希名缓存图） ===")
media = ROOT / "projects" / PID / "media"
all_media = sorted(p for p in media.rglob("*") if p.is_file())
print("media 文件数:", len(all_media))
for p in all_media:
    print("   {:<72} {:>9} {}".format(str(p.relative_to(media))[:72], p.stat().st_size,
                                      (sha(p) or "")[:12]))
print("\n--- 是否存在编辑前后 sha 的记录（检索产物/资产索引/事件）---")
cands = q("select artifact_id, path, task_id, created_at from artifacts where project_id=? and "
          "type='retrieval_candidates' order by created_at", (PID,))
print("retrieval_candidates 产物数:", len(cands))
missing_in_pool, edited_hits = [], []
for c in cands:
    d = json.loads(pathlib.Path(c["path"]).read_text(encoding="utf-8"))
    for cd in d.get("candidates") or []:
        p = cd.get("path")
        if p and not pathlib.Path(p).is_file():
            missing_in_pool.append((c["artifact_id"], cd.get("name"), p))
    txt = json.dumps(d, ensure_ascii=False)
    if "original_sha" in txt or "edited_sha" in txt or "pre_crop" in txt or "edit" in txt.lower():
        edited_hits.append(c["artifact_id"])
print("检索产物中引用了**已不存在文件**的候选数:", len(missing_in_pool))
for x in missing_in_pool[:8]:
    print("   !!", x)
print("检索产物里出现编辑相关字段的产物:", edited_hits[:5])
print("\n--- 事件流里与素材编辑/删除相关的事件 ---")
ev = q("select event_id, type, actor, payload, created_at from events where project_id=? "
       "order by event_id", (PID,))
print("事件数:", len(ev), "| 类型分布:", {t: sum(1 for e in ev if e["type"] == t)
                                        for t in sorted({e["type"] for e in ev})})
for e in ev:
    pl = str(e["payload"])
    if any(k in pl for k in ("crop", "CROP", "edit", "EDIT", "delete", "DELETE", "ingest",
                             "INGEST", "OPERATOR")):
        print("   ", e["event_id"], e["type"], str(e["actor"])[:24], pl[:150])

print("\n=== 9. append-only 检查（与 5-E 阶段快照 DB 对比）===")
if SNAP.is_file():
    s = ro(SNAP)
    for table in ("projects", "tasks", "artifacts", "decisions", "changelog", "events"):
        cols = [r[1] for r in s.execute("pragma table_info({})".format(table))]
        pk = cols[0]
        try:
            old = {str(r[0]): r for r in s.execute("select * from {} where project_id=?".format(table), (PID,))}
        except sqlite3.OperationalError:
            old = {}
        cur = {str(r[0]): r for r in con.execute("select * from {} where project_id=?".format(table), (PID,))}
        if not old and not cur:
            print("  {:<10} 快照 0 行 / 当前 {} 行（本阶段新增项目）".format(table, len(cur)))
            continue
        deleted = sorted(set(old) - set(cur))
        modified = []
        for k in set(old) & set(cur):
            if list(old[k]) != list(cur[k]):
                modified.append(k)
        print("  {:<10} 快照 {} 行 → 当前 {} 行 | 删除 {} | 改写 {} {}".format(
            table, len(old), len(cur), len(deleted), len(modified),
            (deleted[:3], modified[:3]) if (deleted or modified) else ""))
    s.close()
else:
    print("  快照不存在:", SNAP)
con.close()
print("\n=== 10. 项目目录中的其它文件（脚本/清单） ===")
for p in sorted((ROOT / "projects" / PID).rglob("*")):
    if p.is_file() and p.suffix.lower() in (".json", ".md", ".txt", ".py", ".csv"):
        rel = str(p.relative_to(ROOT / "projects" / PID))
        if rel.startswith("artifacts/") or rel.startswith("media/"):
            continue
        print("   ", rel, p.stat().st_size)
