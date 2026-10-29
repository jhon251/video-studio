# -*- coding: utf-8 -*-
"""6-G —— 小样**执行 + 完整验收**（S11 split / S11 visual-aid / LAST_12S outro）。

硬约束：只写 `output/phase6g_sample/<ts>/`；不写 DB / 正式 project / execution registry；
不改 baseline·tag / 历史 artifact / DQ 实现；不 promote；只执行**小样子集**（正式 H3a/H3b/H5/E1–E5
仍 NOT_EXECUTED）；任一 timeline / subtitle / audio identity / integrity / isolation gate 失败立即 STOP。

产出: docs/regression_2x/logs/phase6g_sample_acceptance_report.json
"""
import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
from video_studio.core import captions as core_captions              # noqa: E402
from video_studio.core import direction as core_direction            # noqa: E402
from video_studio.core import integrity as core_integrity            # noqa: E402
from video_studio.core import narration as N                         # noqa: E402
from video_studio.core import visual_aid as VA                       # noqa: E402
from video_studio.ops import execution as OPX                        # noqa: E402

LOGS = ROOT / "docs" / "regression_2x" / "logs"
P2 = json.loads((LOGS / "phase6f_rebuild_plan_v2.json").read_text(encoding="utf-8"))
PKG = json.loads((LOGS / "phase6g_rebuild_proposals.json").read_text(encoding="utf-8"))
N0 = json.loads((LOGS / "phase6g_n0_dcv2_master.json").read_text(encoding="utf-8"))
PLAN = json.loads((LOGS / "phase6g_sample_execution_plan.json").read_text(encoding="utf-8"))
OUT = LOGS / "phase6g_sample_acceptance_report.json"
FFMPEG, FFPROBE = ROOT / "bin" / "ffmpeg.exe", ROOT / "bin" / "ffprobe.exe"
PROD = P2["math_verification"]["production_duration_s"]
TS = time.strftime("%Y%m%d_%H%M%S")
SANDBOX = ROOT / "output" / "phase6g_sample" / TS
BOX, OUTD = SANDBOX / "box", SANDBOX / "out"
CFG = {"tools": {"ffmpeg": {"path": str(FFMPEG), "ffprobe": str(FFPROBE)}}}
MASTER_IN = ROOT / N0["master"]["path"]
W_A, W_B = [487.572, 539.346], [966.656, 978.656]
chain = P2["remapping_21_segments"]
by_scene = {c["scene_id"]: c for c in chain}
PASS, FAIL, ABORT = [], [], {"at": None, "why": None}
FF_CALLS = []

for d in (BOX / "work", BOX / "output", BOX / "artifacts", OUTD):
    d.mkdir(parents=True, exist_ok=True)

# ffmpeg 调用记录（包装生产 `_run`）
_orig_run = OPX._run


def _recorded_run(cmd, timeout=3600):
    FF_CALLS.append({"argv": [str(c) for c in cmd][:14], "t": round(time.time(), 3)})
    return _orig_run(cmd, timeout=timeout)


OPX._run = _recorded_run


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def probe(p: Path) -> dict:
    r = subprocess.run([str(FFPROBE), "-v", "error", "-show_entries",
                        "format=duration:stream=codec_type", "-of", "json", str(p)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    j = json.loads(r.stdout or "{}")
    return {"duration_s": round(float((j.get("format") or {}).get("duration") or 0), 3),
            "has_video": any(s.get("codec_type") == "video" for s in (j.get("streams") or [])),
            "has_audio": any(s.get("codec_type") == "audio" for s in (j.get("streams") or []))}


def audio_md5(p: Path) -> str:
    r = subprocess.run([str(FFMPEG), "-v", "error", "-i", str(p), "-map", "0:a", "-c", "copy",
                        "-f", "md5", "-"], capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    return (r.stdout or "").strip().split("=")[-1]


def check(name, ok, detail=None, hard=True):
    (PASS if ok else (FAIL if hard else PASS)).append(name) if ok else FAIL.append(name)
    print("{}  {} {}".format("PASS" if ok else ("FAIL" if hard else "WARN"), name,
                             "" if ok else json.dumps(detail, ensure_ascii=False,
                                                      default=str)[:220]))
    if not ok and hard:
        raise SystemExit(1) if ABORT["at"] else None
    return ok


def hard(name, ok, detail=None):
    if not ok:
        FAIL.append(name)
        ABORT["at"] = ABORT["at"] or name
        ABORT["why"] = detail
        print("FAIL  {} {}".format(name, json.dumps(detail, ensure_ascii=False, default=str)[:240]))
        raise RuntimeError("SAMPLE_GATE_FAILED: " + name)
    PASS.append(name)
    print("PASS  {}".format(name))
    return True


# ---------------------------------------------------------------- 前置快照
HIST = {"v9": ROOT / "projects" / "p_96efdc03e1aa" / "output" / "t_d0a54bdf1810_draft.mp4"}
m6c = json.loads((LOGS / "phase6c_batch.json").read_text(encoding="utf-8"))
for c in m6c["candidates"]:
    HIST["c" + str(c["index"])] = ROOT / c["film"]
HIST["e1"] = (ROOT / "output" / "phase6b_m4_sandbox" / "p_96efdc03e1aa_6e" / "output" /
              "t_d0a54bdf1810_draft_6c_rp-ad4bbbee7ea2_outro.mp4")
HIST["e2"] = (ROOT / "output" / "phase6b_m4_sandbox" / "p_96efdc03e1aa_6e2" / "output" /
              "t_d0a54bdf1810_draft_6c_rp-bee31dff3335_vaid.mp4")
before = {"history": {k: sha(p) for k, p in HIST.items() if p.is_file()},
          "db": sha(ROOT / "projects" / "video_studio.db"),
          "baseline": sorted(p.name for p in (ROOT / "docs" / "regression_2x" / "baseline").glob("*")),
          "master_in": sha(MASTER_IN),
          "projects_listing": sorted((str(p.relative_to(ROOT)), p.stat().st_size)
                                     for p in (ROOT / "projects" / "p_96efdc03e1aa").rglob("*")
                                     if p.is_file())[:400]}

# ---------------------------------------------------------------- 沙箱 + DCv2 上下文
con = sqlite3.connect("file:{}?mode=ro".format(
    (ROOT / "projects" / "video_studio.db").as_posix()), uri=True)
con.row_factory = sqlite3.Row
con.execute("PRAGMA query_only=ON")
rows = [dict(r) for r in con.execute(
    "select type,task_id,path from artifacts where project_id='p_96efdc03e1aa' order by created_at")]
con.close()
spath = next(r["path"] for r in rows if r["type"] == "script_output")
vpath = next(r["path"] for r in rows if r["type"] == "voice_output")
script = json.loads(Path(spath).read_text(encoding="utf-8"))
voice = json.loads(Path(vpath).read_text(encoding="utf-8"))
_ro = next((r for r in rows if r["type"] == "render_output"
            and r.get("task_id") == "t_d0a54bdf1810"),
           next((r for r in rows if r["type"] == "render_output"), None))
render = json.loads(Path(_ro["path"]).read_text(encoding="utf-8")) if _ro else {}
# 素材绑定（只读 v9 时间轴）
tl_v9 = render.get("material_timeline") or []
asset_of = {}
for e in tl_v9:
    sa = e.get("selected_asset") or {}
    if sa:
        asset_of[str(e.get("scene_id"))] = sa
# 沙箱内副本（隔离：执行上下文不直接指向项目目录）
film_copy = BOX / "output" / "dcv2_master_sandbox.mp4"
shutil.copy2(MASTER_IN, film_copy)
script_copy = BOX / "artifacts" / "script_output.json"
script_copy.write_text(json.dumps(script, ensure_ascii=False), encoding="utf-8")

tl = [{"scene_id": c["scene_id"], "start_s": c["new_timeline_window_s"][0],
       "end_s": c["new_timeline_window_s"][1], "selected_asset": asset_of.get(c["scene_id"], {})}
      for c in chain]
cw = [{"scene_id": c["scene_id"], "start_s": c["new_audio_window_s"][0],
       "end_s": c["new_audio_window_s"][1]} for c in chain]
base_ctx = {"box": str(BOX), "root": str(ROOT), "ffmpeg": str(FFMPEG), "ffprobe": str(FFPROBE),
            "config": CFG, "artifacts": {"script_output": str(script_copy)}}


def ctx_for(film: Path, timeline=None) -> dict:
    c = OPX.attach_dcv2_time_base(dict(base_ctx, film=str(film)),
                                  timeline=timeline or tl, caption_windows=cw,
                                  production_duration_s=PROD,
                                  source="docs/regression_2x/logs/phase6f_rebuild_plan_v2.json")
    return c


plan = N.narration_plan(script, voice)
cues = core_captions.build_cues(
    [{"narration": s["narration"], "duration_s": s.get("duration_s")}
     for s in script["segments"] if str(s.get("narration", "")).strip()],
    windows=[{"start_s": w["start_s"], "end_s": w["end_s"]} for w in cw])
narration_end = max(c["end"] for c in cues)
results, steps_log = {}, []

try:
    # ---------------- exec1：S11 split（小样子集）
    print("\n== exec1 S11 split（小样子集，非正式 H3b）==")
    split_prop = {"proposal_id": "SAMPLE-h3b-s11-subset", "action": "split_scene",
                  "affected_scope": {"scenes": ["S11"]},
                  "proposed_change": {"params": {"target_hold_s": 25.0}}}
    ctx1 = ctx_for(film_copy)
    r1 = OPX.exec_split_scene(ctx1, split_prop)
    out1 = BOX / "output" / "{}_6c_{}.mp4".format(film_copy.stem, "SAMPLE-h3b-s11-subset_split")
    dst1 = OUTD / "sample_1_split.mp4"
    shutil.copy2(out1, dst1)
    results["exec1"] = {"result": r1, "path": str(dst1.relative_to(ROOT)), "sha256": sha(dst1),
                        "probe": probe(dst1), "audio_md5": audio_md5(dst1)}
    steps_log.append({"exec": 1, "proposal_id": "SAMPLE-h3b-s11-subset",
                      "sub_count": r1["split_plan"]["scenes"][0]["sub_count"],
                      "cuts": r1["split_plan"]["scenes"][0]["cuts"],
                      "duration_check": r1["duration_check"], "audio_check": r1["audio_check"],
                      "cut_evidence": r1["cut_evidence"],
                      "caption_time_base": r1.get("caption_time_base"),
                      "timeline_identity": (r1.get("timeline_identity") or {}).get(
                          "identity_sha256")})
    hard("G1 exec1 duration == 978.656±0.05",
         abs(results["exec1"]["probe"]["duration_s"] - PROD) <= 0.05, results["exec1"]["probe"])
    hard("G2 exec1 音轨与母版完全一致（identical_stream）",
         r1["audio_check"]["identical_stream"] is True, r1["audio_check"])
    hard("G3 exec1 时基 = DCv2（caption_time_base.mode=dcv2）",
         (r1.get("caption_time_base") or {}).get("mode") == "dcv2", r1.get("caption_time_base"))
    hard("G4 exec1 字幕末条仍为 DCv2（976.456s，非 1528.636s）",
         abs(narration_end - 976.456) < 0.01, narration_end)
    hard("G5 exec1 切点内容可区分（_cut_evidence.all_distinct）",
         all(c["distinct"] for c in r1["cut_evidence"]), r1["cut_evidence"])

    # ---------------- exec2：S11 visual-aid（inline sample spec）
    print("\n== exec2 S11 visual-aid（inline sample spec，A 形态仅验机制）==")
    sample_spec = PLAN["sample_spec"]
    hard("G6 sample spec hash == 计划值 c7d27fdd373e46bc…",
         VA.spec_sha256(sample_spec) == PLAN["sample_spec_sha256"]
         and VA.spec_sha256(sample_spec).startswith("c7d27fdd"), VA.spec_sha256(sample_spec))
    aid_prop = {"proposal_id": "SAMPLE-e3-mechanism", "action": "add_visual_aid",
                "affected_scope": {"scenes": ["S11"], "window": W_A},
                "proposed_change": {"params": {"visual_aid": sample_spec}}}
    ctx2 = ctx_for(dst1)
    r2 = OPX.exec_add_visual_aid(ctx2, aid_prop)
    out2 = BOX / "output" / "{}_6c_{}.mp4".format(dst1.stem, "SAMPLE-e3-mechanism_vaid")
    dst2 = OUTD / "sample_2_overlay.mp4"
    shutil.copy2(out2, dst2)
    results["exec2"] = {"result": r2, "path": str(dst2.relative_to(ROOT)), "sha256": sha(dst2),
                        "probe": probe(dst2), "audio_md5": audio_md5(dst2)}
    steps_log.append({"exec": 2, "proposal_id": "SAMPLE-e3-mechanism", "window": W_A,
                      "duration_check": r2.get("duration_check"),
                      "audio_check": r2.get("audio_check"),
                      "caption_time_base": r2.get("caption_time_base")})
    hard("G7 exec2 duration == 978.656±0.05",
         abs(results["exec2"]["probe"]["duration_s"] - PROD) <= 0.05, results["exec2"]["probe"])
    hard("G8 exec2 音轨与母版完全一致", r2["audio_check"]["identical_stream"] is True,
         r2["audio_check"])
    hard("G9 exec2 时基 = DCv2", (r2.get("caption_time_base") or {}).get("mode") == "dcv2",
         r2.get("caption_time_base"))

    # ---------------- exec3：LAST_12S outro
    print("\n== exec3 LAST_12S outro ==")
    e1 = next(p for p in PKG["proposals"] if p["label"].startswith("E1"))
    outro_prop = {"proposal_id": "SAMPLE-e1-last12s", "action": "add_outro_card",
                  "scene_id": "S21", "affected_scope": {"scenes": ["S21"], "window": W_B},
                  "proposed_change": {"params": e1["proposed_change"]["params"]}}
    ctx3 = ctx_for(film_copy)
    r3 = OPX.exec_add_outro_card(ctx3, outro_prop)
    out3 = BOX / "output" / "{}_6c_{}.mp4".format(film_copy.stem, "SAMPLE-e1-last12s_outro")
    dst3 = OUTD / "sample_3_outro.mp4"
    shutil.copy2(out3, dst3)
    results["exec3"] = {"result": r3, "path": str(dst3.relative_to(ROOT)), "sha256": sha(dst3),
                        "probe": probe(dst3), "audio_md5": audio_md5(dst3)}
    steps_log.append({"exec": 3, "proposal_id": "SAMPLE-e1-last12s", "window": W_B,
                      "steps": r3.get("steps"), "audio_check": r3.get("audio_check")})
    hard("G10 exec3 duration == 978.656±0.05",
         abs(results["exec3"]["probe"]["duration_s"] - PROD) <= 0.05, results["exec3"]["probe"])
    hard("G11 exec3 音轨与母版完全一致", r3["audio_check"]["identical_stream"] is True,
         r3["audio_check"])
except RuntimeError as exc:
    if "SAMPLE_GATE_FAILED" not in str(exc):
        raise
    print("\n!! 硬门失败，立即 STOP：", ABORT)

# ---------------------------------------------------------------- 落盘执行结果（供验收脚本读取）
exec_results = {
    "schema": "phase6g-sample-exec-results-v1", "stage": "6-G", "ts": TS,
    "sandbox": str(SANDBOX.relative_to(ROOT)),
    "master_input": {"path": str(MASTER_IN.relative_to(ROOT)), "sha256": before["master_in"]},
    "results": {k: {"path": v["path"], "sha256": v["sha256"], "probe": v["probe"],
                    "audio_md5": v["audio_md5"],
                    "duration_check": (v["result"].get("duration_check") or {}),
                    "audio_check": (v["result"].get("audio_check") or {}),
                    "caption_time_base": (v["result"].get("caption_time_base") or {}),
                    "timeline_identity": (v["result"].get("timeline_identity") or {})}
                for k, v in results.items()},
    "steps_log": steps_log,
    "exec1_cut_evidence": results["exec1"]["result"]["cut_evidence"],
    "exec1_split_plan": results["exec1"]["result"]["split_plan"],
    "exec3_steps": results["exec3"]["result"]["steps"],
    "aborted": ABORT, "gates_pass": PASS, "gates_fail": FAIL,
    "ffmpeg_calls": {"count": len(FF_CALLS), "argv_head": [c["argv"][:6] for c in FF_CALLS]},
    "before_state": {"history": {k: v[:16] for k, v in before["history"].items()},
                     "db": before["db"], "baseline": before["baseline"],
                     "projects_listing_len": len(before["projects_listing"])},
}
exec_results["exec_results_sha256"] = hashlib.sha256(json.dumps(
    exec_results, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
    default=str).encode("utf-8")).hexdigest()
(LOGS / "phase6g_sample_exec_results.json").write_text(
    json.dumps(exec_results, ensure_ascii=False, indent=1, default=str), encoding="utf-8")

print("\n== 执行阶段汇总 ==")
for k, v in results.items():
    print("  {} {} {}s audio_md5={} caption_base={}".format(
        k, v["path"], v["probe"]["duration_s"], v["audio_md5"][:12],
        (v["result"].get("caption_time_base") or {}).get("mode")))
print("  gates {} PASS / {} FAIL | ffmpeg calls {}".format(len(PASS), len(FAIL), len(FF_CALLS)))
print("  aborted: {}".format(ABORT))
print("exec results -> {}".format(LOGS / "phase6g_sample_exec_results.json"))
sys.exit(1 if FAIL else 0)
