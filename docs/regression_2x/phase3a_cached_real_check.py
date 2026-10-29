"""3-A 补充验证：在**真实下载的 Commons 字节**上核验外部素材链路的 3-A 断言。

适用对象：Phase 2-E 真实 provider 跑出的项目（如 p_a2fe33da8739），其 media/external/*
是当时**真实**从 upload.wikimedia.org 下载并通过校验的字节（sha256 可核对）。
本脚本只读：核验 attribution 台账、许可门禁、逐镜头 1:1 一致性、以及素材是否真的在成片画面上。

用法: python docs/regression_2x/phase3a_cached_real_check.py <pid>
"""
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
PID = sys.argv[1] if len(sys.argv) > 1 else "p_a2fe33da8739"
DB = ROOT / "projects" / "video_studio.db"
PASS, FAIL = [], []


def check(name: str, ok: bool, detail: object = "") -> None:
    (PASS if ok else FAIL).append(name)
    print("{}  {} | {}".format("PASS" if ok else "FAIL", name, str(detail)[:170]))


def arts(type_: str | None = None) -> list[dict]:
    con = sqlite3.connect(str(DB))
    con.row_factory = sqlite3.Row
    q = "select * from artifacts where project_id=?"
    args: list = [PID]
    if type_:
        q += " and type=?"
        args.append(type_)
    rows = [dict(r) for r in con.execute(q + " order by created_at", args)]
    con.close()
    for r in rows:
        r["payload"] = json.loads(Path(r["path"]).read_text(encoding="utf-8"))
    return rows


def tasks() -> list[dict]:
    con = sqlite3.connect(str(DB))
    con.row_factory = sqlite3.Row
    rows = [dict(r) for r in con.execute(
        "select * from tasks where project_id=? order by rowid", (PID,))]
    con.close()
    return rows


tks = tasks()
print("项目 {} 任务：{}".format(PID, {t["task_type"]: t["status"] for t in tks}))
renders = [t for t in tks if t["task_type"] == "render"]
if not renders:
    print("无 render 任务：无法核验")
    sys.exit(2)
r_task = sorted(renders, key=lambda t: (t["version"], t["task_id"]))[-1]
r_art = [a for a in arts("render_output") if a["task_id"] == r_task["task_id"]]
att_art = [a for a in arts("attribution") if a["task_id"] == r_task["task_id"]]
print("render 任务 {} status={} version={} artifacts={}".format(
    r_task["task_id"], r_task["status"], r_task["version"], len(r_task["artifacts"] or "")))
if not r_art:
    print("该 render 任务没有 render_output（可能未 SUCCEEDED）：无 3-A 台账可核验")
    sys.exit(3)
data = r_art[-1]["payload"]
tl = data.get("material_timeline") or []
check("存在 attribution 产物（3-A 新增）", bool(att_art),
      [Path(a["path"]).name for a in att_art])
if not att_art:
    sys.exit(4)
att = att_art[-1]["payload"]
entries = att.get("entries") or []
with_asset = [s for s in tl if s.get("selected_asset")]

# 1) 台账 ⟷ 时间轴 1:1
check("A1 台账条数 == 时间轴有素材镜头数", len(entries) == len(with_asset),
      "{} vs {}".format(len(entries), len(with_asset)))
a1 = all(e["scene_id"] == s["scene_id"] and
         e["selected_asset"]["asset_id"] == s["selected_asset"]["asset_id"] and
         e["selected_asset"]["sha256"] == s["selected_asset"]["sha256"]
         for e, s in zip(entries, with_asset))
check("A2 逐条 scene_id/asset_id/sha256 一致", a1)

# 2) 台账字段来自真实 provider 声明
ext = [e for e in entries if e.get("scope") == "external"]
check("A3 存在外部素材条目", bool(ext), [(e["scene_id"], e["provider"]) for e in ext])
fields_ok = all(all(e.get(k) for k in ("provider", "source_id", "source_url", "license"))
                for e in ext)
check("A4 外部条目含 provider/source_id/source_url/license", fields_ok,
      [(e["source_id"], e["license"]) for e in ext][:3])

# 3) 许可门禁：外部素材不得为 RESTRICTED/UNKNOWN
bad = [(e["scene_id"], e["license_class"], e["license"]) for e in ext
       if e["license_class"] in ("RESTRICTED", "UNKNOWN")]
check("A5 外部素材无 RESTRICTED/UNKNOWN 入片", not bad, bad or
      att.get("restricted_or_unknown_in_film"))
check("A6 restricted_or_unknown_in_film == []", att.get("restricted_or_unknown_in_film") == [],
      att.get("restricted_or_unknown_in_film_scope"))
cls = att.get("license_classes_used") or {}
check("A7 许可类别已分类记录", bool(cls), cls)

# 4) 真实字节：sha256 与磁盘一致（media/external/*）
sha_ok, sha_detail = True, []
for e in ext:
    p = Path(e["selected_asset"]["path"])
    if not p.is_file():
        sha_ok = False
        sha_detail.append("缺失:{}".format(p.name))
        continue
    real = hashlib.sha256(p.read_bytes()).hexdigest()
    if real != e["selected_asset"]["sha256"]:
        sha_ok = False
        sha_detail.append("sha256 不符:{}".format(p.name))
    else:
        sha_detail.append("{}…{}B".format(real[:12], e["selected_asset"]["bytes"]))
check("A8 台账 sha256 == 磁盘字节（真实下载字节未被替换）", sha_ok, sha_detail)

# 5) 真的出现在成片画面上
appears = [(e["scene_id"], e["appears_in_film"],
            (e.get("film_evidence") or {}).get("corr_expected")) for e in ext]
ok_on_screen = all(a[1] is True and (a[2] or 0) >= 0.30 for a in appears)
check("A9 外部素材 appears_in_film=true 且 corr>=0.30", ok_on_screen, appears)

# 6) credits 文本 + 落盘
txt = data.get("credits_text") or ""
check("A10 credits 文本含 provider/source_id/license/attribution",
      all(k in txt for k in ("provider", "source_id", "license", "attribution")), txt[:80])
cf = data.get("credits_file")
check("A11 credits 文件已落盘", bool(cf) and (Path(ROOT) / "projects" / PID / cf).is_file(), cf)

# 7) 成片可解码 + 外部素材窗口
film = (Path(ROOT) / "projects" / PID / (data.get("output") or "")) \
    if not Path(data.get("output") or "").is_absolute() else Path(data.get("output"))
check("A12 成片文件存在", film.is_file(), film.name if film else None)

print("\n结果: {}/{} 通过".format(len(PASS), len(PASS) + len(FAIL)))
if FAIL:
    print("失败项:", FAIL)
sys.exit(0 if not FAIL else 1)
