# -*- coding: utf-8 -*-
"""P33-4：**登记第二部交付级候选**（append-only、零 promotion）。

与 P32 的差异：本轮渲染链**在全门通过后已自行登记** `render_output` / `attribution`
（实测 `p_23cd348beed8` 与 `p_cf8513debb2e` 均有），故**无需为登记再渲一次**；
本脚本只做：规范化 H7 产物命名 → 核验 → append 登记记录。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys
import time

R = pathlib.Path(r"C:\mp4agent\video-studio")
SB = R / "output" / "phase33_p33_4_sandbox"
L = R / "docs" / "regression_2x" / "logs"
FF = str(R / "bin" / "ffmpeg.exe")
FFPROBE = str(R / "bin" / "ffprobe.exe")
sys.stdout.reconfigure(encoding="utf-8")


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def dur(p, kind="format"):
    ent = "format=duration" if kind == "format" else "stream=duration"
    sel = [] if kind == "format" else ["-select_streams", kind]
    r = subprocess.run([FFPROBE, "-v", "error", *sel, "-show_entries", ent,
                        "-of", "default=nw=1:nk=1", str(p)], capture_output=True, text=True)
    v = (r.stdout or "").strip().splitlines()
    return round(float(v[0]), 3) if v and v[0] else None


def audio_hash(p):
    r = subprocess.run([FF, "-v", "error", "-i", str(p), "-map", "0:a:0", "-c", "copy",
                        "-f", "streamhash", "-hash", "sha256", "-"],
                       capture_output=True, text=True)
    return (r.stdout or "").strip()


def main() -> int:
    fx = json.loads((SB / "fixture.json").read_text(encoding="utf-8"))
    pid = fx["sandbox_project_id"]
    pdir = R / "projects" / pid / "output"
    base = next(f for f in sorted(pdir.glob("*.mp4")) if "with_outro" not in f.name)
    plain = next((f for f in sorted(pdir.glob("*with_outro.mp4"))), None)
    final = pdir / (base.stem + "_with_outro_v2.mp4")
    if plain and plain != final:
        if final.exists():
            final.unlink()
        plain.rename(final)
        print("重命名:", plain.name, "->", final.name)

    import sqlite3
    con = sqlite3.connect("file:" + (R / "projects" / "video_studio.db").as_posix()
                          + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    arts = [dict(r) for r in con.execute(
        "select artifact_id, type, path, sha256, size from artifacts where project_id=?",
        (pid,))]
    con.close()
    ro = next((a for a in arts if a["type"] == "render_output"), None)
    print("artifacts:", sorted({a["type"] for a in arts}))
    print("render_output 已登记:", bool(ro), ro["artifact_id"] if ro else "")
    if not ro:
        print("**未登记 render_output ⇒ 按本项目口径不构成交付级候选**（如实记录）")

    tb = json.loads((R / "output/phase33_voice/timebase_v41.json").read_text(encoding="utf-8"))
    h7 = fx.get("outro") or {}
    rec = {
        "schema": "p33-4-delivery-candidate-v1",
        "stage": "Phase 33 P33-4 第二部交付级候选（v4.1 首次入片 + H7）",
        "registered_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "sandbox_project_id": pid,
        "base_film": str(base.relative_to(R)).replace("\\", "/"),
        "base_sha256": sha(base), "base_bytes": base.stat().st_size,
        "base_duration_s": dur(base),
        "render_output_registered": bool(ro),
        "render_output_artifact": (ro["artifact_id"] if ro else None),
        "final_film": str(final.relative_to(R)).replace("\\", "/"),
        "final_sha256": sha(final), "final_bytes": final.stat().st_size,
        "final_duration_s": dur(final), "final_video_track_s": dur(final, "v:0"),
        "timebase": {"rule": tb["rule"], "audio_time_base_s": tb["audio_time_base_s"],
                     "sum_measured_speech_s": tb["sum_measured_speech_s"],
                     "sum_pause_s": tb["sum_pause_s"],
                     "trailing_pad_s": tb["trailing_pad_s"],
                     "narration_measured_s": tb["narration_measured_s"],
                     "old_contract_s": 978.7,
                     "note": "旧 978.7±1 契约随 v3/V20 谱系废止；本版按新时基登记"},
        "h7": h7,
        "bank_chain": fx.get("bank_chain"),
        "pool_size": fx.get("n_pool"),
        "audio_identical_to_base": audio_hash(final) == audio_hash(base),
        "zero_promotion": True,
        "promotion_baseline_unchanged": ("projects/p_50e10b27b44d/output/"
                                         "t_a4d8c1aafd04_draft.mp4"),
    }
    p = L / "p33_4_delivery_candidate.jsonl"
    with p.open("a", encoding="utf-8") as fh:      # append-only
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(json.dumps({k: rec[k] for k in
                      ("final_film", "final_bytes", "final_duration_s",
                       "final_video_track_s", "audio_identical_to_base",
                       "render_output_registered", "pool_size")},
                     ensure_ascii=False, indent=1))
    print("-> " + p.relative_to(R).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
