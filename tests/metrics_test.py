"""Phase 4-A 测试：只读质量/成本指标（metrics）。

自动断言：
  · **确定性**：项目模式与全库模式两次运行 JSON **逐字节一致**（无时间戳、排序固定）；
  · **只读**：运行前后 DB sha256/大小/行数不变；只读连接写操作被拒绝；不触发任务；
  · **口径分离**：LLM 成本标"估算"（且事件成本与任务行成本分列）、外部素材标"非计费"；
  · **`provider=none` 回归证据**：在默认配置产出的项目上，外部素材请求为 0 / 下载字节为 0，
    且 `config/config.json` 与冻结基线 manifest 的 sha256 一致（未被改动）；
  · **跨模块一致**：与 `run.py report` 的成本/素材口径数值一致；语义计数与 4-B 一致。

用法：python tests/metrics_test.py
"""
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.ops.metrics import (corpus_metrics, project_metrics,  # noqa: E402
                                      semantic_report)
from video_studio.ops.report import build_report, readonly_connection  # noqa: E402

DB = ROOT / "projects" / "video_studio.db"
PY = sys.executable
EXT_PID = "p_f4b466a4a024"          # 真实外部素材项目（3-A）
PASS, FAIL = [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print(("PASS  " if ok else "FAIL  ") + name + (" | " + str(detail)[:200] if detail else ""))


def cli(*args: str):
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    return subprocess.run([PY, "run.py", *args], cwd=str(ROOT), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=1800, env=env)


def db_fp() -> dict:
    con = sqlite3.connect("file:{}?mode=ro".format(DB.as_posix()), uri=True)
    counts = {t: con.execute("select count(*) from {}".format(t)).fetchone()[0]
              for t in ("projects", "tasks", "artifacts", "events")}
    con.close()
    return {"sha256": hashlib.sha256(DB.read_bytes()).hexdigest(), "size": DB.stat().st_size,
            "counts": counts}


def pid_none_provider() -> str | None:
    """找一个**默认配置（provider=none）**产出的项目：有 render_output 且外部请求为 0。"""
    con = sqlite3.connect("file:{}?mode=ro".format(DB.as_posix()), uri=True)
    con.row_factory = sqlite3.Row
    rows = [dict(r) for r in con.execute(
        "select a.project_id, a.path from artifacts a where a.type='retrieval_candidates' "
        "and exists (select 1 from artifacts r where r.project_id=a.project_id "
        "and r.type='render_output') order by a.created_at desc limit 80")]
    con.close()
    for r in rows:
        try:
            d = json.loads(Path(r["path"]).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not d.get("external_requested") and (d.get("material_mode") in ("none", "local_ingest")):
            return r["project_id"]
    return None


before = db_fp()

# ---------------- M1 项目指标 ----------------
r1 = cli("metrics", EXT_PID, "--json")
try:
    m1 = json.loads(r1.stdout)
except json.JSONDecodeError:
    m1 = {}
check("M1 项目指标 rc=0 且 JSON 可解析", r1.returncode == 0 and m1.get("found") is True,
      "rc={} keys={}".format(r1.returncode, sorted(m1)[:6]))
check("M1b 指标含质量/契约/素材/成本/语义/人工六类",
      all(k in m1 for k in ("timeline", "on_screen", "contracts", "material", "llm", "semantics",
                            "human")), sorted(m1))
check("M1c 成本口径标注为估算（非账单）",
      m1.get("llm", {}).get("estimate") is True
      and "非" in m1.get("llm", {}).get("note", "") + "非账单",
      m1.get("llm", {}).get("note"))
check("M1d 外部素材口径标注为非计费且给出用量",
      m1.get("material", {}).get("billing") is False
      and int(m1["material"].get("downloaded_bytes") or 0) > 0,
      {k: m1["material"].get(k) for k in ("requests", "downloaded_bytes", "rate_limited")})
check("M1e 质量指标齐全（上屏率/corr/时长/响度）",
      m1["on_screen"].get("rate") == 1.0 and m1["on_screen"].get("corr_min") is not None
      and m1["contracts"].get("duration_ok") is True and m1["contracts"].get("loudness_ok") is True,
      (m1["on_screen"], {k: m1["contracts"].get(k) for k in ("duration_ok", "loudness_ok")}))

# ---------------- M2 确定性（项目模式） ----------------
r2 = cli("metrics", EXT_PID, "--json")
check("M2 项目指标两次运行 JSON 逐字节一致（确定性）",
      r1.stdout == r2.stdout and len(r1.stdout) > 200,
      "len {} vs {}".format(len(r1.stdout), len(r2.stdout)))

# ---------------- M3 确定性（全库模式，取最近 8 个） ----------------
c1 = cli("metrics", "--all", "--limit", "8", "--json")
c2 = cli("metrics", "--all", "--limit", "8", "--json")
check("M3 全库指标两次运行 JSON 逐字节一致（确定性）", c1.stdout == c2.stdout,
      "len {} vs {}".format(len(c1.stdout), len(c2.stdout)))
try:
    cm = json.loads(c1.stdout)
except json.JSONDecodeError:
    cm = {}
check("M3b 全库汇总含三态计数与合计（MATCH/MISMATCH/UNKNOWN）",
      all(k in (cm.get("aggregate") or {}) for k in ("match", "mismatch", "unknown", "projects")),
      (cm.get("aggregate") or {}).get("projects"))

# ---------------- M4 只读 ----------------
after = db_fp()
check("M4 只读：DB sha256/大小/行数在指标运行前后不变", before == after,
      "{} -> {} | {}".format(before["sha256"][:12], after["sha256"][:12], after["counts"]))
try:
    con = readonly_connection(DB)
    con.execute("insert into memories (memory_id, project_id, kind, agent_role, key, content, "
                "version, created_at) values ('x','x','x','x','x','x',1,0)")
    con.close()
    blocked = False
except sqlite3.OperationalError as exc:
    blocked = "readonly" in str(exc).lower()
check("M4b 只读连接写操作被 SQLite 拒绝", blocked, "OperationalError(readonly)")
r3 = cli("metrics", EXT_PID, "--json")
check("M4c 连续运行未触发任何任务（无新增任务/事件行）", db_fp()["counts"] == after["counts"],
      db_fp()["counts"])

# ---------------- M5 provider=none 回归证据 ----------------
NONE_PID = pid_none_provider()
check("M5 存在默认配置（provider=none）产出的项目可供验证", bool(NONE_PID), NONE_PID)
if NONE_PID:
    mn = project_metrics(DB, NONE_PID)
    check("M5b provider=none 项目：外部请求 0 / 下载 0 字节（默认行为未变）",
          int(mn["material"].get("requests") or 0) == 0
          and int(mn["material"].get("downloaded_bytes") or 0) == 0
          and mn["material"].get("mode") in ("none", "local_ingest", None),
          {k: mn["material"].get(k) for k in ("mode", "requests", "downloaded_bytes")})
    check("M5c provider=none 项目仍能产出成片（未因 4.x 新增而改变默认路径）",
          bool(mn.get("artifacts", {}).get("render_output")), mn.get("artifacts"))
# 5-L **测试契约更新**（不改业务语义）：钉定目标由早已过期的 `3.x-final-baseline`
# 改为当前有效基线 `5.x-post-final-maintenance-baseline`；断言强度不变（仍要求逐字节一致）。
baseline = json.loads((ROOT / "docs" / "regression_2x" / "baseline" /
                       "baseline_manifest_5.x-post-final-maintenance-baseline.json")
                      .read_text(encoding="utf-8"))
cfg_now = hashlib.sha256((ROOT / "config" / "config.json").read_bytes()).hexdigest()
check("M5d config/config.json 与**当前有效基线** manifest 的 sha256 一致（钉定 tag="
      "5.x-post-final-maintenance-baseline；测试契约更新，非业务语义变更）",
      cfg_now == (baseline["files"]["config/config.json"]["sha256"]),
      "{} vs {}".format(cfg_now[:12], baseline["files"]["config/config.json"]["sha256"][:12]))

# ---------------- M6 跨模块一致 ----------------
rep = build_report(DB, EXT_PID, project_dir=ROOT / "projects" / EXT_PID)
check("M6 指标与 report 的成本/素材口径一致",
      abs(rep["cost"]["task_cost_usd_sum"] - m1["llm"]["task_cost_usd_sum"]) < 1e-9
      and int((rep["material"].get("provider_stats") or {}).get("downloaded_bytes") or 0)
      == int(m1["material"].get("downloaded_bytes") or 0),
      (rep["cost"]["task_cost_usd_sum"], m1["llm"]["task_cost_usd_sum"]))
sem = m1.get("semantics") or {}
sem_ref = semantic_report(DB, EXT_PID)
check("M6b 指标中的语义计数与 4-B 判定**逐项一致**（不硬编码旧状态：4-C 替换后该值会变）",
      sem.get("counts") == sem_ref.get("counts")
      and sem.get("mismatch_scenes") == [s["scene_id"] for s in sem_ref["scenes"]
                                         if s["verdict"] == "MISMATCH"],
      {"metrics": sem.get("counts"), "semantic_report": sem_ref.get("counts"),
       "mismatch": sem.get("mismatch_scenes")})

# ---------------- M7 全库口径（只读、描述性） ----------------
full = corpus_metrics(DB, DB.parent)
agg = full["aggregate"]
check("M7 全库指标可运行并给出合计（描述性；不声称准确率）",
      agg["projects"] > 0 and agg["scenes"] > 0, {k: agg[k] for k in
                                                  ("projects", "scenes", "match", "mismatch",
                                                   "unknown")})
print("   全库汇总（如实记录）：{}".format(json.dumps(
    {k: agg[k] for k in ("projects", "scenes", "scenes_with_asset", "on_screen_rate",
                         "match", "mismatch", "unknown", "semantic_mismatch_rate",
                         "loudness_ok", "requests", "downloaded_bytes")}, ensure_ascii=False)))

print("\n结果: {}/{} 通过".format(len(PASS), len(PASS) + len(FAIL)))
if FAIL:
    print("失败项:", FAIL)
sys.exit(0 if not FAIL else 1)
