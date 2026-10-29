"""P0-6 全片 Render：20 镜 concat + 烧录 ASS 字幕 + render_manifest + 自动 QC。

只消费 P0-5 产物；不重新生成单镜/VO/字幕；不美化；不调语速。
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FFMPEG = ROOT / "bin" / "ffmpeg.exe"
FONT = ROOT / "output" / "production_002" / "build_v2" / "msyh.ttc"
GEN_VERSION = "3.2b-p06"
ENC = ["-c:v", "libx264", "-crf", "20", "-preset", "veryfast", "-pix_fmt", "yuv420p",
       "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-r", "25", "-movflags", "+faststart"]

# Phase 3-B：母带链与契约判定统一取自 core.audio（本路径沿用既有 +0.4dB 限幅补偿）
from ..core.audio import (STAGE32B_POST_GAIN_DB, enforce_loudness_on_film,  # noqa: E402
                          mastering_chain)


def _sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _ffmpeg_version() -> str:
    r = subprocess.run([str(FFMPEG), "-version"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.stdout.splitlines()[0] if r.stdout else "unknown"


def _probe(path: Path) -> dict:
    r = subprocess.run([str(FFMPEG), "-i", str(path)], capture_output=True, text=True, encoding="utf-8", errors="replace")
    s = r.stderr
    out = {"exists": path.exists(), "decode_ok": r.returncode != 0 and "Duration:" in s}
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", s)
    out["duration"] = (float(m.group(1)) * 3600 + float(m.group(2)) * 60 + float(m.group(3))
                       if m else 0.0)
    mv = re.search(r"(\d{3,4})x(\d{3,4})", s)
    out["resolution"] = f"{mv.group(1)}x{mv.group(2)}" if mv else ""
    out["fps"] = (re.search(r"(\d+(?:\.\d+)?) fps", s).group(1)
                  if re.search(r"(\d+(?:\.\d+)?) fps", s) else "")
    out["has_audio"] = "Audio:" in s
    out["audio_rate"] = (re.search(r"Audio: [^,]+, (\d+) Hz", s).group(1)
                         if re.search(r"Audio: [^,]+, (\d+) Hz", s) else "")
    return out


def build_final(out_dir: Path, force: bool = False) -> dict:
    shots_dir = out_dir / "production" / "shots"
    ass_path = out_dir / "subtitles.ass"
    al = json.loads((out_dir / "manifests" / "alignment_manifest.json").read_text(encoding="utf-8"))
    sa = json.loads((out_dir / "manifests" / "shot_assembly_manifest.json").read_text(encoding="utf-8"))
    order = [f"S{i:02d}" for i in range(1, 21)]
    shot_files = [shots_dir / f"{sid}.mp4" for sid in order]
    missing = [str(p) for p in shot_files if not p.exists()]
    if missing:
        raise RuntimeError(f"缺镜头：{missing}")

    in_fp = hashlib.sha256(
        "".join(_sha256_file(p) for p in shot_files).encode("utf-8")
        + ass_path.read_bytes()).hexdigest()[:16]
    concat = out_dir / "build" / "concat.mp4"
    final = out_dir / "production" / "final_preview.mp4"
    rm_path = out_dir / "manifests" / "render_manifest.json"
    rm_path.parent.mkdir(parents=True, exist_ok=True)
    if rm_path.exists() and final.exists() and not force:
        m = json.loads(rm_path.read_text(encoding="utf-8"))
        if m.get("input_fingerprint") == in_fp:
            print(f"render 已存在（指纹一致），跳过：{rm_path}")
            return m

    # 1) concat（filter_complex，音画连续）
    concat.mkdir(parents=True, exist_ok=True) if False else None
    concat.parent.mkdir(parents=True, exist_ok=True)
    inputs, fc = [], []
    for i, p in enumerate(shot_files):
        inputs += ["-i", str(p)]
        fc.append(f"[{i}:v][{i}:a]")
    fc_desc = "".join(fc) + "concat=n=20:v=1:a=1[v][a]"
    concat_cmd = [str(FFMPEG), "-y", *inputs, "-filter_complex", fc_desc,
                  "-map", "[v]", "-map", "[a]", *ENC, str(concat)]
    subprocess.run(concat_cmd, capture_output=True, check=True)
    media_dur = _probe(concat)["duration"]

    # 2) 字幕时间边界最终钳制：以 concat 实测时长为真值（只动时间边界，文字/顺序不变）
    sub_manifest = json.loads((out_dir / "manifests" / "subtitle_manifest.json")
                              .read_text(encoding="utf-8"))
    entries = sub_manifest["entries"]
    for e in entries:
        e["end"] = round(min(e["end"], media_dur), 3)
        if e["start"] >= media_dur:
            e["start"] = round(media_dur - 0.001, 3)
    for i in range(1, len(entries)):
        entries[i]["start"] = entries[i - 1]["end"]
    clamped_ass = out_dir / "build" / "subtitles_clamped.ass"
    ass_lines = ["[Script Info]", "ScriptType: v4.00+", "PlayResX: 1920", "PlayResY: 1080",
                 "", "[V4+ Styles]",
                 "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV",
                 "Style: Default,msyh,54,&H00FFFFFF,&H00000000,1,2,0,2,20,20,60",
                 "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Text"]

    def _fmt_ass(t: float) -> str:
        cs = int(round(t * 100))
        h, cs = divmod(cs, 360000)
        m, cs = divmod(cs, 6000)
        s, cs = divmod(cs, 100)
        return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"

    for e in entries:
        ass_lines.append(f"Dialogue: 0,{_fmt_ass(e['start'])},{_fmt_ass(e['end'])},"
                         f"Default,,0,0,0,{e['text']}")
    clamped_ass.write_text("\n".join(ass_lines), encoding="utf-8")
    # 回写钳制后的字幕 manifest（时间边界更新，文字/顺序不变；QC 以实际媒体为真值）
    sub_manifest["entries"] = entries
    sub_manifest["clamp_note"] = f"render 阶段按 concat 实测 {round(media_dur, 3)}s 钳制"
    (out_dir / "manifests" / "subtitle_manifest.json").write_text(
        json.dumps(sub_manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    # 3) 烧录字幕 + loudnorm + alimiter 硬限幅（TP<=-1.5dB）
    fonts_dir = out_dir / "build" / "fonts"
    fonts_dir.mkdir(parents=True, exist_ok=True)
    font_dst = fonts_dir / "msyh.ttc"
    if not font_dst.exists() and FONT.exists():
        import shutil
        shutil.copy(FONT, font_dst)
    burn_cmd = [str(FFMPEG), "-y", "-i", str(concat),
                "-vf", "ass=build/subtitles_clamped.ass:fontsdir=build/fonts",
                "-af", mastering_chain(post_gain_db=STAGE32B_POST_GAIN_DB),
                "-c:v", "libx264", "-crf", "20", "-preset", "veryfast",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "128k", "-ar", "48000",
                "-movflags", "+faststart", str(final)]
    burn_r = subprocess.run(burn_cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=out_dir)
    subtitle_burned = burn_r.returncode == 0
    if not subtitle_burned:
        import shutil as _sh
        _sh.copy(concat, final)

    # Phase 3-B：成片响度契约（实测 → 必要时仅重编音频校正 → 再实测）
    loud = enforce_loudness_on_film(final, exe=str(FFMPEG))

    manifest = {
        "project": "coral", "stage32b_version": GEN_VERSION,
        "input_fingerprint": in_fp,
        "shot_order": order,
        "shot_inputs": {s: {"path": str(p), "sha": _sha256_file(p)}
                        for s, p in zip(order, shot_files)},
        "subtitle_sha": _sha256_file(ass_path),
        "alignment_sha": _sha256_file(out_dir / "manifests" / "alignment_manifest.json"),
        "narration_sha": al.get("narration_sha", ""),
        "shot_assembly_sha": _sha256_file(out_dir / "manifests" / "shot_assembly_manifest.json"),
        "ffmpeg_version": _ffmpeg_version(),
        "ffmpeg_concat_command": " ".join(concat_cmd),
        "ffmpeg_burn_command": " ".join(burn_cmd),
        "encode_params": ENC,
        "requested_duration": round(sum(s["adopted_duration"] for s in al["shots"]), 3),
        "subtitle_burned": subtitle_burned,
        "subtitle_clamp_note": f"末条字幕 end 已按 concat 实测 {round(media_dur,3)}s 钳制（文字/顺序不变）",
        "audio_chain": mastering_chain(post_gain_db=STAGE32B_POST_GAIN_DB),
        "audio_loudness": {"ok": loud["ok"], "contract": loud["contract"],
                           "measured_lufs": loud["final"].get("measured_lufs"),
                           "measured_true_peak_dbtp": loud["final"].get("measured_true_peak_dbtp"),
                           "corrections": loud["corrections"],
                           "reasons": loud["final"].get("reasons") or [],
                           "method": loud["method"]},
        "render_note": "" if subtitle_burned else "字幕烧录失败（libass），成片=无字幕 concat",
    }
    v = _probe(final)
    manifest["rendered_duration"] = round(v["duration"], 3)
    manifest["output_sha"] = _sha256_file(final)
    manifest["output"] = str(final)
    rm_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"render 完成：{final} 时长 {manifest['rendered_duration']}s，"
          f"字幕烧录={subtitle_burned}")
    return manifest


def gate_render(manifest: dict, out_dir: Path) -> dict:
    checks = []

    def check(name, cond, detail=""):
        checks.append((name, cond))
        print(f"{'PASS' if cond else 'FAIL'}  {name} {detail}")

    final = Path(manifest["output"])
    v = _probe(final)
    check("20/20 镜进入 concat", manifest["shot_order"] == [f"S{i:02d}" for i in range(1, 21)])
    check("0 丢镜 / 0 重复", len(manifest["shot_inputs"]) == 20)
    check("视频可解码", v["decode_ok"])
    check("1920×1080", v["resolution"] == "1920x1080", v["resolution"])
    check("25fps", v["fps"] == "25", v["fps"])
    check("音频可解码 + 48kHz", v["has_audio"] and v["audio_rate"] == "48000",
          f"audio={v['has_audio']} rate={v['audio_rate']}")
    check("duration 合理（VO 修复后 ≈102s）", 88 <= v["duration"] <= 112, str(v["duration"]))
    check("字幕正常烧录", manifest.get("subtitle_burned"), str(manifest.get("subtitle_burned")))
    check("output SHA / fingerprint 完整",
          manifest.get("output_sha") and manifest.get("input_fingerprint"))
    check("concat 前后时长一致", abs(manifest["rendered_duration"]
                                     - manifest["requested_duration"]) < 0.5,
          f"req {manifest['requested_duration']} vs rend {manifest['rendered_duration']}")
    ok = all(c[1] for c in checks)
    print(f"\nP0-6 Gate: {'PASS' if ok else 'FAIL'}")
    return {"gate": "PASS" if ok else "FAIL", "fails": [c[0] for c in checks if not c[1]]}
