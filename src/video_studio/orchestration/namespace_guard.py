"""Namespace / Experiment Isolation Guard.

Hard production threshold: any asset outside the run's namespace, or flagged
experimental (stage22 / exp225 / experimental / audit / pilot), or lacking
production authorization may NOT enter a production route. Violations are
BLOCK — never warnings.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from video_studio.orchestration.schemas import GateVerdict


EXPERIMENT_MARKERS = ("stage22", "exp225", "experimental", "audit", "pilot")


@dataclass
class NamespacePolicy:
    run_namespace: str                     # absolute prefix that production assets must live under
    blocked_markers: tuple = EXPERIMENT_MARKERS
    allow_registry: frozenset = frozenset()  # explicitly production-authorized paths (post sign-off)


def check_namespace(path: str, policy: NamespacePolicy) -> dict:
    """Return {verdict, reasons}. BLOCK on: experiment marker, outside namespace,
    or missing production authorization. Explicit allow_registry overrides
    marker/namespace checks (for signed-off assets only, never for status=experimental)."""
    p = str(path)
    pl = p.lower().replace("\\", "/")
    reasons = []
    verdict = GateVerdict.PASS
    if p in policy.allow_registry:
        return {"verdict": GateVerdict.PASS.value, "reasons": ["explicitly_authorized"]}
    if any(m in pl for m in policy.blocked_markers):
        reasons.append(f"experimental_marker:{next(m for m in policy.blocked_markers if m in pl)}")
        verdict = GateVerdict.BLOCK
    ns = str(policy.run_namespace).lower().replace("\\", "/")
    if ns and not pl.startswith(ns.lower().replace("\\", "/")):
        reasons.append(f"outside_run_namespace:{policy.run_namespace}")
        verdict = GateVerdict.BLOCK
    if not reasons:
        reasons.append("ok")
    return {"verdict": verdict.value, "reasons": reasons}
