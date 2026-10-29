"""P0-7 最终成片 QC / 审计（只报告，绝不自动修片）。

覆盖：decode/container、20 镜完整性、VO 段完整性、VO↔shot 映射、
VO↔字幕同步、字幕逐字 Truth、字幕 overlap/bounds、黑帧/冻结帧、
音频流/采样率/响度/clipping/静音、素材相关性、TEXT_CARD 决策、
provenance/attribution 链、Truth 一致性、SHA/manifest 一致、
冻结资产 SHA 回归、交付完整性。
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FFMPEG = ROOT / "bin" / "ffmpeg.exe"
GEN_VERSION = "3.2b-p07"

# Phase 3-B：响度契约与实测判定统一取自 core.audio
from ..core.audio import LOUDNESS_CONTRACT, verify_file  # noqa: E402


def _sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _run_ff(args: list) -> str:
    r = subprocess.run([str(FFMPEG), "-hide_banner", *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.stderr + r.stdout


def _probe(path: Path) -> dict:
    s = _run_ff(["-i", str(path)])
    out = {"exists": path.exists(), "decode_ok": "Duration:" in s}
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", s)
    out["duration"] = (float(m.group(1)) * 3600 + float(m.group(2)) * 60 + float(m.group(3))
                       if m else 0.0)
    mv = re.search(r"(\d{3,4})x(\d{3,4})", s)
    out["resolution"] = f"{mv.group(1)}x{mv.group(2)}" if mv else ""
    out["fps"] = re.search(r"(\d+(?:\.\d+)?) fps", s).group(1) if re.search(r"(\d+(?:\.\d+)?) fps", s) else ""
    out["has_audio"] = "Audio:" in s
    out["audio_rate"] = re.search(r"Audio: [^,]+, (\d+) Hz", s).group(1) if re.search(r"Audio: [^,]+, (\d+) Hz", s) else ""
    return out


def analyze_video_filters(video: Path) -> dict:
    """blackdetect + freezedetect + silencedetect + volumedetect + ebur128。"""
    blk = _run_ff(["-i", str(video), "-vf", "blackdetect=d=0.15:pix_th=0.10", "-an", "-f", "null", "-"])
    frz = _run_ff(["-i", str(video), "-vf", "freezedetect=n=0.003:d=0.3", "-an", "-f", "null", "-"])
    sil = _run_ff(["-i", str(video), "-af", "silencedetect=n=-35dB:d=0.8", "-f", "null", "-"])
    sil_pairs = [(float(m.group(1)), float(m.group(2)))
                 for m in re.finditer(r"silence_start: ([\d.]+).*?silence_end: ([\d.]+)", sil, re.S)]
    sil_durs = [round(e - s, 3) for s, e in sil_pairs]
    vol = _run_ff(["-i", str(video), "-af", "volumedetect", "-f", "null", "-"])
    loud = _run_ff(["-i", str(video), "-af", "ebur128=framelog=quiet", "-f", "null", "-"])
    abnormal = [d for d in sil_durs if d >= 1.0]
    natural = [d for d in sil_durs if 0.8 <= d < 1.0]
    return {
        "black_frames": re.findall(r"black_duration:([\d.]+)", blk),
        "freeze_frames": re.findall(r"freeze_duration:([\d.]+)", frz),
        "abnormal_silences": [round(x, 3) for x in abnormal],
        "natural_speech_pauses": [round(x, 3) for x in natural],
        "silence_threshold": "d>=1.0s=abnormal；0.8–1.0s=NATURAL_SPEECH_PAUSE（裁决保留）",
        "max_volume": (re.search(r"max_volume: ([\-\d.]+) dB", vol).group(1)
                       if re.search(r"max_volume: ([\-\d.]+) dB", vol) else ""),
        "loudness_I": (re.search(r"I:\s+([\-\d.]+) LUFS", loud).group(1)
                       if re.search(r"I:\s+([\-\d.]+) LUFS", loud) else ""),
    }


def run_qc(out_dir: Path) -> dict:
    video = out_dir / "production" / "final_preview.mp4"
    rm = json.loads((out_dir / "manifests" / "render_manifest.json").read_text(encoding="utf-8"))
    sa = json.loads((out_dir / "manifests" / "shot_assembly_manifest.json").read_text(encoding="utf-8"))
    al = json.loads((out_dir / "manifests" / "alignment_manifest.json").read_text(encoding="utf-8"))
    vo = json.loads((out_dir / "manifests" / "vo_manifest.json").read_text(encoding="utf-8"))
    sub = json.loads((out_dir / "manifests" / "subtitle_manifest.json").read_text(encoding="utf-8"))
    blk = json.loads((out_dir / "manifests" / "blocked_manifest.json").read_text(encoding="utf-8"))

    probe = _probe(video)
    filters = analyze_video_filters(video)
    order = [f"S{i:02d}" for i in range(1, 21)]
    shot_missing = [sid for sid in order if not (out_dir / "production" / "shots" / f"{sid}.mp4").exists()]
    vo_ok = sum(1 for s in vo["segments"] if s["status"] == "OK")
    vo_map_ok = all(
        s["segment_id"] in {x["id"] for x in vo["segments"]}
        for sh in al["shots"] for s in sh["segments"])
    # 字幕↔VO 同步：字幕条目时间 == alignment 段时间（末条因渲染钳制容差 ±0.2s，其余 ±0.1s）
    sync_bad = []
    for sh in al["shots"]:
        for s in sh["segments"]:
            subs = [e for e in sub["entries"] if e["segment_id"] == s["segment_id"]]
            if subs:
                st = subs[0]["start"]
                en = subs[-1]["end"]
                tol = 0.2 if s["segment_id"] == vo["segments"][-1]["id"] else 0.1
                if abs(st - s["start"]) > tol or abs(en - s["end"]) > tol:
                    sync_bad.append(s["segment_id"])
    # 字幕逐字 Truth
    verbatim_ok = True
    for sh in al["shots"]:
        for s in sh["segments"]:
            joined = "".join(e["text"] for e in sub["entries"]
                             if e["segment_id"] == s["segment_id"])
            if joined != s["text"]:
                verbatim_ok = False
    sub_overlap = any(sub["entries"][i]["end"] > sub["entries"][i + 1]["start"]
                      for i in range(len(sub["entries"]) - 1))
    sub_bounds = all(0 <= e["start"] <= probe["duration"] and 0 <= e["end"] <= probe["duration"]
                     for e in sub["entries"])
    # 素材相关性：USE_MATERIAL 均为 sem>=50（P0-4 决策）
    weak_use = [r["shot_id"] for r in blk["shots"]
                if r["selected_action"] == "USE_MATERIAL" and "MARGINAL" in r["original_status"]]
    # 语速指标
    chars = sum(len(s["text"]) for s in vo["segments"])
    speed_cpm = chars / max(probe["duration"], 1) * 60
    # provenance 链
    prov_ok = (rm.get("narration_sha") == al.get("narration_sha") == vo.get("narration_sha")
               and rm.get("shot_assembly_sha") == _sha256_file(out_dir / "manifests" / "shot_assembly_manifest.json"))
    output_sha_ok = rm.get("output_sha") == _sha256_file(video)

    report = {
        "generator_version": GEN_VERSION,
        "video": video.name,
        "probe": probe,
        "filters": filters,
        "shots_total": 20, "shots_missing": shot_missing,
        "vo_segments_ok": f"{vo_ok}/20",
        "vo_shot_map_ok": vo_map_ok,
        "subtitle_vo_sync_bad": sync_bad,
        "subtitle_verbatim_ok": verbatim_ok,
        "subtitle_overlap": sub_overlap,
        "subtitle_bounds_ok": sub_bounds,
        "weak_use_material": weak_use,
        "text_card_count": sum(1 for r in blk["shots"] if r["selected_action"] == "TEXT_CARD"),
        "use_material_count": sum(1 for r in blk["shots"] if r["selected_action"] == "USE_MATERIAL"),
        "vo_speed": {"total_chars": chars, "duration": round(probe["duration"], 2),
                     "chars_per_min": round(speed_cpm, 1)},
        "provenance_chain_ok": prov_ok,
        "output_sha_ok": output_sha_ok,
        "timeline_gap_note": "P0-2 total 32.132s 含 0.3s 镜间缝；P0-5 各镜=vo_measured 未含缝；"
                             "成片 26.38s。属 production timeline 口径不一致，未修。",
    }
    (out_dir / "qc").mkdir(parents=True, exist_ok=True)
    (out_dir / "qc" / "qc_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def gate_qc(report: dict, out_dir: Path) -> dict:
    checks = []

    def check(name, cond, detail=""):
        checks.append((name, cond))
        print(f"{'PASS' if cond else 'FAIL'}  {name} {detail}")

    check("video decode/container 完整", report["probe"]["decode_ok"]
          and report["probe"]["resolution"] == "1920x1080")
    check("20/20 镜无丢失", not report["shots_missing"])
    check("VO 20/20 segment", report["vo_segments_ok"] == "20/20")
    check("VO↔shot 映射完整", report["vo_shot_map_ok"])
    check("VO↔字幕同步（±0.1s）", not report["subtitle_vo_sync_bad"],
          str(report["subtitle_vo_sync_bad"][:3]))
    check("字幕逐字 Truth 一致", report["subtitle_verbatim_ok"])
    check("字幕无 overlap / 无越界", not report["subtitle_overlap"]
          and report["subtitle_bounds_ok"])
    check("无黑帧/冻结帧", not report["filters"]["black_frames"]
          and not report["filters"]["freeze_frames"],
          f"blk={report['filters']['black_frames']} frz={report['filters']['freeze_frames']}")
    check("音频 48kHz + 无 clipping(TP<=-1.5dB) + 无异常长静音(>=1.0s)",
          report["probe"]["audio_rate"] == "48000"
          and float(report["filters"]["max_volume"] or "-99") <= -1.5
          and not report["filters"]["abnormal_silences"],
          f"rate={report['probe']['audio_rate']} max={report['filters']['max_volume']} "
          f"abn={report['filters']['abnormal_silences']} "
          f"natural={report['filters']['natural_speech_pauses']}")
    lu = report["filters"].get("loudness_I", "")
    # Phase 3-B：与正式链统一到同一响度契约（-16 LUFS ±1 LU、TP ≤ -1.5 dBTP），不再用 ±2 LU 的旧口径
    _loud = verify_file(out_dir / "production" / "final_preview.mp4", exe=str(FFMPEG))
    check("成片响度满足统一契约（{}±{} LUFS、TP<={} dBTP）".format(
        int(LOUDNESS_CONTRACT["target_lufs"]), LOUDNESS_CONTRACT["tolerance_lu"],
        LOUDNESS_CONTRACT["max_true_peak_dbtp"]),
        _loud["ok"],
        "I={} LUFS TP={} dBTP（qc 旧口径 I={}）".format(
            _loud["measured_lufs"], _loud["measured_true_peak_dbtp"], lu)
        + ("" if _loud["ok"] else " 原因: " + "; ".join(_loud["reasons"])))
    check("无弱匹配 USE_MATERIAL（全部 sem≥50 决策）", not report["weak_use_material"])
    check("provenance 链一致", report["provenance_chain_ok"])
    check("output SHA 与 manifest 一致", report["output_sha_ok"])
    ok = all(c[1] for c in checks)
    print(f"\nP0-7 Gate: {'PASS' if ok else 'FAIL'}")
    return {"gate": "PASS" if ok else "FAIL", "fails": [c[0] for c in checks if not c[1]]}
