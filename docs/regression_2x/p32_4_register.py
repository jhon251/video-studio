# -*- coding: utf-8 -*-
"""P32-4：**登记交付级候选**（append-only、零 promotion）。

做法：以最终参数**再渲一次**（v4.1 × 40 景 + 运动 + 仲裁 + 绑定回退 + pause + bank v2），
使生产链在**全门通过**后自行登记 `render_output` / `attribution`（这正是本项目
「交付级候选」的落地口径——见 Phase 19 记录：「未登记 render_output ⇒ 非交付物」）。

随后在**已登记的成片**上施加 H7 片尾卡（TS 拼接，视频轨满覆盖、音轨流复制），
并把 H7 证据与最终文件名写回登记记录。

零 promotion：不改 baseline/manifest/母片/既有候选。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys
import time

R = pathlib.Path(r"C:\mp4agent\video-studio")
SB = R / "output" / "phase32_p32_4_sandbox"
LOGS = R / "docs" / "regression_2x" / "logs"
sys.path.insert(0, str(R / "src"))
sys.path.insert(0, str(R / "docs" / "regression_2x"))
sys.stdout.reconfigure(encoding="utf-8")

FF = str(R / "bin" / "ffmpeg.exe")
FFPROBE = str(R / "bin" / "ffprobe.exe")


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


def apply_outro(film: pathlib.Path, out: pathlib.Path) -> dict:
    """H7 片尾卡（共享实现 p32_h7.apply_outro：末段窗口内 drawtext + TS 拼接 + 音轨流复制）。"""
    import p32_h7 as H7
    return H7.apply_outro(FF, FFPROBE, film, out, SB / "work_final")


def main() -> int:
    # ---- ① 再渲一次，让生产链登记 render_output/attribution ----
    t0 = time.time()
    rc = subprocess.run([sys.executable, str(R / "docs/regression_2x/phase32_render.py")],
                        cwd=str(R), capture_output=False).returncode
    print("渲染 rc={} {:.1f}s".format(rc, time.time() - t0))
    fx_p = SB / "fixture.json"
    fx = json.loads(fx_p.read_text(encoding="utf-8"))
    pid = fx["sandbox_project_id"]
    pdir = R / "projects" / pid / "output"
    base = next(f for f in sorted(pdir.glob("*.mp4")) if "with_outro" not in f.name)
    print("登记沙箱:", pid, "| 基片:", base.name)

    # ---- ② 核验 render_output 已登记 ----
    import sqlite3
    con = sqlite3.connect("file:" + (R / "projects" / "video_studio.db").as_posix()
                          + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    arts = [dict(r) for r in con.execute(
        "select artifact_id, type, path, sha256, size from artifacts where project_id=?",
        (pid,))]
    con.close()
    kinds = sorted({a["type"] for a in arts})
    ro = next((a for a in arts if a["type"] == "render_output"), None)
    print("artifacts:", kinds)
    print("render_output 已登记:", bool(ro), ro["artifact_id"] if ro else "")
    if not ro:
        print("**未登记 render_output ⇒ 按本项目口径不构成交付级候选**（如实记录）")

    # ---- ③ H7 片尾卡（在已登记成片上）----
    final = pdir / (base.stem + "_with_outro_v2.mp4")
    info = apply_outro(base, final)
    print("H7:", json.dumps({k: info[k] for k in
                            ("window", "duration_before_s", "duration_after_s",
                             "duration_unchanged", "video_full_cover",
                             "audio_identical_to_base", "bytes")},
                           ensure_ascii=False))

    # ---- ④ 登记记录（append-only）----
    rec = {
        "schema": "p32-4-delivery-candidate-v1",
        "stage": "Phase 32 P32-4 终渲染 + 交付级登记",
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
        "h7": info,
        "bank_chain": fx.get("bank_chain"),
        "zero_promotion": True,
        "promotion_baseline_unchanged": ("projects/p_50e10b27b44d/output/"
                                         "t_a4d8c1aafd04_draft.mp4"),
    }
    p = LOGS / "p32_4_delivery_candidate.jsonl"
    with p.open("a", encoding="utf-8") as fh:      # append-only
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print("-> " + p.relative_to(R).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
