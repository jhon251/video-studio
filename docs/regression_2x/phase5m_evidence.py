# -*- coding: utf-8 -*-
"""5-M 证据包：字幕化改造的单元/视觉/真实成片/覆盖率/电池/基线证据。

用法: python docs/regression_2x/phase5m_evidence.py
产出: docs/regression_2x/logs/phase5m_evidence.json
      docs/regression_2x/logs/phase5m_affected_suites.txt
"""
import hashlib
import json
import re
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
R2 = ROOT / "docs" / "regression_2x"
LOGS = R2 / "logs"
BASE = R2 / "baseline"
PY = sys.executable
sys.path.insert(0, str(ROOT / "src"))
from video_studio.core.captions import build_cues  # noqa: E402

TAGS = ("5.x-post-final-maintenance-baseline-r2", "5.x-post-final-maintenance-baseline-r3")
FINAL_TAG = "5.x-final-baseline"
FINAL_SHA = "be1717b9c7fe9ed9124be3876db64b5893915a4d0ffad56bd37eded5e6e2141e"
PID = "p_96efdc03e1aa"

ev = {"stage": "5-M（成片字幕化）", "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def section(name):
    def deco(fn):
        try:
            ev[name] = fn()
            print("[ok]  ", name)
        except Exception as exc:
            ev[name] = {"error": "{}: {}".format(type(exc).__name__, exc)}
            print("[ERR] ", name, "->", type(exc).__name__, exc)
        return fn
    return deco


@section("caption_unit_and_affected_suites")
def _suites():
    out_lines, res = [], {}
    for s in ("captions_test.py", "scene_assembly_test.py", "narration_contract_test.py",
              "maintenance_fixes_test.py", "offline_mock_test.py", "attribution_compliance_test.py",
              "pipeline_mock.py"):
        r = subprocess.run([PY, "tests\\" + s], cwd=str(ROOT), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=3600)
        out = (r.stdout or "") + (r.stderr or "")
        out_lines.append("=" * 26 + " " + s + " rc=" + str(r.returncode) + " " + "=" * 26)
        out_lines.append(out)
        m = re.findall(r"结果:\s*(\d+)\s*/\s*(\d+)\s*通过", out)
        res[s] = {"rc": r.returncode, "ratio": "{}/{}".format(m[0][0], m[0][1]) if m else None,
                  "failed": [l.split()[1] for l in out.splitlines() if l.startswith("FAIL")]}
    (LOGS / "phase5m_affected_suites.txt").write_text("\n".join(out_lines), encoding="utf-8")
    return res


@section("render_v9")
def _render():
    p = LOGS / "phase5m_render_verify.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {"absent": True}


@section("visual_probe")
def _probe():
    p = LOGS / "phase5m_caption_probe" / "report.json"
    d = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}
    return {"probe_frames": d.get("frames"), "probe_mp4": d.get("mp4"),
            "probe_cues": d.get("cues"),
            "old_block_frame": "output/_5m_frames/v8_t20.png（旧：整段文案居中铺满）",
            "new_frames": sorted(x.relative_to(ROOT).as_posix()
                                 for x in (LOGS / "phase5m_frames").glob("*.png"))}


@section("coverage")
def _coverage():
    segs = None
    for p in sorted((ROOT / "projects" / PID / "artifacts").glob("*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:                                        # noqa: BLE001
            continue
        s = d.get("segments")
        if isinstance(s, list) and s and isinstance(s[0], dict) and "narration" in s[0] \
                and "duration_s" in s[0]:
            segs = s
            break
    if not segs:
        return {"absent": True}
    cues = build_cues([{"narration": x["narration"], "duration_s": x.get("duration_s")}
                       for x in segs])
    total = sum(max(float(x.get("duration_s") or 0), 3.0) for x in segs)
    disp = sum(c["dur"] for c in cues)
    gaps, prev = [], 0.0
    for c in cues:
        if c["start"] > prev:
            gaps.append(round(c["start"] - prev, 2))
        prev = c["end"]
    if prev < total:
        gaps.append(round(total - prev, 2))
    per_scene = []
    for si in range(len(segs)):
        cs = [c for c in cues if c["segment_index"] == si]
        per_scene.append({"segment": si, "cues": len(cs),
                          "chars": len(segs[si]["narration"]),
                          "display_s": round(sum(c["dur"] for c in cs), 1),
                          "window_s": float(segs[si]["duration_s"] or 0),
                          "coverage_pct": round(100 * sum(c["dur"] for c in cs)
                                                / float(segs[si]["duration_s"] or 1), 1)})
    return {"cues": len(cues), "display_total_s": round(disp, 1), "timeline_s": total,
            "coverage_pct": round(100 * disp / total, 1),
            "gap_mean_s": round(sum(gaps) / len(gaps), 2) if gaps else None,
            "gap_max_s": max(gaps) if gaps else None,
            "gaps_over_5s": sum(1 for g in gaps if g > 5),
            "per_scene": per_scene}


@section("battery")
def _battery():
    p = LOGS / "phase5m_regression_summary.json"
    d = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {"absent": True}
    if "absent" in d:
        return d
    return {"steps": d["steps_count"], "all_rc_zero_raw": d["all_rc_zero_raw"],
            "rc_nonzero": d["rc_nonzero"], "frozen_logs_restored": d["frozen_logs_restored"],
            "changed": len(d["frozen_logs_changed"]), "added": len(d["frozen_logs_added"]),
            "deleted": len(d["frozen_logs_deleted"]), "total_seconds": d["total_seconds"],
            "per_step": [{"step": s["step"], "rc": s["rc"], "seconds": s["seconds"]}
                         for s in d["steps"]]}


@section("batch_and_suites")
def _batch():
    out = {}
    bp = LOGS / "phase5m_rerun" / "phase3a_regression_batch.json"
    if bp.is_file():
        rows = json.loads(bp.read_text(encoding="utf-8"))
        out["batch"] = {"items": len(rows), "as_expected": sum(1 for r in rows if r["as_expected"]),
                        "unexpected": [r["name"] for r in rows if not r["as_expected"]]}
    sp = LOGS / "phase5m_rerun" / "suites_summary.json"
    if sp.is_file():
        rows = json.loads(sp.read_text(encoding="utf-8"))
        bad = [r["suite"] for r in rows if r["rc"] != 0]
        out["suites"] = {"total": len(rows), "rc0": len(rows) - len(bad), "failed": bad}
    ip = LOGS / "phase5m_rerun" / "phase3a_e2e_mechanical.log"
    if ip.is_file():
        m = re.findall(r"RESULT:\s*(\{.*\})", ip.read_text(encoding="utf-8", errors="replace"))
        out["e2e_mechanical_result"] = m[-1] if m else None
    rp = LOGS / "phase5m_rerun" / "phase3a_run_ingest_test.log"
    if rp.is_file():
        t = rp.read_text(encoding="utf-8", errors="replace")
        out["run_ingest_verdict"] = "PASS" if "VERDICT: PASS" in t else "NOT_PASS"
    return out


@section("code_fingerprint")
def _fp():
    """指纹口径：`after`（契约修正后的基线）与 `now`（冻结前重算）必须一致 ——
    即"电池跑的就是将要冻结的代码/测试"；`before` 是 2026-09-21 首轮前的快照，
    其与 `after` 的差异 = 本阶段按测试契约修正的 `tests/strip_v2_test.py`（已知、已披露）。"""
    def load(n):
        p = LOGS / "phase5m_code_fingerprint_{}.json".format(n)
        return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None
    a, n, b = load("after"), load("now"), load("before")
    fa, fb, fn = (a or {}).get("files", {}), (b or {}).get("files", {}), (n or {}).get("files", {})
    delta_ba = sorted(k for k in set(fa) | set(fb) if fa.get(k) != fb.get(k))
    return {"before": (b or {}).get("aggregate_sha256"),
            "after": (a or {}).get("aggregate_sha256"),
            "now": (n or {}).get("aggregate_sha256"),
            "battery_code_equals_freeze_code": bool(a and n
                                                    and a["aggregate_sha256"] == n["aggregate_sha256"]),
            "before_vs_after_delta_files": delta_ba}


@section("baselines")
def _baselines():
    out = {}
    fz = BASE / "{}.zip".format(FINAL_TAG)
    out["final"] = {"sha256": sha(fz), "unchanged": sha(fz) == FINAL_SHA}
    with zipfile.ZipFile(fz) as z:
        out["final"]["entries"] = len([i for i in z.infolist() if not i.is_dir()])
    for tag in TAGS:
        zp, mp = BASE / "{}.zip".format(tag), BASE / "baseline_manifest_{}.json".format(tag)
        if not zp.is_file() or not mp.is_file():
            out[tag] = {"absent": True}
            continue
        man = json.loads(mp.read_text(encoding="utf-8"))
        missing, drift = [], []
        for rel, rec in man["files"].items():
            lp = ROOT / rel
            if not lp.exists():
                missing.append(rel)
            elif sha(lp) != rec["sha256"]:
                drift.append(rel)
        with zipfile.ZipFile(zp) as z:
            names = {i.filename for i in z.infolist() if not i.is_dir()}
        out[tag] = {"zip_sha256": sha(zp), "file_count": man["file_count"],
                    "zip_matches_manifest": sha(zp) == man["zip_sha256"],
                    "manifest_eq_zip": set(man["files"]) == names,
                    "missing": len(missing), "drift": len(drift), "drift_files": drift[:10],
                    "verdict": "MATCH" if not missing and not drift
                    and set(man["files"]) == names else "DIFF"}
    return out


@section("known_issues")
def _ki():
    ki = (ROOT / "docs" / "KNOWN_ISSUES.md").read_text(encoding="utf-8")
    ids = ["#{}".format(x) for x in re.findall(r"\|\s*\*\*#(\d+)\*\*\s*\|", ki)]
    return {"count": len(ids), "tail": ids[-5:],
            "has_52_to_66": all("#{}".format(n) in ids for n in range(52, 67)),
            "new_resolved": "#66" in ids}


(LOGS / "phase5m_evidence.json").write_text(json.dumps(ev, ensure_ascii=False, indent=1),
                                            encoding="utf-8")
print("\njson ->", LOGS / "phase5m_evidence.json")
