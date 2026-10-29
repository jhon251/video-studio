# -*- coding: utf-8 -*-
"""P31 权威复算：从**渲染实际使用的** material_timeline + 权威窗口复算 DQ-2 与逐景复用。

口径 = P27/P19 报告口径（core.direction.asset_reuse + 每景窗口含其后 pause，末景含 trailing）。
"""
from __future__ import annotations

import collections
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
SANDBOX = R / "output" / "phase31_p31_3_sandbox"
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import narration as NAR                                # noqa: E402
from video_studio.core import direction as DIR                                # noqa: E402

SCRIPT = R / "output/phase27_script_sandbox/script_p27_v41_40seg.json"
VOICE = R / "output/phase20_voice_sandbox/voice_output_40seg_v21.json"
POOL = R / "docs/regression_2x/logs/phase16_retrieval_payload.json"


def main() -> int:
    dec = json.loads((SANDBOX / "material_timeline.json").read_text(encoding="utf-8"))["decisions"]
    script = json.loads(SCRIPT.read_text(encoding="utf-8"))
    voice = json.loads(VOICE.read_text(encoding="utf-8"))
    plan = NAR.narration_plan(script, voice)
    wins = plan["segments"]
    segs = script["segments"]
    idx = {str(s.get("scene_id") or "S%02d" % (i + 1)): i for i, s in enumerate(segs)}
    pool = {c["sha256"]: c for c in
            json.loads(POOL.read_text(encoding="utf-8"))["candidates"]
            if c.get("sha256")}
    tl = []
    for d in dec:
        i = idx.get(d["scene_id"])
        if i is None:
            print("!! 未匹配场景", d["scene_id"])
            continue
        st = wins[i]["start_s"]
        en = wins[i]["end_s"] + wins[i]["pause_s"]
        if i == len(segs) - 1:
            en = plan["audio_time_base_s"]
        tl.append({"scene_id": d["scene_id"], "start_s": st, "end_s": en,
                   "selected_asset": d.get("selected_asset")})
    out = DIR.asset_reuse(tl)
    tot = out["total_s"]
    print("声明时基 {:.3f}s | 视频轨合计 {:.3f}s | Δ={:+.3f}s".format(
        plan["audio_time_base_s"], tot, tot - plan["audio_time_base_s"]))
    print()
    print("=== DQ-2（权威复算）===")
    print("state={}  unique_assets={}  max_asset_share={}  threshold={}".format(
        out["state"], out["unique_assets"], out["max_asset_share"], out["threshold"]))
    print()
    print("{:<14} {:<5} {:<9} {:<9} {:<6} {}".format(
        "sha12", "scn", "secs", "share", "cap>2", "name"))
    for k, v in sorted(out["per_asset"].items(), key=lambda kv: -kv[1]["share"]):
        nm = (pool.get(k) or {}).get("name") if k != "SOLID_COLOR" else "(纯色卡)"
        print("{:<14} {:<5} {:<9.2f} {:<9.4f} {:<6} {}".format(
            str(k)[:12], v["scenes"], v["seconds"], v["share"],
            "YES" if v["scenes"] > 2 else "", str(nm)[:44]))
    print()
    nd = sum(1 for s in tl if (s.get("selected_asset") or {}).get("asset_id"))
    print("有素材景 {}/{} | 纯色卡 {} 景".format(nd, len(tl), len(tl) - nd))
    mx_reuse = max(v["scenes"] for v in out["per_asset"].values())
    print("最大单素材复用景数 = {} | cap=2 需 unique >= {}".format(
        mx_reuse, -(-len(tl) // 2)))
    print()
    verdict = "PASS" if out["state"] == "PASS" else "FAIL"
    print("DQ-2 => {}（阈值 share<=0.35 且 unique>=6）".format(verdict))

    (R / "output" / "p31_probe" / "dq2_p31.json").write_text(json.dumps(
        {"schema": "p31-dq2-measured-v1",
         "declared_time_base_s": plan["audio_time_base_s"],
         "video_track_total_s": tot,
         "dq2": {k: v for k, v in out.items() if k != "findings"},
         "max_reuse_scenes": mx_reuse,
         "scenes_with_asset": nd, "scenes_total": len(tl),
         "per_asset_names": {str(k)[:12]: (pool.get(k) or {}).get("name")
                             for k in out["per_asset"]},
         "verdict": verdict}, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
