"""基于 V2_FINAL_SCRIPT_JARVIS.md 构建离线成片（文字卡 + TTS 配音，ffmpeg 合成）。

步骤：
  1) parse：把 v2 稿切成 10 段，生成 build_v2/txt/SXX.txt（画面显示文本）与 build_v2/tts/SXX.txt（配音纯文本）
  2) TTS：由 PowerShell System.Speech（Microsoft Huihui Desktop zh-CN）按 tts/*.txt 生成 wav/*.wav
  3) scenes：ffmpeg color + drawtext(msyh.ttc) + wav -> scene_SXX.mp4
  4) concat：filter_complex 拼接 -> output/production_002/JARVIS_V2_final.mp4

不改任何冻结物；仅新增 build_v2/ 与成片。
"""
import json
import re
import subprocess
import sys
import wave
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "production_002"
SRC = OUT / "V2_FINAL_SCRIPT_JARVIS.md"
BUILD = OUT / "build_v2"
FFMPEG = ROOT / "bin" / "ffmpeg.exe"
FONT = BUILD / "msyh.ttc"
W, H, FPS = 1920, 1080, 25
PAD = 0.6  # 每镜尾留白秒
FONTSIZE = 42
LINE_SPACING = 20
CHARS_PER_LINE = 22
COLORS = ["0x1a1a2e", "0x0f3460", "0x2d1b4e", "0x0b3d2e", "0x3b1f2b",
          "0x123a5c", "0x2f2a4a", "0x0e4d45", "0x4a2a5a", "0x1c1c38"]

MARKER = re.compile(r"\*\*〔(.+?)〕\*\*")


def parse_sections() -> list[dict]:
    lines = SRC.read_text(encoding="utf-8").splitlines()
    sections, cur = [], None
    for ln in lines:
        m = MARKER.search(ln)
        if m:
            cur = {"title": m.group(1), "body": []}
            sections.append(cur)
        elif cur is not None:
            cur["body"].append(ln)
    for s in sections:
        s["text"] = re.sub(r"\*\*", "", "\n".join(s["body"])).strip()
    return sections


def wrap(text: str, width: int) -> str:
    out, line = [], ""
    for ch in text:
        line += ch
        if len(line) >= width:
            out.append(line)
            line = ""
    if line:
        out.append(line)
    return "\n".join(out)


def tts_speech_text(section) -> str:
    """配音纯文本：段落拼成一句流。"""
    paras = [p.strip() for p in section["text"].splitlines() if p.strip()]
    return "".join(paras)


def display_text(section) -> str:
    paras = [p.strip() for p in section["text"].splitlines() if p.strip()]
    wrapped = "\n\n".join(wrap(p, CHARS_PER_LINE) for p in paras)
    return "「" + section["title"] + "」\n\n" + wrapped


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / w.getframerate()


def run(cmd, cwd=None):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"CMD FAIL: {' '.join(map(str, cmd))}\n{r.stderr[-2000:]}")
    return r


def main():
    BUILD.mkdir(parents=True, exist_ok=True)
    (BUILD / "txt").mkdir(exist_ok=True)
    (BUILD / "tts").mkdir(exist_ok=True)
    (BUILD / "wav").mkdir(exist_ok=True)
    if not FONT.exists():
        import shutil
        shutil.copy(OUT / "build" / "msyh.ttc", FONT)

    sections = parse_sections()
    print(f"parse: {len(sections)} 段 -> {sections[0]['title']} ... {sections[-1]['title']}")

    manifest = []
    for i, s in enumerate(sections, 1):
        sid = f"S{i:02d}"
        (BUILD / "txt" / f"{sid}.txt").write_text(display_text(s), encoding="utf-8")
        (BUILD / "tts" / f"{sid}.txt").write_text(tts_speech_text(s), encoding="utf-8")
        manifest.append({"scene_id": sid, "title": s["title"], "hanzi": len(re.findall(r"[\u4e00-\u9fff]", s["text"]))})

    # ---- TTS（由外部 pwsh 执行，见 build_video_v2_tts.ps1）----
    print("txt/tts 已生成。现在运行 TTS 步骤（pwsh build_video_v2_tts.ps1），然后重新运行本脚本 --scenes")

    manifest_path = BUILD / "manifest_v2.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    if "--scenes" not in sys.argv:
        return

    # ---- scenes ----
    wav_dir = "wav"
    if "--wav-dir" in sys.argv:
        wav_dir = sys.argv[sys.argv.index("--wav-dir") + 1]
    for i, s in enumerate(sections, 1):
        sid = f"S{i:02d}"
        wavp = BUILD / wav_dir / f"{sid}.wav"
        if not wavp.exists():
            raise RuntimeError(f"缺少配音 {wavp}")
        dur = wav_duration(wavp) + PAD
        vf = (f"drawtext=fontfile=msyh.ttc:textfile=txt/{sid}.txt"
              f":fontsize={FONTSIZE}:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2"
              f":line_spacing={LINE_SPACING}")
        run([str(FFMPEG), "-y", "-f", "lavfi", "-i", f"color=c={COLORS[i-1]}:s={W}x{H}:r={FPS}",
             "-i", f"wav/{sid}.wav", "-vf", vf, "-t", f"{dur:.2f}",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
             "-c:a", "aac", "-b:a", "128k", "-shortest", "-pix_fmt", "yuv420p",
             f"scene_{sid}.mp4"], cwd=BUILD)
        print(f"scene {sid}: {dur:.1f}s")

    # ---- concat ----
    n = len(sections)
    inputs, fc = [], []
    for i in range(1, n + 1):
        inputs += ["-i", f"scene_S{i:02d}.mp4"]
        fc.append(f"[{i-1}:v][{i-1}:a]")
    fc_desc = "".join(fc) + f"concat=n={n}:v=1:a=1[v][a]"
    final = OUT / "JARVIS_V2_final.mp4"
    run([str(FFMPEG), "-y", *inputs, "-filter_complex", fc_desc,
         "-map", "[v]", "-map", "[a]",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
         "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(final)], cwd=BUILD)
    print("final:", final, final.stat().st_size / 1e6, "MB")

    # ---- 时长校验（ffmpeg -i 无输出文件时返回码为 1，属正常）----
    r = subprocess.run([str(FFMPEG), "-i", str(final)], capture_output=True,
                       text=True, errors="replace")
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", r.stderr)
    if m:
        h, mm, ss = map(float, m.groups())
        print(f"总时长: {int(h*3600+mm*60+ss)}s = {h*3600+mm*60+ss:.1f}s")


if __name__ == "__main__":
    main()
