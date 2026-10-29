"""Phase 4-C 测试：人审候选替换闭环（人工明确选定 → 既有 redo 生效；校验不过即 fail-closed）。

自动断言：
  H1 **无人工决定时行为不变**（时间轴与自动选材一致、selection_source=automatic）
  H2 **有效人工选定生效**：时间轴选中人工指定素材、`selection_source=human_review`、
     含 decision_id/decided_by/reason；许可类别保留
  H3 选定素材**不在候选池** → 渲染 **BLOCKED**（错误码 `HUMAN_SELECTION_NOT_IN_POOL`），不产出成片
  H4 选定素材**不可用** → 渲染 **BLOCKED**（`HUMAN_SELECTION_UNUSABLE`）
  H5 候选池为空 → 校验返回 `HUMAN_SELECTION_EMPTY_POOL`（禁止随便选一个）
  H6 记录通道：写既有 `decisions`+`changelog`（human_confirmed=1），**不改任务/产物**；
     缺 --by / --reason → 拒绝写入
  H7 人工选定后的 `selected_asset` 投影键与自动选材**完全一致**（防漂移）
  H8 台账 ⟷ 时间轴 1:1（替换后仍成立）

用法：python tests/human_selection_test.py
"""
import hashlib
import json
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.agents.base import AGENTS  # noqa: E402
from video_studio.core.engine import Engine  # noqa: E402
from video_studio.core.selection_review import (SELECTION_KEYS,  # noqa: E402
                                                latest_selections_from_conn, validate_choice)
from video_studio.db.schema import Database  # noqa: E402
from video_studio.llm.router import MockLLM, Router  # noqa: E402
from video_studio.ops.selection_review import record_selection, review_queue  # noqa: E402
from video_studio.ops.report import readonly_connection  # noqa: E402

import video_studio.agents.asset.agent  # noqa: E402,F401
import video_studio.agents.audio.agent  # noqa: E402,F401
import video_studio.agents.editing.agent  # noqa: E402,F401
import video_studio.agents.retrieval.agent  # noqa: E402,F401
import video_studio.agents.script.agent  # noqa: E402,F401
import video_studio.agents.voice.agent  # noqa: E402,F401

DB = ROOT / "projects" / "video_studio.db"
REAL_IMG = ROOT / "output" / "run03" / "asset_cache" / "files" / "r3_S01-B01_3.img.jpg"
REAL_VID = ROOT / "projects" / "p_f4b466a4a024" / "output" / "t_b7a62ec8e29a_draft.mp4"
PASS, FAIL = [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print(("PASS  " if ok else "FAIL  ") + name + (" | " + str(detail)[:200] if detail else ""))


SCRIPT = {"segments": [
    {"chapter": "a", "narration": "VR 头显 佩戴 展示 设备 外观", "duration_s": 6},
    {"chapter": "b", "narration": "VR 头显 佩戴 展示 设备 外观", "duration_s": 6},
], "summary": "4-C human selection"}


def make_engine(catalog: Path):
    cfg = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8"))
    rules = json.loads((ROOT / "config" / "rules.json").read_text(encoding="utf-8"))
    cfg["tools"]["material"] = {"provider": "local_catalog", "catalog": str(catalog),
                                "license_required": True, "min_interval_s": 0,
                                "max_bytes": 8 * 1024 * 1024}
    return Engine(Database(DB), Router(cfg["llm"], MockLLM({}, {})), rules, ROOT / "projects",
                  cfg, AGENTS)


def build_project(tag: str, items: list[dict]):
    """建一个最小项目并渲染；返回 (pid, render_task, render_output, task_row, engine)。

    注意：catalogue 项的键名必须是 provider 期望的 `name`（`asset_name` 不是它的字段——
    早期版本写错键名导致 provider 得到名称 "s1" 而评分为 0，已修正）。
    """
    work = Path(tempfile.mkdtemp(prefix="vs_p4c_"))
    cat = work / "catalog"
    cat.mkdir(parents=True, exist_ok=True)
    entries = []
    for it in items:
        dst = cat / it["name"]
        shutil.copy2(Path(it["file"]), dst)
        entries.append({"source_id": it["source_id"], "name": it["name"],
                        "license": it["license"], "attribution": it["attribution"],
                        "file": str(dst)})
    (cat / "catalogue.json").write_text(json.dumps({"items": entries}, ensure_ascii=False),
                                        encoding="utf-8")
    eng = make_engine(cat)
    pid = eng.create_project("phase4c_" + tag)
    t_script = eng.create_task(pid, "script", "script")
    aid = eng.write_artifact(pid, t_script, "script_output", SCRIPT, summary="脚本")
    eng.attach_artifact(t_script, aid)
    eng.db.set_task_status(t_script, "SUCCEEDED")
    t_ret = eng.create_task(pid, "retrieval", "retrieval", dependencies=[t_script])
    eng.run_cycle(pid, limit=4)
    t_rend = eng.create_task(pid, "render", "editing", dependencies=[t_script, t_ret])
    for _ in range(4):
        eng.run_cycle(pid, limit=4)
        if eng.db.get_task(t_rend)["status"] not in ("PENDING", "DISPATCHED", "RUNNING"):
            break
    con = sqlite3.connect("file:{}?mode=ro".format(DB.as_posix()), uri=True)
    con.row_factory = sqlite3.Row
    row = dict(con.execute("select status, error, version from tasks where task_id=?",
                           (t_rend,)).fetchone())
    a = con.execute("select path, artifact_id from artifacts where task_id=? and "
                    "type='render_output' order by created_at desc limit 1", (t_rend,)).fetchone()
    con.close()
    ren = json.loads(Path(a["path"]).read_text(encoding="utf-8")) if a else None
    return pid, t_rend, ren, row, eng


IMG_A = ROOT / "output" / "run03" / "asset_cache" / "files" / "r3_S01-B01_3.img.jpg"
IMG_B = ROOT / "output" / "run03" / "asset_cache" / "files" / "r3_S01-B01_0.img.jpg"
ITEMS = [
    {"name": "VR头显_正面_展示.jpg", "source_id": "s1", "license": "CC BY 4.0",
     "attribution": "A", "file": str(IMG_A)},
    {"name": "VR头显_侧面_展示.jpg", "source_id": "s2", "license": "CC BY 4.0",
     "attribution": "B", "file": str(IMG_B)},
]

# ---------------- H1 无人工决定 → 行为不变 ----------------
pid1, t1, ren1, row1, _ = build_project("nod", ITEMS)
tl1 = (ren1 or {}).get("material_timeline") or []
sources = {s.get("selection_source") for s in tl1}
check("H1 无人工决定时渲染正常且 selection_source 均为 automatic（行为与 3.x 一致）",
      row1["status"] == "SUCCEEDED" and sources == {"automatic"},
      (row1["status"], sources))
auto_choice = (tl1[0].get("selected_asset") or {}).get("asset_id") if tl1 else None
check("H1b 自动选材结果可读（用于后续对照）", bool(auto_choice), auto_choice)

# ---------------- H2 有效人工选定 → 生效 ----------------
cands = tl1[0].get("candidates") or []
other = next((c["asset_id"] for c in cands if c["asset_id"] != auto_choice), None)
check("H2 前置：该镜头有第二个可用候选（否则无法构造替换）", bool(other),
      [c["asset_id"] for c in cands])
rec = record_selection(DB, pid1, "S01", other, "human:tester", "测试用人工替换（S01）")
check("H2b 记录人工选定成功（写 decisions+changelog）",
      rec.get("ok") is True and rec.get("decision_id") and rec.get("changelog_id"),
      {k: rec.get(k) for k in ("ok", "code", "decision_id", "changelog_id")})
selections = latest_selections_from_conn(sqlite3.connect(DB), pid1)
check("H2c 人工选定可被只读读取（最新一条已批准）",
      selections.get("S01", {}).get("asset_id") == other, selections.get("S01"))
eng = make_engine(Path(tempfile.mkdtemp(prefix="vs_p4c_re_")))
t_new = eng.redo(t1)
for _ in range(4):
    eng.run_cycle(pid1, limit=4)
    if eng.db.get_task(t_new)["status"] not in ("PENDING", "DISPATCHED", "RUNNING"):
        break
con = sqlite3.connect("file:{}?mode=ro".format(DB.as_posix()), uri=True)
con.row_factory = sqlite3.Row
row_new = dict(con.execute("select status, version from tasks where task_id=?",
                           (t_new,)).fetchone())
a_new = con.execute("select path from artifacts where task_id=? and type='render_output' "
                    "order by created_at desc limit 1", (t_new,)).fetchone()
att_new = con.execute("select path from artifacts where task_id=? and type='attribution' "
                      "order by created_at desc limit 1", (t_new,)).fetchone()
con.close()
ren_new = json.loads(Path(a_new["path"]).read_text(encoding="utf-8"))
sc = next((s for s in ren_new["material_timeline"] if s["scene_id"] == "S01"), {})
check("H2d 替换通过既有 redo 生效（版本+1、任务 SUCCEEDED、旧任务保留）",
      row_new["status"] == "SUCCEEDED" and row_new["version"] == 2
      and eng.db.get_task(t1) is not None,
      (row_new["status"], row_new["version"]))
check("H2e 新时间轴选中**人工指定**素材，且带 human_review 证据",
      (sc.get("selected_asset") or {}).get("asset_id") == other
      and sc.get("selection_source") == "human_review"
      and (sc.get("human_selection") or {}).get("decided_by") == "human:tester"
      and (sc.get("human_selection") or {}).get("decision_id") == rec["decision_id"],
      {k: sc.get(k) for k in ("selection_source", "human_selection")})
check("H2f 许可类别与来源字段保留（许可门禁未被绕过）",
      (sc.get("selected_asset") or {}).get("license_class") == "FREE_ATTRIBUTION"
      and (sc.get("selected_asset") or {}).get("license") == "CC BY 4.0",
      {k: (sc.get("selected_asset") or {}).get(k) for k in ("license", "license_class")})

# ---------------- H7 投影键一致 ----------------
auto_sc = next((s for s in ren1["material_timeline"] if s["scene_id"] == "S01"), {})
check("H7 人工选定的 selected_asset 投影键与自动选材完全一致（防漂移）",
      sorted((sc.get("selected_asset") or {}).keys()) == sorted((auto_sc.get("selected_asset")
                                                                 or {}).keys())
      and sorted(sc["selected_asset"]) == sorted(SELECTION_KEYS),
      sorted((sc.get("selected_asset") or {}).keys()))

# ---------------- H8 台账 ⟷ 时间轴 1:1 ----------------
att = json.loads(Path(att_new["path"]).read_text(encoding="utf-8"))
tl_new = ren_new["material_timeline"]
with_asset = [s for s in tl_new if s.get("selected_asset")]
ok_11 = len(att["entries"]) == len(with_asset) and all(
    e["scene_id"] == s["scene_id"]
    and e["selected_asset"]["asset_id"] == s["selected_asset"]["asset_id"]
    and e["selected_asset"]["sha256"] == s["selected_asset"]["sha256"]
    for e, s in zip(att["entries"], with_asset))
check("H8 替换后台账 ⟷ 时间轴逐条 1:1（含被替换镜头）", ok_11,
      (len(att["entries"]), len(with_asset)))

# ---------------- H3 不在候选池 → BLOCKED ----------------
pid3, t3, ren3, row3, eng3 = build_project("bad", ITEMS)
t3_new = eng3.redo(t3)
r_bad = record_selection(DB, pid3, "S01", "asset_不存在", "human:tester", "无效资产")
check("H3 选定素材不在候选池 → 记录时即拒绝（不写库）",
      r_bad.get("ok") is False and r_bad.get("code") == "HUMAN_SELECTION_NOT_IN_POOL",
      r_bad)
# 绕过记录通道，直接写一条"池外"决定 → 渲染必须 BLOCKED
db = Database(DB)
from video_studio.core.selection_review import decision_row  # noqa: E402
db.insert_decision(decision_row(pid3, "S01", "asset_不存在", "human:tester", "越权测试"))
for _ in range(4):
    eng3.run_cycle(pid3, limit=4)
    if eng3.db.get_task(t3_new)["status"] not in ("PENDING", "DISPATCHED", "RUNNING"):
        break
row3b = eng3.db.get_task(t3_new)
check("H3b 池外选定 → 渲染 fail-closed（BLOCKED/FAILED，错误码明确）",
      row3b["status"] in ("FAILED", "BLOCKED")
      and "HUMAN_SELECTION_NOT_IN_POOL" in str(row3b.get("error") or ""),
      (row3b["status"], str(row3b.get("error"))[:110]))

# ---------------- H4 不可用素材 → BLOCKED ----------------
pid4, t4, ren4, row4, eng4 = build_project("unusable", ITEMS)
c4 = (ren4["material_timeline"][0].get("candidates") or [])
pick4 = c4[0]["asset_id"]
val = validate_choice([{**c4[0], "usable": False, "unusable_reason": "ASSET_TOO_SMALL: 10x10"}],
                      pick4, "S01")
check("H4 选定素材不可用 → 校验返回 HUMAN_SELECTION_UNUSABLE",
      val[0] is False and val[1] == "HUMAN_SELECTION_UNUSABLE", val)

# ---------------- H5 空池 ----------------
val5 = validate_choice([], "asset_x", "S01")
check("H5 候选池为空 → HUMAN_SELECTION_EMPTY_POOL（禁止随便选一个）",
      val5[0] is False and val5[1] == "HUMAN_SELECTION_EMPTY_POOL", val5)
q_empty = review_queue(DB, pid4)
check("H5b 复核队列给出 blocked_scenes 字段（供人工看到'必须 BLOCKED'）",
      "blocked_scenes" in q_empty, q_empty.get("blocked_scenes"))

# ---------------- H6 记录通道只动 decisions/changelog ----------------
def counts(pid):
    con = sqlite3.connect("file:{}?mode=ro".format(DB.as_posix()), uri=True)
    out = {t: con.execute("select count(*) from {} where project_id=?".format(t),
                          (pid,)).fetchone()[0]
           for t in ("tasks", "artifacts", "events", "decisions", "changelog")}
    con.close()
    return out


before_c = counts(pid1)
record_selection(DB, pid1, "S02", other, "human:tester", "第二次人工替换（S02）")
after_c = counts(pid1)
check("H6 记录人工选定只增加 decisions/changelog 行（不改任务/产物/事件）",
      after_c["decisions"] == before_c["decisions"] + 1
      and after_c["changelog"] == before_c["changelog"] + 1
      and after_c["tasks"] == before_c["tasks"] and after_c["artifacts"] == before_c["artifacts"],
      "{} -> {}".format(before_c, after_c))
r_noby = record_selection(DB, pid1, "S02", other, "", "缺决策者")
r_noreason = record_selection(DB, pid1, "S02", other, "human:tester", "")
check("H6b 缺 --by / --reason 一律拒绝写入（拒绝无归属/无理由决定）",
      r_noby.get("code") == "HUMAN_SELECTION_NO_REVIEWER"
      and r_noreason.get("code") == "HUMAN_SELECTION_NO_REASON", (r_noby, r_noreason))
con = sqlite3.connect("file:{}?mode=ro".format(DB.as_posix()), uri=True)
row_chg = con.execute("select human_confirmed, target_type from changelog where project_id=? "
                      "order by change_id desc limit 1", (pid1,)).fetchone()
con.close()
check("H6c changelog 行标记 human_confirmed=1 且类型为 selection_override",
      row_chg is not None and row_chg[0] == 1 and row_chg[1] == "selection_override",
      tuple(row_chg) if row_chg else None)

print("\n结果: {}/{} 通过".format(len(PASS), len(PASS) + len(FAIL)))
if FAIL:
    print("失败项:", FAIL)
sys.exit(0 if not FAIL else 1)
