"""Stage 3.1 Material Package 组装层。

输出目录（§十二）：
  materials/       已下载预览文件（图片缩略图；视频只给下载地址）
  metadata/        materials.json（全部候选 + 完整 provenance）
  rights/          rights_summary.json（逐素材版权结论 + 署名文案）
  shot_mapping/    每镜映射 {shot}_mapping.json + all_shots.json
  search_log/      search_log.json（查询/来源状态/缺口）
  README.md        人工使用说明 + 诚实声明
人工状态：APPROVED / REJECTED / NEEDS_REVIEW（默认 NEEDS_REVIEW）。
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

import requests

from .ranking import RELEVANCE_MIN, gate_and_score

REUSE_PENALTY = 12.0  # 跨镜复用同一素材时的排序惩罚
from .rights import classify

UA = {"User-Agent": "video-studio-3.1/0.1 (material research; contact: local)"}
MAX_PREVIEW_MB = 6


def _slug(s: str) -> str:
    s = re.sub(r"[^0-9A-Za-z_\-]+", "_", s)[:60]
    return s.strip("_")


def download_preview(cand, out_path: Path) -> bool:
    if cand.content_type == "video":
        return False  # 视频不下载（给出下载地址即可）
    urls = [u for u in (cand.download_url, cand.original_url) if u]
    for u in urls[:2]:
        try:
            r = requests.get(u, headers=UA, timeout=30)
            r.raise_for_status()
            if len(r.content) > MAX_PREVIEW_MB * 1024 * 1024:
                continue
            ext = ".jpg" if cand.content_type == "image" else ".bin"
            out_path.write_bytes(r.content)
            return True
        except Exception:  # noqa: BLE001
            continue
    return False


def _cand_text(rec) -> str:
    import re as _re
    return _re.sub(r"<[^>]+>", " ", (rec.get("visual_description") or "") + " "
                   + (rec.get("source_name") or "")).strip()


def _diversity_penalty(rec, used_texts: list, used_embeds: list) -> float:
    """跨镜语义去重：与已用 Primary 语义高度重合时扣分（不硬禁，全局最佳仍可保留）。"""
    if not used_embeds:
        return 0.0
    try:
        from .semantic import cosine, embed
        emb = embed([_cand_text(rec)])[0]
        if emb is None:
            return 0.0
        best = max((cosine(emb, u) for u in used_embeds if u), default=0.0)
        return 10.0 if best > 0.88 else 0.0
    except Exception:  # noqa: BLE001
        return 0.0


def build_package(intents, outcomes_by_shot: dict, shotlist: dict,
                  out_dir: Path, source_status: dict, extra_meta: dict) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    for sub in ("materials", "metadata", "rights", "shot_mapping", "search_log"):
        (out_dir / sub).mkdir(exist_ok=True)

    references = {u: i for i, r in enumerate(shotlist.get("references", []), 1)
                  for u in [r.get("url", "")]}
    all_materials, mappings, no_safe, review_rows = [], {}, [], []

    mid = 0
    used_assets: set = set()  # 已用作 Primary 的素材 source_url（跨镜去重）
    used_texts: list = []     # 已用作 Primary 的候选文本（语义去重）
    used_embeds: list = []    # 已用作 Primary 的候选 embedding
    for intent in intents:
        sid = intent.shot_id
        slot = {"shot_id": sid, "section": intent.section, "match_type": intent.match_type,
                "material_kind": intent.material_kind, "status": "NEEDS_REVIEW",
                "primary": None, "alternatives": [], "note": ""}

        # --- Evidence 镜：不搜 b-roll，单独记录证据截图需求（§十一 分离） ---
        if intent.material_kind == "evidence":
            slot["note"] = ("证据截图按 Truth/Evidence 体系处理，不作为 B-roll；"
                            "百度跳转链接须按标题回溯原文（见 PRE_PRODUCTION R4）。")
            slot["evidence_refs"] = intent.evidence_refs
            mappings[sid] = slot
            continue
        if intent.material_kind == "none":
            slot["note"] = "内部占位镜（2.x gap），不成片，无素材需求。"
            mappings[sid] = slot
            continue

        # --- B-roll 镜：检索结果 → 硬门槛 → 评分排序 ---
        if intent.evidence_refs:
            slot["note"] = (f"本镜附带证据引用 {intent.evidence_refs}：证据截图按 "
                            "Truth/Evidence 体系处理，与以下 B-roll 推荐分离（§十一）。")
        outcomes = outcomes_by_shot.get(sid, [])
        passed, rejected = [], []
        for oc in outcomes:
            for cand in oc.candidates:
                rights, scores = gate_and_score(cand, intent, oc.query)
                mid += 1
                rec = {
                    "material_id": f"M-{sid}-{mid:03d}",
                    "shot_id": sid, "query": oc.query,
                    "source": cand.source, "source_name": cand.source_name,
                    "source_url": cand.source_url, "original_url": cand.original_url,
                    "download_url": cand.download_url,
                    "creator": cand.creator, "license": cand.license,
                    "license_url": cand.license_url,
                    "rights_status": rights.status if rights else "UNKNOWN",
                    "commercial_use": rights.commercial_use if rights else False,
                    "attribution_required": rights.attribution_required if rights else False,
                    "attribution_text": rights.attribution_text if rights else "",
                    "content_type": cand.content_type,
                    "duration": cand.duration,
                    "resolution": cand.resolution,
                    "visual_description": cand.visual_description,
                    "match_type": intent.match_type,
                    "match_score": scores["final_score"] if scores else None,
                    "score_detail": scores or None,
                    "review_status": "NEEDS_REVIEW",
                    "copyright_notes": rights.copyright_notes if rights else "",
                    "retrieved_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                }
                all_materials.append(rec)
                if scores is None:
                    rejected.append(rec)
                else:
                    passed.append(rec)

        passed.sort(key=lambda r: -(r["match_score"] or 0))
        # 语义相关度下限（防"凑答案"）：低于阈值的候选不得担任 Primary
        eligible = [r for r in passed
                    if (r.get("score_detail") or {}).get("semantic_match", 0)
                    >= RELEVANCE_MIN]
        if not eligible:
            rejected_reasons = [
                f"{r['material_id']}:{r['rights_status']}" for r in rejected[:8]]
            low_reasons = [f"{r['material_id']}:semantic={r['score_detail']['semantic_match']}"
                           for r in passed[:8]]
            no_safe.append({
                "shot_id": sid,
                "searched_queries": [o.query for o in outcomes],
                "searched_sources": sorted({o.source for o in outcomes}),
                "rejected_candidates": len(rejected),
                "rejection_reasons": rejected_reasons,
                "low_relevance_candidates": low_reasons,
                "recommendation": _selfmake_hint(intent),
            })
            slot["note"] = ("NO_SAFE_MATCH：无达到语义相关度下限的安全素材"
                            "（存在 SAFE 但语义不相关的候选，已拒绝凑数），推荐自制。")
        else:
            # 跨镜去重：URL 复用扣分 + 与已用 Primary 语义重合扣分（仍可作 ALT）
            for r in eligible:
                r["reuse_penalty"] = REUSE_PENALTY if r["source_url"] in used_assets else 0.0
                r["diversity_penalty"] = _diversity_penalty(r, used_texts, used_embeds)
            eligible.sort(key=lambda r: -((r["match_score"] or 0)
                                          - r["reuse_penalty"] - r["diversity_penalty"]))
            safe = [r for r in eligible if r["rights_status"] == "SAFE"]
            cond = [r for r in eligible if r["rights_status"] == "CONDITIONAL"]
            ordered = safe + cond
            slot["primary"] = ordered[0]
            slot["alternatives"] = ordered[1:3]
            slot["status"] = "NEEDS_REVIEW"
            used_assets.add(ordered[0]["source_url"])
            used_texts.append(_cand_text(ordered[0]))
            try:
                from .semantic import embed
                used_embeds.append(embed([used_texts[-1]])[0])
            except Exception:  # noqa: BLE001
                used_embeds.append(None)
            if ordered[0]["rights_status"] == "CONDITIONAL":
                slot["note"] += " 首选为 CONDITIONAL：使用须按 attribution_text 署名。"
            if ordered[0].get("reuse_penalty") or ordered[0].get("diversity_penalty"):
                slot["note"] += (" 首选素材与他镜重合（URL/语义复用，已扣分仍为局部最优），"
                                 "请人工确认或换 ALT。")
            # 下载预览
            for rank, rec in enumerate(ordered[:3], 1):
                file_name = f"{sid}_{rank}_{rec['material_id']}"
                # 需要 Candidate 对象下载预览，从 outcomes 找对应
                for oc in outcomes:
                    for cand in oc.candidates:
                        if cand.source_url == rec["source_url"]:
                            p = out_dir / "materials" / f"{file_name}.jpg"
                            if download_preview(cand, p):
                                rec["preview_file"] = p.name
                            break
                    if "preview_file" in rec:
                        break
        mappings[sid] = slot
        review_rows.append({"shot_id": sid, "status": "NEEDS_REVIEW",
                            "primary": (slot["primary"] or {}).get("material_id"),
                            "note": slot["note"]})

    # ---- 写盘 ----
    (out_dir / "metadata" / "materials.json").write_text(
        json.dumps({"materials": all_materials, "_meta": extra_meta},
                   ensure_ascii=False, indent=2), encoding="utf-8")

    rights_summary = [
        {"material_id": m["material_id"], "rights_status": m["rights_status"],
         "license": m["license"], "license_url": m["license_url"],
         "commercial_use": m["commercial_use"],
         "attribution_required": m["attribution_required"],
         "attribution_text": m["attribution_text"],
         "copyright_notes": m["copyright_notes"]}
        for m in all_materials]
    (out_dir / "rights" / "rights_summary.json").write_text(
        json.dumps(rights_summary, ensure_ascii=False, indent=2), encoding="utf-8")

    for sid, slot in mappings.items():
        (out_dir / "shot_mapping" / f"{sid}_mapping.json").write_text(
            json.dumps(slot, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "shot_mapping" / "all_shots.json").write_text(
        json.dumps({"shots": mappings, "no_safe_match": no_safe,
                    "review_rows": review_rows},
                   ensure_ascii=False, indent=2), encoding="utf-8")

    search_log = {
        "source_status": source_status,
        "queries": [{"shot_id": k, "outcomes": [
            {"query": o.query, "source": o.source, "status": o.status,
             "candidates": len(o.candidates), "note": o.note} for o in v]}
            for k, v in outcomes_by_shot.items()],
        "_meta": extra_meta,
    }
    (out_dir / "search_log" / "search_log.json").write_text(
        json.dumps(search_log, ensure_ascii=False, indent=2), encoding="utf-8")

    readme = build_readme(len(intents), len(all_materials), len(no_safe),
                          source_status, extra_meta)
    (out_dir / "README.md").write_text(readme, encoding="utf-8")

    # ---- Top-N 预览对比页（人工验收用）----
    (out_dir / "preview.html").write_text(
        build_preview_html(mappings, no_safe), encoding="utf-8")

    return {"shots": len(intents), "materials": len(all_materials),
            "no_safe_match": len(no_safe), "out": str(out_dir)}


def _selfmake_hint(intent) -> str:
    hints = {
        "DIRECT": "自录屏（自己操作 AI/手机/设备）或自拍实景；零版权且贴题。",
        "CONCEPTUAL": "自制动态图表 / 示意图 / UI 动效（剪映文字模板即可）。",
        "EMOTIONAL": "自拍城市夜景/人物背影，或自制大字卡氛围背景。",
        "RHYTHM": "自拍延时（街道/云）或复用 Pexels/Pixabay 免版权素材（需记 URL）。",
    }
    return hints.get(intent.match_type, "自制字幕卡/图表。")


def build_preview_html(mappings: dict, no_safe: list) -> str:
    """Top-3 预览对比页：人工一眼看到 Primary/ALT1/ALT2 与排序理由。"""
    parts = [
        "<!DOCTYPE html><html lang='zh'><head><meta charset='utf-8'>",
        "<title>Material Package 预览对比（人工验收）</title>",
        "<style>body{font-family:sans-serif;background:#111;color:#eee;padding:24px}",
        ".shot{border:1px solid #333;border-radius:8px;padding:16px;margin:16px 0;background:#1a1a1a}",
        ".card{display:inline-block;vertical-align:top;width:400px;margin:8px;background:#222;border-radius:6px;padding:10px}",
        "img{max-width:100%;max-height:260px;border-radius:4px;display:block;margin:6px 0}",
        ".tag{font-size:12px;color:#8f8;background:#142;padding:2px 6px;border-radius:4px;margin-right:6px}",
        ".neg{color:#f88;background:#422;padding:2px 6px;border-radius:4px}",
        ".meta{font-size:12px;color:#aaa;margin:3px 0}",
        "h2{color:#fc6}.note{color:#fa5;font-size:13px}",
        "</style></head><body><h1>Material Package · 预览对比（Top-3）</h1>"]
    no_safe_ids = {n["shot_id"] for n in no_safe}
    for sid, slot in mappings.items():
        parts.append(f"<div class='shot'><h2>{sid} · {slot['match_type']} · {slot['section']}</h2>")
        if slot.get("note"):
            parts.append(f"<div class='note'>{_esc(slot['note'])}</div>")
        if sid in no_safe_ids:
            rec = next(n for n in no_safe if n["shot_id"] == sid)
            parts.append(f"<div class='note'>NO_SAFE_MATCH → 自制建议：{_esc(rec['recommendation'])}</div>")
            parts.append(f"<div class='meta'>搜索词：{_esc(' / '.join(rec['searched_queries']))}</div>")
            parts.append("</div>")
            continue
        entries = [("PRIMARY", slot.get("primary"))] + [
            (f"ALT{i}", a) for i, a in enumerate(slot.get("alternatives") or [], 1)]
        for label, rec in entries:
            if not rec:
                continue
            score = rec.get("match_score")
            detail = rec.get("score_detail") or {}
            rights = rec.get("rights_status", "")
            img = ""
            if rec.get("preview_file"):
                img = f"<img src='materials/{_esc(rec.get('preview_file'))}'/>"
            elif rec.get("content_type") == "video":
                img = f"<a href='{_esc(rec.get('download_url',''))}' target='_blank'>▶ 视频素材（点击下载转码）</a>"
            else:
                img = f"<a href='{_esc(rec.get('download_url',''))}' target='_blank'>无本地预览（点击下载原图）</a>"
            parts.append(
                f"<div class='card'><b>{label}</b> <span class='tag'>{rights}</span>"
                f"<span class='tag'>{_esc(rec.get('license') or '')}</span><br/>"
                f"{img}"
                f"<div class='meta'>final={score} | concept={detail.get('concept_score')} "
                f"| action={detail.get('action_score')} | overlap={detail.get('overlap_score')} "
                f"| role_fit={detail.get('style_fit')} | {_esc(rec.get('resolution') or '')}</div>"
                f"<div class='meta'>{_esc((rec.get('visual_description') or '')[:140])}</div>"
                f"<div class='meta'>来源：<a href='{_esc(rec.get('source_url',''))}' target='_blank'>文件页</a> "
                f"| 署名：{_esc(rec.get('attribution_text') or '无需')}</div>"
                f"</div>")
        parts.append("</div>")
    parts.append("</body></html>")
    return "\n".join(parts)


def _esc(s) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def build_readme(n_shots, n_materials, n_no_safe, source_status, meta) -> str:
    lines = [
        "# Material Package（Stage 3.1 · AI 素材研究员输出）",
        "",
        "## 一、这是什么",
        "3.1 只做素材研究与采购建议，不生成最终视频（§十二）。真人按以下流程使用：",
        "下载素材 → 整理 → 放入剪辑软件 → 剪辑。",
        "",
        f"- 镜头数：{n_shots} ｜ 候选素材记录：{n_materials} 条 ｜ NO_SAFE_MATCH 镜头：{n_no_safe} 个",
        f"- 输入：{meta.get('input', '')}",
        f"- 生成时间：{meta.get('generated_at', '')}",
        "",
        "## 二、目录结构",
        "```",
        "materials/      已下载预览图（S{镜号}_{位次}_{material_id}.jpg；视频仅给下载地址）",
        "metadata/       materials.json —— 全部候选 + 完整 provenance 字段",
        "rights/         rights_summary.json —— 逐素材版权结论与署名文案",
        "shot_mapping/   {shot}_mapping.json —— 每镜 Primary/Alternatives；all_shots.json 总览",
        "search_log/     search_log.json —— 每条查询、来源状态、缺口",
        "```",
        "",
        "## 三、版权与诚实声明（重要）",
        "1. 本系统**不声称\"绝对不会侵权\"**（§十五）。它只做一件事：基于可验证的许可证与来源信息进行版权风险筛选。",
        "2. 默认推荐池只放 **SAFE**（CC0 / Public Domain / 明确可商用授权）。",
        "3. **CONDITIONAL**（CC BY / CC BY-SA / GFDL）素材仅作为备选列出，使用时必须按 rights/ 中的 attribution_text 署名并遵守许可证条件。",
        "4. **UNSAFE / UNKNOWN 一律被硬门槛淘汰**，不出现在任何推荐位（可在 metadata 中查看被淘汰记录与原因）。",
        "5. 搜索引擎只是发现工具，不是授权证明；所有推荐均追溯到素材原始页面（source_url）。",
        "",
        "## 四、外部素材源状态（诚实记录）",
    ]
    for k, v in source_status.items():
        lines.append(f"- {k}: {v}")
    lines += [
        "",
        "## 五、人工审核（§十三）",
        "每镜映射默认 `NEEDS_REVIEW`。人工逐镜把 shot_mapping 中对应文件的 status 改为：",
        "- `APPROVED`：确认采用；",
        "- `REJECTED`：弃用该候选（可备注原因）；",
        "- `NEEDS_REVIEW`：保持待审。",
        "审核时重点看：为什么推荐（match_score/score_detail）、为什么安全（rights_status/copyright_notes）、",
        "来源（source_url）、许可证（license/license_url）、要不要署名（attribution_required/attribution_text）。",
        "",
        "## 六、NO_SAFE_MATCH 说明",
        f"共 {n_no_safe} 个镜头没有找到可进入默认池的合法素材。宁可没有素材，也不推荐侵权素材。",
        "每个 NO_SAFE_MATCH 记录：搜索过的来源、用过的关键词、候选被淘汰的原因、推荐的自制方案。",
        "详见 shot_mapping/all_shots.json 的 no_safe_match 段。",
        "",
        "## 七、Evidence 与 B-roll 分离（§十一）",
        "Evidence 镜头不搜 B-roll：证据截图按既有 Truth/Evidence 体系处理（百度跳转链接按标题回溯原文）。",
        "普通网页存在 ≠ 其图片/视频可作 B-roll；B-roll 全部单独过版权判定。",
    ]
    return "\n".join(lines) + "\n"
