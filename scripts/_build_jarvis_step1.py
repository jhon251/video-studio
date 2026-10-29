"""JARVIS 成片构建 · 步骤1：提取口播稿 + 分镜元数据（只读 2.x 蓝图，不改 2.x 代码）。"""
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "production_002"
BUILD = OUT / "build"
BUILD.mkdir(parents=True, exist_ok=True)
(BUILD / "txt").mkdir(exist_ok=True)
(BUILD / "wav").mkdir(exist_ok=True)

pkg = json.loads((OUT / "final_production_plan.json").read_text(encoding="utf-8"))
scenes = pkg["plans"]["bilibili"]["plan"]["scenes"]

# 背景色（按 role 区分，纯色卡片，无素材依赖）
BG = {
    "hook": "0x1a1a2e", "transition": "0x16213e", "body": "0x0f3460",
    "fact": "0x1b4332", "gap": "0x7a5c00", "conclusion": "0x2d1b4e",
    "conclusion_first": "0x2d1b4e",
}


def clean(text: str) -> str:
    t = re.sub(r"（证据 [^）]*）", "", text)
    t = re.sub(r"\[EDIT[^\]]*\]", "", t)
    t = re.sub(r"\[待补[^\]]*\]", "", t)
    t = t.replace("；离谱但真实，备选开场：", "；")
    t = re.sub(r"离谱但真实，", "", t)
    t = t.replace("～", "")
    return re.sub(r"\s+", " ", t).strip()


def wrap(text: str, width: int = 18) -> str:
    """中文按 width 字换行，供 ffmpeg drawtext textfile 使用。"""
    lines, cur = [], ""
    for ch in text:
        cur += ch
        if len(cur) >= width and (ch in "。！？；，、" or len(cur) >= width + 2):
            lines.append(cur)
            cur = ""
    if cur:
        lines.append(cur)
    return "\n".join(lines)


manifest = []
for s in scenes:
    n = clean(s["script_text"])
    sid = s["scene_id"]
    txtfile = BUILD / "txt" / f"{sid}.txt"
    txtfile.write_text(wrap(n, 18), encoding="utf-8")
    manifest.append({
        "scene_id": sid, "role": s["role"], "beat": s["beat"],
        "visual_target": s["visual_target"],
        "emphasis": s["subtitle_emphasis"],
        "duration_hint": s["duration_hint"],
        "bg": BG.get(s["role"], "0x101010"),
        "narration": n,
        "txt": str(txtfile.relative_to(BUILD)),
    })

(BUILD / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
voiced = [m for m in manifest if m["narration"] and m["role"] not in ("fact", "gap")]
print(f"manifest: {len(manifest)} 镜 | 口播镜 {len(voiced)} | txt 已写入 build/txt/")
print("口播镜清单:", ", ".join(m["scene_id"] for m in voiced))
