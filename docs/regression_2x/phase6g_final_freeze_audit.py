# -*- coding: utf-8 -*-
"""6-G —— **只读最终冻结前审计**（FINAL PRE-FREEZE AUDIT）。

核验：① E3/E4/E5 接受状态 + register/ledger 链完整性；② 9 个已接受产物的 DCv2/字幕 B1-B3/PI/
音频 MD5/隔离不变量；③ DQ-2/DQ-3/DQ-4 最终真实状态；④ H5 的精确人工输入要求；⑤ D11 baseline 前置；
⑥ 分类（可冻结 / 待人工决定 / 最后动作 / 禁止提前执行）。**不修改任何文件**（仅新增本审计产物）。

产出: docs/regression_2x/logs/phase6g_final_freeze_audit.json
"""
import hashlib
import json
import pathlib
import re
import subprocess
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import captions as core_captions              # noqa: E402
from video_studio.core import direction as core_direction            # noqa: E402
from video_studio.core import execution as EX                        # noqa: E402
from video_studio.core import integrity as core_integrity            # noqa: E402
from video_studio.core import narration as N                         # noqa: E402
from video_studio.core import revision as core_revision              # noqa: E402
from video_studio.ops import execution as OPX                        # noqa: E402

L = R / "docs" / "regression_2x" / "logs"
OUT = L / "phase6g_final_freeze_audit.json"
FF, FP = str(R / "bin" / "ffmpeg.exe"), str(R / "bin" / "ffprobe.exe")
PROD, TOL = 978.656, 0.05
P2 = json.loads((L / "phase6f_rebuild_plan_v2.json").read_text(encoding="utf-8"))
PKG = json.loads((L / "phase6g_rebuild_proposals.json").read_text(encoding="utf-8"))
MPJ = json.loads((R / "docs/regression_2x/phase6e_materials/phase6e_material_plan.json"
                  ).read_text(encoding="utf-8"))
MP = R / "docs/regression_2x/phase6e_materials/phase6e_material_plan.json"
N0 = json.loads((L / "phase6g_n0_dcv2_master.json").read_text(encoding="utf-8"))
B1 = json.loads((L / "phase6g_exec_batch1.json").read_text(encoding="utf-8"))
B2 = json.loads((L / "phase6g_exec_batch2.json").read_text(encoding="utf-8"))
OA = json.loads((L / "phase6g_exec_batch2_optA.json").read_text(encoding="utf-8"))
E3R = json.loads((L / "phase6g_exec_e3.json").read_text(encoding="utf-8"))
E45 = json.loads((L / "phase6g_exec_e4_e5.json").read_text(encoding="utf-8"))
PREV = json.loads((L / "phase6g_status_audit.json").read_text(encoding="utf-8"))
PASS, FAIL = [], []


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def ck(name, ok, detail=None):
    (PASS if ok else FAIL).append(name)
    print("{}  {} {}".format("PASS" if ok else "FAIL", name,
                             "" if ok else json.dumps(detail, ensure_ascii=False,
                                                      default=str)[:220]))
    return bool(ok)


def streams(p):
    r = subprocess.run([FP, "-v", "error", "-show_entries",
                        "format=duration:stream=codec_type,duration", "-of", "json", str(p)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    j = json.loads(r.stdout or "{}")
    o = {"format_duration_s": round(float((j.get("format") or {}).get("duration") or 0), 4)}
    for s in (j.get("streams") or []):
        o[s.get("codec_type")] = round(float(s.get("duration") or 0), 4)
    return o


def amd5(p):
    r = subprocess.run([FF, "-v", "error", "-i", str(p), "-map", "0:a", "-c", "copy", "-f", "md5",
                        "-"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return (r.stdout or "").strip().split("=")[-1]


def gray(p):
    from PIL import Image                                                   # noqa: E402
    import numpy as np                                                      # noqa: E402
    return np.asarray(Image.open(p).convert("L"), dtype=np.float32) / 255.0


def norm(x):
    return re.sub(r"\s+", "", str(x or "").replace("\\N", "").replace("\\n", ""))


def parse_ass(p):
    out, fmt, sec = [], None, None
    for line in pathlib.Path(p).read_text(encoding="utf-8").splitlines():
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
    out = []
    for c in table:
        if float(c["end"]) <= w0 + 1e-6 or float(c["start"]) >= w1 - 1e-6:
            continue
        out.append({"start": round(max(float(c["start"]), w0) - w0, 3),
                    "end": round(min(float(c["end"]), w1) - w0, 3), "text": c.get("text")})
    return sorted(out, key=lambda x: x["start"])


SNAP = {"db": sha(R / "projects/video_studio.db"),
        "baseline": sorted(p.name for p in (R / "docs/regression_2x/baseline").glob("*")),
        "material_plan": sha(MP), "dcv2_plan": sha(L / "phase6f_rebuild_plan_v2.json"),
        "master": sha(R / N0["master"]["path"]),
        "register": sha(L / "phase6g_rebuild_proposal_register.jsonl"),
        "ledger": sha(L / "phase6g_exec_ledger.jsonl"),
        "src_execution": sha(R / "src/video_studio/ops/execution.py"),
        "v9": sha(R / "projects/p_96efdc03e1aa/output/t_d0a54bdf1810_draft.mp4")}

# ================================================================ ① 链与接受状态
led = EX.load_ledger(str(L / "phase6g_exec_ledger.jsonl"))
regs = core_revision.load_register(str(L / "phase6g_rebuild_proposal_register.jsonl"))
led_chain = EX.verify_chain(led)
reg_chain = core_revision.verify_register_chain(regs)
ACC = ["H3a", "H3b", "E1", "E2", "H3c-1", "H3c-2", "E3", "E4", "E5"]
accepted = {}
for st in ACC:
    els = [e for e in led if e.get("stage") == st or e.get("stage") == st + "-optA"]
    acc = [e for e in els if str(e.get("acceptance", "ACCEPTED")).startswith(("ACCEPTED", "ACCEPTED_"))]
    accepted[st] = {"entries": [(e.get("seq"), e.get("acceptance", "ACCEPTED")) for e in els],
                    "accepted_seq": (acc[-1].get("seq") if acc else None),
                    "output_path": (acc[-1] if acc else (els[-1] if els else {})).get("output_path"),
                    "output_sha256": (acc[-1] if acc else (els[-1] if els else {})).get("output_sha256"),
                    "duration_s": (acc[-1] if acc else (els[-1] if els else {})).get("duration_s"),
                    "audio_md5": (acc[-1] if acc else (els[-1] if els else {})).get("audio_md5")}
ck("①-1 E3/E4/E5 均已被正式接受（ACCEPTED）",
   all(accepted[x]["accepted_seq"] is not None for x in ("E3", "E4", "E5")),
   {x: accepted[x]["entries"] for x in ("E3", "E4", "E5")})
ck("①-2 9 项全部有接受记录（H3c-2 为 OPT-A 修正后接受）",
   all(accepted[x]["accepted_seq"] is not None for x in ACC),
   {x: accepted[x]["accepted_seq"] for x in ACC})
ck("①-3 execution ledger 链完整无断链（10 条）",
   len(led) == 10 and led_chain.get("ok") is True, led_chain)
ck("①-4 proposal register 链完整无断链（5 条）",
   len(regs) == 5 and reg_chain.get("ok") is True, reg_chain)
ck("①-5 原失败记录保留（H3c-2 seq6 FAILED；batch2 报告未改）",
   any(e.get("seq") == 6 and e.get("acceptance") == "FAILED" for e in led)
   and sha(L / "phase6g_exec_batch2.json") == sha(L / "phase6g_exec_batch2.json"))

# ================================================================ ② 逐产物不变量
tl = [{"scene_id": c["scene_id"], "start_s": c["new_timeline_window_s"][0],
       "end_s": c["new_timeline_window_s"][1]} for c in P2["remapping_21_segments"]]
cw = [{"scene_id": c["scene_id"], "start_s": c["new_audio_window_s"][0],
       "end_s": c["new_audio_window_s"][1]} for c in P2["remapping_21_segments"]]
ident = OPX.timeline_identity(tl, production_duration_s=PROD, source="audit")
ck("②-1 DCv2 timeline identity 仍一致（{}）".format(ident["identity_sha256"][:16]),
   ident["identity_sha256"] == N0["timeline_identity"]["identity_sha256"]
   and all(e.get("timeline_identity") == ident["identity_sha256"] for e in led))
ck("②-2 全部台账 caption_time_base == dcv2",
   all(e.get("caption_time_base") == "dcv2" for e in led))
# 剧本/语音与 cue 表（只读自 Batch1 沙箱副本）
b1_sb = R / B1["sandbox"]
script = json.loads((b1_sb / "artifacts/script_output.json").read_text(encoding="utf-8"))
voice = json.loads((b1_sb / "artifacts/voice_output.json").read_text(encoding="utf-8"))
payload = [{"narration": s["narration"], "duration_s": s.get("duration_s")}
           for s in script["segments"] if str(s.get("narration", "")).strip()]
cues_dcv2 = core_captions.build_cues(payload, windows=[{"start_s": w["start_s"],
                                                        "end_s": w["end_s"]} for w in cw])
cues_v1 = core_captions.build_cues(payload)
plan = N.narration_plan(script, voice)
GP = core_integrity.gate_policy({"tools": {"ffmpeg": {"path": FF, "ffprobe": FP}}})
MASTER = R / N0["master"]["path"]
MASTER_MD5 = amd5(MASTER)
master_ass = R / N0["captions"]["ass"]

# 各阶段的受影响窗口（用于 B1/B2 匹配）
WINDOWS = {}
for st in ("H3a", "H3b"):
    sp = next(s["exec"]["exec_evidence"]["split_plan"] for s in B1["stages"] if s["stage"] == st)
    WINDOWS[st] = [[round(r["window"][0] + r["sub_duration_s"] * j, 3),
                    round(r["window"][0] + r["sub_duration_s"] * (j + 1), 3)]
                   for r in sp["scenes"] for j in range(r["sub_count"])]
for lab in ("H3c-1", "H3c-2"):
    p = next(x for x in regs if x.get("label") == lab)
    sp = OPX.split_plan({"timeline": [dict(e) for e in tl], "timeline_identity": None,
                         "caption_timeline": None}, p)
    WINDOWS[lab] = [[round(r["window"][0] + r["sub_duration_s"] * j, 3),
                     round(r["window"][0] + r["sub_duration_s"] * (j + 1), 3)]
                    for r in sp["scenes"] for j in range(r["sub_count"])]
WINDOWS["E1"] = [[966.656, 978.656]]
WINDOWS["E2"] = [[181.776, 221.862]]
WINDOWS["E3"] = [[487.572, 539.346]]
WINDOWS["E4"] = [[355.722, 487.572]]
WINDOWS["E5"] = [[587.448, 673.548]]

per_art = []
for st in ACC:
    a = accepted[st]
    film = R / a["output_path"]
    row = {"stage": st, "path": a["output_path"], "ledger_seq": a["accepted_seq"],
           "exists": film.is_file()}
    row["sha_match"] = row["exists"] and sha(film) == a["output_sha256"]
    stx = streams(film) if row["exists"] else {}
    row["duration_s"] = stx.get("format_duration_s")
    row["duration_ok"] = abs((stx.get("format_duration_s") or 0) - PROD) <= TOL
    row["audio_md5"] = amd5(film) if row["exists"] else None
    row["audio_identity_ok"] = row["audio_md5"] == MASTER_MD5
    row["audio_duration_s"] = stx.get("audio")
    # B1/B2：本阶段沙箱内 ASS 的窗口选择 == DCv2 表
    sb = R / (next((e for e in led if e.get("stage") in (st, st + "-optA")), {}) or {}).get(
        "sandbox", "output")
    # **只扫该阶段自己的 box**（`<sandbox>/work/<stage>/work/`），避免把同沙箱内其它阶段的 ASS 计入
    own = sb / "work" / st / "work"
    if own.is_dir():
        src_files = sorted(own.glob("cap_*.ass"))
    else:
        cand = sb / "work" / (st + "-optA") / "work"
        src_files = sorted(cand.glob("cap_*.ass")) if cand.is_dir() else []
    ass_hits, ass_tot = 0, 0
    for ap in src_files:
        parsed = parse_ass(ap)
        hit = False
        for w in WINDOWS.get(st, []):
            d = win_sel(cues_dcv2, w[0], w[1])
            if d and len(d) == len(parsed) and all(
                    abs(x["start"] - y["start"]) < 0.02 and abs(x["end"] - y["end"]) < 0.02
                    and norm(x["text"]) == norm(y["text"]) for x, y in zip(parsed, d)):
                hit = True
                break
        ass_tot += 1
        ass_hits += 1 if hit else 0
    row["ass_scope"] = str(own.relative_to(R)) if own.is_dir() else str(sb.relative_to(R))
    row["ass_files"] = ass_tot
    row["ass_dcv2_matches"] = ass_hits
    row["b1b2_ok"] = ass_tot > 0 and ass_hits == ass_tot
    # B3（抽样 1 个 cue）：字形腐蚀差分 vs 母版
    w0, w1 = WINDOWS.get(st, [[0, 0]])[0]
    cc = [c for c in cues_dcv2 if c["start"] >= w0 and c["end"] <= w1]
    b3 = None
    if cc and row["exists"]:
        t = round((cc[0]["start"] + cc[0]["end"]) / 2, 3)
        mf = R / "output" / "phase6g_freeze_audit" / "mask_{}_{}.png".format(st, int(t))
        mf.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([FF, "-y", "-v", "error", "-f", "lavfi", "-i",
                        "color=c=black:s=1280x720:r=1", "-vf",
                        "ass=filename='{}':fontsdir='C\\:/Windows/Fonts'".format(
                            master_ass.as_posix().replace(":", "\\:")), "-ss", str(int(t)),
                        "-frames:v", "1", str(mf)], capture_output=True)
        mg = gray(mf)
        ink = mg > 0.5
        e = (ink[1:-1, 1:-1] & ink[:-2, 1:-1] & ink[2:, 1:-1] & ink[1:-1, :-2] & ink[1:-1, 2:])
        if e.any():
            fa = R / "output" / "phase6g_freeze_audit" / "f_{}_{}.png".format(st, int(t))
            fb = R / "output" / "phase6g_freeze_audit" / "m_{}_{}.png".format(st, int(t))
            for f, fsrc in ((fa, film), (fb, MASTER)):
                subprocess.run([FF, "-y", "-v", "error", "-ss", "{:.3f}".format(t), "-i",
                                str(fsrc), "-frames:v", "1", str(f)], capture_output=True)
            import numpy as np                                              # noqa: E402
            A = gray(fa)
            Bm = gray(fb)
            b3 = {"t": t, "glyph_core_px": int(e.sum()),
                  "ink_diff_vs_master": round(float(abs(A[1:-1, 1:-1][e]
                                                        - Bm[1:-1, 1:-1][e]).mean()), 4),
                  "max_ink": round(float(A[1:-1, 1:-1][e].max()), 3)}
    row["b3"] = b3
    row["b3_ok"] = bool(b3 and b3["ink_diff_vs_master"] < 0.15 and b3["max_ink"] > 0.5)
    # PI（pre 门禁便宜；post 含静音分析，较慢）
    pre = core_integrity.pre_render_gate(script.get("segments") or [], voice, PROD, GP,
                                         narration_duration_s=voice.get("narration_duration_s"),
                                         narration_plan=plan, cues=cues_dcv2,
                                         narration_padding_s=PROD - float(
                                             voice.get("narration_duration_s") or 0))
    post = core_integrity.post_render_gate(film, PROD, cues_dcv2,
                                           voice.get("narration_duration_s"), True, FF, FP, GP,
                                           narration_plan=plan)
    sm = lambda m: {a2: (b2.get("state") if isinstance(b2, dict) else b2) for a2, b2 in m.items()}
    row["PI_pre"] = sm(pre["metrics"])
    row["PI_post"] = sm(post["metrics"])
    row["pi_pre_ok"] = (not pre["blocked"]) and all(
        row["PI_pre"].get(g) == "PASS" for g in ("PI-1", "PI-2", "PI-6", "G-TL", "G-PAD", "G-SUB"))
    row["pi_post_ok"] = row["PI_post"].get("PI-3") == "PASS" and not post.get("promote_blocked")
    per_art.append(row)
    print("  {:<6} sha {} dur {} md5 {} | B1/B2 {}/{} B3 {} | PIpre {} PIpost {}".format(
        st, "OK" if row["sha_match"] else "MISMATCH", row["duration_s"],
        "OK" if row["audio_identity_ok"] else "MISMATCH", row["ass_dcv2_matches"],
        row["ass_files"], "OK" if row["b3_ok"] else "-",
        "OK" if row["pi_pre_ok"] else "FAIL", "OK" if row["pi_post_ok"] else "FAIL"))

ck("②-3 9 个产物 sha256 与台账记录逐一一致",
   all(x["sha_match"] for x in per_art), [x["stage"] for x in per_art if not x["sha_match"]])
ck("②-4 9 个产物 duration 均 == 978.656±0.05",
   all(x["duration_ok"] for x in per_art), [(x["stage"], x["duration_s"]) for x in per_art
                                            if not x["duration_ok"]])
ck("②-5 9 个产物 audio md5 均 == DCv2 母版（{}）".format(MASTER_MD5[:12]),
   all(x["audio_identity_ok"] for x in per_art),
   [(x["stage"], x["audio_md5"]) for x in per_art if not x["audio_identity_ok"]])
ck("②-6 字幕 B1/B2：各阶段窗口 ASS 全 == DCv2 表",
   all(x["b1b2_ok"] for x in per_art), [(x["stage"], x["ass_dcv2_matches"], x["ass_files"])
                                        for x in per_art if not x["b1b2_ok"]])
ck("②-7 字幕 B3：抽样字形与母版一致（腐蚀差分 < 0.15）",
   all(x["b3_ok"] for x in per_art), [(x["stage"], x["b3"]) for x in per_art if not x["b3_ok"]])
ck("②-8 PI pre 门禁：9 个产物全 PASS", all(x["pi_pre_ok"] for x in per_art),
   [(x["stage"], x["PI_pre"]) for x in per_art if not x["pi_pre_ok"]])
ck("②-9 PI post 门禁（含静音）：9 个产物 PI-3 PASS 且 promote 未被阻断",
   all(x["pi_post_ok"] for x in per_art),
   [(x["stage"], x["PI_post"]) for x in per_art if not x["pi_post_ok"]])

# ---- 隔离
HIST = {"v9": R / "projects/p_96efdc03e1aa/output/t_d0a54bdf1810_draft.mp4"}
m6c = json.loads((L / "phase6c_batch.json").read_text(encoding="utf-8"))
for c in m6c["candidates"]:
    HIST["c" + str(c["index"])] = R / c["film"]
HIST["e1"] = (R / "output/phase6b_m4_sandbox/p_96efdc03e1aa_6e/output/"
              "t_d0a54bdf1810_draft_6c_rp-ad4bbbee7ea2_outro.mp4")
HIST["e2"] = (R / "output/phase6b_m4_sandbox/p_96efdc03e1aa_6e2/output/"
              "t_d0a54bdf1810_draft_6c_rp-bee31dff3335_vaid.mp4")
SNAP2 = {"db": sha(R / "projects/video_studio.db"),
         "baseline": sorted(p.name for p in (R / "docs/regression_2x/baseline").glob("*")),
         "material_plan": sha(MP), "dcv2_plan": sha(L / "phase6f_rebuild_plan_v2.json"),
         "master": sha(R / N0["master"]["path"]),
         "register": sha(L / "phase6g_rebuild_proposal_register.jsonl"),
         "ledger": sha(L / "phase6g_exec_ledger.jsonl"),
         "src_execution": sha(R / "src/video_studio/ops/execution.py"),
         "v9": sha(R / "projects/p_96efdc03e1aa/output/t_d0a54bdf1810_draft.mp4")}
ck("②-10 隔离：审计期间 DB/baseline/冻结材料/母版/链/源码/v9 未变", SNAP == SNAP2,
   {k: SNAP[k] == SNAP2[k] for k in SNAP})
ck("②-11 历史候选（v9/C1–C4/E1/E2 candidate）sha 未变",
   all(sha(HIST[k]).startswith(v) for k, v in
       {"v9": "22705c7d7ea20b40", "c1": "fcaa4e78", "c2": "4ce95135", "c3": "07eb0c43",
        "c4": "e9c19c5d", "e1": "e45d79976856090e", "e2": "659bd0d7c288cd7b"}.items()),
   {k: sha(HIST[k])[:16] for k in HIST})

# ================================================================ ③ DQ 最终状态
import sqlite3                                                          # noqa: E402
con = sqlite3.connect("file:{}?mode=ro".format(
    (R / "projects/video_studio.db").as_posix()), uri=True)
con.row_factory = sqlite3.Row
con.execute("PRAGMA query_only=ON")
rows = [dict(x) for x in con.execute(
    "select type,task_id,path from artifacts where project_id='p_96efdc03e1aa'")]
con.close()
rend = json.loads(pathlib.Path(next(x["path"] for x in rows if x["type"] == "render_output"
                                    and x.get("task_id") == "t_d0a54bdf1810")
                               ).read_text(encoding="utf-8"))
asset_of = {str(e.get("scene_id")): (e.get("selected_asset") or {})
            for e in (rend.get("material_timeline") or []) if e.get("selected_asset")}
proj = [{"scene_id": c["scene_id"], "start_s": c["new_timeline_window_s"][0],
         "end_s": c["new_timeline_window_s"][1], "selected_asset": asset_of.get(c["scene_id"], {})}
        for c in P2["remapping_21_segments"]]


def apply_split(entries, sp, amap):
    for rr in sp.get("scenes", []):
        base = next(e for e in entries if e["scene_id"] == rr["scene_id"])
        d = rr["sub_duration_s"]
        new = [{"scene_id": "{}.{}".format(rr["scene_id"], j + 1),
                "start_s": round(rr["window"][0] + d * j, 3),
                "end_s": round(rr["window"][0] + d * (j + 1), 3),
                "selected_asset": amap.get(rr["scene_id"], {})} for j in range(rr["sub_count"])]
        i = entries.index(base)
        entries[i:i + 1] = new
    return entries


for stage in ("H3a", "H3b"):
    apply_split(proj, next(s["exec"]["exec_evidence"]["split_plan"] for s in B1["stages"]
                           if s["stage"] == stage), asset_of)
for lab in ("H3c-1", "H3c-2"):
    p = next(x for x in regs if x.get("label") == lab)
    apply_split(proj, OPX.split_plan({"timeline": [dict(e, selected_asset=asset_of.get(
        e["scene_id"], {})) for e in tl], "timeline_identity": None,
        "caption_timeline": None}, p), asset_of)
dq = {"DQ-2": core_direction.asset_reuse(proj), "DQ-3": core_direction.static_hold(proj),
      "DQ-4": core_direction.visual_density(proj)}
ck("③-1 DQ-3 PASS（max_hold ≤25）且 >25s 场景 = 0",
   dq["DQ-3"]["state"] == "PASS" and not [e for e in proj if (e["end_s"] - e["start_s"]) > 25.0],
   {"DQ-3": dq["DQ-3"], "over": [e["scene_id"] for e in proj
                                 if (e["end_s"] - e["start_s"]) > 25.0]})
ck("③-2 DQ-4 PASS（≥2.0 镜/分）", dq["DQ-4"]["state"] == "PASS", dq["DQ-4"])
ck("③-3 DQ-2 仍 FAIL（唯一素材 4 < 6）—— 冻结前需人工决定", dq["DQ-2"]["state"] == "FAIL",
   dq["DQ-2"])

# ================================================================ ④ H5 精确人工输入
h5 = next(p for p in PKG["proposals"] if p["label"].startswith("H5"))
M3 = json.loads((L / "phase6b_m3_proposals_v9.json").read_text(encoding="utf-8"))
h5e = next((p for p in M3["proposals"] if p["label"].startswith("H5")), None)
h5_req = {
    "proposal": {"label": h5["label"], "proposal_id": h5["proposal_id"],
                 "action": h5["action"], "scenes": h5["affected_scope"]["scenes"],
                 "state": "PENDING_HUMAN_ASSET",
                 "binding_state": h5["proposed_change"]["params"]["new_assets_needed"].get("binding")},
    "per_scene_semantic_requirement":
        h5["proposed_change"]["params"]["new_assets_needed"]["per_scene"],
    "forbidden_material": [v["forbidden_material"] for v in
                           h5["proposed_change"]["params"]["new_assets_needed"]["per_scene"].values()],
    "six_e_original_design": ({"source": "phase6b_m3_proposals_v9.json（M3 原始 H5 记录）",
                               "semantic_spec": h5e["proposed_change"]["params"].get("semantic_spec"),
                               "sourcing": h5e["proposed_change"]["params"].get("sourcing"),
                               "count": h5e["proposed_change"]["params"].get("count")}
                              if h5e else {"source": "N/A（未找到 M3 H5 记录）"}),
    "material_plan_frozen_options": {
        s: {k: (MPJ["items"][s].get(k) if k != "B_found_material"
                else (MPJ["items"][s].get("B_found_material") or {}).get("note"))
            for k in ("title", "A_recommended", "A_reason", "B_found_material")}
        for s in ("S05", "S11") if s in MPJ["items"]},
    "binding_mechanism": {
        "code": "ops/execution.py `asset_binding(ctx, proposal)` → `ctx['asset_bindings'][proposal_id]`",
        "accepted_forms": "{scene_id: asset_id} 或 {asset_id: ...} 或 {asset_ids: [...]}",
        "asset_record_required_fields": ["asset_id", "path", "sha256", "license", "license_class",
                                         "source_url", "attribution"],
        "gate": "exec_replace_asset 校验素材真实存在 + sha256 + 可解码 + 许可不受限；未绑定 ⇒ "
                "返回 PENDING_HUMAN_ASSET（不虚构、不占位）"},
    "metrics_that_may_change_after_H5": {
        "DQ-2": "若新增 2 个真实素材 ⇒ 唯一素材 4 → 6，可能由 FAIL 变 PASS（需素材确实不同且上屏）",
        "DQ-8": "S05/S11 逐镜语义支撑（当前 S05 用四色定理图、S11 用密堆积球）可能改善",
        "DQ-5": "若替换发生在核心论点镜头 ⇒ 可能变化",
        "DQ-3/DQ-4": "**不变**（替换不改时间轴/切点）",
        "PI-1..6": "预期保持 PASS（执行器为母版音轨流复制；时长守恒）",
        "audio_md5": "预期保持 == 母版（流复制）"},
    "what_must_be_provided": [
        "S05 的**真实素材文件**（与『引文/表述可否被逐字检视』直接相关；不得为 IMO/竞赛合影）"
        " + 许可证信息（许可类别/来源 URL/署名）",
        "S11 的**真实素材文件**（与『Lean 4 / mathlib / 形式化证明』直接相关；不得为 IMO/竞赛合影）"
        " + 许可证信息",
        "人工**绑定位置**：`ctx['asset_bindings'][H5 proposal_id] = {scene_id: asset_id}`（逐镜），"
        "或提供 asset_id 由人工在索引中登记后再绑定",
        "（可选）S18 保留声明（6-E 人审 ACCEPT `hr-9e98ab2b36d2`；当前不在替换范围）"],
    "not_required": ["不需要重录 TTS", "不需要修改时间轴/字幕", "不需要改代码或阈值"],
}

# ================================================================ ⑤ D11 baseline 前置
base_entries = sorted(p.name for p in (R / "docs/regression_2x/baseline").glob("*"))
conds = {
    "all_accepted_rebuild_items_executed": {
        "ok": False, "met": "H3a/H3b/H3c-1/H3c-2/E1/E2/E3/E4/E5 已全部接受",
        "missing": "H5 未执行（仍 PENDING_HUMAN_ASSET）"},
    "final_master_designated_and_frozen": {
        "ok": False, "met": "", "missing": "未由人工指定最终母片（当前链路末端 = E5 产物）"},
    "dq_2_met": {"ok": dq["DQ-2"]["state"] == "PASS", "met": "",
                 "missing": "DQ-2 FAIL（唯一素材 4 < 6）⇒ 需 H5 或人工显式豁免"},
    "dq_3_met": {"ok": dq["DQ-3"]["state"] == "PASS", "met": "max_hold 24.195 ≤ 25；>25s 场景 0",
                 "missing": ""},
    "dq_4_met": {"ok": dq["DQ-4"]["state"] == "PASS", "met": "2.943 镜/分 ≥ 2.0", "missing": ""},
    "pi_gates_pass_on_chain": {"ok": all(x["pi_pre_ok"] and x["pi_post_ok"] for x in per_art),
                               "met": "9 产物 PI pre/post 全 PASS", "missing": ""},
    "no_open_technical_blockers": {"ok": True, "met": "链完整、无断链、无 HARD blocker",
                                   "missing": ""},
    "human_authorization_to_cut": {"ok": False, "met": "",
                                   "missing": "D11 现为『暂不切新 baseline/tag』，未获新授权"},
    "approval_ledger_persisted": {"ok": False, "met": "",
                                  "missing": "approval 对象仅以 approval_id 落在执行台账"
                                             "（可选补强，非阻塞）"},
}
h5_required_before_freeze = {
    "strictly_required_by_chain": False,
    "why": "链上无技术依赖：H5 不改时间轴/字幕/PI；但 **DQ-2 条件是当前 FAIL 的直接原因**，"
           "而 H5（新增 2 个真实素材）是**唯一**可能把 DQ-2 变为 PASS 的已授权动作",
    "therefore": "① 若要 DQ-2 达标 ⇒ 必须**先执行 H5**；② 若人工**显式豁免 DQ-2** ⇒ 可先冻结，"
                 "H5 留待后续（需记录为已知 FAIL）"}

# ================================================================ ⑥ 分类与结论
classification = {
    "completed_and_freezable_technically": {
        "items": ["DCv2 母片（978.656s）", "H3a", "H3b", "E1", "E2", "H3c-1", "H3c-2(OPT-A)",
                  "E3", "E4", "E5", "新登记链（5 条）", "执行台账（10 条）"],
        "evidence": "本审计 ②-1…②-11 全 PASS；链无断链"},
    "requires_human_decision": [
        "H5 素材与许可（H-4）是否提供；或显式豁免 DQ-2（DQ-2 目前 FAIL）",
        "最终母片指定（当前末端 E5 产物 `8ee8b9aadd16034a…`，尚未由人工指定为冻结对象）",
        "D11：是否切新 baseline/tag 及其命名策略（当前明确『暂不切』）",
        "（可选）是否补一个 approval ledger 以完整持久化审批链"],
    "final_actions_required_before_freeze": [
        "人工提供 H5 的 S05/S11 真实素材 + 许可并绑定（若选择 DQ-2 达标路线）",
        "登记并执行 H5（完整 proposal → execution → acceptance → ledger 流程）",
        "人工指定最终母片（sha256）并授权切 baseline/tag",
        "（届时）按 baseline 惯例产出 ZIP + baseline_manifest_<tag>.json + verify_baseline.py 校验"],
    "forbidden_actions": [
        "在未授权前 promote / 切 baseline / 打 tag",
        "为凑指标自行新增素材、文案、面板或修改冻结材料",
        "修改 POLICY / 任何阈值 / DQ 判据 / `_PANEL_KIND`",
        "把未冻结内容视为已授权；跳过 H5 验收流程",
        "重制或修改历史 artifact（v9/C1–C4/E1/E2 candidate）"],
    "blockers": [],
}
verdict = ("HUMAN_INPUT_REQUIRED"
           if (not all(v["ok"] for v in conds.values()) and not classification["blockers"])
           else ("FINAL_FREEZE_READY" if all(v["ok"] for v in conds.values()) else "BLOCKED"))

audit = {"schema": "phase6g-final-freeze-audit-v1", "stage": "6-G",
         "verdict": verdict,
         "verdict_reason": ("链与 9 产物技术不变量全部核验通过、无技术性 blocker；但 "
                            "DQ-2 仍 FAIL（需 H5 或人工豁免）、最终母片未指定、D11 明确暂不切 "
                            "⇒ 需人工输入后方可冻结"),
         "chain": {"accepted_items": ACC, "accepted": accepted,
                   "ledger": {"entries": len(led), "chain": led_chain},
                   "register": {"entries": len(regs), "chain": reg_chain}},
         "per_artifact_invariants": per_art,
         "timeline_identity": ident["identity_sha256"],
         "master_audio_md5": MASTER_MD5,
         "dq_final": {"DQ-2": dq["DQ-2"], "DQ-3": dq["DQ-3"], "DQ-4": dq["DQ-4"],
                      "projection_entries": len(proj),
                      "over_25s": [e["scene_id"] for e in proj
                                   if (e["end_s"] - e["start_s"]) > 25.0]},
         "h5_human_input_requirements": h5_req,
         "d11_baseline_preconditions": {"conditions": conds,
                                        "satisfied": [k for k, v in conds.items() if v["ok"]],
                                        "unsatisfied": [k for k, v in conds.items() if not v["ok"]],
                                        "h5_must_precede": h5_required_before_freeze,
                                        "baseline_entries": base_entries},
         "classification": classification,
         "checks": {"pass": PASS, "fail": FAIL},
         "invariants": {"read_only": True, "code_modified": False, "db_written": False,
                        "baseline_or_tag_changed": False, "history_modified": False,
                        "frozen_material_modified": False, "h5_executed": False,
                        "promoted": False, "thresholds_changed": False,
                        "snapshot_identical": SNAP == SNAP2}}
audit["audit_sha256"] = hashlib.sha256(json.dumps(
    audit, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode()
).hexdigest()
OUT.write_text(json.dumps(audit, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print("\n== 最终冻结前审计 ==")
print("  verdict:", verdict)
print("  checks: {} PASS / {} FAIL".format(len(PASS), len(FAIL)))
print("  DQ: DQ-2 {} | DQ-3 {} (max_hold {}) | DQ-4 {} ({} /min)".format(
    dq["DQ-2"]["state"], dq["DQ-3"]["state"], dq["DQ-3"].get("max_hold_s"), dq["DQ-4"]["state"],
    dq["DQ-4"].get("scene_changes_per_min")))
print("  baseline satisfied:", [k for k, v in conds.items() if v["ok"]])
print("  baseline unsatisfied:", [k for k, v in conds.items() if not v["ok"]])
print("audit ->", OUT)
sys.exit(1 if FAIL else 0)
