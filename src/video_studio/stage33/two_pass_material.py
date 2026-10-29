"""two_pass_material (Stage 12.25): production two-pass material flow.

PASS 1 — the frozen pipeline exactly as shipped: frozen retrieval -> frozen
pool_precision rerank -> frozen gate (head-6) -> frozen V1 -> frozen CV-2
(Top-3 policy) -> eligibility. Untouched.

PASS 2 — ONLY for beats still EMPTY after pass 1: refetch the pool (frozen),
add non-Commons source candidates (Pexels adapter, same Candidate Contract),
rerank with the frozen pool_precision, then rebuild ONLY the head-slice with
the independent source_quota module (2 seats, Pexels-first), and send the
slice through the SAME frozen Gate -> V1 -> CV-2. Quota never qualifies
material by itself; every candidate is judged by the frozen chain.

Ok beats never enter pass 2 (no extra cost, no regression by construction).
A verdict cache (prefix-tolerant, built from accumulated Stage 12 traces)
avoids duplicate LLM/vision calls; every fresh call is counted and traced.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from video_studio.stage33 import beat_retrieval, pool_precision
from video_studio.stage33 import candidate_quality_gate
from video_studio.stage33.source_quota import quota_slice
from video_studio.stage31.ranking import semantic_match_score

QUALIFIED = ("USABLE", "CONDITIONALLY_USABLE")
QUOTA_SEATS = 2  # Production Default (Stage 12.24 verdict), two-pass only


class VerdictCache:
    """(beat_key, title-prefix-tolerant) verdict store built from accumulated
    Stage 12 traces; production runs may persist new verdicts into it."""

    def __init__(self, store_path: Path | None = None):
        self.gate: dict[str, dict] = {}   # beat -> {title: (keep, reason)}
        self.cv2: dict[str, dict] = {}    # beat -> {title: (fit, label)}
        self.store_path = store_path
        if store_path is not None and store_path.exists():
            s = json.loads(store_path.read_text(encoding="utf-8"))
            self.gate.update({k: {t: tuple(v) for t, v in g.items()}
                              for k, g in s.get("gate", {}).items()})
            self.cv2.update({k: {t: tuple(v) for t, v in g.items()}
                             for k, g in s.get("cv2", {}).items()})

    def save(self):
        if self.store_path is None:
            return
        self.store_path.write_text(json.dumps(
            {"gate": {k: g for k, g in self.gate.items()},
             "cv2": self.cv2}, ensure_ascii=False), encoding="utf-8")

    def load_stage12_traces(self, s33_dir: Path):
        V2 = {(r["shot_id"] + "-" + r["beat_id"]): r for r in
              json.loads((s33_dir / "stage12_13_t1_fix/recovery_v2.json")
                         .read_text(encoding="utf-8"))["results"]}
        for k, r in V2.items():
            for g in r.get("gate_verdicts", []):
                self.gate.setdefault(k, {})[g["candidate_id"]] = (
                    g.get("keep") is True, g.get("reason", ""))
            t1 = r.get("cv2_top1") or {}
            if t1.get("title"):
                self.cv2.setdefault(k, {})[t1["title"]] = (
                    t1.get("vision_fit"), t1.get("labels"))
        for name, sub in (("stage12_16_top2/results_top2.json", "beats"),
                          ("stage12_18_top3/results_top3.json", "beats"),
                          ("stage12_20_gate_top12/results_top12.json", "beats"),
                          ("stage12_23_pexels/results_pexels.json", "beats")):
            p = s33_dir / name
            if not p.exists():
                continue
            for k, e in json.loads(p.read_text(encoding="utf-8"))[sub].items():
                for g in e.get("new_keeps", []) or []:
                    self.gate.setdefault(k, {})[g["title"]] = (
                        True, g.get("reason", ""))
                for g in e.get("new_rejects", []) or []:
                    self.gate.setdefault(k, {})[g["title"]] = (
                        False, g.get("reason", ""))
                for j in e.get("gate_judged", []) or []:
                    self.gate.setdefault(k, {})[j["title"]] = (
                        j.get("keep") is True, j.get("reason", ""))
                for j in (e.get("cv2_judged", []) or []) + \
                         (e.get("coverage_arm", []) or []):
                    if j.get("fit") is not None or j.get("label") is not None:
                        self.cv2.setdefault(k, {})[j["title"]] = (
                            j.get("fit"), j.get("label"))
        p = s33_dir / "stage12_24_quota/results_quota.json"
        if p.exists():
            for k, e in json.loads(p.read_text(encoding="utf-8"))["beats"].items():
                for qn, cfg in e.get("configs", {}).items():
                    for j in cfg.get("gate_judged", []) or []:
                        self.gate.setdefault(k, {})[j["title"]] = (
                            j.get("keep") is True, j.get("reason", ""))
                    for j in cfg.get("cv2_judged", []) or []:
                        if j.get("fit") is not None or j.get("label") is not None:
                            self.cv2.setdefault(k, {})[j["title"]] = (
                                j.get("fit"), j.get("label"))

        # 12.16 / 12.18 store verdicts as flat per-beat fields
        for name in ("stage12_16_top2/results_top2.json",
                     "stage12_18_top3/results_top3.json"):
            p = s33_dir / name
            if not p.exists():
                continue
            for k, e in json.loads(p.read_text(encoding="utf-8"))["beats"].items():
                for pref in ("top1", "rank2", "rank3"):
                    t = e.get(f"{pref}_title")
                    lab = e.get(f"{pref}_label")
                    if t and lab is not None and e.get(f"{pref}_available", True):
                        self.cv2.setdefault(k, {})[t] = (
                            e.get(f"{pref}_fit"), lab)

    @staticmethod
    def _lookup(store: dict, beat: str, title: str):
        b = store.get(beat) or {}
        if title in b:
            return b[title], True
        for t, v in b.items():
            if len(t) < len(title) and title.startswith(t):
                return v, True
        return None, False


def _cv2_judge(key, acq_dir, sid, bid, nar, intent, title, thumburl, stats):
    from video_studio.stage33.asset_cache import acquire_asset
    r = acquire_asset(acq_dir, f"tp_{sid}_{bid}_{abs(hash(title)) % 10**8}",
                      thumburl, ext_hint="image")
    lp = r.get("local_path")
    if not (lp and str(r.get("status", "")).lower() == "ok"):
        return {"error": "download_failed"}
    from video_studio.stage33.vision_controlled import vision_call
    v = vision_call(key, Path(lp), nar, intent["visual_intent"][:200])
    stats["cv2_fresh"] += 1
    p = v.get("parsed") or {}
    return {"fit": p.get("visual_fit_score"), "label": p.get("visual_usability")}


def _run_slice(slice_head, keeps_ctx, gid, cc, gate, th, intent, nar, qctx,
               acq_dir, sid, bid, key, stats, trace):
    keeps = []
    for c in slice_head:
        title = c["title"]
        v, hit = VerdictCache._lookup(gid, sid_bid_key(sid, bid), title)
        if v is not None:
            keep, reason = v
        else:
            g = candidate_quality_gate.judge(th, intent["visual_intent"], c)
            keep, reason = g.get("keep") is True, (g.get("reason") or "")
            gid.setdefault(sid_bid_key(sid, bid), {})[title] = (keep, reason)
            stats["gate_fresh"] += 1
            time.sleep(0.3)
        trace["gate"].append({"title": title[:56], "keep": keep,
                              "source": c.get("src", {}).get("source", "commons"),
                              "cache_hit": hit, "fresh": not hit,
                              "reason": reason[:70]})
        if keep:
            v1s = semantic_match_score(
                CandShim(c["title"], c.get("visual_description", "")),
                IShim(nar, intent), qctx)
            keeps.append((v1s, c))
    keeps.sort(key=lambda x: -x[0])
    cv2rows = []
    for v1s, c in keeps[:3]:
        title = c["title"]
        v, hit = VerdictCache._lookup(cc, sid_bid_key(sid, bid), title)
        if v is not None and (v[0] is not None or v[1] is not None):
            fit, lab = v
            fresh_v = False
        else:
            row = _cv2_judge(key, acq_dir, sid, bid, nar, intent, title,
                             c["thumburl"], stats)
            if "error" in row:
                trace["cv2"].append({"title": title[:56], **row})
                continue
            fit, lab = row["fit"], row["label"]
            cc.setdefault(sid_bid_key(sid, bid), {})[title] = (fit, lab)
            fresh_v = True
        cv2rows.append({"title": title[:56],
                        "source": c.get("src", {}).get("source", "commons"),
                        "v1": round(v1s, 2), "fit": fit, "label": lab,
                        "cache_hit": hit, "fresh": fresh_v})
        trace["cv2"].append(cv2rows[-1])
        if lab in QUALIFIED:
            trace["final"] = {"choice": title[:56], "fit": fit, "label": lab,
                              "source": c.get("src", {}).get("source", "commons"),
                              "thumburl": c.get("thumburl"),
                              "pexels_id": (c.get("src") or {}).get("pexels_id"),
                              "photographer": (c.get("src") or {}).get("photographer"),
                              "license": (c.get("src") or {}).get("license")}
            return trace, True
    trace["final"] = {"choice": None}
    return trace, False


def sid_bid_key(sid, bid):
    return f"{sid}-{bid}"


class CandShim:
    def __init__(self, title, desc=""):
        self.visual_description = desc
        self.raw = {"title": title}


class IShim:
    def __init__(self, nar, intent):
        self.subject = intent.get("visual_subject", "")
        self.action = ""
        self.concepts_pos = intent.get("concepts_pos") or []
        self.concepts_neg = intent.get("concepts_neg") or []
        self.narration = nar


def acquire_beat_material(sid, bid, narration, intent, tiers, pref_intent,
                          th, key, pexels_key, acq_dir, cache: VerdictCache,
                          pexels_adapter, stats=None, t3_queries=None):
    """Two-pass production material flow for one beat. Returns a full
    provenance trace dict."""
    sid_b = sid_bid_key(sid, bid)
    stats = stats if stats is not None else {"gate_fresh": 0, "cv2_fresh": 0,
                                             "pexels_api": 0, "t3_llm": 0}
    qctx = " ".join(tiers["precise"] + tiers["relaxed"] + tiers["counterpart"]
                    + (t3_queries or []))

    def new_trace(pass_name):
        return {"pass": pass_name, "gate": [], "cv2": [], "final": None}

    # ---------- PASS 1: frozen pipeline ----------
    base = beat_retrieval.retrieve_beat_candidates(pref_intent, tiers, limit=8)["merged"]
    rr1 = pool_precision.rerank(base, tiers, pref_intent.get("asset_type_hint", "IMAGE"))
    gid = cache.gate
    cc = cache.cv2
    tr1, ok1 = _run_slice(rr1["merged"][:6], None, gid, cc, None, th, intent,
                          narration, qctx, acq_dir, sid, bid, key, stats, new_trace("pass1"))
    tr1["head_sources"] = [c.get("src", {}).get("source", "commons")
                           for c in rr1["merged"][:6]]
    if ok1:
        tr1["pass2"] = "skipped (material_ok in pass 1)"
        return {"ok": True, "pass1": tr1, "pass2": None, "stats": stats}

    # ---------- PASS 2: quota slice for non-Commons sources ----------
    px = pexels_adapter(tiers["precise"][:2] + (t3_queries or [])[:2], pexels_key)
    stats["pexels_api"] += len(px.get("trace", []))
    seen = {c["title"] for c in base}
    px_new = [c for c in px["candidates"] if c["title"] not in seen]
    rr2 = pool_precision.rerank(
        base + px_new,
        {"precise": tiers["precise"], "relaxed": tiers["relaxed"],
         "counterpart": tiers["counterpart"] + (t3_queries or [])},
        pref_intent.get("asset_type_hint", "IMAGE"))
    sl = quota_slice(rr2["merged"], QUOTA_SEATS)
    armA_head = [c["title"][:56] for c in rr1["merged"][:6]]
    tr2 = new_trace("pass2")
    tr2["quota_seats"] = QUOTA_SEATS
    tr2["source_seats"] = sl["trace"]["source_seats"]
    tr2["displaced_candidates"] = [t for t in armA_head
                                   if t not in [c["title"][:56] for c in sl["head"]]]
    tr2["provenance"] = [{"seat": j,
                          "source": c.get("src", {}).get("source", "commons"),
                          "title": c["title"][:56],
                          "pexels_id": (c.get("src") or {}).get("pexels_id"),
                          "photographer": (c.get("src") or {}).get("photographer"),
                          "license": (c.get("src") or {}).get("license")}
                         for j, c in enumerate(sl["head"], 1)]
    tr2, ok2 = _run_slice(sl["head"], None, gid, cc, None, th, intent,
                          narration, qctx, acq_dir, sid, bid, key, stats, tr2)
    return {"ok": ok2, "pass1": tr1, "pass2": tr2, "stats": stats}
