# -*- coding: utf-8 -*-
"""Phase 57 / P57-2：**F12 渲染**（生产 cue 路径修复后的首次真渲染）。

v6.5 音频／分配／画面**零改动**：复用沙箱工程 `p_3e9292101f10`（F10.1 同一工程，
script/voice/retrieval 产物原样在档），只**重跑 editing 任务**——cue 由
`build_cues_from_words_exact`（P55 验证版，P57-1 已接入生产单一分发链）重建。
分配由 `logs/p56_2_f9_pins.json`（F9 分配 = F10.1 实测 36/36 一致）钉定。

渲染前**前置门（fail-closed，授权书 §1「逐段连续性断言先过」）**：
  · 逐段切片连续性：Σ 景切片时长 == 段音频时长（Δ≤0.35s，P54-1 同规则）；
  · words_manifest（9 段）+ runs_by_scene（36 景）+ pins（36 景）齐备。
任何断 ⇒ 不创建任务、不渲染。

渲染后（outro 前）**产物签名门**：烧录 ASS cue 数 101–111 / 跨度 ≈ 音频 / median ≥3 /
排他 0 / dump 标签与逐条 source 一致（word_exact）。违反 ⇒ 不做 outro、按失败退出。

预算：LLM $0 / 渲染 ≤3h。运行:
  python docs/regression_2x/p57_2_render_f12.py
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import sqlite3
import statistics
import subprocess
import sys
import time
import traceback

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
P = "p_3e9292101f10"
PDIR = R / "projects" / P
LOG = R / "output" / "p40_probe" / "render_f12.log"
V36 = R / "output" / "phase36_voice"
FFPROBE = str(R / "bin" / "ffprobe.exe")
FF = str(R / "bin" / "ffmpeg.exe")
DEPS = ["t_08b2654a032a", "t_1c9aa0e07798", "t_14e51e4f778d"]  # script/voice/retrieval


def log(m):
    print(m, flush=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(str(m) + "\n")


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def dur(p):
    r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", str(p)],
                       capture_output=True, text=True)
    v = (r.stdout or "").strip().splitlines()
    return round(float(v[0]), 3) if v and v[0] else None


def parse_ass(p: pathlib.Path):
    rows = []
    for m in re.finditer(r"Dialogue: 0,([0-9:.]+),([0-9:.]+),",
                         p.read_text(encoding="utf-8")):
        def sec(ts):
            h, mm, rest = ts.split(":")
            return int(h) * 3600 + int(mm) * 60 + float(rest)
        rows.append((sec(m.group(1)), sec(m.group(2))))
    return rows


def precondition() -> list:
    """渲染前置门。返回违规列表（空 = 过）。"""
    v = []
    script = json.loads((PDIR / "artifacts" / "a_aec6a870612e.json")
                        .read_text(encoding="utf-8"))
    segs = script["segments"]
    by_para = {}
    for s in segs:
        by_para.setdefault(str(s["scene_id"]).split("_")[0], []).append(s)
    for para, lst in sorted(by_para.items()):
        tot = 0.0
        for s in lst:
            f = PDIR / "media" / "voice" / "seg" / "{}.wav".format(s["scene_id"])
            d = dur(f) if f.is_file() else None
            if d is None:
                v.append("缺切片:{}".format(s["scene_id"]))
                continue
            tot += d
        pa = V36 / "para" / "{}.mp3".format(para)
        pd = dur(pa) if pa.is_file() else None
        if pd is None:
            v.append("缺段音频:{}".format(para))
            continue
        if abs(tot - pd) > 0.35:
            v.append("切片不连续:{} Σ切片{:.3f} vs 段音频{:.3f}".format(para, tot, pd))
    wm = json.loads((PDIR / "media" / "voice" / "words_manifest.json")
                    .read_text(encoding="utf-8"))
    n_words = sum(len(p.get("words") or []) for p in (wm.get("paras") or []))
    if len(wm.get("paras") or []) != 9 or n_words != 1964:
        v.append("manifest 异常: {} 段 / {} 词".format(len(wm.get("paras") or []), n_words))
    rb = json.loads((PDIR / "media" / "voice" / "runs_by_scene.json")
                    .read_text(encoding="utf-8"))
    if int(rb.get("scene_count") or 0) != 36:
        v.append("runs_by_scene 景数异常: {}".format(rb.get("scene_count")))
    pins = json.loads((R / "docs/regression_2x/logs/p56_2_f9_pins.json")
                      .read_text(encoding="utf-8")).get("pins") or {}
    if len(pins) != 36:
        v.append("pins 异常: {} 景".format(len(pins)))
    return v


def main() -> int:
    LOG.write_text("", encoding="utf-8")
    t0 = time.time()
    log("== P57-2 F12 渲染（生产 cue 路径修复后首次真渲染）==")
    viol = precondition()
    if viol:
        log("**前置门 FAIL-CLOSED**（不渲染）：")
        for x in viol:
            log("  " + x)
        return 1
    log("前置门 PASS：切片连续（9 段 Δ≤0.35）/ manifest 9 段 1964 词 / runs 36 景 / pins 36 景")

    from video_studio.core.env import load_env
    loaded = load_env(R / ".env")
    log("load_env -> {}".format(sorted(loaded.keys())))
    from video_studio.cli import build_engine, load_config
    engine = build_engine(load_config(str(R / "config" / "config.json")))
    # ---- **F10.1 渲染 harness 的内存注入（逐字复刻，config.json 零改动）** ----
    # F10.1 日志（render_f101_v2.log）：「具名绑定 3 景：['P01_2','P01_3','P09_1']」
    # 「内存注入: cap=3 / forbid_adjacent=True / min_scene_gap=3 / bindings=3」。
    # 首轮 F12 尝试（t_e04a7b710817）漏掉此注入 ⇒ 分配纪律整体关闭
    #（material_allocation.enabled=False）⇒ 14 景卡景、0/36 与 pins 一致 ⇒
    # 产物已隔离（output/_quarantine_p57_invalid_alloc/）并记入 erratum。
    bp = json.loads((R / "output/phase36_voice/bindings_proposal.json")
                    .read_text(encoding="utf-8"))
    binds = {sid: {"sha256": v["sha256"], "name": v.get("name"),
                   "reason": v.get("reason"),
                   "approval_document": v.get("approval_document")}
             for sid, v in bp["bindings"].items()}
    engine.config.setdefault("editing", {}).update({
        "max_scenes_per_asset": 3, "forbid_adjacent_same_asset": True,
        "min_scene_gap": 3, "explicit_bindings": binds})
    log("内存注入（复刻 F10.1 harness）: cap=3 / forbid_adjacent=True / "
        "min_scene_gap=3 / bindings={} 景 {}".format(
            len(binds), sorted(binds)))
    log("渲染工程: {}（复用 F10.1 沙箱；音频/分配/画面零改动）".format(P))

    if len(sys.argv) > 1 and sys.argv[1] == "resume":
        # 断点续跑：复用**已 SUCCEEDED** 的 editing 任务（不重复渲染）。
        import sqlite3 as _sq
        _con = _sq.connect("file:" + (R / "projects" / "video_studio.db").as_posix()
                           + "?mode=ro", uri=True)
        _row = _con.execute(
            "select task_id from tasks where project_id=? and agent_role='editing' "
            "and status='SUCCEEDED' order by created_at desc limit 1", (P,)).fetchone()
        _con.close()
        if not _row:
            log("**resume 失败**：无已成功的 editing 任务")
            return 1
        te, status, err = _row[0], "SUCCEEDED", None
        log("resume: editing 任务 {}（已 SUCCEEDED，跳过渲染）".format(te))
    else:
        te = engine.create_task(P, "render", "editing", dependencies=DEPS,
                                inputs={"render_params": {"resolution": "1920x1080",
                                                          "fps": 25}},
                                max_retries=0)
        log("editing 任务: {}（deps={}）".format(te, DEPS))
        status, err = None, None
        try:
            for cyc in range(1, 9):
                k = engine.run_cycle(P, limit=10)
                log("cycle {}: 派发 {} | {:.1f}s".format(cyc, k, time.time() - t0))
                tt = engine.db.get_task(te) or {}
                if (tt or {}).get("status") in ("SUCCEEDED", "FAILED", "BLOCKED"):
                    status, err = tt.get("status"), tt.get("error")
                    break
                if k == 0:
                    break
        except Exception as exc:                                                # noqa: BLE001
            log("异常: {}: {}".format(type(exc).__name__, exc))
            log(traceback.format_exc()[-1200:])
            status = "EXCEPTION:" + type(exc).__name__
        log("渲染总耗时: {:.1f}s | status={} error={}".format(
            time.time() - t0, status, str(err or "")[:300]))
    if status != "SUCCEEDED":
        return 1

    tt = engine.db.get_task(te) or {}
    outs = sorted((PDIR / "output").glob("{}_draft.mp4".format(te)))
    if not outs:
        log("**无 draft 产物**")
        return 1
    draft = outs[-1]
    log("draft: {} {:,}B | {:.3f}s".format(draft.name, draft.stat().st_size,
                                           dur(draft) or 0))

    # ---- 产物签名门（outro 之前；以烧录 ASS 为对象）----
    ass = PDIR / "artifacts" / "_captions_{}.ass".format(te)
    dump_p = PDIR / "artifacts" / "_cuedump_{}.json".format(te)
    dmp = json.loads(dump_p.read_text(encoding="utf-8")) if dump_p.is_file() else {}
    rows = parse_ass(ass) if ass.is_file() else []
    durs = [round(e - s, 3) for s, e in rows]
    span = round(max((e for _, e in rows), default=0) - min((s for s, _ in rows), default=0), 3)
    ov = sum(1 for i in range(1, len(rows)) if rows[i][0] < rows[i - 1][1] - 1e-9)
    aud = dur(PDIR / "media" / "voice" / "narration_v65.mp3")
    gate = {"cues": len(rows), "span_s": span, "audio_s": aud,
            "median_dur": round(statistics.median(durs), 3) if durs else None,
            "max_dur": round(max(durs), 3) if durs else None,
            "overlap_pairs": ov,
            "d_1s_clamped": sum(1 for d in durs if abs(d - 1.0) <= 0.1),
            "dump_cue_source": dmp.get("cue_source"),
            "dump_first_sources": [c.get("source") for c in (dmp.get("first5") or [])],
            "dump_cue_gate": dmp.get("cue_gate")}
    ok = (101 <= gate["cues"] <= 111
          and aud is not None and abs(span - aud) <= 2.0
          and (gate["median_dur"] or 0) >= 3.0
          and ov == 0
          and gate["dump_cue_source"] == "word_exact"
          and set(gate["dump_first_sources"]) == {"word_exact"})
    log("签名门: {}".format(json.dumps(gate, ensure_ascii=False)))
    if not ok:
        log("**签名门 FAIL-CLOSED**（不做 outro、不交验证）")
        return 1
    log("签名门 PASS（cue_source=word_exact 与逐条 source 一致）")

    # ---- 分配指纹核对（**在 outro 之前**；须与 F10.1 的 36 景逐景一致）----
    pins = json.loads((R / "docs/regression_2x/logs/p56_2_f9_pins.json")
                      .read_text(encoding="utf-8")).get("pins") or {}
    con = sqlite3.connect("file:" + (R / "projects" / "video_studio.db").as_posix()
                          + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    r = con.execute("select payload from events where project_id=? and "
                    "type='MATERIAL_TIMELINE' order by ts desc limit 1", (P,)).fetchone()
    dec = json.loads(r["payload"])["decisions"] if r else []
    con.close()
    fp_now = {d["scene_id"]: str((d.get("selected_asset") or {}).get("sha256") or "")[:12]
              for d in dec}
    fp_f101 = {k: str(v)[:12] for k, v in pins.items()}
    same = sum(1 for k, v in fp_f101.items() if fp_now.get(k) == v)
    log("分配指纹: 与 F9/F10.1 pins 一致 {}/36 景".format(same))
    if same != 36:
        # **P57-2 硬门**：分配与 F10.1 不一致 = 画面变量失控（授权书 §2「分配/画面
        # 零改动」被破坏）⇒ 不做 outro、不交验证、按失败退出。
        log("**分配指纹 FAIL-CLOSED**：画面变量失控（须 36/36）")
        return 1

    # ---- H7 片尾卡（与 F10.1 同实现；总时长不变）----
    import importlib
    sys.path.insert(0, str(R / "docs" / "regression_2x"))
    H7 = importlib.import_module("p32_h7")
    cand = PDIR / "output" / (draft.stem + "_with_outro_v2.mp4")
    outro = H7.apply_outro(FF, FFPROBE, draft, cand, PDIR / "work_h7_f12")
    log("H7 DONE: {} | {} -> {} | full_cover={} | audio_identical={}".format(
        cand.name, outro["duration_before_s"], outro["duration_after_s"],
        outro["video_full_cover"], outro["audio_identical_to_base"]))
    if not (outro["duration_unchanged"] and outro["video_full_cover"]
            and outro["audio_identical_to_base"]):
        log("**H7 门 FAIL-CLOSED**")
        return 1

    fixture = {
        "schema": "p57-2-f12-render-fixture-v1", "recorded_at":
        time.strftime("%Y-%m-%dT%H:%M:%S"),
        "sandbox_project_id": P, "editing_task": te,
        "deps": DEPS, "render_status": status, "render_seconds": round(time.time() - t0, 1),
        "draft": draft.name, "draft_sha256": sha(draft), "draft_bytes": draft.stat().st_size,
        "final": cand.name, "final_sha256": sha(cand), "final_bytes": cand.stat().st_size,
        "final_duration_s": dur(cand), "outro": outro,
        "signature_gate": gate, "assignment_same_as_pins": same,
        "note": "音频/分配/画面零改动；唯一变量 = cue 层（word_exact 单一分发链）",
    }
    (R / "output" / "phase36_p36_4_sandbox" / "fixture_f12.json").write_text(
        json.dumps(fixture, ensure_ascii=False, indent=1), encoding="utf-8")
    log("fixture -> output/phase36_p36_4_sandbox/fixture_f12.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
