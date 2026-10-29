# -*- coding: utf-8 -*-
"""P7-2 只读盘点：确定 AssetIndex 的扫描集合（现有本地素材，零网络）。"""
import json
import pathlib
import sqlite3
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")
con = sqlite3.connect("file:{}?mode=ro".format((R / "projects/video_studio.db").as_posix()), uri=True)
con.row_factory = sqlite3.Row
con.execute("PRAGMA query_only=ON")

MEDIA = R / "projects/p_96efdc03e1aa/media"
print("=== projects/p_96efdc03e1aa/media/** ===")
files = sorted(p for p in MEDIA.rglob("*") if p.is_file())
for p in files:
    print("  {:>10,} B  {}".format(p.stat().st_size, p.relative_to(R).as_posix()))
print("  合计:", len(files))

ro = next(dict(r) for r in con.execute(
    "select path from artifacts where type='render_output' and task_id='t_d0a54bdf1810'"))
d = json.loads(pathlib.Path(ro["path"]).read_text(encoding="utf-8"))
used = {}
for seg in d.get("material_timeline") or []:
    sa = seg.get("selected_asset") or {}
    if sa.get("asset_id"):
        used.setdefault(sa["asset_id"], sa)
print()
print("=== 6-G 母片实际使用的资产（material_timeline）===")
for aid, sa in sorted(used.items()):
    p = pathlib.Path(sa.get("path") or "")
    print("  {} | {} | exists={} | source={} | provider={} | license={} | class={}".format(
        aid, (sa.get("name") or "")[:44], p.is_file(), sa.get("source"),
        sa.get("provider"), sa.get("license"), sa.get("license_class")))

print()
print("=== H5 两件素材 ===")
for s, path in (("S05", r"C:\mp4agent\h5_asset_candidates\S05\Russell_PM_1+1=2.png"),
                ("S11", r"C:\mp4agent\h5_asset_candidates\S11\research"
                        r"\S11-D0_LIPIcs-ITP-2023-24_p08_tactic-state-rw.png")):
    p = pathlib.Path(path)
    print("  {} | exists={} | {:>9,} B | {}".format(s, p.is_file(),
                                                    p.stat().st_size if p.is_file() else 0, path))

print()
print("=== 既有 asset_index artifact（项目）===")
ai = next((dict(r) for r in con.execute(
    "select artifact_id,path from artifacts where type='asset_index' "
    "and project_id='p_96efdc03e1aa' order by created_at desc limit 1")), None)
if ai:
    j = json.loads(pathlib.Path(ai["path"]).read_text(encoding="utf-8"))
    fl = j.get("files") or []
    print("  artifact", ai["artifact_id"], "| files n =", len(fl),
          "| material_mode =", j.get("material_mode"))
    if fl:
        print("  files[0] keys:", sorted(fl[0].keys()))
        print("  files[0]:", json.dumps(fl[0], ensure_ascii=False)[:400])
    print("  roots:", json.dumps({k: v for k, v in j.items()
                                  if k not in ("files", "summary")}, ensure_ascii=False)[:300])
print()
print("=== 既有 material_providers / 许可记录（attribution 摘要）===")
at = next((dict(r) for r in con.execute(
    "select path from artifacts where type='attribution' and project_id='p_96efdc03e1aa' "
    "order by created_at desc limit 1")), None)
if at:
    j = json.loads(pathlib.Path(at["path"]).read_text(encoding="utf-8"))
    print("  distinct_assets:", j.get("distinct_assets"), "| license_classes_used:",
          j.get("license_classes_used"), "| entry_count:", j.get("entry_count"))
    ent = (j.get("entries") or [])[:3]
    for e in ent:
        print("   entry:", json.dumps(e, ensure_ascii=False)[:220])
con.close()
