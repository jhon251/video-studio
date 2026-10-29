"""Stage 3.1.3 本地语义层：多语言 sentence-transformer embedding + 缓存。

- 离线可用（模型经 hf-mirror 下载到 models/semantic/）；
- CPU 运行；embedding 结果按文本 SHA256 落盘缓存；
- 只负责语义相关性，绝不绕过版权门禁（版权在 rights 层硬门槛）。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "60")

ROOT = Path(__file__).resolve().parents[3]  # src/video_studio/stage31 -> 项目根
MODEL_DIR = ROOT / "models" / "semantic"
CACHE = ROOT / "models" / "semantic" / "embed_cache.json"
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

_model_obj = None
_cache: dict = {}


def _load_cache():
    global _cache
    if CACHE.exists():
        try:
            _cache = json.loads(CACHE.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            _cache = {}


def _save_cache():
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(_cache), encoding="utf-8")


def _get_model():
    global _model_obj
    if _model_obj is None:
        # 直接 transformers 加载（绕开 sentence-transformers 对 Windows 路径的 repo-id 误判）
        from transformers import AutoModel, AutoTokenizer
        import torch
        local = MODEL_DIR / "paraphrase-multilingual-MiniLM-L12-v2"
        path = str(local) if (local / "config.json").exists() else MODEL_NAME

        class _Encoder:
            def __init__(self, tok, mod):
                self.tok, self.mod = tok, mod

            def encode(self, texts, normalize_embeddings=True):
                inputs = self.tok(texts, padding=True, truncation=True,
                                  return_tensors="pt")
                with torch.no_grad():
                    out = self.mod(**inputs).last_hidden_state
                mask = inputs["attention_mask"].unsqueeze(-1).float()
                vecs = (out * mask).sum(1) / mask.sum(1).clamp(min=1e-9)
                if normalize_embeddings:
                    vecs = torch.nn.functional.normalize(vecs, p=2, dim=1)
                return vecs.numpy()

        tok = AutoTokenizer.from_pretrained(path, local_files_only=(path != MODEL_NAME))
        mod = AutoModel.from_pretrained(path, local_files_only=(path != MODEL_NAME))
        _model_obj = _Encoder(tok, mod)
    return _model_obj


def clean_text(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text or "").strip()


def embed(texts: list[str]) -> list[list[float]]:
    """批量 embedding（带磁盘缓存）。"""
    _load_cache()
    out: list = [None] * len(texts)
    todo = []
    for i, t in enumerate(texts):
        t = clean_text(t)
        key = hashlib.sha256(t.encode("utf-8")).hexdigest()[:24]
        if key in _cache:
            out[i] = _cache[key]
        else:
            todo.append((i, key, t))
    if todo:
        embs = _get_model().encode([t for _, _, t in todo], normalize_embeddings=True)
        for (i, key, _), emb in zip(todo, embs):
            vec = [float(x) for x in emb]
            _cache[key] = vec
            out[i] = vec
        _save_cache()
    return out


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def semantic_similarity(text_a: str, text_b: str) -> float:
    a, b = embed([text_a, text_b])
    if a is None or b is None:
        return 0.0
    return float(cosine(a, b))
