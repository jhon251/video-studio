# -*- coding: utf-8 -*-
"""5-C fail-closed 负向验证（不写任何业务状态；仅写 logs/）。

N1 选材不在候选池 → 必须拒绝（HUMAN_SELECTION_NOT_IN_POOL）
N2 无人工归属（--by 空） → 必须拒绝（HUMAN_SELECTION_NO_REVIEWER）
N3 无理由（--reason 空） → 必须拒绝（HUMAN_SELECTION_NO_REASON）
N4 视觉模型不可用 → mm-review 必须 UNKNOWN:MMC_MM_UNAVAILABLE，且**不自动回退**到别的判据
   （通过 --config 指向一个模型目录不存在的临时配置；主配置不动）
N5 模型不可用时的 5-A multimodal-check 同样必须 UNKNOWN:MM_MODEL_MISSING，不产出 MATCH/MISMATCH

每个用例前后记录 DB sha256 与时间轴，断言"零写入 → 零变更"。

用法：python docs/regression_2x/phase5c_failclosed.py
产出：docs/regression_2x/logs/phase5c_failclosed.json
"""
import hashlib
import json
import pathlib
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(r"C:\mp4agent\video-studio")
LOGS = ROOT / "docs" / "regression_2x" / "logs"
DB = ROOT / "projects" / "video_studio.db"
PY = r"C:\python3.13\python.exe"
PID = "p_f4b466a4a024"
V6 = "a_fa4716cffb26"


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def run(args):
    p = subprocess.run([PY, "run.py"] + args, cwd=str(ROOT), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def timeline_now():
    payload = json.loads((ROOT / "projects" / PID / "artifacts" / (V6 + ".json"))
                         .read_text(encoding="utf-8"))
    return [(s.get("scene_id"), (s.get("selected_asset") or {}).get("asset_id"))
            for s in (payload.get("material_timeline") or [])]


# 临时配置：模型目录不存在（其余与主配置一致）——仅用于 N4/N5
cfg = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8-sig"))
cfg.setdefault("tools", {}).setdefault("multimodal", {})["model_dir"] = "models/__no_such_clip__"
tmpcfg = LOGS / "phase5c_tmp_cfg_no_model.json"
tmpcfg.write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf-8")

cases = []
tl0 = timeline_now()
db0 = sha(DB)


def case(cid, desc, args, expect_codes, expect_rc_nonzero=True, parse_json=False):
    rc, out = run(args)
    rec = {"id": cid, "desc": desc, "args": args, "rc": rc, "db_unchanged": sha(DB) == db0,
           "timeline_unchanged": timeline_now() == tl0,
           "codes_found": [c for c in expect_codes if c in out], "expect_codes": expect_codes}
    if parse_json:
        try:
            rec["parsed"] = json.loads(out[out.index("{"):out.rindex("}") + 1])
        except (ValueError, json.JSONDecodeError):
            rec["parsed"] = None
    else:
        rec["output_tail"] = out.strip().splitlines()[-6:]
    rec["pass"] = bool((rc != 0) == expect_rc_nonzero and rec["codes_found"]
                       and rec["db_unchanged"] and rec["timeline_unchanged"])
    cases.append(rec)
    print(cid, "rc=", rc, "pass=", rec["pass"], "codes=", rec["codes_found"],
          "db_unchanged=", rec["db_unchanged"], "tl_unchanged=", rec["timeline_unchanged"])
    return rec


case("N1", "选定素材不在候选池 → 拒绝（真实写路径，未加 --dry-run）",
     ["select-candidate", PID, "--scene", "S06", "--asset", "asset_deadbeef0000",
      "--by", "human:project-owner", "--reason", "5-C 负向测试：不存在的素材"],
     ["HUMAN_SELECTION_NOT_IN_POOL"])
case("N2", "无人工归属（--by 空）→ 拒绝",
     ["select-candidate", PID, "--scene", "S06", "--asset", "asset_f3cf2b80432d",
      "--by", "   ", "--reason", "5-C 负向测试：无归属"],
     ["HUMAN_SELECTION_NO_REVIEWER"])
case("N3", "无理由（--reason 空）→ 拒绝",
     ["select-candidate", PID, "--scene", "S06", "--asset", "asset_f3cf2b80432d",
      "--by", "human:project-owner", "--reason", "  "],
     ["HUMAN_SELECTION_NO_REASON"])
case("N4", "视觉模型目录缺失 → mm-review 必须 UNKNOWN:MMC_MM_UNAVAILABLE（不自动回退）",
     ["--config", str(tmpcfg), "mm-review", PID, "--artifact", V6, "--json"],
     ["MMC_MM_UNAVAILABLE"], parse_json=True, expect_rc_nonzero=False)
case("N5", "视觉模型目录缺失 → multimodal-check 必须 UNKNOWN:MM_MODEL_MISSING",
     ["--config", str(tmpcfg), "multimodal-check", PID, "--artifact", V6, "--json"],
     ["MM_MODEL_MISSING"], parse_json=True, expect_rc_nonzero=False)

# 补充断言
n4 = next(c for c in cases if c["id"] == "N4")["parsed"] or {}
n5 = next(c for c in cases if c["id"] == "N5")["parsed"] or {}
n4_meta = n4.get("meta") or {}
summary = {
    "cases": cases,
    "zero_writes_all": all(c["db_unchanged"] and c["timeline_unchanged"] for c in cases),
    "n1_n3_all_rc_nonzero": all(c["rc"] != 0 for c in cases[:3]),
    "n4_n5_readonly_rc_zero": all(c["rc"] == 0 for c in cases[3:]),
    "n4_report_status": n4.get("status"), "n4_report_code": n4.get("code"),
    "n4_scenes_statuses": [(s.get("scene_id"), s.get("status"), s.get("code"))
                           for s in (n4.get("scenes") or [])],
    "n4_any_candidate": any((s.get("candidates") or []) for s in (n4.get("scenes") or [])),
    "n4_readonly": n4_meta.get("readonly"), "n4_db_writes": n4_meta.get("db_writes"),
    "n4_production_writes": n4_meta.get("production_writes"),
    "n4_select_candidate_called": n4_meta.get("select_candidate_called"),
    "n4_redo_triggered": n4_meta.get("redo_triggered"),
    "n4_worker_code": n4_meta.get("worker_code"),
    "n5_counts": n5.get("counts"), "n5_applied": n5.get("applied"),
    "n5_scene_verdicts": [(s.get("scene_id"), s.get("verdict"), s.get("code"))
                          for s in (n5.get("scenes") or [])],
    "n5_all_unknown": all(s.get("verdict") == "UNKNOWN" for s in (n5.get("scenes") or [])),
    "n5_no_match_no_mismatch": (n5.get("counts") or {}).get("MATCH") == 0
    and (n5.get("counts") or {}).get("MISMATCH") == 0,
    "db_sha256_before": db0, "db_sha256_after": sha(DB),
    "timeline_before": tl0, "timeline_after": timeline_now(),
}
_ok = (all(c["pass"] for c in cases) and summary["zero_writes_all"]
       and summary["n4_report_status"] == "UNKNOWN"
       and summary["n4_report_code"] == "MMC_MM_UNAVAILABLE"
       and not summary["n4_any_candidate"] and summary["n4_db_writes"] == 0
       and summary["n4_production_writes"] == 0 and summary["n4_redo_triggered"] == 0
       and summary["n4_select_candidate_called"] == 0
       and summary["n5_all_unknown"] and summary["n5_no_match_no_mismatch"]
       and summary["n5_applied"] is False)
summary["ALL_PASS"] = bool(_ok)
(LOGS / "phase5c_failclosed.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1),
                                             encoding="utf-8")
print("\nsummary:", json.dumps({k: v for k, v in summary.items() if k != "cases"},
                               ensure_ascii=False, indent=1))
print("ALL PASS:", summary["ALL_PASS"])
print("written", LOGS / "phase5c_failclosed.json")
