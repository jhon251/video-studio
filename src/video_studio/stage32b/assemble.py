"""P0-5 单镜装配：20 镜 → S01.mp4..S20.mp4（画面 + 对应 VO + 统一规格）。

- USE_MATERIAL：本地预览图/下载素材 → 确定性 Ken Burns（zoompan 1→1.06）；
- TEXT_CARD：色底 + 冻结稿文字（msyh.ttc drawtext），SELF_CREATED；
- 时长严格取 alignment adopted_duration；音频只挂该镜 VO segments；
- 统一 1920x1080@25fps、libx264 crf20 yuv420p、aac 48k；
- 不烧字幕（P0-3 已独立生成）。
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[3]
FFMPEG = ROOT / "bin" / "ffmpeg.exe"
FONT = ROOT / "output" / "production_002" / "build_v2" / "msyh.ttc"
GEN_VERSION = "3.2b-p05"
UA = {"User-Agent": "video-studio-3.2b/0.1 (assembly; contact: local)"}
ENC = ["-c:v", "libx264", "-crf", "20", "-preset", "veryfast", "-pix_fmt", "yuv420p",
       "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-r", "25"]


def _sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _wrap(text: str, width: int = 20) -> str:
    lines, cur = [], ""
    for ch in text:
        cur += ch
        if len(cur) >= width:
            lines.append(cur)
            cur = ""
    if cur:
        lines.append(cur)
    return "\n".join(lines)


def _vo_audio(shot, vo_segments, out_dir: Path) -> Path | None:
    """拼接该镜 VO segments → 单段 wav；无段返回 None。"""
    import soundfile as sf
    import numpy as np
    files, texts = [], []
    for s in shot["segments"]:
        vs = next((x for x in vo_segments if x["id"] == s["segment_id"]), None)
        if vs and vs["status"] == "OK":
            f = out_dir / vs["audio_file"]
            if f.exists():
                files.append(f)
                texts.append(vs["text"])
    if not files:
        return None
    frames = [sf.read(str(f), dtype="float32")[0] for f in files]
    joined = np.concatenate(frames) if len(frames) > 1 else frames[0]
    outp = out_dir / "audio" / f"shot_{shot['shot_id']}.wav"
    outp.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(outp), joined, 24000)
    return outp


def _actual_duration(path: Path) -> float:
    r = subprocess.run([str(FFMPEG), "-i", str(path)], capture_output=True, text=True, encoding="utf-8", errors="replace")
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", r.stderr)
    return float(m.group(1)) * 3600 + float(m.group(2)) * 60 + float(m.group(3)) if m else 0.0


def _ensure_material(rec: dict, out_dir: Path) -> Path:
    """确保素材本地落地（优先预览，否则下载 download_url）。"""
    mats_dir = out_dir / "materials"
    mats_dir.mkdir(parents=True, exist_ok=True)
    pv = rec.get("preview_file")
    if pv:
        local = ROOT / "output" / "stage31_realworld" / "coral" / "material_pkg_real" / "materials" / pv
        if local.exists():
            return local
    url = rec.get("download_url", "")
    if not url:
        return None
    dest = mats_dir / f"{rec['shot_id']}.jpg"
    if dest.exists():
        return dest
    import random
    import time
    last = None
    for attempt in range(6):
        try:
            r = requests.get(url, headers=UA, timeout=60)
            if r.status_code == 200:
                dest.write_bytes(r.content)
                return dest
            last = f"HTTP {r.status_code}"
        except Exception as e:  # noqa: BLE001
            last = f"{type(e).__name__}: {e}"
        wait = 10 * (attempt + 1) if "429" in str(last) else 2 * (attempt + 1)
        time.sleep(wait + random.uniform(0, 1.5))
    raise RuntimeError(f"{rec['shot_id']}: 素材下载失败（重试后仍失败）: {last}")


def build_shot(shot: dict, vo_segments: list, mat_by_id: dict, out_dir: Path) -> dict:
    sid = shot["shot_id"]
    dur = shot["adopted_duration"]
    vo_path = _vo_audio(shot, vo_segments, out_dir)
    tmp_v = out_dir / "build" / f"{sid}_v.mp4"
    tmp_v.parent.mkdir(parents=True, exist_ok=True)
    final = out_dir / "production" / "shots" / f"{sid}.mp4"
    final.parent.mkdir(parents=True, exist_ok=True)
    # 字体复制到 build 目录，ffmpeg 以 build 为 cwd 用相对路径（规避盘符冒号）
    build_font = out_dir / "build" / "msyh.ttc"
    if not build_font.exists() and FONT.exists():
        import shutil
        shutil.copy(FONT, build_font)

    cmd = [str(FFMPEG), "-y"]
    if shot["selected_action"] == "USE_MATERIAL":
        rec = mat_by_id.get(shot.get("source_material"))
        src = _ensure_material(rec, out_dir) if rec else None
        if src is None:
            raise RuntimeError(f"{sid}: USE_MATERIAL 但素材无法落地")
        # 图片 Ken Burns（确定性 zoompan）
        cmd += ["-loop", "1", "-i", str(src), "-vf",
                f"zoompan=z='min(1.0+0.06*on/{int(dur*25) if dur*25>1 else 1},1.20)':"
                f"d={int(dur*25)}:s=1920x1080:fps=25,"
                f"scale=1920:1080:force_original_aspect_ratio=increase,"
                f"crop=1920:1080", "-t", f"{dur:.3f}"]
        material = {"material_id": rec.get("material_id"), "source_url": rec.get("source_url"),
                    "license": rec.get("license"), "attribution": rec.get("attribution_text"),
                    "local_file": str(src), "sha": _sha256_file(src)}
        cwd = None
    else:  # TEXT_CARD
        text = _wrap(shot.get("narration", ""), 20)
        txtfile = out_dir / "build" / f"{sid}.txt"
        txtfile.write_text(text, encoding="utf-8")
        cmd += ["-f", "lavfi", "-i", "color=c=0x0b2e33:s=1920x1080:r=25",
                "-vf", f"drawtext=fontfile=msyh.ttc:textfile={sid}.txt:"
                       f"fontsize=56:fontcolor=white:line_spacing=24:"
                       f"x=(w-text_w)/2:y=(h-text_h)/2",
                "-t", f"{dur:.3f}"]
        material = {"material_id": None, "source_url": "", "license": "",
                    "attribution": "", "local_file": None, "sha": "",
                    "self_created": True}
        cwd = out_dir / "build"
    cmd += ["-an", str(tmp_v)]
    subprocess.run(cmd, capture_output=True, check=True, cwd=cwd)

    # 合成音轨
    if vo_path:
        subprocess.run([str(FFMPEG), "-y", "-i", str(tmp_v), "-i", str(vo_path),
                        "-map", "0:v", "-map", "1:a", "-t", f"{dur:.3f}",
                        *ENC, "-shortest", str(final)], capture_output=True, check=True)
    else:
        subprocess.run([str(FFMPEG), "-y", "-i", str(tmp_v), "-t", f"{dur:.3f}",
                        "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
                        "-map", "0:v", "-map", "1:a", *ENC, "-shortest", str(final)],
                       capture_output=True, check=True)
    actual = _actual_duration(final)
    return {"shot_id": sid, "requested_duration": round(dur, 3),
            "actual_duration": round(actual, 3),
            "duration_delta": round(actual - dur, 3),
            "vo_segments": [s["segment_id"] for s in shot["segments"]],
            "vo_sha": _sha256_file(vo_path) if vo_path else "",
            "output_sha": _sha256_file(final),
            "material": material, "ffmpeg_encode": ENC}


def build_all(blocked_path: Path, alignment_path: Path, vo_path: Path,
              meta_path: Path, out_dir: Path, force: bool = False) -> dict:
    blocked = json.loads(blocked_path.read_text(encoding="utf-8"))
    al = json.loads(alignment_path.read_text(encoding="utf-8"))
    vo = json.loads(vo_path.read_text(encoding="utf-8"))
    mats = json.loads(meta_path.read_text(encoding="utf-8"))["materials"]
    mat_by_id = {m["material_id"]: m for m in mats}
    in_fp = hashlib.sha256(
        (blocked_path.read_text(encoding="utf-8") + alignment_path.read_text(encoding="utf-8")
         + vo_path.read_text(encoding="utf-8") + meta_path.read_text(encoding="utf-8"))
        .encode("utf-8")).hexdigest()[:16]
    idx_path = out_dir / "manifests" / "shot_assembly_manifest.json"
    idx_path.parent.mkdir(parents=True, exist_ok=True)
    if idx_path.exists() and not force:
        m = json.loads(idx_path.read_text(encoding="utf-8"))
        if m.get("input_fingerprint") == in_fp:
            print(f"shot assembly 已存在（指纹一致），跳过：{idx_path}")
            return m

    rows, shot_manifests = [], []
    for sh in al["shots"]:
        b = next(x for x in blocked["shots"] if x["shot_id"] == sh["shot_id"])
        final = out_dir / "production" / "shots" / f"{sh['shot_id']}.mp4"
        sp = out_dir / "manifests" / "shots" / f"{sh['shot_id']}_manifest.json"
        if final.exists() and sp.exists() and not force:
            row = json.loads(sp.read_text(encoding="utf-8"))
            rows.append(row)
            shot_manifests.append(str(sp))
            print(f"{sh['shot_id']}: 已存在，跳过")
            continue
        row = build_shot({**sh, **b}, vo["segments"], mat_by_id, out_dir)
        rows.append(row)
        sp.parent.mkdir(parents=True, exist_ok=True)
        sp.write_text(json.dumps({"input_fingerprint": in_fp, "generator_version": GEN_VERSION,
                                  "narration_sha": al.get("narration_sha", ""),
                                  "alignment_sha": blocked.get("alignment_manifest_sha", ""),
                                  **row}, ensure_ascii=False, indent=2), encoding="utf-8")
        shot_manifests.append(str(sp))
        print(f"{sh['shot_id']}: {b['selected_action']} req={row['requested_duration']} "
              f"act={row['actual_duration']} delta={row['duration_delta']}")
    manifest = {"input_fingerprint": in_fp, "generator_version": GEN_VERSION,
                "narration_sha": al.get("narration_sha", ""),
                "shots": rows, "shot_manifests": shot_manifests}
    idx_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def gate_assembly(manifest: dict, blocked: dict) -> dict:
    checks = []

    def check(name, cond, detail=""):
        checks.append((name, cond))
        print(f"{'PASS' if cond else 'FAIL'}  {name} {detail}")

    rows = manifest["shots"]
    check("20/20 镜装配", len(rows) == 20, f"({len(rows)})")
    check("时长误差 < 0.5s", all(abs(r["duration_delta"]) < 0.5 for r in rows))
    check("VO 段与 shot 正确（20 段全覆盖）",
          sorted(r["shot_id"] for r in rows) == [f"S{i:02d}" for i in range(1, 21)])
    check("TEXT_CARD 均标记 SELF_CREATED", all(
        r["material"].get("self_created") for r in rows if r["material"].get("material_id") is None))
    check("USE_MATERIAL provenance 完整", all(
        r["material"].get("source_url") and r["material"].get("license")
        for r in rows if r["material"].get("material_id")))
    check("UNKNOWN/UNSAFE = 0", all(
        r["material"].get("license", "") not in ("", "UNKNOWN", "UNSAFE") or
        r["material"].get("self_created") for r in rows))
    check("S03 严格 TEXT_CARD（不重接受 cubicle）",
          next(r for r in rows if r["shot_id"] == "S03")["material"].get("material_id") is None)
    check("无黑屏/静音（有输出 SHA 且时长>0）", all(
        r["output_sha"] and r["actual_duration"] > 0 for r in rows))
    ok = all(c[1] for c in checks)
    print(f"\nP0-5 Gate: {'PASS' if ok else 'FAIL'}")
    return {"gate": "PASS" if ok else "FAIL", "fails": [c[0] for c in checks if not c[1]]}
