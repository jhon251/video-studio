"""executor（v3-mvp）：Visual Statement 帧规格 → 帧渲染 → 3.2b 兼容工件 → 成片。

运动渲染：PIL 逐帧（整数裁剪矩形/整数 alpha）→ rawvideo 管道 → ffmpeg。
**废除 zoompan / 正弦微动 / 亚像素浮点。** HOLD = 同一帧重复（帧差恒 0）。
只读：冻结 v3 plan、3.2b coral（VO/字幕/manifests）、Material Package metadata。
"""
from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path

import requests
from PIL import Image

from video_studio.stage33 import graphics

ROOT = Path(__file__).resolve().parents[3]
FFMPEG = ROOT / "bin" / "ffmpeg.exe"
FONT = ROOT / "output" / "production_002" / "build_v2" / "msyh.ttc"
CORAL32B = ROOT / "output" / "stage32b" / "coral"
PKG = ROOT / "output" / "stage31_realworld" / "coral"
ENC = ["-c:v", "libx264", "-crf", "20", "-preset", "veryfast", "-pix_fmt", "yuv420p",
       "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-r", "25"]
UA = {"User-Agent": "video-studio-3.3-v3/0.1 (execution; contact: local)"}
W, H = 1920, 1080


def _sha256_file(p: Path) -> str:
    import hashlib
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _material_local(material_id: str, meta: dict) -> Path | None:
    for d in (PKG / "material_pkg_real" / "materials", CORAL32B / "materials"):
        if d.exists():
            for f in d.iterdir():
                if material_id.lower() in f.name.lower():
                    return f
    sa = json.loads((CORAL32B / "manifests" / "shot_assembly_manifest.json")
                    .read_text(encoding="utf-8"))
    for row in sa["shots"]:
        m = row.get("material", {})
        if m.get("material_id") == material_id and m.get("local_file"):
            p = Path(m["local_file"])
            if p.exists():
                return p
    return None


def _download_material(material_id: str, meta: dict, out_dir: Path) -> Path | None:
    rec = next((m for m in meta["materials"] if m["material_id"] == material_id), None)
    if not rec:
        return None
    url = rec.get("download_url") or rec.get("original_url") or ""
    if not url:
        return None
    urls = [url]
    if rec.get("original_url") and rec["original_url"] != url:
        urls.append(rec["original_url"])
    ct = rec.get("content_type", "image")
    ext = "mp4" if ct == "video" else ("png" if urls[0].endswith(".png") else "jpg")
    dest = out_dir / "materials" / f"{material_id}.{ext}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        return dest
    import random
    last = None
    for attempt in range(6):
        u = urls[0] if attempt < 4 else urls[-1]
        try:
            r = requests.get(u, headers=UA, timeout=90)
            if r.status_code == 200:
                dest.write_bytes(r.content)
                return dest
            last = f"HTTP {r.status_code}"
        except Exception as e:  # noqa: BLE001
            last = f"{type(e).__name__}: {e}"
        time.sleep(10 * (attempt + 1) + random.uniform(0, 2))
    print(f"[executor] {material_id}: 下载失败（{last}）→ 该 beat 无素材层（锚点构图）")
    return None


def _probe_dur(path: Path) -> float:
    r = subprocess.run([str(FFMPEG), "-i", str(path)], capture_output=True, text=True, encoding="utf-8", errors="replace")
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", r.stderr)
    return (float(m.group(1)) * 3600 + float(m.group(2)) * 60 + float(m.group(3))
            if m else 0.0)


def _cover_resize(img: Image.Image) -> Image.Image:
    """等比放大到覆盖 1920×1080 后中心裁剪（等价 force_original_aspect_ratio=increase）。"""
    w, h = img.size
    if w == W and h == H:
        return img
    scale = max(W / w, H / h)
    nw, nh = int(w * scale + 0.5), int(h * scale + 0.5)
    img = img.resize((nw, nh), Image.LANCZOS)
    x = (nw - W) // 2
    y = (nh - H) // 2
    return img.crop((x, y, x + W, y + H))


def _video_frames(src: Path, n: int, tmp_dir: Path) -> list[Path] | None:
    """视频素材 → 帧序列（PIL 消费）。短片自动循环补满时长。"""
    tmp_dir.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
        [str(FFMPEG), "-y", "-hide_banner", "-loglevel", "error", "-stream_loop", "-1",
         "-i", str(src), "-vf", "fps=25,scale=1920:1080:force_original_aspect_ratio=increase,"
                              "crop=1920:1080", "-frames:v", str(n),
         "-q:v", "2", str(tmp_dir / "f%05d.png")],
        capture_output=True)
    if r.returncode != 0:
        return None
    frames = sorted(tmp_dir.glob("f*.png"))
    return frames[:n] if frames else None


def _render_beat(spec: dict, out: Path, style: dict, meta: dict,
                 work_dir: Path, beat_times: dict) -> None:
    # 绝对时间边界 → 帧数（修复 per-beat int() 截断漂移）；spec.n_frames 仅作参考
    from video_studio.stage33.motion import frame_range
    n = frame_range(beat_times["start"], beat_times["end"])
    spec["_rendered_n_frames"] = n
    # 各层帧级数组补齐到 n（尾部重复末值：静态/淡出保持正确）
    for l in spec["layers"]:
        if "alpha_frames" in l:
            a = l["alpha_frames"]
            l["alpha_frames"] = (a + [a[-1]] * n)[:n] if a else [255] * n
        if l.get("rects"):
            r = l["rects"]
            l["rects"] = (r + [r[-1]] * n)[:n]
        if l.get("shift_frames"):
            s = l["shift_frames"]
            l["shift_frames"] = (s + [s[-1]] * n)[:n]
    pal = style["palette"]
    mat_frames: list[Image.Image] | None = None
    mat_layer = next((l for l in spec["layers"] if l["kind"] == "material"), None)
    if mat_layer is not None:
        mid = mat_layer["material_id"]
        src = _material_local(mid, meta) or _download_material(mid, meta, work_dir)
        if src is None:
            spec["layers"] = [l for l in spec["layers"] if l["kind"] != "material"]
            spec["material_dropped"] = True
            mat_layer = None
        else:
            is_video = _probe_dur(src) > 0.5 and src.suffix.lower() in (
                ".mp4", ".webm", ".ogv", ".mov")
            if is_video:
                frames = _video_frames(src, n, work_dir / "vf" / spec["beat_id"])
                mat_frames = [Image.open(f).convert("RGB") for f in (frames or [])]
                if mat_frames:
                    mat_frames = (mat_frames + [mat_frames[-1]] * n)[:n]
            else:
                mat_frames = [_cover_resize(Image.open(src).convert("RGB"))] * n

    base_rgb = graphics.hex_rgb(pal["bg"])
    # 预渲染文本层（每帧 anchor 位置可能随 shift 变化）
    text_layers = []
    for li, l in enumerate(spec["layers"]):
        if l["kind"] == "anchor_text":
            ax, ay = l["anchor"]
            shifts = l.get("shift_frames")
            for i in range(n):
                sx, sy = (shifts[i] if shifts else (0, 0))
                lay, _ = graphics.anchor_text(
                    l["text"], l["font_size"], graphics.hex_rgb(l["color"]),
                    stroke=l.get("stroke", 0), anchor_pos=(ax + sx, ay + sy))
                text_layers.append((li, i, lay))
        elif l["kind"] == "rounded_rect":
            rect_layers = {}
            for i in range(n):
                rect_layers[i] = graphics.rounded_mask(
                    tuple(l["rect"]), l["radius"], graphics.hex_rgb(l["color"]))
            spec.setdefault("_rect_cache", {}).update(rect_layers)

    frames_rgb = []
    for i in range(n):
        if mat_frames is not None and mat_layer is not None:
            rects = mat_layer.get("rects")
            img = mat_frames[i]
            if rects:
                x, y, w, h = rects[i]
                img = img.crop((x, y, x + w, y + h)).resize((W, H), Image.LANCZOS)
            base = img
        else:
            base = graphics.color_canvas(base_rgb)
        comp = []
        for l in spec["layers"]:
            if l["kind"] == "material":
                continue
            if l["kind"] == "color":
                # 底色只作为无素材时的背板；素材存在时绝不覆盖（z-order: 素材在上）
                continue
            a = l["alpha_frames"][i] if i < len(l["alpha_frames"]) else 255
            if l["kind"] == "color":
                comp.append((graphics.color_canvas(graphics.hex_rgb(l["color"])).convert("RGBA"), a))
            elif l["kind"] == "rounded_rect":
                comp.append((spec["_rect_cache"][i], a))
            elif l["kind"] == "anchor_text":
                hit = next((lay for (li, j, lay) in text_layers if li == spec["layers"].index(l)
                            and j == i), None)
                if hit is not None:
                    comp.append((hit, a))
        frames_rgb.append(graphics.compose(base, comp).tobytes())

    proc = subprocess.Popen(
        [str(FFMPEG), "-y", "-hide_banner", "-loglevel", "error",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-framerate", "25",
         "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
         "-pix_fmt", "yuv420p", "-r", "25", str(out)],
        stdin=subprocess.PIPE)
    for f in frames_rgb:
        proc.stdin.write(f)
    proc.stdin.close()
    proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(f"beat 编码失败: {out}")


def _shot_audio(shot_id: str, vo: dict, out_dir: Path) -> Path | None:
    import numpy as np
    import soundfile as sf
    segs = [s for s in vo["segments"] if s["shot_id"] == shot_id and s["status"] == "OK"]
    frames = []
    for s in segs:
        f = CORAL32B / s["audio_file"]
        if f.exists():
            frames.append(sf.read(str(f), dtype="float32")[0])
    if not frames:
        return None
    joined = np.concatenate(frames) if len(frames) > 1 else frames[0]
    outp = out_dir / "audio" / f"shot_{shot_id}.wav"
    outp.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(outp), joined, 24000)
    return outp


def execute_v3(plan: dict, exec_dir: Path, force: bool = False) -> dict:
    exec_dir.mkdir(parents=True, exist_ok=True)
    style = plan.get("style_contract", {})
    meta = json.loads((PKG / "material_pkg_real" / "metadata" / "materials.json")
                      .read_text(encoding="utf-8"))
    vo = json.loads((CORAL32B / "manifests" / "vo_manifest.json").read_text(encoding="utf-8"))
    shots_dir = exec_dir / "production" / "shots"
    shots_dir.mkdir(parents=True, exist_ok=True)
    beats_dir = exec_dir / "build" / "beats"
    beats_dir.mkdir(parents=True, exist_ok=True)
    if not (exec_dir / "build" / "msyh.ttc").exists() and FONT.exists():
        import shutil
        shutil.copy(FONT, exec_dir / "build" / "msyh.ttc")

    beats_by_shot: dict[str, list] = {}
    for b in plan["beats"]:
        beats_by_shot.setdefault(b["shot_id"], []).append(b)

    rows = []
    for sid in [f"S{i:02d}" for i in range(1, 21)]:
        beats = beats_by_shot.get(sid, [])
        clips = []
        for b in beats:
            clip = beats_dir / f"{b['beat_id']}.mp4"
            _render_beat(b["spec"], clip, style, meta, exec_dir,
                         {"start": b["start"], "end": b["end"]})
            clips.append(clip)
        tmp_v = exec_dir / "build" / f"{sid}_v.mp4"
        if len(clips) == 1:
            tmp_v = clips[0]
        else:
            inputs = []
            for c in clips:
                inputs += ["-i", str(c)]
            fc = "".join(f"[{i}:v]" for i in range(len(clips))) + \
                 f"concat=n={len(clips)}:v=1:a=0[v]"
            subprocess.run([str(FFMPEG), "-y", *inputs, "-filter_complex", fc,
                            "-map", "[v]", "-c:v", "libx264", "-crf", "18",
                            "-preset", "veryfast", "-pix_fmt", "yuv420p", "-r", "25",
                            str(tmp_v)], capture_output=True, check=True)
        dur = sum(b["duration"] for b in beats)
        final = shots_dir / f"{sid}.mp4"
        wav = _shot_audio(sid, vo, exec_dir)
        subprocess.run([str(FFMPEG), "-y", "-i", str(tmp_v), "-i", str(wav),
                        "-map", "0:v", "-map", "1:a", "-t", f"{dur:.3f}",
                        *ENC, "-shortest", str(final)], capture_output=True, check=True)
        rows.append({"shot_id": sid, "requested_duration": round(dur, 3),
                     "actual_duration": round(_probe_dur(final), 3),
                     "vo_segments": [s["id"] for s in vo["segments"] if s["shot_id"] == sid],
                     "output_sha": _sha256_file(final),
                     "material": {"self_created": True},
                     "ffmpeg_encode": ENC,
                     "beat_specs": {b["beat_id"]: {
                         "motion_intent": b["spec"]["motion_intent"],
                         "motion_note": b["spec"].get("motion_note"),
                         "anchor_text": b["spec"]["anchor_text"],
                         "material_dropped": b["spec"].get("material_dropped", False)}
                         for b in beats}})

    mdir = exec_dir / "manifests"
    mdir.mkdir(parents=True, exist_ok=True)
    for name in ("alignment_manifest.json", "vo_manifest.json",
                 "subtitle_manifest.json", "blocked_manifest.json"):
        (mdir / name).write_bytes((CORAL32B / "manifests" / name).read_bytes())
    (exec_dir / "subtitles.ass").write_bytes((CORAL32B / "subtitles.ass").read_bytes())
    seg_src, seg_dst = CORAL32B / "audio" / "segments", exec_dir / "audio" / "segments"
    seg_dst.mkdir(parents=True, exist_ok=True)
    for f in seg_src.iterdir():
        if not (seg_dst / f.name).exists():
            (seg_dst / f.name).write_bytes(f.read_bytes())
    sa_manifest = {"input_fingerprint": plan.get("plan_sha", "")[:16],
                   "generator_version": "3.3-v3-mvp-exec",
                   "narration_sha": plan.get("inputs", {}).get("narration_sha", ""),
                   "plan_sha": plan.get("plan_sha", ""),
                   "shots": rows}
    (mdir / "shot_assembly_manifest.json").write_text(
        json.dumps(sa_manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    from video_studio.stage32b.render import build_final as bf, gate_render
    rm = bf(exec_dir, force=True)
    g = gate_render(rm, exec_dir)
    from video_studio.stage32b.qc import run_qc, gate_qc
    qc_report = run_qc(exec_dir)
    qg = gate_qc(qc_report, exec_dir)
    return {"render_manifest": rm, "render_gate": g, "qc_report": qc_report,
            "qc_gate": qg, "shot_assembly": sa_manifest}
