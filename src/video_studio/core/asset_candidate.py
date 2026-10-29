# -*- coding: utf-8 -*-
"""P7-2：**AssetCandidate 契约**（统一资产身份；确定性、离线、零网络）。

设计要点
--------
1. **不知道 ≠ 猜测**：无法确定的事实一律 `UNKNOWN`（未获取/无法判定）或 `NOT_AVAILABLE`
   （该媒体类别本就不适用，例如图像没有 duration）；**不得**用默认值冒充事实。
2. **stable asset_id**：由**内容身份**派生（sha256 + media_kind），与路径、扫描顺序、进程、机器无关：
       asset_id = "ast-" + sha256(canonical({"sha256":…, "media_kind":…}))[:16]
   文件内容一变 ⇒ sha256 变 ⇒ asset_id 变（**不得**仅凭文件名认定"同一素材"）。
3. **sha256 是硬身份**：每个条目记录 sha256 并由 `path → bytes → sha256` 可复算。
4. **感知身份**：复用既有 `orchestration/content_identity.py`（dHash / hamming / MD5 聚类），
   **不新增算法**。感知家族 id 由**成员 dHash** 内容派生（`pf-<hash16>`），因此与路径/顺序无关
   （该模块自身的 `C001` 标签是按路径排序分配的，故**不**直接用作稳定 id）。
5. **镜像不变比较**：既有实现未提供 ⇒ 明确 `UNKNOWN`（不新造算法、不为测试放宽阈值）。
6. **完整 G0–G9 完整性门禁未接线**：`integrity_status` 只按"存在/MIME/可解码/最小尺寸"给出
   最小判定，并显式记录 `full_gate_status = NOT_WIRED`（不冒充已接线）。
"""
from __future__ import annotations

import re

from .visual_requirement import VisualRequirementError, canonical, norm_text, sha256_text

SCHEMA = "asset-candidate-v1"
INDEX_SCHEMA = "asset-index-v1"
INDEX_VERSION = 1

#: 未知语义（不得与"已知为否"混淆）
UNKNOWN = "UNKNOWN"
NOT_AVAILABLE = "NOT_AVAILABLE"

MEDIA_KINDS = ("image", "video", "audio", "other")
SOURCE_TYPES = ("local", "external", "web", "self_made", "ai_generated", "screenshot",
                "frozen_material_plan", UNKNOWN)
DECODE_STATES = ("OK", "FAILED", UNKNOWN)
INTEGRITY_STATES = ("OK", "DEMOTE", "BLOCK", UNKNOWN)

ASSET_ID_PREFIX = "ast-"
FAMILY_ID_PREFIX = "pf-"

#: 每字段：为什么需要 / 来源 / 缺失或无法确定时如何表示
FIELD_SPEC = {
    "asset_id": {"why": "稳定身份，跨阶段/跨机器引用；决定「同一素材」判定",
                 "source": "sha256 + media_kind 的内容派生", "when_unavailable": "不可能缺失"},
    "path": {"why": "定位字节以复算 sha256", "source": "文件系统扫描",
             "when_unavailable": "不可能缺失（条目由真实文件产生）"},
    "sha256": {"why": "**硬身份**；内容变更必须改变身份", "source": "path→bytes→sha256",
               "when_unavailable": "不可能缺失"},
    "media_kind": {"why": "决定几何/时长字段是否适用", "source": "MIME/扩展名 + ffprobe 流",
                   "when_unavailable": "UNKNOWN"},
    "width": {"why": "几何身份与最小尺寸门禁", "source": "PIL/ffprobe",
              "when_unavailable": "UNKNOWN（解码失败时）"},
    "height": {"why": "几何身份与最小尺寸门禁", "source": "PIL/ffprobe",
               "when_unavailable": "UNKNOWN（解码失败时）"},
    "duration_s": {"why": "视频/音频时长（准入与窗口匹配）", "source": "ffprobe",
                   "when_unavailable": "NOT_AVAILABLE（静态图像）；UNKNOWN（无法探测）"},
    "frame_count": {"why": "视频帧数（时长×帧率的硬计数）", "source": "ffprobe nb_frames",
                    "when_unavailable": "NOT_AVAILABLE（图像）；UNKNOWN（容器未提供）"},
    "source_type": {"why": "来源类别决定许可/治理策略",
                    "source": "项目内记录（provider/attribution/H5 人工验收记录）",
                    "when_unavailable": "UNKNOWN（不猜来源）"},
    "provider": {"why": "溯源（外部素材必需）",
                 "source": "media/external/.index.json、attribution artifact、H5 素材记录",
                 "when_unavailable": "UNKNOWN"},
    "source_id": {"why": "溯源（提供方内部 id）", "source": "同上", "when_unavailable": "UNKNOWN"},
    "source_url": {"why": "溯源（可核验链接）", "source": "同上",
                   "when_unavailable": "UNKNOWN（**不构造 URL**）"},
    "license": {"why": "许可门禁与署名台账", "source": "既有声明字段（不判定合法性）",
                "when_unavailable": "UNKNOWN"},
    "license_class": {"why": "机械分类（PUBLIC_DOMAIN/FREE_ATTRIBUTION/RESTRICTED/UNKNOWN）",
                      "source": "core.materials.classify_license", "when_unavailable": "UNKNOWN"},
    "attribution": {"why": "署名义务", "source": "attribution artifact / H5 记录",
                    "when_unavailable": "UNKNOWN"},
    "license_restricted": {"why": "受限素材不得入片", "source": "license_class→布尔（RESTRICTED⇒True）",
                           "when_unavailable": "UNKNOWN（本地 ingest 无提供方声明时为未知，"
                                               "不得当作 False）"},
    "license_gate_applies": {"why": "区分「外部素材受门禁」与「本地自备素材不在门禁范围」",
                             "source": "core.materials.license_gate_applies",
                             "when_unavailable": "按字段本身计算（布尔）"},
    "decode_status": {"why": "不可解码素材绝不进入管线", "source": "PIL/ffprobe 实测",
                      "when_unavailable": "不可能缺失"},
    "integrity_status": {"why": "最小可用性判定（存在/MIME/解码/最小尺寸）",
                         "source": "core.materials.DEFAULT_POLICY 最小尺寸 + 解码结果",
                         "when_unavailable": "UNKNOWN"},
    "perceptual_identity": {"why": "近重复/裁剪/变换关系的基础（B/C/D 类）",
                            "source": "orchestration/content_identity.py 的 dHash/hamming（复用）",
                            "when_unavailable": "status=UNKNOWN（解码失败或模块不可用）"},
    "provenance": {"why": "可追溯（扫描根、来源文件、规则、是否复用算法）", "source": "构建期记录",
                   "when_unavailable": "不可能缺失"},
    "deterministic_hash": {"why": "条目确定性校验（同输入同 hash）", "source": "规范化 body 的 sha256",
                           "when_unavailable": "不可能缺失"},
}

REQUIRED_FIELDS = ("asset_id", "path", "sha256", "media_kind", "width", "height", "duration_s",
                   "frame_count", "source_type", "provider", "source_id", "source_url", "license",
                   "license_class", "attribution", "license_restricted", "license_gate_applies",
                   "decode_status", "integrity_status", "perceptual_identity", "provenance",
                   "deterministic_hash")

INVALID_ASSET = "AC_INVALID_ASSET"
INVALID_SHA = "AC_INVALID_SHA"
INVALID_MEDIA_KIND = "AC_INVALID_MEDIA_KIND"


def asset_identity_core(sha256: str, media_kind: str) -> dict:
    """参与 asset_id 的**最小内容身份**（不含路径/尺寸/时间戳）。"""
    return {"sha256": sha256, "media_kind": media_kind}


def stable_asset_id(sha256: str, media_kind: str) -> str:
    """稳定 asset_id（内容派生；跨机器/目录/进程一致）。"""
    if not re.fullmatch(r"[0-9a-f]{64}", sha256 or ""):
        raise VisualRequirementError(INVALID_SHA, repr(sha256)[:40])
    if media_kind not in MEDIA_KINDS:
        raise VisualRequirementError(INVALID_MEDIA_KIND, repr(media_kind))
    return ASSET_ID_PREFIX + sha256_text(canonical(asset_identity_core(sha256, media_kind)))[:16]


def family_id(dhash_hexes: list[str]) -> str:
    """感知家族 id：由**成员 dHash** 内容派生（与路径/顺序/机器无关）。"""
    hs = sorted(str(h) for h in dhash_hexes if h)
    return FAMILY_ID_PREFIX + sha256_text(canonical({"dhash": hs}))[:16]


def candidate_body(c: dict) -> dict:
    return {k: v for k, v in c.items() if k != "deterministic_hash"}


def candidate_hash(c: dict) -> str:
    return sha256_text(canonical(candidate_body(c)))


def validate_candidate(c: dict) -> list[str]:
    errs: list[str] = []
    if not isinstance(c, dict):
        return ["candidate 必须是对象"]
    for f in REQUIRED_FIELDS:
        if f not in c:
            errs.append("缺少字段 {}".format(f))
    if c.get("schema") != SCHEMA:
        errs.append("schema 必须为 {}".format(SCHEMA))
    sha = c.get("sha256")
    if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{64}", sha or ""):
        errs.append("sha256 非法")
    mk = c.get("media_kind")
    if mk not in MEDIA_KINDS:
        errs.append("media_kind 非法：{!r}".format(mk))
    elif isinstance(sha, str) and re.fullmatch(r"[0-9a-f]{64}", sha or ""):
        if c.get("asset_id") != stable_asset_id(sha, mk):
            errs.append("asset_id 与内容身份不一致（必须由 sha256+media_kind 派生）")
    if c.get("decode_status") not in DECODE_STATES:
        errs.append("decode_status 非法")
    if c.get("integrity_status") not in INTEGRITY_STATES:
        errs.append("integrity_status 非法")
    pi = c.get("perceptual_identity")
    if not isinstance(pi, dict) or "status" not in pi:
        errs.append("perceptual_identity 必须是含 status 的对象")
    if c.get("deterministic_hash") != candidate_hash(c):
        errs.append("deterministic_hash 与 body 不一致")
    # 图像不得给出 duration（NOT_AVAILABLE 而非编造）
    if mk == "image" and c.get("duration_s") not in (NOT_AVAILABLE, None) and \
            c.get("duration_s") != UNKNOWN:
        errs.append("图像 duration_s 必须是 {} 或 {}".format(NOT_AVAILABLE, UNKNOWN))
    return errs


def make_candidate(*, path: str, sha256: str, media_kind: str, width, height, duration_s,
                   frame_count, source_type: str, provider, source_id, source_url, license,
                   license_class, attribution, license_restricted, license_gate_applies: bool,
                   decode_status: str, decode_detail: str, integrity_status: str,
                   integrity_reasons: list, perceptual_identity: dict, provenance: dict,
                   bytes_: int | None = None, legacy_asset_ids: list | None = None,
                   role_in_master: str = UNKNOWN) -> dict:
    c = {
        "schema": SCHEMA,
        "asset_id": stable_asset_id(sha256, media_kind),
        "path": path, "sha256": sha256, "bytes": bytes_ if bytes_ is not None else UNKNOWN,
        "media_kind": media_kind,
        "width": width, "height": height,
        "duration_s": duration_s, "frame_count": frame_count,
        "source_type": source_type, "provider": provider, "source_id": source_id,
        "source_url": source_url, "license": license, "license_class": license_class,
        "attribution": attribution, "license_restricted": license_restricted,
        "license_gate_applies": bool(license_gate_applies),
        "decode_status": decode_status, "decode_detail": decode_detail,
        "integrity_status": integrity_status, "integrity_reasons": list(integrity_reasons or []),
        "perceptual_identity": perceptual_identity,
        "legacy_asset_ids": sorted(set(legacy_asset_ids or [])),
        "role_in_master": role_in_master,
        "provenance": provenance,
    }
    c["deterministic_hash"] = candidate_hash(c)
    errs = validate_candidate(c)
    if errs:
        raise VisualRequirementError(INVALID_ASSET, "; ".join(errs[:6]))
    return c


def perceptual_identity(dhash_bits, dhash_size: int = 8, md5=None, status: str = "OK",
                        reason: str = "") -> dict:
    """感知身份记录。`dhash_bits` 为 content_identity.dhash_of 的返回值（或 None）。"""
    out = {"method": "orchestration.content_identity.dhash_of（复用，未新增算法）",
           "dhash_size": dhash_size, "md5": md5 or UNKNOWN,
           "status": status,
           "mirror_invariance": {"status": UNKNOWN,
                                 "reason": "既有 content_identity/crop_recheck 未提供镜像不变比较；"
                                           "P7-2 不新增算法"}}
    if dhash_bits is not None and status == "OK":
        out["dhash_hex"] = "".join("1" if b else "0" for b in list(dhash_bits))
    else:
        out["dhash_hex"] = UNKNOWN
    if reason:
        out["reason"] = reason
    return out


def hamming_from_hex(a: str, b: str) -> int:
    """由 dhash_hex 计算汉明距离（复用 content_identity.hamming 的语义）。"""
    from ..orchestration.content_identity import hamming                      # noqa: WPS433
    import numpy as np                                                       # noqa: WPS433
    if not a or not b or len(a) != len(b) or UNKNOWN in (a, b):
        raise ValueError("dhash_hex 不可比较")
    av = np.array([c == "1" for c in a])
    bv = np.array([c == "1" for c in b])
    return int(hamming(av, bv))
