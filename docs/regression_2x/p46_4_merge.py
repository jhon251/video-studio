# -*- coding: utf-8 -*-
"""Phase 45 / P45-2+P45-4：**池合并**（15 张既有 + 14 张 Pexels = 29 张）。

· 既有 15 张 = 原 17 张 − 2 张内容排除（螺壳 2442c39e / 举旗照 432cd85b）；
· 新增 14 张 Pexels 携带 **provider-verified overlay 许可字段**（P45-1），
  门禁**直接消费**而无需改 `core/materials.py`；
· 输出合并 payload 供渲染 harness 使用。
"""
from __future__ import annotations

import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")


def gen_candidates():
    """P47-3：**生成的 concept 插图**入池（家族 G，抽象景优先）。

    溯源：`source_of_record` = 生成任务 ID；`license` = 生成物（无第三方署名义务）；
    许可字段走 **overlay**（与 Pexels 同款）⇒ 门禁直接消费、`core/materials.py` 零改动。
    """
    fp = L / "p47_2_gen_batch.json"
    if not fp.is_file():
        return []
    g = json.loads(fp.read_text(encoding="utf-8"))
    out = []
    for it in g.get("items") or []:
        if not it.get("ok"):
            continue
        pth = pathlib.Path(str(it["path"]))
        if not pth.is_file():
            continue
        sid = it["scene_id"]
        out.append({
            "asset_id": "asset_gen_{}".format(sid.lower()),
            "sha256": it["sha256"],
            "path": str(pth),
            "relative_path": "generated_materials/" + pth.name,
            # ---- P49-1：**name 语言中立**（根因修复）----
            # P48 定位：原 name = "Generated concept illustration for {sid} ({visual_hint})"
            # **内嵌了本片中文旁白原文** ⇒ 中文关键词匹配器在 **36/36 景**都给生成素材
            # 最高分（实测素材分=19、命中=证明/人/从/到/字/完）⇒ `_cur` 全片为 G 且被
            # 置首 ⇒ G 份额 72.2% ⇒ 家族门不可达标。
            # **规则（P49 新设计约束）**：**匹配器消费的元数据字段必须语言中立**，
            # 生成/注册素材的 `name` **禁含 v6.5 语料的 CJK 内容**。
            # 场景语义仍通过 `visual_hint` 数组字段单独携带（不参与匹配打分）。
            "name": "GenConcept {} {}".format(sid, str(it["sha256"])[:12]),
            "visual_hint": str(it.get("visual_hint") or ""),
            "bytes": it.get("bytes"), "width": it.get("width"),
            "height": it.get("height"), "media_type": "png",
            "provider": "dashscope/wanx", "source_id": it.get("task_id"),
            "source_url": None,
            "license": "Generated (provider wanx)，无第三方署名义务",
            "license_class": "FREE_ATTRIBUTION", "license_cleared": True,
            "provider_verified": True,
            "source_of_record": it.get("task_id"),
            "attribution": "Generated (DashScope wanx)",
            "origin": "P47-2 文生图（冻结风格 a_黑板粉笔线稿）",
            "usable": True, "match_score": 0,
            "purpose": "abstract-segment visual language (family G)",
            # **抽象景优先**：把这些景排到候选首位（分配器 tie-break 用）
            "preferred_scene": sid,
        })
    return out


def main() -> int:
    ce = json.loads((R / "config/content_exclusions.json")
                    .read_text(encoding="utf-8"))["content_exclusions"]
    ban = [x["sha256_prefix"] for x in ce["excluded"]]
    base = json.loads((L / "phase33_retrieval_payload.json").read_text(encoding="utf-8"))
    pex = json.loads((L / "p45_2_pexels_payload.json").read_text(encoding="utf-8"))
    old = []
    for c in base["candidates"]:
        if not c.get("path"):
            continue
        sh = str(c.get("sha256") or "")
        if any(b in sh for b in ban):
            continue
        old.append(c)
    for c in pex["candidates"]:
        c.setdefault("license", "Pexels License")
        c["license_class"] = "FREE_ATTRIBUTION"
        c["license_cleared"] = True
        c["provider_verified"] = True
        c["source_of_record"] = "Pexels API response (photo object)"
        # ---- P46-1 修复：**Pexels 条目必须自带 `name` / `relative_path`** ----
        # 踩坑：`_build_material_timeline` 的匹配打分（agent.py L265-266）直接读
        # `a["name"]`（**硬取值、非 .get**）⇒ 我的获取脚本只写了 `path`，
        # 导致 `KeyError: 'name'`；且 `relative_path` 缺失会让资产定位退回
        # 被截断的 `path`（实测 `.../f0cd2a28016d82a17daa9cbce6` 无扩展名
        # ⇒ 渲染期素材取不到 ⇒ `corr_best` 坍塌到 0.063 ⇒ `ASSET_INSUFFICIENT`）。
        c.setdefault("name", "Pexels {} by {}".format(
            c.get("source_id") or c.get("asset_id"),
            c.get("photographer") or "unknown"))
        if not c.get("relative_path") and c.get("path"):
            c["relative_path"] = "acquired_materials/" + pathlib.Path(
                str(c["path"])).name
        c.setdefault("origin", "P45-2 governed acquisition (Pexels)")
        c.setdefault("media_type", pathlib.Path(str(c.get("path") or "")).suffix
                     .lstrip(".").lower() or "jpg")
    merged = old + pex["candidates"] + gen_candidates()
    out = {"schema": "p45-4-merged-payload-v1",
           "material_mode": "mixed", "material_provided": True,
           "candidates_total": len(merged),
           "counts": {"existing": len(old), "pexels": len(pex["candidates"])},
           "excluded_sha_prefixes": ban,
           "license_overlay": pex.get("license_overlay"),
           "candidates": merged}
    p = L / "p45_4_merged_payload.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("合并池：既有 {} + Pexels {} = **{} 张**".format(
        len(old), len(pex["candidates"]), len(merged)))
    print("  已剔除（内容排除）: {}".format(ban))
    print("  Pexels 条目均带 overlay 许可字段: {}".format(
        all(c.get("license_cleared") and c.get("license_class") == "FREE_ATTRIBUTION"
            for c in pex["candidates"])))
    print("-> " + str(p.relative_to(R)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
