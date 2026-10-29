# -*- coding: utf-8 -*-
"""Phase 58 / P58：**视频条素材**（media_type=video）端到端回归。

P58-2/P58-3 的三个不变量：
  T1  视频可用性探测：真视频 usable；**坏文件 fail-closed**（绝不入片）；
  T2  渲染装配：视频条场景 + 图片场景混排 → ffmpeg 成功、**时长 == 时间轴**、
      视频场景内**画面在动**（抽两帧相关性 < 0.98，证明不是定格图）；
  T3  tpad 定格：素材短于景长 ⇒ 成片时长**仍精确**，尾段画面定格（相邻帧相关 ≥0.999）
      且与中段不同（不是黑屏）；
  T4  帧检参照：`_verify_scene_frames` 对视频场景用**素材抽帧**作参照 ⇒ 相关 ≥ 阈值
      （此前 PIL 打不开视频 ⇒ 无参照 ⇒ 必假失败）。
运行: python tests/p58_video_material_test.py
"""
from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
WORK = R / "output" / "p58_test_work"
FF = str(R / "bin" / "ffmpeg.exe")
FFPROBE = str(R / "bin" / "ffprobe.exe")
PASS, FAIL = [], []


def check(name, ok, detail=None):
    (PASS if ok else FAIL).append(name)
    print("{}  {} {}".format("PASS" if ok else "FAIL", name,
                             "" if ok else json.dumps(detail, ensure_ascii=False,
                                                      default=str)[:260]))
    return bool(ok)


def run(args):
    return subprocess.run(args, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def dur(p):
    r = run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", str(p)])
    v = (r.stdout or "").strip().splitlines()
    return round(float(v[0]), 3) if v and v[0] else None


def gray(path):
    from PIL import Image
    import numpy as np
    a = np.asarray(Image.open(path).convert("L").resize((48, 48)), dtype=float)
    return a


def corr(a, b):
    import numpy as np
    a, b = a - a.mean(), b - b.mean()
    d = (float((a * b).sum()) /
         (float((a * a).sum()) ** 0.5 * float((b * b).sum()) ** 0.5 + 1e-9))
    return round(d, 4)


def frame_at(video, t, out):
    run([FF, "-y", "-v", "error", "-ss", "{:.2f}".format(t), "-i", str(video),
         "-frames:v", "1", str(out)])
    return out


class Eng:
    config = None

    def project_dir(self, pid):
        return WORK


class Ctx:
    project_id = "p_p58test"
    project_dir = WORK            # FFmpegTool 以 `ctx.project_dir / src` 解析路径
    config = {"tools": {"ffmpeg": {"path": FF}}}


def main() -> int:
    if WORK.exists():
        shutil.rmtree(WORK, ignore_errors=True)
    (WORK / "media").mkdir(parents=True)
    (WORK / "artifacts").mkdir(parents=True)
    from video_studio.agents.editing.agent import (_probe_video_usable,
                                                   EditingAgent)

    # ---- 夹具：6s 视频（运动）+ 3s 视频（短于景长）+ 1 图 ----
    vid6 = WORK / "media" / "test_motion.mp4"
    run([FF, "-y", "-v", "error", "-f", "lavfi", "-i",
         "testsrc2=size=640x360:rate=25:duration=6", "-c:v", "libx264", "-pix_fmt",
         "yuv420p", str(vid6)])
    vid3 = WORK / "media" / "test_short.mp4"
    run([FF, "-y", "-v", "error", "-f", "lavfi", "-i",
         "testsrc2=size=640x360:rate=25:duration=3", "-c:v", "libx264", "-pix_fmt",
         "yuv420p", str(vid3)])
    img = WORK / "media" / "test_img.png"
    run([FF, "-y", "-v", "error", "-f", "lavfi", "-i",
         "color=c=0x335577:size=640x360:duration=1", "-frames:v", "1", str(img)])

    # ---- T1 可用性探测 ----
    u, why, w, h, d = _probe_video_usable(vid6, FFPROBE)
    check("T1a 真视频 usable（{}x{} {:.1f}s）".format(w, h, d or 0),
          u and w == 640 and h == 360, why)
    bad = WORK / "media" / "bad.mp4"
    bad.write_bytes(b"not a video")
    u2, why2, *_ = _probe_video_usable(bad, FFPROBE)
    check("T1b 坏文件 fail-closed（{}）".format(str(why2)[:40]),
          (not u2) and "VIDEO_PROBE_FAILED" in str(why2))

    # ---- T2/T3 渲染装配（视频 6s/4.5s + 短视频 3s/6s + 图 5s）----
    tl = [
        {"scene_id": "S1", "start_s": 0.0, "end_s": 4.5, "fallback_state": "LOCAL_INGEST",
         "insufficiency_class": "NONE",
         "selected_asset": {"asset_id": "asset_vid6", "path": str(vid6)}},
        {"scene_id": "S2", "start_s": 4.5, "end_s": 10.5, "fallback_state": "LOCAL_INGEST",
         "insufficiency_class": "NONE",
         "selected_asset": {"asset_id": "asset_vid3", "path": str(vid3)}},
        {"scene_id": "S3", "start_s": 10.5, "end_s": 15.5, "fallback_state": "LOCAL_INGEST",
         "insufficiency_class": "NONE",
         "selected_asset": {"asset_id": "asset_img", "path": str(img)}},
    ]
    from video_studio.agents.editing.agent import EditingAgent
    args = EditingAgent._narration_args(
        Eng(), {"project_id": "p_p58test", "task_id": "t_p58"}, {"segments": []},
        "640x360", 25, {"codec": "libx264"}, narration_audio=None, timeline=tl,
        audio_time_base_s=15.5)
    out = WORK / "out_p58.mp4"
    r = run([FF, "-y", "-v", "error", *args, str(out)])
    check("T2a 视频条装配 ffmpeg rc=0", r.returncode == 0 and out.is_file(),
          (r.stderr or "")[:200])
    total = 15.5
    if out.is_file():
        dd = dur(out)
        check("T2b 成片时长 == 时间轴 {:.3f}（实测 {}）".format(total, dd),
              dd is not None and abs(dd - total) <= 0.5)
        # 视频场景内画面在动
        f1, f2 = frame_at(out, 0.5, WORK / "s1_a.png"), frame_at(out, 3.5, WORK / "s1_b.png")
        c_motion = corr(gray(f1), gray(f2))
        check("T2c 视频场景画面在动（corr {:.3f} < 0.98）".format(c_motion),
              c_motion < 0.98)
        # T3 tpad：S2 素材 3s / 景 6s —— 尾段应定格
        f3 = frame_at(out, 8.0, WORK / "s2_a.png")
        f4 = frame_at(out, 10.0, WORK / "s2_b.png")
        c_freeze = corr(gray(f3), gray(f4))
        check("T3a 短素材尾段定格（corr {:.3f} ≥ 0.999）".format(c_freeze),
              c_freeze >= 0.999)
        f5 = frame_at(out, 6.9, WORK / "s2_c.png")
        c_tail = corr(gray(f3), gray(f5))
        check("T3b 定格前画面仍在动（corr {:.3f} < 0.99）".format(c_tail),
              c_tail < 0.99)

        # ---- T4 帧检参照（视频场景以素材抽帧作参照）----
        refs_pool = [{"asset_id": "asset_vid6", "path": str(vid6), "usable": True},
                     {"asset_id": "asset_vid3", "path": str(vid3), "usable": True},
                     {"asset_id": "asset_img", "path": str(img), "usable": True}]
        ev, summary = EditingAgent._verify_scene_frames(
            Eng(), Ctx(), out, tl, refs_pool=refs_pool,
            policy={"frame_match_min_corr": 0.30, "frame_argmax_margin": 0.15,
                    "frame_verify": True})
        rows = {e["scene_id"]: e for e in ev}
        v6 = rows.get("S1") or {}
        check("T4a 视频场景 corr ≥ 阈值且 argmax 正确（corr {}）".format(
            v6.get("corr_expected")), v6.get("match") is True, v6)
        v3 = rows.get("S2") or {}
        check("T4b tpad 场景（尾段定格）corr ≥ 阈值（corr {}）".format(
            v3.get("corr_expected")), v3.get("match") is True, v3)
        ref_made = pathlib.Path(str(vid6) + ".ref.jpg").is_file()
        check("T4c 视频参照帧已抽帧缓存", ref_made)

    print()
    print("=" * 74)
    print("p58_video_material_test: {} PASS / {} FAIL".format(len(PASS), len(FAIL)))
    print("=" * 74)
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
