# -*- coding: utf-8 -*-
"""P31：对失败景的实际成片帧，逐个池内素材计算 `.corr` 与 `bank_score`（复刻核验口径）。

用于判定「素材是否真的在屏」以及**池内是否存在更优绑定**（决定是否需要受治理获取）。
只读。
"""
from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.agents.editing.agent import (gray48, frame_corr)             # noqa: E402
from video_studio.core import corr_diagnostics as CD                          # noqa: E402

FF = R / "bin" / "ffmpeg.exe"
POOL = R / "docs/regression_2x/logs/phase16_retrieval_payload.json"
OUT = R / "output" / "p31_probe" / "frames"
OUT.mkdir(parents=True, exist_ok=True)

# 失败景：(scene_id, sample_t, expected_asset_id)
FAILS = [("S11p2", 544.21, None), ("S13p2", 640.94, None)]


def main() -> int:
    fx = json.loads((R / "output/phase31_p31_3_sandbox/fixture.json")
                    .read_text(encoding="utf-8"))
    pid = fx["sandbox_project_id"]
    films = sorted((R / "projects" / pid / "output").glob("*.mp4"),
                   key=lambda p: -p.stat().st_size)
    film = films[0]
    print("成片:", film.name, "{:,}B".format(film.stat().st_size))
    dec = {d["scene_id"]: d for d in
           json.loads((R / "output/phase31_p31_3_sandbox/material_timeline.json")
                      .read_text(encoding="utf-8"))["decisions"]}
    pool = [c for c in json.loads(POOL.read_text(encoding="utf-8"))["candidates"]
            if c.get("path")]
    refs = {}
    for c in pool:
        try:
            refs[c["sha256"]] = gray48(c["path"])
        except Exception as exc:                                            # noqa: BLE001
            print("  ref 读取失败", c.get("name"), exc)
    print("池内可用参考 {} 张".format(len(refs)))
    result = {}
    for sid, t, _exp in FAILS:
        exp = ((dec.get(sid) or {}).get("selected_asset") or {}).get("sha256")
        fp = OUT / "{}.png".format(sid)
        r = subprocess.run([str(FF), "-v", "error", "-y", "-ss", "{:.2f}".format(t),
                            "-i", str(film), "-frames:v", "1", str(fp)],
                           capture_output=True)
        if r.returncode != 0 or not fp.is_file():
            print(sid, "抽帧失败")
            continue
        g = gray48(fp)
        rows = []
        for sha, ref in refs.items():
            c = frame_corr(g, ref)
            try:
                bk = CD.bank_score(g, str(next(x for x in pool if x["sha256"] == sha)["path"]),
                                   res=48)
                b = float(bk["corr"])
            except Exception:                                               # noqa: BLE001
                b = None
            rows.append((sha, c, b))
        rows.sort(key=lambda z: -(z[2] if z[2] is not None else z[1]))
        print()
        print("=== {} (t={}s) 期望素材 {} ===".format(sid, t, str(exp)[:12]))
        print("{:<14} {:<9} {:<9} {}".format("sha12", "corr", "bank", "name"))
        for sha, c, b in rows:
            nm = next(x for x in pool if x["sha256"] == sha)["name"]
            mark = "  <== 期望" if sha == exp else ""
            print("{:<14} {:<9} {:<9} {}{}".format(
                sha[:12], c, ("%.3f" % b) if b is not None else "-", str(nm)[:40], mark))
        result[sid] = {"expected": exp,
                       "rows": [{"sha": s, "corr": c, "bank": b} for s, c, b in rows]}
        # 用期望素材的 bank 判定
        mine = [r for r in rows if r[0] == exp]
        if mine:
            _, cc, bb = mine[0]
            others = [r[2] if r[2] is not None else r[1] for r in rows if r[0] != exp]
            bc = max(others) if others else (bb if bb is not None else cc)
            print("  -> 期望 corr={} bank={} | 其他最大={:.3f} | 判据 corr>=0.30 且 >=best-0.15".format(
                cc, bb, bc))
    (R / "output" / "p31_probe" / "frame_diag.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
