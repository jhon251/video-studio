"""sanitizer：上游只读输入 → 白名单化 LLM context（安全边界第一道门）。

规则（硬）：
- 候选只来自 3.1.4 Material Package（shot_mapping/all_shots.json 各镜 primary/alternatives）；
- 只保留 rights_status∈{SAFE} 或 {CONDITIONAL 且 commercial_use==true}，且 semantic_match>=50；
- UNKNOWN/UNSAFE/sem<50 绝不进入 context，也绝不进入白名单 registry；
- 剥离一切 URL / 文件路径；LLM 只见 material_id + 少量元数据。
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from video_studio.stage33 import schemas

ROOT = Path(__file__).resolve().parents[3]


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _norm_text(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def parse_narration(text: str) -> list[dict]:
    """按【Sxx】切镜（与 3.2b 同口径：跳过标题/空行，剥离标记）。"""
    items, cur = [], None
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s.startswith(">"):
            continue
        import re
        m = re.match(r"^【(S\d+)】(.*)$", s)
        if m:
            cur = {"shot_id": m.group(1), "text": m.group(2).strip()}
            items.append(cur)
        elif cur is not None:
            cur["text"] = (cur["text"] + s).strip()
    return items


def _semantic_match(c: dict) -> float:
    """3.1.4 口径：semantic_match 位于 score_detail.semantic_match（match_score 是加权总分）。"""
    v = c.get("semantic_match")
    if v is None:
        v = (c.get("score_detail") or {}).get("semantic_match")
    return float(v or 0)


_HTML_RE = __import__("re").compile(r"<[^>]+>")
_URL_RE = __import__("re").compile(r"https?://\S+")


def _clean_desc(s: str) -> str:
    s = _HTML_RE.sub(" ", s or "")
    s = __import__("re").sub(r"<[^>]*$", " ", s)   # 包内被截断的未闭合标签残片
    s = __import__("re").sub(r"[<>]", " ", s)      # 任何残留尖括号
    s = _URL_RE.sub(" ", s)
    return __import__("re").sub(r"\s+", " ", s).strip()[:200]


def _pick_fields(c: dict) -> dict:
    """白名单候选的最小字段（无 URL、无文件路径、无 HTML）。"""
    return {
        "material_id": c.get("material_id"),
        "content_type": c.get("content_type", "image"),
        "rights_status": c.get("rights_status", ""),
        "semantic_match": _semantic_match(c),
        "match_type": c.get("match_type", ""),
        "visual_description": _clean_desc(c.get("visual_description")),
        "resolution": c.get("resolution", ""),
    }


def build_whitelist(all_shots: dict) -> tuple[dict, dict]:
    """返回 (whitelist_by_shot, registry)。registry: material_id → {shot_id, rights_status, semantic_match, content_type}。"""
    wl, registry = {}, {}
    for sid, rec in all_shots.get("shots", {}).items():
        cands = []
        for c in ([rec.get("primary")] if rec.get("primary") else []) + list(
                rec.get("alternatives") or []):
            if not c:
                continue
            rs = c.get("rights_status", "")
            cu = bool(c.get("commercial_use"))
            sem = _semantic_match(c)
            if (rs == "SAFE" or (rs == "CONDITIONAL" and cu)) and sem >= schemas.CAPS["SEM_MIN"]:
                f = _pick_fields(c)
                cands.append(f)
                registry[f["material_id"]] = {
                    "shot_id": sid, "rights_status": rs, "semantic_match": sem,
                    "content_type": f["content_type"]}
        wl[sid] = cands
    return wl, registry


def build_context(narration_path: Path, shotlist_path: Path,
                  all_shots_path: Path, alignment_path: Path | None) -> dict:
    """构造 sanitized context（给 director 的 prompt 原料）+ 输入 SHA。"""
    narration = _norm_text(narration_path)
    shots = parse_narration(narration)
    shotlist = json.loads(shotlist_path.read_text(encoding="utf-8"))
    scenes = {s["scene_id"]: s for s in shotlist.get("scenes", [])}
    all_shots = json.loads(all_shots_path.read_text(encoding="utf-8"))
    wl, registry = build_whitelist(all_shots)

    timing = {}
    if alignment_path and alignment_path.exists():
        al = json.loads(alignment_path.read_text(encoding="utf-8"))
        timing = {s["shot_id"]: {"start": s["start"], "end": s["end"],
                                 "duration": s["adopted_duration"]}
                  for s in al["shots"]}

    # 安全断言：白名单内绝无 UNKNOWN/UNSAFE/sem<50
    for sid, cands in wl.items():
        for c in cands:
            assert c["rights_status"] in ("SAFE", "CONDITIONAL"), "whitelist violated"
            assert c["semantic_match"] >= schemas.CAPS["SEM_MIN"], "whitelist violated"

    ctx_shots = []
    for sh in shots:
        sid = sh["shot_id"]
        sc = scenes.get(sid, {})
        ctx_shots.append({
            "shot_id": sid,
            "narration": sh["text"],
            "shot_role": sc.get("role", ""),
            "duration_hint": sc.get("duration_hint", ""),
            "timing": timing.get(sid),
            "whitelisted_candidates": wl.get(sid, []),
        })
    inputs = {
        "narration_sha": sha256_text(narration),
        "shotlist_sha": hashlib.sha256(shotlist_path.read_bytes()).hexdigest(),
        "package_sha": hashlib.sha256(all_shots_path.read_bytes()).hexdigest(),
        "alignment_sha": (hashlib.sha256(alignment_path.read_bytes()).hexdigest()
                          if alignment_path and alignment_path.exists() else ""),
    }
    return {"narration": narration, "shots": ctx_shots, "registry": registry,
            "inputs": inputs}
