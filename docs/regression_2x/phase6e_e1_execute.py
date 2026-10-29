# -*- coding: utf-8 -*-
"""6-E —— **仅执行 E1**（`rp-ad4bbbee7ea2`）：片尾卡 CJK 字体修复。

人工授权（本轮，逐字遵守）：
  · 仅允许执行当前唯一 APPROVE 的 E1；**E2/E3/E4/E5 仍为 HOLD** ⇒ 禁止执行、禁止自动转 APPROVE、
    禁止生成其执行产物；
  · E1 严格使用冻结的 `msyh.ttc`；**不得**改变片尾文字/位置/时长/字幕/音轨/其它 timeline；
  · 按现有 execution contract（core.execution + ops.execution）执行，保持 fail-closed 与幂等；
  · 执行后强制重跑 PI-1…PI-6 + DQ；
  · 核验：豆腐块消失 / 字幕正常 / 音频 hash 不变 / 时长与 AV track 无异常漂移 /
    v9·C1–C4·DB·M5 台账未被修改 / E2–E5 无 execution record；
  · 追加完整 execution ledger + provenance + candidate SHA256；**不 promote**。

用法: python docs/regression_2x/phase6e_e1_execute.py
产出: logs/phase6e_e1_approvals.jsonl（新）
      logs/phase6e_e1_execution_ledger.jsonl（新）
      logs/phase6e_e1_execution.json（报告）+ logs/phase6e_e1_candidate.json
      logs/phase6e_e1_frames/{master,c1,candidate}_outro.png 等（只读取帧证据）
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
from video_studio.core import captions as core_captions            # noqa: E402
from video_studio.core import execution as EX                      # noqa: E402
from video_studio.ops import direction as ops_direction            # noqa: E402
from video_studio.ops import execution as ops_exec                 # noqa: E402

LOGS = ROOT / "docs" / "regression_2x" / "logs"
DB = ROOT / "projects" / "video_studio.db"
PID, FILM_TASK = "p_96efdc03e1aa", "t_d0a54bdf1810"
FILM = ROOT / "projects" / PID / "output" / "{}_draft.mp4".format(FILM_TASK)
V9_SHA = "22705c7d7ea20b40d91120146066b89ab2b5fa5c1a1cab18f5346d4c66497651"
EVIDENCE = "docs/regression_2x/logs/audit_p96efdc_mm.json"
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
FONT_FROZEN_SHA = "d79c55e68b1131eea0cc1c47be4f572d964f28c682e143db2ad09c1e4cb07a3f"
FONT = Path(r"C:\Windows\Fonts\msyh.ttc")
OUTRO_TEXT = "感谢观看　我们下期再见"
APPROVED_BY = "human:director(6-E execution)"
EXECUTED_AT = "2026-10-06T00:00:00Z"

CFG = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8-sig"))
FFMPEG = CFG["tools"]["ffmpeg"]["path"]


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def manifest(d: Path) -> dict:
    return {p.name: (p.stat().st_size, round(p.stat().st_mtime, 3))
            for p in sorted(d.rglob("*")) if p.is_file()}


def probe(p: Path) -> dict:
    out = subprocess.run([FFMPEG.replace("ffmpeg.exe", "ffprobe.exe"), "-v", "error", "-print_format",
                          "json", "-show_format", "-show_streams", str(p)],
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    d = json.loads(out.stdout or "{}")
    v = next((s for s in d.get("streams", []) if s.get("codec_type") == "video"), {})
    a = next((s for s in d.get("streams", []) if s.get("codec_type") == "audio"), {})
    return {"duration_s": float((d.get("format") or {}).get("duration") or 0.0),
            "streams": len(d.get("streams", [])),
            "video": {"codec": v.get("codec_name"), "w": v.get("width"), "h": v.get("height"),
                      "frames": v.get("nb_frames")},
            "audio": {"codec": a.get("codec_name"), "channels": a.get("channels"),
                      "sample_rate": a.get("sample_rate")},
            "container_bitrate": (d.get("format") or {}).get("bit_rate")}


def audio_sha(p: Path) -> str:
    out = subprocess.run([FFMPEG, "-v", "error", "-i", str(p), "-map", "0:a", "-f", "md5", "-"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    return (out.stdout or "").strip().splitlines()[-1].strip() if out.stdout else ""


def extract_frame(film: Path, t: float, dst: Path) -> Path:
    dst.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([FFMPEG, "-y", "-v", "error", "-ss", "{:.3f}".format(t), "-i", str(film),
                    "-frames:v", "1", str(dst)], capture_output=True, text=True, encoding="utf-8",
                   errors="replace")
    return dst


# ---------------------------------------------------------------- 0) 冻结/授权前置校验（fail-closed）
r2 = json.loads(R2.read_text(encoding="utf-8"))
props = {p["label"][:2]: p for p in r2["proposals"]}
E1 = props["E1"]
bm = json.loads(BATCH_MANIFEST.read_text(encoding="utf-8"))
status = json.loads(STATUS.read_text(encoding="utf-8"))
st = {s["label"][:2]: s for s in status["statuses"]}
freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
pre = {"checks": [], "abort": False}


def precheck(name, ok, detail=""):
    pre["checks"].append({"check": name, "ok": bool(ok), "detail": detail})
    if not ok:
        pre["abort"] = True
    print("{}  {} {}".format("PASS" if ok else "FAIL", name, "" if ok else "| " + str(detail)[:200]))


e1_sha = EX.proposal_sha256(E1)
frozen_sha = bm["items"][4]["proposal_sha256"]
precheck("E1 proposal_sha256 == 批次清单冻结值", e1_sha == frozen_sha,
         {"live": e1_sha, "frozen": frozen_sha})
precheck("E1 人工决定 = APPROVE", st["E1"]["decision"] == "APPROVE", st["E1"]["decision"])
precheck("E2–E5 全部仍为 HOLD（本脚本不执行它们）",
         all(st[k]["decision"] == "HOLD" for k in ("E2", "E3", "E4", "E5")),
         {k: st[k]["decision"] for k in ("E2", "E3", "E4", "E5")})
precheck("E1 尚未执行过（幂等前置）",
         not any((e.get("proposal_id") == E1["proposal_id"]
                  and e.get("state") == "SUCCEEDED") for e in EX.load_ledger(M5_EX))
         and not any((e.get("proposal_id") == E1["proposal_id"]
                      and e.get("state") == "SUCCEEDED") for e in EX.load_ledger(LEDGER)))
precheck("冻结字体 msyh.ttc 存在", FONT.is_file(), str(FONT))
font_sha = sha(FONT) if FONT.is_file() else None
precheck("冻结字体 sha256 == Material Freeze 记录值", font_sha == FONT_FROZEN_SHA,
         {"live": font_sha, "frozen": FONT_FROZEN_SHA})
params = (E1.get("proposed_change") or {}).get("params") or {}
precheck("方案参数与冻结规格一致（font_file/fontsdir/text）",
         params.get("font_file") == "msyh.ttc" and params.get("fontsdir") == "C:/Windows/Fonts"
         and (params.get("text") or OUTRO_TEXT) == OUTRO_TEXT, params)
precheck("窗口与冻结一致（S21 [1465,1532]）",
         E1["affected_scope"]["scenes"] == ["S21"]
         and E1["affected_scope"]["window"] == [1465.0, 1532.0], E1["affected_scope"])

# ---- 只读基线 ----
db_b, film_b = sha(DB), sha(FILM)
m5ap_b, m5ex_b = sha(M5_AP), sha(M5_EX)
m6c = json.loads(M6C.read_text(encoding="utf-8"))
cand_b = {c["index"]: sha(ROOT / c["film"]) for c in m6c["candidates"]}
c1_dir = C1.parent
c1_dir_b = manifest(c1_dir)
if pre["abort"]:
    print("\nABORT（fail-closed）：前置校验未通过，未执行任何动作。")
    sys.exit(2)

# ---------------------------------------------------------------- 1) 沙箱 + ctx（只读输入）
con_ok = True
import sqlite3                                                       # noqa: E402
con = sqlite3.connect("file:{}?mode=ro".format(DB.as_posix()), uri=True)
con.row_factory = sqlite3.Row
con.execute("PRAGMA query_only=ON")
rows = [dict(r) for r in con.execute(
    "select artifact_id, task_id, type, path from artifacts where project_id=? order by created_at",
    (PID,))]
con.close()
by_type = {}
for r in rows:
    by_type.setdefault(r["type"], []).append(r)


def payload(t, task=None):
    lst = by_type.get(t) or []
    rec = next((x for x in lst if task and x["task_id"] == task), lst[-1] if lst else None)
    if not rec:
        return {}
    p = Path(rec["path"])
    return json.loads((p if p.is_absolute() else ROOT / p).read_text(encoding="utf-8"))


script = payload("script_output")
voice = payload("voice_output")
render = payload("render_output", FILM_TASK)
timeline = render.get("material_timeline") or []
timeline_total = float((render.get("duration_contract") or {}).get("timeline_duration_s") or 1532.0)
box = ops_exec.prepare_sandbox(ROOT, PID, "6e", FILM,
                               artifacts={"script_output": script, "voice_output": voice})
cues = core_captions.build_cues([{"narration": s.get("narration", ""),
                                  "duration_s": s.get("duration_s")}
                                 for s in (script.get("segments") or [])])
ctx = {"root": ROOT, "box": box["box"], "film": FILM, "artifacts": box["artifacts"],
       "files": box["files"], "ffmpeg": CFG["tools"]["ffmpeg"]["path"],
       "ffprobe": CFG["tools"]["ffmpeg"]["ffprobe"], "config": CFG, "timeline": timeline,
       "timeline_duration_s": timeline_total,
       "evidence": ops_direction.load_evidence(EVIDENCE, ROOT), "cues": cues,
       "asset_index": {}, "asset_bindings": {}}
print("\n沙箱:", Path(box["box"]).relative_to(ROOT))
print("cues:", len(cues), "| 时间轴总长: {:.1f}s".format(timeline_total))

# ---------------------------------------------------------------- 2) 人工批准（绑定 id+hash）
ap = EX.make_approval(E1, "APPROVE", APPROVED_BY,
                      "仅批准 E1（片尾卡 CJK 字体修复）：显式字体 msyh.ttc，文字/位置/时长/字幕/音轨不变",
                      "人工批准轮（6-E）：E1=APPROVE；素材冻结清单 " + freeze["manifest_sha256"][:16]
                      + "；批次清单 " + bm["manifest_sha256"][:16], at=EXECUTED_AT)
ap = EX.append_approval(APPROVALS, ap)
print("批准记录:", ap["approval_id"], "| seq", ap["seq"])

# ---------------------------------------------------------------- 3) 受控执行（仅 E1）
before_out = set(p.name for p in (Path(box["box"]) / "output").rglob("*") if p.is_file()) \
    if (Path(box["box"]) / "output").is_dir() else set()
batch = EX.execute_batch([E1], [ap], ops_exec.EXECUTORS, ctx, recheck=ops_exec.pi_recheck,
                         ledger=LEDGER, ledger_entries=EX.load_ledger(M5_EX))
rec = batch["records"][0]
print("执行状态:", rec["state"], "| executor_invoked:", rec.get("executor_invoked"),
      "| promoted:", rec.get("promoted"), "| auto_approved:", rec.get("auto_approved"))
if rec["state"] != "SUCCEEDED":
    print("why:", rec.get("why"))
out_list = rec.get("outputs") or []
cand = ROOT / out_list[0]["path"] if out_list else None
print("候选成片:", cand, "|", out_list[0]["sha256"][:16] if out_list else None)

# ---------------------------------------------------------------- 4) 强制 PI/DQ + 专项核验
verify = {"pi_dq": rec.get("recheck"), "pi_gate_outcome": rec.get("pi_gate_outcome"),
          "exec_evidence_keys": sorted((rec.get("exec_evidence") or {}).keys())}
if rec["state"] == "SUCCEEDED" and cand and cand.is_file():
    v9_p, c1_p, cd_p = probe(FILM), probe(C1), probe(cand)
    verify["probe"] = {"v9": v9_p, "c1": c1_p, "candidate": cd_p}
    verify["duration_drift_s"] = {"candidate_vs_v9": round(cd_p["duration_s"] - v9_p["duration_s"], 4),
                                  "candidate_vs_c1": round(cd_p["duration_s"] - c1_p["duration_s"], 4)}
    a_v9, a_cd = audio_sha(FILM), audio_sha(cand)
    verify["audio"] = {"v9_audio_md5": a_v9, "candidate_audio_md5": a_cd,
                       "identical": bool(a_v9) and a_v9 == a_cd,
                       "streams": {"v9": v9_p["streams"], "candidate": cd_p["streams"]},
                       "record_audio_check": (rec.get("exec_evidence") or {}).get("audio_check")}
    # ---- 帧证据：母版 / C1（豆腐块）/ 候选，同一时刻 ----
    FRAMES.mkdir(parents=True, exist_ok=True)
    t_cue = None
    for c in cues:
        s = float(c.get("start") or c.get("start_s") or 0.0)
        if 1466.0 <= s <= 1531.0:
            t_cue = s
    t_probe = round((t_cue if t_cue is not None else 1500.0) + 0.5, 3)
    verify["frame_time_s"] = t_probe
    f_master = extract_frame(FILM, t_probe, FRAMES / "master_outro.png")
    f_c1 = extract_frame(C1, t_probe, FRAMES / "c1_outro.png")
    f_cd = extract_frame(cand, t_probe, FRAMES / "candidate_outro.png")

    # ---- 豆腐块判定：与冻结字体渲染的参考字形做比对 + 空心方块检测 ----
    import numpy as np                                              # noqa: E402
    from PIL import Image, ImageDraw, ImageFont                     # noqa: E402
    from scipy import ndimage                                       # noqa: E402

    def glyph_mask(img_path: Path, box_xy=(380, 770, 1540, 950)):
        im = Image.open(img_path).convert("L").crop(box_xy)
        a = np.asarray(im, dtype=np.float32) / 255.0
        bright = a > 0.80
        bg = ndimage.uniform_filter(a, size=9) < 0.72      # 笔画周围应是暗色（卡片底）
        m = bright & bg
        return m

    def ref_mask():
        f = ImageFont.truetype(str(FONT), 64)
        img = Image.new("L", (1200, 160), 0)
        ImageDraw.Draw(img).text((10, 40), OUTRO_TEXT, fill=255, font=f)
        a = np.asarray(img, dtype=np.float32) / 255.0
        return a > 0.5

    def norm_pad(m, size=(1024, 128)):
        ys, xs = np.where(m)
        if len(ys) == 0:
            return np.zeros(size[::-1], dtype=bool)
        crop = m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
        img = Image.fromarray((crop * 255).astype(np.uint8))
        w, h = size
        s = min(w / max(img.width, 1), h / max(img.height, 1))
        img = img.resize((max(1, int(img.width * s)), max(1, int(img.height * s))),
                         Image.NEAREST)
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
            h, w = ys.max() - ys.min() + 1, xs.max() - xs.min() + 1
            if h < 40 or w < 40:
                continue
            fill = comp.sum() / float(h * w)
            sub = comp[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
            holes = 0
            largest = 0
            inv = ~sub
            lab2, n2 = ndimage.label(inv)
            for j in range(1, n2 + 1):
                hj = lab2 == j
                if hj[0, :].any() or hj[-1, :].any() or hj[:, 0].any() or hj[:, -1].any():
                    continue                                  # 与边界相连 ⇒ 不是孔
                if hj.sum() > 50:
                    holes += 1
                    largest = max(largest, hj.sum())
            out.append({"bbox": [int(xs.min()), int(ys.min()), int(w), int(h)], "fill": round(fill, 3),
                        "holes": holes, "largest_hole_ratio": round(largest / float(h * w), 3),
                        "tofu_like": bool(fill < 0.45 and holes == 1
                                          and largest / float(h * w) > 0.45)})
        return out

    ref = norm_pad(ref_mask())
    tofu = {}
    for name, path in (("master", f_master), ("c1", f_c1), ("candidate", f_cd)):
        m = glyph_mask(path)
        nm = norm_pad(m)
        inter = np.logical_and(ref, nm).sum()
        union = np.logical_or(ref, nm).sum()
        boxes = hollow_boxes(m)
        tofu[name] = {"ink_px": int(m.sum()), "glyph_iou_vs_frozen_font": round(inter / max(union, 1), 4),
                      "components": len(boxes),
                      "tofu_like_components": sum(1 for b in boxes if b["tofu_like"]),
                      "components_detail": boxes[:12]}
    verify["tofu"] = tofu
    verify["tofu_verdict"] = {
        "c1_had_tofu": tofu["c1"]["tofu_like_components"] > 0,
        "candidate_tofu_like": tofu["candidate"]["tofu_like_components"],
        "candidate_glyph_iou_improved": tofu["candidate"]["glyph_iou_vs_frozen_font"]
        > tofu["c1"]["glyph_iou_vs_frozen_font"],
        "pass": (tofu["candidate"]["tofu_like_components"] == 0
                 and tofu["candidate"]["glyph_iou_vs_frozen_font"]
                 > tofu["c1"]["glyph_iou_vs_frozen_font"]),
    }
    verify["frames"] = [str(f_master.relative_to(ROOT)), str(f_c1.relative_to(ROOT)),
                        str(f_cd.relative_to(ROOT))]

# ---- E2–E5 无 execution record ----
led = EX.load_ledger(LEDGER)
verify["execution_records"] = {"total": len(led),
                               "proposal_ids": [e.get("proposal_id") for e in led],
                               "only_e1": all(e.get("proposal_id") == E1["proposal_id"] for e in led),
                               "e2_e5_records": [e.get("proposal_id") for e in led
                                                 if e.get("proposal_id") != E1["proposal_id"]]}
ap_led = EX.load_ledger(APPROVALS)
verify["approvals"] = {"total": len(ap_led), "proposal_ids": [e.get("proposal_id") for e in ap_led],
                       "only_e1": all(e.get("proposal_id") == E1["proposal_id"] for e in ap_led)}

# ---- 既有产物未被修改 ----
db_a, film_a = sha(DB), sha(FILM)
m5ap_a, m5ex_a = sha(M5_AP), sha(M5_EX)
cand_a = {c["index"]: sha(ROOT / c["film"]) for c in m6c["candidates"]}
integrity = {"db_unchanged": db_b == db_a, "v9_unchanged": film_b == film_a == V9_SHA,
             "c1_c4_unchanged": all(cand_a[k] == cand_b[k] for k in cand_b),
             "c1_dir_unchanged": manifest(c1_dir) == c1_dir_b,
             "m5_approvals_untouched": m5ap_b == m5ap_a,
             "m5_execution_untouched": m5ex_b == m5ex_a,
             "m5_approvals_entries": len(EX.load_ledger(M5_AP)),
             "m5_execution_entries": len(EX.load_ledger(M5_EX))}
# ---- 6-C 候选 sha256 未被改写（对照 6-C 记录）----
integrity["c1_c4_sha_match_6c_records"] = all(
    cand_a[c["index"]] == c["film_sha256"] for c in m6c["candidates"])

report = {
    "schema": "phase6e-e1-execution-v1", "stage": "6-E",
    "scope": "仅 E1（rp-ad4bbbee7ea2）；E2–E5 保持 HOLD，未执行、未生成产物",
    "executed_at": EXECUTED_AT,
    "preflight": pre,
    "proposal": {"label": E1["label"], "proposal_id": E1["proposal_id"], "proposal_sha256": e1_sha,
                 "action": E1["action"], "scenes": E1["affected_scope"]["scenes"],
                 "window": E1["affected_scope"]["window"],
                 "params": params},
    "freeze_binding": {"material_freeze_manifest_sha256": freeze["manifest_sha256"],
                       "batch_manifest_sha256": bm["manifest_sha256"],
                       "font": {"path": str(FONT), "bytes": FONT.stat().st_size,
                                "sha256": font_sha, "frozen_sha256": FONT_FROZEN_SHA,
                                "match": font_sha == FONT_FROZEN_SHA},
                       "text": OUTRO_TEXT},
    "approval": {k: ap.get(k) for k in ("approval_id", "proposal_id", "proposal_sha256", "decision",
                                        "approved_by", "approved_at", "reason", "provenance",
                                        "seq", "entry_sha256")},
    "execution": {"state": rec["state"], "why": rec.get("why"), "executor_invoked":
                  rec.get("executor_invoked"), "promoted": rec.get("promoted"),
                  "auto_approved": rec.get("auto_approved"),
                  "auto_scope_expansion": rec.get("auto_scope_expansion"),
                  "sandbox_only": rec.get("sandbox_only"),
                  "steps": rec.get("steps"), "outputs": rec.get("outputs"),
                  "ledger_seq": rec.get("seq"), "ledger_entry_sha256": rec.get("entry_sha256"),
                  "gate": batch["gate"]["decisions"].get(E1["proposal_id"])},
    "candidate": ({"path": out_list[0]["path"], "bytes": out_list[0]["bytes"],
                   "sha256": out_list[0]["sha256"],
                   "sha256_live": sha(cand) if cand and cand.is_file() else None}
                  if out_list else None),
    "verify": verify,
    "integrity": integrity,
    "no_promotion": {"promoted": False, "v9_untouched": True, "c1_c4_untouched": True,
                     "note": "候选片留在沙箱，**未** promote 为最终版本"},
}
report["report_sha256"] = hashlib.sha256(
    json.dumps({k: v for k, v in report.items() if k != "report_sha256"}, sort_keys=True,
               ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()
REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
if cand and cand.is_file():
    CAND_JSON.write_text(json.dumps({"schema": "phase6e-e1-candidate-v1",
                                     "proposal_id": E1["proposal_id"],
                                     "proposal_sha256": e1_sha,
                                     "path": out_list[0]["path"], "bytes": out_list[0]["bytes"],
                                     "sha256": out_list[0]["sha256"],
                                     "duration_check": (rec.get("exec_evidence") or {}
                                                        ).get("duration_check"),
                                     "audio_check": (rec.get("exec_evidence") or {}).get("audio_check"),
                                     "pi_gate_outcome": rec.get("pi_gate_outcome"),
                                     "dq": (rec.get("recheck") or {}).get("dq"),
                                     "promoted": False, "human_review_required": True},
                                    ensure_ascii=False, indent=1), encoding="utf-8")

# ---- 登记：执行已开始（且仅 E1）----
def entry_sha(rec: dict) -> str:
    body = {k: v for k, v in rec.items() if k != "entry_sha256"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


ledger_rows = [json.loads(x) for x in RSTATUS_LEDGER.read_text(encoding="utf-8").splitlines() if x.strip()]
EXEC_ID = "6E-E1-EXECUTION-v1"
if not any(e.get("exec_id") == EXEC_ID for e in ledger_rows):
    r = {"schema": "execution-commenced-v1", "stage": "6-E", "exec_id": EXEC_ID,
         "executed_at": EXECUTED_AT, "scope": "E1 only",
         "proposal_id": E1["proposal_id"], "proposal_sha256": e1_sha,
         "approval_id": ap["approval_id"],
         "state": rec["state"], "candidate": (out_list[0] if out_list else None),
         "report": str(REPORT.relative_to(ROOT)), "report_sha256": report["report_sha256"],
         "e2_e5_executed": False, "promoted": False,
         "decided_by": APPROVED_BY,
         "provenance": "人工授权：仅执行 E1；E2–E5 保持 HOLD",
         "read_only": False, "enforced": True, "advisory": False, "executes_changes": True}
    r["seq"] = len(ledger_rows) + 1
    r["prev_sha256"] = ledger_rows[-1]["entry_sha256"] if ledger_rows else ""
    r["entry_sha256"] = entry_sha(r)
    with open(RSTATUS_LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(r, ensure_ascii=False) + "\n")

print("\n=== E1 执行摘要 ===")
print("state:", rec["state"], "| candidate:", (out_list[0]["path"] if out_list else None))
print("candidate sha256:", (out_list[0]["sha256"] if out_list else None))
print("PI gate:", rec.get("pi_gate_outcome"), "| DQ:", json.dumps(
    (rec.get("recheck") or {}).get("dq"), ensure_ascii=False)[:200])
print("tofu:", json.dumps(verify.get("tofu_verdict"), ensure_ascii=False))
print("audio identical:", (verify.get("audio") or {}).get("identical"),
      "| duration drift vs v9:", verify.get("duration_drift_s"))
print("integrity:", json.dumps(integrity, ensure_ascii=False))
print("execution records:", json.dumps(verify["execution_records"], ensure_ascii=False))
print("report ->", REPORT)
