"""4.x Phase 4-D：供给韧性底座（纯函数、离线、确定性、**只读**）。

本模块**不**访问网络、**不**读写数据库、**不**改任何既有判定逻辑；它只提供四件能力：

  1. **失败分类**（限流/超时/永久/策略/许可）——`classify_failure()`：把既有一长串错误码
     （`PROVIDER_*` / `ASSET_*` / 2-C 选择期码）映射为**统一的失败类别 + 是否可重试 + 处置动作**，
     让"失败可解释"有单一来源，而不是散落在各 provider 的 if/else 里。
  2. **重试计划**（有界、确定性）——`retry_decision()`：给定错误码与第几次尝试，返回
     `(是否重试, 退避秒数, 理由)`；退避完全由策略配置决定（无随机抖动），`Retry-After` 只在
     配置上限内被采纳。默认参数下与既有 2-D/2-E 行为**逐值一致**（见 `docs/regression_2x/PHASE4D_REPORT.md`）。
  3. **供给缓存**（搜索层元数据缓存）——`SupplyCache`：按 (provider, 查询, 策略指纹, schema) 缓存
     **候选元数据**（不是字节）。命中只省掉一次搜索请求；**字节仍走内容寻址下载缓存 + 全量校验 +
     许可门禁**，因此缓存**不可能**让未验证素材进入成片（`tests/supply_resilience_test.py` 有断言）。
  4. **可控降级阶梯**——`degradation_plan()`：把"外部已校验 → 本地 → 主题兜底 → 纯色卡 → 阻断"
     写成显式阶梯，并强制两条不变量：`unverified_external_used=False`、`license_bypass=False`。

设计约束（与授权一致）：
  · 不新增数据库表/列（缓存只落**项目目录**下的 JSON 文件，不落库）；
  · 不改 4-A/4-B/4-C 判定逻辑与任何冻结契约；
  · 默认不启用（`supply_cache=False`），需显式配置——默认配置与 `provider=none` 行为完全不变；
  · 供给失败时**绝不**静默使用未验证素材：所有判定仍由 `verify_material` 与许可门禁给出。
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

SUPPLY_SCHEMA = "supply-resilience-v1"

# ---------------- 一、失败分类 ----------------
FAILURE_CLASSES = ("TRANSIENT", "PERMANENT", "POLICY", "LICENSE", "UNKNOWN")
CLASS_MEANING = {
    "TRANSIENT": "临时性失败（网络/限流/服务端），按策略有界重试后仍失败则放弃该候选",
    "PERMANENT": "永久性失败（该素材/端点在本次运行内不会自愈），不重试",
    "POLICY": "策略/配置/本地资源限制（预算、缓存上限、未配置），不重试，需人工或下次运行处理",
    "LICENSE": "许可缺失/不明确/受限：**绝不放行**，转人工（HITL）",
    "UNKNOWN": "未登记错误码：按最保守方式处理（不重试、不放行、如实记录）",
}

# code -> (class, retryable, action)
TAXONOMY: dict[str, tuple[str, bool, str]] = {
    # ---- 传输/Provider 层 ----
    "PROVIDER_NOT_CONFIGURED": ("POLICY", False, "按配置修复后重跑（不伪造候选）"),
    "PROVIDER_UNKNOWN": ("POLICY", False, "provider 名未注册：修配置，不猜测实现"),
    "PROVIDER_TIMEOUT": ("TRANSIENT", True, "有界重试；耗尽后放弃该请求（不降级为未验证素材）"),
    "PROVIDER_HTTP_404": ("PERMANENT", False, "端点/素材不存在：跳过该候选"),
    "PROVIDER_HTTP_5XX": ("TRANSIENT", True, "有界重试；耗尽后放弃该请求"),
    "PROVIDER_HTTP_ERROR": ("PERMANENT", False, "4xx 类客户端错误：不重试，记录并跳过"),
    "PROVIDER_EMPTY_RESPONSE": ("TRANSIENT", True, "有界重试；耗尽后放弃该请求"),
    "PROVIDER_DOWNLOAD_FAILED": ("TRANSIENT", True, "有界重试（可能为源缺失，重试由策略界定）"),
    "PROVIDER_CACHE_LIMIT": ("POLICY", False, "本地缓存上限：不做静默淘汰，拒绝新下载"),
    "PROVIDER_CATALOG_INVALID": ("PERMANENT", False, "目录/端点格式非法：修目录，不静默忽略"),
    "PROVIDER_AUTH_FAILED": ("PERMANENT", False, "凭据问题：人工修复，不重试、不放行"),
    "PROVIDER_RATE_LIMITED": ("TRANSIENT", True, "优先按 Retry-After（上限内）退避重试；耗尽则放弃"),
    "PROVIDER_SEARCH_FAILED": ("TRANSIENT", True, "有界重试；耗尽则本次无外部候选（显式 BLOCKED/HITL）"),
    "PROVIDER_REQUEST_BUDGET": ("POLICY", False, "本次运行请求预算用尽：停止请求（下次运行可恢复）"),
    # ---- 素材校验层 ----
    "ASSET_DANGEROUS_FILENAME": ("PERMANENT", False, "危险文件名：直接拒绝"),
    "ASSET_EXTENSION_NOT_ALLOWED": ("PERMANENT", False, "扩展名不在白名单：拒绝"),
    "ASSET_OVERSIZE": ("PERMANENT", False, "超过单文件上限：拒绝该素材"),
    "ASSET_EMPTY_FILE": ("PERMANENT", False, "0 字节：拒绝"),
    "ASSET_TYPE_MISMATCH": ("PERMANENT", False, "magic bytes 与媒体类型不符：拒绝（不靠扩展名判断）"),
    "ASSET_TRUNCATED": ("TRANSIENT", True, "容器不完整：拒绝该次下载；当前实现不自动重下（如实记录）"),
    "ASSET_PROBE_FAILED": ("PERMANENT", False, "ffprobe 无有效图像/视频流：拒绝"),
    "ASSET_FFMPEG_DECODE_FAILED": ("PERMANENT", False, "ffmpeg 解码失败：拒绝"),
    "ASSET_DECODE_FAILED": ("PERMANENT", False, "PIL 装载失败：拒绝"),
    "ASSET_TOO_SMALL": ("PERMANENT", False, "低于最小尺寸：拒绝"),
    # ---- 许可（绝不重试、绝不放行）----
    "ASSET_LICENSE_MISSING": ("LICENSE", False, "许可缺失：转人工（needs_hitl），不得入片"),
    "ASSET_LICENSE_UNCLEAR": ("LICENSE", False, "许可不明确：转人工（needs_hitl），不得入片"),
    "ASSET_LICENSE_RESTRICTED": ("LICENSE", False, "许可受限（fair use 等）：拒绝，不得入片"),
    # ---- 2-C 选择期码（此处登记以便统一解释；判定逻辑仍只属于 core/materials.py）----
    "ASSET_UNUSABLE": ("PERMANENT", False, "候选不可用：按 2-C 分类学降级"),
    "ASSET_CONFLICT": ("POLICY", False, "与镜头约束冲突：按 2-C 分类学降级"),
    "ASSET_EXHAUSTED": ("POLICY", False, "复用策略禁止复用：按 2-C 分类学降级"),
    "LOW_MATCH": ("PERMANENT", False, "最高分低于阈值：按 2-C 分类学降级"),
    "NO_CANDIDATE": ("PERMANENT", False, "无候选命中：按 2-C 分类学降级"),
}


def classify_failure(code: str | None) -> dict:
    """把错误码映射为统一失败类别。未登记 → UNKNOWN（保守：不重试、不放行）。"""
    key = str(code or "").strip()
    klass, retryable, action = TAXONOMY.get(key, ("UNKNOWN", False, "未登记错误码：保守处理并如实记录"))
    return {"code": key or None, "class": klass, "retryable": bool(retryable),
            "action": action, "meaning": CLASS_MEANING[klass],
            "registered": key in TAXONOMY}


def is_recoverable(code: str | None) -> bool:
    return bool(classify_failure(code)["retryable"])


# ---------------- 二、重试计划（有界、确定性、无抖动）----------------
RETRY_POLICY_DEFAULTS = {
    "max_retries": 2,              # 传输层重试次数（总尝试 = 1 + max_retries）
    "rate_limit_retries": 3,       # 429 单独的（更长）预算，2-E 起沿用
    "rate_limit_backoff_s": 10.0,  # 429 线性退避基数
    "backoff_base_s": 0.2,         # 其它临时性失败线性退避基数
    "max_backoff_s": 30.0,         # 单次退避上限
    "retry_after_max_s": 30.0,     # 采纳 Retry-After 的上限（不无限等待）
}

# 与 2-D/2-E 保持一致：**只有这四类**做传输层重试（这是"行为不变"的关键约束）。
# 注意区分：`classify_failure()` 是**描述性**的（PROVIDER_EMPTY_RESPONSE/PROVIDER_SEARCH_FAILED
# 也属"临时性失败"），而 `retry_decision()` 是**策略性**的（只重试下列四类，沿用 2-D/2-E 冻结语义）。
_RETRYABLE_FOR_TRANSPORT = ("PROVIDER_TIMEOUT", "PROVIDER_HTTP_5XX", "PROVIDER_DOWNLOAD_FAILED",
                            "PROVIDER_RATE_LIMITED")


def retry_decision(code: str | None, attempt: int, policy: dict | None = None,
                   retry_after_s: float | None = None) -> dict:
    """第 `attempt` 次（0 基）尝试失败后：是否重试、等多久、为什么。

    退避与既有实现**逐值一致**（默认策略下）：429 → `min(base*(attempt+1), max)`；
    其它临时性失败 → `min(0.2*(attempt+1), 2.0)`。`Retry-After` 仅在 `retry_after_max_s` 内被采纳。
    """
    pol = {**RETRY_POLICY_DEFAULTS, **(policy or {})}
    key = str(code or "")
    klass = classify_failure(key)["class"]
    rate_limited = key == "PROVIDER_RATE_LIMITED"
    budget = int(pol["rate_limit_retries"]) if rate_limited else int(pol["max_retries"])
    if key not in _RETRYABLE_FOR_TRANSPORT:
        return {"retry": False, "sleep_s": 0.0, "class": klass,
                "reason": "{} 不属可重试类别（{}）".format(key or "空错误码", klass)}
    if attempt >= budget:
        return {"retry": False, "sleep_s": 0.0, "class": klass,
                "reason": "重试预算用尽（attempt={} >= budget={}）".format(attempt, budget)}
    if rate_limited:
        base = float(pol["rate_limit_backoff_s"]) * (attempt + 1)
    else:
        base = float(pol["backoff_base_s"]) * (attempt + 1)
        base = min(base, 2.0)                       # 与既有实现一致：非 429 的退避上限 2.0s
    sleep_s = min(base, float(pol["max_backoff_s"]))
    note = ""
    if rate_limited and retry_after_s is not None:
        hinted = min(float(retry_after_s), float(pol["retry_after_max_s"]))
        if hinted > sleep_s:
            sleep_s, note = hinted, "（采纳 Retry-After，上限 {}s）".format(pol["retry_after_max_s"])
        else:
            note = "（Retry-After={}s 未超过本地退避，忽略）".format(retry_after_s)
    return {"retry": True, "sleep_s": round(sleep_s, 3), "class": klass,
            "reason": "临时性失败，第 {} 次重试退避 {}s{}".format(attempt + 1, round(sleep_s, 3), note)}


# ---------------- 三、失败诊断（失败可解释）----------------
class SupplyDiagnostics:
    """供给过程的结构化记录：每次尝试一条，含类别/动作/是否重试。**只记录，不判定**。"""

    def __init__(self, provider: str | None = None):
        self.provider = provider
        self.attempts: list[dict] = []

    def record(self, *, stage: str, code: str | None, detail: str | None = None,
               scene_id: str | None = None, source_id: str | None = None,
               attempt: int = 0, retry: dict | None = None) -> dict:
        info = classify_failure(code)
        row = {"stage": stage, "code": info["code"], "class": info["class"],
               "retryable": info["retryable"], "action": info["action"],
               "detail": (detail or "")[:300] or None, "scene_id": scene_id,
               "source_id": source_id, "attempt": attempt,
               "retry": bool((retry or {}).get("retry")),
               "sleep_s": float((retry or {}).get("sleep_s") or 0.0)}
        self.attempts.append(row)
        return row

    def counts(self) -> dict:
        out: dict[str, int] = {}
        for a in self.attempts:
            out[a["code"] or "UNKNOWN"] = out.get(a["code"] or "UNKNOWN", 0) + 1
        return out

    def by_class(self) -> dict:
        out: dict[str, int] = {k: 0 for k in FAILURE_CLASSES}
        for a in self.attempts:
            out[a["class"]] = out.get(a["class"], 0) + 1
        return out

    def explanations(self) -> list[str]:
        return ["[{class}] {code}: {action}（{stage}{scene}）".format(
            **{"class": a["class"], "code": a["code"] or "UNKNOWN", "action": a["action"],
               "stage": a["stage"],
               "scene": "" if not a["scene_id"] else " · " + str(a["scene_id"])})
            for a in self.attempts]

    def to_dict(self) -> dict:
        return {"schema": SUPPLY_SCHEMA, "provider": self.provider,
                "attempts": self.attempts, "counts": self.counts(), "by_class": self.by_class(),
                "explanations": self.explanations()}


# ---------------- 四、供给缓存（搜索层元数据缓存）----------------
CACHE_SCHEMA = "supply-search-cache-v1"


def policy_fingerprint(policy: dict | None) -> str:
    """只有**影响搜索结果**的键进入指纹（改配置即换 key，避免用旧策略的候选）。"""
    pol = policy or {}
    keys = ("max_bytes", "allowed_ext", "min_width", "min_height", "license_required",
            "require_https", "search_limit", "provider")
    sub = {k: pol.get(k) for k in keys}
    return hashlib.sha256(json.dumps(sub, sort_keys=True, ensure_ascii=False,
                                     default=str).encode("utf-8")).hexdigest()[:16]


def cache_key(provider_name: str, query_text: str, limit: int, kinds, keywords,
              policy: dict | None) -> str:
    payload = {"schema": CACHE_SCHEMA, "provider": provider_name, "q": str(query_text or ""),
               "limit": int(limit), "kinds": list(kinds or ()),
               "kw": sorted(str(k) for k in (keywords or ())),
               "pol": policy_fingerprint(policy)}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False)
                          .encode("utf-8")).hexdigest()


class SupplyCache:
    """搜索层缓存：**只缓存候选元数据**，字节仍走下载缓存 + 全量校验 + 许可门禁。

    · 目录：`<project_dir>/.supply_cache/search/`（不进 `media/external`，避免影响缓存字节上限口径）
    · 命中条件：文件存在、可解析、schema 一致、未过期（TTL）
    · 任何异常（坏 JSON / 读失败）→ 视为未命中并记原因，**绝不**因缓存问题影响正确性
    """

    def __init__(self, root: str | Path | None, *, enabled: bool = False,
                 ttl_s: float = 900.0, now=None):
        self.root = Path(root) if root else None
        self.enabled = bool(enabled) and self.root is not None
        self.ttl_s = float(ttl_s)
        self._now = now or time.time
        self.stats = {"hits": 0, "misses": 0, "expired": 0, "corrupt": 0, "stores": 0,
                      "disabled": 0}
        self.last_miss_reason: str | None = None

    @property
    def dir(self) -> Path | None:
        return None if self.root is None else self.root / "search"

    def get(self, key: str) -> tuple[list | None, dict]:
        """返回 (候选元数据列表 | None, meta)。meta 含 hit/reason/age_s/cached_at。"""
        if not self.enabled:
            self.stats["disabled"] += 1
            self.last_miss_reason = "DISABLED"
            return None, {"hit": False, "reason": "DISABLED"}
        p = self.dir / "{}.json".format(key)           # type: ignore[union-attr]
        if not p.is_file():
            self.stats["misses"] += 1
            self.last_miss_reason = "MISS"
            return None, {"hit": False, "reason": "MISS", "path": str(p)}
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self.stats["corrupt"] += 1
            self.last_miss_reason = "CORRUPT"
            return None, {"hit": False, "reason": "CORRUPT", "path": str(p)}
        if not isinstance(data, dict) or data.get("schema") != CACHE_SCHEMA:
            self.stats["corrupt"] += 1
            self.last_miss_reason = "SCHEMA_MISMATCH"
            return None, {"hit": False, "reason": "SCHEMA_MISMATCH", "path": str(p)}
        created = float(data.get("created_at") or 0.0)
        age = max(0.0, float(self._now()) - created)
        if self.ttl_s > 0 and age > self.ttl_s:
            self.stats["expired"] += 1
            self.last_miss_reason = "EXPIRED"
            return None, {"hit": False, "reason": "EXPIRED", "age_s": round(age, 3),
                          "ttl_s": self.ttl_s, "path": str(p)}
        cands = data.get("candidates")
        if not isinstance(cands, list):
            self.stats["corrupt"] += 1
            self.last_miss_reason = "CORRUPT"
            return None, {"hit": False, "reason": "CORRUPT", "path": str(p)}
        self.stats["hits"] += 1
        self.last_miss_reason = None
        return cands, {"hit": True, "reason": "HIT", "age_s": round(age, 3),
                       "cached_at": created, "count": len(cands), "path": str(p)}

    def put(self, key: str, candidates: list[dict], meta: dict | None = None) -> dict:
        """原子写；只写元数据。失败不抛异常（缓存永远不是正确性的前提）。"""
        if not self.enabled:
            return {"stored": False, "reason": "DISABLED"}
        try:
            self.dir.mkdir(parents=True, exist_ok=True)   # type: ignore[union-attr]
            payload = {"schema": CACHE_SCHEMA, "key": key, "created_at": float(self._now()),
                       "ttl_s": self.ttl_s, "provider": (meta or {}).get("provider"),
                       "query": (meta or {}).get("query"),
                       "candidates": candidates}
            tmp = (self.dir / "{}.json.tmp".format(key))  # type: ignore[union-attr]
            tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
            os.replace(tmp, self.dir / "{}.json".format(key))  # type: ignore[union-attr]
            self.stats["stores"] += 1
            return {"stored": True, "count": len(candidates)}
        except OSError as exc:
            return {"stored": False, "reason": type(exc).__name__}

    def invalidate(self, key: str) -> bool:
        if not self.enabled:
            return False
        p = self.dir / "{}.json".format(key)           # type: ignore[union-attr]
        try:
            if p.is_file():
                p.unlink()
                return True
        except OSError:
            return False
        return False


# ---------------- 五、可控降级阶梯 ----------------
SUPPLY_LADDER = ("EXTERNAL_VERIFIED", "LOCAL_INGEST", "THEME_FALLBACK", "SOLID_COLOR_CARD",
                 "BLOCKED_FOR_HUMAN")
# 阶梯上"可用素材"与"无素材兜底"的分界：前者必须已校验 + 许可清晰
MATERIAL_RUNGS = ("EXTERNAL_VERIFIED", "LOCAL_INGEST")
FALLBACK_RUNGS = ("THEME_FALLBACK", "SOLID_COLOR_CARD", "BLOCKED_FOR_HUMAN")


def degradation_plan(facts: dict) -> dict:
    """按显式阶梯给出本次供给的降级决定（**只解释，不代替 2-C 判定**）。

    入参 facts（全部由调用方如实给出）：
      has_verified_external / has_local_index / theme_fallback_allowed /
      card_allowed / requires_human
    返回：{"rung", "index", "reason", "allowed_rungs", "invariants"}
    """
    f = dict(facts or {})
    if f.get("has_verified_external"):
        rung, reason = "EXTERNAL_VERIFIED", "外部 provider 有已校验且许可清晰的候选"
    elif f.get("has_local_index"):
        rung, reason = "LOCAL_INGEST", "外部不可用/无候选 → 使用项目本地已登记素材（仍走同一校验）"
    elif f.get("theme_fallback_allowed"):
        rung, reason = "THEME_FALLBACK", "无可用素材且策略允许主题兜底（降级写入 insufficiency_class）"
    elif f.get("card_allowed"):
        rung, reason = "SOLID_COLOR_CARD", "无可用素材 → 纯色卡占位（不伪造画面）"
    else:
        rung, reason = "BLOCKED_FOR_HUMAN", "无可用素材且策略不允许兜底 → 阻断并转人工"
    return {"rung": rung, "index": SUPPLY_LADDER.index(rung), "reason": reason,
            "ladder": list(SUPPLY_LADDER),
            "invariants": {"unverified_external_used": False, "license_bypass": False,
                           "silent_fallback": False},
            "requires_human": rung in ("THEME_FALLBACK", "SOLID_COLOR_CARD", "BLOCKED_FOR_HUMAN")
            or bool(f.get("requires_human"))}


# ---------------- 六、对外汇总 ----------------
def taxonomy_table() -> list[dict]:
    """全量分类表（供报告/证据脚本引用，避免报告里手抄）。"""
    return [{"code": code, "class": c, "retryable": r, "action": a}
            for code, (c, r, a) in sorted(TAXONOMY.items())]


def summarize(outcomes: list[dict]) -> dict:
    """把一批候选结局汇总成计数（`outcomes` 为 {error_code, status} 列表）。"""
    verified = [o for o in outcomes if o.get("status") == "VERIFIED"]
    rejected = [o for o in outcomes if o.get("status") != "VERIFIED"]
    counts: dict[str, int] = {}
    for o in rejected:
        counts[o.get("error_code") or "UNKNOWN"] = counts.get(o.get("error_code") or "UNKNOWN", 0) + 1
    return {"total": len(outcomes), "verified": len(verified), "rejected": len(rejected),
            "rejected_by_code": counts,
            "rejected_by_class": {k: sum(1 for o in rejected
                                         if classify_failure(o.get("error_code"))["class"] == k)
                                  for k in FAILURE_CLASSES},
            "unverified_promoted": 0,
            "license_blocks": sum(1 for o in rejected
                                  if str(o.get("error_code") or "").startswith("ASSET_LICENSE"))}
