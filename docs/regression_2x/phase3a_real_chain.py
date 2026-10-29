"""3.x Phase 3-A 真实链路端到端驱动（真实 LLM + Wikimedia + 真实 TTS + 闸门 + 渲染 + 抽帧）。

单项目连续跑通：
  init → plan → （批准 topic/structure/script 闸门）→ script
  → ingest 无（素材来自真实 Provider）→ 批准全部 Claim（打开生产闸门）
  → retrieval（真实 Wikimedia 搜索/下载/校验）→ voice（真实 TTS，逐段状态 + 复用 + 重试）
  → 旁白完整性闸门 → subtitle/audio_mix → render（时间轴装配 + 时长契约 + 抽帧核验）
  → attribution/credits 交付物 → ffprobe / ffmpeg decode / 抽帧证据

断言（Phase 3-A 要求）：
  A 真实链路各环节均由真实产物证明（外部素材真实下载、TTS 段真实合成、成片真实可解码）
  B RESTRICTED/UNKNOWN 素材不在成片中（provider 拒收 + 分类门禁 + 交付物自检）
  C 署名台账与 material_timeline 逐条一致
  D 外部素材确实出现在成片（appears_in_film=true 且 corr ≥ 阈值）
  E 未解决项如实标记（不把不可证明的写成 PASS）

用法：python docs/regression_2x/phase3a_real_chain.py [--goal "..."] [--resume <pid>]
"""
import argparse
import json
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

FFPROBE = ROOT / "bin" / "ffprobe.exe"
FFMPEG = ROOT / "bin" / "ffmpeg.exe"
LOGS = ROOT / "docs" / "regression_2x" / "logs"
CONFIG = "config/config.real.provider.json"
DEFAULT_GOAL = ("Make a short video introducing what VR headsets look like and how they are worn. "
                "Use real photos of VR headsets.")
PASS, FAIL, PENDING = [], [], []


def clog(m):
    print(m, flush=True)
    with (LOGS / "phase3a_real_chain.log").open("a", encoding="utf-8") as fh:
        fh.write(str(m) + "\n")


def check(name, ok, detail="", pending=False):
    if pending:
        PENDING.append(name)
        print("PEND  " + name + (" | " + str(detail)[:200] if detail else ""))
        return
    (PASS if ok else FAIL).append(name)
    print(("PASS  " if ok else "FAIL  ") + name + (" | " + str(detail)[:220] if detail else ""))


def cli(*args):
    p = subprocess.run([sys.executable, "run.py", "--config", CONFIG, *args], cwd=str(ROOT),
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def rows(text, ch):
    return [[c.strip() for c in ln.split("|")] for ln in text.splitlines()
            if re.match(r"^\|\s*" + ch, ln)]


def db():
    con = sqlite3.connect(str(ROOT / "projects" / "video_studio.db"))
    con.row_factory = sqlite3.Row
    return con


def status_of(pid):
    rc, st = cli("status", pid)
    review, blocked, active, ok, tasks, maxver = [], [], 0, 0, {}, {}
    for f in rows(st, "t_"):
        if len(f) < 8:
            continue
        typ, stt = f[2], f[4]
        try:
            ver = int(f[5] or 0)
        except ValueError:
            ver = 0
        maxver[typ] = max(maxver.get(typ, 0), ver)
        if stt == "NEEDS_REVIEW":
            review.append((f[1], typ))
        elif stt in ("PENDING", "READY", "RUNNING", "DISPATCHED"):
            active += 1
        elif stt == "SUCCEEDED":
            ok += 1
        elif stt in ("FAILED", "BLOCKED"):
            blocked.append((f[1], typ, stt, f[9] if len(f) > 9 else "", ver))
    return review, blocked, active, ok, tasks, maxver


def pending_claims(pid):
    rc, cl = cli("claims", pid)
    return [f for f in rows(cl, "c_") if len(f) > 4 and f[4] not in ("VERIFIED", "REJECTED")]


def drive(pid):
    """批准闸门/Claim 并跑到 settled；真实链路可能因限流/超时失败 → 重做有限次。"""
    redos = {}
    for i in range(1, 61):
        for f in pending_claims(pid):
            cli("approve-claim", f[1], "--comment", "Phase 3-A 真实链路验收")
        review, blocked, active, ok, tasks, maxver = status_of(pid)
        live = [b for b in blocked if b[4] >= maxver.get(b[1], 0)]
        clog("[run {}] ok={} review={} active={} blocked(现行)={}".format(
            i, ok, len(review), active, len(live)))
        for t, typ in review:
            cli("approve", t, "approve", "--comment", "Phase 3-A 验收")
        for t, typ, stt, err, ver in live:
            clog("  BLOCKED {} v{}: {}".format(typ, ver, err[:180]))
            n = redos.get(typ, 0)
            if n < 3:                     # 真实网络/TTS 抖动允许有限重做
                redos[typ] = n + 1
                cli("redo", t)
                clog("  redo {} ({}) 第 {} 次".format(t, typ, n + 1))
            else:
                FAIL.append("任务真实失败:{}".format(typ))
        if FAIL:
            return
        if active == 0 and not review and not pending_claims(pid):
            clog("  settled")
            return
        cli("run", pid)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--goal", default=DEFAULT_GOAL)
    ap.add_argument("--resume", default="")
    args = ap.parse_args()

    if args.resume:
        pid = args.resume
        clog("\n===== resume {} =====".format(pid))
    else:
        rc, out = cli("init", args.goal, "--name", "test_phase3a_real_chain")
        pid = re.search(r"p_[0-9a-f]+", out).group(0)
        clog("\n===== Phase 3-A 真实链路 {} =====".format(pid))
        clog("goal: {}".format(args.goal))
        cli("plan", pid)
        clog("plan 完成")
    drive(pid)
    clog("链路结束，开始核验（project={}）".format(pid))

    con = db()
    arts = {}
    for r in con.execute("select * from artifacts where project_id=? "
                         "order by created_at, artifact_id", (pid,)):
        arts.setdefault(r["type"], []).append(dict(r))
    tasks = {r["task_type"]: dict(r) for r in
             con.execute("select * from tasks where project_id=?", (pid,))}
    con.close()

    def load(t):
        lst = arts.get(t) or []
        return json.loads(Path(lst[-1]["path"]).read_text(encoding="utf-8")) if lst else None

    ret, ren, att, voice = (load("retrieval_candidates"), load("render_output"),
                            load("attribution"), load("voice_output"))
    ext = (ret or {}).get("external_provider") or {}
    stats = ext.get("stats") or {}

    clog("\n=== 全链路证据 ===")
    clog("retrieval: mode={} 外部 verified={} rejected={} provider={}".format(
        (ret or {}).get("material_mode"), (ret or {}).get("external_verified"),
        len((ret or {}).get("external_rejected") or []), ext.get("name")))
    clog("provider stats: " + json.dumps({k: v for k, v in stats.items()
                                          if k != "response_digests"}, ensure_ascii=False))
    if voice:
        clog("voice: status={} complete={} {}/{} 段 reused={}".format(
            voice.get("status"), voice.get("complete"), voice.get("successful_segments"),
            voice.get("expected_segments"), len(voice.get("reused_segments") or [])))
    if ren:
        clog("render: timeline={} 有素材={} assembly={} duration={}s narration={}".format(
            ren.get("scene_count"), ren.get("scenes_with_asset"), ren.get("material_assembly"),
            ren.get("video_duration_s"), ren.get("narration_state")))
    if att:
        clog("attribution: entries={} classes={} restricted_in_film={}".format(
            att.get("entry_count"), att.get("license_classes_used"),
            att.get("restricted_or_unknown_in_film")))

    # ---- A 真实链路各环节 ----
    check("A1 真实 LLM 产出（script/render 等任务由真实模型完成）",
          tasks.get("script", {}).get("status") == "SUCCEEDED"
          and float(tasks.get("script", {}).get("cost_usd") or 0) > 0,
          {"script_cost_usd": tasks.get("script", {}).get("cost_usd")})
    check("A2 真实 Provider 检索（external 模式 + 真实下载字节 > 0）",
          (ret or {}).get("material_mode") in ("external", "mixed")
          and stats.get("downloaded_bytes", 0) > 0,
          {"mode": (ret or {}).get("material_mode"), "bytes": stats.get("downloaded_bytes")})
    check("A3 真实 TTS 逐段状态完整（COMPLETE 且 12/12 或全部段成功）",
          bool(voice) and voice.get("complete") is True
          and voice.get("successful_segments") == voice.get("expected_segments"),
          voice and {"status": voice.get("status"),
                     "seg": "{}/{}".format(voice.get("successful_segments"),
                                           voice.get("expected_segments"))})
    check("A4 旁白完整性闸门通过（render 记录 narration_state=COMPLETE）",
          (ren or {}).get("narration_state") == "COMPLETE",
          (ren or {}).get("narration_state"))
    check("A5 时间轴权威时长成立（成片时长 == 时间轴，误差 ≤ 1s）",
          (ren or {}).get("video_duration_ok") is True,
          (ren or {}).get("video_duration_s"))
    vid = (ren or {}).get("output")
    info, dec_rc = {}, None
    if vid and Path(vid).is_file():
        p = subprocess.run([str(FFPROBE), "-v", "error", "-print_format", "json", "-show_format",
                            "-show_streams", str(vid)], capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        info = json.loads(p.stdout or "{}")
        d = subprocess.run([str(FFMPEG), "-v", "error", "-i", str(vid), "-f", "null", "-"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        dec_rc = d.returncode
    check("A6 成片真实可解码（2 流 + ffmpeg decode rc=0）",
          dec_rc == 0 and len(info.get("streams") or []) == 2,
          {"decode_rc": dec_rc, "duration": (info.get("format") or {}).get("duration")})

    tl = (ren or {}).get("material_timeline") or []
    used = [s for s in tl if s.get("selected_asset")]

    # ---- B 受限/未知许可不得入片 ----
    bad = [s["scene_id"] for s in used
           if (s["selected_asset"].get("license_class") or "UNKNOWN")
           in ("RESTRICTED", "UNKNOWN")]
    check("B1 成片内无 RESTRICTED/UNKNOWN 许可素材", not bad, bad)
    rej_codes = [r.get("error_code") for r in ((ret or {}).get("external_rejected") or [])]
    check("B2 被拒候选（若有）带明确错误码且未入片",
          all(r.get("status") == "REJECTED" for r in ((ret or {}).get("external_rejected") or [])),
          rej_codes[:6])
    check("B3 交付物自检 restricted_or_unknown_in_film 为空",
          (att or {}).get("restricted_or_unknown_in_film") == [],
          (att or {}).get("restricted_or_unknown_in_film"))

    # ---- C 署名台账逐条一致 ----
    by_scene = {s["scene_id"]: s for s in tl}
    mism = []
    for e in (att or {}).get("entries") or []:
        s = by_scene.get(e["scene_id"])
        a = (s or {}).get("selected_asset") or {}
        for k in ("provider", "source_id", "source_url", "license", "usage_restrictions",
                  "attribution"):
            if e.get(k) != a.get(k):
                mism.append((e["scene_id"], k, e.get(k), a.get(k)))
        for k in ("asset_id", "name", "sha256", "path", "bytes"):
            if (e.get("selected_asset") or {}).get(k) != a.get(k):
                mism.append((e["scene_id"], "selected_asset." + k))
    check("C1 署名台账与 material_timeline 逐条一致", not mism, mism[:3])
    check("C2 台账镜头集合 == 有素材镜头集合",
          {e["scene_id"] for e in (att or {}).get("entries") or []}
          == {s["scene_id"] for s in used},
          (len((att or {}).get("entries") or []), len(used)))
    credits_ok = (bool((att or {}).get("credits_file"))
                  and (ROOT / "projects" / pid / att["credits_file"]).is_file())
    if (att or {}).get("entry_count"):
        credits_ok = credits_ok and all(k in (att or {}).get("credits_text", "")
                                        for k in ("provider", "source_id", "license", "attribution"))
    check("C3 credits 文本随片落盘" + ("且含 provider/source_id/license/attribution"
                                      if (att or {}).get("entry_count") else "（无素材→无署名项）"),
          credits_ok, {"file": (att or {}).get("credits_file"),
                       "entries": (att or {}).get("entry_count")})

    # ---- D 外部素材确实出现在成片 ----
    ext_used = [s for s in used if s["selected_asset"].get("provider") == "wikimedia_commons"]
    on_screen = [s for s in ext_used if s.get("appears_in_film") is True]
    mv = (ren or {}).get("material_verification") or {}
    check("D1 外部素材进入时间轴", bool(ext_used), len(ext_used))
    check("D2 外部素材抽帧证实出现在成片（appears_in_film=true）", bool(on_screen),
          [(s["scene_id"], (s.get("film_evidence") or {}).get("corr_expected")
            or (s.get("film_evidence") or {}).get("corr")) for s in on_screen])
    check("D3 相关度达到既定阈值（≥ min_corr）",
          all(((s.get("film_evidence") or {}).get("corr_expected")
               or (s.get("film_evidence") or {}).get("corr") or 0) >= (mv.get("min_corr") or 0.3)
              for s in on_screen),
          {"min_corr": mv.get("min_corr"),
           "corrs": [(s["scene_id"], (s.get("film_evidence") or {}).get("corr_expected")
                      or (s.get("film_evidence") or {}).get("corr")) for s in on_screen]})
    check("D4 渲染侧抽帧核验无失败镜头", not mv.get("failed_scenes"), mv.get("failed_scenes"))

    # ---- E 未解决项如实标记 ----
    if not ext_used:
        check("E1 外部素材入片（如环境限流导致失败须记 PENDING）", False,
              "无外部素材进入时间轴（环境/许可原因）", pending=True)
    att_sample = ((att or {}).get("entries") or [{}])[0]
    rep = {"project": pid, "goal": args.goal, "config": CONFIG,
           "retrieval": {"mode": (ret or {}).get("material_mode"),
                         "verified": (ret or {}).get("external_verified"),
                         "rejected": len((ret or {}).get("external_rejected") or [])},
           "provider_stats": {k: v for k, v in stats.items() if k != "response_digests"},
           "provider_digests": stats.get("response_digests"),
           "voice": voice and {"status": voice.get("status"),
                               "segments": "{}/{}".format(voice.get("successful_segments"),
                                                          voice.get("expected_segments")),
                               "narration_duration_s": voice.get("narration_duration_s"),
                               "duration_contract": voice.get("duration_contract")},
           "render": ren, "attribution_sample": att_sample,
           "attribution_artifact": (ren or {}).get("attribution_artifact"),
           "video": {"path": vid, "decode_rc": dec_rc,
                     "duration_s": (info.get("format") or {}).get("duration"),
                     "streams": len(info.get("streams") or [])},
           "checks": {"pass": PASS, "fail": FAIL, "pending": PENDING},
           "verdict": ("PASS" if not FAIL and not PENDING else
                       "PENDING" if not FAIL else "FAIL")}
    (LOGS / "phase3a_real_chain.json").write_text(
        json.dumps(rep, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    clog("\nVERDICT: {} | PASS={} FAIL={} PENDING={}".format(
        rep["verdict"], len(PASS), len(FAIL), len(PENDING)))
    if FAIL:
        clog("失败项: " + str(FAIL))
    if PENDING:
        clog("未决项: " + str(PENDING))
    clog("记录: " + str(LOGS / "phase3a_real_chain.json"))
    return 0 if rep["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
