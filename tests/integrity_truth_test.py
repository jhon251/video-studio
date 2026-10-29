# -*- coding: utf-8 -*-
"""6-A / M3 —— **Production Integrity 冻结真值集（v2）回归**：度量语义 + 门禁语义 + 审计与边界。

覆盖（对应 6-A/M3 授权书）：
  1. 真值集 `tests/fixtures/production_integrity_truth_v2.json` 的**冻结校验**
     （sha256 锚点 + 策略/开关快照 == 代码默认值 + M1 真值集未被改写）；
  2. PI-1…PI-6 的四态（PASS/FAIL/UNKNOWN/NOT_ASSESSABLE）与**阈值边界**（逐案行为断言）；
  3. 授权书点名的异常类：正常完整旁白 / 短旁白 / 尾部静音 / 中央静音 / 字幕 orphan /
     AV 轨道异常 / segment drift / 缺失数据；
  4. **真实 v9** 固定 FAIL 反例（只读判定；不重渲染、不修改 v9 产物、成片 sha 与目录清单不变）；
  5. `UNKNOWN 永不等于 PASS` 的**行为**断言（summarize 穷举 + 每个 PI 的 fail-closed 处置）；
  6. 缺失 `segment_details` 的历史产物 **PI-6 恒为 UNKNOWN**（全库真实产物只读抽样，
     且用"门禁实际会读到的输入"计算，绝不 PASS/FAIL）；
  7. **gate bypass 可审计**：默认路径全开、生产配置没有静默关闭、显式关闭必须留痕
     （gate report `disabled` + 产物 `effective_flags` / `pre_render.disabled` / `post_render.disabled`）；
  8. **端到端门禁语义**（编辑 agent 真实渲染路径，不是只调函数）：正常片照常交付、
     违约片不落交付物、旁路放行必须留痕、**关掉渲染前硬门也拦得住短旁白**（纵深防线）。

边界与只读声明：合成媒体全部落在系统临时目录；真实 v9 与全库产物**只读**；不写 DB、不写项目目录、
不做任何修复/剪辑/重渲染；不修改 DQ。

用法: python tests/integrity_truth_test.py
"""
import hashlib
import itertools
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
sys.stdout.reconfigure(encoding="utf-8")

from fixtures.build_integrity_fixtures import (make_film,  # noqa: E402
                                               make_track_mismatch)
from video_studio.agents.editing.agent import EditingAgent  # noqa: E402
from video_studio.core import integrity as I  # noqa: E402
from video_studio.core.narration import NarrationIncompleteError  # noqa: E402

TRUTH_PATH = ROOT / "tests" / "fixtures" / "production_integrity_truth_v2.json"
TRUTH_V1_PATH = ROOT / "tests" / "fixtures" / "production_integrity_truth_v1.json"
FREEZE_REC = ROOT / "docs" / "regression_2x" / "logs" / "phase6a_m3_truth_freeze.json"

CFG = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8-sig"))
FFMPEG = CFG["tools"]["ffmpeg"]["path"]
FFPROBE = CFG["tools"]["ffmpeg"]["ffprobe"]
DB = ROOT / "projects" / "video_studio.db"

PASS, FAIL, SKIP = [], [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print("{}  {} {}".format("PASS" if ok else "FAIL", name,
                             "" if ok else "| " + str(detail)[:360]))


def skip(name, why):
    SKIP.append(name)
    print("SKIP  {} | {}".format(name, why))


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def dig(d, path):
    cur = d
    for part in path.split("."):
        cur = cur.get(part) if isinstance(cur, dict) else None
    return cur


def find_metric_field(result, field):
    """在门禁报告的 metrics 里定位字段（容忍 `_s` / `_db` 后缀写法）。"""
    for m in (result.get("metrics") or {}).values():
        if not isinstance(m, dict):
            continue
        for cand in (field, field + "_s", field + "_db"):
            if cand in m:
                return m[cand]
    return None


def _run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError("ffmpeg 失败 rc={}: {}".format(r.returncode, (r.stderr or "")[-300:]))
    return r


TMP = Path(tempfile.mkdtemp(prefix="vs_m3_truth_"))


# ============================================================================
# T0 —— 真值集冻结校验
# ============================================================================
truth_bytes = TRUTH_PATH.read_bytes()
TRUTH = json.loads(truth_bytes.decode("utf-8"))
#: 规范化 sha256：排除 `frozen_sha256` 字段本身（避免自指）。任何真值改动都会改变它。
_canon = json.dumps({k: v for k, v in TRUTH.items() if k != "frozen_sha256"},
                    sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
truth_sha = hashlib.sha256(_canon).hexdigest()
FROZEN_SHA = TRUTH.get("frozen_sha256")
check("T0a 真值集 schema/阶段正确（production-integrity-truth-v2 / 6-A/M3）",
      TRUTH.get("schema") == "production-integrity-truth-v2" and TRUTH.get("stage") == "6-A/M3",
      TRUTH.get("schema"))
check("T0b 真值集规范化 sha256 与冻结锚点一致（改真值必须显式重冻结）",
      FROZEN_SHA == truth_sha, {"live": truth_sha, "frozen_in_file": FROZEN_SHA})
v1_sha = sha(TRUTH_V1_PATH)
if FREEZE_REC.is_file():
    fr = json.loads(FREEZE_REC.read_text(encoding="utf-8"))
    check("T0c M1 真值集（v1）未被改写（与冻结记录一致）", fr.get("v1_sha256") == v1_sha,
          {"v1_live": v1_sha, "recorded": fr.get("v1_sha256")})
    check("T0c M3 真值集 sha 与冻结记录一致",
          fr.get("v2_canonical_sha256") == truth_sha,
          {"live": truth_sha, "recorded": fr.get("v2_canonical_sha256")})
else:
    skip("T0c 冻结记录核对", "缺少 {}（先运行 phase6a_m3_build_truth.py）".format(FREEZE_REC.name))
check("T0d 冻结策略快照 == 代码 DEFAULT_POLICY（阈值漂移即失败）",
      TRUTH["frozen_policy"] == I.DEFAULT_POLICY,
      {k: (TRUTH["frozen_policy"].get(k), I.DEFAULT_POLICY.get(k))
       for k in I.DEFAULT_POLICY if TRUTH["frozen_policy"].get(k) != I.DEFAULT_POLICY.get(k)})
check("T0e 冻结门禁开关快照 == 代码 DEFAULT_GATE_POLICY",
      all(TRUTH["frozen_gate_flags"][k] == I.DEFAULT_GATE_POLICY[k]
          for k in TRUTH["frozen_gate_flags"]), TRUTH["frozen_gate_flags"])
check("T0f 状态可达性声明与源码一致（PI-1/PI-2/PI-5 无 UNKNOWN 路径，各 PI 均有 PASS/FAIL）",
      TRUTH["state_reachability"]["PI-1"]["UNKNOWN"] is False
      and TRUTH["state_reachability"]["PI-2"]["UNKNOWN"] is False
      and TRUTH["state_reachability"]["PI-5"]["UNKNOWN"] is False
      and all(TRUTH["state_reachability"][k]["PASS"] and TRUTH["state_reachability"][k]["FAIL"]
              for k in ("PI-1", "PI-2", "PI-3", "PI-4", "PI-5", "PI-6")))

# ============================================================================
# 合成夹具与执行器
# ============================================================================
cases = {c["id"]: c for c in TRUTH["cases"]}
print("\n真值集用例数:", len(cases))
FILMS = {}
GATE_KEYS = {"states", "blocked", "disabled", "reasons_contain", "note", "state",
             "task_status", "has_render_output", "error_code", "stage", "reason_contains",
             "artifact_count", "new_mp4", "forbidden_artifacts", "effective_flags",
             "pre_render_blocked", "post_render_blocked", "pre_render_disabled",
             "post_render_disabled", "all_state", "min_sample", "forbidden_states",
             "gate_blocked", "gate_case_ref", "film_sha256", "film_bytes", "film_unchanged",
             "pre_states", "post_states", "coverage_ratio", "shortfall_s", "tail_silence_s",
             "orphan_cues", "overall", "unknown_is_not_pass", "failed_metrics",
             "effective_flags.gate_enabled", "effective_flags.post_render_enabled"}


def gen_cues(spec):
    if not spec:
        return []
    kind = spec.get("kind")
    if kind == "explicit":
        return [{"start": float(a), "end": float(b)} for a, b in spec["cues"]]
    if kind == "even":
        return [{"start": round(i * spec["step"], 3),
                 "end": round(i * spec["step"] + spec["dur"], 3)}
                for i in range(spec["count"])]
    if kind == "even_plus_orphans":
        n = spec["count"] - spec["orphans"]
        base = [{"start": round(i * spec["step"], 3),
                 "end": round(i * spec["step"] + spec["dur"], 3)} for i in range(n)]
        orph = [{"start": round(spec["orphan_start"] + i * 0.2, 3),
                 "end": round(spec["orphan_start"] + i * 0.2 + spec["orphan_dur"], 3)}
                for i in range(spec["orphans"])]
        return base + orph
    raise ValueError("未知 cue spec: {}".format(kind))


def get_film(spec) -> Path:
    key = json.dumps(spec, sort_keys=True)
    if key in FILMS:
        return FILMS[key]
    kind = spec["kind"]
    if kind == "clean":
        f = make_film(TMP / "clean_{}.mp4".format(int(spec["duration_s"])), FFMPEG,
                      duration_s=spec["duration_s"], speech_s=spec.get("speech_s",
                                                                     spec["duration_s"]))
    elif kind == "tail":
        f = make_film(TMP / "tail_{}_{}.mp4".format(int(spec["duration_s"]),
                                                    int(spec["speech_s"])),
                      FFMPEG, duration_s=spec["duration_s"], speech_s=spec["speech_s"])
    elif kind == "gap":
        out = TMP / "gap_{}_{}.mp4".format(int(spec["gap_start_s"]), int(spec["gap_len_s"]))
        out.parent.mkdir(parents=True, exist_ok=True)
        g0, g1 = spec["gap_start_s"], spec["gap_start_s"] + spec["gap_len_s"]
        _run([FFMPEG, "-y", "-v", "error", "-f", "lavfi", "-t", "{:.3f}".format(spec["duration_s"]),
              "-i", "testsrc=size=320x180:rate=25", "-f", "lavfi", "-t",
              "{:.3f}".format(spec["duration_s"]), "-i", "sine=frequency=440:sample_rate=24000",
              "-af", "volume=enable='between(t,{:.3f},{:.3f})':volume=0".format(g0, g1),
              "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-pix_fmt", "yuv420p",
              "-preset", "ultrafast", "-c:a", "aac", "-shortest",
              "-t", "{:.3f}".format(spec["duration_s"]), str(out)])
        f = out
    elif kind == "track_mismatch":
        f = make_track_mismatch(TMP / "track_mismatch.mp4", FFMPEG, video_s=spec["video_s"],
                                audio_s=spec["audio_s"],
                                speech_s=spec.get("speech_s", spec["audio_s"]))
    else:
        raise ValueError("未知 film spec: {}".format(kind))
    FILMS[key] = f
    return f


def policy_for(case):
    p = I.gate_policy(None)
    p.update(case.get("policy_override") or {})
    return p


def run_metric(case):
    args = dict(case["args"])
    if "cues" in args and not isinstance(args["cues"], list):
        args["cues"] = gen_cues(args["cues"])
    if args.get("film") == "__MISSING__":
        args["film"] = str(TMP / "definitely_missing.mp4")
    if args.get("film") == "__CLEAN20__":
        args["film"] = str(get_film({"kind": "clean", "duration_s": 20.0, "speech_s": 20.0}))
    if args.get("ffmpeg") == "__CFG__":
        args["ffmpeg"] = FFMPEG
    return getattr(I, case["metric"])(**args)


def run_gate(case):
    spec, pol = case["spec"], policy_for(case)
    if case["kind"] == "pre_gate":
        voice = {"complete": True,
                 "segment_details": [{"duration_s": d} for d in spec["voice_segment_durations"]]}
        segs = [s if isinstance(s, dict) else {"duration_s": s} for s in spec["script_segments"]]
        return I.pre_render_gate(segs, voice, spec["timeline_s"], pol,
                                 narration_duration_s=spec["narration_s"])
    return I.post_render_gate(get_film(spec["film"]), spec["timeline_s"], gen_cues(spec["cues"]),
                              spec["narration_end_s"], spec["narration_expected"],
                              FFMPEG, FFPROBE, pol)


def metric_states(case):
    return {"narration_coverage": "PI-1", "duration_contract_dual": "PI-2",
            "audio_silence_profile": "PI-3", "av_track_consistency": "PI-4",
            "subtitle_orphans": "PI-5", "segment_boundary_drift": "PI-6"}[case["metric"]]


OBSERVED = {}

# ============================================================================
# T1 —— 逐案行为断言
# ============================================================================
for cid, case in cases.items():
    kind = case["kind"]
    exp = case["expect"]
    if kind == "metric":
        res = run_metric(case)
        OBSERVED[cid] = {metric_states(case): res.get("state")}
        if "state" in exp:
            check("{} 状态 = {}".format(cid, exp["state"]), res.get("state") == exp["state"], res)
        for k, v in exp.items():
            if k in GATE_KEYS:
                continue
            if k.endswith("_gt"):
                fld, got = k[:-3], dig(res, k[:-3])
                check("{} {} > {}".format(cid, fld, v), got is not None and got > v,
                      {"got": got})
            elif k.endswith("_lt"):
                fld, got = k[:-3], dig(res, k[:-3])
                check("{} {} < {}".format(cid, fld, v), got is not None and got < v,
                      {"got": got})
            elif k.endswith("_eq"):
                fld, got = k[:-3], dig(res, k[:-3])
                check("{} {} == {}".format(cid, fld, v), got == v, {"got": got})
            else:
                got = dig(res, k)
                check("{} {} == {}".format(cid, k, v), got == v, {"got": got, "want": v})
    elif kind in ("pre_gate", "post_gate"):
        res = run_gate(case)
        OBSERVED[cid] = {k: v.get("state") for k, v in (res.get("metrics") or {}).items()}
        for pi, st in (exp.get("states") or {}).items():
            check("{} {} 状态 = {}".format(cid, pi, st),
                  (res.get("metrics") or {}).get(pi, {}).get("state") == st,
                  (res.get("metrics") or {}).get(pi))
        check("{} 门禁 blocked = {}".format(cid, exp["blocked"]),
              bool(res["blocked"]) == bool(exp["blocked"]),
              {"blocked": res["blocked"], "reasons": res["reasons"]})
        if "disabled" in exp:
            check("{} 旁路留痕 disabled = {}".format(cid, exp["disabled"]),
                  bool(res.get("disabled")) == bool(exp["disabled"]), res.get("disabled"))
        for frag in exp.get("reasons_contain") or []:
            check("{} 原因含『{}』".format(cid, frag),
                  any(frag in r for r in res["reasons"]), res["reasons"])
        for k, v in exp.items():
            if k.endswith("_gt"):
                got = find_metric_field(res, k[:-3])
                check("{} {} > {}".format(cid, k[:-3], v), got is not None and got > v, {"got": got})
            elif k.endswith("_eq"):
                got = find_metric_field(res, k[:-3])
                check("{} {} == {}".format(cid, k[:-3], v), got == v, {"got": got})
            elif k.endswith("_lt"):
                got = find_metric_field(res, k[:-3])
                check("{} {} < {}".format(cid, k[:-3], v), got is not None and got < v,
                      {"got": got})
    elif kind == "summarize":
        res = I.summarize({k: {"state": v} for k, v in case["args"].items()})
        for k, v in exp.items():
            check("{} summarize.{} == {}".format(cid, k, v), res.get(k) == v, res)

# ============================================================================
# T2 —— 覆盖矩阵核对（PI × 状态 → 用例，逐格用实测状态验证）
# ============================================================================
print("\n== T2 覆盖矩阵 ==")
for pi, states in TRUTH["coverage_matrix_expected"].items():
    for state, ids in states.items():
        if not TRUTH["state_reachability"][pi][state]:
            check("T2 {}-{} 声明不可达且矩阵为空".format(pi, state), ids == [], ids)
            continue
        check("T2 {}-{} 至少 1 个用例".format(pi, state), len(ids) >= 1, ids)
        for cid in ids:
            if cid not in OBSERVED:
                continue
            check("T2 {}-{} ← {} 实测一致".format(pi, state, cid),
                  OBSERVED[cid].get(pi) == state, {"case": cid, "got": OBSERVED[cid].get(pi)})
check("T2 PI-3 精确等式边界有诚实声明（媒体层不可确定性分离）",
      "无法在媒体层确定性分离" in TRUTH["boundary_notes"]["PI-3-exact-equality"])
check("T2 PI-6 漂移口径有说明（段边界累计）",
      "段边界累计" in TRUTH["boundary_notes"]["PI-6-drift-is-boundary-based"])

# ============================================================================
# T3 —— UNKNOWN 永不等于 PASS
# ============================================================================
print("\n== T3 UNKNOWN ≠ PASS ==")
for cid in TRUTH["unknown_never_pass_invariants"]["summarize_cases"]:
    res = I.summarize({k: {"state": v} for k, v in cases[cid]["args"].items()})
    check("T3 {} overall 绝不为 PASS".format(cid), res["overall"] != "PASS", res["overall"])
_bad = []
for r in range(1, 5):
    for combo in itertools.combinations(["PASS", "FAIL", "UNKNOWN", "NOT_ASSESSABLE"], r):
        if "UNKNOWN" not in combo and "NOT_ASSESSABLE" not in combo:
            continue
        metrics = {"PI-{}".format(i + 1): {"state": st} for i, st in enumerate(combo)}
        res = I.summarize(metrics)
        if res["overall"] == "PASS":
            _bad.append(combo)
check("T3 穷举：含 UNKNOWN/NOT_ASSESSABLE 的任意状态组合 overall 绝不为 PASS",
      not _bad, _bad)
check("T3 summarize 显式声明 unknown_is_not_pass",
      I.summarize({"PI-1": {"state": "UNKNOWN"}})["unknown_is_not_pass"] is True)
print("\n== T3b 每个 PI 的不可证处置 ==")
_p = I.pre_render_gate([{"duration_s": 3.0}, {"duration_s": 3.0}], {"complete": True}, 8.0,
                       I.gate_policy(None), narration_duration_s=8.0)
check("T3b PI-6 不可证 ⇒ UNKNOWN 且默认不阻断（记录）",
      _p["metrics"]["PI-6"]["state"] == "UNKNOWN" and _p["blocked"] is False, _p["reasons"])
_pm = I.post_render_gate(get_film({"kind": "clean", "duration_s": 20.0, "speech_s": 20.0}), 20.0,
                         gen_cues({"kind": "even", "count": 4, "dur": 5.0, "step": 5.0}), 20.0,
                         True, None, None, I.gate_policy(None))
check("T3b PI-3 不可证（无 ffmpeg）⇒ fail-closed 阻断",
      _pm["metrics"]["PI-3"]["state"] == "UNKNOWN" and _pm["blocked"] is True, _pm["reasons"])
_pi4 = I.av_track_consistency({"has_video": True, "has_audio": True, "video_s": None,
                               "audio_s": 10.0, "video_start": 0.0, "audio_start": 0.0},
                              10.0, I.gate_policy(None))
check("T3b PI-4 不可证 ⇒ UNKNOWN", _pi4["state"] == "UNKNOWN")

# ============================================================================
# T4 —— 真实 v9 固定 FAIL 反例（只读）
# ============================================================================
print("\n== T4 真实 v9 固定 FAIL 反例 ==")
PID, FILM_TASK = "p_96efdc03e1aa", "t_d0a54bdf1810"
_film = ROOT / "projects" / PID / "output" / "{}_draft.mp4".format(FILM_TASK)
_v9 = cases["M3-REAL-V9-FIXED-FAIL-COUNTEREXAMPLE"]["expect"]
if not _film.is_file():
    skip("T4 v9 真实反例", "成片不存在")
else:
    db_sha_before, film_sha_before = sha(DB), sha(_film)
    manifest_before = {p.name: p.stat().st_size for p in sorted(_film.parent.glob("*"))}
    con = sqlite3.connect("file:{}?mode=ro".format(DB.as_posix()), uri=True)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA query_only=ON")
    recs = [dict(r) for r in con.execute(
        "select artifact_id, task_id, type, path, created_at from artifacts where project_id=? "
        "order by created_at", (PID,))]
    con.close()
    by_type = {}
    for r in recs:
        by_type.setdefault(r["type"], []).append(r)

    def payload(rec):
        if not rec:
            return {}
        p = Path(rec["path"])
        try:
            return json.loads((p if p.is_absolute() else ROOT / p).read_text(encoding="utf-8"))
        except Exception:                                        # noqa: BLE001
            return {}

    voice = payload((by_type.get("voice_output") or [None])[-1])
    script = payload((by_type.get("script_output") or [None])[-1])
    sub = payload((by_type.get("subtitle") or [None])[-1])
    render = payload(next((r for r in (by_type.get("render_output") or [])
                           if r["task_id"] == FILM_TASK), None))
    if not (voice and script and sub and render):
        skip("T4 v9 真实反例", "缺少 v9 的 script/voice/subtitle/render 产物之一")
    else:
        timeline_total = float((render.get("duration_contract") or {}).get("timeline_duration_s")
                               or 1532.0)
        pr = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                             "-of", "default=nw=1:nk=1",
                             str(ROOT / "projects" / PID / (voice.get("audio") or ""))],
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
        try:
            narr_s = float((pr.stdout or "").strip())
        except ValueError:
            narr_s = voice.get("narration_duration_s")
        pre = I.pre_render_gate(script.get("segments") or [], voice, timeline_total,
                                I.gate_policy(CFG), narration_duration_s=narr_s)
        post = I.post_render_gate(_film, timeline_total, sub.get("srt") or [], narr_s, True,
                                 FFMPEG, FFPROBE, I.gate_policy(CFG))
        pre_states = {k: v["state"] for k, v in pre["metrics"].items()}
        post_states = {k: v["state"] for k, v in post["metrics"].items()}
        OBSERVED["M3-REAL-V9-FIXED-FAIL-COUNTEREXAMPLE"] = dict(pre_states, **post_states)
        check("T4 v9 渲染前必须阻断（PI-1/PI-2/PI-6 FAIL）",
              pre["blocked"] is True and pre_states == _v9["pre_states"], pre_states)
        check("T4 v9 渲染后必须阻断（PI-3/PI-5 FAIL、PI-4 PASS）",
              post["blocked"] is True and post_states == _v9["post_states"], post_states)
        check("T4 v9 关键实测值与冻结真值一致（覆盖率/短差/尾静音/orphan）",
              abs(pre["metrics"]["PI-1"]["coverage_ratio"] - _v9["coverage_ratio"]) < 0.001
              and abs(pre["metrics"]["PI-2"]["contract"]["shortfall_s"] - _v9["shortfall_s"]) < 0.02
              and abs(post["metrics"]["PI-3"]["tail_silence_s"] - _v9["tail_silence_s"]) < 0.05
              and post["metrics"]["PI-5"]["orphan_cues"] == _v9["orphan_cues"],
              {"PI-1": pre["metrics"]["PI-1"]["coverage_ratio"],
               "PI-3_tail": post["metrics"]["PI-3"]["tail_silence_s"],
               "PI-5_orphan": post["metrics"]["PI-5"]["orphan_cues"]})
        check("T4 v9 成片未被修改（sha256/字节数/目录清单不变）",
              sha(_film) == film_sha_before == _v9["film_sha256"]
              and _film.stat().st_size == _v9["film_bytes"]
              and {p.name: p.stat().st_size for p in sorted(_film.parent.glob("*"))}
              == manifest_before, {"sha": sha(_film)[:16]})
        check("T4 真实 DB 字节未变（只读判定）", sha(DB) == db_sha_before)

# ============================================================================
# T5 —— 历史产物缺 segment_details ⇒ PI-6 恒为 UNKNOWN（用门禁实际读到的输入）
# ============================================================================
print("\n== T5 历史产物 PI-6 恒 UNKNOWN ==")
legacy = cases["M3-LEGACY-PI6-ALWAYS-UNKNOWN"]["expect"]
con = sqlite3.connect("file:{}?mode=ro".format(DB.as_posix()), uri=True)
con.row_factory = sqlite3.Row
con.execute("PRAGMA query_only=ON")
voice_rows = [dict(r) for r in con.execute(
    "select artifact_id, project_id, path from artifacts where type='voice_output' "
    "order by created_at")]
script_by_pid = {}
for r in con.execute("select project_id, path, created_at from artifacts "
                     "where type='script_output' order by created_at"):
    script_by_pid[r["project_id"]] = r["path"]
con.close()
sampled, states, script_missing = 0, {}, 0
for r in voice_rows:
    p = Path(r["path"])
    try:
        d = json.loads((p if p.is_absolute() else ROOT / p).read_text(encoding="utf-8"))
    except Exception:                                            # noqa: BLE001
        continue
    if d.get("segment_details"):
        continue                                   # 只抽样"缺逐段时长"的历史产物
    sp = script_by_pid.get(r["project_id"])
    segs = []
    if sp:
        spath = Path(sp)
        try:
            segs = json.loads((spath if spath.is_absolute() else ROOT / spath)
                              .read_text(encoding="utf-8")).get("segments") or []
        except Exception:                                        # noqa: BLE001
            segs = []
    if not segs:
        script_missing += 1
        segs = [{"duration_s": 60.0}] * 3          # 缺脚本时用非空合成段落（仍不改变结论）
    voice_durs = [x.get("duration_s") for x in (d.get("segment_details") or [])]   # = []
    st = I.segment_boundary_drift(segs, voice_durs, I.gate_policy(None))["state"]
    states[st] = states.get(st, 0) + 1
    sampled += 1
check("T5 缺 segment_details 的历史产物样本 ≥ {}（实测 {}，其中缺脚本产物 {}）".format(
    legacy["min_sample"], sampled, script_missing), sampled >= legacy["min_sample"],
    {"sampled": sampled, "total_voice_output": len(voice_rows)})
check("T5 这些产物 PI-6 恒为 UNKNOWN（绝不 PASS/FAIL）",
      set(states) == {"UNKNOWN"} and not (set(states) & set(legacy["forbidden_states"])), states)
check("T5 缺逐段时长不削弱旁白完整性把关（PI-1 用实测时长独立判定）",
      I.narration_coverage(8.0, 10.0, I.DEFAULT_POLICY)["state"] == "FAIL")
check("T5 门禁对同一输入不据此阻断（等价案见 {}）".format(legacy["gate_case_ref"]),
      bool(cases[legacy["gate_case_ref"]]["expect"]["blocked"]) is False)

# ============================================================================
# T6 —— gate bypass 审计与默认开启
# ============================================================================
print("\n== T6 gate bypass 审计 ==")
check("T6a 默认（无配置）⇒ 门禁全开",
      I.gate_policy(None)["gate_enabled"] is True
      and I.gate_policy(None)["post_render_enabled"] is True)
for cfg_name in ("config.json", "config.mock.json"):
    cfg = json.loads((ROOT / "config" / cfg_name).read_text(encoding="utf-8-sig"))
    gate_cfg = ((cfg.get("gates") or {}).get("integrity") or {})
    check("T6b {} 无静默关闭（gates.integrity.enabled 缺失或非 false）".format(cfg_name),
          gate_cfg.get("enabled") is not False, gate_cfg)
    check("T6b {} 下门禁仍为开启".format(cfg_name),
          I.gate_policy(cfg)["gate_enabled"] is True
          and I.gate_policy(cfg)["post_render_enabled"] is True)
_pol_off = I.gate_policy({"gates": {"integrity": {"enabled": False}}})
check("T6c 显式关闭 ⇒ gate_enabled=False（开关存在，M3 不移除）",
      _pol_off["gate_enabled"] is False and _pol_off["post_render_enabled"] is True)
check("T6d 关闭不静默改变其它策略值",
      all(_pol_off[k] == I.DEFAULT_GATE_POLICY[k] for k in I.DEFAULT_POLICY))
_g = I.pre_render_gate([{"duration_s": 3.0}], {"complete": True}, 5.0, _pol_off,
                       narration_duration_s=None)
check("T6e 渲染前关闭仍留痕：disabled=True + 明确原因",
      _g["disabled"] is True and _g["blocked"] is False
      and any("gate disabled by policy" in r for r in _g["reasons"]), _g["reasons"])
_g2 = I.post_render_gate(get_film({"kind": "tail", "duration_s": 20.0, "speech_s": 12.0}), 20.0,
                         gen_cues({"kind": "even", "count": 3, "dur": 4.0, "step": 4.0}), 12.0,
                         True, FFMPEG, FFPROBE,
                         I.gate_policy({"gates": {"integrity": {"post_render_enabled": False}}}))
check("T6f 渲染后关闭仍留痕：disabled=True、metrics 为空、不阻断",
      _g2["disabled"] is True and _g2["blocked"] is False and (_g2["metrics"] or {}) == {},
      {"disabled": _g2["disabled"], "reasons": _g2["reasons"]})

# ============================================================================
# T7 —— 端到端门禁语义（编辑 agent 真实渲染）
# ============================================================================
print("\n== T7 端到端门禁语义 ==")
CFG_TEST = {"tools": {"tts": {"provider": "edge-tts", "voice_type": "zh-CN-XiaoxiaoNeural"},
                      "ffmpeg": {"path": str(ROOT / "bin" / "ffmpeg.exe"),
                                 "ffprobe": str(ROOT / "bin" / "ffprobe.exe")}},
            "retry": {"default_max_retries": 2, "backoff_base_s": 0.01}}
SCRIPT_M3 = {"segments": [
    {"chapter": "A", "narration": "第一段旁白内容需要完整说明本段的要点", "duration_s": 3},
    {"chapter": "B", "narration": "第二段旁白内容需要完整说明本段的要点", "duration_s": 3},
    {"chapter": "C", "narration": "第三段旁白内容需要完整说明本段的要点", "duration_s": 3},
]}
MODE_SEGD = {"normal": [3.667, 3.667, 3.666], "short_narration": [3.0, 3.0, 3.0],
             "mid_silence": [3.667, 3.667, 3.666], "pi6_drift": [0.2, 0.3, 10.5]}


class _FakeDB:
    def __init__(self, tasks, arts):
        self.tasks, self.arts = tasks, arts

    def get_task(self, tid):
        return self.tasks.get(tid)

    def get_artifact(self, aid):
        return self.arts.get(aid)

    def update_task(self, tid, **kw):
        self.tasks.setdefault(tid, {}).update(kw)

    def set_task_status(self, tid, status, note=""):
        self.tasks.setdefault(tid, {}).update({"status": status, "note": note})


class _FakeEngine:
    def __init__(self, work, gates=None):
        self.work = work
        self.db = _FakeDB({"t_script": {"task_id": "t_script", "artifacts": ["a_script"],
                                        "dependencies": []},
                           "t_voice": {"task_id": "t_voice", "artifacts": ["a_voice"],
                                       "dependencies": ["t_script"]},
                           "t_render": {"task_id": "t_render", "artifacts": [],
                                        "dependencies": ["t_voice"]}}, {})
        self.config = dict(CFG_TEST)
        if gates:
            self.config["gates"] = {"integrity": gates}
        self.written, self.events = [], []

    def project_dir(self, pid):
        return self.work

    def write_artifact(self, project_id, task_id, type_, content, summary="", version=1,
                       license_=None):
        aid = "a_test_{}".format(len(self.written) + 1)
        p = self.work / "artifacts" / "{}.json".format(aid)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(content, ensure_ascii=False, indent=1), encoding="utf-8")
        self.db.arts[aid] = {"artifact_id": aid, "type": type_, "path": str(p), "summary": summary}
        self.written.append({"id": aid, "type": type_, "content": content, "path": str(p)})
        return aid

    def attach_artifact(self, task_id, artifact_id):
        self.db.tasks.setdefault(task_id, {}).setdefault("artifacts", []).append(artifact_id)

    def emit(self, project_id, type_, actor, task_id=None, payload=None, human_visible=False):
        self.events.append({"type": type_, "task": task_id, "payload": payload})


def _mk_mp3(path, seconds, gap=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [FFMPEG, "-y", "-v", "error", "-f", "lavfi", "-t", "{:.3f}".format(seconds), "-i",
           "sine=frequency=440:sample_rate=24000"]
    if gap:
        cmd += ["-af", "volume=enable='between(t,{:.2f},{:.2f})':volume=0".format(*gap)]
    cmd += ["-c:a", "libmp3lame", str(path)]
    _run(cmd)


def e2e_case(mode, gates=None, label=""):
    work = TMP / "e2e_{}_{}".format(mode, label or "default")
    for sub in ("media/voice", "artifacts", "output"):
        (work / sub).mkdir(parents=True, exist_ok=True)
    (work / "artifacts" / "script.json").write_text(json.dumps(SCRIPT_M3, ensure_ascii=False),
                                                   encoding="utf-8")
    narr_len = {"normal": 11.0, "short_narration": 9.0, "mid_silence": 11.0,
                "pi6_drift": 11.0}[mode]
    gap = (4.25, 6.75) if mode == "mid_silence" else None
    _mk_mp3(work / "media" / "voice" / "narration.mp3", narr_len, gap)
    segs = [{"index": i, "audio": "media/voice/seg_{:02d}.mp3".format(i), "status": "SUCCESS",
             "reused": False, "attempts": 1, "bytes": 1000,
             "duration_s": MODE_SEGD[mode][i], "text_sha256": "z"} for i in range(3)]
    voice = {"audio": "media/voice/narration.mp3", "complete": True, "status": "COMPLETE",
             "expected_segments": 3, "successful_segments": 3, "failed_segments": [],
             "narration_duration_s": narr_len, "segments": segs, "segment_details": segs}
    vp = work / "artifacts" / "voice.json"
    vp.write_text(json.dumps(voice, ensure_ascii=False), encoding="utf-8")
    eng = _FakeEngine(work, gates)
    eng.db.arts["a_script"] = {"artifact_id": "a_script", "type": "script_output",
                              "path": str(work / "artifacts" / "script.json")}
    eng.db.arts["a_voice"] = {"artifact_id": "a_voice", "type": "voice_output", "path": str(vp)}
    raised = None
    try:
        EditingAgent().run(eng, {"task_id": "t_render", "project_id": "p_test",
                                 "task_type": "render", "dependencies": ["t_voice"],
                                 "inputs": {}})
    except Exception as exc:                                     # noqa: BLE001
        raised = exc
    return {"raised": raised, "types": [w["type"] for w in eng.written],
            "render": next((w["content"] for w in eng.written if w["type"] == "render_output"),
                           None),
            "mp4": sorted(p.name for p in (work / "output").glob("*.mp4")), "events": eng.events}


def e2e_check(cid):
    case = cases[cid]
    spec, exp = case["spec"], case["expect"]
    r = e2e_case(spec["mode"], gates=case.get("policy_override"),
                 label=cid.split("-")[-1].lower())
    exc = r["raised"]
    status = "SUCCEEDED" if exc is None else "BLOCKED"
    check("{} 任务终态 = {}".format(cid, exp["task_status"]), status == exp["task_status"],
          {"raised": str(exc)[:160], "types": r["types"]})
    if "error_code" in exp:
        check("{} 错误码 = {}".format(cid, exp["error_code"]),
              exp["error_code"] in str(exc), str(exc)[:160])
    if "reason_contains" in exp:
        check("{} 阻断原因含『{}』".format(cid, exp["reason_contains"]),
              exp["reason_contains"] in str(exc), str(exc)[:200])
    if exp.get("stage"):
        detail = getattr(exc, "detail", None) or {}
        got_stage = detail.get("stage") or ("pre_render" if "render 前闸门" in str(exc) else None)
        check("{} 阻断阶段 = {}".format(cid, exp["stage"]), got_stage == exp["stage"],
              {"stage": got_stage})
    if exp.get("has_render_output"):
        check("{} 登记 render_output".format(cid), "render_output" in r["types"], r["types"])
    if exp.get("artifact_count") == 0:
        check("{} 零 artifact 落库".format(cid), r["types"] == [], r["types"])
    if exp.get("new_mp4") is False:
        check("{} 未新增 mp4".format(cid), r["mp4"] == [], r["mp4"])
    for t in exp.get("forbidden_artifacts") or []:
        check("{} 不登记 {} 交付物".format(cid, t), t not in r["types"], r["types"])
    if exp.get("effective_flags") and r["render"]:
        pi = r["render"].get("production_integrity") or {}
        check("{} 产物 effective_flags 全开".format(cid),
              pi.get("effective_flags") == exp["effective_flags"], pi.get("effective_flags"))
    if "effective_flags.gate_enabled" in exp and r["render"]:
        pi = r["render"].get("production_integrity") or {}
        check("{} 产物留痕 effective_flags.gate_enabled=false".format(cid),
              (pi.get("effective_flags") or {}).get("gate_enabled") is False,
              pi.get("effective_flags"))
    if "effective_flags.post_render_enabled" in exp and r["render"]:
        pi = r["render"].get("production_integrity") or {}
        check("{} 产物留痕 effective_flags.post_render_enabled=false".format(cid),
              (pi.get("effective_flags") or {}).get("post_render_enabled") is False,
              pi.get("effective_flags"))
    if exp.get("pre_render_disabled") and r["render"]:
        pi = r["render"].get("production_integrity") or {}
        check("{} 产物留痕 pre_render.disabled=true".format(cid),
              (pi.get("pre_render") or {}).get("disabled") is True, pi.get("pre_render"))
    if exp.get("post_render_disabled") and r["render"]:
        pi = r["render"].get("production_integrity") or {}
        check("{} 产物留痕 post_render.disabled=true".format(cid),
              (pi.get("post_render") or {}).get("disabled") is True, pi.get("post_render"))
    if exp.get("pre_render_blocked") is False and r["render"]:
        pi = r["render"].get("production_integrity") or {}
        check("{} 产物记录 pre/post 均未阻断".format(cid),
              (pi.get("pre_render") or {}).get("blocked") is False
              and (pi.get("post_render") or {}).get("blocked") is False, pi)
    return r


for _cid in ("M3-E2E-NORMAL-COMPLETE", "M3-E2E-SHORT-NARRATION-PRE-BLOCK",
             "M3-E2E-MID-SILENCE-POST-BLOCK", "M3-E2E-PI6-DRIFT-PRE-BLOCK",
             "M3-E2E-PRE-DISABLED-STILL-BLOCKED", "M3-E2E-GATE-DISABLED-AUDITED",
             "M3-E2E-POST-GATE-DISABLED-AUDITED"):
    e2e_check(_cid)

_r = e2e_case("normal")
check("T7 正常完整旁白 ⇒ 零异常、登记 render_output 且交付成片",
      _r["raised"] is None and "render_output" in _r["types"] and len(_r["mp4"]) == 1,
      {"raised": _r["raised"], "types": _r["types"], "mp4": _r["mp4"]})

print("\n结果: {}/{} 通过   SKIP={}".format(len(PASS), len(PASS) + len(FAIL), SKIP))
if FAIL:
    print("失败项:", FAIL)
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(0 if not FAIL else 1)
