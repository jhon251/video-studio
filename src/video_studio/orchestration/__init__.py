"""Visual Orchestration Layer (Video Agent 2.x).

Formal modules for the production chain:

    Retrieval -> Gate -> CV2 -> Assignment -> Global Reuse Policy
    -> Pre-render Visual Integrity Gate -> Crop/Layout -> Crop-aware Recheck
    -> Render -> QA

Layering contract (fixed by EXP-VG 2026-09-10 authorization):
  * candidate -> quality eligible pool -> reuse selection
    (the reuse policy NEVER selects from an un-gated pool)
  * deterministic gates (G0-G4, G8, G9) may BLOCK;
    heuristic signals (G5-G7) are advisory/DEMOTE only until independently calibrated
  * namespace violations are hard BLOCKs, never warnings

All modules are deterministic, pure where practical, schema-typed and audit-logged.
This package adds NEW files only; stage33 frozen modules are untouched.
"""
from video_studio.orchestration.schemas import (
    AssetRef, Candidate, BeatSpec, GateVerdict, GateResult, IntegrityReport,
    DisplayKind, Decision, CropLayout, CropRisk, LedgerEntry,
)
from video_studio.orchestration.content_identity import build_content_index, ContentIndex
from video_studio.orchestration.global_reuse_ledger import GlobalReuseLedger
from video_studio.orchestration.global_reuse_policy import ReusePolicyConfig, run_reuse_policy
from video_studio.orchestration.visual_integrity_gate import IntegrityGateConfig, evaluate_asset
from video_studio.orchestration.crop_recheck import evaluate_crop
from video_studio.orchestration.namespace_guard import NamespacePolicy, check_namespace

__all__ = [
    "AssetRef", "Candidate", "BeatSpec", "GateVerdict", "GateResult", "IntegrityReport",
    "DisplayKind", "Decision", "CropLayout", "CropRisk", "LedgerEntry",
    "build_content_index", "ContentIndex",
    "GlobalReuseLedger", "ReusePolicyConfig", "run_reuse_policy",
    "IntegrityGateConfig", "evaluate_asset",
    "evaluate_crop", "NamespacePolicy", "check_namespace",
]
