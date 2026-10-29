"""模型路由与成本控制。

- 四档：R（推理）/ M（平衡）/ F（快速）/ '-'（无 LLM，确定性任务）。
- 统一 complete() 接口：输入 tier + 提示词 + 输出 JSON Schema，返回校验过的 dict。
- 成本计量：token 数/费用回写到任务记录。
- MockLLM 用于测试与演示：按提示词关键词返回预置 JSON。
"""

from __future__ import annotations

import json
import os
import re


class SchemaError(Exception):
    pass


class LLMError(Exception):
    """带显式 code 的 LLM 调用错误（3.x Phase 1）。

    code 语义（对齐 DeepSeek 官方错误码文档）：
      LLM_AUTH(401) / LLM_BALANCE(402) / LLM_BAD_REQUEST(400,422) /
      LLM_RATE_LIMIT(429) / LLM_SERVER(5xx) / LLM_TIMEOUT / LLM_CONNECTION /
      LLM_BUDGET_EXCEEDED（本地预算闸门，未发出请求）
    """

    def __init__(self, code: str, message: str, status: int | None = None):
        super().__init__("[{}] {}".format(code, message))
        self.code = code
        self.status = status


# DeepSeek 官方价目表（USD / 1M tokens），来源：https://api-docs.deepseek.com/quick_start/pricing
# peak 时段为 UTC 周一至周五 01:00-04:00 与 06:00-10:00，其余为 off-peak（半价）。
DEFAULT_PRICING = {
    "deepseek-flash": {
        "peak": {"cache_hit": 0.006, "cache_miss": 0.30, "output": 1.20},
        "off_peak": {"cache_hit": 0.003, "cache_miss": 0.15, "output": 0.60},
    },
    "deepseek-v4-pro": {
        "peak": {"cache_hit": 0.044, "cache_miss": 1.32, "output": 3.96},
        "off_peak": {"cache_hit": 0.022, "cache_miss": 0.66, "output": 1.98},
    },
}

# 5-K（Post-Final Maintenance）：**当前官方模型目标**与历史命名的显式登记。
#   · `deepseek-flash` = 当前官方 **DeepSeek-V4.1-Flash**（日常 M/F 档默认目标）；
#   · `deepseek-v4-pro` = 当前官方 Pro 线（规划 R 档）；
#   · `deepseek-chat` / `deepseek-reasoner` = **历史世代别名**（V4 之前），
#     `deepseek-v4-flash-vision-exp` = 历史视觉实验 id —— 三者**都不再是本项目的版本目标**，
#     仅在历史脚本/配置中作为显式参数出现；未知模型的价格一律 `unknown_pricing:<model>`（不猜价）。
CURRENT_OFFICIAL_MODELS = {
    "routine": "deepseek-flash",          # DeepSeek-V4.1-Flash（M/F 档默认）
    "reasoning": "deepseek-v4-pro",       # Pro 线（R 档默认）
}
LEGACY_MODEL_IDS = ("deepseek-chat", "deepseek-reasoner", "deepseek-v4-flash-vision-exp")


def price_band(now=None) -> str:
    """返回当前计费时段：peak / off_peak（UTC）。"""
    import datetime as _dt
    now = now or _dt.datetime.now(_dt.timezone.utc)
    if now.weekday() < 5 and (1 <= now.hour < 4 or 6 <= now.hour < 10):
        return "peak"
    return "off_peak"


def compute_cost(model: str, usage: dict, pricing: dict | None = None) -> tuple[float, str]:
    """按 token 用量与官方价目表计算费用。返回 (cost_usd, note)。

    未知模型不猜价格：返回 (0.0, "unknown_pricing:<model>")，由上层在报告中标注。
    """
    table = (pricing or DEFAULT_PRICING).get(model)
    if not table:
        return 0.0, "unknown_pricing:{}".format(model)
    band = price_band()
    p = table.get(band) or table.get("off_peak") or {}
    hit = int(usage.get("cache_hit_tokens") or 0)
    miss = int(usage.get("cache_miss_tokens") or usage.get("prompt_tokens") or 0)
    out = int(usage.get("completion_tokens") or 0)
    cost = (hit * p.get("cache_hit", 0.0) + miss * p.get("cache_miss", 0.0)
            + out * p.get("output", 0.0)) / 1_000_000.0
    return cost, band


def validate_json(data, schema: dict, path: str = "$") -> None:
    """极简 JSON Schema 校验（type/object/properties/required/array/enum）。"""
    stype = schema.get("type")
    if stype == "object":
        if not isinstance(data, dict):
            raise SchemaError(f"{path}: 应为对象")
        props = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in data:
                raise SchemaError(f"{path}.{key}: 缺少必填字段")
        for key, value in data.items():
            if key in props:
                validate_json(value, props[key], f"{path}.{key}")
    elif stype == "array":
        if not isinstance(data, list):
            raise SchemaError(f"{path}: 应为数组")
        for i, item in enumerate(data):
            validate_json(item, schema.get("items", {}), f"{path}[{i}]")
    elif stype == "string":
        if not isinstance(data, str):
            raise SchemaError(f"{path}: 应为字符串")
        if "enum" in schema and data not in schema["enum"]:
            raise SchemaError(f"{path}: 值 {data!r} 不在 {schema['enum']}")
    elif stype == "number":
        if not isinstance(data, (int, float)) or isinstance(data, bool):
            raise SchemaError(f"{path}: 应为数字")
    elif stype == "boolean":
        if not isinstance(data, bool):
            raise SchemaError(f"{path}: 应为布尔")


class DeepSeekClient:
    """OpenAI 兼容的 DeepSeek 客户端（requests，无需额外 SDK）。"""

    def __init__(self, config: dict):
        self.api_key = os.environ.get(config.get("api_key_env", "DEEPSEEK_API_KEY"), "")
        self.base_url = config.get("base_url", "https://api.deepseek.com").rstrip("/")
        self.timeout = config.get("timeout_s", 120)
        self.max_retries = int(config.get("max_retries", 2))
        self.backoff_base_s = float(config.get("backoff_base_s", 5))

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def complete(self, model: str, system: str, user: str, max_tokens: int) -> dict:
        import time as _time
        import requests  # 延迟导入

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
            "temperature": 0.7,
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        last: LLMError | None = None
        for attempt in range(1, self.max_retries + 2):     # 首次 + max_retries 次重试
            t0 = _time.perf_counter()
            try:
                resp = requests.post(f"{self.base_url}/chat/completions", headers=headers,
                                     json=payload, timeout=self.timeout)
            except requests.exceptions.Timeout as exc:
                last = LLMError("LLM_TIMEOUT", f"请求超时（{self.timeout}s）: {exc}")
            except requests.exceptions.RequestException as exc:
                last = LLMError("LLM_CONNECTION", f"连接失败: {type(exc).__name__}: {exc}")
            else:
                latency = round((_time.perf_counter() - t0) * 1000)
                if resp.status_code == 200:
                    body = resp.json()
                    usage = body.get("usage", {}) or {}
                    detail = usage.get("prompt_tokens_details", {}) or {}
                    result = {
                        "text": body["choices"][0]["message"]["content"],
                        "tokens": usage.get("total_tokens", 0),
                        "prompt_tokens": usage.get("prompt_tokens", 0),
                        "completion_tokens": usage.get("completion_tokens", 0),
                        "cache_hit_tokens": usage.get("prompt_cache_hit_tokens",
                                                     detail.get("cached_tokens", 0)),
                        "cache_miss_tokens": usage.get("prompt_cache_miss_tokens",
                                                       usage.get("prompt_tokens", 0)),
                        "reasoning_tokens": (usage.get("completion_tokens_details") or {}).get(
                            "reasoning_tokens", 0),
                        "latency_ms": latency,
                        "attempts": attempt,
                        "model": model,
                    }
                    # P9-1：可诊断错误码 —— 推理模型（如 deepseek-flash）的 `reasoning_content`
                    # 与 `content` **共享 max_tokens**；预算被推理吃满时 content 为空，上层此前
                    # 只能看到"JSON 解析失败"。此处显式归类为 LLM_REASONING_BUDGET_EXHAUSTED
                    # 并附 usage 明细。纪律：**不重试**（同预算同提示重试只会重复烧钱）、
                    # **不自动加大预算**、**不改档位**；content 非空时行为完全不变。
                    usage_detail = {"prompt_tokens": result["prompt_tokens"],
                                    "completion_tokens": result["completion_tokens"],
                                    "reasoning_tokens": result["reasoning_tokens"],
                                    "cache_hit_tokens": result["cache_hit_tokens"],
                                    "cache_miss_tokens": result["cache_miss_tokens"],
                                    "max_tokens_requested": max_tokens}
                    if not (result["text"] or "").strip() and int(
                            result["reasoning_tokens"] or 0) > 0:
                        exc = LLMError(
                            "LLM_REASONING_BUDGET_EXHAUSTED",
                            "content 为空且 reasoning_tokens={} > 0（推理与正文共享 "
                            "max_tokens={}）：推理吃满预算、未产出正文；usage={}".format(
                                result["reasoning_tokens"], max_tokens,
                                json.dumps(usage_detail, ensure_ascii=False)),
                            None)
                        exc.usage = usage_detail
                        exc.model = model
                        raise exc
                    return result
                detail_txt = (resp.text or "")[:300]
                if resp.status_code == 401:
                    raise LLMError("LLM_AUTH", f"鉴权失败（API key 无效）: {detail_txt}", 401)
                if resp.status_code == 402:
                    raise LLMError("LLM_BALANCE", f"余额不足: {detail_txt}", 402)
                if resp.status_code in (400, 422):
                    raise LLMError("LLM_BAD_REQUEST", f"请求参数/格式错误: {detail_txt}",
                                   resp.status_code)
                if resp.status_code == 429:
                    last = LLMError("LLM_RATE_LIMIT", f"限流(429)，第 {attempt} 次: {detail_txt}", 429)
                elif resp.status_code >= 500:
                    last = LLMError("LLM_SERVER", f"服务端错误({resp.status_code}): {detail_txt}",
                                    resp.status_code)
                else:
                    raise LLMError("LLM_HTTP_{}".format(resp.status_code),
                                   f"未预期状态码: {detail_txt}", resp.status_code)
            if attempt <= self.max_retries:
                _time.sleep(self.backoff_base_s * (2 ** (attempt - 1)))   # 5s,10s,...
        raise last or LLMError("LLM_UNKNOWN", "未知失败")


class MockLLM:
    """测试/演示客户端：按提示词关键词返回预置 JSON。"""

    def __init__(self, responses: dict[str, dict] | None = None, default: dict | None = None):
        self.responses = responses or {}
        self.default = default or {}

    @property
    def available(self) -> bool:
        return True

    def complete(self, model: str, system: str, user: str, max_tokens: int) -> dict:
        for keyword, payload in self.responses.items():
            if keyword in user or keyword in system:
                return {"text": json.dumps(payload, ensure_ascii=False), "tokens": 100,
                        "prompt_tokens": 80, "completion_tokens": 20,
                        "cache_hit_tokens": 0, "cache_miss_tokens": 80, "reasoning_tokens": 0,
                        "latency_ms": 0, "attempts": 1, "model": model, "mock": True}
        return {"text": json.dumps(self.default, ensure_ascii=False), "tokens": 100,
                "prompt_tokens": 80, "completion_tokens": 20,
                "cache_hit_tokens": 0, "cache_miss_tokens": 80, "reasoning_tokens": 0,
                "latency_ms": 0, "attempts": 1, "model": model, "mock": True}


class Router:
    """R/M/F 档路由：按配置选择模型，校验输出，回写成本。"""

    def __init__(self, config: dict, client):
        self.config = config
        self.client = client
        self.tiers = config.get("tiers", {})
        self.pricing = config.get("pricing") or DEFAULT_PRICING
        cap = config.get("max_total_usd")
        self.max_total_usd = float(cap) if cap is not None else None
        self.spent_usd = 0.0
        self.calls = 0

    def _call(self, tier_cfg: dict, system: str, user: str, on_cost) -> tuple[str, dict]:
        """单次 LLM 调用 + **立即**记账（HTTP 已返回即计费，方案校验失败也不例外）。"""
        # 5-K：档位缺 `model` 时回退到**当前官方**日常模型（DeepSeek-V4.1-Flash 的官方 id `deepseek-flash`），
        # 不再回退到历史别名 `deepseek-chat`（旧世代，已登记为 LEGACY_MODEL_IDS）。
        model = tier_cfg.get("model") or CURRENT_OFFICIAL_MODELS["routine"]
        result = self.client.complete(model, system, user, tier_cfg.get("max_tokens", 4096))
        usage = {k: result.get(k, 0) for k in
                 ("tokens", "prompt_tokens", "completion_tokens", "cache_hit_tokens",
                  "cache_miss_tokens", "reasoning_tokens", "latency_ms", "attempts")}
        usage["model"] = result.get("model", model)
        usage["tier"] = tier_cfg.get("tier_name")
        usage["mock"] = bool(result.get("mock"))
        cost, band = compute_cost(usage["model"], usage, self.pricing)
        usage["cost_usd"] = round(cost, 8)
        usage["price_band"] = band
        self.spent_usd += cost
        self.calls += 1
        if on_cost is not None:
            try:
                import inspect as _inspect
                n = len([p for p in _inspect.signature(on_cost).parameters.values()
                         if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)])
            except (TypeError, ValueError):
                n = 4
            if n >= 4:
                on_cost(usage["model"], usage["tokens"], cost, usage)
            else:
                on_cost(usage["model"], usage["tokens"], cost)
        return result["text"], usage

    @staticmethod
    def _schema_hint(output_schema: dict | None) -> str:
        """把输出 Schema 明确写进提示词（3.x Phase 1 修复）。

        历史缺陷：agent 提示词只写"输出严格 JSON"，从不告诉模型**需要哪些键**；
        Mock 下预置答复恰好合法，真实模型则自造键名 → 方案校验必然失败
        （实测 plan 缺 $.summary、topic 缺 $.proposals）。
        """
        if not output_schema or output_schema.get("type") != "object":
            return ""
        return ("\n\n# 输出格式（必须严格遵守）\n"
                "只输出一个 JSON 对象，不要任何解释文字或 Markdown 围栏；"
                "必须包含以下 JSON Schema 中 required 列出的全部字段，键名逐字一致：\n"
                + json.dumps(output_schema, ensure_ascii=False))

    def complete(self, tier: str, system: str, user: str, output_schema: dict | None,
                 on_cost=None, repair: bool = True) -> dict:
        """on_cost: callable(model, tokens, cost_usd, usage) 成本回写钩子。

        3.x Phase 1：① cost_usd 为按官方价目表**实算**的费用（旧实现误传档位 budget 上限）；
        ② HTTP 返回即记账，失败调用不丢失费用；③ 调用前检查运行级预算闸门；
        ④ Schema 注入提示词 + 方案校验失败时做**一次**修复重试。
        """
        if tier == "-":
            raise SchemaError("该任务不需要 LLM（tier='-'）")
        if self.max_total_usd is not None and self.spent_usd >= self.max_total_usd:
            raise LLMError("LLM_BUDGET_EXCEEDED",
                           "运行级预算已用尽：已花 ${:.4f} ≥ 上限 ${:.4f}（未发出本次请求）".format(
                               self.spent_usd, self.max_total_usd))
        tier_cfg = dict(self.tiers.get(tier, self.tiers.get("M", {})))
        tier_cfg["tier_name"] = tier
        hint = self._schema_hint(output_schema)
        text, _usage = self._call(tier_cfg, system + hint, user, on_cost)
        try:
            data = self._parse_json(text)
            if output_schema is not None:
                validate_json(data, output_schema)
            return data
        except SchemaError as exc:
            if not repair:
                raise
            if self.max_total_usd is not None and self.spent_usd >= self.max_total_usd:
                raise
            fix_user = (user + "\n\n# 上一次输出不合格\n你的上一次输出校验失败：{}\n"
                               "请重新输出**完整且键名逐字正确**的 JSON 对象。".format(str(exc)[:300]))
            text2, _u2 = self._call(tier_cfg, system + hint, fix_user, on_cost)
            data = self._parse_json(text2)
            if output_schema is not None:
                validate_json(data, output_schema)
            return data

    def account_direct_call(self, model: str, result: dict, tag: str = "direct") -> tuple[float, dict]:
        """给**绕过 `complete()` 的直连调用**记账（3.x Phase 1.1）。

        背景：三个 judge 工具（evidence_signal / llm_semantic_judge / sufficiency_judge）
        用 `router.client.complete(...)` 直接调用，不经过本 Router → 既不写费用、也不发
        `LLM_CALL` 事件，形成台账漏账通道（本次对账核查确认这些通道当前未被触发，但风险真实存在）。
        调用方在拿到 result 后调用本方法，即可把该次调用计入 `spent_usd`/`calls`，
        并取回 (cost_usd, usage) 供落库审计。
        """
        usage = {k: result.get(k, 0) for k in
                 ("tokens", "prompt_tokens", "completion_tokens", "cache_hit_tokens",
                  "cache_miss_tokens", "reasoning_tokens", "latency_ms", "attempts")}
        usage["model"] = result.get("model", model)
        usage["tier"] = tag
        usage["mock"] = bool(result.get("mock"))
        cost, band = compute_cost(usage["model"], usage, self.pricing)
        usage["cost_usd"] = round(cost, 8)
        usage["price_band"] = band
        self.spent_usd += cost
        self.calls += 1
        return cost, usage

    def cost_summary(self) -> dict:
        return {"calls": self.calls, "spent_usd": round(self.spent_usd, 6),
                "max_total_usd": self.max_total_usd,
                "client": type(self.client).__name__}

    @staticmethod
    def _parse_json(text: str) -> dict:
        text = text.strip()
        # 容忍 ```json 围栏
        fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
        if fence:
            text = fence.group(1).strip()
        # 容忍正文前后的解释文字：截取首个 { 到最后一个 }
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            text = text[start:end + 1]
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise SchemaError(f"LLM 输出不是合法 JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise SchemaError("LLM 输出顶层应为对象")
        return data
