# -*- coding: utf-8 -*-
"""Phase 58 / P58-1：**Pexels Videos 采集**（检索 → 下载 → 候选 payload，LLM $0）。

产出一个**视频候选 payload**（`logs/p58_video_payload.json`），与图片池同构：
  {name, path(相对项目 media/), sha256, media_type: "video", duration_s, width, height,
   license, license_class, provider, source_url, attribution}
消费方（P58-2）：editing agent 建池按后缀/`media_type` 识别视频条（ffprobe 可用性），
渲染装配分支按 `media_type` 走视频条输入（-ss/-t 裁剪 + tpad 定格 + 双 trim）。

查询表为**人工精选英文查询**（Pexels 检索英文最优；P49 语言中立只约束 name，
name = `Pexels Video <id> by <作者>`，与既有图片命名同构）。
运行: python docs/regression_2x/p58_1_acquire_videos.py
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys
import time

import requests

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
L = R / "docs" / "regression_2x" / "logs"
VID_DIR = R / "projects" / "p_3e9292101f10" / "media" / "p58_videos"

# 场景 → 英文查询（垂直切片先覆盖 8 个可实拍概念景；全片覆盖后续扩充）
QUERY_MAP = {
    "P02_1": "stack of paper documents desk",
    "P02_2": "person reading documents office",
    "P03_2": "hand writing on paper close up",
    "P04_1": "pencil writing notebook",
    "P05_2": "library bookshelves",
    "P06_2": "computer code on screen",
    "P07_2": "typing on laptop keyboard",
    "P09_3": "person walking library aisle",
}
MIN_W = 1280
MIN_DUR_S = 8.0


def main() -> int:
    from video_studio.core.env import load_env
    env = load_env(R / ".env")
    key = env.get("PEXELS_API_KEY")
    if not key:
        print("PEXELS_API_KEY 缺失 ⇒ fail-closed")
        return 1
    VID_DIR.mkdir(parents=True, exist_ok=True)
    cands, trace = [], []
    for sid, q in QUERY_MAP.items():
        try:
            r = requests.get("https://api.pexels.com/videos/search",
                             params={"query": q, "per_page": 4, "orientation": "landscape"},
                             headers={"Authorization": key}, timeout=30)
            r.raise_for_status()
            items = r.json().get("videos") or []
        except Exception as e:                                              # noqa: BLE001
            trace.append({"scene": sid, "query": q, "n": 0, "error": str(e)[:120]})
            continue
        picked = None
        for v in items:
            dur_s = float(v.get("duration") or 0)
            if dur_s < MIN_DUR_S:
                continue
            files = [f for f in (v.get("video_files") or [])
                     if (f.get("width") or 0) >= MIN_W
                     and str(f.get("file_type")) == "video/mp4"]
            if not files:
                continue
            f = sorted(files, key=lambda x: x.get("width") or 0)[0]   # 够用的最小档
            picked = (v, f)
            break
        if not picked:
            trace.append({"scene": sid, "query": q, "n": len(items),
                          "error": "无 ≥{}s 且 ≥{}w 的 mp4".format(MIN_DUR_S, MIN_W)})
            continue
        v, f = picked
        dest = VID_DIR / "pexels_{}.mp4".format(v.get("id"))
        if not dest.is_file() or dest.stat().st_size == 0:
            try:
                dr = requests.get(f["link"], timeout=180, stream=True)
                dr.raise_for_status()
                with dest.open("wb") as fh:
                    for chunk in dr.iter_content(1 << 20):
                        fh.write(chunk)
            except Exception as e:                                          # noqa: BLE001
                trace.append({"scene": sid, "query": q, "error": "download: " + str(e)[:120]})
                continue
        author = str((v.get("user") or {}).get("name") or "unknown")
        cands.append({
            "name": "Pexels Video {} by {}".format(v.get("id"), author),
            "path": "p58_videos/{}".format(dest.name),
            "sha256": hashlib.sha256(dest.read_bytes()).hexdigest(),
            "bytes": dest.stat().st_size,
            "media_type": "video",
            "duration_s": float(v.get("duration") or 0),
            "width": f.get("width"), "height": f.get("height"),
            "fps": f.get("fps"),
            "license": "Pexels License (free, no attribution required)",
            "license_cleared": True, "license_class": "FREE_ATTRIBUTION",
            "provider": "pexels", "source": "external",
            "source_id": str(v.get("id")),
            "source_url": v.get("url"),
            "attribution": "Pexels Video {} by {}".format(v.get("id"), author),
            "retrieval_match_score": 10,
            "query": q, "for_scene": sid,
        })
        trace.append({"scene": sid, "query": q, "n": len(items),
                      "picked": v.get("id"), "dur": v.get("duration"),
                      "wxh": "{},{}".format(f.get("width"), f.get("height"))})
        time.sleep(1.2)                       # Pexels 限速礼貌间隔
    art = {"schema": "p58-1-video-payload-v1", "recorded_at":
           time.strftime("%Y-%m-%dT%H:%M:%S"),
           "candidates_total": len(cands), "candidates": cands, "trace": trace}
    (L / "p58_video_payload.json").write_text(
        json.dumps(art, ensure_ascii=False, indent=1), encoding="utf-8")
    ok = sum(1 for t in trace if t.get("picked"))
    print("P58-1 采集：{}/{} 景拿到视频（{} 个文件，共 {:.1f} MB）".format(
        ok, len(QUERY_MAP), len(cands),
        sum(c["bytes"] for c in cands) / 1e6))
    for t in trace:
        print("  ", t)
    print("-> " + str((L / "p58_video_payload.json").relative_to(R)))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
