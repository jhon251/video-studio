# -*- coding: utf-8 -*-
"""P31-2 前置侦查（权威路径）：用 `core.narration.narration_plan` 重建窗口，
从 P30 交付候选的 retrieval artifact 取绑定，复算 DQ-2 与 cap=2 可行性。只读。
"""
from __future__ import annotations

import collections
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
OUT = R / "output" / "p31_probe"
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.core import narration as NAR                                # noqa: E402

SCRIPT = R / "output" / "phase27_script_sandbox" / "script_p27_v41_40seg.json"
VOICE = R / "output" / "phase20_voice_sandbox" / "voice_output_40seg_v21.json"
POOL = L / "phase16_retrieval_payload.json"
P30_RETR = (R / "projects" / "p_8b48148d4bf3" / "artifacts" / "a_331e853a4bb9.json")
CAP = 2


def main() -> int:
    script = json.loads(SCRIPT.read_text(encoding="utf-8"))
    voice = json.loads(VOICE.read_text(encoding="utf-8"))
    pol = NAR.narration_plan(script, voice)
    print("time_base={} declared={} pause={} trail={} concat_ok={} complete={}".format(
        pol["audio_time_base_s"], pol["declared_time_base_s"], pol["pause_budget_s"],
        pol["trailing_pad_s"], pol["concat_consistent"], pol["complete"]))
    print("Σactual={}".format(pol["actual_total_narration_s"]))
    wins = pol["segments"]
    segs = script["segments"]
    print("窗口 {} | 前2 {}".format(len(wins), [(w["start_s"], w["end_s"]) for w in wins[:2]]))
    print("末2 {}".format([(w["start_s"], w["end_s"]) for w in wins[-2:]]))

    # P30 绑定
    retr = json.loads(P30_RETR.read_text(encoding="utf-8"))
    bind = retr.get("_p30_binding") or {}
    print("P30 _p30_binding 条数 {}".format(len(bind)))
    pool = {c["sha256"]: c for c in json.loads(POOL.read_text(encoding="utf-8"))["candidates"]}

    # 逐景：绑定按真实 scene_id 落库（bind_scene_id）
    rows = []
    for i, s in enumerate(segs):
        sid = str(s.get("scene_id") or "S%02d" % (i + 1))
        sha = bind.get(sid)
        if sha is None and s.get("parent_scene_id"):
            sha = bind.get(s.get("parent_scene_id"))
        d = wins[i]["actual_s"] + wins[i]["pause_s"]
        rows.append({"scene_id": sid, "parent": s.get("parent_scene_id"), "sha256": sha,
                     "dur": round(d, 3), "start_s": wins[i]["start_s"],
                     "end_s": wins[i]["end_s"]})
    # 与 P30 的 40 景决策对照（数量）
    sha_n = len([r for r in rows if r["sha256"]])
    print("有绑定 {} / {} 景".format(sha_n, len(rows)))

    def dq2(rs):
        tot = sum(r["dur"] for r in rs)
        secs, scen = collections.Counter(), collections.Counter()
        for r in rs:
            k = r["sha256"] or "SOLID"
            secs[k] += r["dur"]
            scen[k] += 1
        sh = {k: v / tot for k, v in secs.items()}
        uniq = len([k for k in secs if k != "SOLID"])
        return {"total_s": round(tot, 3), "unique_assets": uniq,
                "max_asset_share": round(max(sh.values()), 4),
                "max_reuse": max(scen.values()), "secs": secs, "scenes": scen,
                "shares": sh}

    cur = dq2(rows)
    print()
    print("=== 现状（按 P30 绑定 + v2.1 窗口复算）===")
    print("total={total_s} uniq={unique_assets} max_share={max_asset_share} max_reuse={max_reuse}".format(**cur))
    print("{:<14} {:<5} {:<9} {:<9} {}".format("sha12", "scn", "secs", "share", "name"))
    for k in sorted(cur["secs"], key=lambda z: -cur["secs"][z]):
        nm = (pool.get(k) or {}).get("name") or "-"
        print("{:<14} {:<5} {:<9.2f} {:<9.4f} {}".format(
            str(k)[:12], cur["scenes"][k], cur["secs"][k], cur["shares"][k], nm[:44]))
    print()
    print("DQ-2 阈值: max_share <= 0.35 且 uniq >= 6  => {}".format(
        "PASS" if (cur["max_asset_share"] <= 0.35 and cur["unique_assets"] >= 6) else "FAIL"))
    print("cap={} 需 unique >= {}".format(CAP, -(-len(rows) // CAP)))
    print("当前池可用唯一素材 {}".format(len(pool)))

    (OUT / "dq2_current.json").write_text(json.dumps(
        {"schema": "p31-dq2-current-v1", "narration_plan": {
            "audio_time_base_s": pol["audio_time_base_s"],
            "pause_budget_s": pol["pause_budget_s"],
            "trailing_pad_s": pol["trailing_pad_s"],
            "actual_total_narration_s": pol["actual_total_narration_s"]},
         "dq2": {k: v for k, v in cur.items() if k not in ("secs", "scenes", "shares")},
         "per_asset": {str(k)[:12]: {"scenes": cur["scenes"][k],
                                     "seconds": round(cur["secs"][k], 3),
                                     "share": round(cur["shares"][k], 4),
                                     "name": (pool.get(k) or {}).get("name")}
                       for k in cur["secs"]},
         "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("-> " + str(OUT / "dq2_current.json"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
