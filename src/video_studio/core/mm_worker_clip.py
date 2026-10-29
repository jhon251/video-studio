"""5-A：真实视觉模型 worker（CLIP，**本地权重、离线、CPU、确定性**）。

为什么是独立脚本：主解释器（`C:\\python3.13\\python.exe`）**没有 torch**；
本地 CLIP 权重与 `torch/transformers` 只存在于 `.venv_tts`。
因此把模型推理隔离到这个 worker，用 `.venv_tts\\Scripts\\python.exe` 以**子进程**方式调用：
  · 主流程保持零新增依赖；
  · 模型缺失/venv 缺失/超时 → 由调用方 fail-closed 记 UNKNOWN（本脚本只如实返回错误码，绝不编造相似度）。

用法（由 `core/multimodal.py` / `core/mm_temporal.py` 调用，不手工使用）：
  python mm_worker_clip.py --job job.json --out result.json

job:  {"model_dir": "<CLIP snapshot 目录>",
       "images": [{"id": "S01#0", "path": "..."}],
       "labels": [{"id": "xr_device", "text": "a person wearing a virtual reality headset"}],
       "return_embeddings": false}   # 5-D 加法式选项：true 时额外返回逐图 CLIP 视觉嵌入（默认 false）

out:  {"ok": bool, "code": str|None, "detail": str|None,
       "similarities": {image_id: {label_id: float}},   # 归一化余弦相似度，6 位小数
       "embeddings": {image_id: [512 floats]},          # **仅当 return_embeddings=true**
       "image_sha256": {image_id: "..."}, "versions": {...}, "model": {...}}
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("OMP_NUM_THREADS", "1")


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    job = json.loads(Path(args.job).read_text(encoding="utf-8"))
    model_dir = Path(str(job.get("model_dir") or ""))
    out = {"ok": False, "code": None, "detail": None, "similarities": {},
           "image_sha256": {}, "versions": {}, "model": {"dir": str(model_dir)}}
    if not model_dir.is_dir():
        out.update(code="MM_MODEL_MISSING", detail="模型目录不存在: {}".format(model_dir))
        Path(args.out).write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
        return 0
    try:
        import torch
        import transformers
        from PIL import Image
        from transformers import CLIPModel, CLIPProcessor
    except Exception as exc:                                  # noqa: BLE001
        out.update(code="MM_BACKEND_MISSING",
                   detail="{}: {}".format(type(exc).__name__, str(exc)[:160]))
        Path(args.out).write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
        return 0
    try:
        torch.set_num_threads(1)
        torch.manual_seed(0)
        model = CLIPModel.from_pretrained(str(model_dir), local_files_only=True)
        proc = CLIPProcessor.from_pretrained(str(model_dir), local_files_only=True,
                                             use_fast=False)
        model.eval()
        images = list(job.get("images") or [])
        labels = list(job.get("labels") or [])
        # 5-D 加法式选项：只在显式要求时返回逐图视觉嵌入（默认 false → 5-A 输出逐字节不变）
        want_emb = bool(job.get("return_embeddings"))
        if not images or not labels:
            out.update(code="MM_EMPTY_JOB", detail="images/labels 为空")
            Path(args.out).write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
            return 0
        for im in images:
            p = Path(str(im.get("path")))
            out["image_sha256"][str(im.get("id"))] = sha256_file(p) if p.is_file() else None
        with torch.inference_mode():
            text_inputs = proc(text=[str(l["text"]) for l in labels], return_tensors="pt",
                               padding=True, truncation=True)
            text_emb = model.get_text_features(**text_inputs)
            text_emb = text_emb / text_emb.norm(dim=-1, keepdim=True)
            for im in images:
                with Image.open(Path(str(im["path"]))) as img:
                    rgb = img.convert("RGB")
                    vis_inputs = proc(images=rgb, return_tensors="pt")
                vis_emb = model.get_image_features(**vis_inputs)
                vis_emb = vis_emb / vis_emb.norm(dim=-1, keepdim=True)
                sims = (vis_emb @ text_emb.T)[0].tolist()
                out["similarities"][str(im["id"])] = {
                    str(l["id"]): round(float(s), 6) for l, s in zip(labels, sims)}
                if want_emb:
                    out.setdefault("embeddings", {})[str(im["id"])] = [
                        round(float(x), 6) for x in vis_emb[0].tolist()]
        out["versions"] = {"torch": getattr(torch, "__version__", "?"),
                           "transformers": getattr(transformers, "__version__", "?"),
                           "python": sys.version.split()[0],
                           "device": "cpu", "torch_threads": 1,
                           "hf_offline": os.environ.get("HF_HUB_OFFLINE")}
        out["model"] = {"dir": str(model_dir), "snapshot": model_dir.name,
                        "architecture": "CLIPModel/clip-vit-base-patch32",
                        "config_sha256": sha256_file(model_dir / "config.json")
                        if (model_dir / "config.json").is_file() else None,
                        "weights_sha256": sha256_file(model_dir / "model.safetensors")
                        if (model_dir / "model.safetensors").is_file()
                        else (sha256_file(model_dir / "pytorch_model.bin")
                              if (model_dir / "pytorch_model.bin").is_file() else None),
                        "labels": [{"id": l["id"], "text": l["text"]} for l in labels],
                        "images": [im["id"] for im in images]}
        out["ok"] = True
    except Exception as exc:                                  # noqa: BLE001
        out.update(code="MM_WORKER_FAILED", detail="{}: {}".format(type(exc).__name__,
                                                                   str(exc)[:200]))
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
