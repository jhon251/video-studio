# -*- coding: utf-8 -*-
"""5-C append-only / 未授权镜头 / attribution / 许可门禁 核验（只读）。

断言：
 A. 追加性：替换前的每一条 decisions / changelog 行在替换后逐字段不变；新行是追加（id/时间更大）
 B. 旧版本保留：v1..v5 的 render_output 产物文件与成片文件哈希不变、文件仍在
 C. 未授权镜头未被改动：仅 S06 的素材指针变化；S01–S05 的素材与窗口完全一致；S06 窗口不变
 D. attribution↔时间轴 1:1，且 attribution 条目里的素材 sha256 与磁盘一致
 E. 许可门禁：外部素材 license_class 必须已清（PUBLIC_DOMAIN/FREE_ATTRIBUTION），
    并以 core.materials 的真实门禁函数复核（license_gate_applies / license_block_reason）
 F. 渲染自检：material_verification 覆盖 6 镜头 0 失败

用法：python docs/regression_2x/phase5c_append_only.py
产出：docs/regression_2x/logs/phase5c_append_only.json
"""
import hashlib
import json
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
LOGS = ROOT / "docs" / "regression_2x" / "logs"
PID = "p_f4b466a4a024"
from video_studio.core.materials import license_block_reason, license_gate_applies  # noqa: E402

before = json.loads((LOGS / "phase5c_before.json").read_text(encoding="utf-8"))
after = json.loads((LOGS / "phase5c_after.json").read_text(encoding="utf-8"))
cmpj = json.loads((LOGS / "phase5c_compare.json").read_text(encoding="utf-8"))


def sha(p):
    try:
        return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
    except (OSError, TypeError):
        return None


def recorded_hash_ok(artifact_path, recorded_sha, recorded_size):
    """平台记录口径：sha256 = sha256(**LF 归一化**后的产物文本)[:16]，size = LF 字节数。

    （`Engine.write_artifact` 哈希的是内存中的 raw 文本，而 `Path.write_text` 在 Windows 上
    会把 \\n 落盘为 \\r\\n；因此复算时必须先做 CRLF→LF 归一化。）
    """
    try:
        raw = pathlib.Path(artifact_path).read_bytes().replace(b"\r\n", b"\n")
    except OSError:
        return False, False, None, None
    h = hashlib.sha256(raw).hexdigest()[:16]
    return h == recorded_sha, len(raw) == recorded_size, h, len(raw)


# ---------- A. 追加性 ----------
b_dec = {(d["decision_id"]): d for d in before["decisions"]}
a_dec = {(d["decision_id"]): d for d in after["decisions"]}
b_chg = {c["change_id"]: c for c in before["changelog"]}
a_chg = {c["change_id"]: c for c in after["changelog"]}
dec_unchanged = all(k in a_dec and a_dec[k] == v for k, v in b_dec.items())
chg_unchanged = all(k in a_chg and a_chg[k] == v for k, v in b_chg.items())
new_dec = [k for k in a_dec if k not in b_dec]
new_chg = [k for k in a_chg if k not in b_chg]
append_only = (len(a_dec) == len(b_dec) + len(new_dec) and len(a_chg) == len(b_chg) + len(new_chg)
               and dec_unchanged and chg_unchanged)

# ---------- B. 旧版本保留 ----------
# 旧产物的 artifact_path / recorded_sha256 / recorded_size 取自现库；这些行与冻结快照
# （5-B baseline 的 DB 快照）逐列同值已由 phase5c_db_append_only.py 证明（modified 0 / deleted 0）。
import sqlite3  # noqa: E402

_con = sqlite3.connect("file:{}?mode=ro".format(
    (ROOT / "projects" / "video_studio.db").as_posix()), uri=True)
_con.row_factory = sqlite3.Row
b_ros = {r["artifact_id"]: r for r in before["render_outputs"]}
a_ros = {r["artifact_id"]: r for r in after["render_outputs"]}
old_kept = []
for aid, r in b_ros.items():
    a = a_ros.get(aid)
    row = _con.execute("select path, sha256, size from artifacts where artifact_id=?",
                       (aid,)).fetchone()
    h_ok, s_ok, h_calc, s_calc = recorded_hash_ok(row["path"], row["sha256"], row["size"])
    old_kept.append({"artifact_id": aid, "task_id": r["task_id"],
                     "artifact_file_unchanged": bool(a and a["artifact_sha256"] == r["artifact_sha256"]),
                     "film_file_unchanged": bool(a and a["film_sha256"] == r["film_sha256"]),
                     "film_present": pathlib.Path(r["film"]).exists(),
                     "recorded_hash_matches_reconstructed": h_ok,
                     "recorded_size_matches_reconstructed": s_ok,
                     "recorded_sha256": row["sha256"], "recomputed_lf16": h_calc})
_con.close()
old_versions_intact = all(x["artifact_file_unchanged"] and x["film_file_unchanged"]
                          and x["film_present"] and x["recorded_hash_matches_reconstructed"]
                          and x["recorded_size_matches_reconstructed"]
                          for x in old_kept)

# ---------- C. 未授权镜头 ----------
latest = after["render_outputs"][-1]
prev = before["render_outputs"][-1]
tl_now = {s["scene_id"]: s for s in latest["timeline"]}
tl_old = {s["scene_id"]: s for s in prev["timeline"]}
scene_cmp = []
for sid in sorted(tl_now):
    n, o = tl_now[sid], tl_old.get(sid, {})
    scene_cmp.append({"scene_id": sid,
                      "asset_before": o.get("asset_id"), "asset_after": n.get("asset_id"),
                      "asset_same": o.get("asset_id") == n.get("asset_id"),
                      "window_same": (o.get("start_s"), o.get("end_s")) == (n.get("start_s"),
                                                                            n.get("end_s")),
                      "window_after": [n.get("start_s"), n.get("end_s")],
                      "selection_source_after": n.get("selection_source")})
changed = [x["scene_id"] for x in scene_cmp if not x["asset_same"]]
unauthorized_untouched = changed == ["S06"] and all(x["window_same"] for x in scene_cmp)

# ---------- D. attribution 1:1 ----------
att_path = ROOT / "projects" / PID / "artifacts" / (latest["attribution_artifact"] + ".json")
att = json.loads(att_path.read_text(encoding="utf-8"))
entries = att.get("entries") or []
att_rows = []
for e in entries:
    sa = e.get("selected_asset") or {}
    actual = sha(sa.get("path"))
    att_rows.append({"scene_id": e.get("scene_id"), "window_s": e.get("window_s"),
                     "asset_id": sa.get("asset_id"), "name": sa.get("name"),
                     "sha256_matches_file": bool(actual and actual == sa.get("sha256")),
                     "license": e.get("license"), "license_class": e.get("license_class"),
                     "attribution": e.get("attribution"), "provider": e.get("provider"),
                     "source_id": e.get("source_id"), "scope": e.get("scope"),
                     "appears_in_film": e.get("appears_in_film"),
                     "corr": (e.get("film_evidence") or {}).get("corr"),
                     "film_match": (e.get("film_evidence") or {}).get("match")})
att_scenes = [r["scene_id"] for r in att_rows]
attribution_one_to_one = (len(att_rows) == len(latest["timeline"])
                          and sorted(att_scenes) == sorted(tl_now)
                          and all(r["sha256_matches_file"] and r["appears_in_film"]
                                  and r["film_match"] for r in att_rows))

# ---------- E. 许可门禁（真实函数复核；用产物里的**完整** selected_asset 投影） ----------
payload = json.loads(pathlib.Path(latest["artifact_path"]).read_text(encoding="utf-8"))
full_tl = {s.get("scene_id"): s for s in (payload.get("material_timeline") or [])}
CLEARED = {"PUBLIC_DOMAIN", "FREE_ATTRIBUTION"}
gate_rows = []
for sid in sorted(full_tl):
    sa = full_tl[sid].get("selected_asset") or {}
    applies = license_gate_applies(sa, require_license=True)
    block = license_block_reason(sa, require_license=True) if applies else None
    gate_rows.append({"scene_id": sid, "asset_id": sa.get("asset_id"),
                      "license": sa.get("license"), "license_class": sa.get("license_class"),
                      "license_cleared": sa.get("license_cleared"),
                      "gate_applies": applies, "gate_block_reason": block,
                      "class_cleared": sa.get("license_class") in CLEARED})
license_ok = all(r["gate_applies"] and r["gate_block_reason"] is None and r["class_cleared"]
                 and r["license_cleared"] is True for r in gate_rows)
payload_gate_ok = bool((payload.get("license_classes_used") or {}) and
                       not (payload.get("licence_blocked_candidates") or []))

# ---------- F. 渲染自检 ----------
mv = latest.get("material_verification") or {}
render_selfcheck_ok = bool(mv.get("checked_scenes_total") == 6 and not mv.get("failed_scenes")
                           and set(mv.get("checked_scenes") or []) == set(tl_now))

# ---------- G. 新产物（v6）自身口径一致 ----------
h_ok, s_ok, h_calc, s_calc = recorded_hash_ok(latest["artifact_path"],
                                             latest["recorded_sha256"],
                                             latest["recorded_size"])
new_artifact_ok = bool(h_ok and s_ok and latest["artifact_sha256"] == sha(latest["artifact_path"])
                       and latest["film_sha256"] == sha(latest["film"]))

out = {
    "A_append_only": {"decisions_before": len(b_dec), "decisions_after": len(a_dec),
                      "changelog_before": len(b_chg), "changelog_after": len(a_chg),
                      "prior_decision_rows_identical": dec_unchanged,
                      "prior_changelog_rows_identical": chg_unchanged,
                      "new_decision_ids": new_dec, "new_changelog_ids": new_chg,
                      "new_decision_row": [a_dec[k] for k in new_dec],
                      "new_changelog_row": [a_chg[k] for k in new_chg],
                      "ok": bool(append_only)},
    "B_old_versions_intact": {"rows": old_kept, "ok": bool(old_versions_intact),
                              "version_chain": cmpj["version_chain_after"]},
    "C_unauthorized_scenes": {"scenes": scene_cmp, "changed_scenes": changed,
                              "ok": bool(unauthorized_untouched)},
    "D_attribution": {"artifact_id": latest["attribution_artifact"], "rows": att_rows,
                      "ok": bool(attribution_one_to_one)},
    "E_license_gate": {"rows": gate_rows, "ok": bool(license_ok),
                       "license_classes_used": payload.get("license_classes_used"),
                       "licence_blocked_candidates": payload.get("licence_blocked_candidates"),
                       "payload_level_ok": payload_gate_ok,
                       "cleared_classes": sorted(CLEARED)},
    "F_render_selfcheck": {"material_verification": mv, "ok": render_selfcheck_ok},
    "G_new_artifact": {"artifact_id": latest["artifact_id"],
                       "recorded_sha256": latest["recorded_sha256"], "recomputed_lf16": h_calc,
                       "film_sha256": latest["film_sha256"], "ok": new_artifact_ok},
}
out["ALL_PASS"] = all(out[k]["ok"] for k in
                      ("A_append_only", "B_old_versions_intact", "C_unauthorized_scenes",
                       "D_attribution", "E_license_gate", "F_render_selfcheck", "G_new_artifact"))
(LOGS / "phase5c_append_only.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                               encoding="utf-8")

print("A append-only:", out["A_append_only"]["ok"], "new decision", new_dec, "new changelog",
      new_chg, "| prior rows identical:", dec_unchanged, chg_unchanged)
print("B old versions intact:", out["B_old_versions_intact"]["ok"],
      [(x["task_id"], x["film_file_unchanged"], x["film_present"]) for x in old_kept])
print("C only S06 changed:", changed, "windows all same:",
      all(x["window_same"] for x in scene_cmp))
for x in scene_cmp:
    print("   ", x["scene_id"], x["asset_before"], "->", x["asset_after"], x["window_after"],
          x["selection_source_after"])
print("D attribution 1:1:", out["D_attribution"]["ok"], "entries", len(att_rows))
for r in att_rows:
    print("   ", r["scene_id"], r["asset_id"], str(r["name"])[:38], r["license_class"],
          r["source_id"], "corr", r["corr"], "sha_ok", r["sha256_matches_file"])
print("E license gate:", out["E_license_gate"]["ok"],
      [(r["scene_id"], r["license_class"], r["gate_applies"], r["gate_block_reason"])
       for r in gate_rows])
print("F render selfcheck:", render_selfcheck_ok, mv.get("checked_scenes"),
      "failed", mv.get("failed_scenes"))
print("G new artifact:", new_artifact_ok, latest["recorded_sha256"], h_calc)
print("ALL PASS:", out["ALL_PASS"])
print("written", LOGS / "phase5c_append_only.json")
