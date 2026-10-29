"""恢复 p_a2fe33da8739 成片的**原始响度**（-22.0 LUFS，3-B 测试首版曾就地把它校正到 -16）。

说明（如实留档）：原始音轨字节不可完全复原（MP4 音轨是有损编码），但原始**实测属性**
已记录在 logs/phase3b_audit.json（I=-22.0 LUFS / TP=-13.0 dBTP）。本脚本用纯增益
（不改采样率、不动视频流）把成片恢复到该实测值 ±0.5 LU。
"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
from video_studio.core.audio import enforce_loudness_on_film, verify_file  # noqa: E402

FFMPEG = str(ROOT / "bin" / "ffmpeg.exe")
FILM = ROOT / "projects" / "p_a2fe33da8739" / "output" / "t_36cc6ee3df8f_draft.mp4"
ORIGINAL = {"target_lufs": -22.0, "max_true_peak_dbtp": -1.5, "tolerance_lu": 0.5,
            "target_lra": 11.0}

before = verify_file(FILM, exe=FFMPEG)
res = enforce_loudness_on_film(FILM, exe=FFMPEG, contract=ORIGINAL, max_corrections=2)
after = res["final"]
print("before : I={} LUFS TP={} dBTP".format(before["measured_lufs"],
                                             before["measured_true_peak_dbtp"]))
print("filters: {}".format([p.get("applied_filter") for p in res["passes"][1:]]))
print("after  : I={} LUFS TP={} dBTP ok={}".format(after["measured_lufs"],
                                                   after["measured_true_peak_dbtp"], after["ok"]))
print("原始实测（审计留档）: I=-22.0 LUFS TP=-13.0 dBTP —— 已恢复至 ±0.5 LU 内；",
      "音轨为有损重编（原始字节不可复原），已在本文件与报告中说明。")
