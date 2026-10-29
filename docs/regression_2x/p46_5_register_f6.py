# -*- coding: utf-8 -*-
"""Phase 45 / P45-4：**F6 登记（含 1 项 fail-closed 阻断，如实落账）**。

本轮**全部结构性约束达标**，但渲染**被 `ASSET_INSUFFICIENT` 阻断**（2 景素材未出现
在镜头窗口内）⇒ 按授权书「任一断言不可满足 ⇒ STOP 报告」，**F6 不作为交付候选接受**，
改为落账「结构达标 + 渲染阻断」的双面记录，交监理裁定。

达标项（实测）：
  · **锚定越界 = 0**（P44 的 4 处越界已修）
  · **cap 违例 = 无**（扩池后 22 张未锚定 × cap3 = 66 景位 ≥ 36）
  · **间距违例 = 0 / 相邻同素材 = 0 / 相邻同家族 = 0**
  · **Pexels 14 张全部上屏**，家族 E 成立（轮换多样性增量到位）
  · **词级同步金门 2/2 PASS**（median 0.0000s / 覆盖 100%）
阻断项：`P02_2` / `P08_3` 的 `corr_expected ≈ 0.199` vs `corr_best 0.063`
  ⇒ 分配素材**确实没出现在画面里**（其中 `P02_2` 为**具名绑定**景）。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sqlite3
import subprocess
import sys
import time

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
SB = R / "output" / "phase36_p36_4_sandbox"
FFPROBE = str(R / "bin" / "ffprobe.exe")
sys.stdout.reconfigure(encoding="utf-8")


def dur(p, sel=False):
    cmd = [FFPROBE, "-v", "error"]
    if sel:
        cmd += ["-select_streams", "v:0"]
    cmd += ["-show_entries", "stream=duration" if sel else "format=duration",
            "-of", "default=nw=1:nk=1", str(p)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    v = (r.stdout or "").strip().splitlines()
    return round(float(v[0]), 3) if v and v[0] else None


def main() -> int:
    fx = json.loads((SB / "fixture.json").read_text(encoding="utf-8"))
    pid = fx["sandbox_project_id"]
    pdir = R / "projects" / pid / "output"
    mps = sorted(pdir.glob("*.mp4"))
    final = next((f for f in mps if "with_outro" in f.name), None)
    base = next((f for f in mps if "with_outro" not in f.name), None)
    con = sqlite3.connect("file:" + (R / "projects/video_studio.db").as_posix()
                          + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    r = con.execute("select payload from events where project_id=? and "
                    "type='MATERIAL_TIMELINE'", (pid,)).fetchone()
    p = json.loads(r["payload"])
    dec = p["decisions"]
    al = p.get("material_allocation") or {}
    gs = al.get("global_satisfy") or {}
    con.close()

    sync = json.loads((L / "p45_3_caption_word_sync.json").read_text(encoding="utf-8"))
    ov = json.loads((R / "output/phase45_voice/voice_output_v65_ovoice.json")
                    .read_text(encoding="utf-8"))
    pex = json.loads((L / "p45_2_pexels_ledger.json").read_text(encoding="utf-8"))
    anc = {"3f0b94a3f2ac": ["P05_2", "P05_3", "P06_1", "P06_2"],
           "23e71bc8a864": ["P01_2", "P01_3"],
           "65377b888b77": ["P04_4", "P06_3", "P07_4"],
           "1e9d2ab4e64e": ["P06_3", "P07_2", "P09_1"],
           "bd383463dbb9": ["P09_3", "P09_4"],
           "cfae038f6106": ["P09_3", "P09_4"], "33b360a5363c": ["P05_4"]}
    viol = [(d["scene_id"], pf) for d in dec for pf, alw in anc.items()
            if pf in str((d.get("selected_asset") or {}).get("asset_id") or "")
            and d["scene_id"] not in alw]
    pfx = [x["sha256_prefix"] for x in
           json.loads((R / "config/content_exclusions.json")
                      .read_text(encoding="utf-8"))["content_exclusions"]["excluded"]]
    bans = {b: sum(1 for d in dec if b in str(
        (d.get("selected_asset") or {}).get("asset_id"))) for b in pfx}
    pex_sh = [c["sha256"][:12] for c in pex["items"]]
    pex_on = [d["scene_id"] for d in dec
              if any(s in str((d.get("selected_asset") or {}).get("asset_id"))
                     for s in pex_sh)]

    rec = {
        "schema": "p45-4-delivery-candidate-v1",
        "stage": "Phase 45 F6（Pexels 扩池 + 词级重配音 + 锚定修订）",
        "registered_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "acceptance": "**FAIL-CLOSED（渲染被阻断）**—— 结构约束全达标，但素材出现校验未过",
        "sandbox_project_id": pid,
        "base_film": (str(base.relative_to(R)).replace("\\", "/") if base else None),
        "base_bytes": (base.stat().st_size if base else None),
        "base_sha256": (hashlib.sha256(base.read_bytes()).hexdigest() if base else None),
        "final_film": (str(final.relative_to(R)).replace("\\", "/") if final else None),
        "final_bytes": (final.stat().st_size if final else None),
        "final_sha256": (hashlib.sha256(final.read_bytes()).hexdigest() if final else None),
        "final_duration_s": (dur(final) if final else None),
        "final_video_track_s": (dur(final, sel=True) if final else None),
        "blocking_defect": {
            "code": "ASSET_INSUFFICIENT",
            "reason": "分配素材未出现在其镜头窗口内",
            "scenes": ["P02_2", "P08_3"],
            "evidence": {"P02_2": {"expected": "asset_f0cd2a28016d",
                                   "corr_expected": 0.199, "corr_best": 0.063,
                                   "fallback_state": "SOLID_COLOR_CARD"},
                         "P08_3": {"expected": "asset_f0cd2a28016d",
                                   "corr_best": 0.063,
                                   "fallback_state": "LOCAL_INGEST"}},
            "note": ("`P02_2` 属**具名绑定景**（P34 owner-approved 5 景之一）⇒ "
                     "该景的素材确实没渲染进画面。这是**真实缺陷**，fail-closed 正确拦截。"),
            "method": "frame_pearson_48x48",
        },
        "structural_achievements": {
            "anchor_violations": len(viol), "anchor_violation_list": viol[:5],
            "solver_pass": gs.get("pass"),
            "cap_violations": gs.get("cap_violations"),
            "gap_violations": gs.get("gap_violations"),
            "adjacent_same_asset": gs.get("adjacent_violations"),
            "adjacent_same_family": gs.get("adjacent_same_family"),
            "family_counts": gs.get("family_counts"),
            "family_share_violations": gs.get("family_share_violations"),
            "content_exclusions_on_screen": bans,
            "pexels_on_screen_scenes": len(pex_on),
            "pexels_on_screen_list": pex_on,
        },
        "p45_1_pexels_governance": {
            "source": "Pexels API（第二受治源）",
            "license": "Pexels License ⇒ overlay 映射 FREE_ATTRIBUTION（保守，照记署名）",
            "overlay_consumed_by_gate": True,
            "frozen_stack_untouched": "core/materials.py 未改（pin 校验 MATCH）",
            "requests_used": pex["requests"], "requests_cap": pex["max_requests"],
            "verified_items": pex["verified"], "items_cap": pex["max_items"],
            "rejected": pex["rejected"], "failures": len(pex["failures"]),
        },
        "p45_2_targeted_acquisition": {
            "target": "抽象论述景视觉语言", "queries": pex and
            sorted({i["query"] for i in pex["items"]}),
            "items": len(pex["items"]),
            "new_family": "E_黑板粉笔与数学工作场景（14 张，待监理复核分派）",
        },
        "p45_3_ovoice": {
            "voice": ov["voice"], "segments": ov["segments_total"],
            "all_ok": ov["all_segments_ok"], "tolerance": ov["tolerance"],
            "max_deviation": 0.0, "narration_duration_s": ov["narration_duration_s"],
            "words_captured": sum(m["word_count"] for m in ov["segments"]),
            "sync_gate": "tests/caption_word_sync_test.py 2/2 PASS",
            "sync_median_lag_s": sync["median_lag_s"],
            "sync_cover_ratio": sync["cover_ratio"],
            "sync_max_abs_lag_s": sync["max_abs_lag_s"],
            "sentences": sync["sentences"],
        },
        "gates": {
            "caption_word_sync": "PASS 2/2（median 0.0000s，覆盖 100%）",
            "content_exclusion": "待全量回归复核",
            "dq3e": "待复核", "no_picture": "待复核", "metaphor_quota": "待复核",
            "material_appearance": "**FAIL（2 景）** ⇒ 阻断",
        },
        "zero_promotion": True,
        "promotion_baseline_unchanged": "projects/p_50e10b27b44d/output/t_a4d8c1aafd04_draft.mp4",
        "next_action": ("① 修 `P02_2`/`P08_3` 的素材未出现问题（最可能：具名绑定与"
                        "锚定/分配交互，或该素材本身在渲染链路未被使用）；"
                        "② 修好后重渲并按全门复核；③ 再决定是否接受 F6。"),
    }
    pth = L / "p45_4_delivery_candidate.jsonl"
    with pth.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print("F6 落账（FAIL-CLOSED）：{}".format(rec["final_film"]))
    print("  结构达标：锚定越界 {} | cap {} | gap {} | 相邻 {} | 家族相邻 {} | 家族份额 {}".format(
        len(viol), gs.get("cap_violations") or 0, gs.get("gap_violations"),
        gs.get("adjacent_violations"), gs.get("adjacent_same_family"),
        gs.get("family_share_violations") or "无"))
    print("  Pexels 上屏 {} 景 | 禁入上屏 {}".format(len(pex_on), bans))
    print("  词级同步：median {}s | 覆盖 {:.0%}".format(
        sync["median_lag_s"], sync["cover_ratio"]))
    print("  阻断：{} 景素材未出现".format(len(rec["blocking_defect"]["scenes"])))
    print("-> " + str(pth.relative_to(R)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
