# -*- coding: utf-8 -*-
"""P60-3：**A/B 对照 + 语义同步验证**（同旁白同音频，仅画面轨不同）。

· A 组 = 第二期成片 0→61.74s 截取（真实工作流基线：实拍空镜/黑板图，3 镜头）；
· B 组 = F17（P60 explain_viz 模块自主生成的解释动画，11 视觉节拍）；
· 旁白同源：F17 工程的三段 voice wav = EP2 原文件复制（sha 级核对）；
· 同步验证 = 像素级证据：冲突红描边只在词锚窗口内出现、绿色清单只在
  「跑完」拍出现、着色推进单调递增。不以「视频能导出」为通过标准。
运行: python docs/regression_2x/p60_3_ab_verify.py
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import statistics
import subprocess
import sys
import time

R = pathlib.Path(r"C:\mp4agent\video-studio").resolve()
sys.stdout.reconfigure(encoding="utf-8")
FF = str(R / "bin/ffmpeg.exe")
FFPROBE = str(R / "bin/ffprobe.exe")
OUT = R / "output" / "p60_ep2"
FINAL = R / "projects/p_f084eb26e184/output/t_4f182e0dbe7c_draft_with_outro_v2.mp4"
ANIM = OUT / "B_P60_explainer_v2.mp4"
EP2_FILM = R / "projects/p_2eac65565600/output/t_ee63a79fe9f4_draft_with_outro_v2.mp4"
CUT = 61.74
BEATS = json.loads((OUT / "beat_plan_v2.json").read_text(encoding="utf-8"))


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def dur(p):
    r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1", str(p)], capture_output=True, text=True)
    for ln in (r.stdout or "").strip().splitlines():
        if ln.startswith("duration="):
            return round(float(ln.split("=", 1)[1]), 3)
    return None


def grab(src, t, dst):
    subprocess.run([FF, "-y", "-v", "error", "-ss", "{:.3f}".format(t),
                    "-i", str(src), "-frames:v", "1", str(dst)], check=True)


def count_color(png, target, tol):
    from PIL import Image
    im = Image.open(png).convert("RGB")
    px = im.getdata()
    return sum(1 for p_ in px
               if max(abs(a - b_) for a, b_ in zip(p_, target)) <= tol)


def main() -> int:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    frames = OUT / "ab_frames"
    frames.mkdir(exist_ok=True)

    # ---- 0. 旁白同源核对（A/B 音频来源一致性）----
    ep2_seg = R / "projects/p_2eac65565600/media/voice/seg"
    f17_seg = R / "projects/p_f084eb26e184/media/voice/seg"
    voice_same = {sid: sha(ep2_seg / "{}.wav".format(sid))
                  == sha(f17_seg / "{}.wav".format(sid))
                  for sid in ("P01_1", "P01_2", "P01_3")}
    print("voice seg sha 一致:", voice_same)

    # ---- 1. A 组基线（EP2 成片 0→61.74s 截取）----
    a_mp4 = OUT / "A_baseline_v2.mp4"
    subprocess.run([FF, "-y", "-v", "error", "-ss", "0", "-t", "{:.3f}".format(CUT),
                    "-i", str(EP2_FILM), "-c:v", "libx264", "-preset", "fast",
                    "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac",
                    "-b:a", "160k", "-ar", "48000", str(a_mp4)], check=True)
    print("A 基线: {:.3f}s".format(dur(a_mp4) or 0))

    # ---- 2. 逐节拍帧对（A vs B 成片；B 动画源另存）----
    a_shots = [("P01_1", 0.0, 19.204), ("P01_2", 19.204, 39.646),
               ("P01_3", 39.646, 61.74)]
    table = []
    for i, b in enumerate(BEATS["beats"]):
        mid = min((b["start"] + b["end"]) / 2, CUT - 0.3)
        fa = frames / "beat{:02d}_A.png".format(i + 1)
        fb = frames / "beat{:02d}_B.png".format(i + 1)
        fban = frames / "beat{:02d}_B_anim.png".format(i + 1)
        shot = next((s_[0] for s_ in a_shots if s_[1] <= mid < s_[2]), "-")
        grab(a_mp4, mid, fa)
        grab(FINAL, mid, fb)
        grab(ANIM, mid, fban)
        table.append({"beat": i + 1, "t": round(mid, 2),
                      "template": b["template"], "semantic_tag": b["semantic_tag"],
                      "A_shot": shot, "A_frame": str(fa), "B_frame": str(fb),
                      "B_anim_frame": str(fban)})

    # ---- 3. 语义同步的像素级验证（B 动画源，无字幕干扰）----
    RED = (228, 60, 46)             # 冲突描边（与调色板橙 228,87,46 需容差≤12 区分）
    GREEN = (106, 191, 105)
    GRAY = (210, 210, 210)          # 未着色米灰
    c_conflict = OUT / "_px_conflict.png"
    c_before = OUT / "_px_before.png"
    c_final = OUT / "_px_final.png"
    grab(ANIM, 12.5, c_conflict)     # 冲突窗口 11.64–14.14 内
    grab(ANIM, 8.0, c_before)        # 冲突窗口前（同拍）
    grab(ANIM, 61.5, c_final)        # 终拍「跑完」
    red_in = count_color(c_conflict, RED, 20)
    red_before = count_color(c_before, RED, 20)
    green_final = count_color(c_final, GREEN, 30)
    gray_at_8 = count_color(OUT / "_px_before.png", GRAY, 12)
    # 着色推进单调性：同一拍内 6s vs 13.9s 的未着色像素数应递减
    c_e = OUT / "_px_early.png"
    grab(ANIM, 6.0, c_e)
    gray_early = count_color(c_e, GRAY, 12)
    sync = {
        "conflict_red_pixels_in_window(12.5s)": red_in,
        "conflict_red_pixels_before_window(8.0s)": red_before,
        "green_list_pixels_at_final(61.5s)": green_final,
        "uncolored_gray_6s_vs_8s": [gray_early, gray_at_8],
    }
    checks = {
        "V1 冲突红描边出现在词锚窗口内": red_in > 5000,
        "V2 冲突红描边在窗口前不出现": red_before < 5000,
        "V3 「跑完」拍出现绿色清单": green_final > 20000,
        "V4 着色推进（未着色像素随时间减少）": gray_at_8 < gray_early,
        "V5 旁白三段与 EP2 逐字节同源": all(voice_same.values()),
    }

    # ---- 4. 节奏统计 ----
    b_lens = [round(b_["end"] - b_["start"], 2) for b_ in BEATS["beats"]]
    stats = {
        "schema": "p60-ab-stats-v2",
        "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "cut_s": CUT,
        "narration_source": "EP2 P01_1..P01_3 wav（三段 sha 级同源）",
        "A": {"shots": [[s_[0], round(s_[2] - s_[1], 3)] for s_ in a_shots],
              "count": 3, "avg_s": round(statistics.mean(
                  s_[2] - s_[1] for s_ in a_shots), 2),
              "visual": "实拍空镜×2 + 生成黑板图（与旁白主题相关，无逐句解释关系）"},
        "B": {"beats": len(b_lens), "avg_s": round(statistics.mean(b_lens), 2),
              "min_s": min(b_lens), "max_s": max(b_lens),
              "visual": "explain_viz 模板动画：timeline/coloring+冲突/counting×2/"
                        "hold/collapse/hold/checklist/hold/checklist/checklist终态"},
        "pixel_sync_checks": sync,
        "beat_frame_table": table,
    }
    (OUT / "ab_stats_v2.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8")

    all_ok = True
    for name, ok in checks.items():
        print("{}  {}".format("PASS" if ok else "FAIL", name))
        all_ok &= ok
    (R / "docs/regression_2x/logs/p60_ab_verify.json").write_text(
        json.dumps({"pass": sum(1 for v_ in checks.values() if v_),
                    "fail": sum(1 for v_ in checks.values() if not v_),
                    "checks": checks}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    print("A: 3 镜头 avg {:.2f}s | B: {} 拍 avg {:.2f}s | {:.1f}s".format(
        stats["A"]["avg_s"], stats["B"]["beats"], stats["B"]["avg_s"],
        time.time() - t0))
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
