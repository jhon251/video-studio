"""graphics（v3-mvp）：锚点渲染原语（PIL，确定性）。

只提供原语：色块/圆角遮罩/锚点词/合成。**不做"模板"**——版式由 realizer
按 statement 逐帧组装。
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[3]
FONT_PATH = ROOT / "output" / "production_002" / "build_v2" / "msyh.ttc"
W, H = 1920, 1080


def hex_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_PATH), size)


def color_canvas(rgb: tuple[int, int, int], size=(W, H)) -> Image.Image:
    return Image.new("RGB", size, rgb)


def rounded_mask(size: tuple[int, int, int, int], radius: int,
                 fill: tuple[int, int, int], alpha: int = 255) -> Image.Image:
    """圆角矩形层（RGBA）。"""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(size, radius=radius, fill=(*fill, alpha))
    return img


def anchor_text(text: str, size: int, color: tuple[int, int, int],
                stroke: int = 0, stroke_color: tuple[int, int, int] = (0, 0, 0),
                anchor_pos: tuple[int, int] = (W // 2, H // 2)) -> tuple[Image.Image, tuple[int, int, int, int]]:
    """锚点词层（RGBA）：anchor_pos 为文字中心点；返回 (layer, bbox)。"""
    f = font(size)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    bb = d.textbbox((0, 0), text, font=f, stroke_width=stroke)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    x, y = anchor_pos[0] - tw // 2, anchor_pos[1] - th // 2
    d.text((x - bb[0], y - bb[1]), text, font=f, fill=(*color, 255),
           stroke_width=stroke, stroke_fill=(*stroke_color, 255))
    return layer, (x, y, x + tw, y + th)


def compose(base: Image.Image, layers: list[tuple[Image.Image, int]]) -> Image.Image:
    """合成：base RGB + [(RGBA layer, alpha 0-255), ...]（alpha 整数）。"""
    img = base.convert("RGBA")
    for lay, a in layers:
        if a <= 0:
            continue
        if a < 255:
            lay = lay.copy()
            lay.putalpha(lay.getchannel("A").point(lambda v: v * a // 255))
        img = Image.alpha_composite(img, lay)
    return img.convert("RGB")
