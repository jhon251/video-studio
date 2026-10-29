"""Phase 2-A/B 装配单元测试（免费、确定性）：真实 ffmpeg 按素材时间轴出片并逐镜头抽帧核验。

用 3 张真实本地图片 + 合成脚本（非生产项目），直接调用 EditingAgent 的时间轴构建与
ffmpeg 参数生成，验证：
  · 每个镜头分配到不同素材，timeline 字段齐全（scene_id/start_s/end_s/asset_id/fallback/reason）
  · ffmpeg 真正按 timeline 装配（成片时长≈timeline 末尾）
  · 逐镜头抽帧与该镜头素材相关性最高，且不同镜头画面互不相同
  · 无素材镜头 → 纯色底 fallback（不伪造）

用法：python tests/scene_assembly_test.py
"""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.agents.editing.agent import EditingAgent  # noqa: E402

FFMPEG = ROOT / "bin" / "ffmpeg.exe"
FFPROBE = ROOT / "bin" / "ffprobe.exe"
WORK = Path(r"C:\Users\DUALAN~1\AppData\Local\Temp\v161audit\scene_test")
SRC = [("output/run03/asset_cache/files/r3_S01-B01_3.img.jpg", "VR头显_镜片特写.jpg"),
       ("output/run03/asset_cache/files/r3_S01-B02_1.img.jpg", "脑电头环_假人头模_陈列柜.jpg"),
       ("output/run03/asset_cache/files/r3_S01-B01_0.img.jpg", "VR头显_手柄_笔记本.jpg")]
PASS, FAIL = [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print(("PASS  " if ok else "FAIL  ") + name + (" | " + str(detail)[:160] if detail else ""))


def grams(p):
    return np.asarray(Image.open(p).convert("L").resize((48, 48)), dtype=np.float64)


def corr(a, b):
    a, b = a - a.mean(), b - b.mean()
    d = np.sqrt((a ** 2).sum()) * np.sqrt((b ** 2).sum())
    return float((a * b).sum() / d) if d else 0.0


# ---- 准备：媒体目录 + 素材池（与 retrieval 产出的字段一致） ----
if WORK.exists():
    shutil.rmtree(WORK, ignore_errors=True)
media = WORK / "media"
media.mkdir(parents=True, exist_ok=True)
(media / "artifacts").mkdir(exist_ok=True)
pool = []
for rel, name in SRC:
    dst = media / name
    shutil.copy2(ROOT / rel, dst)
    sha = hashlib.sha256(dst.read_bytes()).hexdigest()
    pool.append({"asset_id": "asset_" + sha[:12], "name": name, "source": "local_ingest",
                 "sha256": sha, "path": str(dst), "relative_path": name,
                 "bytes": dst.stat().st_size, "license": "unchecked",
                 "retrieval_match_score": 10})

script = {"segments": [
    {"chapter": "开场", "narration": "先看 VR 头显的镜片，这是进入虚拟世界的第一道门。", "duration_s": 6},
    {"chapter": "设备", "narration": "脑电头环把电极贴在头皮上，用来读取脑电信号。", "duration_s": 5},
    {"chapter": "组合", "narration": "VR 头显配手柄和笔记本，构成一套完整的沉浸设备。", "duration_s": 4},
]}
shots = [{"description": "VR 头显镜片特写", "gen_prompt": "vr headset lens closeup"},
         {"description": "脑电头环 电极", "gen_prompt": "eeg headband electrodes"},
         {"description": "VR 头显 手柄 笔记本", "gen_prompt": "vr headset controllers laptop"}]


class Eng:
    def project_dir(self, pid):
        return media


class Task(dict):
    pass


tl = EditingAgent._build_material_timeline(script, shots, pool)
check("时间轴镜头数 == 段落数", len(tl) == 3, len(tl))
check("每个镜头字段齐全",
      all(set(("scene_id", "start_s", "end_s", "selected_asset", "selection_reason",
               "fallback_state")) <= set(s) for s in tl))
ids = [s["selected_asset"]["asset_id"] for s in tl]
check("3 个镜头使用 3 个不同素材", len(set(ids)) == 3, ids)
check("时间轴连续且首尾正确",
      tl[0]["start_s"] == 0 and all(abs(tl[i]["end_s"] - tl[i + 1]["start_s"]) < 1e-6
                                    for i in range(len(tl) - 1)),
      [(s["start_s"], s["end_s"]) for s in tl])
check("fallback_state 均为 LOCAL_INGEST",
      all(s["fallback_state"] == "LOCAL_INGEST" for s in tl))
check("selection_reason 含命中关键词",
      all("关键词命中" in s["selection_reason"] or "无素材命中" in s["selection_reason"] for s in tl))

# ---- 真实装配 ----
args = EditingAgent._narration_args(Eng(), {"project_id": "p_test"}, script, "1280x720", 30,
                                    {"codec": "libx264"}, narration_audio=None, timeline=tl)
out = WORK / "assembly.mp4"
cmd = [str(FFMPEG), "-y", "-v", "error", *args, str(out)]
r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
check("ffmpeg 按时间轴装配成功（rc=0）", r.returncode == 0 and out.exists(),
      (r.stderr or "")[:200])
if out.exists():
    p = subprocess.run([str(FFPROBE), "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", str(out)], capture_output=True, text=True)
    dur = float(p.stdout.strip() or 0)
    total = tl[-1]["end_s"]
    check("成片时长 == 时间轴总长（±0.6s）", abs(dur - total) <= 0.6, "video={} timeline={}".format(
        round(dur, 2), total))
    d = subprocess.run([str(FFMPEG), "-v", "error", "-i", str(out), "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    check("ffmpeg 解码 rc=0", d.returncode == 0, (d.stderr or "")[:120])
    refs = {a["asset_id"]: grams(a["path"]) for a in pool}
    frames = {}
    for s in tl:
        mid = (s["start_s"] + s["end_s"]) / 2
        fp = WORK / "f_{}.png".format(s["scene_id"])
        subprocess.run([str(FFMPEG), "-y", "-v", "error", "-ss", f"{mid:.2f}", "-i", str(out),
                        "-frames:v", "1", str(fp)], capture_output=True, text=True)
        if not fp.exists():
            check("抽帧 " + s["scene_id"], False)
            continue
        frames[s["scene_id"]] = grams(fp)
        sc = {k: round(corr(frames[s["scene_id"]], v), 3) for k, v in refs.items()}
        want = s["selected_asset"]["asset_id"]
        best = max(sc, key=lambda k: sc[k])
        check("{} 抽帧匹配其分配素材".format(s["scene_id"]),
              best == want and sc[want] > 0.3, "want={} best={} corr={}".format(want, best, sc))
    ks = list(frames)
    if len(ks) >= 2:
        worst = max(corr(frames[ks[i]], frames[ks[j]])
                    for i in range(len(ks)) for j in range(i + 1, len(ks)))
        check("不同镜头画面互不相同（最大相关<0.98）", worst < 0.98, round(worst, 3))

# ---- fallback：无素材池 → 全纯色底，且不伪造 ----
tl0 = EditingAgent._build_material_timeline(script, shots, [])
check("无素材时全部 SOLID_COLOR_CARD", all(s["fallback_state"] == "SOLID_COLOR_CARD" for s in tl0))
check("无素材时不产生 selected_asset", all(s["selected_asset"] is None for s in tl0))

print("\n结果: {}/{} 通过".format(len(PASS), len(PASS) + len(FAIL)))
if FAIL:
    print("失败项:", FAIL)
sys.exit(0 if not FAIL else 1)
