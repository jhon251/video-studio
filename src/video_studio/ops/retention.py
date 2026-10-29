# -*- coding: utf-8 -*-
"""P9-3/P9-4：留存评分**编排层**（**严格只读**：不写文件、不写 DB、不派任务、不阻断任何流程）。

两层结构：
  · 机械层 = `core/retention.py`（纯函数、零 LLM、确定性）
  · LLM 评审层 = 本模块（tier=R / `deepseek-v4-pro`、**temperature=0**、rubric 0-5 + 原文引用证据 +
    top-3 可执行改稿建议）—— **只建议，不改稿**。

纪律：
  · LLM 不可用 / 调用失败 / 输出非法 ⇒ 报告标 `PARTIAL`（仅机械层结果），**禁止编造分数**。
  · 缓存键 = `prompt_version + model + 输入 sha256`（沿用 `llm_judge_cache` 先例）；
    **本模块只读缓存**（cache 由调用方注入/持久化），ops 自身不写任何东西。
  · `temperature=0` 通过**子类**实现（父类 `DeepSeekClient` 行为不变 ⇒ 不改 router 既有语义、
    不改档位、不改预算）；复用 P9-1 的 `LLM_REASONING_BUDGET_EXHAUSTED` 诊断。
  · 职责边界：**critic 管事实红线，retention 管留存**，二者互不替代；本模块不评事实对错。
"""
from __future__ import annotations

import hashlib
import json
import statistics
import sqlite3
import time
from pathlib import Path

from ..core import retention as RT
from ..core.visual_requirement import canonical, sha256_text
from ..llm.router import DeepSeekClient, LLMError, compute_cost

SCHEMA = "retention-report-v1"
VERSION = 1
PROMPT_VERSION = "retention-judge-v2"   # v1→v2：收紧输出体积（长稿 21 段时 v1 被截断，登记于报告）
JUDGE_TIER = "R"                      # deepseek-v4-pro（授权书指定）
JUDGE_TEMPERATURE = 0.0
#: 评审输出本身很小（分数+引文+3 条建议），但 flash/v4-pro 均为**推理模型**、
#: reasoning 与 content 共享 max_tokens（P9-1 的发现）⇒ 预留 12288：
#: v1 提示词在 21 段长稿上于 8192 处被截断（LLM_OUTPUT_INVALID，实测登记）。
JUDGE_MAX_TOKENS = 12288
RUBRIC_ITEMS = ("hook_strength", "cta_naturalness", "tension_curve")
RUBRIC_MAX = 5

JUDGE_SYSTEM = (
    "你是资深中文视频内容评审（留存向）。你只评**好不好看**：hook 强度、CTA 自然度与内容绑定度、"
    "整体叙事张力曲线。**不评事实对错**（事实由另一条 critic 链负责）。\n"
    "纪律：\n"
    "1) 每项评分 0-5（整数或 .5），**必须**附剧本原文引用作为证据（逐字片段，≤40 字）。\n"
    "2) 证据不足时给 `null` 并在 `uncertain` 说明——**禁止编造分数或引文**。\n"
    "3) tension_curve 需给出逐段张力档位（0-5）与**低谷定位**（哪几段张力最低）。\n"
    "4) 输出 top-3 可执行改稿建议：每条含 `target`（段落下标或 'opening'/'ending'）、`action`、"
    "`why`。**只建议，不改稿**。\n"
    "6) **输出体积纪律**：每项 `evidence` 最多 2 条、每条 ≤20 字；`tension_curve.per_segment` "
    "为整数 0-5 数组（段数超过 24 时只给前 24 段并在 `uncertain` 说明）；不要复述剧本。\n"
    "5) 只输出一个 JSON 对象，不要解释文字、不要 Markdown 围栏。"
)

JUDGE_USER_TEMPLATE = (
    "## 剧本（{n} 段，总时长约 {total:.0f}s）\n{script}\n\n"
    "## 机械层已测得（供参考，不重复评分）\n{mech}\n\n"
    "## 输出 JSON（字段）\n"
    '{{"rubric": {{"hook_strength": {{"score": <0-5|null>, "evidence": ["<原文引用>"], '
    '"rationale": "<一句话>", "uncertain": "<或空>"}}, '
    '"cta_naturalness": {{"score": <0-5|null>, "evidence": ["..."], "rationale": "...", '
    '"uncertain": "..."}}, '
    '"tension_curve": {{"score": <0-5|null>, "per_segment": [<0-5>, ...], '
    '"low_points": [<段落下标>], "evidence": ["..."], "rationale": "..."}}}}, '
    '"suggestions": [{{"target": "...", "action": "...", "why": "..."}}]}}'
)


class TemperatureZeroClient(DeepSeekClient):
    """`temperature=0` 的 DeepSeek 客户端（P9-3 要求）。

    父类 `DeepSeekClient.complete` 硬编码 `temperature=0.7`；为**不改动 router 既有行为**，
    此处以子类覆盖，仅替换 temperature 并复用父类属性（api_key/base_url/timeout/重试策略），
    错误语义与 P9-1 的推理预算诊断保持一致。
    """

    def complete(self, model: str, system: str, user: str, max_tokens: int) -> dict:
        import requests
        payload = {"model": model, "messages": [{"role": "system", "content": system},
                                               {"role": "user", "content": user}],
                   "max_tokens": max_tokens, "temperature": JUDGE_TEMPERATURE}
        headers = {"Authorization": "Bearer {}".format(self.api_key),
                   "Content-Type": "application/json"}
        last = None
        for attempt in range(1, self.max_retries + 2):
            t0 = time.perf_counter()
            try:
                resp = requests.post("{}/chat/completions".format(self.base_url), headers=headers,
                                     json=payload, timeout=self.timeout)
            except requests.exceptions.Timeout as exc:
                last = LLMError("LLM_TIMEOUT", "请求超时（{}s）: {}".format(self.timeout, exc))
            except requests.exceptions.RequestException as exc:
                last = LLMError("LLM_CONNECTION", "连接失败: {}: {}".format(type(exc).__name__, exc))
            else:
                latency = round((time.perf_counter() - t0) * 1000)
                if resp.status_code == 200:
                    body = resp.json()
                    usage = body.get("usage", {}) or {}
                    det = usage.get("completion_tokens_details") or {}
                    result = {"text": body["choices"][0]["message"]["content"],
                              "tokens": usage.get("total_tokens", 0),
                              "prompt_tokens": usage.get("prompt_tokens", 0),
                              "completion_tokens": usage.get("completion_tokens", 0),
                              "cache_hit_tokens": usage.get("prompt_cache_hit_tokens",
                                                            (usage.get("prompt_tokens_details")
                                                             or {}).get("cached_tokens", 0)),
                              "cache_miss_tokens": usage.get("prompt_cache_miss_tokens",
                                                             usage.get("prompt_tokens", 0)),
                              "reasoning_tokens": det.get("reasoning_tokens", 0),
                              "latency_ms": latency, "attempts": attempt, "model": model}
                    if not (result["text"] or "").strip() and int(result["reasoning_tokens"]) > 0:
                        exc = LLMError("LLM_REASONING_BUDGET_EXHAUSTED",
                                       "content 空且 reasoning_tokens={} > 0（max_tokens={}）"
                                       .format(result["reasoning_tokens"], max_tokens), None)
                        exc.usage = {"prompt_tokens": result["prompt_tokens"],
                                     "completion_tokens": result["completion_tokens"],
                                     "reasoning_tokens": result["reasoning_tokens"],
                                     "max_tokens_requested": max_tokens}
                        raise exc
                    return result
                txt = (resp.text or "")[:200]
                if resp.status_code == 401:
                    raise LLMError("LLM_AUTH", "鉴权失败: {}".format(txt), 401)
                if resp.status_code == 402:
                    raise LLMError("LLM_BALANCE", "余额不足: {}".format(txt), 402)
                if resp.status_code in (400, 422):
                    raise LLMError("LLM_BAD_REQUEST", "请求错误: {}".format(txt), resp.status_code)
                if resp.status_code == 429:
                    last = LLMError("LLM_RATE_LIMIT", "限流(429)".format(), 429)
                elif resp.status_code >= 500:
                    last = LLMError("LLM_SERVER", "服务端错误({})".format(resp.status_code),
                                    resp.status_code)
                else:
                    raise LLMError("LLM_HTTP_{}".format(resp.status_code), txt, resp.status_code)
            if attempt <= self.max_retries:
                time.sleep(self.backoff_base_s * (2 ** (attempt - 1)))
        raise last or LLMError("LLM_UNKNOWN", "未知失败")


def script_sha256(script: dict) -> str:
    return sha256_text(canonical(script))


def cache_key(script_sha: str, model: str, prompt_version: str = PROMPT_VERSION,
              sample_index: int = 0) -> str:
    """缓存键 = prompt_version + model + 输入 sha256 + **sample 序号**
    （沿用 `llm_judge_cache` 先例；P10-1 起含 sample 序号以支持多采样聚合）。"""
    return hashlib.sha256("|".join([prompt_version, model, script_sha,
                                    str(int(sample_index))]).encode("utf-8")).hexdigest()


def _script_digest_for_prompt(script: dict, limit: int = 6000) -> str:
    segs = script.get("segments") or []
    lines = []
    for i, s in enumerate(segs):
        lines.append("[{}] ({:.0f}s) {}".format(i, float(s.get("duration_s") or 0),
                                                str(s.get("narration") or "")[:400]))
    txt = "\n".join(lines)
    return txt[:limit]


def build_prompt(script: dict, mechanical: dict) -> tuple[str, str]:
    mech = {k: {"status": v["status"], "codes": v["codes"]}
            for k, v in mechanical["dimensions"].items()}
    user = JUDGE_USER_TEMPLATE.format(
        n=mechanical.get("segment_count", 0),
        total=float(mechanical.get("total_duration_s") or 0),
        script=_script_digest_for_prompt(script),
        mech=json.dumps(mech, ensure_ascii=False))
    return JUDGE_SYSTEM, user


def _parse_json(text: str) -> dict:
    t = (text or "").strip()
    if t.startswith("```"):
        t = t.strip("`")
        t = t.split("\n", 1)[1] if "\n" in t else t
    try:
        return json.loads(t)
    except Exception:                                                     # noqa: BLE001
        i, j = t.find("{"), t.rfind("}")
        if 0 <= i < j:
            try:
                return json.loads(t[i:j + 1])
            except Exception:                                             # noqa: BLE001
                return {}
    return {}


def _validate_rubric(payload: dict) -> list[str]:
    errs = []
    rub = payload.get("rubric") or {}
    for item in RUBRIC_ITEMS:
        blk = rub.get(item)
        if not isinstance(blk, dict):
            errs.append("缺少 rubric.{}".format(item))
            continue
        sc = blk.get("score")
        if sc is not None and not (isinstance(sc, (int, float)) and 0 <= sc <= RUBRIC_MAX):
            errs.append("rubric.{} score 越界".format(item))
        if sc is not None and not (blk.get("evidence") or []):
            errs.append("rubric.{} 有分但无原文证据（禁止编造）".format(item))
    if not isinstance(payload.get("suggestions"), list):
        errs.append("缺少 suggestions")
    return errs


CTA_ABSENT_UNCERTAIN = ("机械层判定 0 CTA（CTA_ABSENT）⇒ 该维度不评、不折算 0；"
                        "P11-1 统一语义：全部采样一致 NOT_ASSESSABLE")


def _cta_absent(mechanical: dict) -> bool:
    """机械层是否判定"无 CTA"（0 处互动引导）。"""
    try:
        return int(((mechanical or {}).get("dimensions") or {}).get("cta", {})
                   .get("measured", {}).get("count") or 0) == 0
    except Exception:                                                     # noqa: BLE001
        return False


def _force_cta_not_assessable(judge: dict, mechanical: dict) -> dict:
    """P11-1：无 CTA 稿件 ⇒ CTA 维度对**全部采样**一致输出 NOT_ASSESSABLE（null）。

    修复 Phase 10 暴露的不一致：旧实现按"可用值"取中位，导致 v2 稿出现
    "仅 1/3 采样给分"的 median=1.0（样本数不足且把"无 CTA"当成"低分"）。
    """
    if judge.get("status") != "OK" or not _cta_absent(mechanical):
        return judge
    item = "cta_naturalness"
    rub = dict(judge.get("rubric") or {})
    rub[item] = {"score": None, "evidence": [], "rationale": None, "uncertain": CTA_ABSENT_UNCERTAIN}
    out = {**judge, "rubric": rub}
    if "aggregation" in judge:
        agg = dict(judge["aggregation"])
        prev = agg.get(item) or {}
        agg[item] = {"median": None, "range": None, "agreement": "NOT_ASSESSABLE",
                     "samples": prev.get("samples"),
                     "scored_samples": 0,
                     "sample_coverage": 0.0,
                     "coverage_note": CTA_ABSENT_UNCERTAIN,
                     "picked_sample_index": None,
                     "forced_not_assessable": True}
        out["aggregation"] = agg
    for ps in out.get("per_sample") or []:
        pr = dict(ps.get("rubric") or {})
        if item in pr:
            pr[item] = {"score": None, "evidence": [], "rationale": None,
                        "uncertain": CTA_ABSENT_UNCERTAIN}
        ps["rubric"] = pr
    out["cta_absent_semantics"] = CTA_ABSENT_UNCERTAIN
    return out


def judge_script(script: dict, *, mechanical: dict, cache: dict | None = None,
                 client=None, model: str | None = None, samples: int = 1) -> dict:
    """LLM 评审（只读；cache 由调用方注入/持久化）。

    `samples == 1`：**行为与 Phase 9 完全一致**（单采样路径不变）。
    `samples > 1`：独立采样 N 次（缓存键含 sample 序号），聚合 median + 全距 + agreement
    （全距 ≤1.0 ⇒ STABLE，否则 UNSTABLE）。
    """
    samples = max(1, int(samples))
    if samples == 1:
        return _force_cta_not_assessable(
            _judge_once(script, mechanical=mechanical, cache=cache, client=client,
                        model=model, sample_index=0, single=True), mechanical)
    per, total_cost, total_usage = [], 0.0, {}
    for i in range(samples):
        one = _judge_once(script, mechanical=mechanical, cache=cache, client=client,
                          model=model, sample_index=i, single=False)
        per.append(one)
        total_cost += float(one.get("cost_usd") or 0.0)
        for k, v in (one.get("usage") or {}).items():
            total_usage[k] = (total_usage.get(k) or 0) + (v or 0)
    ok = [p for p in per if p.get("status") == "OK"]
    base = {"prompt_version": PROMPT_VERSION, "model": model or "deepseek-v4-pro",
            "temperature": JUDGE_TEMPERATURE, "samples": samples,
            "per_sample": [{k: p.get(k) for k in ("sample_index", "cache_hit", "status",
                                                  "reason_code", "rubric", "suggestions",
                                                  "cost_usd", "usage")} for p in per],
            "cost_usd_total": round(total_cost, 6), "usage_total": total_usage,
            "aggregation_note": "median + 全距 + agreement（全距 ≤1.0 ⇒ STABLE）；"
                                "rubric 证据取自中位样本（并列取最小 sample 序号）"}
    if not ok:
        codes = sorted({str(p.get("reason_code")) for p in per if p.get("reason_code")})
        return {**base, "status": "PARTIAL", "reason_code": codes[0] if codes else
                "LLM_CLIENT_UNAVAILABLE", "reason_codes": codes, "cache_hit": False,
                "note": "全部采样失败 ⇒ 仅机械层结果；**未编造任何分数**"}
    agg, rubric = {}, {}
    for item in RUBRIC_ITEMS:
        vals = [((p.get("rubric") or {}).get(item) or {}).get("score") for p in ok]
        nums = [v for v in vals if isinstance(v, (int, float))]
        if not nums:
            agg[item] = {"median": None, "range": None, "agreement": "NOT_ASSESSABLE",
                         "samples": vals}
            rubric[item] = {"score": None, "evidence": [], "rationale": None,
                            "uncertain": "全部采样对该项给出 null"}
            continue
        med = statistics.median(nums)
        rng = round(max(nums) - min(nums), 3)
        pick = next(p for p in ok
                    if ((p.get("rubric") or {}).get(item) or {}).get("score") == med)
        blk = (pick.get("rubric") or {}).get(item) or {}
        agg[item] = {"median": med, "range": rng,
                     "agreement": "STABLE" if rng <= 1.0 else "UNSTABLE",
                     "samples": vals, "scored_samples": len(nums),
                     "sample_coverage": round(len(nums) / len(ok), 3),
                     "coverage_note": ("全部采样均给出分数" if len(nums) == len(ok)
                                       else "**仅 {} / {} 采样给出分数**（其余为 null）⇒ median 的"
                                            "样本数不足，谨慎解读".format(len(nums), len(ok))),
                     "picked_sample_index": pick.get("sample_index")}
        rubric[item] = {**blk, "score": med}
    med_hook = agg["hook_strength"]["median"]
    pick = next((p for p in ok
                 if ((p.get("rubric") or {}).get("hook_strength") or {}).get("score") == med_hook),
                ok[0])
    return _force_cta_not_assessable(
        {**base, "status": "OK", "cache_hit": all(p.get("cache_hit") for p in per),
         "rubric": rubric, "aggregation": agg,
         "suggestions": (pick.get("suggestions") or [])[:3],
         "reasoning_tokens": sum(int((p.get("usage") or {}).get("reasoning_tokens") or 0)
                                 for p in ok) or None}, mechanical)


def _judge_once(script: dict, *, mechanical: dict, cache: dict | None, client,
                model: str | None, sample_index: int, single: bool) -> dict:
    """单次 LLM 评审（`single=True` ⇒ 输出形态与 Phase 9 一致）。"""
    sha = script_sha256(script)
    pol_model = model or "deepseek-v4-pro"
    key = cache_key(sha, pol_model, PROMPT_VERSION, sample_index)
    extra = {} if single else {"sample_index": sample_index}
    base = {"prompt_version": PROMPT_VERSION, "model": pol_model,
            "temperature": JUDGE_TEMPERATURE, "cache_key": key,
            "rubric_items": list(RUBRIC_ITEMS), "rubric_max": RUBRIC_MAX, **extra}
    if cache is not None and key in cache:
        hit = json.loads(json.dumps(cache[key]))                          # 深拷贝，防调用方改坏
        return {**base, **hit, "cache_hit": True, "status": "OK"}
    if client is None:
        return {**base, "status": "PARTIAL", "cache_hit": False,
                "reason_code": "LLM_CLIENT_UNAVAILABLE",
                "note": "LLM 不可用 ⇒ 仅机械层结果；**未编造任何分数**"}
    system, user = build_prompt(script, mechanical)
    try:
        res = client.complete(pol_model, system, user, JUDGE_MAX_TOKENS)
    except LLMError as exc:
        return {**base, "status": "PARTIAL", "cache_hit": False,
                "reason_code": exc.code, "detail": str(exc)[:300],
                "usage": getattr(exc, "usage", None),
                "note": "LLM 调用失败 ⇒ 仅机械层结果；**未编造任何分数**"}
    except Exception as exc:                                              # noqa: BLE001
        return {**base, "status": "PARTIAL", "cache_hit": False,
                "reason_code": "LLM_UNEXPECTED_{}".format(type(exc).__name__),
                "detail": str(exc)[:200],
                "note": "LLM 调用异常 ⇒ 仅机械层结果；**未编造任何分数**"}
    usage = {k: res.get(k, 0) for k in ("prompt_tokens", "completion_tokens",
                                        "cache_hit_tokens", "cache_miss_tokens")}
    cost, band = compute_cost(res.get("model", pol_model), usage)
    payload = _parse_json(res.get("text", ""))
    errs = _validate_rubric(payload)
    if errs:
        return {**base, "status": "PARTIAL", "cache_hit": False,
                "reason_code": "LLM_OUTPUT_INVALID", "detail": errs[:4],
                "raw_text": (res.get("text") or "")[:800],
                "usage": usage, "cost_usd": round(cost, 6), "price_band": band,
                "latency_ms": res.get("latency_ms"),
                "note": "LLM 输出不合法 ⇒ 仅机械层结果；**未编造任何分数**"}
    return {**base, "status": "OK", "cache_hit": False, "rubric": payload.get("rubric"),
            "suggestions": (payload.get("suggestions") or [])[:3],
            "usage": usage, "cost_usd": round(cost, 6), "price_band": band,
            "latency_ms": res.get("latency_ms"), "tokens": res.get("tokens"),
            "reasoning_tokens": res.get("reasoning_tokens"),
            "raw_text_sha256": hashlib.sha256((res.get("text") or "").encode("utf-8")).hexdigest()}


def evaluate(script: dict, *, source: dict | None = None, cache: dict | None = None,
             client=None, model: str | None = None, llm: bool = True,
             taken_at: str | None = None, samples: int = 1) -> dict:
    """完整评分（机械层 + LLM 层）。**只读**：不写文件、不写 DB。

    `samples > 1` ⇒ LLM rubric 多采样聚合（P10-1）；`samples == 1` ⇒ 单采样路径行为不变。
    """
    mech = RT.analyze(script, source=source)
    if llm:
        judge = judge_script(script, mechanical=mech, cache=cache, client=client, model=model,
                             samples=samples)
    else:
        judge = {"status": "PARTIAL", "reason_code": "LLM_DISABLED_BY_CALLER",
                 "prompt_version": PROMPT_VERSION, "model": model or "deepseek-v4-pro",
                 "temperature": JUDGE_TEMPERATURE, "cache_hit": False,
                 "note": "调用方显式关闭 LLM 层 ⇒ 仅机械层结果"}
    body = {
        "schema": SCHEMA, "version": VERSION,
        "generation_method": "mechanical(core/retention.py) + llm-judge(ops/retention.py)",
        "taken_at_utc": taken_at or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "script_sha256": mech["script_sha256"], "source": mech.get("source") or {},
        "mechanical": mech, "llm": judge,
        "responsibility_boundary": {
            "critic": "事实红线（claim 证据链 / 幻觉 / 越界断言）——本模块**不评**",
            "retention": "留存质量（hook/节奏/情绪/CTA）——critic **不评**",
            "note": "二者互不替代；本模块不接入任何生产闸门、不阻断任务、不自动改稿"},
        "out_of_scope": RT.OUT_OF_SCOPE,
        "top_suggestions": judge.get("suggestions") or [],
        "read_only": True, "zero_write": True, "dispatches_tasks": False,
        "applied": False, "executed": False, "requires_human_decision": True,
        "artifact_hash": "",
    }
    body["artifact_hash"] = report_hash(body)
    return body


def report_hash(rep: dict) -> str:
    return sha256_text(canonical({k: v for k, v in rep.items()
                                  if k not in ("artifact_hash", "taken_at_utc")}))


def validate_report(rep: dict) -> list[str]:
    errs = []
    if rep.get("schema") != SCHEMA:
        errs.append("schema 非法")
    if rep.get("artifact_hash") != report_hash(rep):
        errs.append("artifact_hash 不一致（注意 taken_at_utc 不参与哈希）")
    for e in RT.validate(rep.get("mechanical") or {}):
        errs.append("mechanical: {}".format(e))
    llm = rep.get("llm") or {}
    if llm.get("status") not in ("OK", "PARTIAL"):
        errs.append("llm.status 非法")
    if llm.get("status") == "PARTIAL" and (llm.get("rubric")):
        errs.append("PARTIAL 报告不得带 rubric 分数（禁止编造）")
    if llm.get("status") == "OK":
        for e in _validate_rubric({"rubric": llm.get("rubric"),
                                   "suggestions": llm.get("suggestions")}):
            errs.append("llm: {}".format(e))
        if int(llm.get("samples") or 1) > 1:
            agg = llm.get("aggregation") or {}
            for item in RUBRIC_ITEMS:
                blk = agg.get(item) or {}
                if "median" not in blk or "range" not in blk or "agreement" not in blk:
                    errs.append("llm.aggregation.{} 缺少 median/range/agreement".format(item))
                elif blk.get("agreement") not in ("STABLE", "UNSTABLE", "NOT_ASSESSABLE"):
                    errs.append("llm.aggregation.{} agreement 非法".format(item))
                elif ((llm.get("rubric") or {}).get(item) or {}).get("score") != blk.get("median"):
                    errs.append("llm.rubric.{} 不等于聚合 median（多采样一致性）".format(item))
    if rep.get("applied") is not False or rep.get("executed") is not False:
        errs.append("只读报告必须 applied=false / executed=false")
    return errs


# ------------------------------------------------------------------ 人读格式
def format_retention(rep: dict) -> str:
    m = rep.get("mechanical") or {}
    llm = rep.get("llm") or {}
    lines = ["留存评分（只读；critic 管事实、retention 管留存）",
             "  脚本 sha256: {}…".format(str(rep.get("script_sha256"))[:16]),
             "  段数 {} | 总时长 {}s | 机械层得分 {}".format(
                 m.get("segment_count"), m.get("total_duration_s"), m.get("mechanical_score")),
             "  机械层维度:"]
    for d, v in (m.get("dimensions") or {}).items():
        codes = ",".join(v.get("codes") or []) or "-"
        lines.append("    {:16s} {:14s} {}".format(d, v["status"], codes))
    if m.get("structural_codes"):
        lines.append("  结构码（不计 FAIL）: {}".format(m["structural_codes"]))
    if llm.get("status") == "OK":
        lines.append("  LLM 评审（{} / T={} / prompt {}）:".format(
            llm.get("model"), llm.get("temperature"), llm.get("prompt_version")))
        for item, blk in (llm.get("rubric") or {}).items():
            ev = (blk.get("evidence") or [""])[0]
            lines.append("    {:16s} {}/5  证据: {}".format(item, blk.get("score"), ev[:48]))
        for i, s in enumerate(llm.get("suggestions") or [], 1):
            lines.append("    建议{} | {} | {} | {}".format(i, s.get("target"),
                                                            str(s.get("action"))[:60],
                                                            str(s.get("why"))[:60]))
        if llm.get("cache_hit"):
            lines.append("    （缓存命中，未重复调用 LLM）")
    else:
        lines.append("  LLM 评审: {}（{}）⇒ 仅机械层结果，未编造分数".format(
            llm.get("status"), llm.get("reason_code")))
    lines.append("  只读：applied={} executed={}（不接入生产闸门、不阻断任务、不改稿）".format(
        rep.get("applied"), rep.get("executed")))
    return "\n".join(lines)


# ------------------------------------------------------------------ 只读 DB 读取（P9-4 CLI）
def _db_ro(db_path: str | Path) -> sqlite3.Connection:
    """只读打开（mode=ro + query_only）；**不写任何东西**。"""
    con = sqlite3.connect("file:{}?mode=ro".format(Path(db_path).as_posix()), uri=True)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA query_only=ON")
    return con


def load_latest_script(db_path: str | Path, project_id: str,
                       task_id: str | None = None) -> dict:
    """读项目最新 `script_output`（或指定 task 的产物）。只读、不派任务。"""
    con = _db_ro(db_path)
    try:
        if task_id:
            rows = con.execute("select a.artifact_id, a.path from tasks t join artifacts a "
                               "on a.artifact_id in (select value from json_each(t.artifacts)) "
                               "where t.task_id=? and a.type='script_output'",
                               (task_id,)).fetchall()
        else:
            rows = con.execute("select artifact_id, path from artifacts where "
                               "project_id=? and type='script_output' order by created_at desc",
                               (project_id,)).fetchall()
        if not rows:
            return {"found": False, "reason": "NO_SCRIPT_ARTIFACT",
                    "project_id": project_id, "task_id": task_id}
        row = rows[0]
        payload = json.loads(Path(row["path"]).read_text(encoding="utf-8"))
        return {"found": True, "artifact_id": row["artifact_id"], "path": row["path"],
                "script": payload, "project_id": project_id, "task_id": task_id,
                "candidates": len(rows)}
    except (sqlite3.Error, OSError, json.JSONDecodeError) as exc:
        return {"found": False, "reason": "READ_FAILED", "detail": str(exc)[:200],
                "project_id": project_id}
    finally:
        con.close()
