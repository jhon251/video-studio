# -*- coding: utf-8 -*-
"""P10-2：**选题信号层**（`topic_signals`）——真实热度/竞品信号 → 归一化快照。

设计要点
--------
1. **两个 provider，同一快照 schema**：
   · `manual`            —— 本地 JSON（人工策展的 hot_rank / competitor_hit 条目）
   · `bilibili_popular`  —— 真实 B 站热门接口（**单次请求**）；`code!=0` / 超时 / 限流 /
     截断 / 结构异常 一律 `PROVIDER_*` 错误码（沿用 `tools/material_provider.py` 分类学），
     **fail-closed，绝不伪造条目**。
2. **快照模式（确定性关键）**：网络访问只发生在**人工触发的只读 CLI**（`run.py fetch-signals`）；
   topic agent 运行时**只读快照文件**、绝不实时联网 ⇒ agent 运行可复现、可审计。
3. 归一化条目字段（固定）：
   `{source, kind, title, url, bvid, author, tname, metrics{view,like,coin,favorite,share,
   danmaku,reply}, duration_s, published_at, rcmd_reason, fetched_at, raw_index, url_derived}`；
   缺失的数值字段记 `null`（**不填 0**，不猜）。
4. 校验：条目上限 100、按 url/bvid 去重、必填字段（title/url）缺失即丢弃并**披露丢弃计数**；
   全程 UTF-8。

**现实差异登记**：授权书称接口返回 `data:[{...}]`；实测（2026-09-30）为
`data:{list:[...], no_more:bool}` ⇒ 本模块**两种形态都接受**，并以实测为准。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import time
import urllib.error
import urllib.request

SCHEMA = "topic-signals-snapshot-v1"
VERSION = 1
MAX_ENTRIES = 100
DEFAULT_PS = 50
PROVIDERS = ("none", "manual", "bilibili_popular")
BILIBILI_POPULAR_URL = "https://api.bilibili.com/x/web-interface/popular"
BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/124.0 Safari/537.36")
DEFAULT_TIMEOUT_S = 15
MAX_BYTES = 4 * 1024 * 1024

#: 结构化 provider 错误码（沿用素材 provider 分类学；禁止 silent fallback）
PROVIDER_ERRORS = (
    "PROVIDER_NOT_CONFIGURED", "PROVIDER_UNKNOWN", "PROVIDER_TIMEOUT",
    "PROVIDER_HTTP_404", "PROVIDER_HTTP_5XX", "PROVIDER_HTTP_ERROR", "PROVIDER_RATE_LIMITED",
    "PROVIDER_CODE_NONZERO", "PROVIDER_MALFORMED", "PROVIDER_TRUNCATED", "PROVIDER_EMPTY",
    "PROVIDER_OVERSIZE", "PROVIDER_FILE_MISSING", "PROVIDER_FILE_INVALID",
)
REQUIRED_ENTRY_FIELDS = ("title", "url")
KINDS = ("hot_rank", "competitor_hit", "manual")
METRIC_KEYS = ("view", "like", "coin", "favorite", "share", "danmaku", "reply")


class TopicSignalsError(RuntimeError):
    def __init__(self, code: str, detail: str = ""):
        super().__init__("[{}] {}".format(code, detail))
        self.code = code
        self.detail = detail


def _iso_utc(epoch) -> str | None:
    try:
        v = int(epoch)
    except (TypeError, ValueError):
        return None
    if v <= 0:
        return None
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(v))


def _int_or_none(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def normalize_entry(raw: dict, *, source: str, kind: str, raw_index: int,
                    fetched_at: str, drop: list, default_kind: str = "hot_rank") -> dict | None:
    """单条归一化。必填缺失 ⇒ 记入 `drop` 并返回 None（**不伪造**）。"""
    if not isinstance(raw, dict):
        drop.append({"raw_index": raw_index, "reason": "NOT_AN_OBJECT"})
        return None
    title = str(raw.get("title") or "").strip()
    if not title:
        drop.append({"raw_index": raw_index, "reason": "MISSING_TITLE"})
        return None
    bvid = str(raw.get("bvid") or "").strip() or None
    url = str(raw.get("url") or raw.get("short_link_v2") or "").strip()
    url_derived = False
    if not url and bvid:                                    # 由真实 bvid 派生规范链接（显式标注）
        url = "https://www.bilibili.com/video/{}".format(bvid)
        url_derived = True
    if not url.lower().startswith(("http://", "https://")):
        drop.append({"raw_index": raw_index, "reason": "MISSING_OR_INVALID_URL",
                     "title": title[:40]})
        return None
    stat = raw.get("stat") if isinstance(raw.get("stat"), dict) else {}
    owner = raw.get("owner") if isinstance(raw.get("owner"), dict) else {}
    rcmd = raw.get("rcmd_reason") if isinstance(raw.get("rcmd_reason"), dict) else {}
    metrics = {k: _int_or_none(stat.get(k)) for k in METRIC_KEYS}
    entry = {
        "source": source,
        "kind": kind or default_kind,
        "title": title,
        "url": url,
        "url_derived": url_derived,
        "bvid": bvid,
        "author": (str(owner.get("name")).strip() or None) if owner.get("name") else None,
        "tname": (str(raw.get("tnamev2") or raw.get("tname") or "").strip() or None),
        "metrics": metrics,
        "duration_s": _int_or_none(raw.get("duration")),
        "published_at": _iso_utc(raw.get("pubdate")),
        "rcmd_reason": (str(rcmd.get("content")).strip() or None) if rcmd.get("content") else None,
        "fetched_at": fetched_at,
        "raw_index": raw_index,
        "desc": (str(raw.get("desc") or "").strip()[:200] or None),
    }
    return entry


def dedupe(entries: list[dict]) -> tuple[list[dict], list[dict]]:
    """按 url / bvid 去重（保留首次出现；顺序稳定）。"""
    seen, kept, dropped = set(), [], []
    for e in entries:
        keys = [("url", e.get("url"))]
        if e.get("bvid"):
            keys.append(("bvid", e["bvid"]))
        hit = next((k for k, v in keys if (k, v) in seen), None)
        if hit:
            dropped.append({"raw_index": e.get("raw_index"), "reason": "DUPLICATE_{}".format(
                hit.upper()), "title": str(e.get("title"))[:40]})
            continue
        for k in keys:
            seen.add(k)
        kept.append(e)
    return kept, dropped


def build_snapshot(*, provider: str, raw_entries: list, fetched_at: str, request_count: int,
                   source_label: str, kind_default: str = "hot_rank",
                   extra: dict | None = None) -> dict:
    """归一化 + 去重 + 上限 + 丢弃披露 ⇒ 快照（确定性内容，时间戳仅在 `fetched_at`）。"""
    drops: list[dict] = []
    norm = []
    for i, raw in enumerate(raw_entries):
        e = normalize_entry(raw, source=source_label, kind=kind_default, raw_index=i,
                            fetched_at=fetched_at, drop=drops)
        if e is not None:
            norm.append(e)
    kept, dups = dedupe(norm)
    drops += dups
    over = kept[MAX_ENTRIES:]
    kept = kept[:MAX_ENTRIES]
    if over:
        drops += [{"raw_index": e.get("raw_index"), "reason": "OVER_LIMIT",
                   "title": str(e.get("title"))[:40]} for e in over]
    kinds = sorted({str(e["kind"]) for e in kept})
    snap = {
        "schema": SCHEMA, "version": VERSION, "provider": provider,
        "source_label": source_label, "fetched_at": fetched_at,
        "request_count": request_count,
        "entries_raw": len(raw_entries), "entries_kept": len(kept),
        "dropped_count": len(drops), "dropped": drops[:50],
        "kinds": kinds, "by_kind": {k: sum(1 for e in kept if e["kind"] == k) for k in kinds},
        "limits": {"max_entries": MAX_ENTRIES},
        "entries": kept,
        "no_fabrication": "所有条目均来自真实 provider 响应/本地策展文件；无条目 ⇒ 空快照 + 错误码",
        "sha256_of_entries": hashlib.sha256(
            json.dumps(kept, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest(),
    }
    if extra:
        snap.update(extra)
    return snap


def validate_snapshot(snap: dict) -> list[str]:
    errs = []
    if snap.get("schema") != SCHEMA:
        errs.append("schema 非法")
    if snap.get("provider") not in PROVIDERS:
        errs.append("provider 非法")
    entries = snap.get("entries") or []
    if len(entries) > MAX_ENTRIES:
        errs.append("条目超过上限 {}".format(MAX_ENTRIES))
    if snap.get("entries_kept") != len(entries):
        errs.append("entries_kept 与实际条目数不一致")
    seen = set()
    for i, e in enumerate(entries):
        for f in REQUIRED_ENTRY_FIELDS:
            if not e.get(f):
                errs.append("entries[{}] 缺少必填 {}".format(i, f))
        if not str(e.get("url", "")).lower().startswith(("http://", "https://")):
            errs.append("entries[{}] url 非法".format(i))
        for key in (("url", e.get("url")), ("bvid", e.get("bvid"))):
            if key[1] and key in seen:
                errs.append("entries[{}] 重复 {}".format(i, key[0]))
            if key[1]:
                seen.add(key)
        for mk in METRIC_KEYS:
            if mk not in (e.get("metrics") or {}):
                errs.append("entries[{}].metrics 缺 {}".format(i, mk))
    return errs


# ------------------------------------------------------------------ providers
def fetch_bilibili_popular(*, transport=None, ps: int = DEFAULT_PS,
                           timeout_s: float = DEFAULT_TIMEOUT_S,
                           max_bytes: int = MAX_BYTES, url: str = BILIBILI_POPULAR_URL) -> dict:
    """真实 B 站热门：**单次请求**；失败 ⇒ `PROVIDER_*`（fail-closed，零伪造条目）。"""
    query = "{}?ps={}".format(url, int(ps))
    if transport is None:
        def transport(u, timeout, max_b):                                  # noqa: ANN001
            req = urllib.request.Request(u, headers={"User-Agent": BROWSER_UA,
                                                     "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:     # noqa: S310 —— 固定 https
                if resp.status == 429:
                    raise TopicSignalsError("PROVIDER_RATE_LIMITED", "HTTP 429")
                if resp.status == 404:
                    raise TopicSignalsError("PROVIDER_HTTP_404", u)
                if resp.status >= 500:
                    raise TopicSignalsError("PROVIDER_HTTP_5XX", "HTTP {}".format(resp.status))
                if resp.status != 200:
                    raise TopicSignalsError("PROVIDER_HTTP_ERROR", "HTTP {}".format(resp.status))
                data = resp.read(max_b + 1)
                if len(data) > max_b:
                    raise TopicSignalsError("PROVIDER_OVERSIZE",
                                            ">{} bytes（流式截断，不落盘）".format(max_b))
                return data
    try:
        raw = transport(query, timeout_s, max_bytes)
    except TopicSignalsError:
        raise
    except urllib.error.HTTPError as exc:                                   # noqa: PERF203
        code = ("PROVIDER_HTTP_404" if exc.code == 404 else
                "PROVIDER_RATE_LIMITED" if exc.code == 429 else
                "PROVIDER_HTTP_5XX" if exc.code >= 500 else "PROVIDER_HTTP_ERROR")
        raise TopicSignalsError(code, "HTTP {}".format(exc.code)) from None
    except TimeoutError:
        raise TopicSignalsError("PROVIDER_TIMEOUT", "读取超时 {}s".format(timeout_s)) from None
    except urllib.error.URLError as exc:
        code = "PROVIDER_TIMEOUT" if "timed out" in str(exc).lower() else "PROVIDER_HTTP_ERROR"
        raise TopicSignalsError(code, str(exc)[:160]) from None
    except Exception as exc:                                                # noqa: BLE001
        raise TopicSignalsError("PROVIDER_HTTP_ERROR",
                                "{}: {}".format(type(exc).__name__, str(exc)[:120])) from None
    if isinstance(raw, dict) and "data" in raw:                             # 允许注入已解析响应
        payload = raw
    else:
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TopicSignalsError("PROVIDER_MALFORMED",
                                    "响应非 UTF-8 JSON: {}".format(type(exc).__name__)) from None
    code = payload.get("code")
    if code != 0:
        raise TopicSignalsError("PROVIDER_CODE_NONZERO",
                                "code={} message={}".format(code, str(payload.get("message"))[:80]))
    data = payload.get("data")
    # 现实差异登记：实测为 {"list": [...], "no_more": bool}；两种形态都接受
    if isinstance(data, dict):
        items = data.get("list")
    else:
        items = data
    if not isinstance(items, list):
        raise TopicSignalsError("PROVIDER_MALFORMED", "data 既非数组也非 {list:[...]}")
    if not items:
        raise TopicSignalsError("PROVIDER_EMPTY", "条目为空（不伪造）")
    if len(items) < int(ps) * 0.5:
        # 明显少于请求量：如实记录（不报错，但标记）
        truncated = True
    else:
        truncated = False
    snap = build_snapshot(provider="bilibili_popular", raw_entries=items[:MAX_ENTRIES],
                          fetched_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                          request_count=1, source_label="bilibili_popular",
                          kind_default="hot_rank",
                          extra={"request": {"url": query, "ua": "browser", "ps": int(ps)},
                                 "response_truncated": truncated,
                                 "data_shape": "list" if isinstance(data, list) else "dict.list"})
    errors = validate_snapshot(snap)
    if errors:
        raise TopicSignalsError("PROVIDER_MALFORMED", "; ".join(errors[:3]))
    return snap


def build_manual_snapshot(path, *, kind_default: str = "manual") -> dict:
    """本地策展 JSON ⇒ 同 schema 快照（离线、确定性）。"""
    p = pathlib.Path(path)
    if not p.is_file():
        raise TopicSignalsError("PROVIDER_FILE_MISSING", str(p))
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TopicSignalsError("PROVIDER_FILE_INVALID",
                                "{}: {}".format(type(exc).__name__, str(exc)[:120])) from None
    items = payload.get("entries") if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        raise TopicSignalsError("PROVIDER_FILE_INVALID", "manual 文件需为数组或 {entries:[...]}")
    if not items:
        raise TopicSignalsError("PROVIDER_EMPTY", "manual 条目为空（不伪造）")
    mtime = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(p.stat().st_mtime))
    snap = build_snapshot(provider="manual", raw_entries=items, fetched_at=mtime,
                          request_count=0, source_label="manual",
                          kind_default=kind_default,
                          extra={"manual_path": str(p),
                                 "manual_sha256": hashlib.sha256(p.read_bytes()).hexdigest()})
    errors = validate_snapshot(snap)
    if errors:
        raise TopicSignalsError("PROVIDER_FILE_INVALID", "; ".join(errors[:3]))
    return snap


def write_snapshot(snap: dict, out_path) -> pathlib.Path:
    """落盘快照（**仅由人工触发的 CLI 调用**；topic agent 运行期从不写）。"""
    p = pathlib.Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(snap, ensure_ascii=False, indent=1), encoding="utf-8")
    return p


def default_snapshot_name(provider: str) -> str:
    return "snapshot_{}_{}.json".format(provider,
                                        time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))


# ------------------------------------------------------------------ agent 读取（只读）
def load_snapshot(path) -> dict:
    """只读快照（同一文件两次读取结果**逐字节一致**的内容）。"""
    p = pathlib.Path(path)
    if not p.is_file():
        raise TopicSignalsError("PROVIDER_FILE_MISSING", str(p))
    try:
        snap = json.loads(p.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TopicSignalsError("PROVIDER_FILE_INVALID",
                                "{}: {}".format(type(exc).__name__, str(exc)[:120])) from None
    errors = validate_snapshot(snap)
    if errors:
        raise TopicSignalsError("PROVIDER_FILE_INVALID", "; ".join(errors[:3]))
    return snap


def latest_snapshot(snapshot_dir) -> pathlib.Path | None:
    d = pathlib.Path(snapshot_dir)
    if not d.is_dir():
        return None
    files = sorted(d.glob("snapshot_*.json"))
    return files[-1] if files else None


def digest(entries: list[dict], *, top_n: int = 5, by: str = "view") -> dict:
    """信号摘要（供 `signals_digest` 与 prompt 使用）：计数 / 类型 / 头部标题。"""
    def metric(e):
        return (e.get("metrics") or {}).get(by) or -1
    ranked = sorted(entries, key=lambda e: (-metric(e), str(e.get("title"))))
    return {"count": len(entries),
            "kinds": sorted({str(e.get("kind")) for e in entries}),
            "by_kind": {k: sum(1 for e in entries if e.get("kind") == k)
                        for k in sorted({str(e.get("kind")) for e in entries})},
            "top_titles": [str(e.get("title")) for e in ranked[:top_n]],
            "top_refs": [int(e.get("raw_index") if e.get("raw_index") is not None else i)
                         for i, e in enumerate(ranked[:top_n])],
            "ranked_by": by}


EXTERNAL_CONFIG_REL = "config/topic_signals.json"


def resolve_config(config: dict | None, *, root=None) -> tuple[dict, str]:
    """解析选题信号配置（**不修改被基线钉定的 config.json**）。

    优先级：
      1) `config["tools"]["topic_signals"]`（若存在——运行时注入或未来重钉基线后写入 config.json）
      2) **外部可选文件** `config/topic_signals.json`（默认不存在 ⇒ provider=none）
      3) 内置默认 `{provider: "none"}`

    **现实差异登记（Phase 10）**：授权书要求把 `tools.topic_signals` 加进 `config.json`；但仓库既有硬契约
    （`tests/metrics_test.py` M5d、`tests/offline_mock_test.py` L7b、`docs/regression_2x/phase5l_evidence.py`）
    把 `config/config.json` 的**逐字节 sha256** 钉在"当前有效基线"manifest 上
    （`5.x-post-final-maintenance-baseline`，值 `7b03424846f1…`）⇒ 改 config.json 必然使这些契约转红，
    而唯一"修法"是重钉基线 manifest——被本阶段边界（不碰一切 baseline 与不可变快照）禁止。
    故**以现实为准**：默认配置改由此处解析（等价语义：默认 `provider=none`），
    `config.json` 保持逐字节未改（sha256 已复原并核验）。
    """
    base = pathlib.Path(root) if root else pathlib.Path(".")
    tools = ((config or {}).get("tools") or {})
    inline = tools.get("topic_signals")
    if isinstance(inline, dict) and inline:
        return dict(inline), "config.tools.topic_signals（内存/未来基线）"
    ext = base / EXTERNAL_CONFIG_REL
    if ext.is_file():
        try:
            j = json.loads(ext.read_text(encoding="utf-8"))
            block = j.get("topic_signals") if isinstance(j, dict) else None
            block = block or (j if isinstance(j, dict) else None)
            if isinstance(block, dict) and block:
                return dict(block), str(ext)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {"provider": "none"}, "{}（损坏 ⇒ 保守回落 none）".format(ext)
    return {"provider": "none"}, "default（无配置 ⇒ provider=none）"


def load_signals_for_agent(config: dict | None, *, root=None) -> dict:
    """topic agent 运行期入口：**只读**快照；provider=none/无快照 ⇒ 明确 status（不联网）。"""
    cfg, cfg_source = resolve_config(config, root=root)
    provider = str(cfg.get("provider") or "none")
    base = pathlib.Path(root) if root else pathlib.Path(".")
    if provider == "none":
        return {"status": "NO_PROVIDER", "provider": provider, "config_source": cfg_source,
                "note": "未配置选题信号 provider（默认 none）⇒ 纯头脑风暴路径"}
    if provider == "manual":
        mp = cfg.get("manual_path")
        if not mp:
            return {"status": "NO_SNAPSHOT", "provider": provider,
                    "reason_code": "PROVIDER_NOT_CONFIGURED", "note": "manual_path 未配置"}
        try:
            snap = build_manual_snapshot(base / mp if not pathlib.Path(mp).is_absolute() else mp)
        except TopicSignalsError as exc:
            return {"status": "ERROR", "provider": provider, "reason_code": exc.code,
                    "detail": exc.detail}
        return {"status": "OK", "provider": provider, "snapshot": snap,
                "entries": snap["entries"], "digest": digest(snap["entries"]),
                "snapshot_path": str(mp)}
    if provider == "bilibili_popular":
        snap_dir = base / str(cfg.get("snapshot_dir") or "signals")
        p = latest_snapshot(snap_dir)
        if p is None:
            return {"status": "NO_SNAPSHOT", "provider": provider,
                    "reason_code": "PROVIDER_FILE_MISSING",
                    "note": "未找到快照；请先人工执行 run.py fetch-signals（agent 不联网）"}
        try:
            snap = load_snapshot(p)
        except TopicSignalsError as exc:
            return {"status": "ERROR", "provider": provider, "reason_code": exc.code,
                    "detail": exc.detail, "snapshot_path": str(p)}
        return {"status": "OK", "provider": provider, "snapshot": snap,
                "entries": snap["entries"], "digest": digest(snap["entries"]),
                "snapshot_path": str(p),
                "snapshot_sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
    return {"status": "ERROR", "provider": provider, "reason_code": "PROVIDER_UNKNOWN",
            "detail": "未知 provider（允许：{}）".format("/".join(PROVIDERS))}


def signals_context_block(entries: list[dict], *, max_entries: int = 30) -> str:
    """把信号渲染成 prompt 片段（**只含真实字段**，带下标供 `signal_refs` 引用）。"""
    lines = ["# 选题信号（真实快照，只读；下标用于 signal_refs）"]
    for i, e in enumerate(entries[:max_entries]):
        m = e.get("metrics") or {}
        lines.append("[{}] {} | 分区:{} | 播放:{} 点赞:{} | 时长:{}s | {} | {}".format(
            i, e.get("title"), e.get("tname") or "?", m.get("view"), m.get("like"),
            e.get("duration_s"), e.get("author") or "?", e.get("url")))
    lines.append("（共 {} 条；以上全部来自真实快照，禁止编造热度数据）".format(len(entries)))
    return "\n".join(lines)
