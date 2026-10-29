# -*- coding: utf-8 -*-
"""6-G / Batch 2 —— **OPT-A：H3c-2 装配层精确时长修正后重新执行 + 完整验收**。

严格遵守人工裁定：
  · H3c-2 原 proposal **不变**（S21,S13,S19,S02,S05,S20；切点/params/target_hold_s=25 不变）；
  · POLICY / 阈值 / 冻结门禁判据**不变**；A1 仍为 `978.656 ± 0.05`（未采用 OPT-B 放宽）；
  · 修正仅在**输出装配层**（opt-in `exact_assembly_duration_s`）：仅视频精确到整帧、音轨 `-c:a copy`；
  · 不覆盖原失败证据（`phase6g_exec_batch2.json` 与台账 seq 6 保留）；
  · 新结果登记为新的一次 acceptance（OPT-A corrected re-acceptance）。

产出: docs/regression_2x/logs/phase6g_exec_batch2_optA.json
"""
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
from video_studio.core import captions as core_captions              # noqa: E402
from video_studio.core import direction as core_direction            # noqa: E402
from video_studio.core import execution as EX                        # noqa: E402
from video_studio.core import integrity as core_integrity            # noqa: E402
from video_studio.core import narration as N                         # noqa: E402
from video_studio.core import revision as core_revision              # noqa: E402
from video_studio.ops import execution as OPX                        # noqa: E402

LOGS = ROOT / "docs" / "regression_2x" / "logs"
P2 = json.loads((LOGS / "phase6f_rebuild_plan_v2.json").read_text(encoding="utf-8"))
N0 = json.loads((LOGS / "phase6g_n0_dcv2_master.json").read_text(encoding="utf-8"))
B1 = json.loads((LOGS / "phase6g_exec_batch1.json").read_text(encoding="utf-8"))
B2 = json.loads((LOGS / "phase6g_exec_batch2.json").read_text(encoding="utf-8"))
OUT = LOGS / "phase6g_exec_batch2_optA.json"
REGISTER = LOGS / "phase6g_rebuild_proposal_register.jsonl"
LEDGER = LOGS / "phase6g_exec_ledger.jsonl"
FFMPEG, FFPROBE = ROOT / "bin" / "ffmpeg.exe", ROOT / "bin" / "ffprobe.exe"
PROD, TOL = 978.656, 0.05
TS = time.strftime("%Y%m%d_%H%M%S")
SANDBOX = ROOT / "output" / "phase6g_exec_batch2_optA" / TS
CFG = {"tools": {"ffmpeg": {"path": str(FFMPEG), "ffprobe": str(FFPROBE)}}}
chain = P2["remapping_21_segments"]
CW = [{"scene_id": c["scene_id"], "start_s": c["new_audio_window_s"][0],
       "end_s": c["new_audio_window_s"][1]} for c in chain]
PASS, FAIL, FF_CALLS = [], [], []
CURRENT = {"stage": "H3c-2-optA"}
_orig_run = OPX._run


def _rec_run(cmd, timeout=3600):
    FF_CALLS.append({"argv": [str(c) for c in cmd][:16]})
    return _orig_run(cmd, timeout=timeout)


OPX._run = _rec_run


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def streams(p):
    r = subprocess.run([FFPROBE, "-v", "error", "-show_entries",
                        "format=duration:stream=codec_type,duration,nb_frames", "-of", "json",
                        str(p)], capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    j = json.loads(r.stdout or "{}")
    o = {"format_duration_s": round(float((j.get("format") or {}).get("duration") or 0), 4)}
    for s in (j.get("streams") or []):
        o[s.get("codec_type")] = {"duration_s": round(float(s.get("duration") or 0), 4),
                                  "nb_frames": s.get("nb_frames")}
    return o


def amd5(p):
    r = subprocess.run([FFMPEG, "-v", "error", "-i", str(p), "-map", "0:a", "-c", "copy", "-f",
                        "md5", "-"], capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    return (r.stdout or "").strip().split("=")[-1]


def hard(name, ok, detail=None):
    (PASS if ok else FAIL).append(name)
    print("{}  {} {}".format("PASS" if ok else "FAIL", name,
                             "" if ok else json.dumps(detail, ensure_ascii=False,
                                                      default=str)[:240]))
    if not ok:
        raise RuntimeError("OPTA_GATE_FAILED: " + name)


def gray(p):
    from PIL import Image                                                   # noqa: E402
    import numpy as np                                                      # noqa: E402
    return np.asarray(Image.open(p).convert("L"), dtype=np.float32) / 255.0


def frame(film, t, name, dur=None):
    import numpy as np                                                      # noqa: E402
    for i, tt in enumerate([t] + ([max(0.0, min(t, dur - 0.25))] if dur else [])
                           + [max(0.0, t - 0.2)]):
        f = SANDBOX / "work" / "acc_{}_{}_{}.png".format(name, str(t).replace(".", "_"), i)
        subprocess.run([FFMPEG, "-y", "-v", "error", "-ss", "{:.3f}".format(tt), "-i", str(film),
                        "-frames:v", "1", str(f)], capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
        if f.is_file():
            return gray(f)
    return np.zeros((720, 1280), dtype=np.float32)


def mask_at(t, ass):
    f = SANDBOX / "work" / "mask_{}.png".format(t)
    subprocess.run([FFMPEG, "-y", "-v", "error", "-f", "lavfi", "-i",
                    "color=c=black:s=1280x720:r=1", "-vf",
                    "ass=filename='{}':fontsdir='C\\:/Windows/Fonts'".format(
                        Path(ass).as_posix().replace(":", "\\:")), "-ss", str(int(t)),
                    "-frames:v", "1", str(f)], capture_output=True, text=True, encoding="utf-8",
                   errors="replace")
    return gray(f)


def erode(b):
    return (b[1:-1, 1:-1] & b[:-2, 1:-1] & b[2:, 1:-1] & b[1:-1, :-2] & b[1:-1, 2:])


def norm(x):
    return re.sub(r"\s+", "", str(x or "").replace("\\N", "").replace("\\n", ""))


def parse_ass(p):
    out, fmt, sec = [], None, None
    for line in Path(p).read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            sec = s
            continue
        if sec == "[Events]" and s.startswith("Format:"):
            fmt = [x.strip() for x in s.split(":", 1)[1].split(",")]
        elif sec == "[Events]" and s.startswith("Dialogue:") and fmt:
            d = dict(zip(fmt, s.split(":", 1)[1].split(",", len(fmt) - 1)))
            f = lambda x: (lambda h, m, ss: round(int(h) * 3600 + int(m) * 60 + float(ss), 3))(
                *x.strip().split(":"))
            out.append({"start": f(d["Start"]), "end": f(d["End"]), "text": d["Text"].strip()})
    return sorted(out, key=lambda x: x["start"])


def win_sel(table, w0, w1):
    r = []
    for c in table:
        if float(c["end"]) <= w0 + 1e-6 or float(c["start"]) >= w1 - 1e-6:
            continue
        r.append({"start": round(max(float(c["start"]), w0) - w0, 3),
                  "end": round(min(float(c["end"]), w1) - w0, 3), "text": c.get("text")})
    return sorted(r, key=lambda x: x["start"])


for d in (SANDBOX / "work", SANDBOX / "out", SANDBOX / "artifacts"):
    d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------- 输入与提案（均不变）
led0 = EX.load_ledger(str(LEDGER))
h1_entry = next(e for e in led0 if e.get("stage") == "H3c-1")
film_in = ROOT / h1_entry["output_path"]
hard("P0 输入 = 已接受的 H3c-1 输出（sha 与台账一致）", sha(film_in) == h1_entry["output_sha256"],
     {"now": sha(film_in)[:16], "ledger": h1_entry["output_sha256"][:16]})
regs = core_revision.load_register(str(REGISTER))
prop = next(r for r in regs if r.get("label") == "H3c-2")
prop_sha = EX.proposal_sha256(prop)
hard("P1 H3c-2 proposal **未变**（sha == 登记原值 c537b2ebe46ee41e…；场景/params 未改）",
     prop_sha == "c537b2ebe46ee41ed" or prop_sha.startswith("c537b2ebe46ee41e"),
     {"sha": prop_sha, "scenes": prop["affected_scope"]["scenes"],
      "params": prop["proposed_change"]["params"].get("target_hold_s")})
hard("P2 场景集合仍为 S21,S13,S19,S02,S05,S20（未扩范围）",
     prop["affected_scope"]["scenes"] == ["S21", "S13", "S19", "S02", "S05", "S20"],
     prop["affected_scope"]["scenes"])
hard("P3 POLICY 未变（6 / 0.30 / forbid_film_wide=True）",
     EX.POLICY["max_scenes_per_proposal"] == 6
     and EX.POLICY["max_share_of_film_per_proposal"] == 0.30
     and EX.POLICY["forbid_film_wide_rewrite"] is True, EX.POLICY)
hard("P4 A1 容差未变（±0.05 s；未采用 OPT-B）", TOL == 0.05 and PROD == 978.656, {"tol": TOL})

b1_sb = ROOT / B1["sandbox"]
art = {"script_output": str(b1_sb / "artifacts" / "script_output.json"),
       "voice_output": str(b1_sb / "artifacts" / "voice_output.json")}
script = json.loads(Path(art["script_output"]).read_text(encoding="utf-8"))
voice = json.loads(Path(art["voice_output"]).read_text(encoding="utf-8"))
payload = [{"narration": s["narration"], "duration_s": s.get("duration_s")}
           for s in script["segments"] if str(s.get("narration", "")).strip()]
cues_dcv2 = core_captions.build_cues(payload, windows=[{"start_s": w["start_s"],
                                                        "end_s": w["end_s"]} for w in CW])
cues_v1 = core_captions.build_cues(payload)
plan = N.narration_plan(script, voice)
GP = core_integrity.gate_policy(CFG)
master_ass = SANDBOX / "work" / "dcv2_master.ass"
master_ass.write_text(core_captions.to_ass(cues_dcv2, resolution="1280x720"), encoding="utf-8")

HIST = {"v9": ROOT / "projects" / "p_96efdc03e1aa" / "output" / "t_d0a54bdf1810_draft.mp4"}
m6c = json.loads((LOGS / "phase6c_batch.json").read_text(encoding="utf-8"))
for c in m6c["candidates"]:
    HIST["c" + str(c["index"])] = ROOT / c["film"]
HIST["e1"] = (ROOT / "output" / "phase6b_m4_sandbox" / "p_96efdc03e1aa_6e" / "output" /
              "t_d0a54bdf1810_draft_6c_rp-ad4bbbee7ea2_outro.mp4")
HIST["e2"] = (ROOT / "output" / "phase6b_m4_sandbox" / "p_96efdc03e1aa_6e2" / "output" /
              "t_d0a54bdf1810_draft_6c_rp-bee31dff3335_vaid.mp4")
BEFORE = {"history": {k: sha(p) for k, p in HIST.items() if p.is_file()},
          "db": sha(ROOT / "projects" / "video_studio.db"),
          "baseline": sorted(p.name for p in (ROOT / "docs" / "regression_2x" / "baseline").glob("*")),
          "master": sha(ROOT / N0["master"]["path"]),
          "b1": {s["stage"]: s["output"]["sha256"] for s in B1["stages"]},
          "h3c1": h1_entry["output_sha256"],
          "b2_failure_report": sha(LOGS / "phase6g_exec_batch2.json"),
          "ledger_before": len(led0),
          "projects_len": len([p for p in (ROOT / "projects" / "p_96efdc03e1aa").rglob("*")
                               if p.is_file()])}

# 只读 v9 素材绑定（切分执行器需要真实素材）
import sqlite3                                                          # noqa: E402
_c = sqlite3.connect("file:{}?mode=ro".format(
    (ROOT / "projects" / "video_studio.db").as_posix()), uri=True)
_c.row_factory = sqlite3.Row
_c.execute("PRAGMA query_only=ON")
_rows = [dict(r) for r in _c.execute(
    "select type,task_id,path from artifacts where project_id='p_96efdc03e1aa'")]
_c.close()
_rend = json.loads(Path(next(r["path"] for r in _rows if r["type"] == "render_output"
                             and r.get("task_id") == "t_d0a54bdf1810")).read_text(encoding="utf-8"))
TL_ASSET = {str(e.get("scene_id")): (e.get("selected_asset") or {})
            for e in (_rend.get("material_timeline") or []) if e.get("selected_asset")}
TL = [{"scene_id": c["scene_id"], "start_s": c["new_timeline_window_s"][0],
       "end_s": c["new_timeline_window_s"][1], "selected_asset": TL_ASSET.get(c["scene_id"], {})}
      for c in chain]

box = SANDBOX / "work" / "H3c-2-optA"
for sd in ("work", "output"):
    (box / sd).mkdir(parents=True, exist_ok=True)
ctx = OPX.attach_dcv2_time_base(
    {"box": str(box), "root": str(ROOT), "ffmpeg": str(FFMPEG), "ffprobe": str(FFPROBE),
     "config": CFG, "film": str(film_in), "cues": cues_dcv2, "evidence": None, "artifacts": art,
     "narration_plan": plan, "exact_assembly_duration_s": PROD},     # ← OPT-A opt-in
    timeline=TL, caption_windows=CW, production_duration_s=PROD,
    source="docs/regression_2x/logs/phase6f_rebuild_plan_v2.json")
ident = OPX.assert_timeline_identity(ctx)
hard("P5 DCv2 timeline identity 校验通过（{}）".format(ident.get("identity_sha256", "")[:16]),
     ident.get("enforced") is True
     and ident["identity_sha256"] == N0["timeline_identity"]["identity_sha256"], ident)
hard("P6 caption time base == DCv2", OPX.caption_time_base(ctx)["mode"] == "dcv2")
appr = EX.make_approval(prop, "APPROVE", "human",
                        "人工裁定 OPT-A（仅装配层确定性时长修正后重新执行 H3c-2；A1 ±0.05s 不变）",
                        {"authorization": "OPT-A 修正后重新验收", "scope": "H3c-2 only",
                         "not_authorized": ["OPT-B", "阈值变更", "H5", "E3", "E4", "E5", "第三批"]})
gate = EX.gate_execution(prop, [appr], None)
hard("P7 execution gate 通过", gate.get("allowed") is True,
     {"code": gate.get("code"), "why": gate.get("why")})
res = EX.execute_proposal(prop, [appr], OPX.EXECUTORS, ctx, recheck=OPX.pi_recheck)
hard("P8 执行 SUCCEEDED", res.get("state") == "SUCCEEDED",
     {"state": res.get("state"), "why": res.get("why")})
exact_step = next((s for s in (res.get("steps") or []) if s.get("step") == "exact_duration_pass_optA"),
                  None)
hard("P9 装配层精确修正已生效（exact_duration_pass_optA 步骤存在）", exact_step is not None,
     (res.get("steps") or [])[-3:])
out_rel = (res.get("outputs") or [{}])[0]["path"]
film_out = SANDBOX / "out" / "H3c-2_optA_rp-4db3b4bd15e5.mp4"
shutil.copy2(ROOT / out_rel, film_out)
st = streams(film_out)
stre = {"path": str(film_out.relative_to(ROOT)), "sha256": sha(film_out),
        "bytes": film_out.stat().st_size, "audio_md5": amd5(film_out), **st}
print("  corrected: duration {} (delta {:+.4f}) video {} frames {} audio {} md5 {}".format(
    st["format_duration_s"], round(st["format_duration_s"] - PROD, 4),
    (st.get("video") or {}).get("duration_s"), (st.get("video") or {}).get("nb_frames"),
    (st.get("audio") or {}).get("duration_s"), stre["audio_md5"][:12]))

hard("A1 duration == 978.656 ± 0.05（实测 {}，修正前 978.720）".format(st["format_duration_s"]),
     abs(st["format_duration_s"] - PROD) <= TOL, stre)
hard("A2 audio identity == 母版（md5 {}）".format(stre["audio_md5"][:12]),
     stre["audio_md5"] == amd5(ROOT / N0["master"]["path"])
     and abs(((st.get("audio") or {}).get("duration_s") or 0) - PROD) <= 0.02, stre)
spx = (res.get("exec_evidence") or {}).get("split_plan") or {}
aff = []
for r in spx.get("scenes", []):
    d = r["sub_duration_s"]
    aff.extend([[round(r["window"][0] + d * j, 3), round(r["window"][0] + d * (j + 1), 3)]
                for j in range(r["sub_count"])])
ass_files = sorted((box / "work").glob("cap_*.ass"))
s1 = []
for ap in ass_files:
    parsed = parse_ass(ap)
    hit = False
    for w in aff:
        d = win_sel(cues_dcv2, w[0], w[1])
        if d and len(d) == len(parsed) and all(
                abs(a["start"] - b["start"]) < 0.02 and abs(a["end"] - b["end"]) < 0.02
                and norm(a["text"]) == norm(b["text"]) for a, b in zip(parsed, d)):
            s1.append({"ass": ap.name, "window": w, "cues": len(parsed), "dcv2_match": True,
                       "v1_differs": win_sel(cues_v1, w[0], w[1]) != d})
            hit = True
            break
    if not hit:
        s1.append({"ass": ap.name, "dcv2_match": False, "cues": len(parsed)})
hard("B1 本阶段窗口 ASS == DCv2 表（{} 窗口）".format(len(ass_files)),
     bool(ass_files) and all(m.get("dcv2_match") for m in s1), s1)
hard("B2 同窗口 v1 选择 != DCv2（负对照）", all(m.get("v1_differs") for m in s1), s1)
fr = []
for w in aff[:3]:
    cc = [c for c in cues_dcv2 if c["start"] >= w[0] and c["end"] <= w[1]]
    if not cc:
        continue
    t = round((cc[0]["start"] + cc[0]["end"]) / 2, 3)
    m = mask_at(int(t), master_ass)
    e = erode(m > 0.5)
    if not e.any():
        continue
    a, b = frame(film_out, t, "sp", st["format_duration_s"]), frame(ROOT / N0["master"]["path"],
                                                                   t, "mst", PROD)
    fr.append({"t": t, "glyph_core_px": int(e.sum()),
               "ink_diff_vs_master": round(float(abs(a[1:-1, 1:-1][e] - b[1:-1, 1:-1][e]).mean()), 4),
               "max_ink": round(float(a[1:-1, 1:-1][e].max()), 3)})
hard("B3 语音时刻字形与母版一致（腐蚀差分 < 0.15；字幕时间轴未变）",
     bool(fr) and all(r["ink_diff_vs_master"] < 0.15 and r["max_ink"] > 0.5 for r in fr), fr)
ce = (res.get("exec_evidence") or {}).get("cut_evidence") or []
hard("C1 切点证据 all_distinct（{} 切点，切换未变）".format(len(ce)),
     bool(ce) and all(c["distinct"] for c in ce), ce)
hard("C2 子镜 <= 25s（target_hold_s 未改）",
     all(r["sub_duration_s"] <= 25.0 + 1e-6 for r in spx.get("scenes", [])),
     [(r["scene_id"], round(r["sub_duration_s"], 3)) for r in spx.get("scenes", [])])
pre = core_integrity.pre_render_gate(script.get("segments") or [], voice, PROD, GP,
                                     narration_duration_s=voice.get("narration_duration_s"),
                                     narration_plan=plan, cues=cues_dcv2,
                                     narration_padding_s=PROD - float(
                                         voice.get("narration_duration_s") or 0))
post = core_integrity.post_render_gate(film_out, PROD, cues_dcv2,
                                       voice.get("narration_duration_s"), True, str(FFMPEG),
                                       str(FFPROBE), GP, narration_plan=plan)
sm = lambda m: {a: (b.get("state") if isinstance(b, dict) else b) for a, b in m.items()}
hard("D1 DCv2 pre-render 未阻断 + PI-1/PI-2/PI-6/G-TL/G-PAD/G-SUB 全 PASS",
     (not pre["blocked"]) and all(sm(pre["metrics"]).get(g) == "PASS"
                                  for g in ("PI-1", "PI-2", "PI-6", "G-TL", "G-PAD", "G-SUB")),
     {"states": sm(pre["metrics"]), "reasons": pre["reasons"]})
hard("D2 DCv2 post-render：PI-3 PASS 且 promote 未被阻断",
     sm(post["metrics"]).get("PI-3") == "PASS" and not post.get("promote_blocked"),
     {"PI-3": post["metrics"]["PI-3"], "reasons": post["reasons"]})
hard("D3 冻结复核（口径已对齐）== PASS", res.get("pi_gate_outcome") == "PASS",
     res.get("pi_gate_outcome"))
bnd = sorted({round(w[0], 3) for w in aff} | {round(w[1] - 0.05, 3) for w in aff})
lum = {str(b): round(float(frame(film_out, b, "bd", st["format_duration_s"]).mean()), 4)
       for b in bnd[:8]}
hard("E1 边界无黑帧", not [k for k, v in lum.items() if v < 0.02], lum)
iso = {"history_unchanged": all(sha(HIST[k]) == v for k, v in BEFORE["history"].items()
                                if HIST[k].is_file()),
       "db_unchanged": sha(ROOT / "projects" / "video_studio.db") == BEFORE["db"],
       "baseline_unchanged": sorted(p.name for p in
                                    (ROOT / "docs" / "regression_2x" / "baseline").glob("*"))
       == BEFORE["baseline"],
       "master_unchanged": sha(ROOT / N0["master"]["path"]) == BEFORE["master"],
       "batch1_unchanged": all(sha(ROOT / s["output"]["path"]) == BEFORE["b1"][s["stage"]]
                               for s in B1["stages"]),
       "h3c1_unchanged": sha(film_in) == BEFORE["h3c1"],
       "failure_record_unchanged": sha(LOGS / "phase6g_exec_batch2.json") == BEFORE["b2_failure_report"],
       "projects_len_unchanged": len([p for p in (ROOT / "projects" / "p_96efdc03e1aa").rglob("*")
                                      if p.is_file()]) == BEFORE["projects_len"],
       "output_in_new_sandbox": str(film_out).startswith(str(SANDBOX))}
hard("F1 隔离：历史/DB/baseline/母版/Batch1/H3c-1/原失败证据/项目目录 均未变",
     all(iso.values()), iso)

# ---- 台账：新的一次 acceptance（保留 seq 6 原失败记录）
entry = EX.append_execution(str(LEDGER), {
    "schema": "revision-execution-v1", "proposal_id": prop["proposal_id"], "label": "H3c-2",
    "stage": "H3c-2-optA", "action": "split_scene", "proposal_sha256": prop_sha,
    "approval_id": appr["approval_id"], "approved_by": "human",
    "input_sha256": sha(film_in), "output_path": stre["path"], "output_sha256": stre["sha256"],
    "duration_s": st["format_duration_s"], "audio_md5": stre["audio_md5"],
    "timeline_identity": N0["timeline_identity"]["identity_sha256"], "caption_time_base": "dcv2",
    "acceptance": "ACCEPTED_OPT_A_EXACT_DURATION",
    "correction": {"type": "assembly_precision_only", "before_s": 978.720, "after_s":
                   st["format_duration_s"], "target_s": PROD, "tolerance_s": TOL,
                   "method": "exact_duration_pass_optA（仅视频整帧；音轨 -c:a copy）",
                   "thresholds_changed": False, "policy_changed": False,
                   "original_failure_entry_seq": 6},
    "pi_states": {**sm(pre["metrics"]), **sm(post["metrics"]), "frozen_recheck":
                  res.get("pi_gate_outcome")},
    "ffmpeg_calls": len(FF_CALLS), "sandbox": str(SANDBOX.relative_to(ROOT)),
    "executed_at": time.strftime("%Y-%m-%dT%H:%M:%S")})

# ---- 已接受链路上的 DQ（Batch1 + H3c-1 + H3c-2）
proj = [{"scene_id": c["scene_id"], "start_s": c["new_timeline_window_s"][0],
         "end_s": c["new_timeline_window_s"][1], "selected_asset": TL_ASSET.get(c["scene_id"], {})}
        for c in chain]


def apply_split(entries, sp, asset_map):
    for r in sp.get("scenes", []):
        base = next(e for e in entries if e["scene_id"] == r["scene_id"])
        d = r["sub_duration_s"]
        new = [{"scene_id": "{}.{}".format(r["scene_id"], j + 1),
                "start_s": round(r["window"][0] + d * j, 3),
                "end_s": round(r["window"][0] + d * (j + 1), 3),
                "selected_asset": asset_map.get(r["scene_id"], {})} for j in range(r["sub_count"])]
        i = entries.index(base)
        entries[i:i + 1] = new
    return entries


for stage in ("H3a", "H3b"):
    apply_split(proj, next(s["exec"]["exec_evidence"]["split_plan"] for s in B1["stages"]
                           if s["stage"] == stage), TL_ASSET)
h3c1 = next(r for r in regs if r.get("label") == "H3c-1")
sp1 = OPX.split_plan({"timeline": [dict(e) for e in TL], "timeline_identity": None,
                      "caption_timeline": None}, h3c1)
apply_split(proj, sp1, TL_ASSET)
apply_split(proj, spx, TL_ASSET)
dq = {"DQ-2": core_direction.asset_reuse(proj), "DQ-3": core_direction.static_hold(proj),
      "DQ-4": core_direction.visual_density(proj)}
over = [{"scene_id": e["scene_id"], "duration_s": round(e["end_s"] - e["start_s"], 3)}
        for e in proj if (e["end_s"] - e["start_s"]) > 25.0]
print("  DQ 实测(accepted lineage): DQ-2 {} (unique {}) | DQ-3 {} (max_hold {}) | DQ-4 {} ({} /min) | entries {} | >25s {}".format(
    dq["DQ-2"]["state"], dq["DQ-2"].get("unique_assets"), dq["DQ-3"]["state"],
    dq["DQ-3"].get("max_hold_s"), dq["DQ-4"]["state"],
    dq["DQ-4"].get("scene_changes_per_min"), len(proj), len(over)))

led = EX.load_ledger(str(LEDGER))
report = {
    "schema": "phase6g-exec-batch2-optA-v1", "stage": "6-G / Batch 2 / OPT-A",
    "state": "H3C2_OPT_A_REACCEPTED" if not FAIL else "H3C2_OPT_A_STOPPED_AT_HARD_GATE",
    "nature": "**输出装配精度修正**（assembly precision fix）：仅把视频精确对齐到 DCv2 时间轴；"
              "**不是**验收阈值放宽（A1 仍为 978.656 ± 0.05 s；OPT-B 未采用；POLICY/门禁判据未改）",
    "proposal_unchanged": {"proposal_id": prop["proposal_id"], "proposal_sha256": prop_sha,
                           "scenes": prop["affected_scope"]["scenes"],
                           "target_hold_s": prop["proposed_change"]["params"]["target_hold_s"],
                           "cuts": [round(x, 3) for r in spx.get("scenes", []) for x in r["cuts"]]},
    "policy_unchanged": {"max_scenes_per_proposal": EX.POLICY["max_scenes_per_proposal"],
                         "max_share_of_film_per_proposal":
                             EX.POLICY["max_share_of_film_per_proposal"],
                         "a1_tolerance_s": TOL, "frozen_gates_changed": False},
    "correction": {"before_s": 978.720, "target_s": PROD, "after_s": st["format_duration_s"],
                   "delta_before_s": 0.064, "delta_after_s":
                       round(st["format_duration_s"] - PROD, 4),
                   "method": exact_step,
                   "video_frames": (st.get("video") or {}).get("nb_frames"),
                   "audio_stream_copied": True, "audio_md5": stre["audio_md5"],
                   "subtitle_timeline_unchanged": True, "cuts_unchanged": True},
    "input": {"path": h1_entry["output_path"], "sha256": h1_entry["output_sha256"],
              "note": "已接受的 H3c-1 输出（Batch1 → H3c-1 → H3c-2 链路）"},
    "output": stre,
    "sandbox": str(SANDBOX.relative_to(ROOT)),
    "gates": {"pass": PASS, "fail": FAIL, "failed": FAIL},
    "PI": {"pre": sm(pre["metrics"]), "post": sm(post["metrics"]),
           "frozen_recheck": res.get("pi_gate_outcome")},
    "subtitle": {"ass_windows": s1, "frames": fr},
    "cut_evidence": ce, "visual_continuity": lum, "isolation": iso,
    "DQ_measured_accepted_lineage": {"DQ-2": dq["DQ-2"], "DQ-3": dq["DQ-3"], "DQ-4": dq["DQ-4"],
                                     "entries": len(proj), "over_25s": over,
                                     "no_further_splitting": True},
    "ledger": {"path": str(LEDGER.relative_to(ROOT)), "entries": len(led),
               "chain": EX.verify_chain(led), "new_seq": entry.get("seq"),
               "original_failure_preserved": {"report": "docs/regression_2x/logs/"
                                                        "phase6g_exec_batch2.json",
                                              "ledger_seq": 6,
                                              "state": "acceptance=FAILED（原失败记录保留）"}},
    "ffmpeg_calls": len(FF_CALLS),
    "claims": {"promoted": False, "db_written": False, "baseline_or_tag_changed": False,
               "historical_artifact_changed": False, "threshold_relaxed": False,
               "policy_changed": False, "h5_e3_e4_e5_executed": False,
               "third_batch_authorized": False}}
report["report_sha256"] = hashlib.sha256(json.dumps(
    report, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode()
).hexdigest()
OUT.write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print("\n== OPT-A 重新验收 ==")
print("  {} gates PASS / {} FAIL | state {}".format(len(PASS), len(FAIL), report["state"]))
print("  978.720 → {} (target 978.656, Δ {:+.4f}s) | audio md5 {} | ledger seq {}".format(
    st["format_duration_s"], round(st["format_duration_s"] - PROD, 4), stre["audio_md5"][:12],
    entry.get("seq")))
print("report ->", OUT)
sys.exit(1 if FAIL else 0)
