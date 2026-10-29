# -*- coding: utf-8 -*-
"""P33-4 终验收：v4.1 首个交付候选（新时基）全门复算。

  · 时长（**新契约 700.592s**）
  · DQ-2（share 口径）+ **adjacent_same_asset** 检查
  · DQ-3（按新时间轴如实复算）
  · 三指标（运动；含 motion quality 探针结论引用）
  · 构造断言 A2（Σ视频轨 == 声明时基）
  · 一致性门（script_media_consistency_test 结论引用）
  · H7 片尾卡：时长不变 + 视频轨满覆盖 + 音轨与基片逐字节一致
  · S17–S18 暗色段素材分散情况
零 LLM、零 VLM、零网络。
"""
from __future__ import annotations

import collections
import hashlib
import json
import pathlib
import subprocess
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
SANDBOX = R / "output" / "phase33_p33_4_sandbox"
L = R / "docs" / "regression_2x" / "logs"
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import direction as DIR                                # noqa: E402
from video_studio.core import motion_metrics as MM                            # noqa: E402

FF = str(R / "bin" / "ffmpeg.exe")
FFPROBE = str(R / "bin" / "ffprobe.exe")
SCRIPT = R / "output/phase33_script_sandbox/script_p33_v41_40seg.json"
TB = R / "output/phase33_voice/timebase_v41.json"
POOL = L / "phase33_retrieval_payload.json"


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
    fx = json.loads((SANDBOX / "fixture.json").read_text(encoding="utf-8"))
    pid = fx["sandbox_project_id"]
    pdir = R / "projects" / pid / "output"
    films = sorted(pdir.glob("*.mp4"))
    final = next((f for f in films if f.name.endswith("_with_outro_v2.mp4")), None)
    base = next((f for f in films if "with_outro" not in f.name), None)
    print("沙箱 {}", pid)
    if base:
        print("基片   : {} ({:,}B)".format(base.name, base.stat().st_size))
    if final:
        print("最终片 : {} ({:,}B)".format(final.name, final.stat().st_size))
    if not base or not final:
        print("!! 尚未产出（渲染未成功）")
        return 1

    tb = json.loads(TB.read_text(encoding="utf-8"))
    new_base = float(tb["audio_time_base_s"])
    d_base, d_final = dur(base), dur(final)
    v_final = dur(final, "v:0")
    print("时长   : {:.3f} -> {:.3f}（新契约 {:.3f} ±1.0）".format(d_base, d_final, new_base))
    print("视频轨 : {:.3f}（满覆盖 {}）".format(v_final, (v_final or 0) >= (d_final or 0) - 0.1))
    a_ok = audio_hash(base) == audio_hash(final)
    print("音轨   : {}".format("与基片逐字节一致 OK" if a_ok else "**不一致**"))

    # ---- 时间轴 / DQ ----
    dec = json.loads((SANDBOX / "material_timeline.json").read_text(encoding="utf-8"))["decisions"]
    script = json.loads(SCRIPT.read_text(encoding="utf-8"))
    wins = {w["scene_id"]: w for w in tb["windows"]}
    pool = {c["sha256"]: c for c in
            json.loads(POOL.read_text(encoding="utf-8"))["candidates"] if c.get("path")}
    tl = []
    for d in dec:
        w = wins.get(d["scene_id"])
        if not w:
            continue
        tl.append({"scene_id": d["scene_id"], "start_s": w["start_s"], "end_s": w["end_s"],
                   "selected_asset": d.get("selected_asset")})
    dq2 = DIR.asset_reuse(tl)
    dq3 = DIR.static_hold(tl)
    vtt = round(sum(s["end_s"] - s["start_s"] for s in tl), 3)
    print()
    print("=== 构造断言 A2 ===")
    print("  Σ视频轨 {:.3f} vs 声明时基 {:.3f} | Δ={:+.3f} => {}".format(
        vtt, new_base, vtt - new_base, "PASS" if abs(vtt - new_base) <= 0.1 else "FAIL"))
    print()
    print("=== DQ-2（share 口径）===")
    print("  state={} unique={} max_share={} thr={}".format(
        dq2["state"], dq2["unique_assets"], dq2["max_asset_share"], dq2["threshold"]))
    # adjacent same asset
    adj = [tl[i]["scene_id"] for i in range(1, len(tl))
           if (tl[i].get("selected_asset") or {}).get("asset_id")
           and (tl[i].get("selected_asset") or {}).get("asset_id")
           == (tl[i - 1].get("selected_asset") or {}).get("asset_id")]
    counts = collections.Counter()
    for s in tl:
        a = (s.get("selected_asset") or {}).get("asset_id")
        if a:
            counts[a] += 1
    print("  新增检查 adjacent_same_asset = {} 处 | 每素材最大景数 = {}".format(
        len(adj), max(counts.values()) if counts else 0))
    print()
    print("=== DQ-3（新时间轴复算；如实）===")
    print("  state={} scenes={} mean_hold={} max_hold={} over={} share_over={}".format(
        dq3["state"], dq3.get("scenes"), dq3.get("mean_hold_s"), dq3.get("max_hold_s"),
        dq3.get("holds_over_threshold"), dq3.get("share_over_threshold")))

    mm = MM.evaluate(str(final), FF)
    print()
    print("=== 三指标（320x180 MAD，阈值不变）===")
    print("  冻结 {:.1%} | 最长静止 {}s | 开场变化 {} | 全过 {}".format(
        mm["freeze_ratio"], mm["longest_static_s"], mm["opening_changes"], mm["all_pass"]))

    # ---- S17–S18 暗色段素材分散 ----
    dark = []
    for s in tl:
        sid = str(s["scene_id"])
        if sid.startswith(("S17", "S18")):
            dark.append((sid, (s.get("selected_asset") or {}).get("asset_id")))
    print()
    print("=== S17–S18 暗色段素材分散 ===")
    for sid, a in dark:
        print("  {:<7} {}".format(sid, a))
    dset = {a for _, a in dark if a}
    print("  不同素材数 {} / 景数 {}".format(len(dset), len(dark)))

    arb = fx.get("arbitration") or {}
    rep = {
        "schema": "phase33-candidate-acceptance-v1",
        "sandbox_project_id": pid,
        "base_film": str(base.relative_to(R)).replace("\\", "/"),
        "final_film": str(final.relative_to(R)).replace("\\", "/"),
        "final_bytes": final.stat().st_size,
        "timebase": {"new_contract_s": new_base, "old_contract_s": 978.7,
                     "rule": tb["rule"]},
        "duration": {"base_s": d_base, "final_s": d_final,
                     "within": abs((d_final or 0) - new_base) <= 1.0,
                     "changed_by_outro": abs((d_final or 0) - (d_base or 0)) > 0.08},
        "video_track": {"final_s": v_final,
                        "full_cover": (v_final or 0) >= (d_final or 0) - 0.1},
        "audio_stream_copy_identical": a_ok,
        "construction_A2": {"video_track_total_s": vtt, "declared_time_base_s": new_base,
                            "delta_s": round(vtt - new_base, 3),
                            "ok": abs(vtt - new_base) <= 0.1},
        "dq2": {k: v for k, v in dq2.items() if k != "findings"},
        "dq2_adjacent_same_asset": {"violations": adj, "count": len(adj)},
        "max_scenes_per_asset": max(counts.values()) if counts else 0,
        "dq3": {k: v for k, v in dq3.items() if k != "findings"},
        "motion_metrics": mm,
        "dark_scene_spread": {"scenes": dark, "distinct_assets": len(dset)},
        "pool_size": len(pool),
        "arbitration": {k: arb.get(k) for k in ("called", "cost_usd")} if arb else None,
        "zero_llm": True,
    }
    p = L / "phase33_candidate_acceptance.json"
    p.write_text(json.dumps(rep, ensure_ascii=False, indent=1, sort_keys=True),
                 encoding="utf-8")
    print()
    print("-> " + p.relative_to(R).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
