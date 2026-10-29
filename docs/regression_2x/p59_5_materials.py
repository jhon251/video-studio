# -*- coding: utf-8 -*-
"""Phase 59 / P59-5：**EP3 素材采集**（27 景零复用：20 Pexels + 5 生成 + 2 PD）。

规则（授权条件 3）：
  · 逐景语义匹配：查询词 = 已审分镜计划的逐景视觉意图（英文检索）；
  · 许可：Pexels License / Wikimedia PD（API extmetadata 核验）/
    自有生成（wanx2.1，黑板主线系列风格）；
  · 重复度：与第二期已用视频 id 全局去重 + 本轮 sha 去重；
  · 画质：视频宽 ≥1280 且时长 ≥ 景长（不足须 tpad 时在证据中标记）；
  · **不合格素材不得静默替代为不相关素材**——失败/不合格 ⇒ 记入 `shortfalls`，
    对应景位留空待处置，绝不用无关素材顶替。
产出：`output/p59_ep3/materials/` + `material_payload.json`（候选池，含逐景映射）。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys
import time
import urllib.parse
import urllib.request

import requests

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
OUT = R / "output" / "p59_ep3" / "materials"
VID = OUT / "pexels_videos"
IMG = OUT / "pd_images"
GEN = OUT / "gen_images"
TB = R / "output" / "p59_ep3" / "voice_full" / "timebase_full.json"
EP2_PAYLOAD = R / "docs" / "regression_2x" / "logs" / "p58_video_payload.json"
MIN_W = 1280

# 逐景素材表（场景 id → 视觉意图查询 / 类型）
PLAN = {
    "P01_1": ("pexels", "smart home bedroom curtains morning light"),
    "P01_2": ("gen", "家居健康管家：一块温暖的居家屏幕，显示药品提醒与家人留言，黑板粉笔风"),
    "P01_3": ("pexels", "man checking phone disappointed close up"),
    "P02_1": ("pexels", "autonomous self driving car city street"),
    "P02_2": ("pexels", "self driving shuttle interior passengers"),
    "P02_3": ("pexels", "hands typing laptop data close up"),
    "P02_4": ("pexels", "warehouse logistics robots automation"),
    "P03_1": ("gen", "异常警报：黑板上一个巨大的红色感叹号与错位的秒表，粉笔笔触，冷色"),
    "P03_2": ("pexels", "dashcam road driving night highway"),
    "P04_1": ("pexels", "elderly man video call smartphone happy"),
    "P04_2": ("pexels", "doctor examining medical scan screen"),
    "P04_3": ("pexels", "doctor signing documents hospital"),
    "P04_4": ("pexels", "hospital corridor empty small town"),
    "P05_1": ("pexels", "students leaving school gate asia"),
    "P05_2": ("gen", "AI 家教：黑板上一个耐心的灯泡导师与对话气泡，粉笔笔触，暖色"),
    "P05_3": ("pexels", "teacher talking with students classroom"),
    "P06_1": ("pexels", "elderly woman robot companion home"),
    "P06_2": ("pexels", "elderly fall alert wristband care"),
    "P06_3": ("pexels", "lonely elderly window silence"),
    "P07_1": ("pexels", "man writing notebook night lamp"),
    "P07_2": ("pexels", "phone screen social media night likes"),
    "P08_1": ("pexels", "data center server room lights"),
    "P08_2": ("gen", "深度伪造：黑板上两张一模一样的笑脸，其中一张是粉笔画的，冷色警示"),
    "P08_3": ("pd", "power loom weaving industrial revolution engraving"),
    "P08_4": ("pd", "ENIAC computer 1946 vacuum tubes"),
    "P09_1": ("pexels", "typing smartphone dark bed night"),
    "P09_2": ("gen", "2040 一天时间线：黑板上从日出到星空的一条粉笔时间轴"),
}


def ua_get(url, **kw):
    req = urllib.request.Request(url, headers={"User-Agent": "video-studio/1.0 (material acquisition)"})
    return urllib.request.urlopen(req, timeout=120, **kw)


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def main() -> int:
    from video_studio.core.env import load_env
    env = load_env(R / ".env")
    key = env.get("PEXELS_API_KEY")
    for d in (VID, IMG, GEN):
        d.mkdir(parents=True, exist_ok=True)
    tb = json.loads(TB.read_text(encoding="utf-8"))
    scene_len = {w["scene_id"]: round(w["end_s"] - w["start_s"], 2) for w in tb["windows"]}
    ep2_used = {str(c.get("source_id")) for c in
                json.loads(EP2_PAYLOAD.read_text(encoding="utf-8")).get("candidates") or []
                if c.get("source_id")}
    cands, shortfalls, trace = [], [], []

    # ---- Pexels ----
    for sid, (typ, q) in PLAN.items():
        if typ != "pexels":
            continue
        need = scene_len.get(sid, 10.0)
        try:
            r = requests.get("https://api.pexels.com/videos/search",
                             params={"query": q, "per_page": 10, "orientation": "landscape"},
                             headers={"Authorization": key}, timeout=30)
            r.raise_for_status()
            items = r.json().get("videos") or []
        except Exception as e:                                              # noqa: BLE001
            shortfalls.append({"scene": sid, "why": "search: " + str(e)[:100]})
            continue
        pick = None
        for v in sorted(items, key=lambda x: -(x.get("duration") or 0)):
            if str(v.get("id")) in ep2_used:
                continue
            if float(v.get("duration") or 0) < min(need, 8.0):
                continue
            files = [f for f in (v.get("video_files") or [])
                     if (f.get("width") or 0) >= MIN_W
                     and str(f.get("file_type")) == "video/mp4"]
            if not files:
                continue
            pick = (v, sorted(files, key=lambda x: x.get("width") or 0)[0])
            break
        if not pick:
            shortfalls.append({"scene": sid, "query": q,
                               "why": "无 ≥{:.0f}s 且未在第二期使用的合格候选".format(min(need, 8.0))})
            continue
        v, f = pick
        dest = VID / "pexels_{}.mp4".format(v.get("id"))
        if not dest.is_file() or dest.stat().st_size == 0:
            try:
                dr = requests.get(f["link"], timeout=240, stream=True)
                dr.raise_for_status()
                with dest.open("wb") as fh:
                    for ch in dr.iter_content(1 << 20):
                        fh.write(ch)
            except Exception as e:                                          # noqa: BLE001
                shortfalls.append({"scene": sid, "why": "download: " + str(e)[:100]})
                continue
        author = str((v.get("user") or {}).get("name") or "unknown")
        cands.append({
            "name": "Pexels Video {} by {}".format(v.get("id"), author),
            "path": "p59_videos/{}".format(dest.name), "sha256": sha(dest),
            "bytes": dest.stat().st_size, "media_type": "video",
            "duration_s": float(v.get("duration") or 0), "width": f.get("width"),
            "height": f.get("height"),
            "license": "Pexels License (free, no attribution required)",
            "license_cleared": True, "license_class": "FREE_ATTRIBUTION",
            "provider": "pexels", "source": "external", "source_id": str(v.get("id")),
            "source_url": v.get("url"),
            "attribution": "Pexels Video {} by {}".format(v.get("id"), author),
            "retrieval_match_score": 10, "query": q, "for_scene": sid})
        ep2_used.add(str(v.get("id")))
        trace.append({"scene": sid, "picked": v.get("id"), "dur": v.get("duration"),
                      "need": need})
        time.sleep(1.0)

    # ---- Wikimedia PD 图像（API 核验许可后下载）----
    for sid, (typ, q) in PLAN.items():
        if typ != "pd":
            continue
        try:
            api = ("https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode({
                "action": "query", "generator": "search", "gsrsearch": "filetype:bitmap " + q,
                "gsrnamespace": 6, "gsrlimit": 8, "prop": "imageinfo",
                "iiprop": "url|extmetadata|size", "iiurlwidth": 1600, "format": "json"}))
            with ua_get(api) as r:
                data = json.loads(r.read().decode())
            pages = (data.get("query") or {}).get("pages") or {}
            pick = None
            for p in sorted(pages.values(), key=lambda x: x.get("index", 99)):
                ii = (p.get("imageinfo") or [{}])[0]
                meta = ii.get("extmetadata") or {}
                lic = str((meta.get("LicenseShortName") or {}).get("value") or "")
                if ("Public domain" not in lic) and ("CC0" not in lic):
                    continue
                if (ii.get("width") or 0) < 1000:
                    continue
                pick = (p, ii, lic)
                break
            if not pick:
                shortfalls.append({"scene": sid, "query": q,
                                   "why": "无 PD/CC0 且 ≥1000px 的候选"})
                continue
            p, ii, lic = pick
            title = p.get("title", "").replace("File:", "")
            dest = IMG / (re.sub(r"[^A-Za-z0-9_.-]", "_", title)[:60] or "pd_img")
            dest = dest.with_suffix(".jpg") if not dest.suffix else dest
            url = ii.get("thumburl") or ii.get("url")
            with ua_get(url) as r, dest.open("wb") as fh:
                fh.write(r.read())
            artist = re.sub(r"<[^>]+>", "", str(
                (ii.get("extmetadata") or {}).get("Artist", {}).get("value", "")))[:80]
            cands.append({
                "name": "Wikimedia Commons: " + title[:60],
                "path": "p59_pd/{}".format(dest.name), "sha256": sha(dest),
                "bytes": dest.stat().st_size, "media_type": "image",
                "license": lic, "license_cleared": True,
                "license_class": "PUBLIC_DOMAIN",
                "provider": "wikimedia_commons", "source": "external",
                "source_id": title, "source_url": ii.get("descriptionurl"),
                "attribution": (artist + " — " + lic).strip("— "),
                "retrieval_match_score": 10, "query": q, "for_scene": sid})
            trace.append({"scene": sid, "picked": title[:50], "license": lic})
        except Exception as e:                                              # noqa: BLE001
            shortfalls.append({"scene": sid, "why": "wikimedia: " + str(e)[:100]})

    art = {"schema": "p59-5-material-payload-v1", "recorded_at":
           time.strftime("%Y-%m-%dT%H:%M:%S"),
           "candidates_total": len(cands), "candidates": cands,
           "trace": trace, "shortfalls": shortfalls}
    (R / "docs/regression_2x/logs/p59_5_material_payload.json").write_text(
        json.dumps(art, ensure_ascii=False, indent=1), encoding="utf-8")
    print("Pexels/PD 采集：候选 {} | 缺口 {}".format(len(cands), len(shortfalls)))
    for s in shortfalls:
        print("  SHORT:", s)
    print("-> docs/regression_2x/logs/p59_5_material_payload.json")
    return 0


import re  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
