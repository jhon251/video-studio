# -*- coding: utf-8 -*-
"""Phase 58 / P58-4：**F14 全片视频采集**（15 景 × 1 条专属视频，零复用）。

按景定查询与**最短时长**（视频时长 ≥ 景长；不足时渲染端 tpad 定格兜底，
但优先选足长素材避免片尾定格）。全局**视频 id 去重**——一景一条，消除复用。
运行: python docs/regression_2x/p58_2_acquire_full.py
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

# 景 → (英文查询, 最短时长 s)。查询按逐景旁白语义人工精选。
SCENE_QUERIES = {
    "P01_4": ("software program code running screen", 11.0),
    "P02_3": ("printing press newspaper pages", 24.0),
    "P03_2": ("old book pages turning close up", 23.0),
    "P03_4": ("dominoes falling chain reaction", 5.5),
    "P04_2": ("team relay race passing baton", 15.0),
    "P04_4": ("person thinking window rain", 17.0),
    "P05_2": ("stack of papers documents review", 21.0),
    "P06_2": ("fork in the road path forest", 16.0),
    "P06_3": ("dictionary pages close up", 19.0),
    "P07_2": ("programmer coding multiple monitors", 24.0),
    "P07_4": ("person studying late night desk lamp", 23.0),
    "P08_2": ("drawing compass geometry paper", 14.5),
    "P08_3": ("abstract artificial intelligence digital", 18.0),
    "P08_4": ("gold medal trophy award", 25.0),
    "P09_5": ("person writing letter pen notebook", 14.5),
}
MIN_W = 1280


def main() -> int:
    from video_studio.core.env import load_env
    env = load_env(R / ".env")
    key = env.get("PEXELS_API_KEY")
    if not key:
        print("PEXELS_API_KEY 缺失 ⇒ fail-closed")
        return 1
    VID_DIR.mkdir(parents=True, exist_ok=True)
    old = json.loads((L / "p58_video_payload.json").read_text(encoding="utf-8")) \
        if (L / "p58_video_payload.json").is_file() else {"candidates": []}
    used_ids = {str(c.get("source_id")) for c in old["candidates"]}
    cands, trace = list(old["candidates"]), []
    for sid, (q, min_dur) in SCENE_QUERIES.items():
        try:
            r = requests.get("https://api.pexels.com/videos/search",
                             params={"query": q, "per_page": 8, "orientation": "landscape"},
                             headers={"Authorization": key}, timeout=30)
            r.raise_for_status()
            items = r.json().get("videos") or []
        except Exception as e:                                              # noqa: BLE001
            trace.append({"scene": sid, "query": q, "error": str(e)[:120]})
            continue
        picked = None
        for v in sorted(items, key=lambda x: -(x.get("duration") or 0)):
            if str(v.get("id")) in used_ids:
                continue                                    # 全局去重：一景一条
            dur_s = float(v.get("duration") or 0)
            if dur_s < min_dur:
                continue
            files = [f for f in (v.get("video_files") or [])
                     if (f.get("width") or 0) >= MIN_W
                     and str(f.get("file_type")) == "video/mp4"]
            if not files:
                continue
            f = sorted(files, key=lambda x: x.get("width") or 0)[0]
            picked = (v, f)
            break
        if not picked:
            trace.append({"scene": sid, "query": q, "n": len(items),
                          "error": "无 ≥{}s 且未复用的候选".format(min_dur)})
            continue
        v, f = picked
        dest = VID_DIR / "pexels_{}.mp4".format(v.get("id"))
        if not dest.is_file() or dest.stat().st_size == 0:
            try:
                dr = requests.get(f["link"], timeout=240, stream=True)
                dr.raise_for_status()
                with dest.open("wb") as fh:
                    for chunk in dr.iter_content(1 << 20):
                        fh.write(chunk)
            except Exception as e:                                          # noqa: BLE001
                trace.append({"scene": sid, "error": "download: " + str(e)[:120]})
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
            "license": "Pexels License (free, no attribution required)",
            "license_cleared": True, "license_class": "FREE_ATTRIBUTION",
            "provider": "pexels", "source": "external",
            "source_id": str(v.get("id")), "source_url": v.get("url"),
            "attribution": "Pexels Video {} by {}".format(v.get("id"), author),
            "retrieval_match_score": 10,
            "query": q, "for_scene": sid,
        })
        used_ids.add(str(v.get("id")))
        trace.append({"scene": sid, "query": q, "picked": v.get("id"),
                      "dur": v.get("duration"), "need": min_dur})
        time.sleep(1.2)
    art = {"schema": "p58-2-video-payload-full-v1",
           "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "candidates_total": len(cands), "candidates": cands, "trace": trace}
    (L / "p58_video_payload.json").write_text(
        json.dumps(art, ensure_ascii=False, indent=1), encoding="utf-8")
    ok = sum(1 for t in trace if t.get("picked"))
    print("P58-4 采集：{}/{} 新景拿到专属视频 | 池累计 {}".format(
        ok, len(SCENE_QUERIES), len(cands)))
    for t in trace:
        print("  ", t)
    print("-> " + str((L / "p58_video_payload.json").relative_to(R)))
    return 0 if ok == len(SCENE_QUERIES) else 1


if __name__ == "__main__":
    raise SystemExit(main())
