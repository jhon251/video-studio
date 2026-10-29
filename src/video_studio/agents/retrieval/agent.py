"""Retrieval Agent：素材检索（V1：关键词评分；V2 升级 embedding 语义检索）。

确定性任务，不需要 LLM。只出候选清单，不决定最终选用。
"""

from __future__ import annotations

import json
import re

from ..base import Agent, register


def kw_tokens(text: str) -> set:
    """匹配关键词：CJK 二元组 + 单字 + 拉丁词（长度≥3）。"""
    t = re.sub(r"[\s\W_]+", "", str(text or ""))
    grams = {t[i:i + 2] for i in range(len(t) - 1)} if len(t) > 1 else set()
    chars = set(t) if t else set()
    latin = {w.lower() for w in re.findall(r"[A-Za-z]{3,}", str(text or ""))}
    return grams | chars | latin


def score(text: str, keywords) -> int:
    """混合打分：二元组命中×2 + 单字命中×1 + 拉丁词×2。

    纯二元组过于严格（实测「脑电头环」对「脑机接口/电极」零命中 → 素材被静默丢弃）；
    改为混合打分仍是**词面匹配**，不伪造候选，命中样例在产物中记录以便追溯。
    """
    hay = str(text or "").lower()
    g = [k for k in keywords if len(k) == 2]
    c = [k for k in keywords if len(k) == 1]
    l = [k for k in keywords if len(k) > 2]
    return 2 * sum(1 for k in g if k.lower() in hay) + sum(1 for k in c if k.lower() in hay) \
        + 2 * sum(1 for k in l if k.lower() in hay)


def matched_tokens(text: str, keywords) -> list:
    hay = str(text or "").lower()
    hits = [k for k in keywords if k.lower() in hay]
    hits.sort(key=lambda k: (-len(k), k))
    return hits[:8]


@register
class RetrievalAgent(Agent):
    role = "retrieval"
    tier = "-"
    needs_llm = False
    description = "素材检索：按需求从素材库匹配候选素材；最终选用由剪辑规划与人工决定。"

    def run(self, engine, task: dict) -> None:
        # 读取素材索引：inputs.asset_index_ref → 依赖产物 → **本项目内最新 asset_index**
        # （3.x-Preflight 修复：asset_audit 是 retrieval 的兄弟节点而非祖先，只走依赖链
        #   永远找不到索引 → ingest 了本地素材也会 0 候选。）
        index_artifact_id = None
        index_source = "none"
        ref = task["inputs"].get("asset_index_ref")
        if ref:
            index_artifact_id = ref
            index_source = "inputs.asset_index_ref"
        else:
            for dep in task.get("dependencies", []):
                dep_task = engine.db.get_task(dep)
                for art_id in dep_task.get("artifacts", []):
                    if engine.db.get_artifact(art_id)["type"] == "asset_index":
                        index_artifact_id = art_id
                        index_source = "dependency_artifacts"
                        break
                if index_artifact_id:
                    break
        if index_artifact_id is None:
            # 项目内扫描（只读）：优先**有文件**的 asset_index（避免命中素材 ingest 之前生成的空索引），
            # 若都为空则取最新一个。
            best, best_n = None, -1
            for t in engine.db.list_tasks(task["project_id"]):
                for art_id in (t.get("artifacts") or []):
                    art = engine.db.get_artifact(art_id)
                    if not art or art["type"] != "asset_index":
                        continue
                    try:
                        with open(art["path"], encoding="utf-8") as fh:
                            n = len((json.load(fh) or {}).get("files") or [])
                    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
                        n = 0
                    fresh = (art.get("created_at") or 0)
                    if (n, fresh) > (best_n, (best or {}).get("created_at") or 0):
                        best, best_n = art, n
            if best:
                index_artifact_id = best["artifact_id"]
                index_source = "project_scan_latest" if best_n else "project_scan_empty"
        files = []
        if index_artifact_id:
            art = engine.db.get_artifact(index_artifact_id)
            with open(art["path"], encoding="utf-8") as fh:
                files = json.load(fh).get("files", [])

        query = str(task["inputs"].get("query", "")).strip()
        query_source = "task_inputs"
        if not query:
            # 3.x-Preflight 修复：lifecycle 的 retrieval 任务不带 query，导致 score() 恒为 0、
            # 候选永远为空（即使已 run.py ingest 本地素材）。回退到依赖产物的文本：
            #   visual_plan_output.shots[].description / gen_prompt  +  script_output.segments[].narration
            parts, queue, seen = [], list(task.get("dependencies", [])), set()
            while queue and len(" ".join(parts)) < 2000:
                dep = queue.pop(0)
                if dep in seen:
                    continue
                seen.add(dep)
                dep_task = engine.db.get_task(dep)
                if dep_task is None:
                    continue
                for art_id in dep_task.get("artifacts", []):
                    art = engine.db.get_artifact(art_id)
                    try:
                        with open(art["path"], encoding="utf-8") as fh:
                            payload = json.load(fh)
                    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
                        continue
                    if art["type"] == "visual_plan_output":
                        for sh in payload.get("shots", []):
                            parts.append(str(sh.get("description", "")))
                            parts.append(str(sh.get("gen_prompt", "")))
                    elif art["type"] == "script_output":
                        for sg in payload.get("segments", []):
                            parts.append(str(sg.get("narration", "")))
                queue.extend(dep_task.get("dependencies", []))
            query = " ".join(p for p in parts if p).strip()
            query_source = "dependency_artifacts(visual_plan/script)" if query else "none"
        keywords = kw_tokens(query)
        # ---- 4.x Phase 4-E：检索质量优化（**默认关闭**，默认路径与既有一致）----
        # tools.retrieval.scoring: 默认 "v1"（既有 kw_tokens+score，未改动）| "v2"（多语言归一+概念扩展+词边界）
        # tools.retrieval.query_expansion: 默认 false | true（用中英同义表为**缺少拉丁词**的查询补拉丁查询串）
        from ...core.retrieval_quality import expand_query_latin, load_retrieval_lexicon
        from ...core.retrieval_quality import retrieval_settings as _rq_settings
        from ...core.retrieval_quality import score_v2 as _score_v2
        _rq = _rq_settings(engine.config)
        scoring_mode = _rq["scoring"]
        expand_enabled = _rq["query_expansion"]
        lex = load_retrieval_lexicon() if (scoring_mode == "v2" or expand_enabled) else None
        expanded_terms: list = []
        query_for_provider = query
        if expand_enabled and lex is not None:
            has_latin = bool(re.findall(r"[A-Za-z]{2,}", query))
            if not has_latin:
                expanded_terms = expand_query_latin(query, lex, limit=3)
                if expanded_terms:
                    query_for_provider = (query + " " + " ".join(expanded_terms)).strip()
        candidates = []
        for f in files:
            hay = "{} {}".format(f.get("name", ""), f.get("ext", ""))
            if scoring_mode == "v2" and lex is not None:
                r2 = _score_v2(hay, query, lex)
                if r2["score"] > 0:
                    candidates.append({**f, "match_score": r2["score"],
                                       "matched_tokens": [m for m in r2["matched"]
                                                          if not m.startswith("concept:")][:8],
                                       "match_concepts": r2["concepts"],
                                       "scoring": "v2",
                                       "ambiguous_terms": r2["ambiguous"]})
            else:
                s = score(hay, keywords)
                if s > 0:
                    candidates.append({**f, "match_score": s,
                                       "matched_tokens": matched_tokens(hay, keywords)})
        candidates.sort(key=lambda x: -x["match_score"])
        # ---- 3.x Phase 2-D：外部素材 Provider（接入前的边界实现）----
        # provider 未配置（默认 none）时此段为纯 no-op，local_ingest 行为**完全不变**。
        # 4-E：启用查询扩展时，provider 侧的关键词也要用**扩展后的文本**重算，否则英文命名素材仍匹配不到。
        provider_keywords = kw_tokens(query_for_provider) if expanded_terms else keywords
        external, external_rejected, provider_info, provider_error = self._external_candidates(
            engine, task, query_for_provider, provider_keywords, has_local_index=bool(files))
        candidates = candidates + external
        candidates.sort(key=lambda x: -x["match_score"])
        # 3.x-Preflight：素材能力边界显式标注（加法字段，不改契约）。三种状态必须可区分，
        # 且 provider 未配置时**绝不伪造候选**：
        #   local_ingest = 项目 media/ 内有素材（由 run.py ingest 登记）
        #   none         = 无任何可用素材（成片将退化为纯色底+烧录字幕）
        #   external     = 已配置外部素材 provider 且有候选（当前环境 provider=none，不可达）
        tools_cfg = engine.config.get("tools", {})
        prov = {k: (tools_cfg.get(k) or {}).get("provider", "none") for k in ("search", "image", "video")}
        # Phase 2-D：tools.material.provider 也是"已配置外部 provider"的一种（否则会被误判为 none）
        prov["material"] = (tools_cfg.get("material") or {}).get("provider", "none")
        provider_configured = any(v not in (None, "", "none") for v in prov.values())
        external_found = int((provider_info or {}).get("candidates_found") or 0)
        # 是否"提供过素材"：本地索引有文件，或外部 provider 返回过候选（无论是否通过校验），
        # 或**外部 provider 请求失败**（Phase 2-E：失败属"提供过但不可用"，必须显式 BLOCKED 而非静默出片）。
        material_provided = (bool(files) or bool(external) or external_found > 0
                             or bool(provider_error))
        if files and external:
            mode = "mixed"
        elif external:
            mode = "external"
        elif files:
            mode = "local_ingest"
        elif provider_configured:
            mode = "external_configured_no_candidate"
        else:
            mode = "none"
        data = {"candidates": candidates[:20], "query": query[:2000], "query_source": query_source,
                "index_source": index_source, "indexed_files": len(files),
                # ---- Phase 2-D：provider 边界与外部候选追溯（纯新增字段）----
                "external_provider": provider_info,
                "external_verified": len(external),
                "external_rejected": external_rejected,
                "external_error": provider_error,
                "material_provided": material_provided,
                "external_requested": provider_configured,
                "external_no_candidate": bool(provider_configured and not external),
                "material_mode": mode, "material_mode_reason": {
                    "local_ingest": "项目 media/ 已登记 {} 个文件，候选按关键词匹配".format(len(files)),
                    "none": "无本地素材且 search/image/video provider 均为 none：候选为空（未伪造）",
                    "external_configured_no_candidate": "已配置外部 provider 但本次无候选",
                    "external": "外部 provider 提供 {} 个已校验候选（未通过校验的一律不进入候选）".format(
                        len(external)),
                    "mixed": "本地 {} 个 + 外部已校验 {} 个候选".format(len(files), len(external)),
                }.get(mode, mode),
                "material_providers": prov,
                # ---- Phase 4-E：检索质量配置的可追溯记录（默认 v1 / 不扩展，加法字段）----
                "retrieval_config": {
                    "scoring": scoring_mode,
                    "query_expansion": expand_enabled,
                    "expanded_terms": expanded_terms,
                    "lexicon": ("retrieval-synonyms-v1|" + str(lex.get("sha256"))[:16]
                                if lex else None),
                    "note": ("v1 = 既有 kw_tokens+score（默认，未改动）；v2 = 多语言归一+概念扩展+词边界匹配"
                             "（opt-in）；候选是否可用仍由校验/许可门禁决定，语义正确性仍由 4-B 判定")},
                "candidates_total": len(candidates),
                "summary": f"检索到 {len(candidates)} 个候选素材（mode={mode}）",
                "confidence": 1.0,
                "note": ("V1 关键词评分；V2 升级 embedding 语义检索。"
                         + ("无素材候选：这不是失败，而是无素材可用，未做任何伪造。"
                            if not candidates else "")
                         + ("外部 provider 未通过校验的候选已单列记录，绝不进入渲染。"
                            if external_rejected else ""))}
        artifact_id = engine.write_artifact(task["project_id"], task["task_id"],
                                            "retrieval_candidates", data, summary=data["summary"])
        engine.attach_artifact(task["task_id"], artifact_id)
        engine.db.update_task(task["task_id"], confidence=1.0)

    @staticmethod
    def _external_candidates(engine, task: dict, query: str, keywords,
                             has_local_index: bool = False) -> tuple[list, list, dict, str | None]:
        """3.x Phase 2-D：走统一 Provider 层取外部候选（搜索 → 下载 → 强校验）。

        返回 (已验证候选(现有候选结构), 被拒候选记录, provider 信息, 错误码)。
        provider 未配置时返回空结构（no-op）。**未通过校验的候选绝不进入返回值第一个列表。**

        4.x Phase 4-D：外层加 `ResilientSupply` façade（供给缓存 / 失败分类 / 过程可解释 / 降级阶梯），
        判定逻辑本身**没有任何改动**——仍是 `verify_material` + 许可门禁说了算；缓存命中恢复出的候选
        一律回到"未下载/未校验"，必须重新校验。
        """
        from ...tools.material_provider import MaterialQuery, provider_from_config
        from ...tools.base import ToolContext
        from ...tools.supply import ResilientSupply

        provider, err, policy = provider_from_config(engine.config)
        info = {"configured": provider is not None or err is not None,
                "name": (provider.name if provider else None), "error": err}
        if provider is None:
            return [], [], info, err
        ctx = ToolContext(role="retrieval", project_id=task["project_id"],
                          project_dir=engine.project_dir(task["project_id"]),
                          db=engine.db, config=engine.config)
        supply = ResilientSupply(provider, policy=policy,
                                 project_dir=engine.project_dir(task["project_id"]))
        found, smeta = supply.search(MaterialQuery(text=query[:500], keywords=keywords), ctx)
        if smeta.get("error_code"):
            # 保留**具体**错误码（鉴权/限流/超时/搜索失败），不要一律塌缩成 DOWNLOAD_FAILED
            code = smeta["error_code"]
            info["search_error"] = smeta.get("error_detail") or code
            info["error_code"] = code
            info["supply_report"] = supply.report(facts=ResilientSupply.degradation_facts(
                has_verified_external=False, has_local_index=has_local_index,
                material_policy=(engine.config.get("tools", {}).get("material") or {}),
                provider_requested=True),
                extra={"stage": "search_failed", "cache": smeta.get("cache")})
            return [], [], info, code
        fetched, fmeta = supply.fetch(found, ctx)
        info.update(capabilities=provider.capabilities(), stats=provider.stats,
                    candidates_found=len(found), candidates_verified=0)
        verified, rejected = [], []
        for c in fetched:
            rec = c.to_record()
            if c.status == "VERIFIED":
                verified.append(c.to_candidate())
            else:
                rejected.append({k: rec.get(k) for k in
                                 ("provider", "source_id", "source_url", "name", "ext", "bytes",
                                  "sha256", "license", "attribution", "usage_restrictions",
                                  "download_status", "status", "error_code", "error_detail",
                                  "needs_hitl", "media_type", "decodable")})
        info["candidates_verified"] = len(verified)
        info["candidates_rejected"] = len(rejected)
        # ---- Phase 4-D：供给过程可解释（纯新增字段；判定结论仍来自上面的 status）----
        info["supply"] = {**fmeta, "cache": smeta.get("cache"), "from_cache": smeta.get("from_cache")}
        info["supply_report"] = supply.report(
            fetched=fetched,
            facts=ResilientSupply.degradation_facts(
                has_verified_external=bool(verified), has_local_index=has_local_index,
                material_policy=(engine.config.get("tools", {}).get("material") or {}),
                provider_requested=True),
            extra={"stage": "fetched"})
        return verified, rejected, info, None
