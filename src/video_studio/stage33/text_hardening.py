"""text_hardening (Stage 10): shared Stage-9-B+C structured-output helper.

Self-contained: talks to DeepSeek directly (B prompt + simplified schema),
strictly validates, repairs ONCE with a corrective re-prompt, and falls back
with an explicit marker when the LLM still fails. NEVER fabricates success.

Not used by CV-2 / V1 / sanitizer / any frozen component.
"""
from __future__ import annotations

import json
import os
import re
import time

import requests

ROOT = None  # set by init
API_KEY = ""
BASE = "https://api.deepseek.com"


def init(root, key: str) -> None:
    global ROOT, API_KEY
    ROOT = root
    API_KEY = key


def call_model(model: str, system: str, user: str, max_tokens: int = 8192,
               temperature: float = 0.2) -> tuple[str, str, dict]:
    r = requests.post(f"{BASE}/chat/completions",
                      headers={"Authorization": f"Bearer {API_KEY}",
                               "Content-Type": "application/json"},
                      json={"model": model, "messages": [
                          {"role": "system", "content": system},
                          {"role": "user", "content": user}],
                          "max_tokens": max_tokens, "temperature": temperature},
                      timeout=180)
    r.raise_for_status()
    body = r.json()
    ch = (body.get("choices") or [{}])[0]
    return (ch.get("message", {}).get("content") or ""), ch.get("finish_reason") or "", body.get("usage", {})


def extract_json(text: str):
    if not text or not text.strip():
        return None, "EMPTY"
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None, "NO_JSON_IN_TEXT"
    try:
        return json.loads(text[start:end + 1]), "OK"
    except Exception as e:  # noqa: BLE001
        return None, f"PARSE_ERR:{str(e)[:40]}"


def validate(data, schema: dict):
    if not isinstance(data, dict):
        return False, "not_object"
    for k in schema.get("required", []):
        if k not in data:
            return False, f"missing:{k}"
        st = schema.get("properties", {}).get(k, {}).get("type")
        if st == "array" and not isinstance(data[k], list):
            return False, f"type:{k}"
        if st == "string" and not isinstance(data[k], str):
            return False, f"type:{k}"
    return True, "valid"


def hardened_call(model: str, system: str, user: str, schema: dict,
                  repair_prompt: str | None = None, max_repair: int = 1,
                  temperature: float = 0.2) -> dict:
    """LLM -> validate -> (repair once) -> validated result | explicit fallback."""
    attempts = []
    current_user = user
    for attempt in range(1, max_repair + 2):
        t0 = time.time()
        try:
            text, finish, usage = call_model(model, system, current_user,
                                             temperature=temperature)
        except Exception as e:  # noqa: BLE001
            attempts.append({"attempt": attempt, "status": "API_FAIL",
                             "note": f"{type(e).__name__}: {str(e)[:60]}", "dt_s": round(time.time() - t0, 2)})
            if attempt <= max_repair and repair_prompt:
                current_user = repair_prompt
                continue
            break
        parsed, parse_note = extract_json(text)
        if parsed is None:
            ok, note = False, parse_note
        else:
            ok, note = validate(parsed, schema)
        attempts.append({"attempt": attempt, "status": "SUCCESS" if ok else "SCHEMA_FAIL",
                         "note": note, "finish": finish, "dt_s": round(time.time() - t0, 2),
                         "len": len(text)})
        if ok:
            return {"status": "SUCCESS", "data": parsed, "attempts": attempts,
                    "used_repair": attempt > 1, "fallback": False}
        if attempt <= max_repair and repair_prompt:
            current_user = repair_prompt
    return {"status": "FALLBACK", "data": None, "attempts": attempts,
            "used_repair": len(attempts) > 1, "fallback": True,
            "note": "deterministic fallback (structured template) NOT LLM success"}
