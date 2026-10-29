# -*- coding: utf-8 -*-
"""P32-2 必答项（定论）：
 ① P31 渲染中仲裁层的真实路径（enabled？VLM available？called？判定？）
 ② P27 验证链仲裁覆盖的**具体景**（是否有 S11p2/S13p2）
 ③ 手工细网格证实的「素材在屏」 vs VLM 存在层 —— 是否构成 VLM 假阴性
只读。
"""
from __future__ import annotations

import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import render_arbitration as ARB                          # noqa: E402
from video_studio.tools import vlm_judge as VJ                                   # noqa: E402


def main() -> int:
    cfg = json.loads((R / "config" / "config.json").read_text(encoding="utf-8"))
    print("=== ① 仲裁链可用性（生产路径）===")
    resolved, src = ARB.resolve_config(cfg, root=R)
    print("  仲裁 enabled = {} | source = {}".format(resolved.get("enabled"), src))
    vcfg, vsrc = VJ.resolve_config(cfg, root=R)
    ok, why = VJ.available(vcfg)
    print("  VLM available = {} | why = {}".format(ok, why))
    print("  VLM config    = {} | source = {}".format(
        json.dumps({k: v for k, v in vcfg.items()
                    if k in ("enabled", "provider", "model", "prompt_version")},
                   ensure_ascii=False), vsrc))
    print()

    print("=== ② P27 验证链仲裁覆盖的景 ===")
    d = json.loads((L / "phase27_p27_3_verification.json").read_text(encoding="utf-8"))
    ps = d["per_scene_verify"]
    print("  failed_before_arbitration = {}".format(ps.get("failed_before_arbitration")))
    print("  failed_after_arbitration  = {}".format(ps.get("failed_after_arbitration")))
    print("  vlm_cost_usd              = {}".format(ps.get("vlm_cost_usd")))
    arb = ps.get("arbitrated") or []
    print("  仲裁逐景（{} 条）:".format(len(arb)))
    for a in arb:
        v = a.get("vlm") or {}
        print("    {:<7} orig_corr={:<7} presence={:<9} model={}".format(
            a.get("scene_id"), a.get("orig_corr"), v.get("presence"), v.get("model")))
    sids = {a.get("scene_id") for a in arb}
    print()
    print("  **S11p2 是否在 P27 仲裁集内**: {}（orig_corr={}）".format(
        "S11p2" in sids,
        next((a.get("orig_corr") for a in arb if a.get("scene_id") == "S11p2"), None)))
    print("  **S13p2 是否在 P27 仲裁集内**: {}".format("S13p2" in sids))
    print()
    print("=== ③ 证据对照（是否构成 VLM 存在层假阴性）===")
    print("  P31 生产渲染：仲裁 enabled=true，但 **VLM available=False**（PROVIDER_NOT_CONFIGURED）")
    print("    ⇒ 两景按 SKIPPED_NOT_CONFIGURED 处理 ⇒ **未做任何语义判定**，成本 $0.0000。")
    print("    根因：阶段脚本直接 import build_engine/load_config，**未走 run.py 的 load_env(.env)**；")
    print("    `.env` 内确含 VLM_API_KEY（已验证：加载后 available=True）。")
    print("  P27 事后验证脚本：传入了可用 VLM（real 调用 $0.004926），逐景判定：")
    for a in arb:
        v = a.get("vlm") or {}
        print("    {:<7} corr={:<7} -> presence={}".format(
            a.get("scene_id"), a.get("orig_corr"), v.get("presence")))
    print("  ⇒ **S11p2 曾被 VLM 判 present（0.286）** ⇒ 若本轮 VLM 可用，它很可能被放行；")
    print("     **S13p2 从未被 VLM 判定过**（P27 仲裁集内没有它）。")
    print("  ⇒ 因此**不能**声称「VLM 判 absent 而素材在屏」；本轮**无 VLM 假阴性证据**，")
    print("     结论是：生产渲染路径上 VLM **未接线**（可用性缺口），不是 VLM 判错。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
