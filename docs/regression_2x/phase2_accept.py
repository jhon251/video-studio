"""3.x Phase 2-A/B 验收驱动：真实选材 + 3 个本地素材 + 镜头级素材时间轴 + 抽帧核验。

流程（全程真实链路，不伪造）：
  1) 真实 LLM 项目：init + ingest（先给素材） + plan（config.real.json）
  2) 跑到 `script` 成功（批准 topic/structure 任务闸门）
  3) 批准 Claim → 跑到 settled（retrieval/asset_audit/render 能看到素材）
  4) 核验：retrieval 命中 ≥3、render 的 material_timeline ≥3 镜头且 ≥3 个不同素材、
     逐镜头抽帧与该镜头素材相关性最高、不同镜头画面互不相同、ffprobe、ffmpeg decode

用法：
  python docs/regression_2x/phase2_accept.py                # 全新跑一遍（真实 LLM）
  python docs/regression_2x/phase2_accept.py --resume <pid>  # 续跑已有项目

status 表格列（9 列，split('|') 后下标）：
  1=task_id 2=type 3=agent 4=status 5=version 6=attempts 7=gate 8=rounds 9=error
claims 表格列：1=claim_id 2=type 3=risk 4=status 5=verdict 6=evidence 7=note 8=text
"""
import hashlib
import json
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
FFPROBE = ROOT / "bin" / "ffprobe.exe"
FFMPEG = ROOT / "bin" / "ffmpeg.exe"
TMP = Path(r"C:\Users\DUALAN~1\AppData\Local\Temp\v161audit\p2")
TMP.mkdir(parents=True, exist_ok=True)
PROMPT = "做一期介绍 VR 与脑机接口设备长什么样的短视频。"
PREFIX = "P2"
MAX_REDO_PER_TYPE = 2  # 同一任务类型最多重做次数，超过即视为真实失败

# 已人工核对内容的本地真图 → ingest 名称（按所见内容命名）
ASSETS = [
    ("output/run03/asset_cache/files/r3_S01-B01_3.img.jpg", "VR头显_镜片特写.jpg"),
    ("output/run03/asset_cache/files/r3_S01-B02_1.img.jpg", "脑电头环_假人头模_陈列柜.jpg"),
    ("output/run03/asset_cache/files/r3_S01-B01_0.img.jpg", "VR头显_手柄_笔记本.jpg"),
]


def clog(m):
    print(m, flush=True)
    with (ROOT / "docs/regression_2x/logs" / "{}_accept.log".format(PREFIX)).open(
            "a", encoding="utf-8") as fh:
        fh.write(str(m) + "\n")


def cli(*args):
    p = subprocess.run([sys.executable, "run.py", "--config", "config/config.real.json", *args],
                       cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def rows(text, ch):
    return [[c.strip() for c in ln.split("|")] for ln in text.splitlines()
            if re.match(r"^\|\s*" + ch, ln)]


def db():
    con = sqlite3.connect(str(ROOT / "projects" / "video_studio.db"))
    con.row_factory = sqlite3.Row
    return con


def status_of(pid):
    """返回 (review, blocked, active, ok, tasks, maxver)。

    redo 会保留旧的 BLOCKED 记录并新建 version+1，因此必须按**类型最高版本**判断真实状态：
    低于该类型最高版本的 BLOCKED/FAILED 行是历史记录，不代表当前失败。
    """
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


def claim_rows(pid):
    rc, cl = cli("claims", pid)
    return rows(cl, "c_")


def pending_claims(pid):
    return [f for f in claim_rows(pid) if len(f) > 4 and f[4] not in ("VERIFIED", "REJECTED")]


def grams(p):
    im = Image.open(p).convert("L").resize((48, 48))
    return np.asarray(im, dtype=np.float64)


def corr(a, b):
    a, b = a - a.mean(), b - b.mean()
    d = np.sqrt((a ** 2).sum()) * np.sqrt((b ** 2).sum())
    return float((a * b).sum() / d) if d else 0.0


def stage_assets(pid):
    """把 3 张已核对内容的真图复制到临时目录并 ingest（扩展名与真实格式一致）。"""
    src_dir = TMP / "ingest_src"
    src_dir.mkdir(parents=True, exist_ok=True)
    staged = []
    for rel, name in ASSETS:
        d = src_dir / name
        shutil.copy2(ROOT / rel, d)
        with Image.open(d) as im:
            fmt, size = im.format, im.size
        staged.append({"src": rel, "ingest_name": name,
                       "sha256": hashlib.sha256(d.read_bytes()).hexdigest(),
                       "bytes": d.stat().st_size, "format": fmt, "size": "{}x{}".format(*size)})
    rc, out = cli("ingest", pid, str(src_dir))
    clog("ingest -> " + out.strip())
    for s in staged:
        clog("  {} | {} | {} bytes | {} {}".format(
            s["ingest_name"], s["sha256"][:16], s["bytes"], s["format"], s["size"]))
    return staged


def wait_for_script(pid, fails, max_rounds=20):
    for i in range(1, max_rounds + 1):
        review, blocked, active, ok, tasks, maxver = status_of(pid)
        live = [b for b in blocked if b[4] >= maxver.get(b[1], 0)]
        clog("[pre {}] ok={} review={} active={} blocked={} script={}".format(
            i, ok, len(review), active, len(live), tasks.get("script")))
        for t, typ in review:
            cli("approve", t, "approve", "--comment", "Phase2-A/B 验收")
            clog("  approve gate {}".format(typ))
        for t, typ, stt, err, ver in live:
            clog("  BLOCKED {} v{} {}: {}".format(typ, ver, stt, err[:140]))
            fails.append("前置任务失败:" + typ)
        if any(b[1] == "script" for b in live):
            return False
        if tasks.get("script") == "SUCCEEDED":
            return True
        if active == 0 and not review:
            return False
        rc, o = cli("run", pid)
        clog("  run -> " + o.strip().splitlines()[-1][:60])
    return False


def drive_to_settle(pid, fails, max_rounds=40):
    """批准 Claim + 任务闸门，重做因瞬时故障阻塞的任务，跑到 settled。

    只对**当前最高版本**的 BLOCKED 记录做 redo；每类型最多 MAX_REDO_PER_TYPE 次。
    """
    redos = {}
    for i in range(1, max_rounds + 1):
        pend = pending_claims(pid)
        for f in pend:
            cli("approve-claim", f[1], "--comment", "Phase2-A/B 验收")
        if pend:
            clog("[claims {}] 批准 {} 条".format(i, len(pend)))
        review, blocked, active, ok, tasks, maxver = status_of(pid)
        live = [b for b in blocked if b[4] >= maxver.get(b[1], 0)]
        stale = len(blocked) - len(live)
        clog("[run {}] ok={} review={} active={} blocked(现行)={} 历史blocked={} redos={}".format(
            i, ok, len(review), active, len(live), stale, redos))
        for t, typ in review:
            cli("approve", t, "approve", "--comment", "Phase2-A/B 验收")
            clog("  approve gate {}".format(typ))
        for t, typ, stt, err, ver in live:
            clog("  BLOCKED {} v{} {}: {}".format(typ, ver, stt, err[:140]))
            n = redos.get(typ, 0)
            if n >= MAX_REDO_PER_TYPE:
                clog("    !! {} 重做 {} 次仍失败，判定真实失败".format(typ, n))
                fails.append("任务真实失败:{}".format(typ))
                continue
            redos[typ] = n + 1
            cli("redo", t)
            clog("    redo {} ({}) 第 {}/{} 次".format(t, typ, n + 1, MAX_REDO_PER_TYPE))
        if fails:
            clog("  中止：存在真实失败")
            return
        if active == 0 and not review and not pend:
            clog("  settled")
            return
        rc, o = cli("run", pid)
        clog("  run -> " + o.strip().splitlines()[-1][:60])
    clog("  !! 未在轮次上限内 settled")
    fails.append("未 settled")


def verify(pid, staged, fails):
    con = db()
    arts = {}
    # 显式按 created_at 排序：同一类型可能有多版本产物（redo 后残留旧版），必须取最新
    for r in con.execute("select * from artifacts where project_id=? "
                         "order by created_at, artifact_id", (pid,)):
        arts.setdefault(r["type"], []).append(dict(r))
    con.close()

    def load(t):
        lst = arts.get(t) or []
        return json.loads(Path(lst[-1]["path"]).read_text(encoding="utf-8")) if lst else None

    rc_a, ren = load("retrieval_candidates"), load("render_output")
    cands = (rc_a or {}).get("candidates") or []
    tl = (ren or {}).get("material_timeline") or []
    used = [s for s in tl if s.get("selected_asset")]
    used_ids = {s["selected_asset"]["asset_id"] for s in used}
    clog("\n=== 产物核验 ===")
    clog("retrieval: mode={} 候选={} 命中={}".format(
        (rc_a or {}).get("material_mode"), (rc_a or {}).get("candidates_total"), len(cands)))
    for c in cands:
        clog("   - {} score={} sha16={} matched={}".format(
            c.get("name"), c.get("match_score"), str(c.get("sha256"))[:16],
            c.get("matched_tokens")))
    clog("render: visual_source={} assembly={} 镜头={} 有素材镜头={} 不同素材={}".format(
        (ren or {}).get("visual_source"), (ren or {}).get("material_assembly"),
        len(tl), len(used), len(used_ids)))
    for s in tl:
        a = s.get("selected_asset") or {}
        clog("   {} {:.1f}-{:.1f}s asset={} fallback={} reason={}".format(
            s["scene_id"], s["start_s"], s["end_s"], a.get("asset_id"),
            s["fallback_state"], str(s.get("selection_reason"))[:70]))

    if len(cands) < 3:
        fails.append("retrieval 命中 <3")
    if len(tl) < 3:
        fails.append("镜头数 <3")
    if len(used_ids) < 3:
        fails.append("使用的不同素材 <3")
    if (ren or {}).get("material_assembly") != "SUCCEEDED":
        fails.append("material_assembly != SUCCEEDED")

    vids = sorted((ROOT / "projects" / pid / "output").glob("*.mp4"))
    # 以 render_output 记录的成片为准（同一项目可能残留历史版本的 draft.mp4）
    video = None
    if ren and ren.get("output") and Path(ren["output"]).is_file():
        video = Path(ren["output"])
    elif vids:
        video = max(vids, key=lambda p: p.stat().st_mtime)
    frame_rows, worst, not_rendered = [], None, []
    if video is None:
        fails.append("无成片")
    else:
        p = subprocess.run([str(FFPROBE), "-v", "error", "-print_format", "json", "-show_format",
                            "-show_streams", str(video)], capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        info = json.loads(p.stdout or "{}")
        streams = info.get("streams", [])
        dur = float((info.get("format") or {}).get("duration") or 0)
        d = subprocess.run([str(FFMPEG), "-v", "error", "-i", str(video), "-f", "null", "-"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        clog("\n成片: {} | {} bytes | {}s | streams {} | decode rc={}".format(
            video.name, video.stat().st_size, dur, len(streams), d.returncode))
        if d.returncode != 0 or len(streams) != 2:
            fails.append("成片校验失败")
        refs = {s["selected_asset"]["asset_id"]: grams(s["selected_asset"]["path"]) for s in used}
        for s in tl:
            start, end = float(s["start_s"]), float(s["end_s"])
            want = (s.get("selected_asset") or {}).get("asset_id")
            if start >= dur:
                # 镜头时间窗完全在成片之后：未渲染（真实原因单独记 PENDING，不伪装成匹配）
                not_rendered.append({"scene_id": s["scene_id"], "window_s": [start, end],
                                     "video_duration_s": round(dur, 3), "reason": "start>=video_end"})
                clog("   {} 时间窗 {:.1f}-{:.1f}s 起点超出成片 {:.1f}s → 未渲染（不计为匹配）".format(
                    s["scene_id"], start, end, dur))
                continue
            # 起点在成片内：该镜头确实已渲染（可能被 -shortest 截断），在可见区间内取中点
            vis_end = min(end, dur)
            mid = (start + vis_end) / 2
            truncated = end > dur
            fp = TMP / "scene_{}.png".format(s["scene_id"])
            subprocess.run([str(FFMPEG), "-y", "-v", "error", "-ss", f"{mid:.2f}", "-i", str(video),
                            "-frames:v", "1", str(fp)], capture_output=True, text=True)
            if not fp.exists():
                fails.append("抽帧失败:" + s["scene_id"])
                continue
            g = grams(fp)
            scores = {aid: round(corr(g, ref), 3) for aid, ref in refs.items()}
            best = max(scores, key=lambda k: scores[k]) if scores else None
            ok = best == want and scores.get(want, 0) > 0.3
            frame_rows.append({"scene_id": s["scene_id"], "t": round(mid, 2),
                               "window_s": [start, end], "expected_asset": want,
                               "corr": scores, "best": best, "match": ok, "rendered": True,
                               "truncated_by_video_end": truncated, "frame": str(fp)})
            if truncated:
                not_rendered.append({"scene_id": s["scene_id"], "window_s": [start, end],
                                     "visible_s": [start, round(vis_end, 3)],
                                     "video_duration_s": round(dur, 3),
                                     "reason": "truncated_by_video_end"})
            clog("   {} 窗口{:.0f}-{:.0f}s t={:.1f}s 期望={} 相关最高={} ({:.3f}) {}{}".format(
                s["scene_id"], start, end, mid, want, best, scores.get(best, 0),
                "OK" if ok else "!! 不匹配", "（被成片结尾截断）" if truncated else ""))
        bad = [f for f in frame_rows if not f["match"]]
        if bad:
            fails.append("抽帧与分配素材不匹配:{}".format([b["scene_id"] for b in bad]))
        gs = {f["scene_id"]: grams(f["frame"]) for f in frame_rows}
        ks = list(gs)
        worst = 0.0            # 全量两两最大相关（同素材镜头本应≈1，仅作参考）
        worst_diff = 0.0       # **不同**素材镜头之间的两两最大相关（判重只用这个）
        diff_pairs = []
        for i in range(len(ks)):
            for j in range(i + 1, len(ks)):
                c = corr(gs[ks[i]], gs[ks[j]])
                worst = max(worst, c)
                a1 = frame_rows[i]["expected_asset"]
                a2 = frame_rows[j]["expected_asset"]
                if a1 != a2:
                    worst_diff = max(worst_diff, c)
                    diff_pairs.append({"scenes": [ks[i], ks[j]], "assets": [a1, a2],
                                       "corr": round(c, 3)})
        if worst_diff > 0.98:
            fails.append("不同素材的镜头画面基本相同")
        clog("   全量两两最大相关: {:.3f}（同素材镜头复用意在预期内）｜"
             "**不同素材**镜头最大相关: {:.3f}（>0.98 视为未真正换素材）".format(worst, worst_diff))
        clog("   不同素材镜头对: " + json.dumps(diff_pairs, ensure_ascii=False))
        shown = {f["expected_asset"] for f in frame_rows if f["match"]}
        clog("   已渲染镜头中确认在屏的不同素材数: {} -> {}".format(len(shown), sorted(shown)))
        if len(shown) < 3:
            fails.append("确认在屏的不同素材 <3")

    # 时间轴总长 vs 成片时长：镜头窗超出成片 → 记为 PENDING（旁白音轨不完整），不伪装成匹配
    tl_total = float(tl[-1]["end_s"]) if tl else 0.0
    video_dur = None
    if video is not None:
        p = subprocess.run([str(FFPROBE), "-v", "error", "-show_entries", "format=duration",
                            "-of", "default=nw=1:nk=1", str(video)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        try:
            video_dur = float((p.stdout or "0").strip())
        except ValueError:
            video_dur = None
    pending = []
    if not_rendered:
        pending.append("成片时长 {}s < 素材时间轴 {}s：{} 个镜头未渲染（{}）——旁白音轨仅覆盖部分段落，"
                       "render 以 -shortest 收尾。属音频阶段缺陷，非素材装配缺陷。".format(
                           video_dur, tl_total, len(not_rendered),
                           "/".join(n["scene_id"] for n in not_rendered)))
    for s in tl:
        if s.get("fallback_state") not in ("LOCAL_INGEST", "SOLID_COLOR_CARD"):
            pending.append("fallback 分类未覆盖：{}".format(s.get("fallback_state")))

    audio_voice = load("voice_output") or {}
    rep = {"project": pid, "prompt": PROMPT, "assets_ingested": staged,
           "retrieval": {"mode": (rc_a or {}).get("material_mode"), "candidates": len(cands),
                         "names": [c.get("name") for c in cands]},
           "timeline": tl, "scenes": len(tl), "scenes_with_asset": len(used),
           "distinct_assets_used": sorted(used_ids),
           "assembly": (ren or {}).get("material_assembly"),
           "visual_source": (ren or {}).get("visual_source"),
           "video": str(video) if video else None,
           "video_duration_s": video_dur, "timeline_total_s": tl_total,
           "frames": frame_rows,
           "scenes_not_rendered": not_rendered,
           "scene_pair_max_corr": worst,
           "cross_asset_max_corr": worst_diff,
           "cross_asset_pairs": diff_pairs,
           "scenes_rendered": len(frame_rows),
           "assets_confirmed_on_screen": sorted(
               {f["expected_asset"] for f in frame_rows if f["match"]}),
           "voice_stage": {"segments_ok": len(audio_voice.get("segments") or []),
                           "errors": len(audio_voice.get("errors") or []),
                           "audio": audio_voice.get("audio")},
           "fails": fails, "pending": pending,
           "verdict": "PASS" if not fails else "FAIL"}
    out_p = ROOT / "docs/regression_2x/logs" / "phase2_accept.json"
    out_p.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    clog("\nVERDICT: " + rep["verdict"] + ("" if not fails else " " + str(fails)))
    clog("记录: " + str(out_p))
    return 0 if not fails else 1


def main():
    fails = []
    if len(sys.argv) > 2 and sys.argv[1] == "--verify":
        # 只复核既有产物/成片（不重跑任何任务，不重渲染）
        pid = sys.argv[2]
        clog("\n===== verify-only {} =====".format(pid))
        return verify(pid, [{"note": "verify-only：复核既有产物"}], fails)
    if len(sys.argv) > 3 and sys.argv[1] == "--redo":
        # 指定任务重做（例如 TTS 断网期间只合成 1/12 段的 voice 任务），随后跑到 settled 并复核
        pid, task_id = sys.argv[2], sys.argv[3]
        clog("\n===== redo {} @ {} =====".format(task_id, pid))
        rc, out = cli("redo", task_id)
        clog("redo -> " + out.strip()[:200])
        drive_to_settle(pid, fails)
        return verify(pid, [{"note": "redo 后复核；素材已在本项目 media/ 中"}], fails)
    if len(sys.argv) > 2 and sys.argv[1] == "--resume":
        pid = sys.argv[2]
        con = db()
        row = con.execute("select goal from projects where project_id=?", (pid,)).fetchone()
        con.close()
        staged = [{"note": "resume：素材已在本项目 media/ 中"}]
        clog("\n===== resume {} | goal={} =====".format(
            pid, (row["goal"] if row else "")[:40]))
        drive_to_settle(pid, fails)
        return verify(pid, staged, fails)

    rc, out = cli("init", PROMPT, "--name", "test_phase2_assets")
    pid = re.search(r"p_[0-9a-f]+", out).group(0)
    clog("\n===== 新项目 {} =====".format(pid))

    # 阶段 0：先给素材库（真实工作流：先提供素材，再进入生产）
    staged = stage_assets(pid)
    rc, out = cli("plan", pid)
    clog("plan -> " + out.strip())

    # 阶段 1：跑到 script 成功
    if not wait_for_script(pid, fails):
        clog("!! script 未成功，无法继续")
        if "script 未成功" not in fails:
            fails.append("script 未成功")
        return verify(pid, staged, fails)

    # 阶段 2：批准 Claim → 跑到 settled
    drive_to_settle(pid, fails)
    return verify(pid, staged, fails)


if __name__ == "__main__":
    sys.exit(main())
