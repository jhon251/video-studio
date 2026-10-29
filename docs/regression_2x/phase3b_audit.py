"""3.x Phase 3-B 审计：实测"两条渲染路径"的音频响度差异（真实 ffmpeg ebur128）。

用法: python docs/regression_2x/phase3b_audit.py [文件...]
默认测：正式链 3-A 真实成片、正式链本地素材成片、stage32b 成片、原始 TTS 旁白。
"""
import json
import shutil
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
from video_studio.core.audio import LOUDNESS_CONTRACT, verify_file  # noqa: E402

OUT = ROOT / "docs" / "regression_2x" / "logs" / "phase3b_audit.json"
DEFAULTS = [
    ("agent_real_chain_film", r"projects\p_f4b466a4a024\output\t_539c107ab85e_draft.mp4"),
    ("agent_2e_film", r"projects\p_a2fe33da8739\output\t_36cc6ee3df8f_draft.mp4"),
    ("stage32b_film", r"output\run03\render\final_long.mp4"),
    ("raw_tts_narration", r"projects\p_f4b466a4a024\media\voice\narration.mp3"),
]
exe = shutil.which("ffmpeg") or str(ROOT / "bin" / "ffmpeg.exe")
targets = [(n, Path(a)) for n, a in
           ([(a, b) for a, b in zip(sys.argv[1::2], sys.argv[2::2])] or DEFAULTS)]

rows = []
print("契约:", json.dumps(LOUDNESS_CONTRACT, ensure_ascii=False))
print("ffmpeg:", exe, "\n")
for name, p in targets:
    if not p.is_file():
        rows.append({"name": name, "path": str(p), "exists": False})
        print("{:22s} 缺失: {}".format(name, p))
        continue
    ev = verify_file(p, exe=exe)
    rows.append({"name": name, "exists": True, **ev,
                 "bytes": p.stat().st_size})
    print("{:22s} I={!s:>7} LUFS  TP={!s:>7} dBTP  Δ={!s:>6} LU  符合契约={}  {}".format(
        name, ev["measured_lufs"], ev["measured_true_peak_dbtp"], ev["delta_lu"], ev["ok"],
        ("; ".join(ev["reasons"]) if ev["reasons"] else "")))
OUT.write_text(json.dumps({"contract": LOUDNESS_CONTRACT, "ffmpeg": exe, "rows": rows},
                          ensure_ascii=False, indent=1), encoding="utf-8")
print("\nwritten", OUT)
