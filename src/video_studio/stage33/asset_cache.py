"""asset_cache（Stage 7B）：persistent material image cache + download throttle + dedup。

Stage 7A 暴露的工程问题：Wikimedia acquisition 429（10/66 候选）。
本模块只解决"缓存/节流/去重/可观测"，**不接触 V1 ranking、不接触 sanitizer 白名单、
不接触 Vision 评判逻辑**。

设计（预注册，发布于实现前）：
- 共享持久缓存目录：output/stage33/cv2/phase7b_controlled/asset_cache/
- 同一素材（material_id）只下载一次；重复请求命中缓存（cache_hit 可观测）
- 下载节流：全局互斥锁 + 每素材之间 min_interval 秒；429 退避 + jitter
- 缓存 metadata：source_url / local_path / content_hash / download_timestamp /
  http_status / retry_count / cache_hit / cache_age
- 下载失败不删候选；返回 failure 由 caller 走 Vision fallback（→ V1 fallback）
- 永不修改原始素材包、永不修改 V1。

不变式：
- CACH-01 cache miss → 下载 → 写入 metadata（同素材串行）
- CACH-02 下载失败不产生任何 ranking 影响（由调用方 fallback）
- CACH-03 缓存命中不重新下载（dedup 生效）
- CACH-04 所有下载记录 http_status / retry_count / timestamp
"""
from __future__ import annotations

import hashlib
import json
import random
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

UA = {"User-Agent": "video-studio-7b-controlled/0.1"}

# 全局节流（进程内互斥 + 间隔）
_throttle_lock = threading.Lock()
_last_download_ts = 0.0
MIN_INTERVAL_S = 2.0          # 每素材最小间隔（避免突发）
BACKOFF_BASE_S = 5.0          # 429 基础退避
MAX_ATTEMPTS = 6
VALID_MIN_BYTES = 500


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_name(material_id: str) -> str:
    return re.sub(r"[^\w.-]", "_", f"{material_id}.img")


def _meta_path(cache_dir: Path, material_id: str) -> Path:
    return cache_dir / "meta" / f"{_safe_name(material_id)}.json"


def load_meta(cache_dir: Path, material_id: str) -> dict | None:
    p = _meta_path(cache_dir, material_id)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return None
    return None


def save_meta(cache_dir: Path, material_id: str, meta: dict) -> None:
    p = _meta_path(cache_dir, material_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def _file_path(cache_dir: Path, material_id: str, ext_hint: str) -> Path:
    ext = {"image": "jpg", "video": "mp4", "other": "bin"}.get(ext_hint, "jpg")
    return cache_dir / "files" / f"{_safe_name(material_id)}.{ext}"


def _throttle(min_interval: float) -> None:
    """全局下载节流：两次下载之间至少 min_interval 秒。"""
    global _last_download_ts
    with _throttle_lock:
        wait = _last_download_ts + min_interval - time.time()
        if wait > 0:
            time.sleep(wait)
        _last_download_ts = time.time()


def acquire_asset(cache_dir: Path, material_id: str, source_url: str,
                  preview_path: Path | None = None, ext_hint: str = "image",
                  forbid_download: bool = False) -> dict:
    """persistent cache 获取素材。

    Returns record: {status, local_path, source, content_hash, cache_hit, cache_age,
                     download_timestamp, http_status, retry_count, failure_reason}
    """
    cache_dir = Path(cache_dir)
    files_dir = cache_dir / "files"
    files_dir.mkdir(parents=True, exist_ok=True)

    # 1) preview 优先（本地已存在，勿下载）
    if preview_path and Path(preview_path).exists():
        p = Path(preview_path)
        return {"status": "OK", "local_path": str(p), "source": "preview",
                "content_hash": _sha256(p), "cache_hit": False, "cache_age": None,
                "download_timestamp": None, "http_status": 200, "retry_count": 0,
                "failure_reason": None, "url_kept": bool(source_url)}

    # 2) 持久缓存命中
    dest = _file_path(cache_dir, material_id, ext_hint)
    meta = load_meta(cache_dir, material_id)
    if dest.exists() and meta and meta.get("status") == "OK":
        age_s = None
        if meta.get("download_timestamp"):
            try:
                ts = datetime.fromisoformat(meta["download_timestamp"].replace("Z", "+00:00"))
                age_s = int((datetime.now(timezone.utc) - ts).total_seconds())
            except Exception:  # noqa: BLE001
                age_s = None
        return {"status": "OK", "local_path": str(dest), "source": "cache",
                "content_hash": _sha256(dest), "cache_hit": True, "cache_age": age_s,
                "download_timestamp": meta.get("download_timestamp"),
                "http_status": meta.get("http_status"), "retry_count": meta.get("retry_count", 0),
                "failure_reason": None, "url_kept": bool(source_url)}

    # 3) 无 URL → 失败（不删候选）
    if not source_url:
        return {"status": "FAIL", "failure_reason": "no_download_url", "cache_hit": False,
                "local_path": None, "source": None, "content_hash": None, "cache_age": None,
                "download_timestamp": None, "http_status": None, "retry_count": 0,
                "url_kept": False}
    if forbid_download:
        return {"status": "FAIL", "failure_reason": "download_forbidden", "cache_hit": False,
                "local_path": None, "source": None, "content_hash": None, "cache_age": None,
                "download_timestamp": None, "http_status": None, "retry_count": 0,
                "url_kept": bool(source_url)}

    # 4) 下载（节流 + 429 退避 + jitter；全程串行同素材避免重复）
    # 注意：锁只存在于 _throttle() 内部保护 _last_download_ts 的读取/更新；
    # 下载循环本身不持锁（避免嵌套锁死锁）。
    last = None
    http_status = None
    retry_count = 0
    for attempt in range(MAX_ATTEMPTS):
        _throttle(MIN_INTERVAL_S)
        try:
            r = requests.get(source_url, headers=UA, timeout=90)
            http_status = r.status_code
            retry_count = attempt + 1
            if r.status_code == 200 and r.content and len(r.content) > VALID_MIN_BYTES:
                dest.write_bytes(r.content)
                h = _sha256(dest)
                save_meta(cache_dir, material_id, {
                    "material_id": material_id, "source_url": source_url,
                    "local_path": str(dest), "content_hash": h,
                    "download_timestamp": _now_iso(), "http_status": 200,
                    "retry_count": retry_count, "status": "OK",
                    "bytes": len(r.content)})
                return {"status": "OK", "local_path": str(dest), "source": "download",
                        "content_hash": h, "cache_hit": False, "cache_age": 0,
                        "download_timestamp": _now_iso(), "http_status": 200,
                        "retry_count": retry_count, "failure_reason": None,
                        "url_kept": True}
            last = f"HTTP {r.status_code} len={len(r.content or b'')}"
        except Exception as e:  # noqa: BLE001
            last = f"{type(e).__name__}: {e}"
        wait = (BACKOFF_BASE_S * (attempt + 1) if "429" in str(last)
                else 2.0 * (attempt + 1)) + random.uniform(0, 1.5)
        time.sleep(wait)
    save_meta(cache_dir, material_id, {
        "material_id": material_id, "source_url": source_url, "local_path": str(dest),
        "content_hash": None, "download_timestamp": _now_iso(),
        "http_status": http_status, "retry_count": retry_count, "status": "FAIL",
        "failure_reason": last})
    return {"status": "FAIL", "failure_reason": f"download_exhausted: {last}",
            "cache_hit": False, "local_path": str(dest) if dest.exists() else None,
            "source": None, "content_hash": None, "cache_age": None,
            "download_timestamp": _now_iso(), "http_status": http_status,
            "retry_count": retry_count, "url_kept": True}


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()
