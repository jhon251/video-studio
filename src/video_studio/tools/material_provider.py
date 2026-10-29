"""外部素材 Provider 接入层（3.x Phase 2-D：**接入前的边界设计与实现**）。

本模块定义统一接口与**强校验边界**。本阶段**不接任何真实外部服务**：默认 provider=`none`，
现有 local_ingest 行为完全不变；真实服务接入前，所有边界（下载/校验/许可证/安全/资源限制）先落地并可测。

## 一、接口（统一搜索/获取/元数据）

  MaterialProvider.search(query, ctx) -> list[ProviderCandidate]
  MaterialProvider.fetch(candidates, ctx) -> list[ProviderCandidate]     # 下载 + 校验（含并发上限）
  MaterialProvider.capabilities() -> dict                                # provider 自述与限制

实现：
  · LocalIngestProvider   —— 现有 local_ingest 的**兼容实现**（就地校验，不复制、不下载）
  · LocalCatalogProvider  —— 本地目录 + catalogue.json（验收用的 fake/local provider，走**同一条**下载+校验管线）
  · HttpCatalogProvider   —— 真实外部形态；transport 可注入；默认仅允许 HTTPS、禁跳转、限时限量

## 二、标准化候选字段（需求 2）

  provider / source_id / source_url / name / ext / license / attribution / usage_restrictions /
  bytes / sha256 / downloaded_path / download_status / probe_result / decodable / status /
  error_code / error_detail / needs_hitl / license_cleared

外部候选最终会被转换成**现有素材候选结构**（`path` 相对项目 media/，`name`/`ext`/`size`/`sha256`/`license`），
因此**不可能绕过** Phase 2-C 的分类学：不可用 → `ASSET_UNUSABLE`、与镜头约束冲突 → `ASSET_CONFLICT`、
被占用且禁止复用 → `ASSET_EXHAUSTED`、分数低于阈值 → `LOW_MATCH`。

## 三、下载与校验边界（需求 3）

下载 → 逐项校验，任一失败即 REJECTED 且带**明确错误码**，绝不进入 ffmpeg：
  1. `ASSET_DANGEROUS_FILENAME`   文件名含路径分隔符/`..`/绝对路径/控制字符/保留设备名/非法字符
  2. `ASSET_EXTENSION_NOT_ALLOWED` 扩展名不在白名单（含 .exe/.sh/.js 等可执行类一律拒绝）
  3. `ASSET_OVERSIZE`             超过 `max_bytes`（流式累计即中断，不写满磁盘）
  4. `ASSET_EMPTY_FILE`           0 字节（含 HTTP 空响应）
  5. `ASSET_TYPE_MISMATCH`        **magic bytes** 与实际媒体类型不符（非媒体文件伪装）
  6. `ASSET_PROBE_FAILED`         ffprobe 无法给出有效图像/视频流与尺寸
  7. `ASSET_FFMPEG_DECODE_FAILED` ffmpeg 解码 rc≠0
  8. `ASSET_DECODE_FAILED`        PIL 装载失败
  9. `ASSET_TOO_SMALL`            尺寸低于 `min_width/min_height`
 10. `PROVIDER_TIMEOUT / PROVIDER_HTTP_404 / PROVIDER_HTTP_5XX / PROVIDER_HTTP_ERROR /
     PROVIDER_EMPTY_RESPONSE / PROVIDER_DOWNLOAD_FAILED`  传输层失败（超时/HTTP 错误/空响应/重试耗尽）
 11. `ASSET_LICENSE_MISSING / ASSET_LICENSE_UNCLEAR`      许可证缺失或不明确
 12. `PROVIDER_CACHE_LIMIT`      缓存超限（不做静默淘汰）

**不允许仅凭 URL 或扩展名认定可用**：扩展名只用于白名单初筛，最终判定必须来自 magic bytes + ffprobe + 解码。

## 四、许可证与归属（需求 4）

`license` 缺失/为空/`unknown`/`unchecked` → `license_cleared=False`、`needs_hitl=True`，
该候选**不得进入正常素材路径**（在 Phase 2-C 分类里体现为 `ASSET_UNUSABLE` + `reason=ASSET_LICENSE_*`，
场景 `needs_hitl=True`）。**不猜测、不生成**许可证；`attribution`/`usage_restrictions` 原样记录，不补全。

## 五、安全与资源（需求 5）

下载超时、大小上限、重试次数、并发上限、内容寻址缓存（同 sha256 不重复下载）、缓存上限；
文件名与落盘路径由**我们自己**按 sha256 生成（不接受远端路径）；只读方式解析媒体，**从不执行**下载内容；
外部 provider 失败时：仍有 local_ingest 可用 → 降级继续（候选标注 provider 与失败原因）；
完全无可用素材 → 交给 Phase 2-C 的 `ASSEMBLY_BLOCKED` → render 阻断（明确 BLOCKED）。
"""

from __future__ import annotations

import hashlib
import http.client
import json
import os
import re
import shutil
import socket
import ssl
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Iterable

# Phase 4-D：失败分类/重试计划/供给缓存/降级阶梯的**单一来源**（纯函数，无副作用）
from ..core.supply import retry_decision as _retry_decision

# ---------------- 错误码 ----------------
PROVIDER_ERRORS = ("PROVIDER_NOT_CONFIGURED", "PROVIDER_UNKNOWN", "PROVIDER_TIMEOUT",
                   "PROVIDER_HTTP_404", "PROVIDER_HTTP_5XX", "PROVIDER_HTTP_ERROR",
                   "PROVIDER_EMPTY_RESPONSE", "PROVIDER_DOWNLOAD_FAILED", "PROVIDER_CACHE_LIMIT",
                   "PROVIDER_CATALOG_INVALID",
                   # Phase 2-E：真实网络才有的失败面
                   "PROVIDER_AUTH_FAILED", "PROVIDER_RATE_LIMITED", "PROVIDER_SEARCH_FAILED",
                   "PROVIDER_REQUEST_BUDGET")
ASSET_ERRORS = ("ASSET_DANGEROUS_FILENAME", "ASSET_EXTENSION_NOT_ALLOWED", "ASSET_OVERSIZE",
                "ASSET_EMPTY_FILE", "ASSET_TYPE_MISMATCH", "ASSET_TRUNCATED",
                "ASSET_PROBE_FAILED", "ASSET_FFMPEG_DECODE_FAILED", "ASSET_DECODE_FAILED",
                "ASSET_TOO_SMALL", "ASSET_LICENSE_MISSING", "ASSET_LICENSE_UNCLEAR",
                "ASSET_LICENSE_RESTRICTED")

DEFAULT_POLICY = {
    "provider": "none",
    "max_bytes": 8 * 1024 * 1024,           # 单文件上限 8 MiB
    "timeout_s": 20,                         # 单次下载超时
    "max_retries": 2,                        # 传输层重试次数（总尝试 = 1 + max_retries）
    "max_concurrent_downloads": 2,
    "max_cache_bytes": 256 * 1024 * 1024,    # 缓存上限（超出即拒绝新下载，不静默淘汰）
    "allowed_ext": [".jpg", ".jpeg", ".png", ".webp"],
    "min_width": 320,
    "min_height": 180,
    "license_required": True,
    "require_https": True,
    "catalog": None,                         # local_catalog 的目录或 http 端点
    "cache_dir": "external",                 # 相对项目 media/
    # ---- Phase 4-D：供给韧性（纯新增键，默认不改变任何既有行为）----
    "supply_cache": False,                   # 搜索层元数据缓存，**默认关闭**
    "supply_cache_ttl_s": 900.0,             # 缓存有效期（秒；0 表示不过期）
    "retry_after_max_s": 30.0,               # 采纳 Retry-After 的上限（不无限等待）
}
_MAGIC = ((".jpg", b"\xff\xd8\xff"), (".jpeg", b"\xff\xd8\xff"), (".png", b"\x89PNG\r\n\x1a\n"))
_WEBP_PREFIX = b"RIFF"
_WEBP_TAG = b"WEBP"
_BAD_EXT = (".exe", ".dll", ".com", ".scr", ".msi", ".bat", ".cmd", ".ps1", ".sh", ".bash",
            ".py", ".js", ".vbs", ".jar", ".lnk", ".php", ".pl", ".rb", ".html", ".htm", ".svg")
_RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)),
             *(f"lpt{i}" for i in range(1, 10))}
# 危险字符黑名单（而不是白名单）：真实素材名常含逗号/括号/撇号等，
# 一律拒绝会误伤真实来源；真正危险的是路径分隔符、盘符、通配符与控制字符。
_NAME_BAD_CHARS = set('<>:"/\\|?*')
_NAME_MAX = 180


def safe_filename(name: str) -> tuple[bool, str, str | None]:
    """危险文件名/路径穿越检查。返回 (ok, cleaned, error_code)。

    注意：**落盘文件名永远由 sha256 生成**，此检查只用于拒绝明显危险的远端名并留痕。
    """
    raw = str(name or "")
    if not raw:
        return False, "", "ASSET_DANGEROUS_FILENAME"
    if any(c in raw for c in ("/", "\\", "\x00")) or ".." in raw:
        return False, raw, "ASSET_DANGEROUS_FILENAME"
    if PurePosixPath(raw).is_absolute() or Path(raw).is_absolute() or re.match(r"^[A-Za-z]:", raw):
        return False, raw, "ASSET_DANGEROUS_FILENAME"
    if any(ord(c) < 32 for c in raw) or any(c in _NAME_BAD_CHARS for c in raw):
        return False, raw, "ASSET_DANGEROUS_FILENAME"
    if len(raw) > _NAME_MAX:
        return False, raw, "ASSET_DANGEROUS_FILENAME"
    stem = Path(raw).stem.lower()
    if stem in _RESERVED:
        return False, raw, "ASSET_DANGEROUS_FILENAME"
    if Path(raw).suffix.lower() in _BAD_EXT:
        # 可执行/脚本类扩展名：属于"危险文件名"，在名字层就拒（扩展名白名单是第二道闸）
        return False, raw, "ASSET_DANGEROUS_FILENAME"
    if not raw.strip():
        return False, raw, "ASSET_DANGEROUS_FILENAME"
    return True, raw, None


# ---------------- 数据结构 ----------------
@dataclass
class MaterialQuery:
    text: str
    scene_id: str | None = None
    limit: int = 10
    kinds: tuple = ("image",)
    keywords: set = field(default_factory=set)


@dataclass
class ProviderCandidate:
    provider: str
    source_id: str
    name: str
    source_url: str | None = None
    ext: str = ""
    license: str | None = None
    attribution: str | None = None
    usage_restrictions: str | None = None
    bytes: int | None = None
    sha256: str | None = None
    downloaded_path: str | None = None
    download_status: str = "NOT_DOWNLOADED"     # NOT_DOWNLOADED/DOWNLOADED/ALREADY_LOCAL/FAILED
    probe_result: dict | None = None
    decodable: bool | None = None
    media_type: str | None = None
    width: int | None = None
    height: int | None = None
    status: str = "CANDIDATE"                   # CANDIDATE/VERIFIED/REJECTED
    error_code: str | None = None
    error_detail: str | None = None
    needs_hitl: bool = False
    license_cleared: bool = False
    license_class: str | None = None            # Phase 3-A：PUBLIC_DOMAIN/FREE_ATTRIBUTION/RESTRICTED/UNKNOWN
    match_score: int = 0
    matched_tokens: list = field(default_factory=list)

    def to_candidate(self) -> dict:
        """转换为**现有素材候选结构**（render 的素材池与 Phase 2-C 分类直接吃这个结构）。"""
        return {
            "path": self.downloaded_path,
            "name": self.name,
            "ext": self.ext,
            "size": self.bytes,
            "sha256": (self.sha256 or "")[:16],
            "license": self.license,
            "match_score": self.match_score,
            "matched_tokens": self.matched_tokens,
            # ---- Phase 2-D：来源与许可（纯新增字段，便于逐镜头追溯）----
            "provider": self.provider,
            "source_id": self.source_id,
            "source_url": self.source_url,
            "attribution": self.attribution,
            "usage_restrictions": self.usage_restrictions,
            "license_cleared": self.license_cleared,
            # Phase 3-A：许可类别随候选一起传递，渲染侧据此做**纵深防御**（RESTRICTED/UNKNOWN 不得入片）
            "license_class": self.license_class,
            "needs_hitl": self.needs_hitl,
            "download_status": self.download_status,
            "media_type": self.media_type,
            "decodable": self.decodable,
            "probe_result": self.probe_result,
            "verified": self.status == "VERIFIED",
        }

    def to_record(self) -> dict:
        d = dict(self.__dict__)
        return d


# ---------------- 传输层 ----------------
def _parse_retry_after(resp) -> float | None:
    """解析 `Retry-After`（秒数形式；HTTP-date 形式不解析，返回 None）。绝不抛异常。"""
    try:
        headers = getattr(resp, "headers", None)
        raw = headers.get("Retry-After") if headers is not None else None
    except Exception:                                     # noqa: BLE001 —— 头解析失败不影响主流程
        return None
    if raw is None:
        return None
    try:
        val = float(str(raw).strip())
    except (TypeError, ValueError):
        return None
    return val if val >= 0 else None


class TransportError(Exception):
    def __init__(self, code: str, detail: str, retry_after_s: float | None = None):
        super().__init__(f"[{code}] {detail}")
        self.code = code
        self.detail = detail
        # Phase 4-D：429 等场景可由传输层给出建议退避（仅在策略上限内被采纳）
        self.retry_after_s = retry_after_s


class _IPv4HTTPSConnection(http.client.HTTPSConnection):
    """**P35-3**：强制 IPv4 的 HTTPS 连接（TTS 同款修法）。

    动机（P33-2 实测失败归因）：本机可解析 AAAA 但**无 IPv6 出口** ⇒ 检索会
    在 IPv6 握手上超时（`PROVIDER_TIMEOUT`）；而 `urllib` 默认按 `getaddrinfo` 顺序尝试。
    处置：把解析结果**过滤为 AF_INET**，从根上避免走 IPv6（不是重试掩盖）。
    """

    def connect(self):
        addrs = socket.getaddrinfo(self.host, self.port, socket.AF_INET,
                                   socket.SOCK_STREAM)
        if not addrs:
            raise TransportError("PROVIDER_TIMEOUT",
                                 "IPv4 解析无结果：{}".format(self.host))
        af, st, proto, _, sa = addrs[0]
        sock = socket.socket(af, st, proto)
        try:
            if self.timeout is not socket._GLOBAL_DEFAULT_TIMEOUT:              # noqa: SLF001
                sock.settimeout(self.timeout)
            sock.connect(sa)
            self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
        except Exception:                                                       # noqa: BLE001
            sock.close()
            raise


class _IPv4Handler(urllib.request.HTTPSHandler):
    """把 HTTPS 连接替换为强制 IPv4 的实现（见 `_IPv4HTTPSConnection`）。"""

    def https_open(self, req):
        return self.do_open(_IPv4HTTPSConnection, req,
                            context=ssl.create_default_context())


class UrllibTransport:
    """默认传输：仅 HTTPS（可配）、禁跳转、限时限量、流式（超限即中断）。

    Phase 2-E：映射真实网络失败面 —— 401/403 → PROVIDER_AUTH_FAILED，429 → PROVIDER_RATE_LIMITED。
    token 只经 `auth_token` 注入（来自环境变量/.env），**不落日志、不写产物**。
    P35-3：`policy["force_ipv4"]=True` 时走 `_IPv4HTTPSConnection`（强制 IPv4）。
    """

    def __init__(self, policy: dict, auth_token: str | None = None):
        self.policy = policy
        self.auth_token = auth_token or ""

    def get(self, url: str, max_bytes: int, timeout_s: float) -> bytes:
        if self.policy.get("require_https", True) and not str(url).lower().startswith("https://"):
            raise TransportError("PROVIDER_HTTP_ERROR", "仅允许 https:// （require_https=true）")
        headers = {"User-Agent": "video-studio-material/1.0 (local pipeline)",
                   "Accept": "application/json,image/*;q=0.9,*/*;q=0.5"}
        if self.auth_token:
            headers["Authorization"] = "Bearer {}".format(self.auth_token)
        req = urllib.request.Request(url, headers=headers)
        _opener = None
        if self.policy.get("force_ipv4"):
            _opener = urllib.request.build_opener(_IPv4Handler())
        try:
            _open = _opener.open if _opener is not None else urllib.request.urlopen
            with _open(req, timeout=timeout_s) as resp:  # noqa: S310 —— 仅 http(s)
                status = getattr(resp, "status", 200)
                if status == 429:
                    # Phase 4-D：真实端点的 Retry-After 只在策略上限内被采纳（不无限等待）
                    raise TransportError("PROVIDER_RATE_LIMITED", "HTTP 429",
                                         retry_after_s=_parse_retry_after(resp))
                if status == 404:
                    raise TransportError("PROVIDER_HTTP_404", url)
                if status >= 500:
                    raise TransportError("PROVIDER_HTTP_5XX", "HTTP {}".format(status))
                if status >= 400:
                    raise TransportError("PROVIDER_HTTP_ERROR", "HTTP {}".format(status))
                chunks, total = [], 0
                while True:
                    b = resp.read(65536)
                    if not b:
                        break
                    total += len(b)
                    if total > max_bytes:
                        raise TransportError("ASSET_OVERSIZE",
                                             ">{} bytes（流式中断，未落盘）".format(max_bytes))
                    chunks.append(b)
        except TransportError:
            raise
        except urllib.error.HTTPError as exc:
            code = ("PROVIDER_HTTP_404" if exc.code == 404
                    else "PROVIDER_AUTH_FAILED" if exc.code in (401, 403)
                    else "PROVIDER_RATE_LIMITED" if exc.code == 429
                    else "PROVIDER_HTTP_5XX" if exc.code >= 500 else "PROVIDER_HTTP_ERROR")
            raise TransportError(code, "HTTP {}".format(exc.code),
                                 retry_after_s=_parse_retry_after(exc)
                                 if exc.code == 429 else None) from None
        except TimeoutError:
            raise TransportError("PROVIDER_TIMEOUT", "读取超时 {}s".format(timeout_s)) from None
        except (urllib.error.URLError, OSError) as exc:
            reason = str(getattr(exc, "reason", exc))
            code = "PROVIDER_TIMEOUT" if "timed out" in reason.lower() else "PROVIDER_DOWNLOAD_FAILED"
            raise TransportError(code, reason[:200]) from None
        data = b"".join(chunks)
        if not data:
            raise TransportError("PROVIDER_EMPTY_RESPONSE", "0 字节响应")
        return data


# ---------------- 校验（下载后边界） ----------------
def sniff_media_type(path: Path) -> tuple[str | None, str | None]:
    """按 magic bytes 判定实际媒体类型。返回 (media_type, error_code)。**不看扩展名**。"""
    try:
        head = path.open("rb").read(16)
    except OSError as exc:
        return None, "ASSET_DECODE_FAILED: {}".format(type(exc).__name__)
    for ext, magic in _MAGIC:
        if head.startswith(magic):
            return ("jpeg" if ext in (".jpg", ".jpeg") else "png"), None
    if head.startswith(_WEBP_PREFIX) and head[8:12] == _WEBP_TAG:
        return "webp", None
    return None, "ASSET_TYPE_MISMATCH"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _probe(ctx, path: Path) -> tuple[dict | None, str | None]:
    """ffprobe 校验：必须有图像/视频流且尺寸有效。"""
    from .base import ToolError
    from .ffmpeg_tool import FFmpegTool
    try:
        res = FFmpegTool().execute({"op": "probe", "inputs": [str(path)]}, ctx)
    except ToolError as exc:
        return None, "ASSET_PROBE_FAILED: {}".format(str(exc)[:120])
    streams = (res.data or {}).get("streams") or []
    vis = [s for s in streams if s.get("codec_type") in ("video", "image")]
    if not vis:
        return {"streams": streams}, "ASSET_PROBE_FAILED: 无图像/视频流"
    s0 = vis[0]
    try:
        w, h = int(s0.get("width") or 0), int(s0.get("height") or 0)
    except (TypeError, ValueError):
        w, h = 0, 0
    if w <= 0 or h <= 0:
        return {"streams": streams}, "ASSET_PROBE_FAILED: 尺寸无效"
    return {"streams": streams, "codec": s0.get("codec_name"), "width": w, "height": h}, None


def _ffmpeg_decode(ffmpeg: str | None, path: Path) -> tuple[bool, str | None]:
    """ffmpeg 解码校验（rc≠0 → 不可用）。"""
    if not ffmpeg:
        return True, None
    try:
        p = subprocess.run([ffmpeg, "-v", "error", "-i", str(path), "-f", "null", "-"],
                           capture_output=True, text=True, timeout=120,
                           encoding="utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError) as exc:
        return False, "ASSET_FFMPEG_DECODE_FAILED: {}".format(type(exc).__name__)
    if p.returncode != 0:
        return False, "ASSET_FFMPEG_DECODE_FAILED: rc={} {}".format(
            p.returncode, (p.stderr or "")[:120])
    return True, None


def container_integrity(path: Path, media_type: str | None) -> tuple[bool, str | None]:
    """容器完整性检查：真实网络下载可能被截断，而**宽松的解码器不会报错**。

    实测（Phase 2-E）：把真实 JPEG 截断到 2 KB 后，magic bytes、ffprobe、ffmpeg 解码（rc=0）、
    `PIL.Image.verify()`（只校验文件头）**全部通过** —— 因此必须显式检查容器结束标记/长度字段。
    """
    try:
        size = path.stat().st_size
        with path.open("rb") as fh:
            head = fh.read(16)
            fh.seek(max(0, size - 64))
            tail = fh.read(64)
    except OSError as exc:
        return False, "ASSET_DECODE_FAILED: {}".format(type(exc).__name__)
    if media_type == "jpeg":
        return (b"\xff\xd9" in tail, None) if b"\xff\xd9" in tail else (
            False, "ASSET_TRUNCATED: 缺少 JPEG EOI(FFD9) 结束标记")
    if media_type == "png":
        return (True, None) if b"IEND" in tail else (False, "ASSET_TRUNCATED: 缺少 PNG IEND")
    if media_type == "webp":
        if len(head) >= 12 and head[:4] == b"RIFF":
            declared = int.from_bytes(head[4:8], "little") + 8
            if declared != size:
                return False, "ASSET_TRUNCATED: RIFF 声明 {} != 实际 {}".format(declared, size)
        return True, None
    return True, None


def verify_material(path: Path, *, policy: dict, ctx=None, expected_ext: str | None = None,
                    check_license: str | None = None) -> dict:
    """对**已落盘**的文件做全量校验。返回 {status, error_code, ...}，绝不抛异常给调用方。"""
    pol = {**DEFAULT_POLICY, **(policy or {})}
    out = {"status": "REJECTED", "error_code": None, "error_detail": None, "bytes": None,
           "sha256": None, "ext": None, "media_type": None, "probe_result": None,
           "decodable": None, "width": None, "height": None, "ffmpeg_decode_ok": None}
    if not path.is_file():
        out.update(error_code="ASSET_DECODE_FAILED", error_detail="文件不存在")
        return out
    size = path.stat().st_size
    out["bytes"] = size
    ext = path.suffix.lower()
    out["ext"] = ext
    if size <= 0:
        out.update(error_code="ASSET_EMPTY_FILE", error_detail="0 字节")
        return out
    if size > int(pol["max_bytes"]):
        out.update(error_code="ASSET_OVERSIZE",
                   error_detail="{} > {}".format(size, pol["max_bytes"]))
        return out
    if expected_ext and ext != expected_ext.lower():
        out.update(error_code="ASSET_EXTENSION_NOT_ALLOWED",
                   error_detail="{} != {}".format(ext, expected_ext))
        return out
    if ext not in [e.lower() for e in pol["allowed_ext"]]:
        out.update(error_code="ASSET_EXTENSION_NOT_ALLOWED", error_detail=ext)
        return out
    out["sha256"] = sha256_file(path)
    media_type, err = sniff_media_type(path)
    if err:
        out.update(error_code=err.split(":")[0], error_detail=err)
        return out
    out["media_type"] = media_type
    integ_ok, integ_err = container_integrity(path, media_type)
    if not integ_ok:
        out.update(error_code=(integ_err or "ASSET_TRUNCATED").split(":")[0],
                   error_detail=integ_err)
        return out
    if ctx is not None:
        probe, err = _probe(ctx, path)
        out["probe_result"] = probe
        if err:
            out.update(error_code=err.split(":")[0], error_detail=err)
            return out
        w, h = probe.get("width"), probe.get("height")
        out["width"], out["height"] = w, h
        if w < int(pol["min_width"]) or h < int(pol["min_height"]):
            out.update(error_code="ASSET_TOO_SMALL",
                       error_detail="{}x{} < {}x{}".format(w, h, pol["min_width"],
                                                           pol["min_height"]))
            return out
        ffmpeg = ((ctx.config.get("tools", {}).get("ffmpeg", {}) or {}).get("path")
                  if hasattr(ctx, "config") else None)
        exe = shutil.which(ffmpeg or "ffmpeg")
        ok, derr = _ffmpeg_decode(exe, path)
        out["ffmpeg_decode_ok"] = ok
        if not ok:
            out.update(error_code=derr.split(":")[0], error_detail=derr)
            return out
    try:
        from PIL import Image
        with Image.open(path) as im:
            im.verify()
        # verify() 只校验文件头；必须**完整解码**像素（截断文件在此暴露）
        with Image.open(path) as im2:
            im2.load()
        out["decodable"] = True
    except Exception as exc:                              # noqa: BLE001
        code = "ASSET_TRUNCATED" if "truncat" in str(exc).lower() else "ASSET_DECODE_FAILED"
        out.update(error_code=code,
                   error_detail="{}: {}".format(type(exc).__name__, str(exc)[:100]))
        return out
    # 许可证：缺失/不明确 → 不得进入正常素材路径（由调用方转成 ASSET_UNUSABLE + needs_hitl）
    lic = (check_license or "").strip().lower()
    if check_license is not None and (not lic or lic in ("unknown", "unchecked", "n/a", "none")):
        out.update(status="REJECTED",
                   error_code="ASSET_LICENSE_MISSING" if not lic else "ASSET_LICENSE_UNCLEAR",
                   error_detail="license={!r}".format(check_license))
        return out
    out["status"] = "VERIFIED"
    return out


# ---------------- Provider 基类与实现 ----------------
class MaterialProvider:
    name = "base"
    is_external = False

    def __init__(self, policy: dict | None = None, transport=None):
        self.policy = {**DEFAULT_POLICY, **(policy or {})}
        self.transport = transport or UrllibTransport(self.policy)
        self.stats = {"searched": 0, "fetched": 0, "rejected": 0, "downloaded_bytes": 0,
                      "cache_hits": 0, "retries": 0}

    def capabilities(self) -> dict:
        return {"provider": self.name, "is_external": self.is_external,
                "limits": {k: self.policy[k] for k in
                           ("max_bytes", "timeout_s", "max_retries", "max_concurrent_downloads",
                            "max_cache_bytes", "allowed_ext", "min_width", "min_height",
                            "license_required", "require_https")}}

    # 子类实现
    def search(self, query: MaterialQuery, ctx) -> list[ProviderCandidate]:
        raise NotImplementedError

    def fetch(self, candidates: Iterable[ProviderCandidate], ctx) -> list[ProviderCandidate]:
        out = []
        for c in candidates:
            out.append(self._fetch_one(c, ctx))
        return out

    def _fetch_one(self, c: ProviderCandidate, ctx) -> ProviderCandidate:
        raise NotImplementedError

    # 通用：内容寻址缓存 + (provider, source_id) 索引（**先查索引再下载**，防重复下载）
    CACHE_INDEX = ".index.json"

    def _cache_lookup(self, cache_dir: Path, source_id: str) -> Path | None:
        """按 (provider, source_id) 命中缓存 → 返回已落盘文件（不再触发下载）。"""
        idx = self._read_index(cache_dir)
        ent = idx.get("{}|{}".format(self.name, source_id))
        if not ent:
            return None
        p = cache_dir / str(ent.get("file") or "")
        try:
            if p.is_file() and p.stat().st_size == int(ent.get("bytes") or -1):
                self.stats["cache_hits"] += 1
                return p
        except (OSError, TypeError, ValueError):
            return None
        return None

    def _cache_store(self, cache_dir: Path, source_id: str, path: Path) -> None:
        idx = self._read_index(cache_dir)
        idx["{}|{}".format(self.name, source_id)] = {
            "file": path.name, "bytes": path.stat().st_size, "cached_at": time.time()}
        try:
            (cache_dir / self.CACHE_INDEX).write_text(
                json.dumps(idx, ensure_ascii=False, indent=1), encoding="utf-8")
        except OSError:
            pass

    def _read_index(self, cache_dir: Path) -> dict:
        p = cache_dir / self.CACHE_INDEX
        if p.is_file():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
            except (OSError, json.JSONDecodeError):
                pass
        return {}

    def _throttle(self) -> None:
        """请求节流钩子（子类可按 provider 礼仪实现最小间隔）。"""

    def _download(self, url: str, cache_dir: Path, ctx, source_id: str = "") -> tuple[Path | None, str | None, str | None]:
        pol = self.policy
        cache_dir.mkdir(parents=True, exist_ok=True)
        if source_id:
            hit = self._cache_lookup(cache_dir, source_id)
            if hit is not None:
                return hit, None, None
        if _dir_bytes(cache_dir) >= int(pol["max_cache_bytes"]):
            return None, "PROVIDER_CACHE_LIMIT", "缓存已达上限 {} 字节".format(pol["max_cache_bytes"])
        attempts = 1 + int(pol["max_retries"])
        last = (None, "PROVIDER_DOWNLOAD_FAILED", "未尝试")
        for i in range(attempts):
            self._throttle()                     # 真实 provider 礼仪：下载同样需要节流（实测 429）
            try:
                data = self.transport.get(url, int(pol["max_bytes"]), float(pol["timeout_s"]))
            except TransportError as exc:
                last = (None, exc.code, exc.detail)
                # Phase 4-D：重试判定/退避统一走 core.supply.retry_decision（默认策略下与 2-D/2-E 逐值一致）
                plan = _retry_decision(exc.code, i, pol,
                                       retry_after_s=getattr(exc, "retry_after_s", None))
                if plan["retry"]:
                    self.stats["retries"] += 1
                    if exc.code == "PROVIDER_RATE_LIMITED":
                        self.stats["rate_limited"] = self.stats.get("rate_limited", 0) + 1
                    if plan["sleep_s"] > 0:
                        time.sleep(float(plan["sleep_s"]))
                    continue
                return last
            sha = hashlib.sha256(data).hexdigest()
            ext = Path(url.split("?")[0]).suffix.lower()
            dest = cache_dir / "{}{}".format(sha, ext)
            if dest.is_file() and dest.stat().st_size == len(data):
                self.stats["cache_hits"] += 1
            else:
                tmp = dest.with_suffix(dest.suffix + ".part")
                tmp.write_bytes(data)
                os.replace(tmp, dest)                 # 原子落盘；文件名为 sha256，不含远端路径
                self.stats["downloaded_bytes"] += len(data)
            if source_id:
                self._cache_store(cache_dir, source_id, dest)
            return dest, None, None
        return last

    def _license_flags(self, c: ProviderCandidate) -> None:
        """统一许可判定（**所有 provider 共用**，Phase 3-A 起含类别门禁）。

        历史缺陷（Phase 3-A 实测）：只有 Wikimedia provider 用了类别分类，通用 provider 只判"非空即清权"，
        于是 `fair use` 这类受限声明会被当成已清权放行。现在统一：类别由 `classify_license` 机械判定，
        只有 `PUBLIC_DOMAIN` / `FREE_ATTRIBUTION` 视为已清权；其余置 `needs_hitl=True`。
        """
        klass, cleared = classify_license(c.license)
        c.license_class = klass
        c.license_cleared = cleared
        if not cleared:
            c.needs_hitl = True


def _dir_bytes(d: Path) -> int:
    total = 0
    if d.is_dir():
        for p in d.rglob("*"):
            if p.is_file():
                try:
                    total += p.stat().st_size
                except OSError:
                    pass
    return total


# ---------------- Phase 3-A：许可合规门禁（规则本体在 core/materials.py，单一来源）----------------
from ..core.materials import (LICENSE_CLASSES, classify_license,  # noqa: E402
                              is_external_candidate, license_block_reason,
                              license_gate_applies)

__all__ = ["LICENSE_CLASSES", "classify_license", "license_block_reason",
           "license_gate_applies", "is_external_candidate"]


class LocalIngestProvider(MaterialProvider):
    """现有 local_ingest 的**兼容实现**：搜索项目 media/ 索引，就地校验，不下载不复制。"""

    name = "local_ingest"
    is_external = False

    def search(self, query: MaterialQuery, ctx) -> list[ProviderCandidate]:
        from ..agents.retrieval.agent import matched_tokens, score
        media = Path(ctx.project_dir) / "media"
        files = list((ctx.inputs or {}).get("index_files") or []) if hasattr(ctx, "inputs") else []
        out = []
        for f in files:
            rel = str(f.get("path") or "")
            hay = "{} {}".format(f.get("name", ""), f.get("ext", ""))
            s = score(hay, query.keywords)
            if s <= 0:
                continue
            out.append(ProviderCandidate(
                provider=self.name, source_id=rel, name=str(f.get("name") or rel),
                source_url=None, ext=str(f.get("ext") or Path(rel).suffix),
                license=f.get("license"), bytes=f.get("size"), sha256=f.get("sha256"),
                downloaded_path=rel, download_status="ALREADY_LOCAL",
                match_score=s, matched_tokens=matched_tokens(hay, query.keywords)))
            self.stats["searched"] += 1
        out.sort(key=lambda c: -c.match_score)
        return out[:query.limit]

    def _fetch_one(self, c: ProviderCandidate, ctx) -> ProviderCandidate:
        media = Path(ctx.project_dir) / "media"
        rel = c.downloaded_path or ""
        ok, clean, err = safe_filename(Path(rel).name)
        if not ok:
            c.status, c.error_code, c.error_detail = "REJECTED", err, rel
            self.stats["rejected"] += 1
            return c
        res = verify_material(media / rel, policy=self.policy, ctx=ctx, check_license=None)
        _apply_verdict(c, res)
        self._license_flags(c)
        block = license_block_reason({"license": c.license, "license_class": c.license_class,
                                      "license_cleared": c.license_cleared},
                                     require_license=bool(self.policy["license_required"]))
        if block and c.status == "VERIFIED":
            c.status = "REJECTED"
            c.error_code = block
            c.error_detail = "license={!r} class={}（需人工确认/授权，不猜测）".format(
                c.license, c.license_class)
        if c.status != "VERIFIED":
            self.stats["rejected"] += 1
        return c


class LocalCatalogProvider(MaterialProvider):
    """fake/local provider：本地目录 + catalogue.json（验收用），走**同一条**下载+校验管线。

    catalogue.json: {"items": [{"source_id","name","url"|"file","license","attribution",
                                "usage_restrictions","ext"} ...]}
    其中 `file` 为本地路径（模拟"下载源"），`url` 用于 HTTP 形态；二者都经过传输层与校验。
    `simulate` 字段仅供**测试注入**（timeout/http_404/http_500/empty），生产目录不应包含。
    """

    name = "local_catalog"
    is_external = True

    def __init__(self, policy=None, transport=None, catalog_dir: str | Path | None = None):
        super().__init__(policy, transport)
        self.catalog_dir = Path(catalog_dir) if catalog_dir else None
        self.stats["catalog_items"] = 0

    def _load_catalog(self) -> list[dict]:
        if not self.catalog_dir:
            raise TransportError("PROVIDER_NOT_CONFIGURED", "未配置 catalogue 目录")
        p = Path(self.catalog_dir) / "catalogue.json"
        if not p.is_file():
            raise TransportError("PROVIDER_CATALOG_INVALID", "缺少 catalogue.json")
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise TransportError("PROVIDER_CATALOG_INVALID", str(exc)[:120]) from None
        items = data.get("items")
        if not isinstance(items, list):
            raise TransportError("PROVIDER_CATALOG_INVALID", "items 必须是数组")
        return items

    def search(self, query: MaterialQuery, ctx) -> list[ProviderCandidate]:
        from ..agents.retrieval.agent import matched_tokens, score
        out = []
        for it in self._load_catalog():
            name = str(it.get("name") or it.get("source_id") or "")
            hay = "{} {}".format(name, it.get("ext") or Path(name).suffix)
            s = score(hay, query.keywords)
            if s <= 0:
                continue
            out.append(ProviderCandidate(
                provider=self.name, source_id=str(it.get("source_id") or name), name=name,
                source_url=it.get("url") or it.get("file"), ext=str(it.get("ext")
                                                                   or Path(name).suffix),
                license=it.get("license"), attribution=it.get("attribution"),
                usage_restrictions=it.get("usage_restrictions"),
                match_score=s, matched_tokens=matched_tokens(hay, query.keywords)))
            out[-1]._simulate = it.get("simulate")          # type: ignore[attr-defined]
        self.stats["catalog_items"] = len(out)
        out.sort(key=lambda c: -c.match_score)
        return out[:query.limit]

    def _fetch_one(self, c: ProviderCandidate, ctx) -> ProviderCandidate:
        media = Path(ctx.project_dir) / "media"
        cache_dir = media / str(self.policy["cache_dir"])
        ok, clean, err = safe_filename(c.name)
        if not ok:
            c.status, c.error_code, c.error_detail = "REJECTED", err, "危险文件名: {}".format(c.name)
            self.stats["rejected"] += 1
            self._license_flags(c)
            return c
        simulate = getattr(c, "_simulate", None)
        try:
            if simulate:
                raise TransportError(*_simulate_error(simulate))
            src = c.source_url or ""
            if str(src).lower().startswith(("http://", "https://")):
                path, code, detail = self._download(src, cache_dir, ctx, source_id=c.source_id)
                if path is None:
                    c.status, c.error_code, c.error_detail = "REJECTED", code, detail
                    c.download_status = "FAILED"
                    self.stats["rejected"] += 1
                    self._license_flags(c)
                    return c
                c.download_status = "DOWNLOADED"
            else:
                sp = Path(src)
                if not sp.is_absolute():
                    sp = Path(self.catalog_dir or ".") / src
                if not sp.is_file():
                    raise TransportError("PROVIDER_DOWNLOAD_FAILED", "源文件不存在: {}".format(src))
                if sp.stat().st_size > int(self.policy["max_bytes"]):
                    raise TransportError("ASSET_OVERSIZE",
                                         "{} > {}".format(sp.stat().st_size, self.policy["max_bytes"]))
                cache_dir.mkdir(parents=True, exist_ok=True)
                if _dir_bytes(cache_dir) >= int(self.policy["max_cache_bytes"]):
                    raise TransportError("PROVIDER_CACHE_LIMIT",
                                         "缓存已达上限 {} 字节".format(self.policy["max_cache_bytes"]))
                dest = cache_dir / (hashlib.sha256(sp.read_bytes()).hexdigest()
                                    + sp.suffix.lower())
                if not dest.is_file():
                    shutil.copyfile(sp, dest)
                    self.stats["downloaded_bytes"] += dest.stat().st_size
                else:
                    self.stats["cache_hits"] += 1
                path = dest
                c.download_status = "DOWNLOADED"
        except TransportError as exc:
            c.status, c.error_code, c.error_detail = "REJECTED", exc.code, exc.detail
            c.download_status = "FAILED"
            self.stats["rejected"] += 1
            self._license_flags(c)
            return c
        c.downloaded_path = path.relative_to(media).as_posix()
        res = verify_material(path, policy=self.policy, ctx=ctx, check_license=None)
        _apply_verdict(c, res)
        if not c.sha256:
            c.sha256 = res.get("sha256")
        self._license_flags(c)
        # 许可证缺失/不明确：**不得**静默进入正常素材路径（即便文件本身合法）
        block = license_block_reason({"license": c.license, "license_class": c.license_class,
                                      "license_cleared": c.license_cleared},
                                     require_license=bool(self.policy["license_required"]))
        if block and c.status == "VERIFIED":
            c.status = "REJECTED"
            c.error_code = block
            c.error_detail = "license={!r} class={}（需人工确认/授权，不猜测）".format(
                c.license, c.license_class)
        if c.status != "VERIFIED":
            self.stats["rejected"] += 1
        return c


class HttpCatalogProvider(LocalCatalogProvider):
    """真实外部形态：catalogue 从 HTTPS 端点获取，素材逐条下载（transport 可注入）。"""

    name = "http_catalog"
    is_external = True

    def _load_catalog(self) -> list[dict]:
        url = (self.policy.get("catalog") or "")
        if not url:
            raise TransportError("PROVIDER_NOT_CONFIGURED", "未配置 catalogue 端点")
        try:
            data = self.transport.get(url, 1 << 20, float(self.policy["timeout_s"]))
            parsed = json.loads(data.decode("utf-8"))
        except TransportError:
            raise
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TransportError("PROVIDER_CATALOG_INVALID", str(exc)[:120]) from None
        items = parsed.get("items")
        if not isinstance(items, list):
            raise TransportError("PROVIDER_CATALOG_INVALID", "items 必须是数组")
        self.catalog_dir = None
        return items


def _simulate_error(kind: str) -> tuple[str, str]:
    return {"timeout": ("PROVIDER_TIMEOUT", "模拟超时"),
            "http_404": ("PROVIDER_HTTP_404", "模拟 404"),
            "http_500": ("PROVIDER_HTTP_5XX", "模拟 500"),
            "empty": ("PROVIDER_EMPTY_RESPONSE", "模拟空响应")}.get(
                str(kind), ("PROVIDER_DOWNLOAD_FAILED", "模拟失败: {}".format(kind)))


def _apply_verdict(c: ProviderCandidate, res: dict) -> None:
    c.bytes = res.get("bytes")
    c.sha256 = res.get("sha256") or c.sha256
    c.media_type = res.get("media_type")
    c.probe_result = res.get("probe_result")
    c.decodable = res.get("decodable")
    c.width, c.height = res.get("width"), res.get("height")
    if res.get("status") == "VERIFIED":
        c.status, c.error_code, c.error_detail = "VERIFIED", None, None
    else:
        c.status = "REJECTED"
        c.error_code = res.get("error_code")
        c.error_detail = res.get("error_detail")


# ---------------- 工厂 / 并发 ----------------
def provider_from_config(config: dict | None) -> tuple[MaterialProvider | None, str | None, dict]:
    """按配置构造 provider。返回 (provider|None, error_code, policy)。

    选择顺序：`tools.material.provider` → `tools.image.provider`（既有开关）→ "none"。
    Phase 2-E：真实 provider 的凭据只从环境变量/.env 读取；`auth.require_key=true` 且无凭据时
    返回 `PROVIDER_NOT_CONFIGURED`（**不伪造候选**）。
    """
    tools = ((config or {}).get("tools") or {})
    mat = dict(tools.get("material") or {})
    pol = {**DEFAULT_POLICY, **mat}
    name = str(pol.get("provider") or "none")
    if name in ("", "none"):
        img = str((tools.get("image") or {}).get("provider") or "none")
        name = img
    if name in ("", "none"):
        return None, None, pol
    if name in ("local_ingest", "local_catalog", "http_catalog"):
        auth = pol.get("auth") or {}
        if auth.get("require_key"):
            from ..core.env import load_env
            load_env(Path(".env"))
            if not os.environ.get(str(auth.get("api_key_env") or ""), "").strip():
                return None, "PROVIDER_NOT_CONFIGURED", pol
    if name == "local_ingest":
        return LocalIngestProvider(pol), None, pol
    if name == "local_catalog":
        return LocalCatalogProvider(pol, catalog_dir=pol.get("catalog")), None, pol
    if name == "http_catalog":
        return HttpCatalogProvider(pol), None, pol
    if name == "wikimedia_commons":
        from .provider_wikimedia import WikimediaCommonsProvider
        p = WikimediaCommonsProvider(pol)
        if (p.policy.get("auth") or {}).get("require_key") and not p.stats.get("token_present"):
            return None, "PROVIDER_NOT_CONFIGURED", pol
        return p, None, pol
    return None, "PROVIDER_UNKNOWN", pol


def fetch_many(provider: MaterialProvider, candidates: list[ProviderCandidate], ctx) -> list[ProviderCandidate]:
    """带**并发上限**的批量获取（默认 2；失败不影响其他候选）。"""
    n = max(1, int(provider.policy["max_concurrent_downloads"]))
    if n == 1 or len(candidates) <= 1:
        return provider.fetch(candidates, ctx)
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=min(n, len(candidates))) as pool:
        return list(pool.map(lambda c: provider._fetch_one(c, ctx), candidates))
