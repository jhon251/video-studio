# -*- coding: utf-8 -*-
"""6-A / M1 单元回归：**Directorial Quality 只读度量**（DQ-1 … DQ-7）。

覆盖：
  D1 DQ-1 Hook 相关性：三态/未评估规则（MATCH→PASS、MISMATCH→FAIL、UNKNOWN→UNKNOWN、无证据→NOT_ASSESSABLE）
  D2 DQ-2 素材复用（v9 真值 4 素材/最大占比 0.333 → FAIL；21 素材 → PASS）
  D3 DQ-3 静态保持（120 s 保持 FAIL；8 s 保持 PASS；freezedetect 只读实测静态片）
  D4 DQ-4 视觉密度（0.5 变化/分钟 FAIL；>2 PASS）
  D5 DQ-5 高潮覆盖（核心镜头素材 2/6 → FAIL；语义 UNKNOWN / MISMATCH / NOT_ASSESSABLE 三态）
  D6 DQ-6 片尾（无 outro+尾部静音 → FAIL；含「感谢观看」→ PASS；语义三态单列）
  D7 DQ-7 汇总：UNKNOWN 不得计入 PASS
  D8 只读保证 + CLI 冒烟（`run.py direction --json --no-freeze`，真实 v9 证据 → DQ-1=UNKNOWN）
  D9 语义纪律：无证据/证据不足时**绝不给 PASS**

用法: python tests/direction_test.py
"""
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
sys.stdout.reconfigure(encoding="utf-8")

from fixtures.build_integrity_fixtures import segments, timeline  # noqa: E402
from video_studio.core import direction as D  # noqa: E402

PASS, FAIL, SKIP = [], [], []
CFG = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8-sig"))
FFMPEG = CFG["tools"]["ffmpeg"]["path"]
TRUTH = json.loads((ROOT / "tests" / "fixtures" / "production_integrity_truth_v1.json")
                   .read_text(encoding="utf-8"))
POLICY = TRUTH["policy"]
V9 = next(c for c in TRUTH["cases"] if c["id"] == "V9-REAL")
V9M = V9["measured"]
DB = ROOT / "projects" / "video_studio.db"


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print("{}  {} {}".format("PASS" if ok else "FAIL", name, "" if ok else "| " + str(detail)[:340]))


def skip(name, why):
    SKIP.append(name)
    print("SKIP  {} | {}".format(name, why))


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def ev(states: dict) -> dict:
    return {k: dict(v) for k, v in states.items()}


# ---------------- D1 DQ-1 ----------------
check("D1a DQ-1 无证据 → NOT_ASSESSABLE（不得 PASS）",
      D.hook_relevance(None, "S01")["state"] == "NOT_ASSESSABLE")
check("D1b DQ-1 证据全 UNKNOWN（v9 真实 S01）→ UNKNOWN（不得 PASS）",
      D.hook_relevance(ev({"S01": {"4b": "UNKNOWN", "5a": "UNKNOWN", "5d": "UNKNOWN",
                                   "judge": "UNKNOWN"}}), "S01")["state"] == "UNKNOWN")
check("D1c DQ-1 任一层 MISMATCH → FAIL",
      D.hook_relevance(ev({"S01": {"5a": "MISMATCH"}}), "S01")["state"] == "FAIL")
check("D1d DQ-1 任一层 MATCH → PASS",
      D.hook_relevance(ev({"S01": {"4b": "MATCH", "5a": "UNKNOWN"}}), "S01")["state"] == "PASS")

# ---------------- D2 DQ-2 ----------------
# v9 真值时间轴：用审计实测的逐镜保持 + 逐镜素材（保证 DQ-2/DQ-3/DQ-4 口径与 6-A 一致）
v9_tl, _t = [], 0.0
for i, (h, aid) in enumerate(zip(V9M["timeline_holds"], V9M["scene_assets"])):
    v9_tl.append({"scene_id": "S{:02d}".format(i + 1), "start_s": round(_t, 3),
                  "end_s": round(_t + h, 3), "selected_asset": {"asset_id": aid}})
    _t += h
r2 = D.asset_reuse(v9_tl, POLICY)
check("D2a DQ-2 v9 真值（21 镜 4 素材、最大素材 510 s/1532 s = 0.3329）→ FAIL",
      r2["state"] == "FAIL" and r2["unique_assets"] == 4
      and abs(r2["max_asset_share"] - 0.3329) < 0.001, r2)
check("D2b DQ-2 21 镜 21 素材 → PASS",
      D.asset_reuse(timeline(21, 8.0), POLICY)["state"] == "PASS")
check("D2c DQ-2 单素材 100% → FAIL",
      D.asset_reuse(timeline(10, 10.0, assets=["asset_a"]), POLICY)["state"] == "FAIL")

# ---------------- D3 DQ-3 ----------------
h120 = D.static_hold(timeline(10, 120.0), None, POLICY)
h8 = D.static_hold(timeline(21, 8.0), None, POLICY)
check("D3a DQ-3 每镜 120 s 静态保持 → FAIL（超阈 10/10）",
      h120["state"] == "FAIL" and h120["holds_over_threshold"] == 10
      and h120["share_over_threshold"] == 1.0, {k: h120[k] for k in
                                                ("state", "mean_hold_s", "max_hold_s",
                                                 "holds_over_threshold")})
check("D3b DQ-3 每镜 8 s → PASS", h8["state"] == "PASS", h8)
tmp = Path(tempfile.mkdtemp(prefix="vs_m1_dir_"))
static_film = tmp / "static.mp4"
rc = subprocess.run([FFMPEG, "-y", "-v", "error", "-f", "lavfi", "-t", "12",
                     "-i", "color=c=0x102030:size=320x180:rate=25", "-c:v", "libx264",
                     "-pix_fmt", "yuv420p", "-preset", "ultrafast", str(static_film)],
                    capture_output=True)
blocks, err = D.measure_freeze(static_film, FFMPEG, 12.0)
check("D3c DQ-3 freezedetect 只读实测：纯色静态片 → 至少 1 段冻结且最长 ≥8 s",
      rc.returncode == 0 and bool(blocks) and max(b["dur"] or 0 for b in blocks) >= 8.0,
      {"blocks": len(blocks), "blocks_head": blocks[:2], "err_tail": (err or "")[-120:]})
v9_holds = D.static_hold(v9_tl, None, POLICY)
check("D3d DQ-3 v9 真值（保持 40–95 s，21/21 超 25 s 阈）→ FAIL",
      v9_holds["state"] == "FAIL" and v9_holds["holds_over_threshold"] == 21
      and abs(v9_holds["mean_hold_s"] - 72.952) < 0.01, v9_holds["mean_hold_s"])

# ---------------- D4 DQ-4 ----------------
check("D4a DQ-4 10 镜 ×120 s（0.5 变化/分钟）→ FAIL",
      D.visual_density(timeline(10, 120.0), None, POLICY)["state"] == "FAIL")
check("D4b DQ-4 21 镜 ×8 s（7.5 变化/分钟）→ PASS",
      D.visual_density(timeline(21, 8.0), None, POLICY)["state"] == "PASS")
v9_dens = D.visual_density(v9_tl, None, POLICY)
check("D4c DQ-4 v9 真值（21 镜/1532 s = 0.822 变化/分钟）→ FAIL",
      v9_dens["state"] == "FAIL"
      and abs(v9_dens["scene_changes_per_min"] - V9M["changes_per_min"]) < 0.005,
      v9_dens["scene_changes_per_min"])

# ---------------- D5 DQ-5 ----------------
segs_core = [{"duration_s": 10.0, "narration": "这一段讨论机器证明与 Lean 的形式化检查。"}
             for _ in range(8)]
tl_core = timeline(8, 90.0, assets=["asset_a", "asset_b"])
c5 = D.climax_coverage(segs_core, tl_core, None, POLICY)
check("D5a DQ-5 核心镜头仅 2 素材 → 结构项 FAIL；无证据 → 语义 NOT_ASSESSABLE（不得 PASS）",
      c5["state"] == "FAIL" and c5["semantic_state"] == "NOT_ASSESSABLE"
      and c5["distinct_assets_in_core"] == 2, {k: c5[k] for k in
                                               ("state", "core_scenes", "distinct_assets_in_core",
                                                "semantic_state")})
c5u = D.climax_coverage(segs_core, tl_core, ev({"S{:02d}".format(i + 1):
                                               {"judge": "UNKNOWN"} for i in range(8)}), POLICY)
check("D5b DQ-5 语义证据全 UNKNOWN → semantic_state=UNKNOWN（不得 PASS）",
      c5u["semantic_state"] == "UNKNOWN", c5u["semantic_state"])
c5m = D.climax_coverage(segs_core, tl_core, ev({"S{:02d}".format(i + 1):
                                                {"judge": "MATCH" if i else "MISMATCH"}
                                                for i in range(8)}), POLICY)
check("D5c DQ-5 存在 MISMATCH → semantic_state=FAIL（必须暴露，不被 MATCH 稀释）",
      c5m["semantic_state"] == "FAIL", c5m["semantic_counts"])
c5v = D.climax_coverage([{"duration_s": d,
                          "narration": ("这一句是关于限制声明的说明。" if (i + 1) == V9M["non_core_scene"]
                                        else "四色定理与机器检查的形式化证明。")}
                         for i, d in enumerate(V9M["script_durs"])], v9_tl,
                        ev({"S{:02d}".format(i + 1): {"judge": "UNKNOWN"} for i in range(21)}),
                        POLICY)
check("D5d DQ-5 v9 真值：核心镜头 20 个（非核心 = S16 无关键词）、素材 4 → 结构项 FAIL、"
      "语义 UNKNOWN（不得 PASS）",
      c5v["state"] == "FAIL" and c5v["core_scenes"] == 20 and c5v["distinct_assets_in_core"] == 4
      and c5v["semantic_state"] == "UNKNOWN",
      {k: c5v[k] for k in ("state", "core_scenes", "distinct_assets_in_core", "semantic_state")})

# ---------------- D6 DQ-6 ----------------
segs_no_outro = [{"duration_s": 10.0, "narration": "这一段是限制声明，不是结尾语。"} for _ in range(6)]
segs_outro = segs_no_outro[:-1] + [{"duration_s": 10.0, "narration": "感谢观看，我们下期再见。"}]
e_fail = D.ending_completeness(segs_no_outro, timeline(6, 10.0), 20.0, None, POLICY)
e_ok = D.ending_completeness(segs_outro, timeline(6, 10.0), 0.0, None, POLICY)
check("D6a DQ-6 无 outro 关键词且尾部静音 20 s → FAIL；语义 NOT_ASSESSABLE",
      e_fail["state"] == "FAIL" and e_fail["semantic_state"] == "NOT_ASSESSABLE", e_fail)
check("D6b DQ-6 末镜含「感谢观看/我们下期再见」且无尾部静音 → PASS（命中仅在末镜内）",
      e_ok["state"] == "PASS" and e_ok["outro_keyword_hits"]
      and all(h["scene_index"] == 6 for h in e_ok["outro_keyword_hits"]),
      {"state": e_ok["state"], "hits": e_ok["outro_keyword_hits"]})
e_v9 = D.ending_completeness([{"duration_s": d, "narration": "这一期里有一堆我刻意没有写死的地方。"}
                              for d in V9M["script_durs"]], v9_tl, 570.869, None, POLICY)
check("D6c DQ-6 v9 真值：末 2 镜无 outro 关键词 + 尾部静音 570.869 s → FAIL",
      e_v9["state"] == "FAIL" and not e_v9["outro_keyword_hits"], e_v9["state"])

# ---------------- D7 DQ-7 ----------------
s_unknown = D.summarize_direction({"DQ-1": {"state": "UNKNOWN", "semantic": True}})
s_na = D.summarize_direction({"DQ-1": {"state": "NOT_ASSESSABLE", "semantic": True}})
s_fail = D.summarize_direction({"DQ-2": {"state": "FAIL"}, "DQ-4": {"state": "PASS"}})
s_pass = D.summarize_direction({"DQ-2": {"state": "PASS"}, "DQ-4": {"state": "PASS"}})
check("D7 DQ-7 汇总口径：UNKNOWN→UNKNOWN / NOT_ASSESSABLE→NOT_ASSESSABLE / 有 FAIL→FAIL / "
      "全 PASS→PASS（UNKNOWN≠PASS）",
      s_unknown["overall"] == "UNKNOWN" and s_na["overall"] == "NOT_ASSESSABLE"
      and s_fail["overall"] == "FAIL" and s_pass["overall"] == "PASS"
      and s_unknown["unknown_is_not_pass"] is True,
      {k: v["overall"] for k, v in (("u", s_unknown), ("na", s_na), ("f", s_fail),
                                    ("p", s_pass))})

# ---------------- D8/D9 只读 + CLI ----------------
if DB.is_file():
    before = {p.relative_to(ROOT).as_posix(): (p.stat().st_size, int(p.stat().st_mtime))
              for p in (ROOT / "projects" / V9["project_id"]).rglob("*") if p.is_file()}
    db_before = sha(DB)
    ev_path = ROOT / "docs" / "regression_2x" / "logs" / "audit_p96efdc_mm.json"
    r = subprocess.run([sys.executable, "run.py", "direction", V9["project_id"], "--json",
                        "--film-task", V9["film_task"], "--no-freeze",
                        "--evidence", str(ev_path)], cwd=str(ROOT), capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=1800)
    after = {p.relative_to(ROOT).as_posix(): (p.stat().st_size, int(p.stat().st_mtime))
             for p in (ROOT / "projects" / V9["project_id"]).rglob("*") if p.is_file()}
    db_after = sha(DB)
    try:
        cli = json.loads(r.stdout)
    except Exception as exc:                                    # noqa: BLE001
        cli = {"err": repr(exc), "head": (r.stdout or "")[:200]}
    check("D8a 只读：direction 报告后项目目录零新增/零改动 + DB sha256 不变",
          before == after and db_before == db_after,
          {"new": sorted(set(after) - set(before)), "db_same": db_before == db_after})
    check("D8b `run.py direction --json`：结构可机读、只读未接线、DQ 指标齐全"
          "（6-A/M1 六项 + 6-B/M1 新增 DQ-8；DQ-7 为总评）",
          cli.get("schema") == "directorial-quality-v1" and cli.get("read_only") is True
          and cli.get("enforced") is False
          and set(cli.get("metrics", {})) == {"DQ-1", "DQ-2", "DQ-3", "DQ-4", "DQ-5", "DQ-6",
                                              "DQ-8"},
          {k: cli.get(k) for k in ("schema", "read_only", "enforced")})
    if cli.get("metrics"):
        mm = cli["metrics"]
        check("D8c 端到端复现 v9：DQ-2/DQ-3/DQ-4/DQ-5/DQ-6 = FAIL、DQ-1 = UNKNOWN、"
              "DQ-8 逐镜语义支撑有判定、语义项单列且 UNKNOWN≠PASS",
              mm["DQ-1"]["state"] == "UNKNOWN"
              and all(mm[k]["state"] == "FAIL" for k in ("DQ-2", "DQ-3", "DQ-4", "DQ-5", "DQ-6"))
              and mm["DQ-8"]["state"] in ("FAIL", "UNKNOWN", "NOT_ASSESSABLE", "PASS")
              and cli["summary"]["overall"] == "FAIL"
              and cli["summary"]["semantic_states"].get("DQ-1") == "UNKNOWN"
              and set(cli["summary"]["semantic_metrics"]) >= {"DQ-1", "DQ-5", "DQ-6", "DQ-8"},
              {k: v["state"] for k, v in mm.items()})
else:
    skip("D8 端到端 / 只读", "无 DB")

print("\n结果: {}/{} 通过{}".format(len(PASS), len(PASS) + len(FAIL),
                                   "（另有 {} 项 SKIP）".format(len(SKIP)) if SKIP else ""))
if FAIL:
    print("失败项:", FAIL)
sys.exit(0 if not FAIL else 1)
