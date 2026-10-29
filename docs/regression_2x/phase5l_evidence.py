# -*- coding: utf-8 -*-
"""5-L 证据包：离线 mock 隔离 + M5d 钉定 + 重渲染验收 + 全量电池/批次 + 基线校验。

用法: python docs/regression_2x/phase5l_evidence.py
产出: docs/regression_2x/logs/phase5l_evidence.json
      docs/regression_2x/logs/phase5l_targeted_suites.txt
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
NEW_TAG = "5.x-post-final-maintenance-baseline"
R2_TAG = "5.x-post-final-maintenance-baseline-r2"
FINAL_TAG = "5.x-final-baseline"
FINAL_SHA = "be1717b9c7fe9ed9124be3876db64b5893915a4d0ffad56bd37eded5e6e2141e"

ev = {"stage": "5-L (5-K 已确认失败项修复)", "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}


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


@section("targeted_suites")
def _targeted():
    out_lines, res = [], {}
    for suite in ("maintenance_fixes_test.py", "offline_mock_test.py"):
        r = subprocess.run([PY, "tests\\" + suite], cwd=str(ROOT), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=3600)
        out = (r.stdout or "") + (r.stderr or "")
        out_lines.append("=" * 30 + " " + suite + " rc=" + str(r.returncode) + " " + "=" * 30)
        out_lines.append(out)
        m = re.findall(r"结果:\s*(\d+)\s*/\s*(\d+)\s*通过", out)
        res[suite] = {"rc": r.returncode, "ratio": "{}/{}".format(m[0][0], m[0][1]) if m else None,
                      "failed": [l.split()[1] for l in out.splitlines() if l.startswith("FAIL")]}
    (LOGS / "phase5l_targeted_suites.txt").write_text("\n".join(out_lines), encoding="utf-8")
    return res


@section("offline_mock_isolation")
def _mock():
    prod_p = ROOT / "config" / "config.json"
    mock_p = ROOT / "config" / "config.mock.json"
    prod = json.loads(prod_p.read_text(encoding="utf-8-sig"))
    mock = json.loads(mock_p.read_text(encoding="utf-8"))
    sites = {}
    for rel, needle in (("tests/cost_accounting_test.py", 'config" / "config.mock.json'),
                        ("tests/pipeline_mock.py", 'config" / "config.mock.json'),
                        ("docs/regression_2x/run_ingest_test.py", "config/config.mock.json"),
                        ("docs/regression_2x/run_all_tests.py", "config/config.mock.json")):
        sites[rel] = needle in (ROOT / rel).read_text(encoding="utf-8")
    prod_hits = [p.relative_to(ROOT).as_posix() for p in list((ROOT / "src").rglob("*.py"))
                 + [ROOT / "run.py"] if "config.mock.json" in p.read_text(encoding="utf-8",
                                                                          errors="replace")]
    return {"prod_config_sha256": sha(prod_p), "prod_has_mock": "mock" in (prod.get("llm") or {}),
            "prod_tiers": {k: v.get("model") for k, v in (prod.get("llm") or {}).get("tiers", {}).items()},
            "mock_config_sha256": sha(mock_p),
            "mock_responses_roles": len(((mock.get("llm") or {}).get("mock") or {}).get("responses") or {}),
            "mock_offline_block": mock.get("_offline"),
            "explicit_use_sites": sites,
            "production_code_referencing_mock": prod_hits,
            "cli_default_is_prod": "config.mock.json" not in (ROOT / "src/video_studio/cli.py")
            .read_text(encoding="utf-8")}


@section("m5d_repin")
def _m5d():
    mt = (ROOT / "tests" / "metrics_test.py").read_text(encoding="utf-8")
    man = json.loads((BASE / "baseline_manifest_{}.json".format(NEW_TAG)).read_text(encoding="utf-8"))
    cfg_now = sha(ROOT / "config" / "config.json")
    return {"pins_current_tag": "baseline_manifest_{}.json".format(NEW_TAG) in mt,
            "old_pin_removed": "baseline_manifest_3.x-final-baseline.json" not in mt,
            "pin_satisfiable": man["files"]["config/config.json"]["sha256"] == cfg_now,
            "pinned_sha12": man["files"]["config/config.json"]["sha256"][:12],
            "config_now_sha12": cfg_now[:12],
            "phase4ab_repinned": "baseline_manifest_{}.json".format(NEW_TAG)
            in (R2 / "phase4ab_evidence.py").read_text(encoding="utf-8"),
            "note": "测试/证据契约更新（钉定 tag 换代），断言强度不变；未修改任何业务语义"}


@section("rerender")
def _rerender():
    p = LOGS / "phase5l_render_verify.json"
    d = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {"absent": True}
    if "absent" in d:
        return d
    old, new = d.get("old_film_probe") or {}, d.get("new_film_probe") or {}
    tl = d.get("timeline_total_s")
    return {"new_task": d.get("new_task_row"), "new_film": d.get("new_film"),
            "old_film_unchanged": (d.get("old_film") or {}).get("unchanged"),
            "old_video_track_s": old.get("v_s"), "new_video_track_s": new.get("v_s"),
            "timeline_total_s": tl,
            "old_shortfall_s": round(tl - old.get("v_s", 0), 3) if tl else None,
            "new_shortfall_s": round(tl - new.get("v_s", 0), 3) if tl else None,
            "new_frames": new.get("frames"), "new_fmt_s": new.get("fmt_s"),
            "loudness": d.get("new_film_loudness"),
            "content_unchanged": {k: v.get("same") for k, v in
                                  (d.get("content_unchanged") or {}).items()},
            "claims_unchanged": d.get("claims_unchanged"),
            "decisions_unchanged": d.get("decisions_unchanged"),
            "attribution": d.get("attribution"),
            "films_changed": d.get("films_changed"), "films_added": d.get("films_added")}


@section("snapshots")
def _snaps():
    b = json.loads((LOGS / "phase5l_snapshot_before.json").read_text(encoding="utf-8"))
    a = json.loads((LOGS / "phase5l_snapshot_after.json").read_text(encoding="utf-8"))
    return {"artifacts_before": len(b["artifacts"]), "artifacts_after": len(a["artifacts"]),
            "artifacts_added": sorted(set(x["artifact_id"] for x in a["artifacts"])
                                      - set(x["artifact_id"] for x in b["artifacts"])),
            "claims": {"before": b["claims_by_status"], "after": a["claims_by_status"],
                       "same_ids": b["claim_ids"] == a["claim_ids"]},
            "decisions": {"before": b["decisions"]["count"], "after": a["decisions"]["count"],
                          "by_made_by_same": b["decisions"]["by_made_by"] == a["decisions"]["by_made_by"],
                          "selection_override": a["decisions"]["by_node"].get("selection_override")},
            "films_changed": [k for k in b["films"] if k in a["films"]
                              and b["films"][k]["sha256"] != a["films"][k]["sha256"]],
            "films_added": sorted(set(a["films"]) - set(b["films"]))}


@section("battery")
def _battery():
    p = LOGS / "phase5l_regression_summary.json"
    d = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {"absent": True}
    if "absent" in d:
        return d
    return {"steps": d["steps_count"], "all_rc_zero_raw": d["all_rc_zero_raw"],
            "rc_nonzero": d["rc_nonzero"], "frozen_logs_restored": d["frozen_logs_restored"],
            "frozen_logs_pre_count": d["frozen_logs_pre_count"],
            "changed": len(d["frozen_logs_changed"]), "added": len(d["frozen_logs_added"]),
            "deleted": len(d["frozen_logs_deleted"]), "total_seconds": d["total_seconds"],
            "per_step": [{"step": s["step"], "rc": s["rc"], "seconds": s["seconds"]}
                         for s in d["steps"]]}


@section("batch_and_suites")
def _batch():
    out = {}
    bp = LOGS / "phase5l_rerun" / "phase3a_regression_batch.json"
    if bp.is_file():
        rows = json.loads(bp.read_text(encoding="utf-8"))
        out["batch"] = {"items": len(rows), "as_expected": sum(1 for r in rows if r["as_expected"]),
                        "unexpected": [r["name"] for r in rows if not r["as_expected"]],
                        "rows": [{"name": r["name"], "rc": r["rc"], "ratios": r.get("ratios"),
                                  "tail": (r.get("tail") or [""])[0][:120]} for r in rows]}
    sp = LOGS / "phase5l_rerun" / "suites_summary.json"
    if sp.is_file():
        rows = json.loads(sp.read_text(encoding="utf-8"))
        bad = [r["suite"] for r in rows if r["rc"] != 0]
        out["suites"] = {"total": len(rows), "rc0": len(rows) - len(bad), "failed": bad}
    return out


@section("e2e_and_ingest")
def _e2e():
    out = {}
    ep = LOGS / "phase5l_rerun" / "3a_regression_batch.log"
    ip = LOGS / "phase5l_rerun" / "phase3a_e2e_mechanical.log"
    if ip.is_file():
        t = ip.read_text(encoding="utf-8", errors="replace")
        m = re.findall(r"RESULT:\s*(\{.*\})", t)
        out["e2e_mechanical_result"] = m[-1] if m else None
    bp = LOGS / "phase5l_rerun" / "phase3a_regression_batch.json"
    if bp.is_file():
        rows = json.loads(bp.read_text(encoding="utf-8"))
        for r in rows:
            if r["name"] in ("run_ingest_test", "e2e_mechanical", "metrics_readonly",
                             "phase2e_real_provider", "suite_all"):
                out[r["name"]] = {"rc": r["rc"], "as_expected": r["as_expected"],
                                  "ratios": r.get("ratios"), "tail": (r.get("tail") or [""])[-1][:140]}
    return out


@section("baselines")
def _baselines():
    out = {}
    fz = BASE / "{}.zip".format(FINAL_TAG)
    out["final"] = {"sha256": sha(fz), "unchanged": sha(fz) == FINAL_SHA}
    with zipfile.ZipFile(fz) as z:
        out["final"]["entries"] = len([i for i in z.infolist() if not i.is_dir()])
    for tag in (NEW_TAG, R2_TAG):
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
        out[tag] = {"zip_sha256": sha(zp), "manifest_zip_sha256": man["zip_sha256"],
                    "zip_matches_manifest": sha(zp) == man["zip_sha256"],
                    "file_count": man["file_count"], "manifest_eq_zip": set(man["files"]) == names,
                    "missing": len(missing), "drift": len(drift), "drift_files": drift[:12],
                    "verdict": "MATCH" if not missing and not drift and set(man["files"]) == names
                    else "DIFF"}
    return out


@section("known_issues_preserved")
def _ki():
    ki = (ROOT / "docs" / "KNOWN_ISSUES.md").read_text(encoding="utf-8")
    ids = ["#{}".format(x) for x in re.findall(r"\|\s*\*\*#(\d+)\*\*\s*\|", ki)]
    return {"count": len(ids), "has_52_to_64": all("#{}".format(n) in ids for n in range(52, 65)),
            "tail": ids[-6:], "note": "item 6：本阶段不处理 provenance 四件套，登记保持 #52–#64 不变"}


(LOGS / "phase5l_evidence.json").write_text(json.dumps(ev, ensure_ascii=False, indent=1),
                                           encoding="utf-8")
print("\njson ->", LOGS / "phase5l_evidence.json")
