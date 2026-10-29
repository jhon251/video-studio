# -*- coding: utf-8 -*-
"""6-E —— **E2 v2 执行**（仅 `rp-bee31dff3335` / `8ff60656e40925f1…`）。

人工执行令（本轮）：仅允许执行 E2 v2；E3/E4/E5 保持 HOLD；action=add_visual_aid，严格使用冻结
`spec_source`；禁止检索/下载/引入外部素材；禁止 IMO 合影；不得新增冻结计划之外的语义；
fail-closed / 幂等 / locality / conflict 契约不变；执行后跑 PI/DQ（BLOCKED 如实保留）；不 promote。

产出: logs/phase6e_e2_approvals.jsonl（新）
      logs/phase6e_e2_execution_ledger.jsonl（新）
      logs/phase6e_e2_execution.json（报告）+ logs/phase6e_e2_candidate.json
      logs/phase6e_e2_frames/*.png（只读取帧证据）
"""
import hashlib
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
from video_studio.core import captions as core_captions             # noqa: E402
from video_studio.core import execution as EX                       # noqa: E402
from video_studio.core import revision as core_revision             # noqa: E402
from video_studio.core import visual_aid as VA                      # noqa: E402
from video_studio.ops import direction as ops_direction             # noqa: E402
from video_studio.ops import execution as ops_exec                  # noqa: E402

LOGS = ROOT / "docs" / "regression_2x" / "logs"
MAT = ROOT / "docs" / "regression_2x" / "phase6e_materials"
DB = ROOT / "projects" / "video_studio.db"
PID, FILM_TASK = "p_96efdc03e1aa", "t_d0a54bdf1810"
FILM = ROOT / "projects" / PID / "output" / "{}_draft.mp4".format(FILM_TASK)
V9_SHA = "22705c7d7ea20b40d91120146066b89ab2b5fa5c1a1cab18f5346d4c66497651"
EVIDENCE = "docs/regression_2x/logs/audit_p96efdc_mm.json"
PROPOSAL_ID = "rp-bee31dff3335"
PROPOSAL_SHA = "8ff60656e40925f15d55650c7909b6d1adda0b9a2980d5fd9857534f95879d5f"
PLAN = MAT / "phase6e_material_plan.json"
PLAN_SHA_REQUIRED = "0cefd8810515138cf3a8e2057ffcf3c695bc16d7b8cfac818bd6fcad74689df8"
CANON = LOGS / "phase6e_e2_v2_proposal.json"
REG = LOGS / "phase6e_proposal_register_r2.jsonl"
BM = LOGS / "phase6e_execution_batch_manifest.json"
STATUS = LOGS / "phase6e_approval_status_r2.json"
FREEZE = MAT / "phase6e_material_freeze_manifest.json"
M3 = LOGS / "phase6b_m3_proposals_v9.json"
M5_AP = LOGS / "phase6b_m4_approvals_v9.jsonl"
M5_EX = LOGS / "phase6b_m4_execution_ledger_v9.jsonl"
E1_LEDGER = LOGS / "phase6e_e1_execution_ledger.jsonl"
E1_DIR = ROOT / "output" / "phase6b_m4_sandbox" / "p_96efdc03e1aa_6e"
M6C = LOGS / "phase6c_batch.json"
APPROVALS = LOGS / "phase6e_e2_approvals.jsonl"
LEDGER = LOGS / "phase6e_e2_execution_ledger.jsonl"
REPORT = LOGS / "phase6e_e2_execution.json"
CAND_JSON = LOGS / "phase6e_e2_candidate.json"
FRAMES = LOGS / "phase6e_e2_frames"
FONT = Path(r"C:\Windows\Fonts\msyh.ttc")
FONT_SHA = "d79c55e68b1131eea0cc1c47be4f572d964f28c682e143db2ad09c1e4cb07a3f"
IMO_ASSET = "asset_432cd85be6f1"
EXECUTED_AT = "2026-10-09T00:00:00Z"
CFG = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8-sig"))
FFMPEG = CFG["tools"]["ffmpeg"]["path"]
FFPROBE = CFG["tools"]["ffmpeg"]["ffprobe"]


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def jsonable(o):
    import numpy as np
    if isinstance(o, dict):
        return {str(k): jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [jsonable(v) for v in o]
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    return o


def probe(p: Path) -> dict:
    out = subprocess.run([FFPROBE, "-v", "error", "-print_format", "json", "-show_format",
                          "-show_streams", str(p)], capture_output=True, text=True,
                         encoding="utf-8", errors="replace")
    d = json.loads(out.stdout or "{}")
    v = next((s for s in d.get("streams", []) if s.get("codec_type") == "video"), {})
    a = next((s for s in d.get("streams", []) if s.get("codec_type") == "audio"), {})
    return {"duration_s": float((d.get("format") or {}).get("duration") or 0.0),
            "streams": len(d.get("streams", [])),
            "video": {"codec": v.get("codec_name"), "w": v.get("width"), "h": v.get("height")},
            "audio": {"codec": a.get("codec_name"), "channels": a.get("channels"),
                      "sample_rate": a.get("sample_rate")}}


def audio_md5(p: Path) -> str:
    out = subprocess.run([FFMPEG, "-v", "error", "-i", str(p), "-map", "0:a", "-f", "md5", "-"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    return (out.stdout or "").strip().splitlines()[-1].strip() if out.stdout else ""


def extract(film: Path, t: float, dst: Path) -> Path:
    dst.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([FFMPEG, "-y", "-v", "error", "-ss", "{:.3f}".format(t), "-i", str(film),
                    "-frames:v", "1", str(dst)], capture_output=True, text=True,
                   encoding="utf-8", errors="replace")
    return dst


checks = []


def ck(name, ok, detail=None):
    checks.append({"check": name, "ok": bool(ok), "detail": jsonable(detail)})
    print("{}  {} {}".format("PASS" if ok else "FAIL", name,
                             "" if ok else "| " + json.dumps(jsonable(detail),
                                                             ensure_ascii=False)[:220]))
    return bool(ok)


# ---------------- 0) 前置校验（fail-closed）----------------
print("== 0) 前置校验 ==")
v2 = json.loads(CANON.read_text(encoding="utf-8"))
live_sha = EX.proposal_sha256(v2)
reg = core_revision.load_register(REG)
reg_v2 = next(r for r in reg if r["proposal_id"] == PROPOSAL_ID)
st = {s["label"][:2]: s for s in json.loads(STATUS.read_text(encoding="utf-8"))["statuses"]}
bm = json.loads(BM.read_text(encoding="utf-8"))
freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
m6c = json.loads(M6C.read_text(encoding="utf-8"))
abort = []
if not ck("0a proposal_id/hash 与人工执行令一致",
          v2["proposal_id"] == PROPOSAL_ID == reg_v2["proposal_id"] and live_sha == PROPOSAL_SHA
          and EX.proposal_sha256(reg_v2) == PROPOSAL_SHA,
          {"id": v2["proposal_id"], "live": live_sha, "ordered": PROPOSAL_SHA}):
    abort.append("hash")
if not ck("0b action = add_visual_aid 且状态为待执行（approved=false 于 proposal 本体）",
          v2["action"] == "add_visual_aid" and v2["status"] == "PROPOSED_AWAITING_HUMAN_APPROVAL"):
    abort.append("action")
if not ck("0c E2 状态为 HOLD 且本轮执行令为其授权载体（E3/E4/E5 仍 HOLD）",
          st["E2"]["decision"] == "HOLD" and all(st[k]["decision"] == "HOLD"
                                                 for k in ("E3", "E4", "E5")),
          {k: st[k]["decision"] for k in ("E2", "E3", "E4", "E5")}):
    abort.append("status")
if not ck("0d E2 v2 尚未执行过（幂等前置）",
          not any(e.get("proposal_id") == PROPOSAL_ID and e.get("state") == "SUCCEEDED"
                  for e in EX.load_ledger(LEDGER) + EX.load_ledger(M5_EX))):
    abort.append("idempotency")
if not ck("0e 冻结计划 sha256 == 人工指定值", PLAN.is_file() and sha(PLAN) == PLAN_SHA_REQUIRED,
          {"live": sha(PLAN) if PLAN.is_file() else None, "required": PLAN_SHA_REQUIRED}):
    abort.append("plan")
params = v2["proposed_change"]["params"]
psk = params["spec_source"]
if not ck("0f spec_source 绑定（path/item/sha256）与冻结一致",
          psk["path"] == "docs/regression_2x/phase6e_materials/phase6e_material_plan.json"
          and psk["item"] == "E2" and psk["sha256"] == PLAN_SHA_REQUIRED, psk):
    abort.append("spec_source")
spec = VA.compile_from_plan_item(json.loads(PLAN.read_text(encoding="utf-8"))["items"]["E2"])
VA.verify_spec(spec)
spec_sha = VA.spec_sha256(spec)
_spec_strs = [s for _, s in VA._walk_strings(spec)]
_spec_keys = set(VA._walk_keys(spec))
if not ck("0g 编译 spec 无外部素材字段 / 无引语 / 无被否决素材 id",
          IMO_ASSET not in " ".join(_spec_strs)
          and not (_spec_keys & set(VA.EXTERNAL_KEYS))
          and not any(q in s for s in _spec_strs for q in VA.WESTERN_QUOTES),
          {"spec_sha256": spec_sha, "panels": [p["id"] for p in spec["panels"]],
           "external_keys_hit": sorted(_spec_keys & set(VA.EXTERNAL_KEYS)),
           "quote_hit": [s[:40] for s in _spec_strs if any(q in s for q in VA.WESTERN_QUOTES)]}):
    abort.append("spec_content")
if not ck("0h 局部化：1 镜 / 占比 0.0359 ≤ 上限",
          len(v2["affected_scope"]["scenes"]) == 1
          and v2["affected_scope"]["share_of_film"]
          <= core_revision.DEFAULT_POLICY["max_share_of_film_per_proposal"]):
    abort.append("locality")
executed_c = [p for p in json.loads(M3.read_text(encoding="utf-8"))["proposals"]
              if p["label"] in ("H3-batch1-split-longest", "H3-batch2-next-longest",
                                "H5-semantic-mismatch-replace", "H7-outro-card")]
cross = []
for q in executed_c:
    c = EX.pair_conflict(reg_v2, q)
    if c:
        cross.append({"executed": q["label"], "kinds": c["kinds"],
                      "shared_scenes": c.get("shared_scenes"),
                      "requires_human_reapproval": EX.OVERLAP_POLICY["requires_human_reapproval"],
                      "confirmed_by": "human:director(6-E E2 v2 execution order)",
                      "confirmation_basis": "本轮执行令明确给出 proposal_id+proposal_sha256 授权执行，"
                                            "且该令在跨批次重叠已声明之后发出 ⇒ 视为人工确认重新批准"})
effective = [reg_v2] + [r for r in reg if r["label"].startswith(("E3", "E4", "E5"))]
matrix = EX.detect_conflicts(effective)
if not ck("0i 冲突：生效集合内部 0 对；E2↔H5 跨批次重叠已由本轮执行令确认",
          matrix["conflict_pair_count"] == 0
          and [c for c in cross if c["executed"] == "H5-semantic-mismatch-replace"] != [],
          {"internal": matrix["conflict_pair_count"], "cross": cross}):
    abort.append("conflict")
if not ck("0j 冻结字体存在且 sha256 一致", FONT.is_file() and sha(FONT) == FONT_SHA):
    abort.append("font")
if not ck("0k E3/E4/E5 proposal_sha256 未变（与批次清单一致）",
          all(EX.proposal_sha256(next(r for r in reg if r["label"].startswith(k)))
              == next(i for i in bm["items"] if i["label"].startswith(k))["proposal_sha256"]
              for k in ("E3", "E4", "E5"))):
    abort.append("e3e4e5")
if abort:
    print("\nABORT（fail-closed）：前置校验未通过 {}，未执行任何动作。".format(abort))
    sys.exit(2)

# 只读基线
db_b, v9_b = sha(DB), sha(FILM)
cand_b = {c["index"]: sha(ROOT / c["film"]) for c in m6c["candidates"]}
m5ap_b, m5ex_b = sha(M5_AP), sha(M5_EX)
e1_inv_b = {str(p.relative_to(E1_DIR)): (p.stat().st_size, round(p.stat().st_mtime, 3))
            for p in E1_DIR.rglob("*") if p.is_file()} if E1_DIR.is_dir() else {}
freeze_b = sha(FREEZE)

# ---------------- 1) 沙箱 + ctx ----------------
con = sqlite3.connect("file:{}?mode=ro".format(DB.as_posix()), uri=True)
con.row_factory = sqlite3.Row
con.execute("PRAGMA query_only=ON")
rows = [dict(r) for r in con.execute(
    "select type, task_id, path from artifacts where project_id=? order by created_at", (PID,))]
con.close()
by_type = {}
for r in rows:
    by_type.setdefault(r["type"], []).append(r)


def payload(t, task=None):
    lst = by_type.get(t) or []
    x = next((y for y in lst if task and y["task_id"] == task), lst[-1] if lst else None)
    if not x:
        return {}
    p = Path(x["path"])
    return json.loads((p if p.is_absolute() else ROOT / p).read_text(encoding="utf-8"))


script, voice = payload("script_output"), payload("voice_output")
render = payload("render_output", FILM_TASK)
timeline = render.get("material_timeline") or []
timeline_total = float((render.get("duration_contract") or {}).get("timeline_duration_s") or 1532.0)
box = ops_exec.prepare_sandbox(ROOT, PID, "6e2", FILM,
                              artifacts={"script_output": script, "voice_output": voice})
cues = core_captions.build_cues([{"narration": s.get("narration", ""),
                                  "duration_s": s.get("duration_s")}
                                 for s in (script.get("segments") or [])])
ctx = {"root": ROOT, "box": box["box"], "film": FILM, "artifacts": box["artifacts"],
       "files": box["files"], "ffmpeg": FFMPEG, "ffprobe": FFPROBE, "config": CFG,
       "timeline": timeline, "timeline_duration_s": timeline_total,
       "evidence": ops_direction.load_evidence(EVIDENCE, ROOT), "cues": cues,
       "asset_index": {}, "asset_bindings": {},
       "visual_aid_font": str(FONT), "visual_aid_font_sha256": FONT_SHA}
print("\n沙箱:", Path(box["box"]).relative_to(ROOT))

# ---------------- 2) 人工批准（绑定 id+hash）与跨批次确认 ----------------
ap = EX.make_approval(
    v2, "APPROVE", "human:director(6-E E2 v2 execution order)",
    "批准执行 E2 v2（add_visual_aid，S05 [245,300]）：严格使用冻结 spec_source，无外部素材，禁止 IMO 合影",
    "人工执行令（本轮）：proposal_id={} proposal_sha256={}；跨批次重叠（E2↔H5）随该令确认".format(
        PROPOSAL_ID, PROPOSAL_SHA), at=EXECUTED_AT)
ap["cross_batch_confirmation"] = cross
ap = EX.append_approval(APPROVALS, ap)
print("批准:", ap["approval_id"], "| seq", ap["seq"], "| hash", ap["proposal_sha256"][:16])

# ---------------- 3) 受控执行（仅 E2）----------------
batch = EX.execute_batch([reg_v2], [ap], ops_exec.EXECUTORS, ctx, recheck=ops_exec.pi_recheck,
                         ledger=LEDGER, ledger_entries=EX.load_ledger(M5_EX)
                         + EX.load_ledger(E1_LEDGER))
rec = batch["records"][0]
print("执行状态:", rec["state"], "| executor_invoked:", rec.get("executor_invoked"),
      "| promoted:", rec.get("promoted"), "| auto_approved:", rec.get("auto_approved"))
if rec["state"] != "SUCCEEDED":
    print("why:", rec.get("why"))
outs = rec.get("outputs") or []
cand = ROOT / outs[0]["path"] if outs else None
print("候选:", (outs[0]["path"] if outs else None), "|", (outs[0]["sha256"][:16] if outs else None))

# ---------------- 4) 专项核验 ----------------
verify = {"pi_gate_outcome": rec.get("pi_gate_outcome"),
          "pi_metrics": (rec.get("recheck") or {}).get("pi_metrics"),
          "pi_failed": (rec.get("recheck") or {}).get("pi_failed"),
          "pre_render_gate": (rec.get("recheck") or {}).get("pre_render_gate"),
          "post_render_gate": (rec.get("recheck") or {}).get("post_render_gate"),
          "dq_summary": (rec.get("recheck") or {}).get("dq_summary"),
          "dq_details": (rec.get("recheck") or {}).get("dq_details")}
if rec["state"] == "SUCCEEDED" and cand and cand.is_file():
    v9_p, cd_p = probe(FILM), probe(cand)
    c1 = ROOT / m6c["candidates"][0]["film"]
    a_v9, a_cd, a_c1 = audio_md5(FILM), audio_md5(cand), audio_md5(c1)
    verify["probe"] = {"v9": v9_p, "candidate": cd_p}
    verify["duration"] = {"drift_vs_v9_s": round(cd_p["duration_s"] - v9_p["duration_s"], 4),
                          "record_duration_check": (rec.get("exec_evidence") or {}
                                                    ).get("duration_check")}
    verify["audio"] = {"v9_md5": a_v9, "candidate_md5": a_cd, "c1_md5": a_c1,
                       "byte_identical_to_v9": a_v9 == a_cd,
                       "identical_to_c1": a_c1 == a_cd,
                       "record_audio_check": (rec.get("exec_evidence") or {}).get("audio_check")}
    ev = (rec.get("exec_evidence") or {}).get("visual_aid_evidence") or {}
    verify["spec_binding"] = {"spec_sha256_expected": spec_sha,
                              "spec_sha256_evidence": ev.get("spec_sha256"),
                              "match": ev.get("spec_sha256") == spec_sha,
                              "spec_source": (rec.get("exec_evidence") or {}
                                              ).get("visual_aid_spec_source"),
                              "safe_bottom_ok": ev.get("safe_bottom_ok"),
                              "quote_free_verified": ev.get("quote_free_verified"),
                              "panels": [p["id"] for p in ev.get("panels") or []],
                              "rendered_text": ev.get("rendered_text"),
                              "font": ev.get("font")}
    # 帧证据（窗口内两点 + 字幕时点）
    t_pts = [250.0, 272.0]
    t_cue = None
    for c in cues:
        s = float(c.get("start") or c.get("start_s") or 0.0)
        if 246.0 <= s <= 299.0:
            t_cue = s
    if t_cue is not None:
        t_pts.append(round(t_cue + 0.4, 3))
    import numpy as np
    from PIL import Image
    from scipy import ndimage
    frames, metrics = {}, {}
    for t in t_pts:
        tag = "t{:07.3f}".format(t)
        fm = extract(FILM, t, FRAMES / "master_{}.png".format(tag))
        fc = extract(cand, t, FRAMES / "candidate_{}.png".format(tag))
        frames[tag] = [str(fm.relative_to(ROOT)), str(fc.relative_to(ROOT))]
        a_m = np.asarray(Image.open(fm).convert("L"), dtype=np.float32) / 255.0
        a_c = np.asarray(Image.open(fc).convert("L"), dtype=np.float32) / 255.0
        boxes = [[p["bbox"][0], p["bbox"][1], p["bbox"][0] + p["bbox"][2],
                  p["bbox"][1] + p["bbox"][3]] for p in (ev.get("panels") or [])]
        ink_c, lum_m, lum_c, cov = 0, [], [], []
        for x0, y0, x1, y1 in boxes:
            y1b, x1b = min(y1, a_c.shape[0]), min(x1, a_c.shape[1])
            sub_m, sub_c = a_m[y0:y1b, x0:x1b], a_c[y0:y1b, x0:x1b]
            if sub_c.size == 0:
                continue
            lum_m.append(float(sub_m.mean()))
            lum_c.append(float(sub_c.mean()))
            white = sub_c > 0.80
            near = ndimage.uniform_filter(sub_c, size=9) < 0.72
            ink = white & near
            ink_c += int(ink.sum())
            cov.append(float((np.abs(sub_c - sub_m) > 0.08).mean()))
        bot = int(a_c.shape[0] * 0.95)
        metrics[tag] = {"panel_ink_px_candidate": ink_c,
                        "panel_mean_lum_master": round(float(np.mean(lum_m)), 4) if lum_m else None,
                        "panel_mean_lum_candidate": round(float(np.mean(lum_c)), 4) if lum_c else None,
                        "panel_changed_share": round(float(np.mean(cov)), 4) if cov else None,
                        "bottom5_gray_diff": round(float(np.abs(a_c[bot:] - a_m[bot:]).mean() * 255), 4),
                        "frame_gray_diff": round(float(np.abs(a_c - a_m).mean() * 255), 4)}
        # 字幕带（底部 18%）outline ink
        def band_ink(a):
            b = a[int(a.shape[0] * 0.82):]
            w = b > 0.72
            return int(((b < 0.45) & ndimage.binary_dilation(w, iterations=2)).sum())
        metrics[tag]["subtitle_ink_master"] = band_ink(a_m)
        metrics[tag]["subtitle_ink_candidate"] = band_ink(a_c)
    verify["frames"] = frames
    verify["frame_metrics"] = metrics
    mid = "t272.000"
    m = metrics.get(mid) or list(metrics.values())[0]
    verify["overlay_verdict"] = jsonable({
        "overlay_present_in_window": bool(m["panel_ink_px_candidate"] > 200
                                          and (m["panel_changed_share"] or 0) > 0.3),
        "panels_darken_backdrop": (m["panel_mean_lum_candidate"] is not None
                                   and m["panel_mean_lum_master"] is not None
                                   and m["panel_mean_lum_candidate"] < m["panel_mean_lum_master"]),
        "bottom5_untouched": m["bottom5_gray_diff"] < 2.0,
        "subtitles_preserved": (m["subtitle_ink_candidate"] >= 0.5 * m["subtitle_ink_master"]),
        "safe_bottom_ok": ev.get("safe_bottom_ok"),
        "quote_free_verified": ev.get("quote_free_verified"),
        "spec_sha_match": ev.get("spec_sha256") == spec_sha,
        "backdrop_note": "S05 底层仍为已执行 H5 的 IMO 合影（被半透明面板压暗）；本方案未新增对该素材的"
                         "引用，但底层素材仍部分可见 ⇒ 若规则 4 意指『画面任何位置都不得出现 IMO 合影』，"
                         "则需人工另定（增加不透明遮罩或改用 replace 类动作）",
    })

# ---------------- 5) 幂等探针 ----------------
idem = EX.execute_batch([reg_v2], [ap], ops_exec.EXECUTORS, ctx, recheck=ops_exec.pi_recheck,
                        ledger=LEDGER, ledger_entries=EX.load_ledger(M5_EX))
idem_rec = idem["records"][0]
verify["idempotency_probe"] = {"state": idem_rec["state"],
                               "executor_invoked": idem_rec.get("executor_invoked"),
                               "candidate_sha_unchanged": (sha(cand) == outs[0]["sha256"]
                                                           if outs and cand and cand.is_file()
                                                           else None)}

# ---------------- 6) 无副作用 / E3-E5 未动 ----------------
led = EX.load_ledger(LEDGER)
integrity = {"v9_sha256": sha(FILM), "v9_unchanged": sha(FILM) == V9_SHA,
             "c1_c4_unchanged": all(sha(ROOT / c["film"]) == cand_b[c["index"]]
                                    for c in m6c["candidates"]),
             "db_unchanged": sha(DB) == db_b,
             "m5_approvals_untouched": sha(M5_AP) == m5ap_b,
             "m5_execution_untouched": sha(M5_EX) == m5ex_b,
             "m5_entries": [len(EX.load_ledger(M5_AP)), len(EX.load_ledger(M5_EX))],
             "e1_sandbox_unchanged": ({str(p.relative_to(E1_DIR)):
                                       (p.stat().st_size, round(p.stat().st_mtime, 3))
                                       for p in E1_DIR.rglob("*") if p.is_file()}
                                      if E1_DIR.is_dir() else {}) == e1_inv_b,
             "material_freeze_unchanged": sha(FREEZE) == freeze_b,
             "e3_e4_e5_proposal_unchanged": all(
                 EX.proposal_sha256(next(r for r in reg if r["label"].startswith(k)))
                 == next(i for i in bm["items"] if i["label"].startswith(k))["proposal_sha256"]
                 for k in ("E3", "E4", "E5")),
             "execution_ledger": {"entries": len(led),
                                  "proposal_ids": [e.get("proposal_id") for e in led],
                                  "states": [e.get("state") for e in led],
                                  "only_e2": all(e.get("proposal_id") == PROPOSAL_ID for e in led)}}

report = jsonable({
    "schema": "phase6e-e2-execution-v1", "stage": "6-E", "executed_at": EXECUTED_AT,
    "scope": "仅 E2 v2（rp-bee31dff3335）；E3/E4/E5 保持 HOLD，未执行、未自动批准",
    "proposal": {"proposal_id": PROPOSAL_ID, "proposal_sha256": PROPOSAL_SHA,
                 "action": v2["action"], "version": 2,
                 "scenes": v2["affected_scope"]["scenes"],
                 "window": v2["affected_scope"]["window"],
                 "spec_source": psk, "spec_sha256": spec_sha},
    "approval": {k: ap.get(k) for k in ("approval_id", "proposal_id", "proposal_sha256", "decision",
                                        "approved_by", "approved_at", "reason", "provenance",
                                        "seq", "entry_sha256")},
    "cross_batch_confirmation": cross,
    "execution": {"state": rec["state"], "why": rec.get("why"),
                  "executor_invoked": rec.get("executor_invoked"), "promoted": rec.get("promoted"),
                  "auto_approved": rec.get("auto_approved"),
                  "sandbox_only": rec.get("sandbox_only"),
                  "ledger_seq": rec.get("seq"), "ledger_entry_sha256": rec.get("entry_sha256"),
                  "steps": rec.get("steps")},
    "candidate": ({"path": outs[0]["path"], "bytes": outs[0]["bytes"], "sha256": outs[0]["sha256"],
                   "sha256_live": sha(cand)} if outs and cand and cand.is_file() else None),
    "verify": verify, "integrity": integrity, "checks": checks,
    "preflight_abort": abort, "no_promotion": True, "human_review_required": True,
})
report["report_sha256"] = hashlib.sha256(
    json.dumps({k: v for k, v in report.items() if k != "report_sha256"}, sort_keys=True,
               ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()
REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
if outs and cand and cand.is_file():
    CAND_JSON.write_text(json.dumps(jsonable({
        "schema": "phase6e-e2-candidate-v1", "proposal_id": PROPOSAL_ID,
        "proposal_sha256": PROPOSAL_SHA, "spec_sha256": spec_sha,
        "path": outs[0]["path"], "bytes": outs[0]["bytes"], "sha256": sha(cand),
        "pi_gate_outcome": rec.get("pi_gate_outcome"), "dq_summary": verify.get("dq_summary"),
        "duration_check": (rec.get("exec_evidence") or {}).get("duration_check"),
        "audio_check": (rec.get("exec_evidence") or {}).get("audio_check"),
        "overlay_verdict": verify.get("overlay_verdict"),
        "promoted": False, "human_review_required": True}), ensure_ascii=False, indent=1),
        encoding="utf-8")


def entry_sha(r):
    b = {k: v for k, v in r.items() if k != "entry_sha256"}
    return hashlib.sha256(json.dumps(b, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


rows2 = [json.loads(x) for x in (LOGS / "phase6e_approval_status_r2.jsonl")
         .read_text(encoding="utf-8").splitlines() if x.strip()]
EXEC_ID = "6E-E2-EXECUTION-v1"
if not any(e.get("exec_id") == EXEC_ID for e in rows2):
    r = {"schema": "execution-commenced-v1", "stage": "6-E", "exec_id": EXEC_ID,
         "executed_at": EXECUTED_AT, "scope": "E2 only",
         "proposal_id": PROPOSAL_ID, "proposal_sha256": PROPOSAL_SHA,
         "action": v2["action"], "spec_sha256": spec_sha, "approval_id": ap["approval_id"],
         "state": rec["state"],
         "candidate": ({"path": outs[0]["path"], "bytes": outs[0]["bytes"], "sha256": sha(cand)}
                       if outs and cand and cand.is_file() else None),
         "pi_gate_outcome": rec.get("pi_gate_outcome"), "dq_summary": verify.get("dq_summary"),
         "cross_batch_confirmed_by": "human:director(6-E E2 v2 execution order)",
         "report": str(REPORT.relative_to(ROOT)), "report_sha256": report["report_sha256"],
         "e3_e4_e5_executed": False, "promoted": False, "decided_by": ap["approved_by"],
         "provenance": "人工执行令：仅执行 E2 v2", "read_only": False, "enforced": True,
         "advisory": False, "executes_changes": True}
    r["seq"] = len(rows2) + 1
    r["prev_sha256"] = rows2[-1]["entry_sha256"] if rows2 else ""
    r["entry_sha256"] = entry_sha(r)
    with open(LOGS / "phase6e_approval_status_r2.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(r, ensure_ascii=False) + "\n")

print("\n=== E2 执行摘要 ===")
print("state:", rec["state"], "| candidate sha256:", (outs[0]["sha256"] if outs else None))
print("spec_sha256:", spec_sha)
print("PI gate:", rec.get("pi_gate_outcome"), "| PI failed:", verify.get("pi_failed"))
print("DQ:", json.dumps(verify.get("dq_summary"), ensure_ascii=False)[:220])
print("overlay:", json.dumps(verify.get("overlay_verdict"), ensure_ascii=False)[:400])
print("audio byte-identical(v9):", (verify.get("audio") or {}).get("byte_identical_to_v9"),
      "| duration drift:", (verify.get("duration") or {}).get("drift_vs_v9_s"))
print("idempotency:", json.dumps(verify.get("idempotency_probe"), ensure_ascii=False))
print("integrity:", json.dumps(integrity, ensure_ascii=False)[:500])
print("report ->", REPORT)
