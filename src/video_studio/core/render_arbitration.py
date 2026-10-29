# -*- coding: utf-8 -*-
"""Phase 19 / P19-1：渲染后逐景核验的 **VLM 存在性仲裁层**（加法、配置门控、**默认关闭**）。

背景：冻结的 48×48 corr 余弦度量有三类结构性盲区（KNOWN_ISSUES #74），会把
**素材确实在屏**的场景误判为失败。Phase 18 P18-3 已证明 `vlm-presence-verify-v1`
在"帧里在不在该素材"这一**存在性**任务上达标（25/25、false-present 0）。

本模块把该能力接入**渲染后逐景核验链**：
  · 仅当某景 `corr < 阈值`（已被度量判失败）时，才调用仲裁层；
  · `present`    ⇒ 该景重分类为 `PASS_VLM_PRESENT`（**放行**，并附 VLM 证据/版本/模型/成本）；
  · `absent` / `uncertain` / **调用失败** ⇒ **维持阻断**（fail-closed 语义零改动）。

开关（与 `config/render_motion.json` 同款外部文件模式）：
  内存 `config.tools.render_arbitration` → `config/render_arbitration.json` → 默认 off。
**`config.json` 零改动**；关闭时核验行为与现状**逐字节一致**（`apply_arbitration`
在门控关闭时直接原样返回入参对象）。
"""
from __future__ import annotations

import json
import os
import pathlib

SCHEMA = "render-arbitration-config-v1"
DEFAULT_CONFIG = {"enabled": False}
EXTERNAL_FILENAME = "render_arbitration.json"

#: 仲裁结论（写入 render_output 逐景证据）
PASS_VLM_PRESENT = "PASS_VLM_PRESENT"
BLOCKED = "BLOCKED"
NOT_NEEDED = "NOT_NEEDED"


def resolve_config(config: dict | None = None, root: str | pathlib.Path | None = None
                   ) -> tuple[dict, str]:
    """三级链：内存 `config.tools.render_arbitration` → `config/render_arbitration.json`
    → 默认 `{"enabled": false}`。返回 `(resolved, source)`。**只做加法**。"""
    r = pathlib.Path(root) if root else pathlib.Path(
        os.environ.get("VIDEO_STUDIO_ROOT", ".")).resolve()
    merged = dict(DEFAULT_CONFIG)
    source = "default"
    p = r / "config" / EXTERNAL_FILENAME
    if p.is_file():
        try:
            j = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(j, dict):
                merged.update({k: v for k, v in j.items()})
                source = str(p)
        except Exception:                                                   # noqa: BLE001
            pass
    mem = ((config or {}).get("tools") or {}).get("render_arbitration")
    if isinstance(mem, dict) and mem:
        merged.update(mem)
        source = "config.tools.render_arbitration"
    return {"enabled": bool(merged.get("enabled", False)),
            "prompt_version": str(merged.get("prompt_version") or ""),
            "model": str(merged.get("model") or ""),
            "_source": source}, source


def _vlm_verifier(root):
    """延迟导入：仅在启用时才 import VLM provider（关闭时零副作用）。"""
    import sys
    sys.path.insert(0, str(pathlib.Path(root) / "src"))
    from video_studio.tools import vlm_judge as V
    return V


def apply_arbitration(*, verification: dict, frame_dir, timeline: list, engine, root,
                      config: dict | None = None, budget_usd: float = 0.5,
                      verifier=None) -> tuple[dict, dict]:
    """对核验结果施加仲裁层。

    **门控关闭时**：原样返回 `(verification, {"enabled": False})` ——
    不新建/不修改任何容器，保证与现状**逐字节一致**。

    门控开启时：仅对 `failed_scenes` 逐景调 VLM；
    `present` ⇒ 从 `failed_scenes` 移入 `arbitrated_scenes`（附证据）；
    其余 ⇒ 留在 `failed_scenes`（维持阻断）。

    返回 `(verification', arbitration_report)`。
    """
    cfg, src = resolve_config(config, root=root)
    if not cfg["enabled"]:
        return verification, {"enabled": False, "source": src,
                              "note": "仲裁层关闭：核验行为与现状逐字节一致"}
    failed = list(verification.get("failed_scenes") or [])
    if not failed:
        return verification, {"enabled": True, "source": src, "called": 0,
                              "arbitrated": [], "still_failed": [],
                              "note": "无失败景 ⇒ 无需仲裁"}

    r = pathlib.Path(root)
    V = verifier or _vlm_verifier(r)
    vcfg, vsrc = V.resolve_config(config, root=r)
    if cfg.get("model"):
        vcfg = {**vcfg, "model": cfg["model"]}
    ok, why = V.available(vcfg)

    spent = 0.0
    arbitrated, still_failed, records = [], [], []
    for f in failed:
        sid = f.get("scene_id")
        rec = {"scene_id": sid, "orig_failure": f, "arbitration": None,
               "final": None, "vlm": None, "cost_usd": 0.0}
        fp = pathlib.Path(frame_dir) / "_frame_{}.png".format(sid)
        asset_path = None
        try:
            idx = next(i for i, s in enumerate(timeline) if s.get("scene_id") == sid)
            asset_path = ((timeline[idx].get("selected_asset") or {}).get("path"))
            # P58-3：**视频素材的仲裁参照 = 已抽的源帧参照图**（VLM 比对图片而非 mp4）。
            if asset_path and str(asset_path).lower().endswith((".mp4", ".webm", ".mov")):
                _sib = sorted(pathlib.Path(str(asset_path)).parent.glob(
                    pathlib.Path(str(asset_path)).name + ".ref_*.jpg"))
                if _sib:
                    asset_path = str(_sib[-1])
        except StopIteration:
            idx = None
        if idx is None or not asset_path or not pathlib.Path(str(asset_path)).is_file() \
                or not fp.is_file():
            rec["arbitration"] = "SKIPPED_MISSING_INPUT"
            rec["final"] = BLOCKED
            still_failed.append(f)
            records.append(rec)
            continue
        if not ok:
            rec["arbitration"] = "SKIPPED_NOT_CONFIGURED"
            rec["final"] = BLOCKED
            still_failed.append(f)
            records.append(rec)
            continue
        res = V.judge_presence(frame_path=fp, asset_path=asset_path, cfg=vcfg, root=r,
                               budget_usd=budget_usd, spent_usd=spent)
        spent = round(spent + float(res.get("cost_usd") or 0.0), 8)
        pres = res.get("presence")
        rec["arbitration"] = "VLM_PRESENCE_VERIFY"
        rec["cost_usd"] = float(res.get("cost_usd") or 0.0)
        rec["vlm"] = {
            "prompt_version": res.get("prompt_version"), "model": res.get("model"),
            "presence": pres, "reason": res.get("reason"),
            "cache_hit": res.get("cache_hit"), "error_code": res.get("error_code"),
            "frame_sha256": (res.get("frame_image") or {}).get("source_sha256"),
            "asset_sha256": (res.get("asset_image") or {}).get("source_sha256"),
        }
        if pres == "present":
            rec["final"] = PASS_VLM_PRESENT
            arbitrated.append({"scene_id": sid, "orig_corr": f.get("corr_expected"),
                               "vlm": rec["vlm"]})
        else:
            rec["final"] = BLOCKED
            still_failed.append(f)
        records.append(rec)

    out = dict(verification)
    out["failed_scenes"] = still_failed
    out["arbitrated_scenes"] = arbitrated
    report = {"enabled": True, "source": src, "vlm_config_source": vsrc,
              "provider_available": ok, "unavailable_reason": why,
              "called": len([r_ for r_ in records if r_["arbitration"]
                             == "VLM_PRESENCE_VERIFY"]),
              "arbitrated": arbitrated, "still_failed": still_failed,
              "records": records, "cost_usd": spent, "budget_usd": budget_usd,
              "policy": ("corr<阈值 ⇒ VLM 存在性核验；present ⇒ PASS_VLM_PRESENT；"
                         "absent/uncertain/失败 ⇒ 维持阻断（fail-closed）")}
    return out, report
