# -*- coding: utf-8 -*-
"""5-K 证据包：把本阶段的实测证据汇总为单个 JSON（只读产品文件，只写 docs/regression_2x/logs/）。

用法: python docs/regression_2x/phase5k_evidence.py
产出: docs/regression_2x/logs/phase5k_evidence.json
      docs/regression_2x/logs/phase5k_targeted_regression.txt
      docs/regression_2x/logs/phase5k_model_audit.json
"""
import glob
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
FINAL_TAG = "5.x-final-baseline"
FINAL_SHA = "be1717b9c7fe9ed9124be3876db64b5893915a4d0ffad56bd37eded5e6e2141e"
NEW_TAG = "5.x-post-final-maintenance-baseline"

ev = {"stage": "5-K Post-Final Maintenance", "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
      "authorization_baseline": {"tag": FINAL_TAG, "zip_sha256": FINAL_SHA, "must_be_untouched": True}}


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
        except Exception as exc:  # 证据收集失败必须显式记录，不得静默
            ev[name] = {"error": "{}: {}".format(type(exc).__name__, exc)}
            print("[ERR] ", name, "->", type(exc).__name__, exc)
        return fn
    return deco


# ---------- 1. 针对性回归（5-K 授权 item ①②④） ----------
@section("targeted_regression")
def _targeted():
    r = subprocess.run([PY, "tests\\maintenance_fixes_test.py"], cwd=str(ROOT), capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=3600)
    out = (r.stdout or "") + (r.stderr or "")
    (LOGS / "phase5k_targeted_regression.txt").write_text(out, encoding="utf-8")
    lines = [l.strip() for l in out.splitlines()]
    passed = [l for l in lines if l.startswith("PASS")]
    failed = [l for l in lines if l.startswith("FAIL")]
    total = re.findall(r"结果:\s*(\d+)\s*/\s*(\d+)\s*通过", out)
    s0s1s4 = []
    for m in re.finditer(r"d=(\S+)\s+S0=(\S+)\s+S1=(\S+)\s+S4=(\S+)\s+frames=(\S+)\s+r_fps=(\S+)\s+"
                         r"Δ\(S4-S0\)=(\S+)\s+S1短=(\S+)", out):
        s0s1s4.append({"d": float(m.group(1)), "S0_frozen_s": float(m.group(2)),
                       "S1_drift_s": float(m.group(3)), "S4_corrected_s": float(m.group(4)),
                       "S4_frames": m.group(5), "S4_r_fps": m.group(6),
                       "delta_S4_minus_S0_s": float(m.group(7)), "S1_short_by_s": float(m.group(8))})
    return {"rc": r.returncode, "passed": len(passed), "failed": len(failed),
            "ratio": "{}/{}".format(total[0][0], total[0][1]) if total else None,
            "failed_names": [l.split()[1] for l in failed],
            "three_shape_table": s0s1s4, "log": "logs/phase5k_targeted_regression.txt"}


# ---------- 2. 超时改动（item ②） ----------
@section("ffmpeg_timeouts")
def _timeouts():
    src = (ROOT / "src/video_studio/tools/ffmpeg_tool.py").read_text(encoding="utf-8")
    raw = src.split('if op == "raw":', 1)[1].split('if op == "probe":', 1)[0]
    ren = src.split('if op == "render":', 1)[1]
    return {"all_timeouts": sorted({int(x) for x in re.findall(r"timeout=(\d+)", src)}),
            "raw_op_7200": "timeout=7200" in raw, "render_op_7200": "timeout=7200" in ren,
            "no_1800_left": "timeout=1800" not in src}


# ---------- 3. 模型默认配置（item ③）+ 历史 id 清册（登记项 #59） ----------
@section("model_config")
def _models():
    cfg = json.loads((ROOT / "config/config.json").read_text(encoding="utf-8-sig"))
    router = (ROOT / "src/video_studio/llm/router.py").read_text(encoding="utf-8")
    tiers = {k: v.get("model") for k, v in (cfg.get("llm", {}).get("tiers") or {}).items()}
    official = re.search(r"CURRENT_OFFICIAL_MODELS\s*=\s*\{[^}]*\}", router)
    legacy = re.search(r"LEGACY_MODEL_IDS\s*=\s*\([^)]*\)", router)
    return {"tiers": tiers, "pricing_models": sorted((cfg["llm"].get("pricing") or {}).keys()),
            "router_CURRENT_OFFICIAL_MODELS": official.group(0) if official else None,
            "router_LEGACY_MODEL_IDS": legacy.group(0) if legacy else None,
            "router_fallback_points_to_legacy": 'tier_cfg.get("model", "deepseek-chat")' in router}


@section("legacy_model_id_audit")
def _legacy():
    ids = ["deepseek-chat", "deepseek-reasoner", "deepseek-v4-flash-vision-exp", "deepseek-v4-flash"]
    buckets = {"live_default_path": [], "frozen_tools_judge": [], "stage33_frozen": [],
               "tests_fixture": [], "scripts": [], "docs": [], "output_historical": []}
    roots = {"tests_fixture": ROOT / "tests", "scripts": ROOT / "scripts", "docs": ROOT / "docs"}
    for p in (ROOT / "src").rglob("*.py"):
        rel = p.relative_to(ROOT).as_posix()
        text = p.read_text(encoding="utf-8", errors="replace")
        hits = [i for i in ids if i in text]
        if not hits:
            continue
        if rel.startswith("src/video_studio/tools/") and p.name in (
                "sufficiency_judge.py", "llm_semantic_judge.py", "evidence_signal.py"):
            buckets["frozen_tools_judge"].append({"file": rel, "ids": hits})
        elif rel.startswith("src/video_studio/stage33/"):
            buckets["stage33_frozen"].append({"file": rel, "ids": hits})
        else:
            buckets["live_default_path"].append({"file": rel, "ids": hits})
    for key, root in roots.items():
        for p in root.rglob("*.py"):
            if "regression_2x" in p.as_posix() and key == "docs":
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
            hits = [i for i in ids if i in text]
            if hits:
                buckets[key].append({"file": p.relative_to(ROOT).as_posix(), "ids": hits})
    hist = 0
    hist_files = []
    for p in (ROOT / "output").rglob("*.py"):
        text = p.read_text(encoding="utf-8", errors="replace")
        hits = [i for i in ids if i in text]
        if hits:
            hist += 1
            if len(hist_files) < 40:
                hist_files.append({"file": p.relative_to(ROOT).as_posix(), "ids": hits})
    buckets["output_historical_count"] = hist
    buckets["output_historical_sample"] = hist_files
    buckets["counts"] = {k: len(v) for k, v in buckets.items() if isinstance(v, list)}
    (LOGS / "phase5k_model_audit.json").write_text(json.dumps(buckets, ensure_ascii=False, indent=1),
                                                  encoding="utf-8")
    return buckets


# ---------- 4. 禁止项守卫（与最终冻结基线逐字节一致） ----------
GUARD = ["src/video_studio/core/mm_judge.py", "src/video_studio/ops/mm_judge.py",
         "src/video_studio/tests/mm_judge_test.py", "tests/mm_judge_test.py",
         "tests/fixtures/mm_truth_set_v1.json", "tests/fixtures/mm_judge_truth_v1.json",
         "src/video_studio/core/multimodal.py", "src/video_studio/core/mm_temporal.py",
         "src/video_studio/core/mm_quality.py", "src/video_studio/core/mm_worker_clip.py",
         "src/video_studio/ops/multimodal.py", "src/video_studio/ops/mm_temporal.py",
         "src/video_studio/ops/mm_quality.py", "src/video_studio/ops/mm_judge.py",
         "src/video_studio/core/selection_review.py", "src/video_studio/ops/selection_review.py",
         "src/video_studio/core/audio.py", "src/video_studio/core/materials.py"]
GUARD += [p.relative_to(ROOT).as_posix()
          for p in sorted((ROOT / "tests/fixtures").glob("mm_truth_set_v2*.json"))]


@section("guard_groups_vs_frozen_baseline")
def _guard():
    with zipfile.ZipFile(BASE / "{}.zip".format(FINAL_TAG)) as z:
        names = {i.filename for i in z.infolist() if not i.is_dir()}
        rows = []
        for rel in sorted(set(GUARD)):
            live = ROOT / rel
            if not live.is_file():
                rows.append({"file": rel, "in_tree": False})
                continue
            live_sha = sha(live)
            in_zip = rel in names
            zip_sha = hashlib.sha256(z.read(rel)).hexdigest() if in_zip else None
            rows.append({"file": rel, "in_tree": True, "in_final_baseline": in_zip,
                         "identical_to_final": (zip_sha == live_sha) if in_zip else None,
                         "sha256_12": live_sha[:12]})
    changed = [r["file"] for r in rows if r.get("identical_to_final") is False]
    return {"checked": len(rows), "changed_vs_final": changed, "rows": rows}


# ---------- 5. 杂物清理（item ⑥） ----------
@section("cleanup_quarantine")
def _cleanup():
    qdir = ROOT / "output" / "_quarantine_20260921"
    man = json.loads((qdir / "MANIFEST.json").read_text(encoding="utf-8"))
    rows = []
    for m in man.get("moved", []):
        q = ROOT / m["quarantined_path"] if "quarantined_path" in m else None
        rows.append({"original": m.get("original_path"), "sha256_12": (m.get("sha256") or "")[:12],
                     "bytes": m.get("bytes"),
                     "still_in_original": (ROOT / m["original_path"]).exists() if m.get("original_path") else None,
                     "quarantined_exists": bool(q and q.is_file()),
                     "quarantined_sha_ok": bool(q and q.is_file() and sha(q) == m.get("sha256"))})
    leftovers = [p.relative_to(ROOT).as_posix() for p in (ROOT / "config").rglob("*")
                 if p.is_file() and (p.suffix in (".bak", ".tmp", ".orig") or p.name.endswith("~"))]
    return {"moved": rows, "config_leftovers": leftovers,
            "config_bak_absent": not (ROOT / "config" / "config.mock.json.bak").exists()}


# ---------- 6. 既有产物探针（登记项 #56/#57，只读） ----------
@section("existing_film_probe")
def _film():
    cfg = json.loads((ROOT / "config/config.json").read_text(encoding="utf-8-sig"))
    ffprobe = cfg["tools"]["ffmpeg"]["ffprobe"]
    check = json.loads((LOGS / "audit_p96efdc_film_check.json").read_text(encoding="utf-8"))
    film = Path(check["film"])
    r = subprocess.run([ffprobe, "-v", "error", "-print_format", "json", "-show_format", "-show_streams",
                        str(film)], capture_output=True, text=True, encoding="utf-8", errors="replace")
    d = json.loads(r.stdout or "{}")
    v = next((s for s in d.get("streams") or [] if s.get("codec_type") == "video"), {})
    a = next((s for s in d.get("streams") or [] if s.get("codec_type") == "audio"), {})
    audit_md = (R2 / "AUDIT_P96EFDC03E1AA.md").read_text(encoding="utf-8")
    m = re.search(r"\*\*(\d+\.\d+) s\*\*", audit_md)
    return {"film": str(film), "film_sha256": sha(film)[:16],
            "container_duration_s": round(float(d["format"]["duration"]), 3),
            "video_track_duration_s": round(float(v.get("duration") or 0), 3),
            "audio_track_duration_s": round(float(a.get("duration") or 0), 3),
            "video_frames": int(v.get("nb_frames") or 0),
            "audited_timeline_total_s": float(m.group(1)) if m else None,
            "video_short_by_s": (round(float(m.group(1)) - float(v.get("duration") or 0), 3)
                                 if m else None),
            "note": "既有产物未重渲染（登记 #57）；修复只对后续渲染生效"}


# ---------- 7. 全量回归（item ⑧） ----------
@section("full_regression_batch")
def _batch():
    # 本阶段批次结果已在冻结证据恢复时另存到 phase5k_batch_logs/（logs/ 下同名文件已回拷为旧内容）
    p = LOGS / "phase5k_batch_logs" / "phase3a_regression_batch.json"
    if not p.is_file():
        p = LOGS / "phase3a_regression_batch.json"
    rows = json.loads(p.read_text(encoding="utf-8"))
    return {"source": p.relative_to(ROOT).as_posix(),
            "items": len(rows), "as_expected": sum(1 for r in rows if r["as_expected"]),
            "unexpected": [r["name"] for r in rows if not r["as_expected"]],
            "network_items": [r["name"] for r in rows if r["needs_network"]],
            "rows": [{"name": r["name"], "rc": r["rc"], "expect": r["expect"],
                      "ratios": r.get("ratios"), "seconds": r.get("seconds"),
                      "needs_network": r["needs_network"]} for r in rows]}


@section("suites_summary")
def _suites():
    p = LOGS / "phase5k_batch_logs" / "suites_summary.json"
    if not p.is_file():
        p = LOGS / "suites_summary.json"
    rows = json.loads(p.read_text(encoding="utf-8"))
    bad = [r["suite"] for r in rows if r["rc"] != 0]
    return {"source": p.relative_to(ROOT).as_posix(), "suites": len(rows),
            "rc0": len(rows) - len(bad), "failed": bad,
            "tails": {r["suite"]: r.get("tail") for r in rows if r["rc"] != 0}}


@section("logs_restore")
def _restore():
    p = LOGS / "phase5k_logs_restore.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {"absent": True}


@section("battery_readonly_subset")
def _battery_ro():
    p = LOGS / "phase5k_battery_readonly.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {"absent": True}


@section("cost_probe")
def _cost():
    p = LOGS / "phase5k_cost_probe.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {"absent": True}


# ---------- 8. 基线（item ⑨）+ 最终基线未被改写 ----------
@section("baselines")
def _baselines():
    out = {}
    fz = BASE / "{}.zip".format(FINAL_TAG)
    with zipfile.ZipFile(fz) as z:
        out["final_zip_sha256"] = sha(fz)
        out["final_zip_unchanged"] = sha(fz) == FINAL_SHA
        out["final_zip_entries"] = len([i for i in z.infolist() if not i.is_dir()])
    nz = BASE / "{}.zip".format(NEW_TAG)
    nm = BASE / "baseline_manifest_{}.json".format(NEW_TAG)
    if nz.is_file() and nm.is_file():
        man = json.loads(nm.read_text(encoding="utf-8"))
        missing, drift = [], []
        for rel, rec in man["files"].items():
            lp = ROOT / rel
            if not lp.exists():
                missing.append(rel)
            elif sha(lp) != rec["sha256"]:
                drift.append(rel)
        with zipfile.ZipFile(nz) as z:
            zip_names = {i.filename for i in z.infolist() if not i.is_dir()}
        out["new"] = {"tag": NEW_TAG, "zip_sha256": sha(nz), "manifest_zip_sha256": man["zip_sha256"],
                      "zip_matches_manifest": sha(nz) == man["zip_sha256"],
                      "file_count": man["file_count"], "manifest_eq_zip_entries": set(man["files"]) == zip_names,
                      "missing_in_tree": len(missing), "drift_vs_tree": len(drift),
                      "drift_files": drift, "missing_files": missing,
                      "verdict": "MATCH" if not missing and not drift and set(man["files"]) == zip_names else "DIFF"}
    else:
        out["new"] = {"absent": True}
    return out


# ---------- 9. 文档登记（item ⑤⑦） ----------
@section("docs_registration")
def _docs():
    cl = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    heads = [(i, l) for i, l in enumerate(cl.splitlines(), 1) if l.startswith("## ")]
    want = {"5-H": "## 5-H", "5-I": "## 5-I", "5-J": "## 5-J",
            "5.x Final": "## 5.x Final", "5-K": "## 5-K"}
    found = {}
    for k, prefix in want.items():
        hit = next((i for i, l in heads if l.startswith(prefix)), None)
        found[k] = hit
    ki = (ROOT / "docs" / "KNOWN_ISSUES.md").read_text(encoding="utf-8")
    ids = re.findall(r"\|\s*\*\*#(\d+)\*\*\s*\|", ki)
    return {"changelog_headings": [{"line": i, "text": l[:90]} for i, l in heads[:8]],
            "changelog_stage_lines": found,
            "changelog_order_ok": all(v is not None for v in found.values())
            and found["5-K"] < found["5.x Final"] < found["5-J"] < found["5-I"] < found["5-H"],
            "changelog_line_count": len(cl.splitlines()),
            "v257_5g_line": next((i for i, l in heads if "V2.5.7" in l), None),
            "known_issues_ids": ["#{}".format(x) for x in ids],
            "known_issues_5k_registered": all("#{}".format(n) in ["#{}".format(x) for x in ids]
                                              for n in range(52, 65))}


(LOGS / "phase5k_evidence.json").write_text(json.dumps(ev, ensure_ascii=False, indent=1),
                                           encoding="utf-8")
print("\njson ->", LOGS / "phase5k_evidence.json")
