"""subtitle_pipeline (Stage 12.4): narration -> TTS-duration-aligned SRT + burn-in.

Reuses existing subtitle agent timestamp logic (agents/subtitle/agent.py ts())
and REAL TTS segment durations (probed from F5 wav files). No second subtitle
system. Timeline invariants: start>=0, end>start, end<=audio_duration+tol,
no overlap, no inversion, no negative duration.

Two outputs:
  A. SRT sidecar
  B. Burn-in via ffmpeg drawtext (white + shadow, bottom safe area) —
     libass not compiled in this ffmpeg build, so subtitles filter is
     unavailable; drawtext is the verified path (libfreetype present).

Composition decision is NOT modified; subtitle sits in bottom safe area.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FFMPEG = ROOT / "bin" / "ffmpeg.exe"
FONT = ROOT / "output/production_002/build_v2/msyh.ttc"


def ts(seconds: float) -> str:
    """SRT timestamp (same format as agents/subtitle/agent.py)."""
    ms = int(round(seconds * 1000))
    h, rem = divmod(ms, 3600000)
    m, rem = divmod(rem, 60000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def probe_wav_duration(p: Path) -> float:
    r = subprocess.run([str(FFMPEG), "-i", str(p)], capture_output=True, text=True, encoding="utf-8", errors="replace")
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", r.stderr)
    if m:
        return float(m.group(1)) * 3600 + float(m.group(2)) * 60 + float(m.group(3))
    return 0.0


def split_for_subtitle(text: str, max_chars: int = 22) -> list[str]:
    """Split narration into readable short subtitle lines (<= max_chars),
    preferring punctuation boundaries (，。；！？、, spaces)."""
    # split on punctuation first
    parts = re.split(r"(?<=[，。；！？、,.!?])", text)
    parts = [p.strip() for p in parts if p.strip()]
    lines = []
    for part in parts:
        if len(part) <= max_chars:
            lines.append(part)
        else:
            # further split on remaining commas/spaces
            sub = re.split(r"(?<=[，、, ])", part)
            buf = ""
            for s in sub:
                if not s:
                    continue
                if len(buf) + len(s) <= max_chars:
                    buf += s
                else:
                    if buf:
                        lines.append(buf.strip())
                    buf = s
            if buf:
                lines.append(buf.strip())
    return lines or ([text] if text else [])


def build_srt(shots: list[dict]) -> tuple[str, list[dict]]:
    """Build SRT aligned to REAL per-shot wav durations.

    shots: [{shot_id, narration, wav_path}]. Each shot = one subtitle cue
    (long narration may be split across cue lines with proportional time).
    """
    entries = []
    cursor = 0.0
    for sh in shots:
        wav = Path(sh["wav_path"])
        dur = probe_wav_duration(wav) if wav.exists() else sh.get("est_s", 5.0)
        if dur <= 0:
            dur = 5.0
        text = sh["narration"]
        lines = split_for_subtitle(text)
        n = len(lines)
        # proportional time per line within this shot's audio
        weights = [len(l) + 1 for l in lines]
        total_w = sum(weights)
        start = cursor
        shot_start = cursor
        for i, (line, w) in enumerate(zip(lines, weights)):
            if i == n - 1:
                end = shot_start + dur  # last line ends at shot end (NOT accumulated start)
            else:
                end = start + dur * w / total_w
            entries.append({"text": line, "start": round(start, 3),
                            "end": round(end, 3), "shot_id": sh["shot_id"]})
            start = end
        cursor += dur
    srt_parts = []
    for i, e in enumerate(entries, 1):
        srt_parts.append(f"{i}\n{ts(e['start'])} --> {ts(e['end'])}\n{e['text']}\n")
    return "\n".join(srt_parts), entries


def validate_timing(entries: list[dict], audio_total: float) -> dict:
    """Timeline invariants."""
    problems = []
    for i, e in enumerate(entries):
        if e["start"] < 0:
            problems.append(f"idx{i}: start<0")
        if e["end"] <= e["start"]:
            problems.append(f"idx{i}: end<=start")
        if e["end"] > audio_total + 0.05:
            problems.append(f"idx{i}: end>audio_total ({e['end']}>{audio_total})")
    for i in range(1, len(entries)):
        if entries[i]["start"] < entries[i - 1]["end"] - 0.001:
            problems.append(f"overlap idx{i-1}->{i}")
    return {"valid": len(problems) == 0, "problems": problems,
            "n_entries": len(entries), "audio_total_s": round(audio_total, 3)}


def burn_in(video_no_sub: Path, srt_path: Path, out_mp4: Path,
            font: Path | None = None) -> dict:
    """Burn SRT via drawtext (libass unavailable). White + shadow, bottom-center.
    Since drawtext can't read SRT directly, we render per-cue subtitle overlay
    by re-encoding video with drawtext on segments is complex; simpler robust
    path: drawtext enabled=between(t,start,end) for each cue in one filter chain.
    """
    font = font or FONT
    entries = []
    with open(srt_path, encoding="utf-8") as f:
        raw = f.read()
    # parse SRT cues
    blocks = re.split(r"\n\s*\n", raw.strip())
    for b in blocks:
        lines = b.strip().splitlines()
        if len(lines) < 2:
            continue
        # index line; timings line; text lines
        idx = 0
        if lines[0].strip().isdigit():
            idx = 1
        tm = lines[idx] if idx < len(lines) else ""
        m = re.match(r"(-?\d+):(\d+):(\d+),(\d+)\s*-->\s*(-?\d+):(\d+):(\d+),(\d+)", tm)
        if not m:
            continue
        def sec(base: int) -> float:
            h = int(m.group(base))
            mi = int(m.group(base + 1))
            s = int(m.group(base + 2))
            ms = int(m.group(base + 3))
            return h * 3600 + mi * 60 + s + ms / 1000.0
        t0, t1 = sec(1), sec(5)
        if t0 < 0:
            t0 = 0.0  # part-boundary drift can yield tiny negative local starts; clamp to timeline start
        text = " ".join(x.strip() for x in lines[idx + 1:] if x.strip())
        entries.append((t0, t1, text))

    # build drawtext chain using textfile= (avoids inline escaping of CJK
    # quotes/colons). Each cue gets its own txt; enabled=between(t0,t1).
    vf_parts = []
    txt_dir = out_mp4.parent / "_subtxt"
    txt_dir.mkdir(parents=True, exist_ok=True)
    import shutil
    build_font = txt_dir / "msyh.ttc"
    if not build_font.exists() and Path(font).exists():
        shutil.copy(Path(font), build_font)
    for (t0, t1, text) in entries:
        tf = txt_dir / f"cue_{len(vf_parts):03d}.txt"
        tf.write_text(text, encoding="utf-8")
        rel = tf.name  # ffmpeg cwd = txt_dir for relative textfile path
        vf_parts.append(
            f"drawtext=fontfile=msyh.ttc:textfile={rel}:expansion=none:fontsize=40:fontcolor=white:"
            f"borderw=2:bordercolor=black@0.7:shadowx=1:shadowy=1:"
            f"x=(w-text_w)/2:y=h-90:enable='between(t,{t0:.2f},{t1:.2f})'")
    cmd = [str(FFMPEG), "-y", "-i", str(video_no_sub)]
    cmd += ["-vf", ",".join(vf_parts)]
    cmd += ["-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p", str(out_mp4)]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(txt_dir))
    err = (r.stderr or "")[-400:]
    return {"success": r.returncode == 0, "stderr": err}
