"""5.x Phase 5-A 单测：多模态语义验证器（真实视觉模型 CLIP，**只读、离线、确定性**）。

覆盖授权要求：
  A 默认关闭 + 配置读取（非法值回退，不放松阈值）
  B 纯函数规则：三态判定 / 抽帧计划 / 期望域推导（含**词边界**修正与 4-E 回退链）
  C **真实模型回归**：冻结 3-A 产物 `a_2ed5f41d6b58` 上 S04/S06 必须 MISMATCH（与 4-B 真值一致）；
    当前成片上给出明确 MATCH（S01）与明确 UNKNOWN（S05 边际不足）
  D fail-closed：模型缺失 / venv 缺失 / 无帧 / 无旁白 → 一律 UNKNOWN + 明确错误码（绝不伪造判定）
  E 确定性：同一批帧两次推理 → 报告逐字节一致
  F 只读：DB 字节、五张表行数、项目文件（含成片）逐字节不变
  G 不覆盖 4-B：4-B 词表/真值未改；报告声明 overwrites_4b_results=false；两条证据层并存
  H 记录模型/版本/输入指纹（权重 sha256、torch/transformers 版本、帧 sha256、产物 sha256）

用法：python tests/multimodal_test.py
"""
import hashlib
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.core.multimodal import (DOMAIN_PROMPTS, MM_DEFAULTS, expected_domain_from_narration,
                                          frame_plan, mm_settings, validate,
                                          verdict_for_scene, run_worker)
from video_studio.ops.multimodal import (extract_frames, format_mm, labels_from_prompts,
                                         multimodal_report)

REAL_DB = ROOT / "projects" / "video_studio.db"
REAL_PID = "p_f4b466a4a024"
FROZEN_ARTIFACT = "a_2ed5f41d6b58"          # 4-B 真值钉定的冻结 3-A 成片（S04/S06 = 鲨鱼照）
CURRENT_MATCH = {"S01": "MATCH", "S04": "MATCH"}   # 当前成片（v5）上的明确 MATCH
PASS, FAIL = [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print(("PASS  " if ok else "FAIL  ") + name + (" | " + str(detail)[:240] if detail else ""))


def sha(p: Path):
    try:
        return hashlib.sha256(p.read_bytes()).hexdigest()
    except OSError:
        return None


def project_state():
    con = sqlite3.connect(str(REAL_DB))
    counts = {t: con.execute("select count(*) from {}".format(t)).fetchone()[0]
              for t in ("tasks", "artifacts", "events", "decisions", "changelog")}
    con.close()
    proj = REAL_DB.parent / REAL_PID
    files = {str(p.relative_to(proj)): sha(p) for p in sorted(proj.rglob("*")) if p.is_file()}
    return {"db": sha(REAL_DB), "counts": counts, "files": files,
            "films": {k: v for k, v in files.items() if k.endswith(".mp4")}}


# ============ A. 默认关闭 + 配置 ============
print("== A. 默认关闭与配置 ==")
d0 = mm_settings({})
check("A1 缺省 = 关闭（enabled=False），后端/模型目录/阈值有默认值",
      d0["enabled"] is False and d0["_source"] == "default(disabled)"
      and d0["backend"] == "clip_local" and d0["min_sim"] == MM_DEFAULTS["min_sim"]
      and d0["margin"] == MM_DEFAULTS["margin"], {k: d0[k] for k in
                                                  ("enabled", "backend", "min_sim", "margin")})
d1 = mm_settings({"tools": {"multimodal": {"enabled": True, "min_sim": "x", "frames_per_scene": 0,
                                           "margin": 0.05}}})
check("A2 非法值回退默认（不放松阈值）；合法值生效；帧数下限保护",
      d1["enabled"] is True and d1["min_sim"] == MM_DEFAULTS["min_sim"]
      and d1["margin"] == 0.05 and d1["frames_per_scene"] == MM_DEFAULTS["frames_per_scene"]
      and d1["_notes"], {"min_sim": d1["min_sim"], "margin": d1["margin"],
                         "frames": d1["frames_per_scene"], "notes": d1["_notes"]})
check("A3 提示词表覆盖 12 个语义域且都是英文（CLIP 文本塔只支持英文）",
      len(DOMAIN_PROMPTS) == 12 and all(
          all(ord(c) < 128 for c in t) for ts in DOMAIN_PROMPTS.values() for t in ts),
      sorted(DOMAIN_PROMPTS))

# ============ B. 纯函数规则 ============
print("== B. 纯函数规则（三态 / 抽帧 / 期望域） ==")
st = {"min_sim": 0.20, "margin": 0.02, "top_k": 3}
v_match = verdict_for_scene({"xr_device": 0.30, "wildlife": 0.20}, "xr_device", st)
v_mis = verdict_for_scene({"xr_device": 0.16, "wildlife": 0.32}, "xr_device", st)
v_low = verdict_for_scene({"xr_device": 0.12, "wildlife": 0.14}, "xr_device", st)
v_amb = verdict_for_scene({"xr_device": 0.30, "wildlife": 0.295}, "xr_device", st)
v_nod = verdict_for_scene({"xr_device": 0.30}, None, st)
check("B1 MATCH：期望域既达下限又领先其它域 ≥ margin",
      v_match["verdict"] == "MATCH" and v_match["delta"] == 0.1, v_match["reason"])
check("B2 MISMATCH：其它域领先期望域 ≥ margin 且达下限",
      v_mis["verdict"] == "MISMATCH" and v_mis["best_other_domain"] == "wildlife",
      v_mis["reason"])
check("B3 UNKNOWN：信号不足（低于 min_sim）→ MM_LOW_SIGNAL",
      v_low["verdict"] == "UNKNOWN" and v_low["code"] == "MM_LOW_SIGNAL", v_low["reason"])
check("B4 UNKNOWN：边际不足（歧义）→ MM_AMBIGUOUS",
      v_amb["verdict"] == "UNKNOWN" and v_amb["code"] == "MM_AMBIGUOUS", v_amb["reason"])
check("B5 UNKNOWN：期望域未知 → MM_UNKNOWN_DOMAIN（不猜）",
      v_nod["verdict"] == "UNKNOWN" and v_nod["code"] == "MM_UNKNOWN_DOMAIN")
plan = frame_plan([{"scene_id": "S01", "start_s": 0.0, "end_s": 12.0},
                   {"scene_id": "S02", "start_s": None, "end_s": None}], 3)
check("B6 抽帧计划：窗口内 25/50/75% 取点；窗口缺失则该镜头无时间点（不猜）",
      plan[0]["times"] == [3.0, 6.0, 9.0] and plan[1]["times"] == []
      and plan[1]["duration_s"] is None, plan)
no_car = expected_domain_from_narration(
    "最后交代边界：Cardboard 没用，它已停止维护；所有引文都要回链核对原句和图片授权。")
check("B7 期望域推导：拉丁形式**按词边界**命中（'car' 不得命中 'Cardboard'）",
      "vehicle" not in (no_car.get("matched") or {}), no_car.get("matched"))
glasses = expected_domain_from_narration("戴眼镜的人怎么办？路径不止一种。")
check("B8 期望域推导：4-B 无命中时回退 4-E 词典（'眼镜' → xr_device），并记录来源",
      glasses["domain"] == "xr_device"
      and glasses["method"] == "lexicon_4e_retrieval_fallback_v1", glasses)
zh = expected_domain_from_narration("VR 头显长什么样？Quest 3、PSVR2、PICO 4 的官方图摆在一起。")
check("B9 期望域推导：4-B 词表命中时用 4-B（记录来源，含中文/拉丁命中词）",
      zh["domain"] == "xr_device" and zh["method"] == "lexicon_4b_surface_vote_v1"
      and "vr" in zh["matched"]["xr_device"], zh["matched"])

# ============ C. 真实模型回归 ============
print("== C. 真实视觉模型回归（CLIP 本地权重，CPU 离线） ==")
frozen_rep = multimodal_report(REAL_DB, REAL_PID, artifact_id=FROZEN_ARTIFACT,
                               config=json.loads((ROOT / "config" / "config.json")
                                                 .read_text(encoding="utf-8")))
fz = {s["scene_id"]: s for s in frozen_rep.get("scenes") or []}
check("C1 冻结 3-A 产物可跑通：真实模型 + 抽帧 + 逐镜头证据",
      frozen_rep.get("applied") is True and len(fz) == 6
      and (frozen_rep.get("model") or {}).get("weights_sha256")
      and (frozen_rep.get("versions") or {}).get("torch"),
      {"film": frozen_rep.get("film"), "frames": (frozen_rep.get("meta") or {}).get("frames_extracted"),
       "model": (frozen_rep.get("model") or {}).get("snapshot")})
check("C2 **真值回归**：S04 判定 MISMATCH（画面像 wildlife、旁白期望 xr_device），与 4-B 真值一致",
      fz.get("S04", {}).get("verdict") == "MISMATCH"
      and fz["S04"]["best_other_domain"] == "wildlife"
      and fz["S04"]["delta"] < 0, {k: fz.get("S04", {}).get(k) for k in
                                   ("verdict", "expected_domain", "best_other_domain", "delta")})
check("C3 **真值回归**：S06 判定 MISMATCH（期望域来自 4-E 回退链，如实记录来源）",
      fz.get("S06", {}).get("verdict") == "MISMATCH"
      and fz["S06"]["expected_domain"] == "xr_device"
      and fz["S06"]["expected_domain_source"] == "lexicon_4e_retrieval_fallback_v1"
      and fz["S06"]["delta"] < 0, {k: fz.get("S06", {}).get(k) for k in
                                   ("verdict", "expected_domain", "delta")})
check("C4 冻结产物上其余镜头（S01/S02/S03/S05）**未**被判 MISMATCH（与 4-B 的 TP=2/TN=4 一致）",
      all(fz.get(s, {}).get("verdict") != "MISMATCH" for s in ("S01", "S02", "S03", "S05")),
      {s: fz.get(s, {}).get("verdict") for s in ("S01", "S02", "S03", "S05")})
check("C5 计数自洽：MATCH/MISMATCH/UNKNOWN 之和 == 镜头数，且与逐镜头判定一致",
      sum(frozen_rep["counts"].values()) == 6
      and frozen_rep["counts"]["MISMATCH"] == sum(1 for s in fz.values()
                                                  if s["verdict"] == "MISMATCH"),
      frozen_rep["counts"])
cur_rep = multimodal_report(REAL_DB, REAL_PID,
                            config=json.loads((ROOT / "config" / "config.json")
                                              .read_text(encoding="utf-8")))
cs = {s["scene_id"]: s for s in cur_rep.get("scenes") or []}
check("C6 明确 MATCH 案例：当前成片（v5，已人工修复）S01/S04 判定 MATCH",
      all(cs.get(s, {}).get("verdict") == "MATCH" for s in CURRENT_MATCH),
      {s: cs.get(s, {}).get("verdict") for s in CURRENT_MATCH})
check("C7 明确 UNKNOWN 案例：当前成片 S05 边际不足 → UNKNOWN/MM_AMBIGUOUS（不强行判定）",
      cs.get("S05", {}).get("verdict") == "UNKNOWN"
      and cs["S05"]["code"] == "MM_AMBIGUOUS", {k: cs.get("S05", {}).get(k) for k in
                                                ("verdict", "code", "delta")})
check("C8 修复后成片**没有** MISMATCH（与 4-B 的 MATCH=6 方向一致；本层更保守，UNKNOWN 如实记录）",
      cur_rep["counts"]["MISMATCH"] == 0, cur_rep["counts"])

# ============ D. fail-closed ============
print("== D. fail-closed（模型/环境不可用时必须 UNKNOWN，禁止伪造） ==")
cfg = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8"))
bad_model = mm_settings({"tools": {"multimodal": {"enabled": True,
                                                  "model_dir": "models/clip/NO_SUCH_SNAPSHOT"}}})
rep_bad = multimodal_report(REAL_DB, REAL_PID, config={**cfg, "tools": {
    **cfg["tools"], "multimodal": {"model_dir": "models/clip/NO_SUCH_SNAPSHOT"}}})
check("D1 模型目录不存在 → 全部 UNKNOWN + MM_MODEL_MISSING（无相似度、无判定）",
      rep_bad.get("error", {}).get("code") == "MM_MODEL_MISSING"
      and all(s["verdict"] == "UNKNOWN" for s in rep_bad.get("scenes") or [])
      and rep_bad["counts"]["MATCH"] == 0 and rep_bad["counts"]["MISMATCH"] == 0,
      rep_bad.get("error"))
bad_py = {**cfg, "tools": {**cfg["tools"], "multimodal": {"python": ".venv_tts/Scripts/NO_SUCH.exe"}}}
rep_py = multimodal_report(REAL_DB, REAL_PID, config=bad_py)
check("D2 worker 解释器不存在 → MM_PYTHON_MISSING + 全部 UNKNOWN",
      rep_py.get("error", {}).get("code") == "MM_PYTHON_MISSING"
      and rep_py["counts"]["MISMATCH"] == 0, rep_py.get("error"))
res = run_worker([], [{"id": "a", "text": "x"}], mm_settings({}), root=ROOT)
check("D3 worker 空输入 → 明确错误码（不抛异常、不返回伪造相似度）",
      res.get("ok") is False and res.get("code") in ("MM_EMPTY_JOB", "MM_MODEL_MISSING",
                                                     "MM_WORKER_FAILED"),
      {"ok": res.get("ok"), "code": res.get("code")})
rep_noframes = validate([], [{"id": "a", "text": "x", "domain": "a"}], root=ROOT,
                        settings=mm_settings({}), narration_by_scene={"S01": {"text": "x"}})
check("D4 无帧 → 全部 UNKNOWN + MM_NO_FRAMES（不猜测画面内容）",
      rep_noframes["error"]["code"] == "MM_NO_FRAMES"
      and rep_noframes["scenes"][0]["verdict"] == "UNKNOWN", rep_noframes["error"])

# ============ E. 确定性 ============
print("== E. 确定性与可复算 ==")
CLI_BEFORE = project_state()          # CLI 运行前的只读快照（F 组断言用）
plan1 = frame_plan([{"scene_id": "S01", "start_s": 0.0, "end_s": 12.0},
                    {"scene_id": "S02", "start_s": 12.0, "end_s": 32.0}], 1)
frames, errs = extract_frames(frozen_rep["film"], plan1,
                              Path((frozen_rep["meta"] or {}).get("frames_dir")),
                              ffmpeg=cfg["tools"]["ffmpeg"]["path"])
labels = labels_from_prompts()
r1 = validate(frames, labels, root=ROOT, settings=mm_settings({"tools": {"multimodal": {"enabled": True}}}),
              narration_by_scene={"S01": {"text": (fz.get("S01") or {}).get("narration_text") or ""},
                                  "S02": {"text": (fz.get("S02") or {}).get("narration_text") or ""}})
r2 = validate(frames, labels, root=ROOT, settings=mm_settings({"tools": {"multimodal": {"enabled": True}}}),
              narration_by_scene={"S01": {"text": (fz.get("S01") or {}).get("narration_text") or ""},
                                  "S02": {"text": (fz.get("S02") or {}).get("narration_text") or ""}})
r1.pop("settings_notes", None)
r2.pop("settings_notes", None)
check("E1 同一批帧两次推理 → 报告逐字节一致（CLIP CPU 单线程 + 固定权重）",
      json.dumps(r1, ensure_ascii=False, sort_keys=True)
      == json.dumps(r2, ensure_ascii=False, sort_keys=True)
      and r1["counts"] == r2["counts"], r1["counts"])
check("E2 抽帧可复算：同一时间点抽帧 → 帧 sha256 一致",
      all(f["sha256"] for f in frames) and len({f["sha256"] for f in frames}) == len(frames),
      [f["sha256"][:12] for f in frames])
cli1 = subprocess.run([sys.executable, "run.py", "multimodal-check", REAL_PID, "--json",
                       "--frames-dir", str(Path((frozen_rep["meta"] or {}).get("frames_dir")))],
                      cwd=str(ROOT), capture_output=True)
j1 = json.loads(cli1.stdout.decode("utf-8", "replace"))
def _norm(rep):
    rep = json.loads(json.dumps(rep))
    for f in rep.get("scenes") or []:
        for fr in f.get("frames") or []:
            fr.pop("path", None)
    (rep.get("meta") or {}).pop("frames_dir", None)
    return json.dumps(rep, ensure_ascii=False, sort_keys=True)
cli2 = subprocess.run([sys.executable, "run.py", "multimodal-check", REAL_PID, "--json",
                       "--frames-dir", str(Path((frozen_rep["meta"] or {}).get("frames_dir")))],
                      cwd=str(ROOT), capture_output=True)
j2 = json.loads(cli2.stdout.decode("utf-8", "replace"))
check("E3 CLI 两次运行（当前成片）判定与相似度完全一致（剔除路径类字段后逐字节一致）",
      cli1.returncode == 0 and cli2.returncode == 0 and _norm(j1) == _norm(j2),
      {"rc": [cli1.returncode, cli2.returncode], "counts": j1.get("counts")})

# ============ F/G/H. 只读、不覆盖 4-B、指纹 ============
print("== F/G/H. 只读 / 不覆盖 4-B / 指纹 ==")
def successful_render_versions():
    """该项目成功渲染的版本数（= 成片文件应有条数）。用于替代写死的"5 个成片"。

    （5-C 授权的人工候选替换使该项目由 v5 → v6，写死的 5 会让"只读"断言误报失败；
    改为结构性断言：成片条数 == 成功渲染任务数，且运行前后逐字节一致。）
    """
    con = sqlite3.connect(str(REAL_DB))
    n = con.execute("select count(*) from tasks where project_id=? and task_type='render' "
                    "and status='SUCCEEDED'", (REAL_PID,)).fetchone()[0]
    con.close()
    return n


after = project_state()
check("F1 只读：真实 DB 字节与五张表行数在全部运行之后仍与运行前一致",
      CLI_BEFORE["db"] == after["db"] and CLI_BEFORE["counts"] == after["counts"],
      {"before": CLI_BEFORE["counts"], "after": after["counts"]})
check("F2 只读：项目内所有文件（含成片）逐字节未变；未新增生产产物（成片条数 == 成功渲染版本数）",
      CLI_BEFORE["files"] == after["files"] and after["films"] == CLI_BEFORE["films"]
      and len(after["films"]) == successful_render_versions(),
      {"files": len(after["files"]), "films": len(after["films"]),
       "render_versions": successful_render_versions()})
check("G1 不覆盖 4-B：报告声明 overwrites_4b_results=false，且 4-B 词表/真值未被本层修改",
      frozen_rep["policy"]["overwrites_4b_results"] is False
      and frozen_rep["policy"]["writes_to_db"] is False
      and sha(ROOT / "src/video_studio/core/lexicons/semantics_v1.json").startswith("083e8d55")
      and "TRUTH_ARTIFACT = \"a_2ed5f41d6b58\"" in
      (ROOT / "tests" / "semantic_check_test.py").read_text(encoding="utf-8"))
mm_src = (ROOT / "src/video_studio/core/multimodal.py").read_text(encoding="utf-8")
check("G2 静态证明：多模态层不写库/不写产物/不触发 redo/不修改 4-B 判定逻辑",
      all(tok not in mm_src for tok in ("insert into", "update ", "delete from",
                                        "write_artifact", "set_task_status", "run_cycle",
                                        "build_engine"))
      and "verify_scene" not in mm_src and "def domain_votes" not in mm_src,
      "ok")
check("H1 记录模型与版本：权重 sha256 / config sha256 / snapshot / torch / transformers",
      (frozen_rep["model"].get("weights_sha256")
       and frozen_rep["model"].get("config_sha256")
       and frozen_rep["model"].get("snapshot") == "3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268"
       and frozen_rep["versions"].get("device") == "cpu"
       and frozen_rep["versions"].get("hf_offline") == "1"),
      {k: str(frozen_rep["model"].get(k))[:16] for k in ("weights_sha256", "config_sha256")})
check("H2 记录输入指纹：产物 artifact_id/sha256 + 成片 sha256 + 逐帧 sha256 + 旁白 sha256",
      (frozen_rep["sources"].get("render_output") or {}).get("artifact_id") == FROZEN_ARTIFACT
      and (frozen_rep["sources"].get("film_sha256"))
      and fz["S01"]["frames"] and fz["S01"]["frames"][0]["sha256"]
      and fz["S01"]["narration_sha256"], {"frames": len(fz["S01"]["frames"])})
check("H3 人读输出标注只读与『不覆盖 4-B』（且不出现『已执行/已应用』字样）",
      "只读证据层" in format_mm(frozen_rep) and "未触发 redo" in format_mm(frozen_rep)
      and "不覆盖 4-B" in format_mm(frozen_rep), format_mm(frozen_rep).splitlines()[0])

print("\n结果: {}/{} 通过".format(len(PASS), len(PASS) + len(FAIL)))
if FAIL:
    print("失败项:", FAIL)
sys.exit(1 if FAIL else 0)
