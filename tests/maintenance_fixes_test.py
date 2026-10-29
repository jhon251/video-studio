"""5.x Phase 5-K 单测：Post-Final Maintenance（正式纳入 3 项既有改动 + 修正 + 反证 + 守卫）。

覆盖授权要求（只做这 10 项，不新增视频能力，不改 Judge/truth set/threshold/multimodal/human chain）：
  M1 源码级：`agents/editing/agent.py` 静态图输入 = 1fps 取帧 + **每段 `trim=duration=d` 精确裁切**
     （5-K 审计发现原 `-framerate 1` 形态会让每镜短 ~1s → 已修正并在此断言修复形态）
  M2 **反证（真实 ffmpeg，段落级）**：整数与**小数** d 下，段视频时长 == d（±0.05）
  M3 **反证（真实 ffmpeg，片级）**：3 段装配（含小数时长）→ **视频轨时长 == 时间轴总长**（±0.1）
     —— 这条断言正是能捕获"每镜短 1s、整片视频轨短 21s"缺陷的回归
  M4 **反证（真实 ffmpeg）：视频输入路径不受影响** —— 视频素材走 raw op 时不带 `-framerate`/`-loop`，
     且时长/fps/帧数与源一致
  M5 `tools/ffmpeg_tool.py` 两处 timeout 均为 **7200s**（raw + render），无 1800s 残留；其它 op 超时未动
  M6 默认配置 = **当前官方模型**：M/F=`deepseek-flash`（DeepSeek-V4.1-Flash）、R=`deepseek-v4-pro`；
     价格表覆盖；历史别名不再是默认目标
  M7 杂物清理：`config/config.mock.json.bak` 不存在；`config/` 无 `*.bak/*.tmp/*.orig`；隔离目录有清单
  M8 禁止项守卫：Judge / truth set / threshold / multimodal evaluator / human decision chain
     与 `5.x-final-baseline` 逐字节一致；该基线本体未被改写

用法：python tests/maintenance_fixes_test.py
"""
import hashlib
import json
import pathlib
import re
import subprocess
import sys
import tempfile
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.llm.router import (CURRENT_OFFICIAL_MODELS, DEFAULT_PRICING,  # noqa: E402
                                     LEGACY_MODEL_IDS, compute_cost)
from video_studio.tools.base import ToolContext  # noqa: E402
from video_studio.tools.ffmpeg_tool import FFmpegTool  # noqa: E402

FINAL_ZIP = ROOT / "docs" / "regression_2x" / "baseline" / "5.x-final-baseline.zip"
FINAL_MAN = (ROOT / "docs" / "regression_2x" / "baseline" /
             "baseline_manifest_5.x-final-baseline.json")
FINAL_SHA = "be1717b9c7fe9ed9124be3876db64b5893915a4d0ffad56bd37eded5e6e2141e"
CFG = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8-sig"))
FFMPEG = CFG["tools"]["ffmpeg"]["path"]
FFPROBE = CFG["tools"]["ffmpeg"]["ffprobe"]
PASS, FAIL = [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print(("PASS  " if ok else "FAIL  ") + name + (" | " + str(detail)[:230] if detail else ""))


def sha(p):
    try:
        return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
    except OSError:
        return None


def probe(p):
    r = subprocess.run([FFPROBE, "-v", "error", "-print_format", "json", "-show_format",
                        "-show_streams", str(p)], capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    d = json.loads(r.stdout or "{}")
    v = next((s for s in d.get("streams") or [] if s.get("codec_type") == "video"), {})
    return {"fmt": round(float((d.get("format") or {}).get("duration") or 0), 3),
            "v": round(float(v.get("duration") or 0), 3),
            "frames": int(v.get("nb_frames") or 0), "fps": v.get("avg_frame_rate"),
            "r_fps": v.get("r_frame_rate"), "codec": v.get("codec_name")}


AGENT_SRC = (ROOT / "src" / "video_studio" / "agents" / "editing" / "agent.py").read_text(
    encoding="utf-8")
TOOL_SRC = (ROOT / "src" / "video_studio" / "tools" / "ffmpeg_tool.py").read_text(encoding="utf-8")
ROUTER_SRC = (ROOT / "src" / "video_studio" / "llm" / "router.py").read_text(encoding="utf-8")

# ============ M1 源码级（修复形态） ============
print("== M1 静态图输入：1fps 取帧 + 每段精确 trim（5-K 修正后的正式形态） ==")
img_block = AGENT_SRC.split('if sc.get("selected_asset"):', 1)[1].split("else:", 1)[0]
check("M1a 图片输入使用 `-loop 1 -framerate 1`（1fps 取帧，解码量 ~d 帧而非 25·d 帧）",
      '"-loop", "1", "-framerate", "1"' in img_block
      and AGENT_SRC.count("-framerate") >= 1, img_block.strip().splitlines()[-2:])
check("M1b 输入 `-t` = `ceil(d)+2`（保证 1fps 源足够覆盖 d 秒；原形态取 d 会短 ~1s）",
      "math.ceil(d)) + 2.0" in img_block and "src_t" in img_block,
      [l.strip() for l in img_block.splitlines() if "src_t" in l])
check("M1c 每段滤镜含 `fps,trim=duration=d,setpts=PTS-STARTPTS`（段长精确 = d，含小数）",
      "trim=duration={d:.3f}" in AGENT_SRC and "setpts=PTS-STARTPTS[v{i}]" in AGENT_SRC,
      [l.strip()[:90] for l in AGENT_SRC.splitlines() if "trim=duration=" in l])
check("M1d 旧的缺陷形态（图片输入直接 `-t d`、无 trim）已不存在",
      '"-framerate", "1", "-t", f"{d:.3f}", "-i"' not in AGENT_SRC)
check("M1e 纯色底分支未受影响（仍是 `-f lavfi -t d`，且滤镜同样被 trim 规范到 d）",
      '"-f", "lavfi", "-t", f"{d:.3f}"' in AGENT_SRC)
check("M1f `-framerate` 未泄漏到 tools/、core/、stage32b/（不出现于图片装配之外）",
      all("-framerate" not in p.read_text(encoding="utf-8", errors="replace")
          for p in list((ROOT / "src" / "video_studio" / "tools").rglob("*.py"))
          + list((ROOT / "src" / "video_studio" / "core").rglob("*.py"))
          + list((ROOT / "src" / "video_studio" / "stage32b").rglob("*.py"))))

# ============ 真实 ffmpeg 夹具 ============
tmp = pathlib.Path(tempfile.mkdtemp(prefix="vs_5k_"))
img_a, img_b = tmp / "a.png", tmp / "b.png"
subprocess.run([FFMPEG, "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=0x204060:size=640x360",
                "-frames:v", "1", str(img_a)], capture_output=True)
subprocess.run([FFMPEG, "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=0x602040:size=640x360",
                "-frames:v", "1", str(img_b)], capture_output=True)
tool = FFmpegTool()
ctx = ToolContext(role="editing", project_id="p_test", project_dir=tmp, db=None,
                  config={"tools": {"ffmpeg": {"path": FFMPEG, "ffprobe": FFPROBE}}})


def image_segment_args(d, img, fps=30, tw=640, th=360):
    """**逐字复刻**当前 agent.py 中图片分支的参数形态（输入 + 该段滤镜）= S4 修正形态。"""
    import math as _m
    src_t = float(_m.ceil(d)) + 2.0
    inputs = ["-loop", "1", "-framerate", "1", "-t", f"{src_t:.3f}", "-i", str(img)]
    filt = (f"[0:v]scale={tw}:{th}:force_original_aspect_ratio=increase,"
            f"crop={tw}:{th},setsar=1,fps={fps},trim=duration={d:.3f},setpts=PTS-STARTPTS[v0]")
    return inputs, filt


SEG_FILTER_S0 = ("[0:v]scale=640:360:force_original_aspect_ratio=increase,"
                 "crop=640:360,setsar=1,fps=30[v0]")


def run_segment(shape, d, out):
    """三种形态同条件渲染：S0=冻结基线 / S1=post-final 漂移 / S4=5-K 修正。"""
    if shape == "S4":
        ins, filt = image_segment_args(d, img_a)
    elif shape == "S1":  # post-final 漂移形态：加了 -framerate 1 但仍按 d 取源、无 trim
        ins = ["-loop", "1", "-framerate", "1", "-t", f"{d:.3f}", "-i", str(img_a)]
        filt = SEG_FILTER_S0
    elif shape == "S0":  # 冻结 5.x Final 形态：默认 25fps 循环源 + 无 trim
        ins = ["-loop", "1", "-t", f"{d:.3f}", "-i", str(img_a)]
        filt = SEG_FILTER_S0
    else:
        raise ValueError(shape)
    tool.execute({"op": "raw", "args": [*ins, "-filter_complex", filt, "-map", "[v0]",
                                        "-c:v", "libx264", "-pix_fmt", "yuv420p",
                                        "-t", f"{d:.3f}"], "output": str(out)}, ctx)
    return probe(out) if out.is_file() else {}


# 冻结基线内的原始形态（证据取自 ZIP 本体，非记忆）
BASE_ZIP = ROOT / "docs" / "regression_2x" / "baseline" / "5.x-final-baseline.zip"
import zipfile as _zf
with _zf.ZipFile(BASE_ZIP) as _z:
    BASE_AGENT = _z.read("src/video_studio/agents/editing/agent.py").decode("utf-8")
check("M2a 冻结基线（5.x-final-baseline）内图片分支 = S0 形态（无 `-framerate`、无 `trim`）",
      '"-loop", "1", "-t", f"{d:.3f}", "-i"' in BASE_AGENT
      and "-framerate" not in BASE_AGENT and "trim=duration" not in BASE_AGENT,
      [l.strip()[:88] for l in BASE_AGENT.splitlines() if '"-loop", "1"' in l])

print("\n== M2 反证（真实 ffmpeg，段落级）：S0 冻结形态 / S1 漂移形态 / S4 修正形态 同条件对比 ==")
rows = []
for d in (2.0, 2.5, 20.0, 73.4):
    got = {s: run_segment(s, d, tmp / f"seg_{s}_{d}.mp4") for s in ("S0", "S1", "S4")}
    want_frames = round(d * 30)
    ok_frames = got["S4"].get("frames") == want_frames and got["S4"].get("r_fps") == "30/1"
    ok_s0 = bool(got["S0"]) and abs(got["S4"]["v"] - got["S0"]["v"]) <= 0.02
    ok_s1 = bool(got["S1"]) and (got["S0"]["v"] - got["S1"]["v"]) >= (0.9 if d == int(d) else 0.4)
    rows.append({"d": d, "want_frames": want_frames,
                 "S0": got["S0"].get("v"), "S1": got["S1"].get("v"), "S4": got["S4"].get("v"),
                 "S4_frames": got["S4"].get("frames"), "S4_r_fps": got["S4"].get("r_fps"),
                 "ok_frames": ok_frames, "ok_s0": ok_s0, "ok_s1": ok_s1,
                 "delta_s0": round(got["S4"]["v"] - got["S0"]["v"], 3) if got["S0"] else None,
                 "short_s1": round(got["S0"]["v"] - got["S1"]["v"], 3) if got["S0"] else None})
    print("   d={:<6} S0={:<8} S1={:<8} S4={:<8} frames={}/{} r_fps={} Δ(S4-S0)={} S1短={}".format(
        d, got["S0"].get("v"), got["S1"].get("v"), got["S4"].get("v"), got["S4"].get("frames"),
        want_frames, got["S4"].get("r_fps"), rows[-1]["delta_s0"], rows[-1]["short_s1"]))
check("M2b 修正形态帧数精确 = round(d·30)（2.0/2.5/20.0/73.4 → 60/75/600/2202），标称率 30/1",
      all(x["ok_frames"] for x in rows), rows)
check("M2c 修正形态时长 == 冻结基线 S0 时长（±0.02）—— 语义与 5.x Final 一致，不引入时长变化",
      all(x["ok_s0"] for x in rows), rows)
check("M2d **漂移形态 S1 每段被静默截短**（整数 d ≥0.9s；小数 d ≥0.4s，取决于 floor(d) 帧数）",
      all(x["ok_s1"] for x in rows), rows)

print("\n== M3 反证（真实 ffmpeg，片级）：视频轨时长 == 时间轴总长 ==")
D = [7.0, 5.5, 9.25]
TOTAL = round(sum(D), 3)
film = tmp / "film.mp4"
film_s1 = tmp / "film_s1.mp4"
narration = tmp / "narr.m4a"
subprocess.run([FFMPEG, "-y", "-v", "error", "-f", "lavfi", "-i",
                f"sine=frequency=220:duration={TOTAL:.3f}", "-c:a", "aac", str(narration)],
               capture_output=True)


def build_film(shape, out):
    """S4=当前修正形态；S1=post-final 漂移形态（`-framerate 1 -t d`、无 trim）。"""
    ins, filts = [], []
    for i, (d, im) in enumerate(zip(D, (img_a, img_b, img_a))):
        if shape == "S4":
            src_t = float(__import__("math").ceil(d)) + 2.0
            ins += ["-loop", "1", "-framerate", "1", "-t", f"{src_t:.3f}", "-i", str(im)]
            filts.append(f"[{i}:v]scale=640:360:force_original_aspect_ratio=increase,crop=640:360,"
                         f"setsar=1,fps=30,trim=duration={d:.3f},setpts=PTS-STARTPTS[v{i}]")
        else:
            ins += ["-loop", "1", "-framerate", "1", "-t", f"{d:.3f}", "-i", str(im)]
            filts.append(f"[{i}:v]scale=640:360:force_original_aspect_ratio=increase,crop=640:360,"
                         f"setsar=1,fps=30[v{i}]")
    ins += ["-i", str(narration)]
    filts.append("".join(f"[v{i}]" for i in range(len(D))) + f"concat=n={len(D)}:v=1:a=0[vc]")
    filts.append("[vc]format=yuv420p[vout]")
    filts.append(f"[{len(D)}:a]apad[aout]")
    r = tool.execute({"op": "raw", "args": [*ins, "-filter_complex", ";".join(filts),
                                            "-map", "[vout]", "-map", "[aout]",
                                            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a",
                                            "aac", "-t", f"{TOTAL:.3f}"], "output": str(out)},
                     ctx)
    return (probe(out) if out.is_file() else {}), r


fp, r_film = build_film("S4", film)
fp1, _ = build_film("S1", film_s1)
check("M3a 三段装配（7.0+5.5+9.25=21.75s）产出可解码成片，容器时长 == 时间轴总长",
      bool(fp) and abs(fp["fmt"] - TOTAL) <= 0.15 and fp["codec"] == "h264",
      {"expect": TOTAL, "got": fp})
check("M3b **视频轨时长 == 时间轴总长**（±0.1）",
      bool(fp) and abs(fp["v"] - TOTAL) <= 0.1, {"expect": TOTAL, "video_track": fp.get("v")})
check("M3c 段落累计误差 ≤ 1 帧（逐段 trim 的舍入上限）+ 帧数与时间轴差 ≤1 帧 + 标称 30/1",
      bool(fp) and abs(fp["v"] - TOTAL) <= 1 / 30 + 0.01 and fp["r_fps"] == "30/1"
      and abs(fp["frames"] - TOTAL * 30) <= 1,
      {"expect": TOTAL, "v": fp.get("v"), "frames": fp.get("frames"), "r_fps": fp.get("r_fps"),
       "want_frames": TOTAL * 30})
check("M3d **片级缺陷复现**：漂移形态 S1 视频轨比修正形态短 ≈ 段落数 × 1s（≥2.5s）",
      bool(fp1) and bool(fp) and fp["v"] - fp1["v"] >= 2.5,
      {"S4_video_track": fp.get("v"), "S1_video_track": fp1.get("v"),
       "short_by": round(fp["v"] - fp1["v"], 3) if fp and fp1 else None})

print("\n== M4 反证（真实 ffmpeg）：视频输入路径不受影响 ==")
src_video = tmp / "srcv.mp4"
subprocess.run([FFMPEG, "-y", "-v", "error", "-f", "lavfi", "-i",
                "testsrc=size=640x360:rate=30:duration=3", "-c:v", "libx264", "-pix_fmt",
                "yuv420p", str(src_video)], capture_output=True)
vid_out = tmp / "vid.mp4"
r_v = tool.execute({"op": "raw", "args": ["-i", str(src_video), "-vf", "scale=640:360,fps=30",
                                          "-c:v", "libx264", "-pix_fmt", "yuv420p", "-t", "2.0"],
                    "output": str(vid_out)}, ctx)
vp = probe(vid_out) if vid_out.is_file() else {}
check("M4a 视频输入经 raw op 正常转码（时长 2.0s、30fps、h264）",
      bool(vp) and abs(vp["v"] - 2.0) <= 0.1 and vp["r_fps"] == "30/1" and vp["codec"] == "h264",
      vp)
check("M4b 视频路径命令中无 `-framerate` / `-loop`（图片专用参数未泄漏）",
      "-framerate" not in json.dumps(getattr(r_v, "data", {}) or {}, ensure_ascii=False)
      and "-loop" not in json.dumps(getattr(r_v, "data", {}) or {}, ensure_ascii=False),
      sorted((getattr(r_v, "data", {}) or {}).keys())[:5])

print("\n== M5 ffmpeg_tool 超时（两处 7200s，其它未动） ==")
timeouts = sorted(set(int(m) for m in re.findall(r"timeout=(\d+)", TOOL_SRC)))
raw_block = TOOL_SRC.split('if op == "raw":', 1)[1].split('if op == "probe":', 1)[0]
render_block = TOOL_SRC.split('if op == "render":', 1)[1]
check("M5a `raw` 与 `render` 两处 timeout 均为 7200s，且文件中无 1800s",
      TOOL_SRC.count("timeout=7200") == 2 and "timeout=1800" not in TOOL_SRC
      and "timeout=7200" in raw_block and "timeout=7200" in render_block, timeouts)
check("M5b 其它 op 超时未改动（ffprobe 校验=60 / probe=120 / concat=600）",
      60 in timeouts and 120 in timeouts and 600 in timeouts, timeouts)
check("M5c 超时改动不改行为：本用例的图片路径（M2 三形态 / M3 两形态）与视频路径（M4）真实渲染均成功",
      all(x["ok_frames"] and x["ok_s0"] and x["ok_s1"] for x in rows) and bool(fp) and bool(fp1)
      and bool(vp), "见 M2/M3/M4")

print("\n== M6 默认配置 = 当前官方模型（V4.1-Flash 为日常默认） ==")
tiers = CFG["llm"]["tiers"]
check("M6a M/F 档 = `deepseek-flash`（当前官方 DeepSeek-V4.1-Flash）、R 档 = `deepseek-v4-pro`",
      tiers["M"]["model"] == CURRENT_OFFICIAL_MODELS["routine"]
      and tiers["F"]["model"] == CURRENT_OFFICIAL_MODELS["routine"]
      and tiers["R"]["model"] == CURRENT_OFFICIAL_MODELS["reasoning"],
      {k: v.get("model") for k, v in tiers.items()})
check("M6b 价格表覆盖全部档位模型；历史别名一律 unknown_pricing（不猜价）",
      all(t["model"] in CFG["llm"]["pricing"] for t in tiers.values())
      and compute_cost(LEGACY_MODEL_IDS[0], {"cache_miss_tokens": 1000})[1].startswith(
          "unknown_pricing:"),
      {"flash_cost": compute_cost("deepseek-flash", {"cache_miss_tokens": 1000})[0]})
check("M6c 历史别名不再是默认目标：router 回退不指向 `deepseek-chat`，且登记为 LEGACY_MODEL_IDS",
      'tier_cfg.get("model", "deepseek-chat")' not in ROUTER_SRC
      and 'CURRENT_OFFICIAL_MODELS["routine"]' in ROUTER_SRC
      and "deepseek-chat" in LEGACY_MODEL_IDS,
      {"legacy": LEGACY_MODEL_IDS})

print("\n== M7 杂物清理（不纳入正式 baseline） ==")
junk_cfg = sorted(p.name for p in (ROOT / "config").glob("*")
                  if p.suffix in (".bak", ".tmp", ".orig", ".old") or p.name.endswith("~"))
check("M7a `config/config.mock.json.bak` 已清理，`config/` 内无备份/临时文件",
      not (ROOT / "config" / "config.mock.json.bak").exists() and not junk_cfg, junk_cfg)
check("M7b 清理留痕：隔离目录含 MANIFEST.json（原路径/sha256 可回溯）",
      (ROOT / "output" / "_quarantine_20260921" / "MANIFEST.json").is_file())

print("\n== M8 禁止项守卫（与 5.x-final-baseline 逐字节一致） ==")
GUARDED = {
    "Judge": ["src/video_studio/core/mm_judge.py", "src/video_studio/ops/mm_judge.py",
              "tests/mm_judge_test.py"],
    "truth_set": ["tests/fixtures/mm_truth_set_v1.json", "tests/fixtures/mm_judge_truth_v1.json"],
    "multimodal_evaluator": ["src/video_studio/core/multimodal.py",
                             "src/video_studio/core/mm_temporal.py",
                             "src/video_studio/core/mm_quality.py",
                             "src/video_studio/ops/multimodal.py",
                             "src/video_studio/ops/mm_temporal.py",
                             "src/video_studio/ops/mm_quality.py",
                             "src/video_studio/core/mm_worker_clip.py"],
    "human_decision_chain": ["src/video_studio/core/selection_review.py",
                             "src/video_studio/ops/selection_review.py"],
    "thresholds": ["src/video_studio/core/audio.py", "src/video_studio/core/materials.py"],
}
man = json.loads(FINAL_MAN.read_text(encoding="utf-8"))
diffs = {g: [f for f in fs if man["files"].get(f, {}).get("sha256") != sha(ROOT / f)]
         for g, fs in GUARDED.items()}
check("M8a Judge / truth set / multimodal evaluator / human decision chain / thresholds 全部未改",
      not any(diffs.values()), diffs)
check("M8b 5.x-final-baseline 本体未被改写（ZIP sha256 == 授权值 == manifest）",
      sha(FINAL_ZIP) == FINAL_SHA and man.get("zip_sha256") == FINAL_SHA,
      (sha(FINAL_ZIP) or "")[:16])
z = zipfile.ZipFile(FINAL_ZIP)
check("M8c 基线内条目数与 manifest 一致（未被增删）",
      len([i for i in z.infolist() if not i.is_dir()]) == man["file_count"], man["file_count"])
# 6-A/M1 **测试契约更新**（不改业务语义）：本守卫的**意图**是"不得新增**视频能力** ops/ 模块"。
# 6-A/M1 经授权新增两个**只读度量**模块（`ops/integrity.py`、`ops/direction.py`）→ 改为：
#   ① 只有**显式白名单**内的只读 metrics/report 模块可新增，其余任何新增 ops/ 模块一律 FAIL（强度不变）；
#   ② 对白名单模块做**只读静态检查**（禁止 DB 写标记、产物写标记、engine/任务派发引用）。
# 6-B/M2 **测试契约更新**：经授权新增 `ops/review.py`（Human Review Bridge 只读编排：读 DQ 报告 +
#   读/追加人工决策台账；不写 DB、不写产物、不派发任务）→ 纳入同一白名单与同一静态检查。
# 6-B/M3 **测试契约更新**：经授权新增 `ops/revision.py`（Revision Proposal 只读编排：读闭环报告 +
#   生成/登记**方案**；不执行任何修改、不写 DB、不写产物）→ 同样纳入白名单与静态检查。
READONLY_OPS_WHITELIST = {"src/video_studio/ops/integrity.py",
                          "src/video_studio/ops/direction.py",
                          "src/video_studio/ops/review.py",
                          "src/video_studio/ops/revision.py",
                          # P7-1（人工授权新增）：VisualRequirement **只读**入口——以
                          # `mode=ro` + `query_only` 只读打开 DB、**不写任何文件**（artifact 落盘在
                          # 阶段脚本 docs/regression_2x/phase7_p7_1_build.py）、无网络、无 LLM 调用。
                          "src/video_studio/ops/visual_requirement.py",
                          # P7-2（人工授权新增）：AssetIndex **只读**入口——同样只读打开 DB、
                          # 不写任何文件（artifact 落盘在 docs/regression_2x/phase7_p7_2_build.py）、
                          # 零网络（不下载素材）。
                          "src/video_studio/ops/asset_index.py",
                          # P7-3（人工授权新增）：多样性度量**只读**入口——只读打开 DB、
                          # 不写任何文件（artifact 落盘在 docs/regression_2x/phase7_p7_3_build.py）、
                          # 零网络/零 LLM（只做算术与统计）。
                          "src/video_studio/ops/asset_diversity.py",
                          # P7-4（人工授权新增）：相关性判定**只读**入口——只读打开 DB、
                          # 不写任何文件（artifact 落盘在 docs/regression_2x/phase7_p7_4_build.py）、
                          # 零网络/零 VLM（只消费既有产物与人类判定证据）。
                          "src/video_studio/ops/visual_relevance.py",
                          # P7-5（人工授权新增）：受治理获取**只读**入口——只读打开 DB、
                          # **不写任何文件、不下载**（DRY_RUN 默认；live 需显式授权且本仓库
                          # provider=none ⇒ fail-closed）；artifact 落盘在
                          # docs/regression_2x/phase7_p7_5_build.py。
                          "src/video_studio/ops/visual_acquisition.py",
                          # P7-6（人工授权新增）：绑定提案 + 覆盖闭环**只读**入口——只读打开 DB、
                          # 不写任何文件、**零执行**（不改 timeline/素材/6-G，不 rebuild/render，
                          # 不写 ledger/register）；artifact 落盘在
                          # docs/regression_2x/phase7_p7_6_build.py。
                          "src/video_studio/ops/visual_binding.py",
                          # Phase 9（人工授权新增）：留存评分**只读**编排层——DB 以 mode=ro 打开、
                          # **不写任何文件**（LLM 缓存由调用方注入/持久化，ops 自身不落盘）、
                          # 不接入生产闸门、不派任务、不自动改稿；报告由 CLI/阶段脚本输出。
                          "src/video_studio/ops/retention.py"}
# 6-B/M4 **测试契约更新**（强度**加强**而非放宽）：经授权新增 `ops/execution.py`
#   （受控执行编排：沙箱准备 + 真实执行器 + 强制 PI/DQ 复核）。该模块**不是只读模块**，
#   因此**禁止**并入上面的只读白名单（不得把写型模块伪装成只读）；改为独立的
#   "授权写入型 ops" 类别，并施加**比只读检查更强的静态约束**：
#     ① 沙箱前缀必须声明且以 `output/` 开头（不得写 src/docs/baseline/项目目录）；
#     ② **所有** write_text/write_bytes/rmtree/copy2/mkdir/unlink/touch/Path.replace 的目标实参必须
#        **沙箱派生**（AST 污点传播：目标必须是 `box` 或由 `box` 传递派生的名字；
#        `str.replace(old,new)` 双参形态不算文件替换）；
#     ③ 仍受同一套"无 DB 写"禁令（INSERT/UPDATE/DELETE、create_task/run_cycle/write_artifact）；
#     ④ 不得自建绕过人工审批的执行入口（禁止 execute_proposal/execute_all/apply_*/auto_* 函数）；
#     ⑤ 不得 import agents 生产模块；且任何 agents/ 模块**不得引用**该模块（生产链不可达）。
#   其余任何新增 ops/ 模块仍一律 FAIL（= 原守卫意图不变；本类别**不给**只读豁免）。
AUTHORIZED_WRITE_OPS = {"src/video_studio/ops/execution.py"}
_SANDBOX_ROOT_PREFIX = "output/"
_RECV_DEST_CALLS = {"write_text", "write_bytes", "mkdir", "unlink", "touch", "replace"}
_ARG_DEST_CALLS = {"rmtree": 0, "copy2": 1, "move": 1}
_BYPASS_ENTRY_NAMES = {"execute_proposal", "run_execution", "execute_all", "apply_all",
                       "apply_proposal", "fallback_plan", "auto_execute", "auto_apply"}
_WRITE_CALLS = ("write_artifact", "attach_artifact", "build_engine", "commit", "executescript",
                "create_task", "run_cycle", "redo", "update_task", "create_project")
_WRITE_SQL = ("insert into", "delete from", "update tasks", "create table", "drop table")


def _sandbox_write_violations(rel):
    """授权写入型 ops 模块的**更强**静态检查（AST 级；含沙箱污点传播）。

    目标：静态证明该模块**只**能写沙箱（`output/phase6b_m4_sandbox/...`），
    且没有任何绕过人工审批的执行入口。
    """
    import ast as _ast
    src = (ROOT / rel).read_text(encoding="utf-8")
    tree = _ast.parse(src)
    viol = []
    # ① 沙箱前缀声明 + 以 output/ 开头（读 AST 常量，不靠文本猜测）
    prefix_ok = False
    for node in _ast.walk(tree):
        if isinstance(node, _ast.Assign):
            for t in node.targets:
                if isinstance(t, _ast.Name) and t.id == "SANDBOX_ROOT_REL" \
                        and isinstance(node.value, _ast.Constant) \
                        and isinstance(node.value.value, str):
                    prefix_ok = node.value.value.startswith(_SANDBOX_ROOT_PREFIX)
    if not prefix_ok:
        viol.append("sandbox_prefix_not_output")
    # ② 无 DB 写（同一套禁令）
    for node in _ast.walk(tree):
        if isinstance(node, _ast.Call):
            nm = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
            if nm in _WRITE_CALLS:
                viol.append("call:" + str(nm))
            for a in list(node.args) + [k.value for k in node.keywords]:
                if isinstance(a, _ast.Constant) and isinstance(a.value, str):
                    low = a.value.lower()
                    for k in _WRITE_SQL:
                        if k in low:
                            viol.append("sql:" + k)
    # ③ 无绕过审批的执行入口
    for node in _ast.walk(tree):
        if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
            if node.name.startswith("auto_") or node.name in _BYPASS_ENTRY_NAMES:
                viol.append("bypass_entry:" + node.name)
    # ④ 沙箱污点传播：任何写入/删除目标都必须由 `box` 派生
    #    目标位置口径：write_text/write_bytes/mkdir/unlink/touch = **接收者**；
    #                  rmtree(idx0)/copy2(idx1)/move(idx1) = 对应实参。
    tainted = {"box"}
    for _ in range(6):                      # 传递闭包（`film_copy = box/...` → `dst` 派生链）
        for node in _ast.walk(tree):
            if isinstance(node, _ast.Assign):
                seg = _ast.get_source_segment(src, node.value) or ""
                if any(re.search(r"\b{}\b".format(re.escape(t)), seg) for t in tainted):
                    for t in node.targets:
                        if isinstance(t, _ast.Name):
                            tainted.add(t.id)
    for node in _ast.walk(tree):
        if not (isinstance(node, _ast.Call) and isinstance(node.func, _ast.Attribute)):
            continue
        attr = node.func.attr
        if attr == "replace" and len(node.args) == 2:
            # `str.replace(old, new)`（纯字符串处理）不是文件替换；`Path.replace(target)` 只有一个实参
            continue
        if attr in _RECV_DEST_CALLS:
            dest = node.func.value
        elif attr in _ARG_DEST_CALLS:
            idx = _ARG_DEST_CALLS[attr]
            dest = node.args[idx] if len(node.args) > idx else None
        else:
            continue
        if dest is None:
            viol.append("dest_arg_missing:" + attr)
            continue
        seg = _ast.get_source_segment(src, dest) or ""
        if not any(re.search(r"\b{}\b".format(re.escape(t)), seg) for t in tainted):
            viol.append("dest_not_sandbox:{}:{}".format(attr, seg[:60]))
    # ⑤ 不得 import agents 生产模块；agents 也不得引用该模块
    for node in _ast.walk(tree):
        if isinstance(node, _ast.ImportFrom) and (node.module or "").startswith("..agents"):
            viol.append("imports_agents:" + str(node.module))
    stem = rel.rsplit("/", 1)[-1][:-3]
    for p in sorted((ROOT / "src" / "video_studio" / "agents").rglob("*.py")):
        txt = p.read_text(encoding="utf-8")
        if re.search(r"(ops[\. ]+import[ ]+{}|ops\.{}\b|import {}\b)".format(
                stem, stem, stem), txt):
            viol.append("reachable_from_agents:" + p.name)
    return sorted(set(viol))


def _readonly_violations(rel):
    """AST 级只读静态检查（只看**代码**，不误判 docstring/注释）。

    `ro_connection` 的两种合法形态（6-B/M3 契约更新，意图不变 = 绝不写库）：
      ① 该模块**自己**以 `mode=ro` + `query_only` 打开 DB；
      ② 该模块**不碰 DB**，而是 import 另一个白名单内的只读 ops 模块并委托其读取
         （如 `ops/revision.py` → `ops/review.py` → `ops/direction.py`）。
    """
    import ast as _ast
    src = (ROOT / rel).read_text(encoding="utf-8")
    tree = _ast.parse(src)
    viol, imports = [], []
    for node in _ast.walk(tree):
        if isinstance(node, _ast.Call):
            fn = node.func
            name = getattr(fn, "attr", None) or getattr(fn, "id", None)
            if name in _WRITE_CALLS:
                viol.append("call:" + str(name))
            for a in list(node.args) + [k.value for k in node.keywords]:
                if isinstance(a, _ast.Constant) and isinstance(a.value, str):
                    low = a.value.lower()
                    for k in _WRITE_SQL:
                        if k in low:
                            viol.append("sql:" + k)
        elif isinstance(node, _ast.ImportFrom):
            imports.append(node.module or "")
    low_src = src.lower()
    own_ro = ("mode=ro" in low_src and "query_only" in low_src)
    _self_stem = rel.rsplit("/", 1)[-1][:-3]           # 例如 ops/revision.py → revision
    _peers = [w.rsplit("/", 1)[-1][:-3] for w in READONLY_OPS_WHITELIST]
    delegated = any(m.rsplit(".", 1)[-1] in [p for p in _peers if p != _self_stem]
                    for m in imports)
    return sorted(set(viol)), (own_ro or delegated)


_new_ops = sorted(p.relative_to(ROOT).as_posix()
                  for p in (ROOT / "src" / "video_studio" / "ops").glob("*.py")
                  if p.relative_to(ROOT).as_posix() not in man["files"])
_unexpected_ops = sorted(set(_new_ops) - READONLY_OPS_WHITELIST - AUTHORIZED_WRITE_OPS)
_ro_violations, _ro_ro_ok = {}, {}
for _rel in sorted(READONLY_OPS_WHITELIST):
    if (ROOT / _rel).is_file():
        _v, _ok = _readonly_violations(_rel)
        _ro_ro_ok[_rel] = _ok
        if _v or not _ok:
            _ro_violations[_rel] = {"violations": _v, "ro_connection": _ok}
check("M8d 未新增**视频能力** ops/ 模块（仅允许经授权的只读 metrics/report 白名单，"
      "且白名单模块通过 AST 只读静态检查 + 只读连接标记）",
      not _unexpected_ops and not _ro_violations,
      {"unexpected_new_ops": _unexpected_ops, "readonly_violations": _ro_violations,
       "readonly_ok": _ro_ro_ok, "whitelist": sorted(READONLY_OPS_WHITELIST)})
# 6-B/M4 新增守卫：授权写入型 ops 模块必须通过**更强**的沙箱/无绕过静态检查
_write_violations, _write_targets = {}, {}
for _rel in sorted(AUTHORIZED_WRITE_OPS):
    if (ROOT / _rel).is_file():
        _wv = _sandbox_write_violations(_rel)
        _write_targets[_rel] = len(_wv)
        if _wv:
            _write_violations[_rel] = _wv
        check("M8e {}：写入目标**仅限沙箱**（output/ 前缀 + AST 污点全部由 box 派生）、"
              "无 DB 写、无绕过人工审批的执行入口、生产链（agents/）不可达".format(
                  _rel.rsplit("/", 1)[-1]),
              _wv == [], _wv)
check("M8e 授权写入型 ops 白名单不包含任何只读白名单成员（写型模块不得伪装只读）",
      not (AUTHORIZED_WRITE_OPS & READONLY_OPS_WHITELIST),
      sorted(AUTHORIZED_WRITE_OPS & READONLY_OPS_WHITELIST))

print("\n结果: {}/{} 通过".format(len(PASS), len(PASS) + len(FAIL)))
if FAIL:
    print("失败项:", FAIL)
sys.exit(1 if FAIL else 0)
