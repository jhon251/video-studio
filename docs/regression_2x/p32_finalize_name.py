# -*- coding: utf-8 -*-
"""P32-4：把最终 H7 产物规范命名为 `*_with_outro_v2.mp4`（**TS 拼接修正版**），
并更新 fixture 记录（含视频轨覆盖与音轨一致性核验）。

背景：首版 H7 用 MP4 `-c copy` concat，接头时间戳断裂 ⇒ 视频轨仅 975.73s（补齐缺陷）；
修正版改用 MPEG-TS 中间格式 ⇒ 视频轨 977.93s 满覆盖。命名保留 `_v2` 以**避免歧义**。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
FF = str(R / "bin" / "ffmpeg.exe")
FFPROBE = str(R / "bin" / "ffprobe.exe")
SB = R / "output" / "phase32_p32_4_sandbox"
sys.stdout.reconfigure(encoding="utf-8")


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def dur(p, kind="format"):
    ent = "format=duration" if kind == "format" else "stream=duration"
    sel = [] if kind == "format" else ["-select_streams", kind]
    r = subprocess.run([FFPROBE, "-v", "error", *sel, "-show_entries", ent,
                        "-of", "default=nw=1:nk=1", str(p)],
                       capture_output=True, text=True)
    v = (r.stdout or "").strip().splitlines()
    return round(float(v[0]), 3) if v and v[0] else None


def audio_hash(p):
    r = subprocess.run([FF, "-v", "error", "-i", str(p), "-map", "0:a:0", "-c", "copy",
                        "-f", "streamhash", "-hash", "sha256", "-"],
                       capture_output=True, text=True)
    return (r.stdout or "").strip()


def main() -> int:
    fx_p = SB / "fixture.json"
    fx = json.loads(fx_p.read_text(encoding="utf-8"))
    pid = fx["sandbox_project_id"]
    pdir = R / "projects" / pid / "output"
    base = next(f for f in sorted(pdir.glob("*.mp4")) if "with_outro" not in f.name)
    plain = next((f for f in sorted(pdir.glob("*with_outro.mp4"))), None)
    final = pdir / (base.stem + "_with_outro_v2.mp4")
    if plain and plain != final:
        if final.exists():
            final.unlink()
        plain.rename(final)
        print("重命名: {} -> {}".format(plain.name, final.name))
    info = {
        "base_film": str(base.relative_to(R)).replace("\\", "/"),
        "final_film": str(final.relative_to(R)).replace("\\", "/"),
        "final_bytes": final.stat().st_size,
        "container_duration_s": dur(final),
        "base_container_duration_s": dur(base),
        "video_track_duration_s": dur(final, "v:0"),
        "base_video_track_duration_s": dur(base, "v:0"),
        "video_track_full_cover": (dur(final, "v:0") or 0) >= (dur(final) or 0) - 0.1,
        "audio_streamhash": audio_hash(final),
        "base_audio_streamhash": audio_hash(base),
        "audio_identical": audio_hash(final) == audio_hash(base),
        "outro_impl": "mpegts concat stream-copy (P32-4 corrected)",
        "note": ("首版 MP4-concat 产物视频轨仅 975.73s（补齐缺陷）⇒ 已弃用；"
                 "本文件为 TS 拼接修正版。"),
    }
    fx["outro_final"] = info
    fx_p.write_text(json.dumps(fx, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(info, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
