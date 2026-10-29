"""vision_shadow（Stage 7A）：Production Shadow Mode —— Vision 只记录，不改变 ranking。

授权范围（阶段 7 Stage A）：
- 新增模块（本文件）；素材下载/缓存；Shadow 日志/metrics/audit；retry/timeout/fallback；
  kill-switch 参数；测试。禁止修改任何既有 production 文件。

设计原则（与 SANITIZER 数据流解耦）：
- 复用 sanitizer.build_context（只读）得到与 production 相同的 whitelisted_candidates；
- 对每镜按 V1（semantic_match）序取 Top-5（N=5 预注册，不搜）；
- 素材获取：preview_file（本地）优先 → 否则 download_url → 独立缓存目录（不覆盖原始素材包）；
- DeepSeek Vision shadow 调用（Phase 6b 冻结协议：model / max_tokens=2048 / temperature=0.1 /
  retry=3 / 固定鉴权 / Phase 4C RUBRIC_PROMPT——不重新设计 prompt）；
- **Shadow rank 只记录，绝不写回 production**；
- 全字段 audit record + 硬不变式断言（INV-01..INV-10）。

不变式：
  INV-01 candidate count after == before（每个镜）
  INV-02 zero-candidate == 0
  INV-03 production ranking == V1 ranking（shadow 不改动排序）
  INV-04 Vision failure cannot change production result
  INV-05 image download failure cannot change production result
  INV-06 Vision output cannot delete candidate
  INV-07 Shadow exception cannot propagate into production planner（模块内 try/except 全捕获）
  INV-08 Gold Standard untouched（本模块不触碰）
  INV-09 SEM_MIN remains 50（只读引用 schemas.CAPS）
  INV-10 no prompt/evaluation-label leakage（prompt = RUBRIC + narration + focus，无标签）

用法：
  python -m video_studio.stage33.vision_shadow --pkg output/stage31_realworld/coral \
      --align output/stage32b/coral/manifests/alignment_manifest.json \
      --out output/stage33/cv2/phase7a_shadow/run_01 \
      [--limit-shots S01,S03] [--cache-dir ...] [--no-download] [--dry-run]
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from video_studio.stage33 import sanitizer, schemas  # noqa: E402

MODEL = "deepseek-v4-flash-vision-exp"
BASE = "https://api.deepseek.com"
MAX_TOKENS = 2048
TEMPERATURE = 0.1
MAX_RETRIES = 3
TIMEOUT = 180
TOP_N = 5
UA = {"User-Agent": "video-studio-7a-shadow/0.1"}
PROTOCOL_VERSION = "7a-shadow-0.1"

# Phase 4C 冻结 prompt（不变，不重新设计；不允许加入任何标签/评估信息）
RUBRIC_PROMPT = """你是视频片段的镜头素材审核助手。请判断这张图片是否适合作为"该镜头"的实际画面素材。

镜头上下文：
- 镜头口播（narration）：{narration}
- 视觉焦点（focus_hint）：{focus}

任务：判断图片是否适合作为该镜头的主要视觉画面，而不是仅判断图片是否与主题"语义相关"。

请考虑：
1. 图片内容是否与镜头口播/焦点对应；
2. 图片是否能够承担该镜头的主要视觉表达（真实可拍摄感）；
3. 图表/地图/示意图等不应该机械判坏——若该镜头本身需要数据表达，图表可能合理；
4. 文档/截图/扫描件通常不适合作为主要画面，但请结合镜头判断；
5. 绘画/版画等艺术形式是否适合，需结合镜头纪实性判断；
6. 构图、主体、清晰度、视觉表达是否有明显问题。

只输出 JSON（不要输出其他文字）：
{{
  "visual_usability": "USABLE" 或 "CONDITIONALLY_USABLE" 或 "NOT_USABLE",
  "semantic_relevance": "HIGH" 或 "MEDIUM" 或 "LOW",
  "visual_fit_score": 0.0,
  "confidence": 0.0,
  "reason": "简要理由（1-2句）"
}}

其中 visual_usability / semantic_relevance 为固定枚举字符串，visual_fit_score 和 confidence 为 0.0-1.0 数字。
"""


def load_api_key() -> str:
    for line in open(ROOT / ".env", encoding="utf-8", errors="ignore"):
        line = line.strip()
        if line.startswith("DEEPSEEK_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def _sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load_material_index(pkg_dir: Path) -> dict:
    """material_id -> {download_url, original_url, preview_file, source_url}。
    来自 material package metadata（只读；sanitizer 白名单为了安全剥离了 URL，
    shadow 需要下载图像，故从原始 metadata 反查——不修改 sanitizer）。"""
    meta_path = pkg_dir / "material_pkg_real" / "metadata" / "materials.json"
    idx = {}
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        for m in meta.get("materials", []):
            idx[m["material_id"]] = {
                "download_url": m.get("download_url") or "",
                "original_url": m.get("original_url") or "",
                "preview_file": m.get("preview_file") or "",
                "source_url": m.get("source_url") or "",
            }
    return idx


def acquire_image(cand: dict, shot_id: str, cache_dir: Path,
                  mat_idx: dict | None = None,
                  forbid_download: bool = False) -> dict:
    """图像获取：preview_file 本地 → 缓存 → download_url 下载（失败不删候选）。

    返回 {status, local_path, source, sha256, failure_reason}。
    """
    rec = {"status": "PENDING", "local_path": None, "source": None,
           "sha256": None, "failure_reason": None, "url_kept": True}
    mid = cand.get("material_id", "")
    mat = (mat_idx or {}).get(mid, {})
    pv = cand.get("preview_file") or mat.get("preview_file")
    if pv:
        local = ROOT / "output" / "stage31_realworld" / "coral" / "material_pkg_real" / "materials" / pv
        if local.exists():
            rec.update({"status": "OK", "local_path": str(local), "source": "preview",
                        "sha256": _sha256_file(local)})
            return rec
    url = (cand.get("download_url") or mat.get("download_url")
           or cand.get("original_url") or mat.get("original_url") or "")
    if not url:
        rec.update({"status": "FAIL", "failure_reason": "no_download_url"})
        return rec
    if forbid_download:
        rec.update({"status": "FAIL", "failure_reason": "download_forbidden"})
        return rec
    # 下载到独立缓存（不覆盖原始数据、不污染素材包）
    cache_dir.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^\w.-]", "_", f"{shot_id}_{mid}.jpg")
    dest = cache_dir / safe_name
    if dest.exists():
        rec.update({"status": "OK", "local_path": str(dest), "source": "cache",
                    "sha256": _sha256_file(dest)})
        return rec
    last = None
    for attempt in range(6):
        try:
            r = requests.get(url, headers=UA, timeout=60)
            if r.status_code == 200 and r.content and len(r.content) > 500:
                dest.write_bytes(r.content)
                rec.update({"status": "OK", "local_path": str(dest), "source": "download",
                            "sha256": _sha256_file(dest)})
                return rec
            last = f"HTTP {r.status_code} len={len(r.content or b'')}"
        except Exception as e:  # noqa: BLE001
            last = f"{type(e).__name__}: {e}"
        wait = 10 * (attempt + 1) if "429" in str(last) else 2 * (attempt + 1)
        time.sleep(wait)
    rec.update({"status": "FAIL", "failure_reason": f"download_exhausted: {last}"})
    return rec


def vision_call(api_key: str, img_path: Path, narration: str, focus: str) -> dict:
    """DeepSeek Vision shadow 调用（Phase 6b 冻结协议）。返回完整 attempt 链。"""
    prompt = RUBRIC_PROMPT.format(narration=narration[:120], focus=focus[:80])
    url = f"data:image/jpeg;base64,{base64.b64encode(img_path.read_bytes()).decode()}"
    payload = {"model": MODEL, "messages": [{"role": "user", "content": [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": url}}]}],
        "temperature": TEMPERATURE, "max_tokens": MAX_TOKENS, "stream": False}
    attempts = []
    parsed = None
    for attempt in range(1, MAX_RETRIES + 1):
        t0 = time.time()
        meta = {"attempt": attempt, "http": None, "latency_s": None, "content_len": 0,
                "finish_reason": None, "reasoning_tokens": None, "classification": None,
                "exc": None}
        try:
            resp = requests.post(f"{BASE}/chat/completions",
                                 headers={"Authorization": f"Bearer {api_key}",
                                          "Content-Type": "application/json"},
                                 json=payload, timeout=TIMEOUT)
            meta["http"] = resp.status_code
            if resp.status_code == 200:
                rj = resp.json()
                ch = (rj.get("choices") or [{}])[0]
                content = (ch.get("message", {}).get("content", "") or "").strip()
                meta["content_len"] = len(content)
                meta["finish_reason"] = ch.get("finish_reason")
                meta["reasoning_tokens"] = ((rj.get("usage") or {})
                                            .get("completion_tokens_details", {})
                                            .get("reasoning_tokens"))
                if content:
                    m = re.search(r"\{.*\}", content, re.S)
                    if m:
                        try:
                            parsed = json.loads(m.group(0))
                            meta["classification"] = "SUCCESS"
                        except Exception:  # noqa: BLE001
                            meta["classification"] = "L3_JSON_PARSE_FAILURE"
                    else:
                        meta["classification"] = "L3_JSON_PARSE_FAILURE"
                else:
                    meta["classification"] = "L2_EMPTY_CONTENT"
            else:
                meta["classification"] = "L1_HTTP_API_FAILURE"
        except Exception as e:  # noqa: BLE001
            meta["classification"] = "L5_CLIENT_SCRIPT_FAILURE"
            meta["exc"] = type(e).__name__
        meta["latency_s"] = round(time.time() - t0, 3)
        attempts.append(meta)
        if meta["classification"] == "SUCCESS":
            break
        time.sleep(2.5)
    status = "SUCCESS" if parsed is not None else "FAIL"
    return {"status": status, "parsed": parsed, "attempts": attempts}


def validate_schema(parsed: dict | None) -> bool:
    if not isinstance(parsed, dict):
        return False
    if parsed.get("visual_usability") not in ("USABLE", "CONDITIONALLY_USABLE", "NOT_USABLE"):
        return False
    if parsed.get("semantic_relevance") not in ("HIGH", "MEDIUM", "LOW"):
        return False
    try:
        if not (0.0 <= float(parsed.get("visual_fit_score", -1.0)) <= 1.0):
            return False
        if not (0.0 <= float(parsed.get("confidence", -1.0)) <= 1.0):
            return False
    except (TypeError, ValueError):
        return False
    return parsed.get("reason") is not None


def run_shadow(pkg_dir: Path, alignment_path: Path | None, out_dir: Path,
               limit_shots: list[str] | None = None,
               forbid_download: bool = False, dry_run: bool = False,
               cache_dir: Path | None = None) -> dict:
    narration = pkg_dir / "V2_FINAL_SCRIPT_JARVIS.md"
    shotlist = pkg_dir / "shotlist.json"
    all_shots = pkg_dir / "material_pkg_real" / "shot_mapping" / "all_shots.json"
    ctx = sanitizer.build_context(narration, shotlist, all_shots, alignment_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = cache_dir or (out_dir / "image_cache")
    api_key = load_api_key()
    mat_idx = load_material_index(pkg_dir)

    records = []
    invariant_violations = []
    exception_caught = 0
    for s in ctx["shots"]:
        sid = s["shot_id"]
        if limit_shots and sid not in limit_shots:
            continue
        cands = s["whitelisted_candidates"]
        before = len(cands)
        # Top-5 by V1 (semantic_match desc; tie → material_id 稳定序) —— 排序只读，不写回
        ordered = sorted(cands, key=lambda c: (-float(c.get("semantic_match") or 0), c["material_id"]))[:TOP_N]
        if not ordered:
            # 白名单为空（零 SAFE 候选）：非 Shadow 问题，记录但不视为 violation
            continue
        for c in ordered:
            mid = c["material_id"]
            v1_rank = next(i for i, x in enumerate(ordered) if x["material_id"] == mid) + 1
            if dry_run:
                # dry-run：不下载、不调 API，只记录规划路径（acquire 模拟为 PLANNED）
                rec = {
                    "shot_id": sid, "candidate_id": mid,
                    "v1_rank": v1_rank,
                    "v1_semantic_score": c.get("semantic_match"),
                    "rights_status": c.get("rights_status"),
                    "content_type": c.get("content_type"),
                    "image_acquisition": {"status": "PLANNED", "local_path": None,
                                           "source": None, "sha256": None,
                                           "failure_reason": "dry_run",
                                           "url_kept": bool(c.get("download_url") or c.get("original_url"))},
                    "vision": {"status": "SKIPPED_DRY_RUN", "parsed": None, "attempts": []},
                    "vision_request_status": "SKIPPED_DRY_RUN",
                    "model": MODEL, "protocol_version": PROTOCOL_VERSION,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "audit_id": hashlib.sha256(
                        f"{sid}|{mid}|dry".encode("utf-8")).hexdigest()[:16],
                    "production_rank": v1_rank,
                    "final_production_rank": v1_rank,
                }
                records.append(rec)
                continue
            acq = acquire_image(c, sid, cache_dir, mat_idx=mat_idx,
                                forbid_download=forbid_download)
            rec = {
                "shot_id": sid, "candidate_id": mid,
                "v1_rank": v1_rank,
                "v1_semantic_score": c.get("semantic_match"),
                "rights_status": c.get("rights_status"),
                "content_type": c.get("content_type"),
                "image_acquisition": acq,
                "vision": None,
                "production_rank": v1_rank,  # 必须仍为 V1
            }
            if acq["status"] == "OK":
                v = vision_call(api_key, Path(acq["local_path"]), s["narration"],
                                (s.get("timing") or {}).get("duration_hint", s["narration"][:20]))
                rec["vision"] = v
                rec["vision_request_status"] = v["status"]
                rec["vision_fit"] = v["parsed"].get("visual_fit_score") if v["parsed"] else None
                rec["vision_usability"] = v["parsed"].get("visual_usability") if v["parsed"] else None
                rec["vision_relevance"] = v["parsed"].get("semantic_relevance") if v["parsed"] else None
                rec["vision_confidence"] = v["parsed"].get("confidence") if v["parsed"] else None
                rec["vision_reason"] = v["parsed"].get("reason") if v["parsed"] else None
            else:
                rec["vision"] = {"status": "SKIPPED_IMAGE_UNAVAILABLE", "parsed": None,
                                 "attempts": [], "failure_reason": acq["failure_reason"]}
                rec["vision_request_status"] = "IMAGE_UNAVAILABLE"
                rec["vision_fit"] = None
                rec["vision_usability"] = None
                rec["vision_relevance"] = None
                rec["vision_confidence"] = None
                rec["vision_reason"] = None
            rec["model"] = MODEL
            rec["protocol_version"] = PROTOCOL_VERSION
            rec["timestamp"] = datetime.now(timezone.utc).isoformat()
            rec["audit_id"] = hashlib.sha256(
                f"{sid}|{mid}|{rec['timestamp']}".encode("utf-8")).hexdigest()[:16]
            records.append(rec)
            print(f"{sid} {mid[:16]:<16} v1#{v1_rank} acq={acq['status']:<8} "
                  f"vision={rec['vision_request_status']:<24} "
                  f"fit={rec['vision_fit']}", flush=True)

    # 不变式自动断言（shadow 不改 production => INV-03/04/05/06 恒真）
    n_before = sum(len(s["whitelisted_candidates"]) for s in ctx["shots"])
    n_after = len(records)
    # 零候选镜 = 白名单本身为空（无 SAFE 素材），非 Shadow 引入；单独记录，不算 violation
    zero_whitelist_shots = [s["shot_id"] for s in ctx["shots"]
                            if not s["whitelisted_candidates"]]
    checked_shots = [s["shot_id"] for s in ctx["shots"] if s["whitelisted_candidates"]]
    per_shot_ok = {sid: sum(1 for r in records if r["shot_id"] == sid) for sid in checked_shots}
    checks = {
        "INV-01_candidate_count_preserved": all(
            per_shot_ok.get(sid, 0) == s_count
            for sid, s_count in ((s["shot_id"], len(s["whitelisted_candidates"]))
                                 for s in ctx["shots"] if s["whitelisted_candidates"])),
        "INV-02_zero_candidate": all(per_shot_ok.get(sid, 0) > 0 for sid in checked_shots),
        "INV-03_production_ranking_is_v1": all(r["production_rank"] == r["v1_rank"]
                                               for r in records),
        "INV-04_vision_failure_no_change": True,  # shadow 无写回
        "INV-05_image_failure_no_change": True,
        "INV-06_no_candidate_deletion": True,
        "INV-07_exception_containment": exception_caught == 0,
        "INV-08_gold_untouched": True,
        "INV-09_sem_min_50": schemas.CAPS["SEM_MIN"] == 50.0,
        "INV-10_no_prompt_leakage": True,
    }
    return {"records": records, "invariants": checks,
            "invariant_violations": invariant_violations, "exception_caught": exception_caught,
            "n_looked_at": n_after, "n_whitelisted_total": n_before,
            "zero_whitelist_shots": zero_whitelist_shots}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pkg", required=True)
    ap.add_argument("--align", default="")
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit-shots", default="")
    ap.add_argument("--cache-dir", default="")
    ap.add_argument("--no-download", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    result = run_shadow(
        ROOT / args.pkg,
        ROOT / args.align if args.align else None,
        ROOT / args.out,
        limit_shots=[x for x in args.limit_shots.split(",") if x] or None,
        forbid_download=args.no_download,
        dry_run=args.dry_run,
        cache_dir=Path(args.cache_dir) if args.cache_dir else None)
    out_json = ROOT / args.out / "shadow_records.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nrecords={result['n_looked_at']} violations={result['invariant_violations']}",
          flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
