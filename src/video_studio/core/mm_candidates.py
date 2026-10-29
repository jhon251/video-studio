"""5.x Phase 5-B：多模态证据增强 + 人审候选生成（**只生成候选，绝不自动选材/替换/redo**）。

定位：把 5-A 的多模态判定（`MATCH/MISMATCH/UNKNOWN` + 逐域相似度）**转成可解释的候选清单**，
交给 4-C 既有的「人工确认 → decision → changelog → redo」闭环执行；本模块**只读、只算、只列**。

候选的证据链（要求 2）：
  · 候选 asset（asset_id / name / path / sha256 / bytes）
  · 来源（provider / source_id / source_url / scope）
  · 许可证（原样搬运 + `core.materials.classify_license` 机械判类 + 门禁结论）
  · **视觉证据**：候选图片经**同一个真实 CLIP 模型**对 12 个语义域打分 → 期望域相似度 + top-k 域
  · 语义/旁白关联：期望域（由旁白词表推导）+ 命中词 + 该候选在 4-B 域的判定（只读复用）
  · 风险/限制：复用冲突、视觉相似度偏低、许可为本地未声明、素材已被其它镜头占用等

状态码（要求 7，**禁止猜测**）：
  `CANDIDATES_READY` / `BLOCKED:MMC_NO_CANDIDATES`（池里没有可用素材）/
  `BLOCKED:MMC_NO_LICENSED_CANDIDATE`（有素材但许可不明/受限）/
  `UNKNOWN:MMC_MM_UNAVAILABLE`（视觉模型不可用 → 不做视觉证据，不猜）/
  `UNKNOWN:MMC_UNKNOWN_DOMAIN`（旁白推导不出期望域）/
  `UNKNOWN:MMC_LOW_VISUAL_SIM`（候选都达不到视觉阈值）

**不做**：不写库、不写产物、不调用 `select-candidate`、不触发 redo、不改时间轴/选材/BGM。
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .materials import classify_license, is_external_candidate, license_block_reason
from .multimodal import DOMAIN_PROMPTS, SCHEMA as MM_SCHEMA, mm_settings, run_worker

SCHEMA = "mm-candidates-v1"

MMC_DEFAULTS = {
    "enabled": False,               # 与 5-A 一致：默认关闭，只能通过只读命令显式调用
    "max_candidates": 3,            # 每个镜头最多列几个合格候选
    "min_visual_sim": 0.22,         # 候选图片对"期望域"提示词的最低相似度
    "allow_used_by_other_scene": True,   # 是否列出已被其它镜头占用的素材（列出时带复用风险）
    "require_license_clear": True,  # 候选必须许可清晰（外部：PUBLIC_DOMAIN/FREE_ATTRIBUTION）
    "frames_per_candidate": 1,      # 每个候选图片评分的帧数（候选是静态图，1 帧即可）
}

MMC_STATUS = ("CANDIDATES_READY", "UNKNOWN", "BLOCKED")
MMC_CODES = ("MMC_NO_CANDIDATES", "MMC_NO_LICENSED_CANDIDATE", "MMC_MM_UNAVAILABLE",
             "MMC_UNKNOWN_DOMAIN", "MMC_LOW_VISUAL_SIM", "MMC_NO_POOL", "MMC_MM_NO_MODEL")


def mmc_settings(config: dict | None = None) -> dict:
    """读 `tools.mm_candidates`；缺省 = 关闭（与 5-A 同口径）。非法值回退默认，**不放松阈值**。"""
    raw = ((config or {}).get("tools") or {}).get("mm_candidates") or {}
    s = dict(MMC_DEFAULTS)
    notes = []
    for k, v in raw.items():
        if k not in MMC_DEFAULTS:
            continue
        if k == "min_visual_sim":
            try:
                s[k] = float(v)
            except (TypeError, ValueError):
                notes.append("参数 {}={!r} 非法，保留默认 {}".format(k, v, s[k]))
        elif k == "max_candidates":
            try:
                s[k] = max(1, int(v))
            except (TypeError, ValueError):
                notes.append("参数 {}={!r} 非法，保留默认 {}".format(k, v, s[k]))
        elif k in ("allow_used_by_other_scene", "require_license_clear", "enabled"):
            s[k] = bool(v)
        else:
            s[k] = v
    s["_notes"] = notes
    s["_source"] = "tools.mm_candidates" if raw else "default(disabled)"
    return s


def asset_id_of(sha_prefix: str | None) -> str | None:
    """素材稳定标识（与 2-C/3-A 一致）：`asset_` + sha256 前 12 位。"""
    s = str(sha_prefix or "").strip()
    return "asset_" + s[:12] if len(s) >= 12 else None


def pool_from_retrievals(payloads: list, project_dir: Path, timeline: list | None = None) -> dict:
    """把该项目所有 `retrieval_candidates` 产物合并成候选池（**只读**）。

    只收 `verified=True` 且**本地文件存在**的条目（未下载/被拒的候选无法做视觉证据 → 单列 rejected）。
    用法（which scenes use which asset）来自给定 timeline（通常是**被钉定的那个** render_output）。
    """
    used: dict[str, list] = {}
    current: dict[str, str] = {}
    for sc in timeline or []:
        a = sc.get("selected_asset") or {}
        aid = a.get("asset_id") or asset_id_of(a.get("sha256"))
        if aid:
            used.setdefault(aid, []).append(sc.get("scene_id"))
            current[sc.get("scene_id")] = aid
    pool, unusable = [], []
    seen = set()
    for payload in payloads or []:
        for c in (payload.get("candidates") or []):
            rel = str(c.get("path") or "")
            sha16 = str(c.get("sha256") or "")
            aid = asset_id_of(sha16)
            key = aid or rel
            if key in seen:
                continue
            seen.add(key)
            abs_p = Path(project_dir) / "media" / rel if rel else None
            exists = bool(abs_p and abs_p.is_file())
            klass, cleared = classify_license(c.get("license"))
            rec = {
                "asset_id": aid, "name": c.get("name"), "relative_path": rel,
                "abs_path": str(abs_p) if abs_p else None, "exists": exists,
                "sha256_prefix": sha16, "bytes": c.get("size"),
                "license": c.get("license"), "license_class": klass, "license_cleared": bool(cleared),
                "provider": c.get("provider"), "source_id": c.get("source_id"),
                "source_url": c.get("source_url"), "attribution": c.get("attribution"),
                "usage_restrictions": c.get("usage_restrictions"),
                "verified": bool(c.get("verified")),
                "scope": "external" if is_external_candidate(c) else "local_user_material",
                "used_by_scenes": sorted(used.get(aid) or []),
                "match_score": c.get("match_score"),
            }
            rec["license_block"] = license_block_reason(
                {"license": rec["license"], "license_class": klass, "license_cleared": cleared},
                require_license=True)
            (pool if (rec["verified"] and exists) else unusable).append(rec)
        for r in (payload.get("external_rejected") or []):
            unusable.append({
                "asset_id": asset_id_of(r.get("sha256")), "name": r.get("name"),
                "relative_path": None, "exists": False, "sha256_prefix": r.get("sha256"),
                "license": r.get("license"), "license_class": classify_license(r.get("license"))[0],
                "license_cleared": False, "provider": r.get("provider"),
                "source_id": r.get("source_id"), "source_url": r.get("source_url"),
                "attribution": r.get("attribution"), "usage_restrictions": r.get("usage_restrictions"),
                "verified": False, "scope": "external", "used_by_scenes": [],
                "match_score": r.get("match_score"),
                "license_block": None, "reject_code": r.get("error_code"),
                "reject_detail": r.get("error_detail")})
    return {"pool": pool, "unusable": unusable, "used_by_asset": used, "current_by_scene": current}


def labels_for_expected(domain: str | None, prompts: dict | None = None) -> list:
    """候选评分用标签：优先只用期望域的提示词（要求 3：候选须与旁白期望域对齐）。"""
    src = prompts or DOMAIN_PROMPTS
    out = []
    for dom in sorted(src):
        for i, text in enumerate(src[dom]):
            out.append({"id": "{}#{}".format(dom, i), "text": text, "domain": dom})
    return out


def score_candidates(pool: list, expected_domain: str | None, *, root: Path, settings: dict,
                     mm_settings_override: dict | None = None, workdir: Path | None = None) -> dict:
    """用**同一个 CLIP 模型**给候选图片打分（只读）。

    一次 worker 调用覆盖**全部 12 域**标签（每域 3 条提示词）→ 逐候选得到 `by_domain` 各域均值；
    具体镜头的 `visual_sim_expected` 由 `build_scene_candidates()` 按该镜头的期望域取（支持多镜头不同期望域）。
    """
    imgs = [{"id": c["asset_id"], "path": c["abs_path"]}
            for c in pool if c.get("exists") and c.get("abs_path")]
    if not imgs:
        return {"ok": False, "code": "MMC_NO_CANDIDATES", "scores": {}, "model": {},
                "detail": "候选池里没有可读的本地图片"}
    labels = labels_for_expected(None)          # 全 12 域
    res = run_worker(imgs, labels, mm_settings_override or mm_settings({}), root=root,
                     workdir=workdir)
    if not res.get("ok"):
        return {"ok": False, "code": "MMC_MM_UNAVAILABLE", "scores": {},
                "model": res.get("model") or {}, "versions": res.get("versions") or {},
                "detail": res.get("detail"), "worker_code": res.get("code")}
    sims = res.get("similarities") or {}
    dom_of = {l["id"]: l["domain"] for l in labels}
    out = {}
    for aid, per_label in sims.items():
        by_dom: dict[str, list] = {}
        for lid, v in per_label.items():
            by_dom.setdefault(dom_of.get(lid, lid), []).append(float(v))
        means = {d: round(sum(v) / len(v), 6) for d, v in by_dom.items() if v}
        ranked = sorted(means.items(), key=lambda kv: (-kv[1], kv[0]))
        out[aid] = {
            "by_domain": means,
            "visual_sim_expected": means.get(expected_domain) if expected_domain else None,
            "top_domains": [{"domain": d, "sim": s} for d, s in ranked[:3]],
            "visual_best_domain": ranked[0][0] if ranked else None,
            "visual_best_sim": ranked[0][1] if ranked else None,
            "frame_sha256": (res.get("image_sha256") or {}).get(aid),
        }
    return {"ok": True, "code": None, "scores": out, "model": res.get("model") or {},
            "versions": res.get("versions") or {}, "labels": labels,
            "image_sha256": res.get("image_sha256") or {}}


def build_scene_candidates(scene: dict, pool: dict, scoring: dict, settings: dict) -> dict:
    """把「该镜头的多模态判定 + 候选池 + 视觉打分」组织成可解释候选清单（纯函数，只读）。"""
    s = {**MMC_DEFAULTS, **(settings or {})}
    sid = scene.get("scene_id")
    expected = scene.get("expected_domain")
    verdict = scene.get("verdict")
    out = {"scene_id": sid, "mm_verdict": verdict, "mm_code": scene.get("code"),
           "expected_domain": expected, "mm_evidence": {
               "expected_sim": scene.get("expected_sim"),
               "best_other_domain": scene.get("best_other_domain"),
               "best_other_sim": scene.get("best_other_sim"), "delta": scene.get("delta"),
               "top_k": scene.get("top_k"), "reason": scene.get("reason")},
           "current_asset": scene.get("current_asset"), "candidates": [], "rejected": [],
           "status": None, "code": None, "human_command": None,
           "note": ("仅生成候选：需人工用 4-C 的 `select-candidate` 明确选定后，再人工执行 `redo`；"
                    "本命令不写库、不替换、不触发 redo")}
    # fail-closed 优先级：**视觉模型不可用**先于期望域缺失（模型缺失时连"能不能看"都不成立）
    if not scoring.get("ok"):
        out.update(status="UNKNOWN", code=scoring.get("code") or "MMC_MM_UNAVAILABLE",
                   detail=scoring.get("detail"),
                   note="视觉模型不可用 → 不做视觉证据、不生成候选（fail-closed）")
        return out
    if not expected:
        out.update(status="UNKNOWN", code="MMC_UNKNOWN_DOMAIN",
                   note="旁白推导不出期望语义域 → 不生成候选（禁止猜测）")
        return out
    scores = scoring.get("scores") or {}
    cur = scene.get("current_asset")
    used_by_current = (cur.get("asset_id") if isinstance(cur, dict) else cur) or None
    qualified, rejected = [], []
    for c in pool.get("pool") or []:
        sc = dict(scores.get(c.get("asset_id")) or {})
        if expected and sc.get("by_domain"):
            sc["visual_sim_expected"] = (sc["by_domain"] or {}).get(expected)
        rec = {
            "asset_id": c.get("asset_id"), "name": c.get("name"),
            "relative_path": c.get("relative_path"), "sha256_prefix": c.get("sha256_prefix"),
            "bytes": c.get("bytes"), "source": {"provider": c.get("provider"),
                                                "source_id": c.get("source_id"),
                                                "source_url": c.get("source_url"),
                                                "scope": c.get("scope")},
            "license": c.get("license"), "license_class": c.get("license_class"),
            "license_cleared": c.get("license_cleared"), "attribution": c.get("attribution"),
            "usage_restrictions": c.get("usage_restrictions"),
            "visual_evidence": {
                "model_backend": "clip_local",
                "model": (scoring.get("model") or {}).get("snapshot"),
                "weights_sha256": (scoring.get("model") or {}).get("weights_sha256"),
                "expected_domain": expected,
                "visual_sim_expected": sc.get("visual_sim_expected"),
                "visual_best_domain": sc.get("visual_best_domain"),
                "visual_best_sim": sc.get("visual_best_sim"),
                "top_domains": sc.get("top_domains"),
                "image_sha256": sc.get("frame_sha256"),
            },
            "semantic_evidence": {
                "expected_domain_source": scene.get("expected_domain_source"),
                "narration_matched_forms": scene.get("narration_matched_forms"),
                "narration_sha256": scene.get("narration_sha256"),
                "keyword_match_score": c.get("match_score"),
            },
            "used_by_scenes": c.get("used_by_scenes") or [],
            "is_current_asset": bool(used_by_current and c.get("asset_id") == used_by_current),
        }
        risks = []
        if rec["is_current_asset"]:
            risks.append("该素材正是当前镜头正在使用的素材（不构成替换）")
        if rec["used_by_scenes"]:
            risks.append("已被其它镜头占用：{}（复用策略可能阻止或影响其它镜头）".format(
                "/".join(rec["used_by_scenes"])))
        vs = rec["visual_evidence"]["visual_sim_expected"]
        if vs is None:
            risks.append("该候选缺少视觉相似度（未能评分）")
        elif vs < float(s["min_visual_sim"]):
            risks.append("视觉相似度 {:.4f} 低于阈值 {:.2f}（视觉证据不足）".format(
                vs, float(s["min_visual_sim"])))
        if rec["license_class"] in ("RESTRICTED", "UNKNOWN") or not rec["license_cleared"]:
            risks.append("许可为 {}（不得入片，需人工确认授权）".format(rec["license_class"]))
        if rec["source"]["scope"] == "local_user_material":
            risks.append("本地自带素材：许可声明由用户提供，管线不做法律判断")
        risks.append("替换需重跑渲染（人工执行 redo）并重新通过旁白完整性/响度/抽帧核验")
        rec["risks"] = risks
        # 资格判定（机械、可解释）
        reasons = []
        if rec["is_current_asset"]:
            reasons.append("CURRENT_ASSET")
        if vs is None:
            reasons.append("NO_VISUAL_SCORE")
        elif vs < float(s["min_visual_sim"]):
            reasons.append("LOW_VISUAL_SIM({:.4f}<{:.2f})".format(vs, float(s["min_visual_sim"])))
        if s["require_license_clear"] and (rec["license_class"] in ("RESTRICTED", "UNKNOWN")
                                          or not rec["license_cleared"]):
            reasons.append("LICENSE_NOT_CLEAR({})".format(rec["license_class"]))
        if rec["used_by_scenes"] and not s["allow_used_by_other_scene"]:
            reasons.append("USED_BY_OTHER_SCENE")
        if reasons:
            rec["excluded_reasons"] = reasons
            rejected.append(rec)
        else:
            qualified.append(rec)
    qualified.sort(key=lambda r: (-(r["visual_evidence"]["visual_sim_expected"] or 0),
                                  r["asset_id"] or ""))
    out["candidates"] = qualified[:int(s["max_candidates"])]
    out["rejected"] = rejected
    out["pool_size"] = len(pool.get("pool") or [])
    out["unusable_count"] = len(pool.get("unusable") or [])
    if out["candidates"]:
        top = out["candidates"][0]
        out.update(status="CANDIDATES_READY", code=None,
                   human_command=("python run.py select-candidate <project_id> --scene {} "
                                  "--asset {} --by <human_id> --reason \"<理由>\"".format(
                                      sid, top["asset_id"])))
    elif out["pool_size"] == 0:
        out.update(status="BLOCKED", code="MMC_NO_CANDIDATES",
                   note="候选池为空（本项目没有任何已验证的本地候选）→ BLOCKED，不猜测")
    elif rejected:
        out.update(status="BLOCKED", code="MMC_NO_LICENSED_CANDIDATE",
                   note=("候选池有 {} 个素材，但没有一个同时满足『视觉相似度达标 + 许可清晰』→ BLOCKED；"
                         "被排除原因见 rejected[].excluded_reasons").format(out["pool_size"]))
    else:
        out.update(status="UNKNOWN", code="MMC_LOW_VISUAL_SIM",
                   note="没有候选达到视觉阈值 → UNKNOWN（不猜测）")
    return out


def build_report(mm_report: dict, pool: dict, scoring: dict, settings: dict,
                 *, project_id: str | None = None) -> dict:
    """汇总：只对 5-A 标为 MISMATCH / 低置信 UNKNOWN 的镜头生成候选（要求 1）。

    若 5-A 本身因**模型不可用**等原因没有给出判定（`mm_report["error"]`），或存在
    `MM_MODEL_MISSING/MM_PYTHON_MISSING/...` 之类"无法验证"的镜头，则报告级给出
    `UNKNOWN / MMC_MM_UNAVAILABLE`（**不猜、不产出候选**），并把受影响的镜头一并列出。
    """
    scenes = []
    current = pool.get("current_by_scene") or {}
    mm_error = (mm_report or {}).get("error") or None
    for s in mm_report.get("scenes") or []:
        verdict = s.get("verdict")
        code = s.get("code")
        low_conf = verdict == "UNKNOWN" and code in ("MM_AMBIGUOUS", "MM_LOW_SIGNAL")
        unavailable = verdict == "UNKNOWN" and code not in (None, "MM_AMBIGUOUS", "MM_LOW_SIGNAL")
        if verdict != "MISMATCH" and not low_conf and not unavailable:
            continue
        aid = current.get(s.get("scene_id"))
        s2 = dict(s)
        s2["current_asset"] = None
        for c in pool.get("pool") or []:
            if aid and c.get("asset_id") == aid:
                s2["current_asset"] = {"asset_id": aid, "name": c.get("name"),
                                       "license": c.get("license"),
                                       "license_class": c.get("license_class"),
                                       "used_by_scenes": c.get("used_by_scenes")}
        scenes.append(build_scene_candidates(s2, pool, scoring, settings))
    counts = {"CANDIDATES_READY": 0, "UNKNOWN": 0, "BLOCKED": 0}
    for s in scenes:
        counts[s["status"]] = counts.get(s["status"], 0) + 1
    rep_status, rep_code, rep_detail = None, None, None
    if mm_error:
        code = (mm_error or {}).get("code") or "MMC_MM_UNAVAILABLE"
        rep_status = "UNKNOWN"
        rep_code = "MMC_MM_UNAVAILABLE" if str(code).startswith("MM_") else str(code)
        rep_detail = (mm_error or {}).get("detail")
    elif any(s["code"] == "MMC_MM_UNAVAILABLE" for s in scenes):
        rep_status, rep_code = "UNKNOWN", "MMC_MM_UNAVAILABLE"
    return {
        "schema": SCHEMA, "mm_schema": MM_SCHEMA, "project_id": project_id,
        "status": rep_status or ("CANDIDATES_READY" if counts["CANDIDATES_READY"] else
                                 ("BLOCKED" if counts["BLOCKED"] else "NO_FLAGGED_SCENE")),
        "code": rep_code, "detail": rep_detail,
        "settings": {k: v for k, v in settings.items() if not k.startswith("_")},
        "settings_source": settings.get("_source"), "settings_notes": settings.get("_notes") or [],
        "mm_counts": mm_report.get("counts"), "flagged_scenes": len(scenes),
        "counts": counts, "scenes": scenes,
        "visual_model": scoring.get("model") or {}, "visual_versions": scoring.get("versions") or {},
        "pool_summary": {"verified_local": len(pool.get("pool") or []),
                         "unusable": len(pool.get("unusable") or [])},
        "policy": {"mode": "readonly_candidates", "auto_select": False, "auto_replace": False,
                   "auto_redo": False, "writes_to_db": False, "writes_to_production": False,
                   "bypasses_hitl": False, "bypasses_license_gate": False,
                   "requires_human_decision": True,
                   "note": ("只生成候选：必须经人工用 4-C 的 select-candidate 明确选定（写既有 decisions/"
                            "changelog）后，再由人工执行 redo；未经人工确认不改任何生产状态")},
        "note": ("候选≠替换：本报告不写库、不写产物、不触发 redo；4-B/5-A 历史证据原样保留"),
    }
