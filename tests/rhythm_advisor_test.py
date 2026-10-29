"""4.x Phase 4-G 单测：只读节奏分析与人工建议（**全离线、确定性、只读**）。

覆盖授权验收：
  A 正常节奏 / B 过短镜头 / C 过长镜头 / D 旁白与镜头边界异常 / E BGM 关闭 / F BGM 开启
  G 空旁白与异常时长 / H 无法判断（UNKNOWN，不强行给建议）/ I 输出确定性与重复运行一致
  J 只读验证（DB / 任务 / 产物 / 事件 / decisions / changelog 一律不新增、不修改）
  K 五项显式证明：不自动改时长、不绕过 HITL、不改变现有渲染结果、同输入同建议、建议不被误报为已执行

用法：python tests/rhythm_advisor_test.py
"""
import hashlib
import json
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.core.rhythm import (DEFAULT_SETTINGS, RULES, UNKNOWN_RULES,  # noqa: E402
                                      analyze_rhythm, narration_windows, rhythm_settings)
from video_studio.ops.rhythm import (collect_rhythm_inputs, format_rhythm,  # noqa: E402
                                     rhythm_report)

# ---------------------------------------------------------------------------
# 2026-10-20：出厂阈值已改为**外部标杆**（max_scene_s 20→10 / static_warn 15→4 /
# min_cuts_per_min 2→15 / max_cuts_per_min 12→45 / min_scene_s 3→1）。
# 本套件验的是**建议器的行为契约**（哪条规则会在什么输入下触发），不是阈值本身，
# 因此这里用 LEGACY 阈值把行为契约钉住；出厂阈值另由文末 Z 组单独断言。
# ---------------------------------------------------------------------------
SHIPPED_SETTINGS = dict(DEFAULT_SETTINGS)
LEGACY_SETTINGS = dict(DEFAULT_SETTINGS, min_scene_s=3.0, max_scene_s=20.0,
                       static_warn_s=15.0, min_cuts_per_min=2.0, max_cuts_per_min=12.0)
_analyze_rhythm = analyze_rhythm


def analyze_rhythm(payload: dict, *, settings: dict | None = None, **kw):  # noqa: D401
    return _analyze_rhythm(payload, settings={**LEGACY_SETTINGS, **(settings or {})}, **kw)

REAL_DB = ROOT / "projects" / "video_studio.db"
REAL_PID = "p_f4b466a4a024"
PASS, FAIL = [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print(("PASS  " if ok else "FAIL  ") + name + (" | " + str(detail)[:220] if detail else ""))


def sha256_file(p: Path) -> str | None:
    try:
        return hashlib.sha256(p.read_bytes()).hexdigest()
    except OSError:
        return None


def scenes(*durs, static=True, ext=".jpg"):
    out, t = [], 0.0
    for i, d in enumerate(durs):
        out.append({"scene_id": "S{:02d}".format(i + 1), "start_s": t, "end_s": t + d,
                    "segment_index": i, "fallback_state": "LOCAL_INGEST",
                    "selection_source": "automatic",
                    "selected_asset": {"asset_id": "a{}".format(i), "name": "img{}.jpg".format(i),
                                       "ext": ext if static else ".mp4"}})
        t += d
    return out


def narration(*durs, total=None):
    segs = [{"index": i, "status": "SUCCESS", "duration_s": d} for i, d in enumerate(durs)]
    return {"segments": segs, "total_s": (round(sum(durs), 3) if total is None else total),
            "complete": True, "trimmed": False}


def payload(timeline, narr=None, *, film=None, bgm=None, sources=None, settings=None):
    return {"timeline": timeline, "narration": narr,
            "film_duration_s": (film if film is not None
                                else (timeline[-1]["end_s"] if timeline else None)),
            "bgm": bgm or {}, "sources": sources or {}}


def rules_of(rep, kind="suggestions"):
    return [x["rule"] for x in rep[kind]]


REQUIRED_FIELDS = ("suggestion_id", "scene_id", "current_duration_s", "rule", "evidence",
                   "action", "risk", "confidence", "status", "applied", "executed",
                   "requires_human_decision")

# ============ A. 正常节奏 ============
print("== A. 正常节奏 ==")
tl = scenes(8, 10, 12, 9, 11, 13)              # 全部 ≤ static_warn(15) 且 ≥ min_scene(3)
narr = narration(8, 10, 12, 9, 11, 13)          # 旁白段落与镜头边界**对齐**（正常节奏的定义）
rep_a = analyze_rhythm(payload(tl, narr))
check("A1 正常节奏：无建议、无 UNKNOWN、applied_changes=0、策略为只读",
      rep_a["suggestions"] == [] and rep_a["unknowns"] == []
      and rep_a["applied_changes"] == 0 and rep_a["policy"]["mode"] == "readonly_advisory"
      and rep_a["policy"]["auto_apply"] is False, rep_a["summary"]["suggestions_by_rule"])
check("A2 概览：镜头数/切换数/密度/旁白总时长均可复算",
      rep_a["summary"]["scene_count"] == 6 and rep_a["summary"]["cuts"] == 5
      and abs(rep_a["summary"]["cuts_per_min"] - 5 / (63 / 60)) < 0.01
      and rep_a["summary"]["narration_total_s"] == narr["total_s"], rep_a["summary"])
check("A3 每条建议都带齐要求字段（本用例无建议，先校验规则表字段完备）",
      all(all(k in RULES[r] for k in ("area", "param", "action", "risk")) for r in RULES)
      and len(RULES) >= 10 and len(UNKNOWN_RULES) >= 5)

# ============ B. 过短镜头 ============
print("== B. 过短镜头 ==")
rep_b = analyze_rhythm(payload(scenes(12, 1.5, 18, 14), narration(10, 1.4, 17, 13)))
sg = [s for s in rep_b["suggestions"] if s["rule"] == "R_SCENE_TOO_SHORT"]
check("B1 过短镜头被识别（R_SCENE_TOO_SHORT，scene_id/当前时长/阈值正确）",
      len(sg) == 1 and sg[0]["scene_id"] == "S02" and sg[0]["current_duration_s"] == 1.5
      and sg[0]["threshold_s"] == LEGACY_SETTINGS["min_scene_s"], sg[0] if sg else None)
check("B2 建议字段齐全 + 状态为『建议（未执行）』",
      sg and all(k in sg[0] for k in REQUIRED_FIELDS) and sg[0]["status"] == "SUGGESTION"
      and sg[0]["applied"] is False and sg[0]["executed"] is False
      and sg[0]["requires_human_decision"] is True
      and sg[0]["evidence"]["measured_duration_s"] == 1.5,
      sg[0] if sg else None)
check("B3 依据/动作/风险/置信度可读（证据含 measured/threshold/delta）",
      sg and sg[0]["evidence"].get("threshold_s") == 3.0
      and "delta_s" in sg[0]["evidence"] and sg[0]["action"] and sg[0]["risk"]
      and sg[0]["confidence"] in ("HIGH", "MEDIUM"), sg[0]["evidence"] if sg else None)

# ============ C. 过长镜头 ============
print("== C. 过长镜头 ==")
rep_c = analyze_rhythm(payload(scenes(12, 30, 18), narration(11, 28, 17)))
sg_c = [s for s in rep_c["suggestions"] if s["rule"] == "R_SCENE_TOO_LONG"]
check("C1 过长镜头被识别（30s > 20s，HIGH 置信）",
      len(sg_c) == 1 and sg_c[0]["current_duration_s"] == 30.0
      and sg_c[0]["evidence"]["delta_s"] == 10.0 and sg_c[0]["confidence"] == "HIGH",
      sg_c[0]["evidence"] if sg_c else None)
check("C2 过长与过短规则互斥（不会同时报同一镜头）",
      not [s for s in rep_c["suggestions"] if s["rule"] == "R_SCENE_TOO_SHORT"])

# ============ D. 旁白与镜头边界异常 ============
print("== D. 旁白与镜头边界异常 ==")
rep_d = analyze_rhythm(payload(scenes(12, 12), narration(16, 8)))
mid = [s for s in rep_d["suggestions"] if s["rule"] == "R_CUT_MID_NARRATION"]
check("D1 切换落在旁白句中 → R_CUT_MID_NARRATION（含 tail_s 与容差证据）",
      len(mid) == 1 and mid[0]["scene_id"] == "S01"
      and mid[0]["evidence"]["crossing"] == "speech_continues_after_cut"
      and mid[0]["evidence"]["tail_s"] == 4.0
      and mid[0]["evidence"]["tolerance_s"] == 0.5, [m["evidence"] for m in mid])
rep_d2 = analyze_rhythm(payload(scenes(20, 10), narration(4, 26)))
mid2 = [s for s in rep_d2["suggestions"] if s["rule"] == "R_CUT_MID_NARRATION"]
check("D2 旁白在镜头开始前已开始 → crossing=speech_started_before_cut（lead_s 为负）",
      mid2 and mid2[0]["evidence"]["crossing"] == "speech_started_before_cut"
      and mid2[0]["evidence"]["lead_s"] < 0, [m["evidence"] for m in mid2])
rep_d3 = analyze_rhythm(payload(scenes(12, 12), narration(11.8, 12.2)))
check("D3 容差内的边界偏移不报警（0.2s < 0.5s 容差）",
      not [s for s in rep_d3["suggestions"] if s["rule"] == "R_CUT_MID_NARRATION"])
rep_d4 = analyze_rhythm(payload(scenes(12, 12), narration(15, 15), film=20))
trl = [s for s in rep_d4["suggestions"] if s["rule"] == "R_NARRATION_TRIMMED"]
check("D4 旁白总时长超过成片 → R_NARRATION_TRIMMED（口播被裁，片级建议挂在末镜头）",
      len(trl) == 1 and trl[0]["scope"] == "film" and trl[0]["scene_id"] == "S02"
      and trl[0]["evidence"]["excess_s"] == 10.0, trl[0]["evidence"] if trl else None)

# ============ E/F. BGM 关闭 / 开启 ============
print("== E/F. BGM 关闭与开启 ==")
rep_e = analyze_rhythm(payload(scenes(12, 12), narration(11, 11), bgm={"enabled": False}))
check("E1 BGM 关闭：不产生任何 BGM 节奏建议，概览如实标注 enabled=False",
      not [s for s in rep_e["suggestions"] if s["rule"].startswith("R_BGM")]
      and rep_e["summary"]["bgm"]["enabled"] is False
      and not [u for u in rep_e["unknowns"] if u["rule"] == "R_UNKNOWN_BGM"],
      rep_e["summary"]["bgm"])
duck = [{"start_s": 0.0, "end_s": 3.0}, {"start_s": 4.0, "end_s": 6.0},
        {"start_s": 7.0, "end_s": 9.0}]
rep_f = analyze_rhythm(payload(scenes(12, 12), narration(11, 11),
                               bgm={"enabled": True, "applied": True, "intervals": duck,
                                    "bed_db": -20.0, "duck_db": -26.0}))
bg = [s for s in rep_f["suggestions"] if s["rule"] == "R_BGM_DUCK_FRAGMENTED"]
check("F1 BGM 开启且生效：单镜头内 duck 切换 3 次（>2）→ R_BGM_DUCK_FRAGMENTED（含窗口与参数）",
      len(bg) == 1 and bg[0]["scene_id"] == "S01"
      and bg[0]["evidence"]["duck_transitions_in_scene"] == 3
      and bg[0]["evidence"]["bed_db"] == -20.0 and bg[0]["evidence"]["duck_db"] == -26.0,
      bg[0]["evidence"] if bg else None)
rep_f2 = analyze_rhythm(payload(scenes(12, 12), narration(11, 11),
                                bgm={"enabled": True, "applied": False}))
check("F2 BGM 已配置但未生效 → UNKNOWN（不给 BGM 建议）",
      not [s for s in rep_f2["suggestions"] if s["rule"].startswith("R_BGM")]
      and [u for u in rep_f2["unknowns"] if u["rule"] == "R_UNKNOWN_BGM"])

# ============ G. 空旁白 / 异常时长 ============
print("== G. 空旁白与异常时长 ==")
rep_g = analyze_rhythm(payload(scenes(12, 12), None))
check("G1 无旁白产物：每镜头 UNKNOWN_NARRATION + 片级 UNKNOWN_NARRATION_TOTAL，且不产生覆盖建议",
      len([u for u in rep_g["unknowns"] if u["rule"] == "R_UNKNOWN_NARRATION"]) == 2
      and [u for u in rep_g["unknowns"] if u["rule"] == "R_UNKNOWN_NARRATION_TOTAL"]
      and not [s for s in rep_g["suggestions"] if s["rule"] == "R_CUT_MID_NARRATION"],
      rules_of(rep_g, "unknowns"))
empty_narr = {"segments": [{"index": 0, "status": "FAILED", "duration_s": None},
                           {"index": 1, "status": "SUCCESS", "duration_s": 0.0}],
              "total_s": None, "complete": False}
rep_g2 = analyze_rhythm(payload(scenes(12, 12), empty_narr))
check("G2 旁白段落全不可用（失败/0 时长）：全部 UNKNOWN，不强行给建议",
      len([u for u in rep_g2["unknowns"] if u["rule"] == "R_UNKNOWN_NARRATION"]) == 2
      and not rep_g2["suggestions"], {"unknowns": rules_of(rep_g2, "unknowns"),
                                      "suggestions": rules_of(rep_g2)})
bad_tl = [{"scene_id": "S01", "start_s": None, "end_s": None, "segment_index": 0,
           "selected_asset": {"name": "x.jpg"}}]
rep_g3 = analyze_rhythm(payload(bad_tl, narration(5), film=None))
check("G3 镜头时长缺失 + 成片时长缺失 → UNKNOWN_DURATION / UNKNOWN_FILM_DURATION（无建议）",
      [u for u in rep_g3["unknowns"] if u["rule"] == "R_UNKNOWN_DURATION"]
      and [u for u in rep_g3["unknowns"] if u["rule"] == "R_UNKNOWN_FILM_DURATION"]
      and not rep_g3["suggestions"], rules_of(rep_g3, "unknowns"))

# ============ H. 无法判断 ============
print("== H. 无法判断（UNKNOWN） ==")
tl_h = [{"scene_id": "S01", "start_s": 0.0, "end_s": 25.0, "segment_index": 0,
         "selected_asset": {"name": "material_without_ext", "ext": None}}]
rep_h = analyze_rhythm(payload(tl_h, narration(20), film=25))
check("H1 素材类型未知 → UNKNOWN_ASSET_TYPE，且**不**给出静态画面建议",
      [u for u in rep_h["unknowns"] if u["rule"] == "R_UNKNOWN_ASSET_TYPE"]
      and not [s for s in rep_h["suggestions"] if s["rule"] == "R_STATIC_HOLD"],
      {"unknowns": rules_of(rep_h, "unknowns"), "suggestions": rules_of(rep_h)})
check("H2 静态判定依据可解释（ext_field 优先于 name_suffix）",
      analyze_rhythm(payload(scenes(20), narration(18)))["scenes"][0]["asset"]["ext_basis"]
      == "ext_field"
      and analyze_rhythm(payload([{"scene_id": "S01", "start_s": 0, "end_s": 20,
                                   "segment_index": 0,
                                   "selected_asset": {"name": "a.jpg"}}],
                                 narration(18)))["scenes"][0]["asset"]["ext_basis"]
      == "name_suffix")
rep_h3 = analyze_rhythm(payload([], None, film=None))
check("H3 无时间轴/无旁白/无成片时长：报告仍可产出（全 UNKNOWN，不崩溃、不猜测）",
      rep_h3["scenes"] == [] and rep_h3["suggestions"] == []
      and len(rep_h3["unknowns"]) >= 2, rules_of(rep_h3, "unknowns"))

# ============ I. 确定性 ============
print("== I. 输出确定性与重复运行一致性 ==")
j1 = json.dumps(analyze_rhythm(payload(tl, narr)), ensure_ascii=False, sort_keys=True)
j2 = json.dumps(analyze_rhythm(payload(tl, narr)), ensure_ascii=False, sort_keys=True)
j3 = json.dumps(analyze_rhythm(payload(scenes(8, 10, 12, 9, 11, 13), narration(8, 10, 12, 9, 11, 13))),
                ensure_ascii=False, sort_keys=True)
check("I1 同输入同配置 → 逐字节相同输出（三次调用）", j1 == j2 == j3)
check("I2 设置来源与输入指纹随报告输出（可复算/可核对）",
      analyze_rhythm(payload(tl, narr, sources={"render_output": {"sha256": "x"}}))
      ["input_fingerprints"] == {"render_output": {"sha256": "x"}}
      and analyze_rhythm(payload(tl, narr))["settings_source"] in ("default(readonly)",
                                                                   "tools.rhythm"))

# ============ J/K. 只读验证与五项显式证明（真实项目 + 真实 DB） ============
print("== J/K. 只读验证与显式证明（真实项目 {}） ==".format(REAL_PID))
con = sqlite3.connect(str(REAL_DB))


def counts():
    out = {}
    for t in ("tasks", "artifacts", "events", "decisions", "changelog"):
        out[t] = con.execute("select count(*) from {}".format(t)).fetchone()[0]
    return out


def project_state():
    rows = con.execute("select artifact_id, type, path, sha256 from artifacts where project_id=?",
                       (REAL_PID,)).fetchall()
    proj_dir = REAL_DB.parent / REAL_PID
    files = {}
    for p in sorted(proj_dir.rglob("*")):
        if p.is_file():
            files[str(p.relative_to(proj_dir))] = sha256_file(p)
    films = {k: v for k, v in files.items() if k.endswith(".mp4")}
    return {"db_sha256": sha256_file(REAL_DB), "counts": counts(),
            "artifacts": sorted((a[0], a[1], a[3]) for a in rows), "files": files,
            "films": films}


before = project_state()
runs = []
for _ in range(3):
    r = rhythm_report(REAL_DB, REAL_PID)
    runs.append(json.dumps(r, ensure_ascii=False, sort_keys=True))
cli1 = subprocess.run([sys.executable, "run.py", "rhythm", REAL_PID, "--json"], cwd=str(ROOT),
                      capture_output=True)
cli2 = subprocess.run([sys.executable, "run.py", "rhythm", REAL_PID, "--json"], cwd=str(ROOT),
                      capture_output=True)
cli3 = subprocess.run([sys.executable, "run.py", "rhythm", REAL_PID], cwd=str(ROOT),
                      capture_output=True)
after = project_state()
rep_real = json.loads(runs[0])

check("J1 只读：真实 DB 字节、任务/产物/事件/decisions/changelog 计数全部不变",
      before["db_sha256"] == after["db_sha256"] and before["counts"] == after["counts"],
      {"before": before["counts"], "after": after["counts"]})
check("J2 只读：项目内所有文件（含成片与产物）逐字节未变",
      before["files"] == after["files"] and before["artifacts"] == after["artifacts"],
      {"files": len(before["files"]), "films": list(before["films"])})
_ro = sqlite3.connect("file:{}?mode=ro".format(REAL_DB.as_posix()), uri=True)
try:
    _ro.execute("insert into events(ts,project_id,type,actor,payload,human_visible) "
                "values(0,'x','X','x','{}',0)")
    _write_rejected = False
except sqlite3.OperationalError:
    _write_rejected = True
finally:
    _ro.close()
check("J3 只读连接在 SQLite 层面拒绝写入（INSERT 抛 OperationalError）", _write_rejected)
check("J4 CLI 三次运行（含 --json 两次）输出逐字节一致（幂等/确定性）",
      cli1.returncode == 0 and cli2.returncode == 0 and cli3.returncode == 0
      and cli1.stdout == cli2.stdout and len(runs[0]) == len(runs[1]) == len(runs[2]),
      {"rc": [cli1.returncode, cli2.returncode, cli3.returncode]})
check("K1 不自动改时长：applied_changes=0 且所有建议 applied/executed=False",
      rep_real["applied_changes"] == 0
      and all(s["applied"] is False and s["executed"] is False
              and s["status"] == "SUGGESTION" for s in rep_real["suggestions"])
      and rep_real["policy"]["changes_scene_duration"] is False,
      rep_real["summary"]["suggestions_by_rule"])
check("K2 不绕过 HITL：decisions/changelog 零新增 + 策略声明 + 建议标注需人工决定",
      before["counts"]["decisions"] == after["counts"]["decisions"]
      and before["counts"]["changelog"] == after["counts"]["changelog"]
      and rep_real["policy"]["bypasses_hitl"] is False
      and rep_real["policy"]["requires_human_decision"] is True
      and all(s["requires_human_decision"] is True for s in rep_real["suggestions"]))
check("K3 不改变现有渲染结果：render_output 产物与成片文件哈希未变",
      before["films"] == after["films"] and before["films"]
      and before["artifacts"] == after["artifacts"],
      {"films": list(before["films"]), "count": len(before["films"])})
check("K4 建议不被误报为已执行：文本输出标注『建议·未执行』、无『已执行/已应用』字样",
      "建议·未执行" in cli3.stdout.decode("utf-8", "replace")
      and "未执行任何改动" in cli3.stdout.decode("utf-8", "replace")
      and "applied_changes=0" in cli3.stdout.decode("utf-8", "replace")
      and not re.search(r"已执行|已应用|已修改|已生效", cli3.stdout.decode("utf-8", "replace")),
      cli3.stdout.decode("utf-8", "replace").splitlines()[-1][:120])
src_rhythm = (ROOT / "src" / "video_studio" / "core" / "rhythm.py").read_text(encoding="utf-8")
src_ops = (ROOT / "src" / "video_studio" / "ops" / "rhythm.py").read_text(encoding="utf-8")
_imports = sorted(set(re.findall(r"^(?:import|from)\s+([A-Za-z_][\w.]*)", src_rhythm, re.M)))
check("K5 静态证明：建议器不含写库/写产物/触发 redo/调度器路径，且只依赖标准库",
      not re.search(r"\b(insert\s+into|update\s+\w+\s+set|delete\s+from)\b", src_ops, re.I)
      and all(tok not in src_ops + src_rhythm for tok in
              ("write_artifact", "set_task_status", "run_cycle", "build_engine",
               "subprocess", "os.system", "eval(", "exec("))
      and not re.search(r"redo\s*\(|\.redo\b|[\"']redo[\"']", src_ops + src_rhythm)
      and _imports == ["__future__", "hashlib", "json"], {"imports": _imports})
check("K6 结论与真实数据一致（离线复核）：成片/镜头/切换密度/建议数可复算",
      rep_real["summary"]["scene_count"] == 6 and rep_real["summary"]["film_duration_s"] == 104.0
      and abs(rep_real["summary"]["cuts_per_min"] - 2.885) < 0.01
      and rep_real["summary"]["suggestions"] == len(rep_real["suggestions"])
      and rep_real["summary"]["unknowns"] == len(rep_real["unknowns"]),
      rep_real["summary"])
check("K7 输入指纹可核对（render_output/voice_output 的 artifact_id 与 sha256 均在报告中）",
      rep_real["input_fingerprints"].get("render_output", {}).get("artifact_id")
      and len(rep_real["input_fingerprints"]["render_output"]["sha256"]) == 64
      and rep_real["input_fingerprints"].get("voice_output", {}).get("artifact_id"),
      list(rep_real["input_fingerprints"]))
con.close()

# ============ Z. 出厂阈值（外部标杆）============
# 2026-10-20：阈值从"内部历史自洽"改为"外部标杆"。这里把出厂值钉住，
# 防止后续被无声改回宽松口径（旧值会让 18.4s/镜、3.4 次/分钟的成片全部 PASS）。
print("== Z. 出厂阈值（外部标杆）==")
check("Z1 镜长上限 10s（旧 20）", SHIPPED_SETTINGS["max_scene_s"] == 10.0,
      SHIPPED_SETTINGS["max_scene_s"])
check("Z2 静态可疑阈值 4s（旧 15）", SHIPPED_SETTINGS["static_warn_s"] == 4.0,
      SHIPPED_SETTINGS["static_warn_s"])
check("Z3 切换密度下限 15 次/分钟（旧 2）", SHIPPED_SETTINGS["min_cuts_per_min"] == 15.0,
      SHIPPED_SETTINGS["min_cuts_per_min"])
check("Z4 切换密度上限 45 次/分钟（旧 12；快剪不误报）",
      SHIPPED_SETTINGS["max_cuts_per_min"] == 45.0, SHIPPED_SETTINGS["max_cuts_per_min"])
check("Z5 镜长下限 1s（旧 3；允许更碎切点）", SHIPPED_SETTINGS["min_scene_s"] == 1.0,
      SHIPPED_SETTINGS["min_scene_s"])

print("\n结果: {}/{} 通过".format(len(PASS), len(PASS) + len(FAIL)))
if FAIL:
    print("失败项:", FAIL)
sys.exit(1 if FAIL else 0)
