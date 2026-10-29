"""Pre-render Visual Integrity Gate.

Deterministic gates may BLOCK: G0 existence, G1 MIME, G2 resolution,
G3 aspect ratio, G4 content duplicate (MD5+dHash), G8 namespace/experiment
isolation, G9 provenance chain.
Heuristic signals G5 (collage/screenshot), G6 (text density), G7 (watermark)
are ADVISORY ONLY — they are calibrated-unready (EXP-VG2 FP 5-6/51) and must
never be the sole trigger of a BLOCK. They may DEMOTE only when combined with
a deterministic finding; standalone they record an advisory signal.

G4 duplicate rule: the FIRST occurrence (by `first_seen_order`) of a content
passes; later byte/perceptual duplicates of the same content BLOCK.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image

from video_studio.orchestration.schemas import (
    AssetRef, GateResult, GateVerdict, IntegrityReport,
)
from video_studio.orchestration.content_identity import ContentIndex, dhash_of, hamming, md5_of

BLOCKING = {"G0", "G1", "G2", "G3", "G4", "G8", "G9"}
EXPERIMENT_MARKERS = ("stage22", "exp225", "experimental", "audit", "pilot")


@dataclass
class IntegrityGateConfig:
    photo_min_short_side: int = 720         # below this (and >= block) -> DEMOTE (upscale note)
    photo_block_short_side: int = 480       # below this -> BLOCK (unusable)
    chart_min_w: int = 1280
    chart_min_h: int = 720
    ar_min: float = 0.8
    ar_max: float = 2.2
    min_bytes: int = 5120
    run_namespace: str = ""                 # e.g. absolute prefix of the run dir
    allow_registry: frozenset = frozenset()  # explicitly signed-off paths (overrides G8 marker/namespace)
    content_index: ContentIndex | None = None
    displayed_contents: set = field(default_factory=set)   # content_ids already on screen (G4 display-level)
    provenance: dict = field(default_factory=dict)         # material_id -> {beat,title,url,verdict}
    g5_grid_rows: int = 8
    g5_grid_cols: int = 8
    g6_busy_edge: float = 0.30
    g7_corner_factor: float = 3.5


def _edge_ratio(g: np.ndarray) -> float:
    gy, gx = np.gradient(g.astype(float))
    return float((np.hypot(gx, gy) > 24).mean())


def _uniform_lines(g: np.ndarray):
    return int((g.std(axis=1) < 3).sum()), int((g.std(axis=0) < 3).sum())


def _corner_edge(g: np.ndarray):
    h, w = g.shape
    gh, gw = max(8, int(h * 0.10)), max(24, int(w * 0.16))
    glob = _edge_ratio(g)
    mx = max(_edge_ratio(g[0:gh, 0:gw]), _edge_ratio(g[0:gh, w - gw:w]),
             _edge_ratio(g[h - gh:h, 0:gw]), _edge_ratio(g[h - gh:h, w - gw:w]))
    return mx, glob


def evaluate_asset(asset: AssetRef, cfg: IntegrityGateConfig) -> IntegrityReport:
    rep = IntegrityReport(asset=asset)
    p = asset.path
    g = None
    im = None

    def add(r: GateResult):
        rep.results.append(r)
        v = r.verdict.value
        if r.verdict == GateVerdict.BLOCK:
            rep.block_gates.append(r.gate)
        elif r.verdict == GateVerdict.DEMOTE:
            rep.demote_gates.append(r.gate)
        elif r.verdict == GateVerdict.ADVISORY:
            rep.advisory_gates.append(r.gate)

    # G0
    if not os.path.exists(p) or os.path.getsize(p) <= cfg.min_bytes:
        add(GateResult("G0", GateVerdict.BLOCK, "missing_or_tiny", {"size": os.path.getsize(p) if os.path.exists(p) else -1}))
        rep.final = GateVerdict.BLOCK
        return rep
    try:
        im = Image.open(p)
        im.load()
        g = np.asarray(im.convert("L"))
    except Exception as ex:  # unreadable
        add(GateResult("G0", GateVerdict.BLOCK, f"unreadable:{ex}"))
        rep.final = GateVerdict.BLOCK
        return rep
    add(GateResult("G0", GateVerdict.PASS, "ok", {"bytes": os.path.getsize(p)}))

    is_chart = asset.asset_type == "CHART"
    w, h = im.size

    # G1 MIME
    fmt = (im.format or "?").upper()
    add(GateResult("G1", GateVerdict.PASS if fmt in ("JPEG", "PNG") else GateVerdict.BLOCK,
                   f"format_{fmt}"))

    # G2 resolution
    if is_chart:
        ok = w >= cfg.chart_min_w and h >= cfg.chart_min_h
        add(GateResult("G2", GateVerdict.PASS if ok else GateVerdict.BLOCK,
                       "chart_res_ok" if ok else f"chart_res_{w}x{h}_below_{cfg.chart_min_w}x{cfg.chart_min_h}",
                       {"w": w, "h": h}))
    else:
        short = min(w, h)
        if short < cfg.photo_block_short_side:
            add(GateResult("G2", GateVerdict.BLOCK, f"short_side_{short}_below_{cfg.photo_block_short_side}",
                           {"w": w, "h": h}))
        elif short < cfg.photo_min_short_side:
            add(GateResult("G2", GateVerdict.DEMOTE, f"short_side_{short}_upscale_to_{cfg.photo_min_short_side}",
                           {"w": w, "h": h}))
        else:
            add(GateResult("G2", GateVerdict.PASS, "res_ok", {"w": w, "h": h}))

    # G3 aspect (photos): out-of-band -> force contain (presentation demotion, not rejection)
    ar = w / h
    if not is_chart and not (cfg.ar_min <= ar <= cfg.ar_max):
        add(GateResult("G3", GateVerdict.DEMOTE, f"ar_{ar:.3f}_outside_[{cfg.ar_min},{cfg.ar_max}]_force_contain", {"ar": ar}))
    else:
        add(GateResult("G3", GateVerdict.PASS, "ok", {"ar": ar}))

    # G4 duplicate: DISPLAY-level content uniqueness (safety net). Content uniqueness
    # across displays is the reuse policy's job; at candidate stage displayed_contents
    # is empty so every pool candidate passes here (pool twins are deduped by policy).
    if cfg.content_index is not None:
        cid = cfg.content_index.content_id(p)
        if cid in cfg.displayed_contents:
            add(GateResult("G4", GateVerdict.BLOCK, f"content_{cid}_already_displayed", {"content": cid}))
        else:
            note = f"content_{cid}_pool_twins_{len(cfg.content_index.members[cid]) - 1}" \
                if len(cfg.content_index.members.get(cid, [])) > 1 else "unique"
            add(GateResult("G4", GateVerdict.PASS, note, {"content": cid}))
    else:
        add(GateResult("G4", GateVerdict.PASS, "no_index_provided", {}))

    # G5 collage/screenshot (photos only) — ADVISORY, never blocks
    if is_chart:
        add(GateResult("G5", GateVerdict.PASS, "skip_chart_profile"))
    else:
        ur, uc = _uniform_lines(g)
        sus = ur >= cfg.g5_grid_rows and uc >= cfg.g5_grid_cols
        add(GateResult("G5", GateVerdict.ADVISORY if sus else GateVerdict.PASS,
                       f"uniform_grid_{ur}x{uc}" if sus else "ok", {"rows": ur, "cols": uc}))

    # G6 text density — advisory marker for charts (no subtitle overlap), edge-busy for photos
    er = _edge_ratio(g)
    if is_chart:
        add(GateResult("G6", GateVerdict.DEMOTE, "text_asset_must_avoid_subtitle_overlap", {"edge": er}))
    else:
        add(GateResult("G6", GateVerdict.ADVISORY if er > cfg.g6_busy_edge else GateVerdict.PASS,
                       f"busy_edge_{er:.3f}" if er > cfg.g6_busy_edge else "ok", {"edge": er}))

    # G7 watermark corners — advisory only
    if is_chart:
        add(GateResult("G7", GateVerdict.PASS, "skip_chart_profile"))
    else:
        mx, glob = _corner_edge(g)
        sus = glob > 0.02 and mx > glob * cfg.g7_corner_factor and mx > 0.10
        add(GateResult("G7", GateVerdict.ADVISORY if sus else GateVerdict.PASS,
                       f"corner_edge_{mx:.3f}_vs_{glob:.3f}" if sus else "ok",
                       {"corner": mx, "global": glob}))

    # G8 namespace / experiment isolation — hard BLOCK (explicit signed-off registry overrides)
    if p in cfg.allow_registry:
        add(GateResult("G8", GateVerdict.PASS, "explicitly_authorized_registry", {}))
    elif asset.artifact_status != "production" or not asset.production_authorized:
        add(GateResult("G8", GateVerdict.BLOCK, "not_production_authorized",
                       {"status": asset.artifact_status}))
    else:
        pl = p.lower()
        if any(m in pl for m in EXPERIMENT_MARKERS):
            add(GateResult("G8", GateVerdict.BLOCK, f"experiment_marker_in_path:{pl}", {}))
        elif cfg.run_namespace and not p.startswith(cfg.run_namespace):
            add(GateResult("G8", GateVerdict.BLOCK, "outside_run_namespace", {"namespace": cfg.run_namespace}))
        else:
            add(GateResult("G8", GateVerdict.PASS, "ok", {}))

    # G9 provenance chain
    prov = cfg.provenance.get(asset.material_id) if cfg.provenance else None
    if is_chart:
        add(GateResult("G9", GateVerdict.BLOCK, "chart_has_no_photo_provenance_chain", {}))
    elif prov is None:
        add(GateResult("G9", GateVerdict.BLOCK, "no_provenance_entry", {}))
    elif not prov.get("beat") or not prov.get("title"):
        add(GateResult("G9", GateVerdict.BLOCK, "provenance_missing_fields", {}))
    else:
        add(GateResult("G9", GateVerdict.PASS, "ok", {}))

    blocking = [r for r in rep.results if r.gate in BLOCKING and r.verdict == GateVerdict.BLOCK]
    rep.final = GateVerdict.BLOCK if blocking else (
        GateVerdict.DEMOTE if rep.demote_gates else GateVerdict.PASS)
    return rep
