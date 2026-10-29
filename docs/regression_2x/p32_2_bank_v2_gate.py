# -*- coding: utf-8 -*-
"""P32-2 双门验证：`bank-derived-v2`（探针 48→192 + 网格加密，步进 ≤170px）。

**门定义在运行前写死并先行落盘**（`logs/p32_2_gate_definition.json`），
本脚本**不在看到结果后调整**任何判据、阈值或语料。

正门（必须 **100% PASS**）
  · P17 目视在屏五景（S02/S06/S07/S08/S13）的 `output/phase17_attr_pack` 真实成片帧
    × 各自**声明素材**（frame_10/50/90 三帧全算）
  · P31 本轮真实成片帧 `S11p2` / `S13p2`（t=544.21 / 640.94） × 各自声明素材 `301ff850be9c`
  · 判据：`bank_score_v2(frame, asset) >= 0.30`（**冻结阈值不变**）
反门（必须 **0 误通过**）
  · 每个正门帧 × 池内**其它**素材（排除该景声明素材）
  · 重点盯：v1 的两条误通过（S02/S07 画面 × `301ff850be9c`）
  · 另含 P31 成片上**非声明素材**的对照（池内全部其它素材）
  · 判据：误通过 = 分数 >= 0.30
两门全过 ⇒ 采纳 v2；任一门不过 ⇒ 不采纳，如实报告。

同时输出 v1（冻结）与 v2 的**同语料**对照，便于审计"是否放宽"。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys
import time

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
PACK = R / "output" / "phase17_attr_pack"
P31_FRAMES = R / "output" / "p31_probe" / "frames"
POOL = L / "phase16_retrieval_payload.json"
THRESHOLD = 0.30                      # 冻结阈值（**不得改动**）
P17_SCENES = ("S02", "S06", "S07", "S08", "S13")
V1_FALSE_PASS = [("S02", "301ff850be9c"), ("S07", "301ff850be9c")]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.path.insert(0, str(R / "src"))
    import numpy as np                                                            # noqa: E402
    from PIL import Image                                                         # noqa: E402
    from video_studio.core import corr_diagnostics as CD                           # noqa: E402

    pool = [c for c in json.loads(POOL.read_text(encoding="utf-8"))["candidates"]
            if c.get("path")]
    by_sha = {c["sha256"]: c for c in pool}

    # ---------- 语料构建 ----------
    pos, neg = [], []

    def load(p, res):
        with Image.open(p) as im:
            return np.asarray(im.convert("L").resize((res, res)), dtype=np.float64)

    def scores(frame_path, asset_path):
        """同一对 (frame, asset) 的 v1 / v2 / v1.5 分数 —— **各版本按自身分辨率**载入画面。"""
        b1 = CD.bank_score(load(frame_path, 48), str(asset_path), res=48)["corr"]
        b2 = CD.bank_score_v2(load(frame_path, CD.BANK_RES_V2), str(asset_path))["corr"]
        return b1, b2, round(max(b1, b2), 4)

    def _win(frame_path, asset_path):
        b2 = CD.bank_score_v2(load(frame_path, CD.BANK_RES_V2), str(asset_path))
        return {k: b2[k] for k in ("scale", "x0", "y0", "w", "h", "grid")}

    for s in P17_SCENES:
        ap = sorted((PACK / s).glob("asset.*"))[0]
        asha = hashlib.sha256(ap.read_bytes()).hexdigest()
        for fr in sorted((PACK / s).glob("frame_*.png")):
            pos.append({"scene": s, "source": "phase17_attr_pack",
                        "frame": str(fr.relative_to(R)).replace("\\", "/"),
                        "asset": str(ap.relative_to(R)).replace("\\", "/"),
                        "asset_sha12": asha[:12]})
    for sid, t in (("S11p2", 544.21), ("S13p2", 640.94)):
        pos.append({"scene": sid, "source": "phase31_film",
                    "frame": "output/p31_probe/frames/{}.png".format(sid),
                    "asset": by_sha["301ff850be9cc1a1dd460fcfa6ce2763d0786c5ba2c42193915a74efcb1f99ba"]["path"],
                    "asset_sha12": "301ff850be9c", "sample_t": t})

    # 反门：正门各帧 × 池内**其它**素材。
    # **污染修正**：若某素材恰好是**另一景的声明素材**，则「该景画面 vs 它」不是负例
    #（画面里确实有它）⇒ 必须排除，否则会把"同素材复用"误记成"误通过"。
    declared = {}
    for s in P17_SCENES:
        a = sorted((PACK / s).glob("asset.*"))[0]
        declared[s] = hashlib.sha256(a.read_bytes()).hexdigest()
    for p in pos:
        own = p["asset_sha12"]
        for c in pool:
            if c["sha256"][:12] == own:
                continue
            # 该素材是否是本景 own 之外的某景声明素材（画面确含它 ⇒ 非负例）
            if any(c["sha256"][:12] == v[:12] for v in declared.values()):
                continue
            neg.append({"scene": p["scene"], "source": p["source"], "frame": p["frame"],
                        "other": c["name"], "other_sha12": c["sha256"][:12],
                        "path": c["path"],
                        "watch": any(c["sha256"][:12] == w for _, w in V1_FALSE_PASS)})

    gate_def = {
        "schema": "p32-2-gate-definition-v1",
        "stage": "Phase 32 P32-2 bank 网格覆盖修复（bank-derived-v2）",
        "written_before_measurement": True,
        "threshold_frozen": THRESHOLD,
        "v2_params": {"res": CD.BANK_RES_V2, "scales": list(CD.BANK_SCALES_V2),
                      "grid": CD.BANK_GRID_V2, "max_step_px": CD.BANK_STEP_PX_V2},
        "v1_params": {"res": 48, "scales": list(CD.BANK_SCALES), "grid": CD.BANK_GRID},
        "positive_gate": {
            "require": "100% PASS（>= 0.30）",
            "corpus": "P17 目视在屏五景（S02/S06/S07/S08/S13）attr_pack 真实成片帧 × 各自声明素材"
                      " + P31 本轮 S11p2/S13p2 真实成片帧 × 声明素材 301ff850be9c",
            "n": len(pos), "entries": pos},
        "negative_gate": {
            "require": "0 误通过（全部 < 0.30）",
            "corpus": "正门各帧 × 池内其它素材（排除该景声明素材）",
            "watch": "v1 的两条误通过：S02/S07 画面 × 301ff850be9c",
            "n": len(neg)},
        "accept_rule": "两门全过 ⇒ 采纳 v2 并版本化；任一门不过 ⇒ 不采纳，如实报告",
    }
    L.mkdir(parents=True, exist_ok=True)
    (L / "p32_2_gate_definition.json").write_text(
        json.dumps(gate_def, ensure_ascii=False, indent=1), encoding="utf-8")
    print("门定义（运行前写死）-> logs/p32_2_gate_definition.json")
    print("  正门语料 {} 条 | 反门语料 {} 条 | 阈值 {}（不变）".format(
        len(pos), len(neg), THRESHOLD))
    print("  v2 参数: res={} scales={} grid={} 步进上限={}px".format(
        CD.BANK_RES_V2, CD.BANK_SCALES_V2, CD.BANK_GRID_V2, CD.BANK_STEP_PX_V2))
    print()

    # 步进断言（运行前写死）：对每张素材核验 max_step ≤ 170px
    step_rows, step_ok = [], True
    for c in pool:
        with Image.open(c["path"]) as im:
            W, H = im.size
        g = CD.grid_step_px(W, H)
        step_rows.append({"name": c["name"], "wh": [W, H], "max_step_px": g["max_step_px"],
                          "ok": g["ok"]})
        step_ok = step_ok and g["ok"]
    print("=== 步进断言（v2: ≤{}px）===".format(CD.BANK_STEP_PX_V2))
    for r in step_rows:
        print("  {:<44} {:>10} max_step={:>4}px {}".format(
            str(r["name"])[:44], str(r["wh"]), r["max_step_px"], "✔" if r["ok"] else "✘"))
    print("  => {}".format("全部满足 ✔" if step_ok else "**存在超限 ✘**"))
    print()

    # ---------- 正门 ----------
    t0 = time.time()
    print("=== 正门（要求 100% PASS）===")
    print("{:<8} {:<16} {:>9} {:>9} {}".format("scene", "source", "v1", "v2", "v2 窗口"))
    pos_rows = []
    for p in pos:
        apath = p["asset"] if pathlib.Path(p["asset"]).is_absolute() else R / p["asset"]
        b1, b2c, b15 = scores(R / p["frame"], apath)
        row = {"scene": p["scene"], "source": p["source"], "frame": p["frame"],
               "v1": b1, "v2": b2c, "v1_5": b15,
               "v1_pass": b1 >= THRESHOLD, "v2_pass": b2c >= THRESHOLD,
               "v1_5_pass": b15 >= THRESHOLD,
               "v2_window": _win(R / p["frame"], apath)}
        pos_rows.append(row)
        print("{:<8} {:<16} {:>8.4f} {:>8.4f} {:>8.4f}".format(
            p["scene"], p["source"], b1, b2c, b15))
    pos_pass = [r for r in pos_rows if r["v2_pass"]]
    pos_pass15 = [r for r in pos_rows if r["v1_5_pass"]]
    pos_pass1 = [r for r in pos_rows if r["v1_pass"]]
    pos_ok = len(pos_pass) == len(pos_rows)
    print()
    print("正门: v2 {}/{} | v1 {}/{} | v1.5 {}/{} => {}".format(
        len(pos_pass), len(pos_rows), len(pos_pass1), len(pos_rows),
        len(pos_pass15), len(pos_rows), "**PASS ✔**" if pos_ok else "**FAIL ✘**"))

    # ---------- 反门 ----------
    print()
    print("=== 反门（要求 0 误通过）===")
    neg_rows = []
    for n in neg:
        b1, b2, b15 = scores(R / n["frame"], n["path"])
        neg_rows.append({**n, "v1": b1, "v2": b2, "v1_5": b15,
                         "v1_fp": b1 >= THRESHOLD, "v2_fp": b2 >= THRESHOLD,
                         "v1_5_fp": b15 >= THRESHOLD})
    fp2 = [r for r in neg_rows if r["v2_fp"]]
    fp1 = [r for r in neg_rows if r["v1_fp"]]
    fp15 = [r for r in neg_rows if r["v1_5_fp"]]
    neg_ok = len(fp2) == 0
    print("反门: v2 误通过 {} / {} | v1 误通过 {} / {} | v1.5 误通过 {} / {} => {}".format(
        len(fp2), len(neg_rows), len(fp1), len(neg_rows), len(fp15), len(neg_rows),
        "**PASS ✔**" if neg_ok else "**FAIL ✘**"))
    print()
    print("  最高分 10 条（反门）:")
    for r in sorted(neg_rows, key=lambda z: -z["v2"])[:10]:
        print("    {:<6} vs {:<42} v1 {:.4f} v2 {:.4f} {}{}".format(
            r["scene"], str(r["other"])[:42], r["v1"], r["v2"],
            " <=v1误通过" if r["v1_fp"] else "",
            " **v2误通过**" if r["v2_fp"] else ""))
    print()
    print("  v1 两条误通过对照:")
    for r in neg_rows:
        if r["watch"]:
            print("    {:<6} vs 301ff850be9c v1 {:.4f} v2 {:.4f} {}".format(
                r["scene"], r["v1"], r["v2"], "**仍误通过**" if r["v2_fp"] else "已消除 ✔"))

    verdict = "ADOPT_V2" if (pos_ok and neg_ok) else "REJECT_V2"
    out = {"schema": "p32-2-bank-v2-dual-gate-v1", "threshold": THRESHOLD,
           "step_assertion": {"limit_px": CD.BANK_STEP_PX_V2, "ok": step_ok,
                              "rows": step_rows},
           "positive": {"n": len(pos_rows), "pass_v2": len(pos_pass),
                        "pass_v1": len(pos_pass1), "pass_v1_5": len(pos_pass15),
                        "ok": pos_ok, "rows": pos_rows},
           "negative": {"n": len(neg_rows), "fp_v2": len(fp2), "fp_v1": len(fp1),
                        "fp_v1_5": len(fp15),
                        "ok": neg_ok, "top": sorted(neg_rows, key=lambda z: -z["v2"])[:20],
                        "watch": [r for r in neg_rows if r["watch"]]},
           "verdict": verdict, "elapsed_s": round(time.time() - t0, 1),
           "zero_llm": True, "zero_vlm": True, "zero_network": True}
    (L / "p32_2_bank_v2_dual_gate.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print()
    print("=" * 74)
    print("判定: {}（正门 {} | 反门 {} | 步进 {}）".format(
        verdict, "PASS" if pos_ok else "FAIL", "PASS" if neg_ok else "FAIL",
        "PASS" if step_ok else "FAIL"))
    print("-> logs/p32_2_bank_v2_dual_gate.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
