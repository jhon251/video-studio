"""Local ingest regression (3.x-Preflight item 4; expectation updated in 3.x Phase 2-A/B).

Creates project D, ingests two local images, then runs the standard pipeline and asserts:
  asset_index.material_mode == local_ingest
  retrieval_candidates.material_mode == local_ingest and candidates_total > 0
  render_output.material_assembly == SUCCEEDED
  if any timeline scene got an asset -> visual_source == material_timeline
  (no asset hit at all -> ingested_material_background / solid_color_subtitle_card)
  draft.mp4 exists and is probed by the REAL ffprobe (2 streams)

Usage: python docs/regression_2x/run_ingest_test.py
"""
import json
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
LOGS = ROOT / "docs" / "regression_2x" / "logs"
LOGS.mkdir(parents=True, exist_ok=True)
FFPROBE = ROOT / "bin" / "ffprobe.exe"
PROMPT = "本地素材 ingest 回归测试：做一期鲸鱼娘皮肤演示视频。"
PREFIX = "D"


def log(m):
    print(m, flush=True)
    with (LOGS / "D_ingest_loop.log").open("a", encoding="utf-8") as fh:
        fh.write(str(m) + "\n")


MOCK_CFG = "config/config.mock.json"   # 5-L：离线用例**显式**指定 mock 配置（生产默认不含 llm.mock）

# ---------------- 6-A/M2：本用例改用「配音计划模式」--------------
# 背景：mock 脚本计划 15 s/段，而真实 TTS 对该文本只产出约 4.2 s ⇒ 成片在 17 s 时间轴里会留下
# 约 13 s 尾静音（实测见 logs/phase6a_m2_shortfilm_probe.json：同类历史成片尾静音 13.26 s/78%）。
# 这正是 6-A/M2 授权点名的「短旁白 / 成片静音」违约类，渲染前硬门按设计会阻断它。
# 本用例验证的是 **本地素材 ingest → 素材时间轴装配 → 成片** 这条链路，与旁白完整性无关；
# 故在**临时配置**（不改基线 config/config.mock.json）里把 TTS provider 设为 none，
# 走产线既有的「配音计划模式」：编辑侧仍真实渲染、真实抽帧核验，
# 旁白完整性由 narration_contract / audio_loudness / bgm_ducking / integrity_gates /
# phase3a_real_chain 等专门用例与证据步骤覆盖。
_CFG_TMP = Path(tempfile.mkdtemp(prefix="vs_ingest_cfg_")) / "config.mock.planonly.json"
_cfg = json.loads((ROOT / MOCK_CFG).read_text(encoding="utf-8"))
_cfg.setdefault("tools", {}).setdefault("tts", {})["provider"] = "none"
_CFG_TMP.write_text(json.dumps(_cfg, ensure_ascii=False, indent=1), encoding="utf-8")
MOCK_CFG = str(_CFG_TMP)


def cli(*a):
    p = subprocess.run([sys.executable, "run.py", "--config", MOCK_CFG, *a], cwd=str(ROOT),
                       capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def rows(text, ch):
    return [[c.strip() for c in ln.split("|")] for ln in text.splitlines()
            if re.match(r"^\|\s*" + ch, ln)]


# ---- 1. temp media dir: two renamed local images matching the mock content keywords
src_dir = ROOT / "output" / "run03" / "asset_cache" / "files"
cands = sorted(src_dir.glob("*.jpg"))[:2] or sorted(src_dir.glob("*.png"))[:2]
assert cands, "no source image found under output/run03/asset_cache/files"
tmp = Path(tempfile.mkdtemp(prefix="vstudio_ingest_"))
names = ["鲸鱼娘皮肤界面截图_01" + cands[0].suffix, "鲸鱼娘皮肤展示_02" + cands[0].suffix]
for c, n in zip(cands, names):
    shutil.copy2(c, tmp / n)
log("ingest 源目录: {} -> {}".format(tmp, names))

# ---- 2. init + ingest + plan
rc, out = cli("init", PROMPT, "--name", "testD_ingest")
pid = re.search(r"p_[0-9a-f]+", out).group(0)
log("init -> {} ({})".format(pid, out.strip()))
rc, out = cli("ingest", pid, str(tmp))
log("ingest -> " + out.strip())
rc, out = cli("plan", pid)
log("plan -> " + out.strip())

# ---- 3. drive run + approvals + claim gate
redone = set()
for i in range(1, 41):
    rc, cl = cli("claims", pid)
    for f in rows(cl, "c_"):
        if len(f) >= 9 and f[7]:
            rc2, o2 = cli("approve-claim", f[1], "--comment", "3.x-preflight ingest test")
            log("  approve-claim {} -> {}".format(f[1], o2.strip().splitlines()[-1][:60]))
    rc, st = cli("status", pid)
    (LOGS / "D_status_r{}.log".format(i)).write_text(st, encoding="utf-8")
    review, blocked, active, ok = [], [], 0, 0
    for f in rows(st, "t_"):
        if len(f) < 6:
            continue
        if f[4] == "NEEDS_REVIEW":
            review.append(f[1])
        elif f[4] in ("PENDING", "READY", "RUNNING", "DISPATCHED"):
            active += 1
        elif f[4] == "SUCCEEDED":
            ok += 1
        elif f[4] in ("BLOCKED", "FAILED"):
            blocked.append(f[1])
    log("[round {}] succeeded={} review={} active={} blocked={}".format(i, ok, len(review), active, len(blocked)))
    if review:
        for t in review:
            cli("approve", t, "approve", "--comment", "3.x-preflight")
        continue
    if blocked:
        for t in blocked:
            if t not in redone:
                redone.add(t)
                cli("redo", t)
        continue
    if active == 0:
        log("  settled")
        break
    rc, o2 = cli("run", pid)
    log("  run -> " + o2.strip().splitlines()[-1][:60])

# ---- 4. assertions on artifacts
con = sqlite3.connect(str(ROOT / "projects" / "video_studio.db"))
con.row_factory = sqlite3.Row
arts = {}
for r in con.execute("select * from artifacts where project_id=?", (pid,)):
    arts.setdefault(r["type"], []).append(dict(r))
con.close()

def payload(atype):
    lst = arts.get(atype) or []
    if not lst:
        return None
    return json.loads(Path(lst[-1]["path"]).read_text(encoding="utf-8"))

fails = []
ai, rc_, ro = payload("asset_index"), payload("retrieval_candidates"), payload("render_output")
log("\n--- artifact assertions ---")
log("asset_index.files={} material_mode={} providers={}".format(
    len((ai or {}).get("files", [])), (ai or {}).get("material_mode"), (ai or {}).get("material_providers")))
log("retrieval.material_mode={} candidates_total={} query_source={} query={}".format(
    (rc_ or {}).get("material_mode"), (rc_ or {}).get("candidates_total"),
    (rc_ or {}).get("query_source"), str((rc_ or {}).get("query"))[:60]))
log("render.visual_source={} material_mode={} material_candidates={} material_assembly={} "
    "scenes={} scenes_with_asset={}".format(
        (ro or {}).get("visual_source"), (ro or {}).get("material_mode"),
        (ro or {}).get("material_candidates"), (ro or {}).get("material_assembly"),
        (ro or {}).get("scene_count"), (ro or {}).get("scenes_with_asset")))
if not ai or ai.get("material_mode") != "local_ingest" or len(ai.get("files", [])) < 2:
    fails.append("asset_index 未标记 local_ingest 或文件数不足")
if not rc_ or rc_.get("material_mode") != "local_ingest" or (rc_.get("candidates_total") or 0) < 1:
    fails.append("retrieval 未匹配到本地素材候选")
# 3.x Phase 2-A/B：有素材时按**素材时间轴**逐镜头装配（visual_source=material_timeline），
# 无素材才退回 ingested_material_background / solid_color_subtitle_card。
tl = (ro or {}).get("material_timeline") or []
tl_with_asset = [s for s in tl if s.get("selected_asset")]
if not ro or ro.get("material_assembly") != "SUCCEEDED":
    fails.append("render 未实现素材装配（期望 material_assembly=SUCCEEDED）")
elif tl_with_asset:
    if ro.get("visual_source") != "material_timeline":
        fails.append("有素材命中时 visual_source 应为 material_timeline，实际 "
                     + str(ro.get("visual_source")))
    # 镜头数取决于 mock 脚本段数（可能只有 1 段），因此只要求「≥1 镜头且 ≥1 素材已装配」
    if len(tl) < 1 or len({s["selected_asset"]["asset_id"] for s in tl_with_asset}) < 1:
        fails.append("素材时间轴镜头/素材数不足")
else:
    if ro.get("visual_source") not in ("ingested_material_background",
                                       "solid_color_subtitle_card"):
        fails.append("无素材命中时 visual_source 应为背景/纯色底，实际 "
                     + str(ro.get("visual_source")))
if ro and ro.get("material_mode") != "local_ingest":
    fails.append("render 未继承 material_mode=local_ingest")
if ro and tl_with_asset and not ro.get("assets_used"):
    fails.append("assets_used 缺失（时间轴素材未登记）")

# ---- 5. video probe with the real ffprobe
vids = sorted((ROOT / "projects" / pid / "output").glob("*.mp4"))
log("\n--- video ---")
if not vids:
    fails.append("无成片")
else:
    v = vids[-1]
    p = subprocess.run([str(FFPROBE), "-v", "error", "-print_format", "json",
                        "-show_format", "-show_streams", str(v)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    info = json.loads(p.stdout or "{}")
    streams = info.get("streams", [])
    log("{} {} bytes streams={} duration={}".format(v.name, v.stat().st_size, len(streams),
                                                    (info.get("format") or {}).get("duration")))
    for s in streams:
        log("   {} {} {}x{} sr={} ch={}".format(s.get("codec_type"), s.get("codec_name"),
                                                s.get("width"), s.get("height"),
                                                s.get("sample_rate"), s.get("channels")))
    if len(streams) != 2:
        fails.append("成片流数 != 2")

# ---- 6. 3.x Phase 2-A/B：抽帧证明「成片里出现的确实是时间轴分配的素材」（免费、确定性）
if vids and tl_with_asset:
    import numpy as np
    from PIL import Image

    ffmpeg = str(ROOT / "bin" / "ffmpeg.exe")

    def grams(p):
        return np.asarray(Image.open(p).convert("L").resize((48, 48)), dtype=np.float64)

    def corr(a, b):
        a, b = a - a.mean(), b - b.mean()
        d = float(np.sqrt((a ** 2).sum()) * np.sqrt((b ** 2).sum()))
        return float((a * b).sum() / d) if d else 0.0

    dur = float((info.get("format") or {}).get("duration") or 0)
    refs = {s["selected_asset"]["asset_id"]: grams(s["selected_asset"]["path"])
            for s in tl_with_asset}
    tmp_frames = Path(tempfile.mkdtemp(prefix="vstudio_frames_"))
    log("\n--- 抽帧核验（成片 vs 时间轴素材）---")
    checked = 0
    for s in tl:
        if not s.get("selected_asset"):
            continue
        start, end = float(s["start_s"]), float(s["end_s"])
        if start >= dur:
            log("   {} 时间窗 {:.1f}-{:.1f}s 起点超出成片 {:.2f}s → 未渲染".format(
                s["scene_id"], start, end, dur))
            continue
        # 起点在成片内 → 该镜头确实已渲染（可能被 -shortest 截断）；在可见区间取中点
        vis_end = min(end, dur)
        mid = (start + vis_end) / 2
        fp = tmp_frames / "{}.png".format(s["scene_id"])
        subprocess.run([ffmpeg, "-y", "-v", "error", "-ss", "{:.2f}".format(mid),
                        "-i", str(v), "-frames:v", "1", str(fp)],
                       capture_output=True, text=True)
        if not fp.exists():
            fails.append("抽帧失败:" + s["scene_id"])
            continue
        g = grams(fp)
        scores = {aid: round(corr(g, ref), 3) for aid, ref in refs.items()}
        want = s["selected_asset"]["asset_id"]
        best = max(scores, key=lambda k: scores[k])
        ok = best == want and scores.get(want, 0) > 0.3
        checked += 1
        log("   {} 窗口{:.0f}-{:.0f}s t={:.1f}s 期望={} 最高={} ({:.3f}) {}".format(
            s["scene_id"], start, end, mid, want, best, scores.get(best, 0),
            "OK" if ok else "!! 不匹配"))
        if not ok:
            fails.append("抽帧与分配素材不匹配:" + s["scene_id"])
    if checked == 0:
        fails.append("没有任何镜头落在成片时长内，无法抽帧核验")

log("\nVERDICT: " + ("PASS" if not fails else "FAIL -> " + str(fails)))
(LOGS / "D_ingest_result.json").write_text(json.dumps(
    {"project": pid, "asset_index": ai, "retrieval": rc_, "render": ro,
     "video": str(vids[-1]) if vids else None, "fails": fails,
     "verdict": "PASS" if not fails else "FAIL"}, ensure_ascii=False, indent=1), encoding="utf-8")
sys.exit(1 if fails else 0)
