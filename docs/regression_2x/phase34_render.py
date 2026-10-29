# -*- coding: utf-8 -*-
"""P34-4 终渲染：v4.2 净稿 + **无画面清零** + **运动停用**。

与 phase33_render.py 的差异（全部为最小必要差异）：
  1. 脚本/音频/时基 → **v4.2**（`script_p34_v42_40seg.json` / `narration_v42.mp3` / `timebase_v42.json`）；
  2. **具名绑定**（P34-1）：8 个"有旁白 + 纯色卡"景按授权书 §1(a) 具名绑定池内素材
     （**绕过匹配分阈值**，语义相关性由人工判定，带 `approval_document`）；
  3. **运动停用**（P34-2）：`render_motion.json` 已置 `enabled=false`（构造断言与三指标照跑）。

零 LLM；VLM 仅仲裁层按需。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
import sqlite3
import sys
import time
import traceback

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
SANDBOX = R / "output" / "phase34_p34_4_sandbox"
LOGS = R / "docs" / "regression_2x" / "logs"
SRC = R / "projects" / "p_96efdc03e1aa"
SCRIPT = R / "output/phase34_script_sandbox/script_p34_v42_40seg.json"
VOICEJ = R / "output/phase34_voice/voice_output_v42.json"
AUDIO = R / "output/phase34_voice/narration_v42.mp3"
SEGD = R / "output/phase34_voice/seg"
VISUAL = SRC / "artifacts" / "a_a6279580600a.json"
POOL_PAYLOAD = LOGS / "phase33_retrieval_payload.json"
FFPROBE = R / "bin" / "ffprobe.exe"

# P34-1 具名绑定：8 个卡景 → 池内素材（按旁白语义人工选定；见报告 §1.2）
#   key = 场景 id，value = {sha256 前缀, 选定理由}
BIND_SPEC = {
    "S03p1": ("1d2fe4b325bd", "机器验证数学 vs 知识论：黑板公式（形式化/机械检查意象）"),
    "S05p1": ("a3aff2f300eb", "「没有人读完」：人手书写证明（规模/不可通读意象）"),
    "S05p2": ("f0cd2a28016d", "「审稿拖很久、跑了多少机时」：历史数学文献页（年代/文献意象）"),
    "S13p1": ("1e9d2ab4e64e", "「真正的工作量在翻译」：Lean 交互界面截图（人→机翻译意象）"),
    "S16p1": ("301ff850be9c", "「机器能否做出人做不出的证明」：数学分支总图（知识结构意象）"),
    "S17p1": ("23e71bc8a864", "「验证从人类共同体转向机器逐句检查」：集邮式证明链（逐条检视意象）"),
    "S17p2": ("acaa16094c3b", "「数学家手上的活儿重排」：图论示例图（结构/重排意象）"),
    "S21p1": ("65377b888b77", "「证据等级差得很远」：罗素《数学原理》1+1=2 页（证据/严谨意象）"),
}


def log(m):
    print(m, flush=True)
    SANDBOX.mkdir(parents=True, exist_ok=True)
    with (SANDBOX / "render.log").open("a", encoding="utf-8") as fh:
        fh.write(str(m) + "\n")


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def dur(p):
    r = subprocess.run([str(FFPROBE), "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", str(p)], capture_output=True, text=True)
    v = (r.stdout or "").strip().splitlines()
    return round(float(v[0]), 3) if v and v[0] else None


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    from video_studio.core.env import load_env
    loaded = load_env(R / ".env")
    log("load_env -> {}".format(sorted(loaded.keys())))
    from video_studio.cli import build_engine, load_config
    from video_studio.tools import vlm_judge as _vj
    from video_studio.core import corr_diagnostics as _CD
    from video_studio.core import motion as _MO
    _cfg = json.loads((R / "config/config.json").read_text(encoding="utf-8"))
    _vcfg, _ = _vj.resolve_config(_cfg, root=R)
    _ok, _ = _vj.available(_vcfg)
    _bcfg, _bsrc = _CD.resolve_config(_cfg, root=R)
    _mcfg, _msrc = _MO.resolve_config(_cfg, root=R)
    log("VLM available={} | bank={} | **motion enabled={}** (src={})".format(
        _ok, _bcfg.get("bank_derived"), _mcfg.get("enabled"), str(_msrc)[-40:]))

    script = json.loads(SCRIPT.read_text(encoding="utf-8"))
    voice_obj = json.loads(VOICEJ.read_text(encoding="utf-8"))
    pool = json.loads(POOL_PAYLOAD.read_text(encoding="utf-8"))
    cands = [c for c in pool["candidates"] if c.get("path")]
    # 解析具名绑定（前缀 → 完整 sha256）
    binds = {}
    for sid, (pre, why) in BIND_SPEC.items():
        hit = next((c for c in cands if str(c["sha256"]).startswith(pre)), None)
        if hit is None:
            log("!! 具名绑定未解析: {} -> {}".format(sid, pre))
            continue
        binds[sid] = {"sha256": hit["sha256"], "name": hit.get("name"), "reason": why,
                      "approval_document": "Phase 34 授权书 §1(a)"}
    log("具名绑定 {} 个: {}".format(len(binds), {k: v["name"][:18] for k, v in binds.items()}))

    engine = build_engine(load_config(str(R / "config" / "config.json")))
    engine.config.setdefault("editing", {}).update({
        "max_scenes_per_asset": 3, "forbid_adjacent_same_asset": True,
        "explicit_bindings": binds})
    log("内存注入: cap=3 / forbid_adjacent=True / explicit_bindings={}".format(len(binds)))

    pid = engine.create_project("Phase 34 P34-4 交付级候选（v4.2 + 无画面清零 + 运动停用）",
                                name="phase34-p34-4-delivery-candidate")
    log("沙箱项目: " + pid)
    pdir = engine.project_dir(pid)
    t = pdir / "media" / "voice" / "narration_v42.mp3"
    t.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(AUDIO, t)
    n = 0
    for f in sorted(SEGD.glob("*.mp3")):
        d = pdir / "media" / "voice" / "seg" / f.name
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, d)
        n += 1
    log("音频就位: narration_v42.mp3 + {} 切片".format(n))

    ts = engine.create_task(pid, "script", "script", max_retries=0)
    tv = engine.create_task(pid, "voice", "voice", max_retries=0)
    tr = engine.create_task(pid, "retrieval", "retrieval", max_retries=0)
    te = engine.create_task(pid, "render", "editing", dependencies=[ts, tv, tr],
                            inputs={"render_params": {"resolution": "1920x1080", "fps": 25}},
                            max_retries=0)
    from video_studio.agents.base import AGENTS

    def h_script(eng, task):
        aid = eng.write_artifact(pid, task["task_id"], "script_output", script,
                                 summary="v4.2 净稿 × 40 段")
        eng.attach_artifact(task["task_id"], aid)
        vj = json.loads(VISUAL.read_text(encoding="utf-8"))
        vid = eng.write_artifact(pid, task["task_id"], "visual_plan_output", vj,
                                 summary="沿用 H5 visual_plan")
        eng.attach_artifact(task["task_id"], vid)
        log("  [script] {}".format(aid))
        return {}

    def h_voice(eng, task):
        v = dict(voice_obj)
        v["audio"] = "media/voice/narration_v42.mp3"
        v["segments"] = [{**s, "audio": "media/voice/" + s["audio"]} for s in v["segments"]]
        aid = eng.write_artifact(pid, task["task_id"], "voice_output", v,
                                 summary="v4.2 逐段配音（{} 段）".format(len(v["segments"])))
        eng.attach_artifact(task["task_id"], aid)
        log("  [voice] {}".format(aid))
        return {}

    def h_retrieval(eng, task):
        sel = {"schema": "retrieval-candidates-v1", "material_mode": "mixed",
               "candidates_total": len(cands), "material_provided": True,
               "candidates": cands}
        aid = eng.write_artifact(pid, task["task_id"], "retrieval_candidates", sel,
                                 summary="池 {} 张".format(len(cands)))
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
                                            str((tt or {}).get("error"))[:260]))
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
        {"schema": "p34-material-timeline-v1", "project_id": pid, "decisions": decisions},
        ensure_ascii=False, indent=1), encoding="utf-8")
    _cards = [d["scene_id"] for d in decisions
              if not (d.get("selected_asset") or {}).get("asset_id")]
    _bound = [d["scene_id"] for d in decisions
              if (d.get("selected_asset") or {}).get("asset_id")
              and "具名绑定" in str(d.get("fallback_reason"))]
    log("material_timeline -> {} 条 | **残留卡景 {}** | 具名绑定生效 {} | 仲裁 {}".format(
        len(decisions), _cards, len(_bound),
        json.dumps({k: (arb or {}).get(k) for k in ("called", "cost_usd")},
                   ensure_ascii=False) if arb else "无"))
    if arb:
        log("  仲裁 arbitrated={} still_failed={}".format(
            len(arb.get("arbitrated") or []), len(arb.get("still_failed") or [])))

    outro = None
    if outs and (tt or {}).get("status") == "SUCCEEDED":
        import importlib
        H7 = importlib.import_module("p32_h7")
        base = outs[-1]
        cand = pdir / "output" / (base.stem + "_with_outro_v2.mp4")
        try:
            outro = H7.apply_outro(str(R / "bin" / "ffmpeg.exe"), str(FFPROBE),
                                   base, cand, SANDBOX / "work_h7")
            log("H7 DONE: {} | {} -> {} | full_cover={}".format(
                cand.name, outro["duration_before_s"], outro["duration_after_s"],
                outro["video_full_cover"]))
        except Exception as exc:                                            # noqa: BLE001
            log("H7 失败: {}: {}".format(type(exc).__name__, exc))
    else:
        log("渲染未成功 ⇒ 不施加 H7")

    (SANDBOX / "fixture.json").write_text(json.dumps({
        "schema": "phase34-fixture-v1", "sandbox_project_id": pid,
        "tasks": {"script": ts, "voice": tv, "retrieval": tr, "editing": te},
        "script_sha256": sha(SCRIPT), "audio_sha256": sha(AUDIO),
        "n_pool": len(cands), "vlm_available": bool(_ok),
        "bank_chain": _bcfg.get("bank_derived"),
        "motion_enabled": bool(_mcfg.get("enabled")),
        "explicit_bindings": {k: v["sha256"][:12] for k, v in binds.items()},
        "card_scenes_remaining": _cards,
        "arbitration": arb, "outro": outro,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    log("fixture -> " + str((SANDBOX / "fixture.json").relative_to(R)))


if __name__ == "__main__":
    main()
