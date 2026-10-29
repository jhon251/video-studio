# -*- coding: utf-8 -*-
"""6-E —— **E1 执行核验与报告**（从既有 execution ledger 取证，不重复执行）。

背景：`phase6e_e1_execute.py` 的真实执行**已 SUCCEEDED**（候选已产出、台账已落账），
但在写报告时因 numpy 类型不可序列化而中断（报告未落盘）。
本脚本**不重跑执行**，而是：
  1) 从 `logs/phase6e_e1_execution_ledger.jsonl` 读取那条 SUCCEEDED 记录（唯一执行证据）；
  2) **幂等探针**：用同一 proposal+approval 再调一次 `execute_batch`
     ⇒ 预期 `BLOCKED_ALREADY_EXECUTED` 且 `executor_invoked=False`、候选 sha256 不变；
  3) 完整核验：PI/DQ、豆腐块、字幕、音频哈希、时长/AV、既有产物完整性、E2–E5 无执行记录；
  4) 落盘报告 + 候选记录 + 登记（仅 E1）。

用法: python docs/regression_2x/phase6e_e1_verify.py
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
from video_studio.core import execution as EX                      # noqa: E402
from video_studio.ops import execution as ops_exec                 # noqa: E402

LOGS = ROOT / "docs" / "regression_2x" / "logs"
DB = ROOT / "projects" / "video_studio.db"
PID, FILM_TASK = "p_96efdc03e1aa", "t_d0a54bdf1810"
FILM = ROOT / "projects" / PID / "output" / "{}_draft.mp4".format(FILM_TASK)
V9_SHA = "22705c7d7ea20b40d91120146066b89ab2b5fa5c1a1cab18f5346d4c66497651"
M5_EX = LOGS / "phase6b_m4_execution_ledger_v9.jsonl"
M5_AP = LOGS / "phase6b_m4_approvals_v9.jsonl"
M6C = LOGS / "phase6c_batch.json"
R2 = LOGS / "phase6e_round2.json"
BATCH_MANIFEST = LOGS / "phase6e_execution_batch_manifest.json"
STATUS = LOGS / "phase6e_approval_status_r2.json"
RSTATUS_LEDGER = LOGS / "phase6e_approval_status_r2.jsonl"
FREEZE = ROOT / "docs" / "regression_2x" / "phase6e_materials" / "phase6e_material_freeze_manifest.json"
APPROVALS = LOGS / "phase6e_e1_approvals.jsonl"
LEDGER = LOGS / "phase6e_e1_execution_ledger.jsonl"
REPORT = LOGS / "phase6e_e1_execution.json"
CAND_JSON = LOGS / "phase6e_e1_candidate.json"
FRAMES = LOGS / "phase6e_e1_frames"
C1 = ROOT / "output" / "phase6b_m4_sandbox" / "p_96efdc03e1aa_6c" / "output" / (
    "t_d0a54bdf1810_draft_6c_rp-13aae40036e3_outro.mp4")
FONT = Path(r"C:\Windows\Fonts\msyh.ttc")
FONT_FROZEN_SHA = "d79c55e68b1131eea0cc1c47be4f572d964f28c682e143db2ad09c1e4cb07a3f"
OUTRO_TEXT = "感谢观看　我们下期再见"
EXECUTED_AT = "2026-10-06T00:00:00Z"
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
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    return o


def manifest(d: Path) -> dict:
    return {p.name: (p.stat().st_size, round(p.stat().st_mtime, 3))
            for p in sorted(d.rglob("*")) if p.is_file()}


def probe(p: Path) -> dict:
    out = subprocess.run([FFPROBE, "-v", "error", "-print_format", "json", "-show_format",
                          "-show_streams", str(p)], capture_output=True, text=True,
                         encoding="utf-8", errors="replace")
    d = json.loads(out.stdout or "{}")
    v = next((s for s in d.get("streams", []) if s.get("codec_type") == "video"), {})
    a = next((s for s in d.get("streams", []) if s.get("codec_type") == "audio"), {})
    return jsonable({"duration_s": float((d.get("format") or {}).get("duration") or 0.0),
                     "streams": len(d.get("streams", [])),
                     "video": {"codec": v.get("codec_name"), "w": v.get("width"),
                               "h": v.get("height"), "frames": v.get("nb_frames"),
                               "time_base": v.get("time_base")},
                     "audio": {"codec": a.get("codec_name"), "channels": a.get("channels"),
                               "sample_rate": a.get("sample_rate"),
                               "duration": a.get("duration")}})


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


# ---- 0) 读取执行证据 ----
r2 = json.loads(R2.read_text(encoding="utf-8"))
E1 = next(p for p in r2["proposals"] if p["label"].startswith("E1"))
e1_sha = EX.proposal_sha256(E1)
led = EX.load_ledger(LEDGER)
succeeded = [e for e in led if e.get("proposal_id") == E1["proposal_id"]
             and e.get("state") == "SUCCEEDED"]
assert succeeded, "未找到 E1 的 SUCCEEDED 记录（执行未发生或台账缺失）"
rec = succeeded[0]
ap_led = EX.load_ledger(APPROVALS)
ap = ap_led[0]
bm = json.loads(BATCH_MANIFEST.read_text(encoding="utf-8"))
freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
cand = ROOT / rec["outputs"][0]["path"]
cand_before = sha(cand)
print("执行记录: state={} seq={} executor_invoked={} promoted={}".format(
    rec["state"], rec.get("seq"), rec.get("executor_invoked"), rec.get("promoted")))
print("候选:", cand.relative_to(ROOT), "|", rec["outputs"][0]["sha256"][:16])

# ---- 1) 幂等探针（不重跑执行）----
con = sqlite3.connect("file:{}?mode=ro".format(DB.as_posix()), uri=True)
con.row_factory = sqlite3.Row
con.execute("PRAGMA query_only=ON")
art = [dict(r) for r in con.execute(
    "select artifact_id, task_id, type, path from artifacts where project_id=? order by created_at",
    (PID,))]
con.close()
by_type = {}
for r in art:
    by_type.setdefault(r["type"], []).append(r)


def payload(t, task=None):
    lst = by_type.get(t) or []
    x = next((y for y in lst if task and y["task_id"] == task), lst[-1] if lst else None)
    if not x:
        return {}
    p = Path(x["path"])
    return json.loads((p if p.is_absolute() else ROOT / p).read_text(encoding="utf-8"))


box_path = next((p for p in (ROOT / "output" / "phase6b_m4_sandbox" / "p_96efdc03e1aa_6e").glob("*")
                 if p.is_dir()), None)
box = {"box": str(box_path), "artifacts": {}, "files": {}}
ctx_probe = {"root": ROOT, "box": box["box"], "film": FILM, "artifacts": {}, "files": {},
             "ffmpeg": FFMPEG, "ffprobe": FFPROBE, "config": CFG, "timeline": [],
             "timeline_duration_s": 1532.0, "evidence": {}, "cues": [], "asset_index": {},
             "asset_bindings": {}}
idem_batch = EX.execute_batch([E1], [ap], ops_exec.EXECUTORS, ctx_probe,
                              recheck=ops_exec.pi_recheck, ledger=LEDGER,
                              ledger_entries=EX.load_ledger(M5_EX))
idem_rec = idem_batch["records"][0]
cand_after = sha(cand)
print("幂等探针:", idem_rec["state"], "| executor_invoked:", idem_rec.get("executor_invoked"),
      "| 候选 sha256 不变:", cand_before == cand_after)

# ---- 2) 完整核验 ----
v9_p, c1_p, cd_p = probe(FILM), probe(C1), probe(cand)
a_v9, a_c1, a_cd = audio_md5(FILM), audio_md5(C1), audio_md5(cand)
verify = {"probe": {"v9": v9_p, "c1": c1_p, "candidate": cd_p},
          "duration_drift_s": {"candidate_vs_v9": round(cd_p["duration_s"] - v9_p["duration_s"], 4),
                               "candidate_vs_c1": round(cd_p["duration_s"] - c1_p["duration_s"], 4)},
          "audio": {"v9_md5": a_v9, "c1_md5": a_c1, "candidate_md5": a_cd,
                    "identical_to_v9": a_v9 == a_cd, "identical_to_c1": a_c1 == a_cd,
                    "record_audio_check": rec.get("exec_evidence", {}).get("audio_check")},
          "pi_dq": rec.get("recheck"), "pi_gate_outcome": rec.get("pi_gate_outcome"),
          "duration_check": rec.get("exec_evidence", {}).get("duration_check")}

# 字幕窗口选点（与 S21 窗口内某条 cue 对齐）
script = payload("script_output")
from video_studio.core import captions as core_captions                          # noqa: E402
cues = core_captions.build_cues([{"narration": s.get("narration", ""),
                                  "duration_s": s.get("duration_s")}
                                 for s in (script.get("segments") or [])])
t_cue = None
for c in cues:
    s = float(c.get("start") or c.get("start_s") or 0.0)
    if 1466.0 <= s <= 1531.0:
        t_cue = s
t_probe = round((t_cue if t_cue is not None else 1500.0) + 0.5, 3)
f_master = extract(FILM, t_probe, FRAMES / "master_outro.png")
f_c1 = extract(C1, t_probe, FRAMES / "c1_outro.png")
f_cd = extract(cand, t_probe, FRAMES / "candidate_outro.png")
verify["frame_time_s"] = t_probe
verify["frames"] = [str(x.relative_to(ROOT)) for x in (f_master, f_c1, f_cd)]
verify["subtitle_probe_time_s"] = t_cue

import numpy as np                                                               # noqa: E402
from PIL import Image, ImageDraw, ImageFont                                      # noqa: E402
from scipy import ndimage                                                        # noqa: E402


def glyph_mask(path: Path, box_xy=(380, 770, 1540, 950)):
    im = Image.open(path).convert("L").crop(box_xy)
    a = np.asarray(im, dtype=np.float32) / 255.0
    return (a > 0.80) & (ndimage.uniform_filter(a, size=9) < 0.72)


def ref_mask():
    f = ImageFont.truetype(str(FONT), 64)
    img = Image.new("L", (1200, 160), 0)
    ImageDraw.Draw(img).text((10, 40), OUTRO_TEXT, fill=255, font=f)
    return np.asarray(img, dtype=np.float32) / 255.0 > 0.5


def norm_pad(m, size=(1024, 128)):
    ys, xs = np.where(m)
    if len(ys) == 0:
        return np.zeros((size[1], size[0]), dtype=bool)
    crop = m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    img = Image.fromarray((crop * 255).astype(np.uint8))
    w, h = size
    s = min(w / max(img.width, 1), h / max(img.height, 1))
    img = img.resize((max(1, int(img.width * s)), max(1, int(img.height * s))), Image.NEAREST)
    canvas = Image.new("L", size, 0)
    canvas.paste(img, ((w - img.width) // 2, (h - img.height) // 2))
    return np.asarray(canvas) > 127


def hollow_boxes(m):
    lab, n = ndimage.label(m)
    out = []
    for i in range(1, n + 1):
        comp = lab == i
        if comp.sum() < 120:
            continue
        ys, xs = np.where(comp)
        h, w = int(ys.max() - ys.min() + 1), int(xs.max() - xs.min() + 1)
        if h < 40 or w < 40:
            continue
        sub = comp[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
        fill = float(sub.sum()) / float(h * w)
        lab2, n2 = ndimage.label(~sub)
        holes, largest = 0, 0
        for j in range(1, n2 + 1):
            hj = lab2 == j
            if hj[0, :].any() or hj[-1, :].any() or hj[:, 0].any() or hj[:, -1].any():
                continue
            if hj.sum() > 50:
                holes += 1
                largest = max(largest, int(hj.sum()))
        ratio = largest / float(h * w)
        out.append({"bbox": [int(xs.min()), int(ys.min()), w, h], "fill": round(fill, 3),
                    "holes": holes, "largest_hole_ratio": round(ratio, 3),
                    "tofu_like": bool(fill < 0.45 and holes == 1 and ratio > 0.45)})
    return out


ref = norm_pad(ref_mask())
tofu = {}
for name, path in (("master", f_master), ("c1", f_c1), ("candidate", f_cd)):
    m = glyph_mask(path)
    nm = norm_pad(m)
    iou = float(np.logical_and(ref, nm).sum()) / float(max(np.logical_or(ref, nm).sum(), 1))
    bx = hollow_boxes(m)
    tofu[name] = jsonable({"ink_px": int(m.sum()), "glyph_iou_vs_frozen_font": round(iou, 4),
                           "components": len(bx),
                           "tofu_like_components": sum(1 for b in bx if b["tofu_like"]),
                           "components_detail": bx[:12]})
verify["tofu"] = tofu
verify["tofu_verdict"] = {
    "c1_had_tofu": tofu["c1"]["tofu_like_components"] > 0,
    "candidate_tofu_like_components": tofu["candidate"]["tofu_like_components"],
    "iou_c1": tofu["c1"]["glyph_iou_vs_frozen_font"],
    "iou_candidate": tofu["candidate"]["glyph_iou_vs_frozen_font"],
    "pass": (tofu["candidate"]["tofu_like_components"] == 0
             and tofu["candidate"]["glyph_iou_vs_frozen_font"]
             > tofu["c1"]["glyph_iou_vs_frozen_font"])}

# 字幕带（底部 18%）outline ink：母版 vs 候选（同刻）
def band_ink(path: Path):
    im = Image.open(path).convert("L")
    w, h = im.size
    a = np.asarray(im.crop((0, int(h * 0.82), w, h)), dtype=np.float32) / 255.0
    white = a > 0.72
    near = ndimage.binary_dilation(white, iterations=2)
    return jsonable({"band_white_px": int(white.sum()), "band_outline_ink_px": int(((a < 0.45) & near).sum())})


verify["subtitle_band"] = {"master": band_ink(f_master), "candidate": band_ink(f_cd),
                           "note": "底部 18% 带的『白色字形 + 相邻暗描边』像素（字幕存在性证据）"}

# ---- 3) E2–E5 无执行记录 + 既有产物完整性 ----
led2 = EX.load_ledger(LEDGER)
m6c = json.loads(M6C.read_text(encoding="utf-8"))
verify["execution_records"] = {"total": len(led2),
                               "states": [e.get("state") for e in led2],
                               "proposal_ids": [e.get("proposal_id") for e in led2],
                               "only_e1": all(e.get("proposal_id") == E1["proposal_id"] for e in led2),
                               "e2_e5_records": [e.get("proposal_id") for e in led2
                                                 if e.get("proposal_id") != E1["proposal_id"]],
                               "idempotency_probe": {"state": idem_rec["state"],
                                                     "executor_invoked":
                                                         idem_rec.get("executor_invoked"),
                                                     "candidate_sha_unchanged": cand_before == cand_after}}
verify["approvals"] = {"total": len(ap_led), "proposal_ids": [e.get("proposal_id") for e in ap_led],
                       "only_e1": all(e.get("proposal_id") == E1["proposal_id"] for e in ap_led)}
integration = {"db_sha256": sha(DB), "v9_sha256": sha(FILM), "v9_unchanged": sha(FILM) == V9_SHA,
               "c1_c4_sha256_now": {c["index"]: sha(ROOT / c["film"]) for c in m6c["candidates"]},
               "c1_c4_unchanged": all(sha(ROOT / c["film"]) == c["film_sha256"]
                                      for c in m6c["candidates"]),
               "m5_approvals_entries": len(EX.load_ledger(M5_AP)),
               "m5_execution_entries": len(EX.load_ledger(M5_EX)),
               "m5_untouched_entries_only": (len(EX.load_ledger(M5_AP)) == 3
                                             and len(EX.load_ledger(M5_EX)) == 5),
               "sandbox_6c_dir_files": sorted(p.name for p in C1.parent.rglob("*") if p.is_file()),
               "sandbox_6e_dir_files": sorted(p.name for p in cand.parent.rglob("*") if p.is_file()),
               "font": {"path": str(FONT), "bytes": FONT.stat().st_size, "sha256": sha(FONT),
                        "frozen_sha256": FONT_FROZEN_SHA, "match": sha(FONT) == FONT_FROZEN_SHA}}

report = jsonable({
    "schema": "phase6e-e1-execution-v1", "stage": "6-E", "executed_at": EXECUTED_AT,
    "scope": "仅 E1（rp-ad4bbbee7ea2）；E2–E5 保持 HOLD ⇒ 未执行、未生成产物、未自动转 APPROVE",
    "proposal": {"label": E1["label"], "proposal_id": E1["proposal_id"],
                 "proposal_sha256": e1_sha, "action": E1["action"],
                 "scenes": E1["affected_scope"]["scenes"],
                 "window": E1["affected_scope"]["window"],
                 "params": E1["proposed_change"]["params"]},
    "freeze_binding": {"material_freeze_manifest_sha256": freeze["manifest_sha256"],
                       "batch_manifest_sha256": bm["manifest_sha256"],
                       "font_sha256": FONT_FROZEN_SHA, "text": OUTRO_TEXT},
    "approval": {k: ap.get(k) for k in ("approval_id", "proposal_id", "proposal_sha256", "decision",
                                        "approved_by", "approved_at", "reason", "provenance",
                                        "seq", "entry_sha256")},
    "execution": {"state": rec["state"], "why": rec.get("why"),
                  "executor_invoked": rec.get("executor_invoked"),
                  "promoted": rec.get("promoted"), "auto_approved": rec.get("auto_approved"),
                  "auto_scope_expansion": rec.get("auto_scope_expansion"),
                  "sandbox_only": rec.get("sandbox_only"), "steps": rec.get("steps"),
                  "ledger_seq": rec.get("seq"), "ledger_entry_sha256": rec.get("entry_sha256"),
                  "exec_evidence_keys": sorted((rec.get("exec_evidence") or {}).keys())},
    "candidate": {"path": rec["outputs"][0]["path"], "bytes": rec["outputs"][0]["bytes"],
                  "sha256": rec["outputs"][0]["sha256"], "sha256_live": cand_after},
    "verify": verify, "integrity": integration,
    "no_promotion": True, "human_review_required": True,
})
report["report_sha256"] = hashlib.sha256(
    json.dumps({k: v for k, v in report.items() if k != "report_sha256"}, sort_keys=True,
               ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()
REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
CAND_JSON.write_text(json.dumps(jsonable({
    "schema": "phase6e-e1-candidate-v1", "proposal_id": E1["proposal_id"],
    "proposal_sha256": e1_sha, "path": rec["outputs"][0]["path"],
    "bytes": rec["outputs"][0]["bytes"], "sha256": cand_after,
    "duration_check": rec.get("exec_evidence", {}).get("duration_check"),
    "audio_check": rec.get("exec_evidence", {}).get("audio_check"),
    "pi_gate_outcome": rec.get("pi_gate_outcome"), "dq": (rec.get("recheck") or {}).get("dq"),
    "promoted": False, "human_review_required": True}), ensure_ascii=False, indent=1),
    encoding="utf-8")


def entry_sha(r: dict) -> str:
    body = {k: v for k, v in r.items() if k != "entry_sha256"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


rows = [json.loads(x) for x in RSTATUS_LEDGER.read_text(encoding="utf-8").splitlines() if x.strip()]
EXEC_ID = "6E-E1-EXECUTION-v1"
if not any(e.get("exec_id") == EXEC_ID for e in rows):
    r = {"schema": "execution-commenced-v1", "stage": "6-E", "exec_id": EXEC_ID,
         "executed_at": EXECUTED_AT, "scope": "E1 only",
         "proposal_id": E1["proposal_id"], "proposal_sha256": e1_sha,
         "approval_id": ap["approval_id"], "state": rec["state"],
         "candidate": {"path": rec["outputs"][0]["path"], "bytes": rec["outputs"][0]["bytes"],
                       "sha256": cand_after},
         "report": str(REPORT.relative_to(ROOT)), "report_sha256": report["report_sha256"],
         "e2_e5_executed": False, "promoted": False,
         "decided_by": ap["approved_by"],
         "provenance": "人工授权：仅执行 E1；E2–E5 保持 HOLD",
         "read_only": False, "enforced": True, "advisory": False, "executes_changes": True}
    r["seq"] = len(rows) + 1
    r["prev_sha256"] = rows[-1]["entry_sha256"] if rows else ""
    r["entry_sha256"] = entry_sha(r)
    with open(RSTATUS_LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(r, ensure_ascii=False) + "\n")

print("\n=== E1 执行核验 ===")
print("PI gate:", rec.get("pi_gate_outcome"))
dq = (rec.get("recheck") or {}).get("dq")
print("DQ:", json.dumps(dq, ensure_ascii=False)[:400] if dq else None)
print("tofu:", json.dumps(verify["tofu_verdict"], ensure_ascii=False))
print("audio identical(v9):", verify["audio"]["identical_to_v9"],
      "| identical(C1):", verify["audio"]["identical_to_c1"])
print("duration drift:", verify["duration_drift_s"], "| candidate vs v9 streams:",
      cd_p["streams"], v9_p["streams"])
print("subtitle band:", json.dumps(verify["subtitle_band"], ensure_ascii=False))
print("execution records:", json.dumps(verify["execution_records"], ensure_ascii=False))
print("integrity:", json.dumps(integration, ensure_ascii=False)[:600])
print("report ->", REPORT)
