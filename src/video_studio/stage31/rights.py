"""Stage 3.1 版权/授权判定层（硬门槛）。

原则（§四/§十五）：
- 基于可验证的许可证与来源信息做版权风险筛选，不声称"绝对不会侵权"。
- SAFE / CONDITIONAL / UNSAFE / UNKNOWN 四档；UNSAFE / UNKNOWN 不得进入默认推荐池。
- 领域黑名单（影视/新闻/社交平台等）先行判定，不依赖"许可证文字"。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

# ---- 平台/领域黑名单（UNSAFE，先于许可证判断）----
UNSAFE_DOMAINS = (
    "youtube.com", "youtu.be", "bilibili.com", "xiaohongshu.com", "xhslink.com",
    "douyin.com", "iesdouyin.com", "tiktok.com", "v.qq.com", "iqiyi.com",
    "youku.com", "netflix.com", "disney.com", "marvel.com", "imdb.com",
    "weibo.com", "instagram.com", "facebook.com", "x.com", "twitter.com",
    "hbo.com", "hulu.com", "primevideo.com", "vimeo.com", "gettyimages.com",
    "shutterstock.com", "gettyimages.cn", "vcg.com", "tuchong.com",
    "zcool.com.cn", "huaban.com", "duitang.com",
)

# ---- 许可证分类（normalize 后前缀/包含匹配）----
_SAFE_PATTERNS = (
    "cc0", "cc-zero", "public domain", "pd", "cc pd", "cc-pd", "pdm",
)
_CONDITIONAL_PATTERNS = (
    "cc by 4.0", "cc by 3.0", "cc by 2.5", "cc by 2.0", "cc by 1.0", "cc by",
    "cc by-sa 4.0", "cc by-sa 3.0", "cc by-sa 2.5", "cc by-sa 2.0", "cc by-sa",
    "gfdl",
)
_UNSAFE_PATTERNS = (
    "cc by-nc", "cc by-nd", "all rights reserved", "copyright", "fair use",
    "©", "no known copyright",  # "no known copyright" 按 UNKNOWN 处理更稳——见下方顺序调整
)


def normalize_license(raw: Optional[str]) -> str:
    if not raw:
        return ""
    s = re.sub(r"\s+", " ", str(raw)).strip().lower()
    s = s.replace("creativecommons", "cc").replace("creative commons", "cc")
    return s


def _domain_unsafe(url: Optional[str]) -> bool:
    if not url:
        return False
    u = url.lower()
    return any(d in u for d in UNSAFE_DOMAINS)


@dataclass
class RightsInfo:
    status: str                      # SAFE | CONDITIONAL | UNSAFE | UNKNOWN
    commercial_use: bool = False
    attribution_required: bool = False
    attribution_text: str = ""
    license: str = ""
    license_url: str = ""
    copyright_notes: str = ""


def classify(url: Optional[str], license_text: Optional[str],
             source_name: str = "", creator: str = "") -> RightsInfo:
    """核心判定：领域黑名单 → 许可证文本 → UNKNOWN。"""
    # 1) 领域黑名单：影视/新闻/社交/商业图库站点一律 UNSAFE
    if _domain_unsafe(url):
        return RightsInfo(
            status="UNSAFE", license="all-rights-reserved(domain-blacklist)",
            copyright_notes="来源域在黑名单（影视/新闻/社交/图库平台），禁止作为 B-roll 进入推荐池。",
        )
    lic = normalize_license(license_text)

    # 2) 无任何许可证信息 → UNKNOWN
    if not lic:
        return RightsInfo(
            status="UNKNOWN", license="",
            copyright_notes="未提供可验证的许可证信息，按 §四 排除出默认推荐池。",
        )

    # 3) 非商业/禁演绎/版权保留 → UNSAFE
    if "by-nc" in lic or "by-nd" in lic or "all rights reserved" in lic or "fair use" in lic:
        return RightsInfo(
            status="UNSAFE", license=license_text or "",
            copyright_notes="许可证限制商业使用或演绎（NC/ND/ARR/FairUse），排除。",
        )

    # 4) CC0 / Public Domain → SAFE
    if any(p in lic for p in _SAFE_PATTERNS):
        return RightsInfo(
            status="SAFE", commercial_use=True, attribution_required=False,
            license=license_text or "",
            copyright_notes="公有领域 / CC0：可商用，无需署名。",
        )

    # 5) CC BY / CC BY-SA / GFDL → CONDITIONAL（必须署名，BY-SA 附带条件）
    if "by-sa" in lic:
        return RightsInfo(
            status="CONDITIONAL", commercial_use=True, attribution_required=True,
            license=license_text or "",
            attribution_text=_make_attribution(license_text, creator),
            copyright_notes="CC BY-SA：可商用，须署名作者与许可证；衍生作品须以相同许可证发布。",
        )
    if "cc by" in lic:
        return RightsInfo(
            status="CONDITIONAL", commercial_use=True, attribution_required=True,
            license=license_text or "",
            attribution_text=_make_attribution(license_text, creator),
            copyright_notes="CC BY：可商用，须署名作者并注明许可证。",
        )
    if "gfdl" in lic:
        return RightsInfo(
            status="CONDITIONAL", commercial_use=True, attribution_required=True,
            license=license_text or "",
            attribution_text=_make_attribution(license_text, creator),
            copyright_notes="GFDL：可商用，须署名并提供许可证副本。",
        )

    # 6) 其余无法识别 → UNKNOWN
    return RightsInfo(
        status="UNKNOWN", license=license_text or "",
        copyright_notes=f"许可证文本无法识别（{lic[:40]}），按 UNKNOWN 排除。",
    )


def _make_attribution(license_text, creator) -> str:
    parts = []
    if creator:
        parts.append(f"作者：{creator}")
    if license_text:
        parts.append(f"许可证：{license_text}")
    return " ｜ ".join(parts) if parts else "须按来源页要求署名"


def hard_gate(info: RightsInfo) -> bool:
    """默认推荐池只允许 SAFE；CONDITIONAL 需单独标注授权条件。"""
    return info.status == "SAFE"


def pool_status(info: RightsInfo) -> str:
    if info.status == "SAFE":
        return "SAFE_POOL"
    if info.status == "CONDITIONAL":
        return "CONDITIONAL_POOL"  # 允许进入"条件池"，但默认推荐列表仍以 SAFE 优先
    return "EXCLUDED"
