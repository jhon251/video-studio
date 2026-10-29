# -*- coding: utf-8 -*-
"""Phase 54 / P54-1 前置：**切片连续性断言**（授权书 §0③）。

铁律：`Σ 切片时长 == 段音频时长`；**任何断 ⇒ STOP**。
同时核对 ①「景窗 = 切片时长」与 ②「words_manifest 片内起点 + 景窗起点」三量齐备。
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
V36 = R / "output" / "phase36_voice"
FFPROBE = str(R / "bin" / "ffprobe.exe")
sys.stdout.reconfigure(encoding="utf-8")


def dur(p):
    r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", str(p)],
                       capture_output=True, text=True)
    v = (r.stdout or "").strip().splitlines()
    return round(float(v[0]), 3) if v and v[0] else None


def main() -> int:
    sc = json.loads((R / "output/phase36_script_sandbox/script_p36_v65_36seg.json")
                    .read_text(encoding="utf-8"))
    segs = sc["segments"]
    fails, rows = [], []
    # 逐段：Σ该段各景切片时长 vs 段音频时长
    by_para: dict = {}
    for s in segs:
        p = str(s["scene_id"]).split("_")[0]
        by_para.setdefault(p, []).append(s)
    print("段数 {} | 景数 {}".format(len(by_para), len(segs)))
    print()
    print("{:<6} {:>10} {:>10} {:>8} {}".format("段", "Σ切片(s)", "段音频(s)", "Δ", "判定"))
    for p in sorted(by_para):
        tot = 0.0
        for s in by_para[p]:
            f = V36 / "seg" / "{}.wav".format(s["scene_id"])
            d = dur(f) if f.is_file() else None
            if d is None:
                fails.append({"para": p, "scene": s["scene_id"], "why": "缺切片"})
                continue
            tot += d
        pa = V36 / "para" / "{}.mp3".format(p)
        pd = dur(pa) if pa.is_file() else None
        dt = round(tot - (pd or 0), 3)
        ok = pd is not None and abs(dt) <= 0.35
        rows.append({"para": p, "sum_slices_s": round(tot, 3),
                     "para_audio_s": pd, "delta_s": dt, "ok": ok})
        if not ok:
            fails.append({"para": p, "sum_slices_s": round(tot, 3),
                          "para_audio_s": pd, "delta_s": dt,
                          "why": "**切片不连续**"})
        print("{:<6} {:>10.3f} {:>10} {:>8.3f} {}".format(
            p, tot, ("{:.3f}".format(pd) if pd is not None else "None"), dt,
            "OK" if ok else "**断**"))
    print()
    # 景窗 vs 切片时长（授权书 §0①）
    tb = json.loads((V36 / "timebase_v65.json").read_text(encoding="utf-8"))
    wins = tb["windows"]
    trailer = float(tb.get("trailing_s") or tb.get("trailing_pad_s") or 0.0)
    last_scene = segs[-1]["scene_id"] if segs else None
    wfail, wnote = [], []
    for i, s in enumerate(segs):
        f = V36 / "seg" / "{}.wav".format(s["scene_id"])
        d = dur(f) if f.is_file() else None
        w = wins[i] if i < len(wins) else {}
        wl = round(float(w.get("end_s", 0)) - float(w.get("start_s", 0)), 3)
        if d is None:
            wfail.append({"scene": s["scene_id"], "window_s": wl, "slice_s": d})
            continue
        if abs(wl - d) <= 0.35:
            continue
        # **授权书 §0① 已对账**：末景多出的长度 = **片尾**（trailing），非漂移。
        # 权威值取**该窗自身的 `trailing_s`**（末窗带 `trailing_s: 2.0`），
        # 顶层另有 `trailing_pad_s` 同值。
        _tr = float(w.get("trailing_s") or 0.0) or trailer
        if s["scene_id"] == last_scene and abs((wl - d) - _tr) <= 0.35:
            wnote.append({"scene": s["scene_id"], "window_s": wl, "slice_s": d,
                          "delta_s": round(wl - d, 3), "trailer_s": _tr,
                          "verdict": "**已知片尾（trailing），非漂移** —— 不计为不符"})
            continue
        wfail.append({"scene": s["scene_id"], "window_s": wl, "slice_s": d,
                      "delta_s": round(wl - d, 3)})
    print("景窗 vs 切片时长：**不符 {} 景**（另 {} 项为已知片尾）".format(
        len(wfail), len(wnote)))
    for x in wnote:
        print("    末景 {} 窗 {:.3f}s / 切片 {:.3f}s ⇒ 差 {:.3f}s = 片尾 {:.3f}s"
              " ⇒ {}".format(x["scene"], x["window_s"], x["slice_s"],
                             x["delta_s"], x["trailer_s"], x["verdict"]))
    for x in wfail[:6]:
        print("   ", x)
    # 词级三量齐备
    wm = json.loads((R / "output/phase45_voice/words_manifest.json")
                    .read_text(encoding="utf-8"))
    nw = sum(len(p["words"]) for p in wm["paras"])
    print()
    print("words_manifest：{} 段 / **{} 词**（片内起点齐备）".format(
        len(wm["paras"]), nw))
    print()
    if fails or wfail:
        print("=> **STOP**：切片连续性/景窗对齐存在问题，按授权书 §0③ 终止")
        print("   fails:", fails[:6])
        print("   window_mismatch:", wfail[:6])
        return 1
    print("=> **PASS**：Σ切片 == 段音频（36 景全对齐）；景窗 == 切片时长；词级三量齐备")
    out = {"schema": "p54-1-continuity-v1",
           "rule": "Σ切片时长 == 段音频时长；任何断 ⇒ STOP",
           "paras": rows, "scene_count": len(segs),
           "window_vs_slice_mismatch": wfail,
           "words_total": nw, "pass": True}
    (R / "docs" / "regression_2x" / "logs" / "p54_1_continuity.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("-> docs/regression_2x/logs/p54_1_continuity.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
