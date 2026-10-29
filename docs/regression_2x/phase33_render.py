# -*- coding: utf-8 -*-
"""P33-4 终渲染：**v4.1 稿首次入片**。

链路：v4.1 音频（新时基 700.592s）× 新窗口 × 扩容池（≥20）× 运动质量修复版（守卫）
      × 仲裁 × 绑定回退 × 构造断言，随后施加 **H7 片尾卡（in-window overlay，时长不变）**。

与 phase32_render.py 的差异（全部为最小必要差异）：
  1. 脚本 → v4.1 40 段（`script_p27_v41_40seg.json`，**首次真正入片**）；
  2. 音频 → `output/phase33_voice/narration_v41.mp3`（**本期配音**，非旧谱系音频）；
  3. 池 → `phase33_retrieval_payload.json`（扩容后 ≥20 张）；
  4. 加载 `.env`（仲裁层 VLM 可用）；`bank_derived` 走外部链（v2）。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
import sqlite3
import subprocess
import sys
import time
import traceback

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
SANDBOX = R / "output" / "phase33_p33_4_sandbox"
LOGS = R / "docs" / "regression_2x" / "logs"
SRC = R / "projects" / "p_96efdc03e1aa"
SCRIPT = R / "output/phase33_script_sandbox/script_p33_v41_40seg.json"
VOICEJ = R / "output/phase33_voice/voice_output_v41.json"
AUDIO = R / "output/phase33_voice/narration_v41.mp3"
SEGD = R / "output/phase33_voice/seg"
VISUAL = SRC / "artifacts" / "a_a6279580600a.json"
POOL_PAYLOAD = LOGS / "phase33_retrieval_payload.json"
FFPROBE = R / "bin" / "ffprobe.exe"


def log(m):
    print(m, flush=True)
    SANDBOX.mkdir(parents=True, exist_ok=True)
    with (SANDBOX / "render.log").open("a", encoding="utf-8") as fh:
        fh.write(str(m) + "\n")


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    from video_studio.core.env import load_env
    loaded = load_env(R / ".env")
    log("load_env -> {}".format(sorted(loaded.keys())))
    from video_studio.cli import build_engine, load_config
    from video_studio.tools import vlm_judge as _vj
    from video_studio.core import corr_diagnostics as _CD
    _cfg = json.loads((R / "config/config.json").read_text(encoding="utf-8"))
    _vcfg, _vsrc = _vj.resolve_config(_cfg, root=R)
    _ok, _why = _vj.available(_vcfg)
    _bcfg, _bsrc = _CD.resolve_config(_cfg, root=R)
    log("VLM available={} | bank chain={} | source={}".format(
        _ok, _bcfg.get("bank_derived"), str(_bsrc)[-46:]))

    script = json.loads(SCRIPT.read_text(encoding="utf-8"))
    voice_obj = json.loads(VOICEJ.read_text(encoding="utf-8"))
    pool = json.loads(POOL_PAYLOAD.read_text(encoding="utf-8"))
    cands = [c for c in pool["candidates"] if c.get("path")]
    log("底片 {} 段 | 池候选 {} 张 | 新时基 {}".format(
        len(script["segments"]), len(cands),
        json.loads((R / "output/phase33_voice/timebase_v41.json")
                   .read_text(encoding="utf-8"))["audio_time_base_s"]))

    engine = build_engine(load_config(str(R / "config" / "config.json")))
    # P33-2：分配纪律**内存注入**（`config.json` 为钉定文件，**不落盘**；同
    # `config.tools.render_motion` 的运行时注入先例）。
    try:
        engine.config.setdefault("editing", {}).update({
            "max_scenes_per_asset": 3, "forbid_adjacent_same_asset": True})
        log("分配纪律（内存注入）: max_scenes_per_asset=3, forbid_adjacent_same_asset=True")
    except Exception as _e:                                                 # noqa: BLE001
        log("分配纪律注入失败: {}".format(_e))
    pid = engine.create_project("Phase 33 P33-4 交付级候选（v4.1 首次入片 + H7）",
                                name="phase33-p33-4-delivery-candidate")
    log("沙箱项目: " + pid)
    pdir = engine.project_dir(pid)
    t = pdir / "media" / "voice" / "narration_v41.mp3"
    t.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(AUDIO, t)
    n = 0
    for f in sorted(SEGD.glob("*.mp3")):
        d = pdir / "media" / "voice" / "seg" / f.name
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, d)
        n += 1
    log("音频就位: narration_v41.mp3 + {} 切片".format(n))

    ts = engine.create_task(pid, "script", "script", max_retries=0)
    tv = engine.create_task(pid, "voice", "voice", max_retries=0)
    tr = engine.create_task(pid, "retrieval", "retrieval", max_retries=0)
    te = engine.create_task(pid, "render", "editing", dependencies=[ts, tv, tr],
                            inputs={"render_params": {"resolution": "1920x1080", "fps": 25}},
                            max_retries=0)
    from video_studio.agents.base import AGENTS

    def h_script(eng, task):
        aid = eng.write_artifact(pid, task["task_id"], "script_output", script,
                                 summary="v4.1 × 40 段（首次入片）")
        eng.attach_artifact(task["task_id"], aid)
        vj = json.loads(VISUAL.read_text(encoding="utf-8"))
        vid = eng.write_artifact(pid, task["task_id"], "visual_plan_output", vj,
                                 summary="沿用 H5 visual_plan")
        eng.attach_artifact(task["task_id"], vid)
        log("  [script] {}".format(aid))
        return {}

    def h_voice(eng, task):
        v = dict(voice_obj)
        v["audio"] = "media/voice/narration_v41.mp3"
        v["segments"] = [{**s, "audio": "media/voice/" + s["audio"]} for s in v["segments"]]
        aid = eng.write_artifact(pid, task["task_id"], "voice_output", v,
                                 summary="v4.1 逐段配音（{} 段）".format(len(v["segments"])))
        eng.attach_artifact(task["task_id"], aid)
        log("  [voice] {}".format(aid))
        return {}

    def h_retrieval(eng, task):
        sel = {"schema": "retrieval-candidates-v1", "material_mode": "mixed",
               "candidates_total": len(cands), "material_provided": True,
               "candidates": cands}
        aid = eng.write_artifact(pid, task["task_id"], "retrieval_candidates", sel,
                                 summary="扩容池 {} 张".format(len(cands)))
        eng.attach_artifact(task["task_id"], aid)
        log("  [retrieval] {}".format(aid))
        return {}

    for role, fn in (("script", h_script), ("voice", h_voice), ("retrieval", h_retrieval)):
        if role in AGENTS:
            AGENTS[role].run = fn
    t0 = time.time()
    try:
        for cyc in range(1, 9):
            k = engine.run_cycle(pid, limit=10)
            log("cycle {}: 派发 {} | {:.1f}s".format(cyc, k, time.time() - t0))
            if k == 0:
                break
    except Exception as exc:                                                    # noqa: BLE001
        log("异常: {}: {}".format(type(exc).__name__, exc))
        log(traceback.format_exc()[-1500:])
    log("渲染总耗时: {:.1f}s".format(time.time() - t0))
    tt = engine.db.get_task(te)
    log("render: status={} error={}".format((tt or {}).get("status"),
                                            str((tt or {}).get("error"))[:300]))
    outs = sorted((pdir / "output").glob("*.mp4"))
    for f in outs:
        log("  out {} {:,}B".format(f.name, f.stat().st_size))

    con = sqlite3.connect("file:" + (R / "projects" / "video_studio.db").as_posix()
                          + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    r = con.execute("select payload from events where project_id=? and "
                    "type='MATERIAL_TIMELINE' order by ts desc limit 1", (pid,)).fetchone()
    decisions = json.loads(r["payload"])["decisions"] if r else []
    ra = con.execute("select payload from events where project_id=? and "
                     "type='RENDER_ARBITRATION' order by ts desc limit 1", (pid,)).fetchone()
    arb = json.loads(ra["payload"]) if ra else None
    con.close()
    (SANDBOX / "material_timeline.json").write_text(json.dumps(
        {"schema": "p33-material-timeline-v1", "project_id": pid, "decisions": decisions},
        ensure_ascii=False, indent=1), encoding="utf-8")
    log("material_timeline -> {} 条 | 仲裁 {}".format(
        len(decisions), json.dumps({k: arb.get(k) for k in
                                    ("called", "cost_usd")}, ensure_ascii=False)
        if arb else "无"))
    if arb:
        log("  仲裁 arbitrated={} still_failed={}".format(
            len(arb.get("arbitrated") or []), len(arb.get("still_failed") or [])))

    # ---- H7 片尾卡（复用 P32 已验证的 TS 拼接实现） ----
    outro = None
    if outs and (tt or {}).get("status") == "SUCCEEDED":
        import importlib
        H7 = importlib.import_module("p32_h7")
        base = outs[-1]
        cand = pdir / "output" / (base.stem + "_with_outro_v2.mp4")
        try:
            outro = H7.apply_outro(str(R / "bin" / "ffmpeg.exe"),
                                   str(FFPROBE), base, cand, SANDBOX / "work_h7")
            log("H7 DONE: {} | {} -> {} | video_full_cover={}".format(
                cand.name, outro["duration_before_s"], outro["duration_after_s"],
                outro["video_full_cover"]))
        except Exception as exc:                                            # noqa: BLE001
            log("H7 失败: {}: {}".format(type(exc).__name__, exc))
    else:
        log("渲染未成功 ⇒ 不施加 H7")

    (SANDBOX / "fixture.json").write_text(json.dumps({
        "schema": "phase33-fixture-v1", "sandbox_project_id": pid,
        "tasks": {"script": ts, "voice": tv, "retrieval": tr, "editing": te},
        "script_sha256": sha(SCRIPT), "audio_sha256": sha(AUDIO),
        "n_pool": len(cands), "vlm_available": bool(_ok),
        "bank_chain": _bcfg.get("bank_derived"), "arbitration": arb, "outro": outro,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    log("fixture -> " + str((SANDBOX / "fixture.json").relative_to(R)))


if __name__ == "__main__":
    main()
