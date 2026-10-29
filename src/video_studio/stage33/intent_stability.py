"""intent_stability (Stage 12.9): content-addressed Visual Intent cache.

Problem (12.8): the same beat narration produced different visual themes on
re-roll (S06-B02: city transformation vs factory imagery), so downstream
gate/CV-2 verdicts flip between runs.

Fix: persistent cache keyed by sha256(narration + full prompt text). The same
beat narration always resolves to the same stored intent:
  - first generation: real LLM call (12.6-calibrated prompt, temperature 0),
    stored;
  - repeat generations: cache hit, returned verbatim with
    llm_status="CACHE_HIT" (fully traceable);
  - prompt/narration change -> different key -> natural regeneration.
No shot-id mapping, no keyword rules, no theme forcing: whatever the LLM
generated first is what every repeat run sees.

This module is only consulted by visual_intent.generate; nothing else changes.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CACHE_DIR = ROOT / "output/stage33/intent_cache"
VERSION = "v1"


def _key(narration: str, prompt_text: str) -> str:
    h = hashlib.sha256()
    h.update(VERSION.encode())
    h.update(narration.strip().encode("utf-8"))
    h.update(prompt_text.strip().encode("utf-8"))
    return h.hexdigest()[:24]


def _path(key: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{key}.json"


def get_cached(narration: str, prompt_text: str) -> dict | None:
    p = _path(_key(narration, prompt_text))
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return None
    return None


def store(narration: str, prompt_text: str, intent: dict) -> str:
    key = _key(narration, prompt_text)
    _path(key).write_text(json.dumps(intent, ensure_ascii=False, indent=2),
                          encoding="utf-8")
    return key
