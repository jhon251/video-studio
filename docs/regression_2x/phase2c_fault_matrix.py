"""Phase 2-C 故障矩阵驱动：真实构造 4 类素材不足 + 真实成片/阻断证据。

每个用例都是一个**真实项目**（真实 DB / 真实 ingest / 真实 retrieval / 真实 ffmpeg 渲染），
脚本产物由驱动写入（确定性 2 段脚本，避免消耗 LLM 额度），素材是真实图片文件。

用例：
  A_normal        命中素材（皮肤界面截图）           → S01 LOCAL_INGEST + S02 占位（混合）→ 出片，抽帧核验
  B_no_candidate  只有完全无关的素材               → 全场景 NO_CANDIDATE → ASSEMBLY_BLOCKED → render BLOCKED
  C_low_match     素材名只共享 1 个字（低于阈值 3）  → LOW_MATCH → THEME_FALLBACK → 出片（降级素材上屏）
  D_unusable      素材文件损坏（伪装 jpg 的文本）    → ASSET_UNUSABLE → ASSEMBLY_BLOCKED → render BLOCKED

用法：python docs/regression_2x/phase2c_fault_matrix.py [--case A|B|C|D ...]
"""
import argparse
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.agents.base import AGENTS  # noqa: E402
from video_studio.core.engine import Engine  # noqa: E402
from video_studio.db.schema import Database  # noqa: E402
from video_studio.llm.router import MockLLM, Router  # noqa: E402

# Agent 需被导入才会 @register（与 cli.py 一致）——本驱动用到 script/retrieval/editing/asset
import video_studio.agents.asset.agent  # noqa: E402,F401
import video_studio.agents.editing.agent  # noqa: E402,F401
import video_studio.agents.retrieval.agent  # noqa: E402,F401
import video_studio.agents.script.agent  # noqa: E402,F401

FFPROBE = ROOT / "bin" / "ffprobe.exe"
FFMPEG = ROOT / "bin" / "ffmpeg.exe"
LOGS = ROOT / "docs" / "regression_2x" / "logs"
LOGS.mkdir(parents=True, exist_ok=True)
REAL_IMG = ROOT / "output" / "run03" / "asset_cache" / "files" / "r3_S01-B02_1.img.jpg"
REAL_IMG2 = ROOT / "output" / "run03" / "asset_cache" / "files" / "r3_S01-B01_3.img.jpg"

SCRIPT = {"segments": [
    {"chapter": "命中段", "narration": "皮肤界面截图展示鲸鱼娘皮肤。", "duration_s": 4},
    {"chapter": "无关段", "narration": "这一段讲完全无关的内容。", "duration_s": 4},
], "summary": "Phase 2-C 故障矩阵测试脚本"}


def log(m):
    print(m, flush=True)
    with (LOGS / "phase2c_fault_matrix.log").open("a", encoding="utf-8") as fh:
        fh.write(str(m) + "\n")


def cli(*a):
    p = subprocess.run([sys.executable, "run.py", "--config", "config/config.json", *a],
                       cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def engine_for():
    cfg = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8"))
    rules = json.loads((ROOT / "config" / "rules.json").read_text(encoding="utf-8"))
    return Engine(Database(ROOT / "projects" / "video_studio.db"),
                  Router(cfg["llm"], MockLLM(cfg["llm"].get("mock", {}).get("responses", {}),
                                             cfg["llm"].get("mock", {}).get("default", {}))),
                  rules, ROOT / "projects", cfg, AGENTS)


def build_case(case, asset_files, name):
    """建项目 → ingest 素材 → 写脚本产物 → retrieval → render。返回结果字典。"""
    eng = engine_for()
    pid = eng.create_project(name)
    src = Path(tempfile.mkdtemp(prefix="vs_p2c_"))
    for rel, dst_name in asset_files:
        if rel is None:                       # 构造损坏素材（伪装扩展名的文本文件）
            (src / dst_name).write_bytes(b"NOT-AN-IMAGE " * 40)
        else:
            shutil.copy2(ROOT / rel, src / dst_name)
    rc, out = cli("ingest", pid, str(src))
    log("  ingest -> " + out.strip().splitlines()[-1][:120])

    t_script = eng.create_task(pid, "script", "script")
    aid = eng.write_artifact(pid, t_script, "script_output", SCRIPT, summary="脚本")
    eng.attach_artifact(t_script, aid)
    eng.db.set_task_status(t_script, "SUCCEEDED")

    t_ret = eng.create_task(pid, "retrieval", "retrieval", dependencies=[t_script])
    eng.run_cycle(pid, limit=4)
    t_rend = eng.create_task(pid, "render", "editing", dependencies=[t_script, t_ret])
    # 跑到终态：素材不足会 FAILED→重试→BLOCKED，逐个 cycle 推进直到不再是 PENDING/FAILED
    first_error, cycles = None, 0
    for cycles in range(1, 6):
        eng.run_cycle(pid, limit=4)
        st = eng.db.get_task(t_rend)["status"]
        if first_error is None and eng.db.get_task(t_rend)["error"]:
            first_error = eng.db.get_task(t_rend)["error"]
        if st not in ("PENDING", "DISPATCHED", "RUNNING"):
            break

    con = sqlite3.connect(str(ROOT / "projects" / "video_studio.db"))
    con.row_factory = sqlite3.Row

    def task(tid):
        return dict(con.execute("select * from tasks where task_id=?", (tid,)).fetchone())

    def art(tid, type_):
        rows = list(con.execute("select * from artifacts where task_id=? and type=? "
                                "order by created_at desc", (tid, type_)))
        if not rows:
            return None
        return json.loads(Path(rows[0]["path"]).read_text(encoding="utf-8"))

    # 阻断场景的追溯记录在 render 前的 MATERIAL_TIMELINE 事件里（既有事件类型，未新增）
    ev = con.execute("select payload from events where project_id=? and type='MATERIAL_TIMELINE' "
                     "order by ts desc limit 1", (pid,)).fetchone()
    timeline_event = json.loads(ev["payload"]) if ev else None

    res = {"case": case, "project": pid, "render_task": t_rend, "cycles": cycles,
           "render_status": task(t_rend)["status"], "render_error": task(t_rend)["error"],
           "first_error": first_error, "timeline_event": timeline_event,
           "retrieval": art(t_ret, "retrieval_candidates"), "render": art(t_rend, "render_output")}
    con.close()
    return res


def probe(path, extra_args=()):
    p = subprocess.run([str(FFPROBE), "-v", "error", *extra_args, "-print_format", "json",
                        "-show_format", "-show_streams", str(path)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return json.loads(p.stdout or "{}")


CASES = {
    "A_normal": [("output/run03/asset_cache/files/r3_S01-B01_3.img.jpg", "皮肤界面截图_01.jpg")],
    "B_no_candidate": [("output/run03/asset_cache/files/r3_S01-B01_3.img.jpg", "mountain_view.jpg")],
    "C_low_match": [("output/run03/asset_cache/files/r3_S01-B01_3.img.jpg", "面.jpg")],
    "D_unusable": [(None, "皮肤界面截图_损坏.jpg")],
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", action="append", default=None)
    args = ap.parse_args()
    want = args.case or list(CASES)
    out = []
    for case in want:
        log("\n=== case {} ===".format(case))
        res = build_case(case, CASES[case], "test_phase2c_" + case.lower())
        rd = res.get("render") or {}
        tl = rd.get("material_timeline") or []
        log("  project={} render_status={} cycles={}".format(
            res["project"], res["render_status"], res["cycles"]))
        if res.get("render_error"):
            log("  render_error=" + str(res["render_error"])[:300])
        tev = res.get("timeline_event") or {}
        if tev.get("decisions"):
            log("  timeline_event(render 前阻断证据): " + json.dumps([{
                "scene": d["scene_id"], "class": d["insufficiency_class"],
                "state": d["fallback_state"], "reason": d["fallback_reason"][:90],
                "asset": (d.get("selected_asset") or {}).get("name"),
                "hitl": d["needs_hitl"], "allowed": d["allowed_in_final_render"]}
                for d in tev["decisions"]], ensure_ascii=False))
            log("  assembly_class(event)={}".format(tev.get("assembly_class")))
        if res.get("retrieval"):
            r = res["retrieval"]
            log("  retrieval: mode={} candidates_total={} names={}".format(
                r.get("material_mode"), r.get("candidates_total"),
                [c.get("name") for c in (r.get("candidates") or [])]))
        if tl:
            log("  scenes: " + json.dumps([{
                "scene": s["scene_id"], "class": s["insufficiency_class"],
                "state": s["fallback_state"], "asset": (s.get("selected_asset") or {}).get("name"),
                "score": (s.get("candidates") or [{}])[0].get("match_score")
                if s.get("candidates") else None,
                "hitl": s["needs_hitl"], "allowed": s["allowed_in_final_render"],
                "appears": s.get("appears_in_film")} for s in tl], ensure_ascii=False))
            log("  assembly={} insuff={}".format(
                rd.get("material_assembly"),
                json.dumps((rd.get("insufficiency_summary") or {}).get("assembly_class"))))
            ev = rd.get("material_verification") or {}
            log("  frame_verification: checked={} placeholder={} failed={} skipped={}".format(
                ev.get("checked_scenes"), ev.get("placeholder_verified"),
                [f["scene_id"] for f in (ev.get("failed_scenes") or [])], ev.get("skipped")))
        vids = sorted((ROOT / "projects" / res["project"] / "output").glob("*.mp4"))
        if vids:
            v = vids[-1]
            info = probe(v)
            dur = (info.get("format") or {}).get("duration")
            dec = subprocess.run([str(FFMPEG), "-v", "error", "-i", str(v), "-f", "null", "-"],
                                 capture_output=True, text=True, encoding="utf-8", errors="replace")
            log("  成片 {} {}bytes duration={} streams={} decode_rc={}".format(
                v.name, v.stat().st_size, dur, len(info.get("streams") or []), dec.returncode))
            res["video"] = {"path": str(v), "bytes": v.stat().st_size, "duration_s": dur,
                            "streams": len(info.get("streams") or []),
                            "decode_rc": dec.returncode}
        else:
            log("  无成片（render {}）".format(res["render_status"]))
            res["video"] = None
        out.append(res)
    p = LOGS / "phase2c_fault_matrix.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    log("\n记录: " + str(p))
    return 0


if __name__ == "__main__":
    sys.exit(main())
