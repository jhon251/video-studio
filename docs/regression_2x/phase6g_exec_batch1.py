# -*- coding: utf-8 -*-
"""6-G —— 第一批**正式 proposal 执行**：H3a → H3b → E1 → E2（逐项完整验收，任一 HARD 失败即 STOP）。

约束：DCv2 timeline + DCv2 caption timeline（禁止 v1）；narration truth / audio_time_base / audio identity
不变；历史 artifact·baseline·tag·DB 不写；正式 execution ledger 用**新台账**（不写 6-E 历史台账）；
不 promote；不执行 H5/E3/E4/E5/H3c；候选不作为后续历史输入。

产出: docs/regression_2x/logs/phase6g_exec_batch1.json（+ 新执行台账 phase6g_exec_ledger.jsonl）
"""
import hashlib
import json
import re
import shutil
import sqlite3
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
PKG = json.loads((LOGS / "phase6g_rebuild_proposals.json").read_text(encoding="utf-8"))
N0 = json.loads((LOGS / "phase6g_n0_dcv2_master.json").read_text(encoding="utf-8"))
OUT = LOGS / "phase6g_exec_batch1.json"
LEDGER = LOGS / "phase6g_exec_ledger.jsonl"
FFMPEG, FFPROBE = ROOT / "bin" / "ffmpeg.exe", ROOT / "bin" / "ffprobe.exe"
PROD = P2["math_verification"]["production_duration_s"]
TS = time.strftime("%Y%m%d_%H%M%S")
SANDBOX = ROOT / "output" / "phase6g_exec" / TS
CFG = {"tools": {"ffmpeg": {"path": str(FFMPEG), "ffprobe": str(FFPROBE)}}}
MASTER = ROOT / N0["master"]["path"]
chain = P2["remapping_21_segments"]
by_label = {p["label"]: p for p in PKG["proposals"]}
AUTH = ("人工授权（本回合）：6-G Sandbox 小样已通过 20/20 gates ⇒ 授权第一批正式 proposal "
        "H3a → H3b → E1 → E2；H5/E3/E4/E5/H3c 保持未授权")
STAGES = [("H3a", "H3a-rebuild-split-longest"), ("H3b", "H3b-rebuild-split-next-longest"),
          ("E1", "E1-rebuild-outro-last12s"), ("E2", "E2-rebuild-visual-aid-redesign")]
PASS, FAIL, STAGE_RESULTS = [], [], []
FF_CALLS = []

# ---------------------------------------------------------------- 只读输入
con = sqlite3.connect("file:{}?mode=ro".format(
    (ROOT / "projects" / "video_studio.db").as_posix()), uri=True)
con.row_factory = sqlite3.Row
con.execute("PRAGMA query_only=ON")
rows = [dict(r) for r in con.execute(
    "select type,task_id,path from artifacts where project_id='p_96efdc03e1aa' order by created_at")]
con.close()
script = json.loads(Path(next(r["path"] for r in rows if r["type"] == "script_output")
                         ).read_text(encoding="utf-8"))
voice = json.loads(Path(next(r["path"] for r in rows if r["type"] == "voice_output")
                        ).read_text(encoding="utf-8"))
_ro = next(r for r in rows if r["type"] == "render_output" and r.get("task_id") == "t_d0a54bdf1810")
render = json.loads(Path(_ro["path"]).read_text(encoding="utf-8"))
asset_of = {str(e.get("scene_id")): (e.get("selected_asset") or {})
            for e in (render.get("material_timeline") or []) if e.get("selected_asset")}
payload = [{"narration": s["narration"], "duration_s": s.get("duration_s")}
           for s in script["segments"] if str(s.get("narration", "")).strip()]
cw = [{"scene_id": c["scene_id"], "start_s": c["new_audio_window_s"][0],
       "end_s": c["new_audio_window_s"][1]} for c in chain]
tl = [{"scene_id": c["scene_id"], "start_s": c["new_timeline_window_s"][0],
       "end_s": c["new_timeline_window_s"][1], "selected_asset": asset_of.get(c["scene_id"], {})}
      for c in chain]
cues_dcv2 = core_captions.build_cues(payload, windows=[{"start_s": w["start_s"], "end_s": w["end_s"]}
                                                       for w in cw])
cues_v1 = core_captions.build_cues(payload)
plan = N.narration_plan(script, voice)
GP = core_integrity.gate_policy(CFG)

HIST = {"v9": ROOT / "projects" / "p_96efdc03e1aa" / "output" / "t_d0a54bdf1810_draft.mp4"}
m6c = json.loads((LOGS / "phase6c_batch.json").read_text(encoding="utf-8"))
for c in m6c["candidates"]:
    HIST["c" + str(c["index"])] = ROOT / c["film"]
HIST["e1"] = (ROOT / "output" / "phase6b_m4_sandbox" / "p_96efdc03e1aa_6e" / "output" /
              "t_d0a54bdf1810_draft_6c_rp-ad4bbbee7ea2_outro.mp4")
HIST["e2"] = (ROOT / "output" / "phase6b_m4_sandbox" / "p_96efdc03e1aa_6e2" / "output" /
              "t_d0a54bdf1810_draft_6c_rp-bee31dff3335_vaid.mp4")
BEFORE = {"history": {k: hashlib.sha256(p.read_bytes()).hexdigest() for k, p in HIST.items()
                      if p.is_file()},
          "db": hashlib.sha256((ROOT / "projects" / "video_studio.db").read_bytes()).hexdigest(),
          "baseline": sorted(p.name for p in (ROOT / "docs" / "regression_2x" / "baseline").glob("*")),
          "master": hashlib.sha256(MASTER.read_bytes()).hexdigest(),
          "projects_len": len([p for p in (ROOT / "projects" / "p_96efdc03e1aa").rglob("*")
                               if p.is_file()])}
for d in (SANDBOX / "work", SANDBOX / "out", SANDBOX / "artifacts"):
    d.mkdir(parents=True, exist_ok=True)
script_copy = SANDBOX / "artifacts" / "script_output.json"
script_copy.write_text(json.dumps(script, ensure_ascii=False), encoding="utf-8")
voice_copy = SANDBOX / "artifacts" / "voice_output.json"
voice_copy.write_text(json.dumps(voice, ensure_ascii=False), encoding="utf-8")
master_ass = SANDBOX / "work" / "dcv2_master.ass"
master_ass.write_text(core_captions.to_ass(cues_dcv2, resolution="1280x720"), encoding="utf-8")

_orig_run = OPX._run


def _rec_run(cmd, timeout=3600):
    FF_CALLS.append({"stage": CURRENT.get("stage"), "argv": [str(c) for c in cmd][:16]})
    return _orig_run(cmd, timeout=timeout)


OPX._run = _rec_run
CURRENT = {"stage": None}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def probe(p: Path) -> dict:
    r = subprocess.run([str(FFPROBE), "-v", "error", "-show_entries", "format=duration",
                        "-of", "json", str(p)], capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    return round(float((json.loads(r.stdout or "{}").get("format") or {}).get("duration") or 0), 3)


def amd5(p: Path) -> str:
    r = subprocess.run([str(FFMPEG), "-v", "error", "-i", str(p), "-map", "0:a", "-c", "copy",
                        "-f", "md5", "-"], capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    return (r.stdout or "").strip().split("=")[-1]


def hard(name, ok, detail=None):
    (PASS if ok else FAIL).append(name)
    print("{}  {} {}".format("PASS" if ok else "FAIL", name,
                             "" if ok else json.dumps(detail, ensure_ascii=False,
                                                      default=str)[:250]))
    if not ok:
        raise RuntimeError("BATCH1_GATE_FAILED: " + name)
    return True


def frame(film: Path, t: float, name: str, dur: float | None = None):
    from PIL import Image                                                   # noqa: E402
    import numpy as np                                                      # noqa: E402
    for i, tt in enumerate([t] + ([max(0.0, min(t, dur - 0.25))] if dur else []) + [max(0.0, t - 0.2)]):
        f = SANDBOX / "work" / "acc_{}_{}_{}.png".format(name, str(t).replace(".", "_"), i)
        subprocess.run([str(FFMPEG), "-y", "-v", "error", "-ss", "{:.3f}".format(tt), "-i", str(film),
                        "-frames:v", "1", str(f)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
        if f.is_file():
            return np.asarray(Image.open(f).convert("L"), dtype=np.float32) / 255.0
    return np.zeros((720, 1280), dtype=np.float32)


def mask_at(t: int, ass: Path):
    from PIL import Image                                                   # noqa: E402
    import numpy as np                                                      # noqa: E402
    f = SANDBOX / "work" / "mask_{}.png".format(t)
    subprocess.run([str(FFMPEG), "-y", "-v", "error", "-f", "lavfi", "-i",
                    "color=c=black:s=1280x720:r=1", "-vf",
                    "ass=filename='{}':fontsdir='C\\:/Windows/Fonts'".format(
                        ass.as_posix().replace(":", "\\:")), "-ss", str(int(t)), "-frames:v", "1",
                    str(f)], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return np.asarray(Image.open(f).convert("L"), dtype=np.float32) / 255.0


def erode(b):
    """布尔掩膜腐蚀 1px：取字形**内部**（不受抗锯齿/描边/背景影响）。"""
    return (b[1:-1, 1:-1] & b[:-2, 1:-1] & b[2:, 1:-1] & b[1:-1, :-2] & b[1:-1, 2:])


def _norm(x):
    return re.sub(r"\s+", "", str(x or "").replace("\\N", "").replace("\\n", ""))


def parse_ass(p: Path):
    out, fmt, sec_name = [], None, None
    for line in p.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            sec_name = s
            continue
        if sec_name == "[Events]" and s.startswith("Format:"):
            fmt = [x.strip() for x in s.split(":", 1)[1].split(",")]
        elif sec_name == "[Events]" and s.startswith("Dialogue:") and fmt:
            d = dict(zip(fmt, s.split(":", 1)[1].split(",", len(fmt) - 1)))
            h, m, ss = d["Start"].strip().split(":")
            h2, m2, ss2 = d["End"].strip().split(":")
            out.append({"start": round(int(h) * 3600 + int(m) * 60 + float(ss), 3),
                        "end": round(int(h2) * 3600 + int(m2) * 60 + float(ss2), 3),
                        "text": d["Text"].strip()})
    return sorted(out, key=lambda x: x["start"])


def win_sel(table, w0, w1):
    r = []
    for c in table:
        if float(c["end"]) <= w0 + 1e-6 or float(c["start"]) >= w1 - 1e-6:
            continue
        r.append({"start": round(max(float(c["start"]), w0) - w0, 3),
                  "end": round(min(float(c["end"]), w1) - w0, 3), "text": c.get("text")})
    return sorted(r, key=lambda x: x["start"])


def cue_at(t, table):
    return [c for c in table if float(c["start"]) <= t < float(c["end"])]


def mk_ctx(film: Path, box: Path):
    return OPX.attach_dcv2_time_base(
        {"box": str(box), "root": str(ROOT), "ffmpeg": str(FFMPEG), "ffprobe": str(FFPROBE),
         "config": CFG, "film": str(film), "cues": cues_dcv2, "evidence": None,
         "artifacts": {"script_output": str(script_copy), "voice_output": str(voice_copy)}},
        timeline=tl, caption_windows=cw, production_duration_s=PROD,
        source="docs/regression_2x/logs/phase6f_rebuild_plan_v2.json")


# ---------------------------------------------------------------- 逐项执行
film_in = SANDBOX / "out" / "stage0_dcv2_master.mp4"
shutil.copy2(MASTER, film_in)
proj_tl = [dict(e) for e in tl]
STOPPED = None
for sid, label in STAGES:
    CURRENT["stage"] = sid
    box = SANDBOX / "work" / sid
    box.mkdir(parents=True, exist_ok=True)
    (box / "work").mkdir(exist_ok=True)
    (box / "output").mkdir(exist_ok=True)
    prop = by_label[label]
    print("\n===== {} {} =====".format(sid, label))
    stage = {"stage": sid, "proposal_id": prop["proposal_id"], "label": label,
             "action": prop["action"],
             "proposal_sha256": EX.proposal_sha256(prop),
             "package_recorded_sha256": next(h["proposal_sha256"] for h in PKG["hashes"]["proposals"]
                                             if h["label"] == label),
             "input": {"path": str(film_in.relative_to(ROOT)), "sha256": sha(film_in),
                       "duration_s": probe(film_in)}}
    hard("{} 提案身份一致（verify_proposal 空错误 + sha == package 记录）".format(sid),
         core_revision.verify_proposal(prop) == [] and stage["proposal_sha256"]
         == stage["package_recorded_sha256"], stage)
    appr = EX.make_approval(prop, "APPROVE", "human", AUTH,
                            {"authorization": "6-G 第一批正式执行授权（本回合人工指令）",
                             "scope": "H3a→H3b→E1→E2", "not_authorized": ["H5", "E3", "E4", "E5",
                                                                         "H3c"]})
    ctx = mk_ctx(film_in, box)
    ident = OPX.assert_timeline_identity(ctx)
    base = OPX.caption_time_base(ctx)
    hard("{} 前置：timeline identity == DCv2（{}）".format(sid, ident.get("identity_sha256", "")[:16]),
         ident.get("enforced") is True
         and ident["identity_sha256"] == N0["timeline_identity"]["identity_sha256"], ident)
    hard("{} 前置：caption timeline == DCv2（禁止 v1）".format(sid), base["mode"] == "dcv2", base)
    gate = EX.gate_execution(prop, [appr], None)
    hard("{} 执行门禁通过（APPROVED + 局部化）".format(sid), gate.get("allowed") is True,
         {"code": gate.get("code"), "why": gate.get("why")})
    res = EX.execute_proposal(prop, [appr], OPX.EXECUTORS, ctx, recheck=OPX.pi_recheck)
    hard("{} 执行 SUCCEEDED（state={}）".format(sid, res.get("state")),
         res.get("state") == "SUCCEEDED", {"state": res.get("state"), "why": res.get("why"),
                                          "steps": (res.get("steps") or [])[:2]})
    out_rel = (res.get("outputs") or [{}])[0].get("path")
    out_src = ROOT / out_rel
    film_out = SANDBOX / "out" / "{}_{}.mp4".format(sid, label)
    shutil.copy2(out_src, film_out)
    dur, md5 = probe(film_out), amd5(film_out)
    stage["output"] = {"path": str(film_out.relative_to(ROOT)), "sha256": sha(film_out),
                       "duration_s": dur, "audio_md5": md5}
    stage["exec"] = {"state": res.get("state"), "proposal_sha256": res.get("proposal_sha256"),
                     "approval_ref": res.get("approval_ref"), "steps": res.get("steps"),
                     "recheck_pi_gate_outcome": res.get("pi_gate_outcome"),
                     "exec_evidence": res.get("exec_evidence"), "notes": res.get("notes")}
    # ---- 验收 A：duration + audio identity
    hard("{} A1 duration == 978.656±0.05（实测 {}）".format(sid, dur), abs(dur - PROD) <= 0.05, dur)
    hard("{} A2 audio identity == 母版（{}）".format(sid, md5[:12]),
         md5 == amd5(MASTER), {"out": md5, "master": amd5(MASTER)})
    # ---- 验收 B：字幕（确定性 + 帧级）
    # 受影响窗口：切分用**执行器回报的子镜几何**；叠加/片尾卡用 affected_scope.window
    affected = []
    if prop["action"] == "split_scene":
        spx = ((res.get("exec_evidence") or {}).get("split_plan") or {}).get("scenes") or []
        for r in spx:
            d = r["sub_duration_s"]
            affected.extend([[round(r["window"][0] + d * j, 3), round(r["window"][0] + d * (j + 1), 3)]
                             for j in range(r["sub_count"])])
    elif prop["action"] in ("add_outro_card", "add_visual_aid"):
        affected = [prop["affected_scope"]["window"]]
    ass_files = sorted((box / "work").glob("cap_*.ass"))
    s1 = []
    for ap in ass_files:
        parsed = parse_ass(ap)
        best = None
        for w in affected:
            d = win_sel(cues_dcv2, w[0], w[1])
            if d and len(d) == len(parsed) and all(
                    abs(a["start"] - b["start"]) < 0.02 and abs(a["end"] - b["end"]) < 0.02
                    and _norm(a["text"]) == _norm(b["text"]) for a, b in zip(parsed, d)):
                best = {"ass": ap.name, "window": w, "cues": len(parsed), "dcv2_match": True,
                        "v1_differs": win_sel(cues_v1, w[0], w[1]) != d}
                break
        s1.append(best or {"ass": ap.name, "dcv2_match": False, "cues": len(parsed)})
    hard("{} B1 本阶段窗口 ASS == DCv2 表（{} 个）".format(sid, len(ass_files)),
         bool(ass_files) and all(m.get("dcv2_match") for m in s1), s1)
    hard("{} B2 同窗口 v1 选择 ≠ DCv2（负对照）".format(sid),
         all(m.get("v1_differs") for m in s1), s1)
    speech_ts = []
    for w in affected[:3]:
        cc = [c for c in cues_dcv2 if c["start"] >= w[0] and c["end"] <= w[1]]
        if cc:
            speech_ts.append(round((cc[0]["start"] + cc[0]["end"]) / 2, 3))
    fr = []
    for t in speech_ts:
        m = mask_at(int(t), master_ass)
        ink = m > 0.5
        e = erode(ink)
        a = frame(film_out, t, sid + "sp", dur)
        b = frame(MASTER, t, sid + "mst", PROD)
        if not e.any():
            fr.append({"t": t, "mask_px": int(ink.sum()), "glyph_core_px": 0})
            continue
        d = float(abs(a[1:-1, 1:-1][e] - b[1:-1, 1:-1][e]).mean())
        mx = float(a[1:-1, 1:-1][e].max())
        fr.append({"t": t, "mask_px": int(ink.sum()), "glyph_core_px": int(e.sum()),
                   "ink_diff_vs_master": round(d, 4), "max_ink": round(mx, 3)})
    hard("{} B3 语音时刻字形与母版一致（腐蚀字形差分 < 0.15 且有墨迹）".format(sid),
         bool(fr) and all(r.get("glyph_core_px", 0) > 0 and r["ink_diff_vs_master"] < 0.15
                          and r["max_ink"] > 0.5 for r in fr), fr)
    stage["acceptance_subtitle"] = {"ass": s1, "frames": fr}
    # ---- 验收 C：动作相关
    if prop["action"] == "split_scene":
        ce = (res.get("exec_evidence") or {}).get("cut_evidence") or []
        hard("{} C1 切点证据 all_distinct（{} 切点）".format(sid, len(ce)),
             bool(ce) and all(c["distinct"] for c in ce), ce)
        sp = (res.get("exec_evidence") or {}).get("split_plan") or {}
        hard("{} C2 子镜均 ≤ target_hold_s=25".format(sid),
             all(r["sub_duration_s"] <= 25.0 + 1e-6 for r in sp.get("scenes", [])),
             [(r["scene_id"], round(r["sub_duration_s"], 3)) for r in sp.get("scenes", [])])
        for r in sp.get("scenes", []):
            base_e = next(e for e in proj_tl if e["scene_id"] == r["scene_id"])
            d = r["sub_duration_s"]
            new_entries = [{"scene_id": "{}.{}".format(r["scene_id"], j + 1),
                            "start_s": round(r["window"][0] + d * j, 3),
                            "end_s": round(r["window"][0] + d * (j + 1), 3),
                            "selected_asset": base_e.get("selected_asset")}
                           for j in range(r["sub_count"])]
            i = proj_tl.index(base_e)
            proj_tl[i:i + 1] = new_entries
        stage["projected_timeline_entries"] = len(proj_tl)
    if prop["action"] == "add_outro_card":
        tw = prop["affected_scope"]["window"]
        tail_t = round(tw[1] - 0.9, 3)
        a = frame(film_out, tail_t, sid + "tail", dur)
        mo = frame(MASTER, tail_t, sid + "mtail", PROD)
        bot = float(abs(a[int(a.shape[0] * 0.85):] - mo[int(mo.shape[0] * 0.85):]).mean())
        mid = float(abs(a[int(a.shape[0] * 0.50):int(a.shape[0] * 0.75)]
                        - mo[int(mo.shape[0] * 0.50):int(mo.shape[0] * 0.75)]).mean())
        hard("{} C1 收尾区底部带无字幕（diff<0.03）且 mid 带出现卡片（diff>0.03）".format(sid),
             bot < 0.03 and mid > 0.03 and not cue_at(tail_t, cues_dcv2),
             {"t": tail_t, "bottom_diff": round(bot, 4), "mid_diff": round(mid, 4)})
        stage["acceptance_action"] = {"tail_t": tail_t, "bottom_diff": round(bot, 4),
                                      "mid_diff": round(mid, 4)}
    if prop["action"] == "add_visual_aid":
        w = prop["affected_scope"]["window"]
        t = round((w[0] + w[1]) / 2, 3)
        a = frame(film_out, t, sid + "aid", dur)
        m = frame(film_in, t, sid + "in", PROD)
        import numpy as np                                                  # noqa: E402
        h = a.shape[0]
        diff_mid = float(abs(a[int(h * 0.20):int(h * 0.60)] - m[int(h * 0.20):int(h * 0.60)]).mean())
        diff_bot = float(abs(a[int(h * 0.90):] - m[int(h * 0.90):]).mean())
        hard("{} C1 叠加层可见（中带 diff>0.02）且底部字幕安全区未额外变化（<0.20）".format(sid),
             diff_mid > 0.02 and diff_bot < 0.20,
             {"t": t, "mid_diff": round(diff_mid, 4), "bottom_diff": round(diff_bot, 4)})
        stage["acceptance_action"] = {"t": t, "mid_diff": round(diff_mid, 4),
                                      "bottom_diff": round(diff_bot, 4)}
    # ---- 验收 D：PI-1..6（DCv2 口径，权威）+ 冻结口径复核（记录）
    pre = core_integrity.pre_render_gate(script.get("segments") or [], voice, PROD, GP,
                                         narration_duration_s=voice.get("narration_duration_s"),
                                         narration_plan=plan, cues=cues_dcv2,
                                         narration_padding_s=PROD - float(
                                             voice.get("narration_duration_s") or 0))
    post = core_integrity.post_render_gate(film_out, PROD, cues_dcv2,
                                           voice.get("narration_duration_s"), True, str(FFMPEG),
                                           str(FFPROBE), GP, narration_plan=plan)
    st = lambda m: {a: (b.get("state") if isinstance(b, dict) else b) for a, b in m.items()}
    stage["PI"] = {"pre_blocked": pre["blocked"], "post_blocked": post["blocked"],
                   "pre_states": st(pre["metrics"]), "post_states": st(post["metrics"]),
                   "promote_blocked": post.get("promote_blocked"),
                   "frozen_recheck_recorded": res.get("pi_gate_outcome")}
    hard("{} D1 pre-render 未阻断 + PI-1/PI-2/PI-6/G-TL/G-PAD/G-SUB 全 PASS".format(sid),
         (not pre["blocked"]) and all(st(pre["metrics"]).get(g) == "PASS"
                                      for g in ("PI-1", "PI-2", "PI-6", "G-TL", "G-PAD", "G-SUB")),
         {"blocked": pre["blocked"], "states": st(pre["metrics"]), "reasons": pre["reasons"]})
    hard("{} D2 post-render：PI-3 PASS 且 promote 未被静音阻断".format(sid),
         st(post["metrics"]).get("PI-3") == "PASS" and not post.get("promote_blocked"),
         {"PI-3": post["metrics"]["PI-3"], "reasons": post["reasons"]})
    # ---- 验收 E：视觉连续 / 黑帧 / DQ（仅记录）
    bnd = sorted({round(w[0], 3) for w in affected} | {round(w[1] - 0.05, 3) for w in affected})
    lum = {str(b): round(float(frame(film_out, b, sid + "bd", dur).mean()), 4) for b in bnd[:6]}
    stage["visual_continuity"] = {"boundary_luma": lum,
                                  "black_frames": [k for k, v in lum.items() if v < 0.02]}
    hard("{} E1 边界无黑帧".format(sid), not stage["visual_continuity"]["black_frames"],
         stage["visual_continuity"])
    dq_src = [dict(e) for e in proj_tl]
    stage["DQ_measured"] = {"DQ-2": core_direction.asset_reuse(dq_src),
                            "DQ-3": core_direction.static_hold(dq_src),
                            "DQ-4": core_direction.visual_density(dq_src),
                            "note": "**实测记录，非闭环判定**；H3c 未授权 ⇒ >25s 场景仍可能存在"}
    print("   DQ 实测: DQ-3 state={} max_hold={} | DQ-4 {} 镜/分 | DQ-2 唯一素材 {}".format(
        stage["DQ_measured"]["DQ-3"].get("state"), stage["DQ_measured"]["DQ-3"].get("max_hold_s"),
        stage["DQ_measured"]["DQ-4"].get("scene_changes_per_min"),
        stage["DQ_measured"]["DQ-2"].get("unique_assets")))
    # ---- 验收 F：隔离
    iso = {"history_unchanged": all(hashlib.sha256(HIST[k].read_bytes()).hexdigest() == v
                                    for k, v in BEFORE["history"].items() if HIST[k].is_file()),
           "db_unchanged": hashlib.sha256((ROOT / "projects" / "video_studio.db").read_bytes()
                                          ).hexdigest() == BEFORE["db"],
           "baseline_unchanged": sorted(p.name for p in
                                        (ROOT / "docs" / "regression_2x" / "baseline").glob("*"))
           == BEFORE["baseline"],
           "master_unchanged": sha(MASTER) == BEFORE["master"],
           "projects_len": len([p for p in (ROOT / "projects" / "p_96efdc03e1aa").rglob("*")
                                if p.is_file()]) == BEFORE["projects_len"],
           "output_in_sandbox": str(film_out).startswith(str(SANDBOX))}
    hard("{} F1 隔离：历史/DB/baseline/母版/项目目录均未变".format(sid), all(iso.values()), iso)
    stage["isolation"] = iso
    stage["ffmpeg_calls"] = len([c for c in FF_CALLS if c["stage"] == sid])
    STAGE_RESULTS.append(stage)
    entry = EX.append_execution(str(LEDGER), {
        "schema": "revision-execution-v1", "proposal_id": prop["proposal_id"], "label": label,
        "action": prop["action"], "proposal_sha256": stage["proposal_sha256"],
        "approval_id": appr["approval_id"], "approved_by": "human",
        "stage": sid, "input_sha256": stage["input"]["sha256"],
        "output_path": stage["output"]["path"], "output_sha256": stage["output"]["sha256"],
        "duration_s": dur, "audio_md5": md5, "timeline_identity":
            N0["timeline_identity"]["identity_sha256"],
        "caption_time_base": "dcv2", "pi_states": stage["PI"]["pre_states"] | stage["PI"]["post_states"],
        "dq_measured": {k: stage["DQ_measured"][k].get("state") for k in ("DQ-2", "DQ-3", "DQ-4")},
        "ffmpeg_calls": stage["ffmpeg_calls"], "sandbox": str(SANDBOX.relative_to(ROOT)),
        "executed_at": time.strftime("%Y-%m-%dT%H:%M:%S")})
    stage["ledger_entry"] = {"seq": entry.get("seq"), "entry_sha256": entry.get("entry_sha256")}
    film_in = film_out
    print("   -> {} ({}s, sha {})".format(stage["output"]["path"], dur,
                                          stage["output"]["sha256"][:12]))

ledger_entries = EX.load_ledger(str(LEDGER))
chainchk = EX.verify_chain(ledger_entries)
report = {"schema": "phase6g-exec-batch1-v1", "stage": "6-G",
          "state": "BATCH1_SUCCEEDED_AWAITING_HUMAN_AUTHORIZATION" if not FAIL
          else "BATCH1_STOPPED_AT_HARD_GATE",
          "authorized_order": ["H3a", "H3b", "E1", "E2"],
          "not_authorized_kept": {"H5": "PENDING_HUMAN_ASSET", "E3": "AWAITING_H-6",
                                  "E4/E5": "PENDING_D8", "H3c": "authorized=false"},
          "sandbox": str(SANDBOX.relative_to(ROOT)),
          "timeline_identity": N0["timeline_identity"]["identity_sha256"],
          "master": {"path": N0["master"]["path"], "sha256": N0["master"]["sha256"],
                     "duration_s": N0["master"]["duration_s"]},
          "stages": STAGE_RESULTS,
          "gates": {"pass": len(PASS), "fail": len(FAIL), "failed": FAIL},
          "ledger": {"path": str(LEDGER.relative_to(ROOT)), "entries": len(ledger_entries),
                     "chain": chainchk},
          "ffmpeg_calls_total": len(FF_CALLS),
          "ffmpeg_argv_by_stage": {s: [c["argv"] for c in FF_CALLS if c["stage"] == s][:4]
                                   for s, _ in STAGES},
          "isolation_final": {"history": {k: hashlib.sha256(p.read_bytes()).hexdigest()[:16]
                                          for k, p in HIST.items() if p.is_file()},
                              "db_unchanged": hashlib.sha256(
                                  (ROOT / "projects" / "video_studio.db").read_bytes()
                              ).hexdigest() == BEFORE["db"],
                              "baseline_unchanged": sorted(
                                  p.name for p in (ROOT / "docs" / "regression_2x" /
                                                   "baseline").glob("*")) == BEFORE["baseline"],
                              "master_unchanged": sha(MASTER) == BEFORE["master"]},
          "claims": {"batch1_pass_is_not_overall_dq_pass": True,
                     "directorial_quality_closed": False,
                     "dq3_pass_claimed": False, "dq4_pass_claimed": False,
                     "promoted": False, "baseline_or_tag_changed": False,
                     "historical_registry_written": False,
                     "candidates_used_as_input": False,
                     "note": "第一批 PASS ≠ 整体 DQ-3/DQ-4 PASS，≠ directorial quality 闭环；"
                             "H3c 仍未授权；H5/E3/E4/E5 未执行"}}
report["report_sha256"] = hashlib.sha256(json.dumps(
    report, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode()
).hexdigest()
OUT.write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str), encoding="utf-8")

print("\n== 第一批执行汇总 ==")
for s in STAGE_RESULTS:
    print("  {} {} {}s sha {} | PI pre={} post={} | DQ3={} DQ4={}".format(
        s["stage"], s["output"]["path"].split("/")[-1], s["output"]["duration_s"],
        s["output"]["sha256"][:12], all(v == "PASS" for v in s["PI"]["pre_states"].values()),
        all(v == "PASS" for v in s["PI"]["post_states"].values()),
        s["DQ_measured"]["DQ-3"].get("state"), s["DQ_measured"]["DQ-4"].get("state")))
print("  gates: {} PASS / {} FAIL | ledger {} entries chain_ok={} | ffmpeg {}".format(
    len(PASS), len(FAIL), len(ledger_entries), chainchk.get("ok"), len(FF_CALLS)))
print("  state:", report["state"])
print("report ->", OUT)
sys.exit(1 if FAIL else 0)
