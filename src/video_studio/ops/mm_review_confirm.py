# -*- coding: utf-8 -*-
"""mm-review-confirm: append-only human decision record for Final Gate.

Principles:
- READ-ONLY on evaluation/judgment systems (mm_judge, mm_quality, multimodal,
  mm_temporal, semantics — zero modification).
- WRITE only to mm_review_decisions.jsonl in the project directory (append-only).
- Every decision is human-input; the system never auto-executes replace.
- keep_unknown ≠ accept (semantically distinct).
- Historical decisions cannot be overwritten or deleted.
- Illegal input → fail-closed (no record written).
"""
import json
import uuid
from pathlib import Path

VALID_DECISIONS = {"accept", "replace", "keep_unknown"}
REQUIRED_FIELDS = ("scene_id", "case_id", "decision")
OPTIONAL_REPLACE = "replacement_asset_id"


def sha256_file(p):
    import hashlib
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run_mm_review_confirm(*, db_path, project_id: str, decisions_path: str,
                          judge_json_path: str, truth_set_path: str,
                          decided_by: str) -> dict:
    """Validate human decisions and append to mm_review_decisions.jsonl.

    Fail-closed: any validation error → no record written.
    """
    import datetime
    # ---- input fingerprint (from actual files) ----
    fp = {}
    for label, path in [("judge_json", judge_json_path), ("truth_set", truth_set_path)]:
        pp = Path(path)
        if not pp.is_file():
            return {"ok": False, "error": f"{label} not found: {path}"}
        fp[label] = sha256_file(pp)

    # ---- read decisions file ----
    dp = Path(decisions_path)
    if not dp.is_file():
        return {"ok": False, "error": f"decisions file not found: {decisions_path}"}
    try:
        decisions = json.loads(dp.read_text(encoding="utf-8"))
    except Exception as ex:
        return {"ok": False, "error": f"decisions file not valid JSON: {ex}"}
    if not isinstance(decisions, list):
        return {"ok": False, "error": "decisions must be a JSON array"}

    # ---- validate each decision (fail-closed: any error = no write) ----
    errors = []
    for i, d in enumerate(decisions):
        if not isinstance(d, dict):
            errors.append(f"[{i}] not a dict")
            continue
        for f in REQUIRED_FIELDS:
            if f not in d or not str(d.get(f, "")).strip():
                errors.append(f"[{i}] missing required field: {f}")
        decision = d.get("decision", "")
        if decision not in VALID_DECISIONS:
            errors.append(f"[{i}] invalid decision: {decision!r} (must be accept/replace/keep_unknown)")
        if decision == "replace" and not d.get(OPTIONAL_REPLACE, "").strip():
            errors.append(f"[{i}] replace requires {OPTIONAL_REPLACE}")
        if decision == "keep_unknown" and d.get("replacement_asset_id"):
            errors.append(f"[{i}] keep_unknown must not have replacement_asset_id")
    if errors:
        return {"ok": False, "error": "validation failed: " + "; ".join(errors[:5])}

    # ---- decisions file (append-only JSONL) ----
    proj_dir = Path(db_path).parent / project_id
    proj_dir.mkdir(parents=True, exist_ok=True)
    decisions_file = proj_dir / "mm_review_decisions.jsonl"
    now = datetime.datetime.now().isoformat(timespec="seconds")

    appended = 0
    with open(decisions_file, "a", encoding="utf-8") as f:
        for d in decisions:
            record = {
                "decision_id": f"dec_{uuid.uuid4().hex[:12]}",
                "project_id": project_id,
                "scene_id": d["scene_id"],
                "case_id": d["case_id"],
                "decision": d["decision"],
                "rationale": d.get("rationale", ""),
                "original_asset_id": d.get("original_asset_id", ""),
                "replacement_asset_id": d.get(OPTIONAL_REPLACE, "") or None,
                "decided_by": decided_by,
                "decided_at": now,
                "input_fingerprint": {
                    "judge_json_sha256": fp["judge_json"],
                    "truth_set_sha256": fp["truth_set"],
                },
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            appended += 1

    return {"ok": True, "appended": appended, "decisions_file": str(decisions_file)}
