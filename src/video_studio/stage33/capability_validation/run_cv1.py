"""CV-1：本地素材视觉理解 PoC（能力假设验证实验，独立于 V3 pipeline）。

H1：真正让系统"看见"素材，能显著改善"语义相关但视觉不适合"的候选选择。
独立命名空间，不 import 3.3 运行链；不修改任何基线。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

import requests
from PIL import Image

ROOT = Path(__file__).resolve().parents[4]
WORK = ROOT / "src" / "video_studio" / "stage33" / "capability_validation"
DATA = ROOT / "output" / "stage33" / "cv1"
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
UA = {"User-Agent": "video-studio-cv1/0.1"}

NUM_RE = re.compile(
    r"[0-9]+(?:[.,][0-9]+)?(?:%|℃|°C|度|米|倍|年)?"
    r"|[一二两三四五六七八九十百千万亿]{1,}(?:度|米|倍|年|分之一|°C|℃)")
PERSON_CUES = ["人", "小孩", "孩子", "渔民", "她", "科学家", "潜水员", "我们"]

# 11 视觉类型（零样本提示词）＋ 4 个二值属性
TYPES = {
    "PORTRAIT_STILL": "a film still or portrait photograph of a person",
    "PAINTING": "an oil painting or classical illustration",
    "PERSON_PHOTO": "a real-life photograph of people",
    "NATURE": "a natural landscape",
    "OCEAN_CORAL": "an underwater scene of coral reef or ocean",
    "ANIMAL": "a photograph of an animal",
    "CHART_SCI": "a chart, graph, map or scientific figure",
    "SCIENCE_ACT": "a scientific or technical procedure",
    "CITY": "a city skyline or urban scene",
    "VIDEO_FRAME": "a frame from a video",
    "OTHER": "other",
}
BINARIES = {
    "has_person": ["a scene containing a person or people",
                   "a scene without any person"],
    "is_painting": ["a painting or illustration",
                    "a real photograph"],
    "is_chart": ["a chart graph map or diagram with data",
                 "a natural photographic scene"],
    "has_text": ["an image with text or labels",
                 "an image without any text"],
}

# 人工标签（视觉类型 + 正/负对），源自文档化裁决与前期人工观看
HUMAN_TYPE = {
    "M-S03-162": "PORTRAIT_STILL", "M-S12-607": "PAINTING",
    "M-S19-954": "PERSON_PHOTO", "M-S19-953": "PERSON_PHOTO",
    "M-S04-224": "OCEAN_CORAL", "M-S04-222": "OCEAN_CORAL", "M-S04-221": "OCEAN_CORAL",
    "M-S05-276": "OCEAN_CORAL", "M-S05-251": "OCEAN_CORAL",
    "M-S08-407": "CHART_SCI", "M-S09-456": "OCEAN_CORAL", "M-S17-825": "OCEAN_CORAL",
    "M-S14-687": "ANIMAL",
    "M-S06-303": "CHART_SCI", "M-S06-307": "CHART_SCI",
    "M-S07-358": "CHART_SCI", "M-S07-357": "CHART_SCI",
    "M-S11-552": "SCIENCE_ACT", "M-S20-1041": "CITY",
    "M-S06-323": "CHART_SCI", "M-S20-1034": "CITY",
}
POSITIVES = [  # (shot, material) 人工正例
    ("S04", "M-S04-224"), ("S04", "M-S04-222"), ("S05", "M-S05-276"),
    ("S06", "M-S06-303"), ("S07", "M-S07-358"), ("S08", "M-S08-407"),
    ("S09", "M-S09-456"), ("S11", "M-S11-552"), ("S14", "M-S14-687"),
    ("S17", "M-S17-825"), ("S20", "M-S20-1041"),
]
NEGATIVES = [  # (shot, material) 人工负例（1-3 为人工裁决；4-10 为构造对照）
    ("S03", "M-S03-162"), ("S12", "M-S12-607"), ("S19", "M-S19-954"),
    ("S01", "M-S03-162"), ("S06", "M-S19-954"), ("S08", "M-S12-607"),
    ("S03", "M-S20-1041"), ("S14", "M-S06-303"), ("S19", "M-S17-825"),
    ("S17", "M-S19-953"),
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_model():
    import torch
    from transformers import CLIPModel, CLIPProcessor
    m = CLIPModel.from_pretrained("openai/clip-vit-base-patch32", cache_dir=str(ROOT / "models" / "clip"))
    p = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32", cache_dir=str(ROOT / "models" / "clip"))
    m.eval()
    return m, p


def download_material(material_id: str, meta: dict, dest_dir: Path) -> Path | None:
    rec = next((x for x in meta["materials"] if x["material_id"] == material_id), None)
    if not rec:
        return None
    url = rec.get("download_url") or rec.get("original_url") or ""
    if not url:
        return None
    ext = "png" if url.endswith(".png") else "jpg"
    if rec.get("content_type") == "video":
        ext = "mp4"
    dest = dest_dir / f"{material_id}.{ext}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        return dest
    for attempt in range(4):
        try:
            r = requests.get(url, headers=UA, timeout=90)
            if r.status_code == 200:
                dest.write_bytes(r.content)
                return dest
        except Exception as e:  # noqa: BLE001
            last = f"{type(e).__name__}: {e}"
        time.sleep(6 * (attempt + 1))
    print(f"[cv1] {material_id} 下载失败")
    return None


def extract_features(model, processor, image_paths: dict) -> dict:
    import torch
    feats = {}
    t0 = time.time()
    texts = list(TYPES.values())
    btexts = {k: v for k, v in BINARIES.items()}
    for mid, p in image_paths.items():
        img = Image.open(p).convert("RGB")
        # 图像嵌入
        inp = processor(images=img, return_tensors="pt")
        with torch.no_grad():
            imgf = model.get_image_features(**inp)
            imgf = imgf / imgf.norm(dim=-1, keepdim=True)
        # 类型零样本
        tinp = processor(text=texts, return_tensors="pt", padding=True, truncation=True)
        with torch.no_grad():
            txf = model.get_text_features(**tinp)
            txf = txf / txf.norm(dim=-1, keepdim=True)
            logits = (imgf @ txf.T).squeeze(0)
            type_probs = torch.softmax(logits * 2.0, dim=0).tolist()
        # 二值属性
        attrs = {}
        for k, (pos, neg) in btexts.items():
            ainp = processor(text=[pos, neg], return_tensors="pt", padding=True, truncation=True)
            with torch.no_grad():
                axf = model.get_text_features(**ainp)
                axf = axf / axf.norm(dim=-1, keepdim=True)
                alogits = (imgf @ axf.T).squeeze(0).tolist()
            attrs[k] = alogits[0] >= alogits[1]
        feats[mid] = {"image_embedding": imgf.squeeze(0).tolist(),
                      "type_probs": {t: round(pb, 4) for t, pb in zip(TYPES, type_probs)},
                      "pred_type": max(TYPES, key=lambda t: type_probs[list(TYPES).index(t)]),
                      "attrs": attrs}
    return feats, {"n": len(image_paths), "elapsed_s": round(time.time() - t0, 1)}


def text_embedding(model, processor, text: str) -> list:
    import torch
    inp = processor(text=[text], return_tensors="pt", padding=True, truncation=True)
    with torch.no_grad():
        f = model.get_text_features(**inp)
    f = f / f.norm(dim=-1, keepdim=True)
    return f.squeeze(0).tolist()


def cosine(a, b):
    return sum(x * y for x, y in zip(a, b))


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    DATA.mkdir(parents=True, exist_ok=True)
    meta = json.loads((ROOT / "output" / "stage31_realworld" / "coral" /
                       "material_pkg_real" / "metadata" / "materials.json")
                      .read_text(encoding="utf-8"))
    narration = (ROOT / "output" / "stage31_realworld" / "coral" /
                 "V2_FINAL_SCRIPT_JARVIS.md").read_text(encoding="utf-8")
    nar_by_shot = {}
    for line in narration.splitlines():
        m = re.match(r"^【(S\d+)】(.*)$", line.strip())
        if m:
            nar_by_shot[m.group(1)] = m.group(2).strip()
    candidates = list(HUMAN_TYPE.keys())
    semantic = {m["material_id"]: (m.get("score_detail") or {}).get("semantic_match", 0)
                or 0 for m in meta["materials"]}

    # 1) 素材本地化 + SHA
    img_dir = DATA / "images"
    image_paths, sha = {}, {}
    for mid in candidates:
        p = download_material(mid, meta, img_dir)
        if p and p.suffix.lower() != ".mp4":
            image_paths[mid] = p
            sha[mid] = _sha256(p)
        else:
            print(f"[cv1] {mid} 无静态图可用（视频或下载失败），排除")
    print(f"[cv1] 可用候选 {len(image_paths)}/{len(candidates)}")

    # 2) 特征提取
    model, processor = load_model()
    feats, timing = extract_features(model, processor, image_paths)
    print(f"[cv1] 特征提取 {timing['n']} 图，{timing['elapsed_s']}s，"
          f"≈{timing['elapsed_s']/max(timing['n'],1):.1f}s/图")
    (DATA / "features.json").write_text(json.dumps(feats, ensure_ascii=False), encoding="utf-8")

    # 3) 属性可靠性（模型 vs 人工标签）
    type_ok = 0
    for mid, f in feats.items():
        if f["pred_type"] == HUMAN_TYPE.get(mid):
            type_ok += 1
    type_acc = type_ok / max(len(feats), 1)
    # 二值属性 vs 人工推断（PAINTING→is_painting；PERSON_*→has_person；CHART_SCI→is_chart）
    attr_gt = {}
    for mid in feats:
        t = HUMAN_TYPE[mid]
        attr_gt[mid] = {"is_painting": t == "PAINTING",
                        "has_person": t in ("PORTRAIT_STILL", "PERSON_PHOTO"),
                        "is_chart": t == "CHART_SCI"}
    attr_stats = {k: {"ok": 0, "n": 0} for k in ("is_painting", "has_person", "is_chart")}
    for mid, f in feats.items():
        for k in attr_stats:
            attr_stats[k]["n"] += 1
            if f["attrs"].get(k) == attr_gt[mid][k]:
                attr_stats[k]["ok"] += 1

    # 4) A/B 排序（shot × 候选池）
    import math
    t_emb = {s: text_embedding(model, processor, nar) for s, nar in nar_by_shot.items()}
    clip_sim = {}
    for mid, f in feats.items():
        for s in nar_by_shot:
            clip_sim[(s, mid)] = cosine(f["image_embedding"], t_emb[s])

    def shot_cues(nar):
        return {"data": bool(NUM_RE.search(nar)),
                "person": any(c in nar for c in PERSON_CUES)}

    def type_fit(s, mid):
        t = HUMAN_TYPE[mid]
        cues = shot_cues(nar_by_shot[s])
        fit = 0.0
        if cues["data"] and t in ("CHART_SCI",):
            fit += 0.5
        if cues["person"] and t in ("PERSON_PHOTO", "PORTRAIT_STILL"):
            fit += 0.3
        if t in ("PAINTING", "PORTRAIT_STILL"):
            fit -= 0.5
        if cues["data"] and t in ("PERSON_PHOTO", "PAINTING"):
            fit -= 0.3
        return max(-1.0, min(1.0, fit))

    def clip01(x):
        return max(0.0, min(1.0, (x - 0.15) / 0.25))

    results = {}
    for w in (0.3, 0.5, 0.7):
        r1, r2 = [], []
        for s in nar_by_shot:
            ranked = []
            for mid in feats:
                sem = semantic.get(mid, 0) / 100.0
                vis = 0.5 * clip01(clip_sim[(s, mid)]) + 0.3 * ((type_fit(s, mid) + 1) / 2) \
                    + 0.2 * sem
                final = w * sem + (1 - w) * vis
                ranked.append((mid, sem, round(vis, 4), round(final, 4)))
            ranked.sort(key=lambda x: x[3], reverse=True)
            ids = [x[0] for x in ranked]
            for (ps, pm) in POSITIVES:
                if ps == s and pm in ids:
                    r2.append(ids.index(pm) < len(ids) / 2)
            for (ns, nm) in NEGATIVES:
                if ns == s and nm in ids:
                    r1.append(ids.index(nm) >= len(ids) / 2)
        # Top-1/3 命中（正例是否在自身 shot 的 top）
        top1 = top3 = 0
        for (ps, pm) in POSITIVES:
            ranked = sorted(
                [(mid, w * (semantic.get(mid, 0) / 100) + (1 - w) *
                  (0.5 * clip01(clip_sim[(ps, mid)]) + 0.3 * ((type_fit(ps, mid) + 1) / 2)
                   + 0.2 * (semantic.get(mid, 0) / 100)))
                 for mid in feats], key=lambda x: x[1], reverse=True)
            ids = [x[0] for x in ranked]
            if pm == ids[0]:
                top1 += 1
            if pm in ids[:3]:
                top3 += 1
        results[w] = {
            "R1_negative_sink_rate": round(sum(r1) / max(len(r1), 1), 3),
            "R2_positive_keep_rate": round(sum(r2) / max(len(r2), 1), 3),
            "negative_false_retention": round(1 - sum(r1) / max(len(r1), 1), 3),
            "positive_false_rejection": round(1 - sum(r2) / max(len(r2), 1), 3),
            "top1_hits": top1, "top3_hits": top3, "n_positives": len(POSITIVES),
            "n_negatives_eval": len(r1),
        }

    # semantic-only 基线（Top-half 命中）
    sem_top1 = sem_top3 = 0
    for (ps, pm) in POSITIVES:
        ranked = sorted(feats, key=lambda m: semantic.get(m, 0), reverse=True)
        if pm == ranked[0]:
            sem_top1 += 1
        if pm in ranked[:3]:
            sem_top3 += 1

    out = {
        "n_candidates": len(feats), "type_accuracy": round(type_acc, 3),
        "attr_stats": {k: {"acc": round(v["ok"] / max(v["n"], 1), 3), "n": v["n"]}
                       for k, v in attr_stats.items()},
        "timing": timing, "semantic_baseline": {"top1": sem_top1, "top3": sem_top3},
        "results": {str(k): v for k, v in results.items()},
        "negatives": [list(x) for x in NEGATIVES],
        "positives": [list(x) for x in POSITIVES],
        "sha": sha,
    }
    (DATA / "cv1_result.json").write_text(json.dumps(out, ensure_ascii=False, indent=2),
                                          encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
