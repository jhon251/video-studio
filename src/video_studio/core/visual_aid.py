# -*- coding: utf-8 -*-
"""自制视觉辅助层（`add_visual_aid`）的 **schema / 校验 / 编译 / 渲染**。

设计原则（与 6-E 冻结规则一致）：
  · **无外部素材**：spec 中出现任何 asset_id / 图片路径 ⇒ 直接拒绝（fail-closed）；
  · **不伪造引语**：渲染文本不得出现西文双引号（直接引语标记）；『』内的强调短语长度受限；
  · **每条内容必须绑定来源**（`source` 为审计字段；画面只渲染 `source_label` 短标签）；
  · **可确定性编译**：`compile_from_plan_item()` 把冻结的素材计划（phase6e_material_plan.json 的
    `items.<key>.C_self_made_spec`）**逐字**转成 spec，不新增任何事实、不改写任何措辞；
  · **安全区**：叠加层不得进入画面底部 5%（字幕安全区）；
  · **字体显式**：必须给出字体文件；给定期望 sha256 时校验（fail-closed）。

本模块**不调用 ffmpeg**、不写除 overlay PNG 之外的任何文件。
"""
from __future__ import annotations

import hashlib
import json
import re
import textwrap
from pathlib import Path

SCHEMA = "visual-aid-spec-v1"
LAYOUTS = ("ladder_cards_positions", "panel_columns")
PANEL_KINDS = ("ladder", "cards", "positions", "timeline", "slots")
REQUIRED_TOP = ("schema", "layout", "panels", "no_external_assets", "forbid_verbatim_quotes")
REQUIRED_PANEL = ("id", "title", "kind", "items", "source", "source_label")
MAX_PANELS = 4
MAX_ITEMS_PER_PANEL = 8
MAX_ITEM_CHARS = 200
MAX_TITLE_CHARS = 28
MAX_SOURCE_LABEL_CHARS = 24
MAX_WRAPPED_LINES_PER_PANEL = 14
WRAP_COLS = 46
FOCUS_MARKERS = ("当前", "本片当前状态")
SAFE_BOTTOM_FRACTION = 0.95
DEFAULT_FONT = r"C:\Windows\Fonts\msyh.ttc"
# 画面/规格中禁止出现的资产标识（被明确否决的 IMO 合影）与外部素材键
FORBIDDEN_ASSET_IDS = ("asset_432cd85be6f1",)
EXTERNAL_KEYS = ("asset_id", "asset_path", "file", "file_path", "image", "image_path", "url",
                 "download", "local_path")
WESTERN_QUOTES = ('"', "\u201c", "\u201d")
CJK_QUOTE_SPAN = re.compile(r"[『「]([^』」]{0,})[』」]")
MAX_CJK_QUOTE_CHARS = 24


class VisualAidError(ValueError):
    """fail-closed：带稳定错误码，便于审计与测试。"""

    def __init__(self, code: str, why: str):
        super().__init__("{}: {}".format(code, why))
        self.code = code
        self.why = why


def spec_sha256(spec: dict) -> str:
    return hashlib.sha256(json.dumps(spec, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def _walk_strings(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk_strings(v, "{}.{}".format(path, k))
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            yield from _walk_strings(v, "{}[{}]".format(path, i))
    elif isinstance(obj, str):
        yield path, obj


def _walk_keys(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _walk_keys(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _walk_keys(v)


def verify_spec(spec: dict) -> dict:
    """校验 spec；任何不合格 ⇒ 抛 `VisualAidError`（fail-closed）。返回规范摘要。"""
    if not isinstance(spec, dict):
        raise VisualAidError("VISUAL_AID_SPEC_NOT_OBJECT", "spec 必须是对象")
    for f in REQUIRED_TOP:
        if f not in spec:
            raise VisualAidError("VISUAL_AID_SPEC_MISSING_FIELD", "缺少字段 {}".format(f))
    if spec["schema"] != SCHEMA:
        raise VisualAidError("VISUAL_AID_BAD_SCHEMA", "期望 {}，实际 {}".format(SCHEMA,
                                                                             spec["schema"]))
    if spec["layout"] not in LAYOUTS:
        raise VisualAidError("VISUAL_AID_BAD_LAYOUT", str(spec["layout"]))
    if spec.get("no_external_assets") is not True:
        raise VisualAidError("VISUAL_AID_EXTERNAL_ASSET",
                             "no_external_assets 必须为 true（自制层不得引用外部素材）")
    if spec.get("forbid_verbatim_quotes") is not True:
        raise VisualAidError("VISUAL_AID_VERBATIM_QUOTE", "forbid_verbatim_quotes 必须为 true")
    panels = spec.get("panels")
    if not isinstance(panels, list) or not (1 <= len(panels) <= MAX_PANELS):
        raise VisualAidError("VISUAL_AID_PANEL_COUNT",
                             "panel 数必须在 1..{}".format(MAX_PANELS))
    ids = set()
    for p in panels:
        if not isinstance(p, dict):
            raise VisualAidError("VISUAL_AID_PANEL_NOT_OBJECT", str(type(p)))
        for f in REQUIRED_PANEL:
            if f not in p:
                raise VisualAidError("VISUAL_AID_PANEL_MISSING_FIELD",
                                     "panel {} 缺少 {}".format(p.get("id"), f))
        if p["id"] in ids:
            raise VisualAidError("VISUAL_AID_PANEL_DUPLICATE_ID", p["id"])
        ids.add(p["id"])
        if not p["title"] or not p["source"] or not p["source_label"]:
            raise VisualAidError("VISUAL_AID_PANEL_MISSING_FIELD",
                                 "panel {} 的 title/source/source_label 不得为空".format(p["id"]))
        if p["kind"] not in PANEL_KINDS:
            raise VisualAidError("VISUAL_AID_PANEL_BAD_KIND", str(p["kind"]))
        if len(p["title"]) > MAX_TITLE_CHARS:
            raise VisualAidError("VISUAL_AID_TITLE_TOO_LONG", p["title"][:40])
        if len(p["source_label"]) > MAX_SOURCE_LABEL_CHARS:
            raise VisualAidError("VISUAL_AID_SOURCE_LABEL_TOO_LONG", p["source_label"])
        if not isinstance(p["items"], list) or not p["items"]:
            raise VisualAidError("VISUAL_AID_PANEL_EMPTY", p["id"])
        if len(p["items"]) > MAX_ITEMS_PER_PANEL:
            raise VisualAidError("VISUAL_AID_PANEL_TOO_MANY_ITEMS", p["id"])
        lines = 0
        for it in p["items"]:
            if not isinstance(it, str) or not it.strip():
                raise VisualAidError("VISUAL_AID_ITEM_NOT_TEXT", p["id"])
            if len(it) > MAX_ITEM_CHARS:
                raise VisualAidError("VISUAL_AID_ITEM_TOO_LONG", it[:40])
            for q in WESTERN_QUOTES:
                if q in it:
                    raise VisualAidError("VISUAL_AID_VERBATIM_QUOTE",
                                         "渲染文本不得含直接引语标记：{}".format(it[:40]))
            for m in CJK_QUOTE_SPAN.finditer(it):
                if len(m.group(1)) > MAX_CJK_QUOTE_CHARS:
                    raise VisualAidError("VISUAL_AID_LONG_QUOTE",
                                         "『』强调片段过长（{} 字）".format(len(m.group(1))))
            lines += len(_wrap(it))
        if lines > MAX_WRAPPED_LINES_PER_PANEL:
            raise VisualAidError("VISUAL_AID_PANEL_TOO_DENSE", "{} 行数 {}".format(p["id"], lines))
    # 外部素材 / 禁止资产（递归扫描键与文本）
    for k in _walk_keys(spec):
        if k in EXTERNAL_KEYS:
            raise VisualAidError("VISUAL_AID_EXTERNAL_ASSET", "spec 不得含字段 {}".format(k))
    for path, s in _walk_strings(spec):
        for aid in FORBIDDEN_ASSET_IDS:
            if aid in s:
                raise VisualAidError("VISUAL_AID_FORBIDDEN_ASSET", "{} 出现在 {}".format(aid, path))
        if s.lower().startswith("http"):
            raise VisualAidError("VISUAL_AID_EXTERNAL_ASSET", "spec 不得含 URL：{}".format(path))
    return {"schema": SCHEMA, "panels": [p["id"] for p in panels], "panel_count": len(panels),
            "spec_sha256": spec_sha256(spec), "rendered_text_lines": _panel_lines(spec)}


def _wrap(text: str, cols: int = WRAP_COLS) -> list:
    """CJK/拉丁混排折行：优先按空格断词，超宽 token 按字符断。"""
    out = []
    for para in str(text).split("\n"):
        if not para:
            out.append("")
            continue
        if len(para) <= cols:
            out.append(para)
            continue
        buf = ""
        for tok in re.findall(r"\S+\s*|\s+", para):
            while len(tok) > cols:
                if buf:
                    out.append(buf.rstrip())
                    buf = ""
                out.append(tok[:cols])
                tok = tok[cols:]
            if len(buf) + len(tok) <= cols:
                buf += tok
            else:
                if buf.strip():
                    out.append(buf.rstrip())
                buf = tok.lstrip()
        if buf.strip():
            out.append(buf.rstrip())
    return out or [""]


def _panel_lines(spec: dict) -> dict:
    return {p["id"]: {"title": p["title"], "lines": [l for it in p["items"] for l in _wrap(it)],
                      "source_label": p["source_label"]} for p in spec["panels"]}


# ----------------------------------------------------------------- 从冻结计划确定性编译
_PANEL_KIND = {"P1": "ladder", "P2": "cards", "P3": "positions"}
_SOURCE_LABEL = {"P1": "来源：本片 S05 旁白", "P2": "来源：Crossref 记录（DOI 已核验）",
                 "P3": "来源：本片 S06/S07 旁白（转述）"}


def compile_from_plan_item(item: dict) -> dict:
    """把冻结素材计划中的 `C_self_made_spec` **逐字**转成 spec（不新增事实、不改写措辞）。"""
    c = (item or {}).get("C_self_made_spec")
    if not isinstance(c, dict) or not c.get("panels"):
        raise VisualAidError("VISUAL_AID_PLAN_ITEM_INVALID", "计划条目缺少 C_self_made_spec.panels")
    panels, sources = [], []
    for p in c["panels"]:
        pid = str(p.get("id") or "")
        kind = _PANEL_KIND.get(pid)
        if kind is None:
            raise VisualAidError("VISUAL_AID_PLAN_ITEM_INVALID", "未知 panel id {}".format(pid))
        items = [str(x) for x in (p.get("content") or [])]
        if not items:
            raise VisualAidError("VISUAL_AID_PLAN_ITEM_INVALID", "{} 无 content".format(pid))
        src = "；".join(str(x) for x in (p.get("fact_sources") or []))
        if not src:
            raise VisualAidError("VISUAL_AID_PLAN_ITEM_INVALID", "{} 无 fact_sources".format(pid))
        panels.append({"id": pid, "title": str(p.get("title") or pid), "kind": kind,
                       "items": items, "source": src, "source_label": _SOURCE_LABEL[pid],
                       "pos": p.get("pos")})
        sources.append(src)
    spec = {"schema": SCHEMA, "layout": "ladder_cards_positions", "panels": panels,
            "no_external_assets": True, "forbid_verbatim_quotes": True,
            "origin": {"compiled_from": "material_plan.C_self_made_spec",
                       "panel_ids": [p["id"] for p in panels]},
            "sources": sources,
            "must_not": [str(x) for x in (c.get("must_not") or [])]}
    verify_spec(spec)
    return spec


# ----------------------------------------------------------------- 渲染（PIL，无 ffmpeg）
def render_overlay(spec: dict, out_png: Path, size=(1920, 1080), font_path=DEFAULT_FONT,
                   expected_font_sha256: str | None = None, font_size=30,
                   title_size=38) -> dict:
    """把 spec 渲染成整幅 RGBA 叠加层 PNG；返回审计证据。fail-closed。"""
    from PIL import Image, ImageDraw, ImageFont

    info = verify_spec(spec)
    fp = Path(font_path)
    if not fp.is_file():
        raise VisualAidError("VISUAL_AID_FONT_MISSING", str(fp))
    font_sha = _file_sha(fp)
    if expected_font_sha256 and font_sha != expected_font_sha256:
        raise VisualAidError("VISUAL_AID_FONT_MISMATCH",
                             "字体 sha256 {} != 期望 {}".format(font_sha, expected_font_sha256))
    w, h = size
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # 版式按画布高度**等比缩放**（对任意分辨率稳健；1080p 时 scale=1）
    s = h / 1080.0
    font_size = max(10, int(round(font_size * s)))
    title_size = max(12, int(round(title_size * s)))
    pad = max(6, int(round(26 * s)))
    y0 = int(round(150 * s))
    indent = max(4, int(round(34 * s)))
    f_title = ImageFont.truetype(str(fp), title_size)
    f_body = ImageFont.truetype(str(fp), font_size)
    f_small = ImageFont.truetype(str(fp), max(8, int(font_size * 0.72)))
    safe_bottom = int(h * SAFE_BOTTOM_FRACTION)
    # 版式：P1 左半，P2/P3 右半上下叠放
    left_x, left_w = max(8, int(round(60 * s))), int(w * 0.42)
    right_x, right_w = left_x + left_w + max(8, int(round(40 * s))), w - (left_x + left_w
                                                                          + max(8, int(round(40 * s)))) - max(8, int(round(60 * s)))
    box_layout = {"P1": (left_x, y0, left_w), "P2": (right_x, y0, right_w),
                  "P3": (right_x, h // 2 + int(round(20 * s)), right_w)}
    panels_out, max_bottom = [], 0
    for p in spec["panels"]:
        x, y, pw = box_layout.get(p["id"], (left_x, 150, left_w))
        lines = [l for it in p["items"] for l in _wrap(it)]
        line_h = font_size + max(4, int(round(12 * s)))
        content_h = (title_size + max(6, int(round(18 * s))) + line_h * len(lines)
                     + max(8, int(round(26 * s))) + (font_size * 0.72 + max(4, int(round(10 * s)))))
        ph = int(content_h) + pad * 2
        if y + ph > safe_bottom:
            raise VisualAidError("VISUAL_AID_UNSAFE_BOTTOM",
                                 "{} 底部 {} > 安全区 {}".format(p["id"], y + ph, safe_bottom))
        d.rounded_rectangle([x, y, x + pw, y + ph], radius=max(4, int(round(14 * s))), fill=(12, 14, 18, 178),
                            outline=(235, 238, 245, 210), width=2)
        d.text((x + pad, y + pad - max(1, int(round(4 * s)))), p["title"], font=f_title, fill=(255, 255, 255, 255))
        cy = y + pad + title_size + max(4, int(round(14 * s)))
        if p["kind"] == "ladder":
            for i, (it, ln) in enumerate(zip(p["items"], lines)):
                focus = any(m in it for m in FOCUS_MARKERS)
                bar_x0 = x + pad + i * indent
                bar_x1 = x + pw - pad
                d.rectangle([bar_x0, cy - max(1, int(round(4 * s))), bar_x1, cy + line_h - max(2, int(round(8 * s)))],
                            fill=(246, 178, 60, 210) if focus else (58, 64, 78, 190),
                            outline=(255, 255, 255, 120), width=1)
                d.text((bar_x0 + max(3, int(round(14 * s))), cy), ln, font=f_body,
                       fill=(20, 20, 24, 255) if focus else (238, 240, 246, 255))
                cy += line_h
        else:
            for ln in lines:
                d.text((x + pad, cy), ln, font=f_body, fill=(238, 240, 246, 255))
                cy += line_h
            if p["kind"] == "positions":
                d.line([x + pad, cy + max(1, int(round(4 * s))), x + pw - pad, cy + max(1, int(round(4 * s)))],
                       fill=(120, 128, 146, 200), width=2)
                cy += max(2, int(round(8 * s)))
        d.text((x + pad, y + ph - pad - int(font_size * 0.72)), p["source_label"], font=f_small,
               fill=(176, 184, 200, 235))
        panels_out.append({"id": p["id"], "kind": p["kind"], "bbox": [x, y, pw, ph],
                           "title": p["title"], "lines": lines,
                           "source": p["source"], "source_label": p["source_label"]})
        max_bottom = max(max_bottom, y + ph)
    out_png = Path(out_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_png)
    return {"overlay_png": str(out_png), "bytes": out_png.stat().st_size,
            "sha256": _file_sha(out_png), "size": [w, h],
            "spec_sha256": info["spec_sha256"], "spec_summary": info,
            "font": {"path": str(fp), "sha256": font_sha, "size": font_size},
            "safe_bottom_px": safe_bottom, "max_panel_bottom_px": max_bottom,
            "safe_bottom_ok": max_bottom <= safe_bottom,
            "panels": panels_out,
            "rendered_text": {p["id"]: {"title": p["title"], "lines": p["lines"],
                                        "source_label": p["source_label"],
                                        "source_audit": p["source"]} for p in panels_out},
            "no_external_assets": True, "forbid_verbatim_quotes": True,
            "quote_free_verified": not any(q in s for _, s in _walk_strings(spec["panels"])
                                           for q in WESTERN_QUOTES)}


def _file_sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def textwrap_preview(spec: dict) -> str:                                  # 便于人工审阅
    return json.dumps(_panel_lines(spec), ensure_ascii=False, indent=1)
