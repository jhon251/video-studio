# -*- coding: utf-8 -*-
"""P18-3 仲裁层落地：`corr < 阈值` 的场景 → VLM 存在性核验 → present 放行 / 否则维持阻断。

设计纪律（**不放宽真门**）：
  · 仅在**确定性度量已判失败**时启用；**不改变** corr 阈值（仍 0.30）、不改变任何 PI 门禁；
  · `present` ⇒ 场景**放行**（附 VLM 证据 + prompt_version + 模型名）；
  · `absent` / `uncertain` / 调用失败 ⇒ **维持阻断**（fail-closed）；
  · 结果与证据**逐景留痕**，供人工复核与审计。
"""
from __future__ import annotations

import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core.env import load_env                                     # noqa: E402
load_env(R / ".env")
from video_studio.tools import vlm_judge as V                                   # noqa: E402

PACK = R / "output" / "phase17_attr_pack"
SCENES = ("S02", "S06", "S07", "S08", "S13")
BUDGET = 0.50


def arbitrate_scene(*, scene_id: str, frame_path, asset_path, corr_value: float,
                    cfg: dict, root, threshold: float = 0.30,
                    spent_usd: float = 0.0, budget_usd: float = BUDGET) -> dict:
    """单景仲裁：corr >= 阈值 ⇒ 直接放行；否则 VLM 存在性核验。

    返回 {scene_id, corr, threshold, deterministic_pass, arbitration, final,
          vlm_evidence, cost_usd}
    """
    out = {"scene_id": scene_id, "corr": round(float(corr_value), 4),
           "threshold": threshold, "deterministic_pass": bool(corr_value >= threshold),
           "arbitration": None, "final": None, "vlm_evidence": None, "cost_usd": 0.0}
    if out["deterministic_pass"]:
        out["final"] = "PASS_DETERMINISTIC"
        out["arbitration"] = "NOT_NEEDED"
        return out
    res = V.judge_presence(frame_path=frame_path, asset_path=asset_path, cfg=cfg,
                           root=root, budget_usd=budget_usd, spent_usd=spent_usd)
    pres = res.get("presence")
    out["arbitration"] = "VLM_PRESENCE_VERIFY"
    out["cost_usd"] = float(res.get("cost_usd") or 0.0)
    out["vlm_evidence"] = {
        "prompt_version": res.get("prompt_version"),
        "model": res.get("model"),
        "presence": pres,
        "reason": res.get("reason"),
        "cache_hit": res.get("cache_hit"),
        "error_code": res.get("error_code"),
        "frame_sha256": (res.get("frame_image") or {}).get("source_sha256"),
        "asset_sha256": (res.get("asset_image") or {}).get("source_sha256"),
        "jpeg_sha256": {"frame": (res.get("frame_image") or {}).get("jpeg_sha256"),
                        "asset": (res.get("asset_image") or {}).get("jpeg_sha256")},
    }
    out["final"] = "PASS_VLM_PRESENT" if pres == "present" else "BLOCKED"
    return out


cfg, src = V.resolve_config(json.loads((R / "config" / "config.json").read_text(encoding="utf-8")),
                            root=R)
ok, why = V.available(cfg)
print("provider:", cfg.get("model"), "| available:", ok)
# 五景的确定性 corr（P18-2 最佳变体 m1=max(bank48,bank192) 的值）
CORR = {"S02": 0.6986, "S06": 0.5977, "S07": 0.2766, "S08": 0.8644, "S13": 0.3763}
# 为验证仲裁层，对 S07（唯一 <0.30 者）做核验；其余直接放行
spent = 0.0
rows = []
for sid in SCENES:
    r = arbitrate_scene(scene_id=sid, frame_path=PACK / sid / "frame_50.png",
                        asset_path=next((PACK / sid).glob("asset.*")),
                        corr_value=CORR[sid], cfg=cfg, root=R, spent_usd=spent)
    spent = round(spent + r["cost_usd"], 8)
    rows.append(r)
    print("  {} corr={:<8} 确定性={} 仲裁={} 最终={} | {}".format(
        sid, r["corr"], r["deterministic_pass"], r["arbitration"], r["final"],
        (r["vlm_evidence"] or {}).get("reason", "")[:44] if r["vlm_evidence"] else ""))

rep = {
    "schema": "phase18-p18-3-arbitration-v1",
    "stage": "Phase 18 P18-3 仲裁层（corr<阈值 → VLM 存在性核验）",
    "policy": ("仅当确定性度量判失败时启用；阈值仍 0.30；present ⇒ 放行（附证据）；"
               "absent/uncertain/失败 ⇒ 维持阻断（fail-closed）；结果逐景留痕。"),
    "threshold": 0.30,
    "provider": {"model": cfg.get("model"), "available": ok,
                 "prompt_version": V.PROMPT_VERSION_PRESENCE, "config_source": src},
    "corr_source": "P18-2 最佳变体 m1 = max(bank48, bank192)",
    "scenes": rows,
    "summary": {"total": len(rows),
                "deterministic_pass": sum(1 for r in rows if r["deterministic_pass"]),
                "arbitrated": sum(1 for r in rows if r["arbitration"] == "VLM_PRESENCE_VERIFY"),
                "final_pass": sum(1 for r in rows if r["final"].startswith("PASS")),
                "final_blocked": sum(1 for r in rows if r["final"] == "BLOCKED")},
    "cost": {"budget_usd": BUDGET, "spent_usd": spent},
    "zero_promotion": True,
}
(L / "phase18_p18_3_arbitration.json").write_text(
    json.dumps(rep, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
print()
print("小结:", json.dumps(rep["summary"], ensure_ascii=False))
print("成本: ${:.4f} / ${:.2f}".format(spent, BUDGET))
print("->", (L / "phase18_p18_3_arbitration.json").relative_to(R).as_posix())
