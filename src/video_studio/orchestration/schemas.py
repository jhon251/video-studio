"""Input/output schemas for the Visual Orchestration Layer.

Dataclass-only, JSON-serializable via as_dict(); no behavior hidden in properties
beyond serialization. Every module consumes/produces these types.
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class GateVerdict(str, Enum):
    PASS = "PASS"
    DEMOTE = "DEMOTE"
    BLOCK = "BLOCK"
    ADVISORY = "ADVISORY"   # signal recorded, no action


class DisplayKind(str, Enum):
    EVIDENCE = "EVIDENCE"                 # own-pool, correspondence-claiming display
    ANCHOR_CALLBACK = "ANCHOR_CALLBACK"   # registered callback reuse
    BORROW = "BORROW"                     # HN/FALLBACK borrow (corner tag)
    VIZ = "VIZ"
    BLANK = "BLANK"                       # blank card


def as_dict(obj):
    if dataclasses.is_dataclass(obj):
        return {k: as_dict(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, list):
        return [as_dict(x) for x in obj]
    if isinstance(obj, dict):
        return {k: as_dict(v) for k, v in obj.items()}
    return obj


@dataclass
class AssetRef:
    """A physical asset file with its provenance minimal set."""
    material_id: str
    path: str
    beat_id: str                  # retrieval-owning beat (pool origin)
    source: str = ""              # wikimedia / pexels / ...
    asset_type: str = "PHOTO"     # PHOTO | CHART
    namespace: str = ""           # owning run namespace, e.g. "prod02"
    artifact_status: str = "production"  # production | experimental
    production_authorized: bool = True


@dataclass
class Candidate:
    """A beat candidate as seen by the reuse policy (already quality-eligible
    or carrying the upstream ineligibility reason)."""
    material_id: str
    content_id: str               # content cluster id from ContentIndex
    path: str
    eligible: bool = True
    ineligible_reason: str = ""
    cv2_usability: str = ""       # USABLE / CONDITIONALLY_USABLE / NOT_USABLE / "" / VIZ_AUTHORIZED
    cv2_fit: float = -1.0
    viz: bool = False             # narrow-authorized structural card (F-delta); not retrieved material


@dataclass
class BeatSpec:
    beat_id: str
    route: str                    # EVIDENCE | HN | VIZ
    chapter_id: int
    start: float
    end: float
    candidates: list = field(default_factory=list)   # list[Candidate]


@dataclass
class GateResult:
    gate: str                     # G0..G9
    verdict: GateVerdict
    reason: str
    measured: dict = field(default_factory=dict)


@dataclass
class IntegrityReport:
    asset: AssetRef
    results: list = field(default_factory=list)      # list[GateResult]
    final: GateVerdict = GateVerdict.PASS
    block_gates: list = field(default_factory=list)
    demote_gates: list = field(default_factory=list)
    advisory_gates: list = field(default_factory=list)


@dataclass
class Decision:
    """One beat's visual decision emitted by the reuse policy."""
    beat_id: str
    action: DisplayKind
    content_id: Optional[str] = None
    material_id: Optional[str] = None
    cls: str = ""                 # CORRESPONDING / HONEST_NEUTRAL / FALLBACK / VISUALIZATION / BLANK_CARD
    borrow_from: Optional[str] = None
    callback_of: Optional[str] = None
    reason: str = ""
    demoted_from: Optional[str] = None   # original action if cascade fired


@dataclass
class LedgerEntry:
    """One display row of the global reuse ledger."""
    content_id: str
    material_id: str
    beat_id: str
    chapter_id: int
    ts_start: float
    ts_end: float
    asset_type: str
    narrative_function: str       # DisplayKind value
    source: str
    callback_of: Optional[str] = None
    reuse_count: int = 0          # display ordinal of this content (0-based)
    borrow_count: int = 0         # 1 if this row is a borrow
    first_seen: float = 0.0
    last_seen: float = 0.0


@dataclass
class CropLayout:
    """The crop/layout decision that will hit the render for an asset."""
    out_w: int = 1920
    out_h: int = 1080
    fit_mode: str = "cover"       # cover | contain | detail_crop
    crop_box: Optional[tuple] = None   # (l, t, r, b) in source pixels; None = full frame


@dataclass
class CropRisk:
    asset_material_id: str
    beat_id: str
    visible_frac: float
    dhash_shift: int
    displacement_frac: float      # center displacement of crop vs image center
    aspect_transform: float       # out AR / source AR
    text_collision_risk: bool
    verdict: GateVerdict
    reasons: list = field(default_factory=list)
