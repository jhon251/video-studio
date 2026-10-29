"""Stage 10: Long-form (8-12 min) real E2E — text hardened + materials + CV-2
+ (if assets available) real MP4 render via existing stage32b vo/assemble chain.

Chain:
  Topic -> Research (hardened LLM) -> Reasoning (hardened LLM) -> Narrative ->
  Script 8-12min (hardened LLM, ~24-36 shots) -> Material Planning ->
  Commons retrieval -> CV-2 V1->Top-5->Vision rerank->V1 fallback (FROZEN
  primitives) -> Final Production Plan -> render (F5-TTS + Ken Burns + concat)

CV-2 is strictly frozen: only calls vision_controlled.vision_call /
asset_cache.acquire_asset. No algorithm change.
"""
from __future__ import annotations

import base64
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from video_studio.core.env import load_env  # noqa: E402
from video_studio.stage33 import text_hardening as th  # noqa: E402

UA = {"User-Agent": "video-studio-stage10/0.1"}
TARGET_SECONDS = (8 * 60, 12 * 60)
CN_CHARS_PER_SEC = 4.0  # avg chinese narration chars per second (spoken)
SHOTS_TARGET_MIN = 24
SHOTS_TARGET_MAX = 36

# ---------- schemas (Stage 9 B: simplified + explicit field names) ----------
SCHEMA_RESEARCH = {
    "type": "object",
    "properties": {
        "facts": {"type": "array", "items": {"type": "string"}},
        "sources": {"type": "array", "items": {"type": "string"}},
        "timeline": {"type": "array", "items": {"type": "string"}},
        "summary": {"type": "string"}},
    "required": ["facts", "summary"]}

SCHEMA_REASONING = {
    "type": "object",
    "properties": {
        "causal_chain": {"type": "array", "items": {"type": "string"}},
        "assumptions": {"type": "array", "items": {"type": "string"}},
        "uncertainties": {"type": "array", "items": {"type": "string"}},
        "summary": {"type": "string"}},
    "required": ["causal_chain", "summary"]}

SCHEMA_SCRIPT_BATCH = {
    "type": "object",
    "properties": {
        "narration_line": {"type": "string"},
        "summary": {"type": "string"}},
    "required": ["narration_line", "summary"]}

SCHEMA_SHOT_PLAN = {
    "type": "object",
    "properties": {
        "shots": {"type": "array", "items": {"type": "object",
            "properties": {"shot_id": {"type": "string"}, "narration": {"type": "string"},
                           "role": {"type": "string"}},
            "required": ["shot_id", "narration", "role"]}},
        "summary": {"type": "string"}},
    "required": ["shots", "summary"]}

PROMPT_STRICT = (
    "你是视频科研文案研究员。只输出一个 JSON 对象：禁止 Markdown、禁止解释、禁止任何 JSON 以外的文字。\n"
    "字段（严格使用这些名字）：\n"
    "  \"facts\": 字符串数组，每条为一句话\n"
    "  \"sources\": 字符串数组（来源名称）\n"
    "  \"timeline\": 字符串数组\n"
    "  \"summary\": 字符串\n"
    "主题：{topic}")

PROMPT_REASON = (
    "你是视频推演分析师。只输出 JSON 对象（无 Markdown 无解释）。字段：\n"
    "  \"causal_chain\": 字符串数组（因果/推演链）\n"
    "  \"assumptions\": 字符串数组\n"
    "  \"uncertainties\": 字符串数组\n"
    "  \"summary\": 字符串\n"
    "主题：{topic}")

PROMPT_LINE = (
    "你是视频节目旁白作者。只输出 JSON 对象（无 Markdown 无解释）。字段：\n"
    "  \"narration_line\": 字符串（40-90 个汉字，一段完整旁白，有信息量，不重复）\n"
    "  \"summary\": 字符串\n"
    "主题：{topic}\n上一段：{prev}\n角色：{role}")


def load_key() -> str:
    for line in open(ROOT / ".env", encoding="utf-8", errors="ignore"):
        line = line.strip()
        if line.startswith("DEEPSEEK_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def tts_seconds(text: str) -> float:
    return round(len(text) / CN_CHARS_PER_SEC, 1)


def research_stage(topic, out, model="deepseek-chat"):
    res = th.hardened_call(model, "你是视频科研文案研究员。",
                           PROMPT_STRICT.replace("{topic}", topic), SCHEMA_RESEARCH,
                           repair_prompt=PROMPT_STRICT.replace("{topic}", topic))
    out.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    return res


def reasoning_stage(topic, out, model="deepseek-chat"):
    res = th.hardened_call(model, "你是视频推演分析师。",
                           PROMPT_REASON.replace("{topic}", topic), SCHEMA_REASONING,
                           repair_prompt=PROMPT_REASON.replace("{topic}", topic))
    out.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    return res


def script_stage(topic, out, model="deepseek-chat", n_lines=30,
                 take_every=1) -> list[dict]:
    """Generate narration lines one by one (hardened, honest, no repetition
    control beyond prompt). Returns [{line, role}]."""
    lines = []
    roles = ["hook", "fact", "tech", "speculation", "counter", "bigger", "hypo",
             "open", "fact", "tech", "speculation", "counter", "bigger", "hypo",
             "open", "fact", "tech", "speculation", "counter", "bigger", "hypo",
             "open", "fact", "tech", "speculation", "counter", "bigger", "hypo",
             "open", "fact"]
    prev = ""
    for i in range(n_lines):
        role = roles[i % len(roles)]
        user = PROMPT_LINE.replace("{topic}", topic).replace("{prev}", prev[:80]).replace("{role}", role)
        r = th.hardened_call(model, "你是视频节目旁白作者。", user, SCHEMA_SCRIPT_BATCH,
                             repair_prompt=user, temperature=0.7)
        line = (r.get("data") or {}).get("narration_line", "")
        rec = {"index": i + 1, "role": role, "line": line, "status": r["status"],
               "fallback": r.get("fallback", False), "attempts": r.get("attempts")}
        lines.append(rec)
        prev = line or prev
        print(f"  L{i+1:02d} [{role}] {line[:36]}... ({r['status']})", flush=True)
        time.sleep(0.4)
    (out / "script_lines.json").write_text(json.dumps(lines, ensure_ascii=False, indent=2),
                                           encoding="utf-8")
    return lines


# ---------- Commons retrieval (WT source same as frozen pool) ----------
def commons_search(query: str, limit: int = 6) -> list[dict]:
    url = "https://commons.wikimedia.org/w/api.php"
    params = {"action": "query", "format": "json", "generator": "search",
              "gsrsearch": query, "gsrnamespace": 6, "gsrlimit": limit,
              "prop": "imageinfo", "iiprop": "url|size", "iiurlwidth": 640}
    try:
        r = requests.get(url, headers=UA, params=params, timeout=40)
        pages = r.json().get("query", {}).get("pages", {})
        out = []
        for pid, pg in pages.items():
            ii = (pg.get("imageinfo") or [{}])[0]
            out.append({"title": pg.get("title", ""), "thumburl": ii.get("thumburl") or "",
                        "url": ii.get("descriptionurl") or "", "size": ii.get("width", 0)})
        return out
    except Exception:  # noqa: BLE001
        return []


QUERY_BY_ROLE = {
    "hook": "future technology AGI abstract", "fact": "AI history timeline",
    "tech": "large language model neural network", "speculation": "automation future work",
    "counter": "robotics computer brain", "bigger": "human civilization future",
    "hypo": "artificial general intelligence concept", "open": "futuristic city technology",
}


def build_shot_plan(lines: list[dict]) -> list[dict]:
    shots = []
    for i, l in enumerate(lines):
        sid = f"S{i+1:02d}"
        shots.append({
            "shot_id": sid, "narration": l["line"], "role": l["role"],
            "material_query": QUERY_BY_ROLE.get(l["role"], "future technology"),
            "tts_est_s": tts_seconds(l["line"]),
            "source_line": l["index"],
        })
    return shots


def retrieve_for_shots(shots: list[dict], out_dir: Path) -> dict:
    all_shots = {}
    for sh in shots:
        cands = commons_search(sh["material_query"], limit=6)
        all_shots[sh["shot_id"]] = {"query": sh["material_query"],
                                    "role": sh["role"], "requested": cands}
    (out_dir / "candidates.json").write_text(
        json.dumps({"shots": all_shots}, ensure_ascii=False, indent=2), encoding="utf-8")
    return all_shots


# ---------- CV-2 (FROZEN primitives) ----------
def cv2_rerank(shots: list[dict], cands: dict, out_dir: Path) -> dict:
    from video_studio.stage33.asset_cache import acquire_asset
    from video_studio.stage33.vision_controlled import vision_call, load_api_key

    api_key = load_api_key()
    cache_dir = ROOT / "output/stage33/stage10_long_form/asset_cache"
    per_shot = []
    vision_calls = 0
    successes = 0
    cache_hits = 0
    fallbacks = 0
    for sh in shots:
        sid = sh["shot_id"]
        req = cands.get(sid, {}).get("requested", [])
        picks = [c for c in req if c.get("thumburl")][:5]
        if not picks:
            per_shot.append({"shot_id": sid, "baseline": [], "vision": [], "final": [],
                             "fallback_reason": "no_candidate"})
            fallbacks += 1
            continue
        baseline = [{"rank": i + 1, "title": c["title"], "thumburl": c["thumburl"],
                     "url": c.get("url", "")} for i, c in enumerate(picks)]
        scored = []
        for b in baseline:
            acq = acquire_asset(cache_dir, f"{sid}_{b['rank']}", b["thumburl"],
                                preview_path=None, ext_hint="image")
            v = None
            if acq["status"] == "OK":
                v = vision_call(api_key, Path(acq["local_path"]),
                                sh["narration"], sh.get("material_query", ""))
                vision_calls += 1
                if v and v.get("parsed"):
                    successes += 1
            fit = (v or {}).get("parsed", {}).get("visual_fit_score") if v and v.get("parsed") else None
            scored.append({"rank": b["rank"], "title": b["title"], "vision_fit": fit,
                           "vision_success": bool(v and v.get("parsed")),
                           "acq": acq["status"], "cache_hit": acq["cache_hit"]})
            if acq["cache_hit"]:
                cache_hits += 1
            if not (v and v.get("parsed")):
                fallbacks += 1

        def sk(x):
            return (-(x["vision_fit"] if x["vision_fit"] is not None else -1.0), x["rank"])
        vision_top = sorted(scored, key=sk)
        final = [{"rank": i + 1, "title": x["title"], "vision_fit": x["vision_fit"],
                  "rank_source": "VISION_RERANK" if x["vision_fit"] is not None else "V1_FALLBACK"}
                 for i, x in enumerate(vision_top)]
        per_shot.append({"shot_id": sid, "baseline_top_k": [c["rank"] for c in baseline],
                         "vision_top_k": [c["rank"] for c in vision_top],
                         "final_top_k": final, "candidates": scored})
    res = {"cv2_vision_calls": vision_calls, "vision_success": successes,
           "vision_success_rate": round(successes / max(vision_calls, 1), 4),
           "cache_hit": cache_hits, "fallback_events": fallbacks,
           "per_shot": per_shot}
    (out_dir / "cv2_results.json").write_text(json.dumps(res, ensure_ascii=False, indent=2),
                                              encoding="utf-8")
    return res


# ---------- Render: real MP4 via F5-TTS + Ken Burns + concat ----------
def render_mp4(shots: list[dict], cv2: dict, out_dir: Path,
               material_dir: Path | None = None, max_shots: int | None = None) -> dict:
    """Render a real MP4: per-shot image (Vision top-1) Ken Burns + F5 audio +
    concat. Uses existing stage32b/vo build_vo and ffmpeg. Returns manifest."""
    from video_studio.stage32b import vo as vo_mod

    if max_shots:
        shots = shots[:max_shots]

    # 1. narration text in 【Sxx】-per-line format for vo.build_vo
    nar_path = out_dir / "narration_formatted.txt"
    lines = [f"【{s['shot_id']}】{s['narration']}" for s in shots]
    nar_path.write_text("\n".join(lines), encoding="utf-8")

    # 2. VO (F5-TTS, real)
    t0 = time.time()
    vo_dir = out_dir / "vo"
    vo_dir.mkdir(parents=True, exist_ok=True)
    try:
        manifest = vo_mod.build_vo(nar_path, vo_dir)
    except Exception as e:  # noqa: BLE001
        return {"status": "RENDER_FAILED_VO", "error": f"{type(e).__name__}: {str(e)[:200]}",
                "elapsed_s": round(time.time() - t0, 1)}
    vo_elapsed = round(time.time() - t0, 1)

    # 3. per-shot image -> Ken Burns clip
    seg_by_shot = {}
    for seg in manifest["segments"]:
        seg_by_shot.setdefault(seg["shot_id"], []).append(seg)

    clip_dir = out_dir / "clips"
    clip_dir.mkdir(parents=True, exist_ok=True)
    FFMPEG = ROOT / "bin" / "ffmpeg.exe"
    per_shot = []
    t1 = time.time()
    for s in shots:
        sid = s["shot_id"]
        segs = seg_by_shot.get(sid, [])
        dur = round(sum(x["duration"] for x in segs if x["status"] == "OK"), 3)
        if dur < 0.5:
            dur = 4.0
        # material: Vision top-1 candidate image (download if needed via cv2 candidates)
        top = None
        for ps in cv2.get("per_shot", []):
            if ps.get("shot_id") == sid:
                top = (ps.get("final_top_k") or [{}])[0]
                break
        thumb = (top or {}).get("thumburl", "")
        img = None
        if thumb:
            try:
                r = requests.get(thumb, headers=UA, timeout=60)
                if r.status_code == 200 and len(r.content) > 500:
                    img = out_dir / "materials" / f"{sid}.jpg"
                    img.parent.mkdir(parents=True, exist_ok=True)
                    img.write_bytes(r.content)
            except Exception:  # noqa: BLE001
                img = None
        clip = clip_dir / f"{sid}.mp4"
        if img is None:
            # fallback: solid-color card with text (deterministic, NOT fake material)
            txt = out_dir / "build" / f"{sid}.txt"
            txt.parent.mkdir(parents=True, exist_ok=True)
            txt.write_text(s["narration"][:18], encoding="utf-8")
            cmd = [str(FFMPEG), "-y", "-f", "lavfi", "-i", "color=c=0x0b2e33:s=1920x1080:r=25",
                   "-vf", f"drawtext=fontfile=msyh.ttc:textfile={sid}.txt:fontsize=56:fontcolor=white", "-t", f"{dur:.3f}"]
        else:
            cmd = [str(FFMPEG), "-y", "-loop", "1", "-i", str(img), "-vf",
                   f"zoompan=z='min(1.0+0.06*on/{int(dur*25) if dur*25>1 else 1},1.20)':d={int(dur*25)}:s=1920x1080:fps=25,"
                   f"scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080",
                   "-t", f"{dur:.3f}"]
        cmd += ["-an", str(clip)]
        sub = __import__("subprocess")
        sub.run(cmd, capture_output=True, check=True)
        per_shot.append({"shot_id": sid, "duration": round(dur, 3),
                         "material": top.get("title") if top else None,
                         "clip": str(clip)})
        print(f"  clip {sid} {dur:.1f}s ({'image' if img else 'text_card'})", flush=True)
    clip_elapsed = round(time.time() - t1, 1)

    # 4. concat
    final = out_dir / "final_8_12min.mp4"
    concat_file = out_dir / "concat.txt"
    concat_file.write_text("\n".join(f"file '{c['clip'].replace(chr(92), '/')}'" for c in per_shot),
                           encoding="utf-8")
    sub = __import__("subprocess")
    sub.run([str(FFMPEG), "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
             "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p", "-an", str(final)],
            capture_output=True, check=True)
    # 5. mux audio (voiceover.wav) if exists
    vo_final = vo_dir / "voiceover.wav"
    mp4_final = out_dir / "final_8_12min.mp4"
    if vo_final.exists():
        tmp = out_dir / "final_with_audio.mp4"
        sub.run([str(FFMPEG), "-y", "-i", str(mp4_final), "-i", str(vo_final),
                 "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac",
                 "-b:a", "128k", "-shortest", str(tmp)], capture_output=True, check=True)
        if tmp.exists():
            tmp.replace(mp4_final)
    size = mp4_final.stat().st_size if mp4_final.exists() else 0
    total_dur = round(sum(c["duration"] for c in per_shot), 3)
    return {"status": "MP4_RENDERED", "file": str(mp4_final), "size_bytes": size,
            "duration_s": total_dur, "resolution": "1920x1080", "fps": 25,
            "n_shots": len(per_shot), "vo_elapsed_s": vo_elapsed,
            "clip_elapsed_s": clip_elapsed, "vo_manifest": manifest.get("total_duration"),
            "video_codec": "libx264", "audio_status": "aac (voiceover.wav)" if vo_final.exists() else "NO_AUDIO",
            "material_used": sum(1 for c in per_shot if c.get("material"))}
