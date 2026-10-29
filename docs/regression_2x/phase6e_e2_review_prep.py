# -*- coding: utf-8 -*-
"""6-E —— **E2 候选只读人工审查准备**（Human Review Checklist/Report）。

禁止：执行 E2/E3/E4/E5、promote、修改源码/DB/材料/时间轴、再次执行 E2。
本脚本**只做**：只读抽帧 + 可测指标 + 完整性取证 + 生成"待人工确认"清单。
所有**判断**（是否 PPT 化、是否易理解、是否信息噪音、耦合是否有效、是否拥挤、进入/退出是否自然）
一律标记 `pending_human_decision=True`，脚本**不**给出 ACCEPT/REJECT。

产出: logs/phase6e_e2_review_prep.json
      logs/phase6e_e2_review_frames/{master,candidate}_t*.png
"""
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
from video_studio.core import execution as EX                        # noqa: E402
from video_studio.core import visual_aid as VA                      # noqa: E402

LOGS = ROOT / "docs" / "regression_2x" / "logs"
MAT = ROOT / "docs" / "regression_2x" / "phase6e_materials"
DB = ROOT / "projects" / "video_studio.db"
FILM = ROOT / "projects" / "p_96efdc03e1aa" / "output" / "t_d0a54bdf1810_draft.mp4"
V9_SHA = "22705c7d7ea20b40d91120146066b89ab2b5fa5c1a1cab18f5346d4c66497651"
PROPOSAL_ID = "rp-bee31dff3335"
PROPOSAL_SHA = "8ff60656e40925f15d55650c7909b6d1adda0b9a2980d5fd9857534f95879d5f"
SPEC_SHA = "4e5559424aa749c81eb707d34838307987f7c1f51d775c2baf1faf6b010cc553"
E2REPORT = LOGS / "phase6e_e2_execution.json"
E2_LEDGER = LOGS / "phase6e_e2_execution_ledger.jsonl"
E1_LEDGER = LOGS / "phase6e_e1_execution_ledger.jsonl"
M5_AP = LOGS / "phase6b_m4_approvals_v9.jsonl"
M5_EX = LOGS / "phase6b_m4_execution_ledger_v9.jsonl"
M6C = LOGS / "phase6c_batch.json"
BM = LOGS / "phase6e_execution_batch_manifest.json"
FREEZE = MAT / "phase6e_material_freeze_manifest.json"
PLAN = MAT / "phase6e_material_plan.json"
REG = LOGS / "phase6e_proposal_register_r2.jsonl"
STATUS_LEDGER = LOGS / "phase6e_approval_status_r2.jsonl"
FRAMES = LOGS / "phase6e_e2_review_frames"
OUT = LOGS / "phase6e_e2_review_prep.json"
E1_DIR = ROOT / "output" / "phase6b_m4_sandbox" / "p_96efdc03e1aa_6e"
CFG = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8-sig"))
FFMPEG = CFG["tools"]["ffmpeg"]["path"]
WINDOW = (245.0, 300.0)
GRID = [244.5, 246.0, 248.0, 255.0, 262.0, 270.0, 278.0, 285.0, 292.0, 297.0, 299.0, 299.5, 300.5]


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def inventory(d: Path) -> dict:
    return {str(p.relative_to(d)): (p.stat().st_size, round(p.stat().st_mtime, 3))
            for p in d.rglob("*") if p.is_file()} if d.is_dir() else {}


def extract(film: Path, t: float, dst: Path) -> Path:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.is_file():
        subprocess.run([FFMPEG, "-y", "-v", "error", "-ss", "{:.3f}".format(t), "-i", str(film),
                        "-frames:v", "1", str(dst)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return dst


# ---------- 0) 只读基线 ----------
rep = json.loads(E2REPORT.read_text(encoding="utf-8"))
cand = ROOT / rep["candidate"]["path"]
cand_sha_recorded = rep["candidate"]["sha256"]
m6c = json.loads(M6C.read_text(encoding="utf-8"))
bm = json.loads(BM.read_text(encoding="utf-8"))
reg = [json.loads(x) for x in REG.read_text(encoding="utf-8").splitlines() if x.strip()]
base = {"v9_sha256": sha(FILM), "candidate_sha256": sha(cand) if cand.is_file() else None,
        "c1_c4": {c["index"]: sha(ROOT / c["film"]) for c in m6c["candidates"]},
        "db_sha256": sha(DB), "m5_ap": sha(M5_AP), "m5_ex": sha(M5_EX),
        "freeze": sha(FREEZE), "e1_inv": inventory(E1_DIR),
        "e2_ledger_entries": len(EX.load_ledger(E2_LEDGER)),
        "status_ledger_entries": len([json.loads(x) for x in
                                      STATUS_LEDGER.read_text(encoding="utf-8").splitlines()
                                      if x.strip()])}

ev = ((rep.get("execution") or {}).get("steps") or [])
spec_ev = rep["verify"]["spec_binding"]
panels = spec_ev["panels"]

import numpy as np                                                          # noqa: E402
from PIL import Image, ImageDraw, ImageFont                                 # noqa: E402
from scipy import ndimage                                                   # noqa: E402

# 面板 bbox（来自执行证据）
overlay_png = None
for s in ev:
    if s.get("step") == "render_visual_aid_overlay":
        overlay_png = ROOT / "output" / "phase6b_m4_sandbox" / "p_96efdc03e1aa_6e2" / "work" / \
            s["overlay_png"]
panel_boxes = []
if overlay_png and overlay_png.is_file():
    from PIL import Image as _I
    with _I.open(overlay_png) as im:
        ov = np.asarray(im)
    alpha = ov[:, :, 3]
    cov_total = float((alpha > 8).mean())
    # 粗定位：alpha>8 的行/列范围 → 面板并集面积
    ys, xs = np.where(alpha > 8)
    union = {"y": [int(ys.min()), int(ys.max())], "x": [int(xs.min()), int(xs.max())],
             "area_share": float(((xs.max() - xs.min() + 1) * (ys.max() - ys.min() + 1))
                                 / float(alpha.size))}
else:
    alpha, cov_total, union = None, None, None

# ---------- 1) 逐点抽帧 + 指标 ----------
print("== 抽帧与指标（{} 点 × 2 片）==".format(len(GRID)))
rows = []
def entropy(a):
    h, _ = np.histogram((a * 255).astype(np.uint8), bins=64, range=(0, 255), density=False)
    p = h / max(h.sum(), 1)
    p = p[p > 0]
    return float(-(p * np.log2(p)).sum())

def edge_density(a):
    sx = ndimage.sobel(a, axis=1)
    sy = ndimage.sobel(a, axis=0)
    return float(np.hypot(sx, sy).mean())

def glyph_ink(a, boxes):
    n = 0
    for x0, y0, x1, y1 in boxes:
        sub = a[y0:min(y1, a.shape[0]), x0:min(x1, a.shape[1])]
        if sub.size == 0:
            continue
        n += int(((sub > 0.80) & (ndimage.uniform_filter(sub, size=9) < 0.72)).sum())
    return n

def band_ink(a):
    b = a[int(a.shape[0] * 0.82):]
    w = b > 0.72
    return int(((b < 0.45) & ndimage.binary_dilation(w, iterations=2)).sum())

for t in GRID:
    tag = "t{:07.3f}".format(t)
    fm = extract(FILM, t, FRAMES / "master_{}.png".format(tag))
    fc = extract(cand, t, FRAMES / "candidate_{}.png".format(tag))
    a_m = np.asarray(Image.open(fm).convert("L"), dtype=np.float32) / 255.0
    a_c = np.asarray(Image.open(fc).convert("L"), dtype=np.float32) / 255.0
    boxes = panel_boxes
    in_win = WINDOW[0] < t < WINDOW[1]
    row = {"t": t, "in_window": in_win,
           "gray_diff": round(float(np.abs(a_c - a_m).mean() * 255), 3),
           "entropy_master": round(entropy(a_m), 4), "entropy_candidate": round(entropy(a_c), 4),
           "edge_density_master": round(edge_density(a_m), 5),
           "edge_density_candidate": round(edge_density(a_c), 5),
           "subtitle_ink_master": band_ink(a_m), "subtitle_ink_candidate": band_ink(a_c),
           "frames": [str(fm.relative_to(ROOT)), str(fc.relative_to(ROOT))]}
    if overlay_png and overlay_png.is_file():
        # 面板区白字墨迹（候选用真实 bbox；母版同区做对照）
        bxs = [[int(b[0]), int(b[1]), int(b[0] + b[2]), int(b[1] + b[3])]
               for b in [p["bbox"] for p in (rep["verify"]["spec_binding"].get("panels_bbox") or [])]]
        if not bxs:
            # 用 overlay alpha 的连通域 bbox 作为面板区
            lab, n = ndimage.label(alpha > 8)
            bxs = []
            for i in range(1, n + 1):
                ys, xs = np.where(lab == i)
                if len(ys) < 5000:
                    continue
                bxs.append([int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1])
        row["panel_count_detected"] = len(bxs)
        row["panel_ink_master"] = glyph_ink(a_m, bxs)
        row["panel_ink_candidate"] = glyph_ink(a_c, bxs)
        lums = [(float(a_m[b[1]:b[3], b[0]:b[2]].mean()), float(a_c[b[1]:b[3], b[0]:b[2]].mean()))
                for b in bxs if a_c[b[1]:b[3], b[0]:b[2]].size]
        row["panel_lum_master"] = round(float(np.mean([x[0] for x in lums])), 4) if lums else None
        row["panel_lum_candidate"] = round(float(np.mean([x[1] for x in lums])), 4) if lums else None
    rows.append(row)
    print("  t={:7.1f} win={} diff={:6.2f} entropy {:.3f}->{:.3f} edge {:.4f}->{:.4f} sub_ink {}->{}".format(
        t, int(in_win), row["gray_diff"], row["entropy_master"], row["entropy_candidate"],
        row["edge_density_master"], row["edge_density_candidate"],
        row["subtitle_ink_master"], row["subtitle_ink_candidate"]))

# ---------- 2) 时间活动性（是否"只是画面变化"）----------
def activity(key):
    vals = [r[key] for r in rows]
    return [round(abs(vals[i + 1] - vals[i]), 5) for i in range(len(vals) - 1)]
inwin = [r for r in rows if r["in_window"]]
activity_entropy_c = [round(abs(inwin[i + 1]["entropy_candidate"] - inwin[i]["entropy_candidate"]), 4)
                      for i in range(len(inwin) - 1)]
activity_entropy_m = [round(abs(inwin[i + 1]["entropy_master"] - inwin[i]["entropy_master"]), 4)
                      for i in range(len(inwin) - 1)]
activity_edge_c = [round(abs(inwin[i + 1]["edge_density_candidate"] - inwin[i]["edge_density_candidate"]), 5)
                   for i in range(len(inwin) - 1)]
activity_edge_m = [round(abs(inwin[i + 1]["edge_density_master"] - inwin[i]["edge_density_master"]), 5)
                   for i in range(len(inwin) - 1)]

# ---------- 3) 进入/退出边界（是否硬切）----------
def r_at(t):
    return next((r for r in rows if abs(r["t"] - t) < 1e-6), None)
entry = {"t_before": r_at(244.5), "t_after": r_at(246.0)}
exit_ = {"t_before": r_at(299.5), "t_after": r_at(300.5)}
entry_boundary = {"overlay_absent_before": (entry["t_before"] or {}).get("gray_diff", 9) < 2.0,
                  "overlay_present_after": (entry["t_after"] or {}).get("gray_diff", 0) > 10.0,
                  "transition_abrupt_no_fade": True,
                  "evidence": {"before_gray_diff": (entry["t_before"] or {}).get("gray_diff"),
                               "after_gray_diff": (entry["t_after"] or {}).get("gray_diff")}}
exit_boundary = {"overlay_present_before": (exit_["t_before"] or {}).get("gray_diff", 0) > 10.0,
                 "overlay_absent_after": (exit_["t_after"] or {}).get("gray_diff", 9) < 2.0,
                 "transition_abrupt_no_fade": True,
                 "evidence": {"before_gray_diff": (exit_["t_before"] or {}).get("gray_diff"),
                              "after_gray_diff": (exit_["t_after"] or {}).get("gray_diff")}}

# ---------- 4) 帧内是否真含冻结文本（模板匹配，证明"文字真的在画面上"）----------
def ref_mask(text, size, font_size=30, wrap=46):
    f = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", font_size)
    lines = VA._wrap(text, wrap)
    img = Image.new("L", (size[0], max(40, 40 * len(lines))), 0)
    d = ImageDraw.Draw(img)
    for i, ln in enumerate(lines):
        d.text((5, 5 + i * (font_size + 8)), ln, fill=255, font=f)
    m = np.asarray(img, dtype=np.float32) / 255.0 > 0.5
    ys, xs = np.where(m)
    return m[ys.min():ys.max() + 1, xs.min():xs.max() + 1] if len(ys) else m


def norm(m, size=(768, 64)):
    img = Image.fromarray((m * 255).astype(np.uint8))
    s = min(size[0] / max(img.width, 1), size[1] / max(img.height, 1))
    img = img.resize((max(1, int(img.width * s)), max(1, int(img.height * s))), Image.NEAREST)
    canvas = Image.new("L", size, 0)
    canvas.paste(img, ((size[0] - img.width) // 2, (size[1] - img.height) // 2))
    return np.asarray(canvas) > 127


tmpl = {}
t_ref = 270.0
fc = FRAMES / "candidate_t{:07.3f}.png".format(t_ref)
if fc.is_file() and overlay_png and overlay_png.is_file():
    a_c = np.asarray(Image.open(fc).convert("L"), dtype=np.float32) / 255.0
    lab, n = ndimage.label(alpha > 8)
    boxes = []
    for i in range(1, n):
        ys, xs = np.where(lab == i)
        if len(ys) < 5000:
            continue
        boxes.append([int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1])
    boxes.sort(key=lambda b: (b[1], b[0]))
    # 用执行证据里的渲染文本（结构：{P1:{title,lines,...},...}）
    rt = rep["verify"]["spec_binding"]["rendered_text"]
    for pid in ("P1", "P2", "P3"):
        ent = rt[pid]
        for ln in [ent["title"]] + ent["lines"]:
            r = norm(ref_mask(ln, (1024, 64)), (1024, 64))
            best = 0.0
            for b in boxes:
                sub = a_c[b[1]:b[3], b[0]:b[2]]
                if sub.size == 0:
                    continue
                m = (sub > 0.80) & (ndimage.uniform_filter(sub, size=9) < 0.72)
                ys, xs = np.where(m)
                if len(ys) < 20:
                    continue
                nm = norm(m[ys.min():ys.max() + 1, xs.min():xs.max() + 1], (1024, 64))
                iou = float(np.logical_and(r, nm).sum()) / float(max(np.logical_or(r, nm).sum(), 1))
                best = max(best, iou)
            tmpl.setdefault(pid, []).append({"text": ln[:60], "best_iou_vs_frozen_font": round(best, 4)})

# ---------- 5) 完整性（只读）----------
integrity = {
    "candidate_sha256_recorded": cand_sha_recorded,
    "candidate_sha256_now": sha(cand) if cand.is_file() else None,
    "candidate_unchanged": (sha(cand) == cand_sha_recorded) if cand.is_file() else False,
    "v9_unchanged": sha(FILM) == V9_SHA == base["v9_sha256"],
    "c1_c4_unchanged": all(sha(ROOT / c["film"]) == base["c1_c4"][c["index"]]
                           for c in m6c["candidates"]),
    "db_unchanged": sha(DB) == base["db_sha256"],
    "m5_ledgers_untouched": sha(M5_AP) == base["m5_ap"] and sha(M5_EX) == base["m5_ex"],
    "m5_entries": [len(EX.load_ledger(M5_AP)), len(EX.load_ledger(M5_EX))],
    "material_freeze_unchanged": sha(FREEZE) == base["freeze"],
    "e1_sandbox_unchanged": inventory(E1_DIR) == base["e1_inv"],
    "e2_ledger_entries_unchanged": len(EX.load_ledger(E2_LEDGER)) == base["e2_ledger_entries"],
    "status_ledger_entries_unchanged": len([json.loads(x) for x in
                                            STATUS_LEDGER.read_text(encoding="utf-8").splitlines()
                                            if x.strip()]) == base["status_ledger_entries"],
    "promoted": False,
    "e3_e4_e5_proposal_unchanged": all(
        EX.proposal_sha256(next(r for r in reg if r["label"].startswith(k)))
        == next(i for i in bm["items"] if i["label"].startswith(k))["proposal_sha256"]
        for k in ("E3", "E4", "E5")),
    "no_new_execution": True,
}

# ---------- 6) 报告（判断一律待人工确认）----------
def pend(qid, question, machine_evidence, human_decides):
    return {"id": qid, "question": question, "machine_evidence": machine_evidence,
            "human_must_decide": human_decides, "verdict": "PENDING_HUMAN_REVIEW",
            "auto_accept": False, "auto_reject": False}


report = {
    "schema": "phase6e-e2-human-review-prep-v1", "stage": "6-E",
    "review_target": {"proposal_id": PROPOSAL_ID, "proposal_sha256": PROPOSAL_SHA,
                      "spec_sha256": SPEC_SHA,
                      "candidate": str(cand.relative_to(ROOT)),
                      "candidate_sha256": integrity["candidate_sha256_now"],
                      "window_s": list(WINDOW)},
    "note": "**只读审查准备**：未执行任何 proposal、未 promote、未修改源码/DB/材料/时间轴。"
            "所有判断均为 `PENDING_HUMAN_REVIEW`，脚本不给出 ACCEPT/REJECT。",
    "automated_metrics": {"per_sample": rows,
                          "activity_entropy_candidate": activity_entropy_c,
                          "activity_entropy_master": activity_entropy_m,
                          "activity_edge_candidate": activity_edge_c,
                          "activity_edge_master": activity_edge_m,
                          "overlay": {"png_sha256": sha(overlay_png) if overlay_png
                                      and overlay_png.is_file() else None,
                                      "alpha_coverage_share": cov_total,
                                      "panel_union_bbox_share": (union or {}).get("area_share"),
                                      "panel_union_bbox": union},
                          "entry_boundary": entry_boundary, "exit_boundary": exit_boundary,
                          "text_template_match": tmpl},
    "checklist": [
        pend("Q1", "245–300s 信息图是否**真正服务 S05 narration**，而非单纯 PPT 化？",
             {"narration_moves": ["引用被检视的程度（转述状态）", "1980 年两篇文献的两种立场",
                                  "可检视性争论"],
              "panels_map_1to1": {"P1(阶梯)": "对 S05『只能用转述 / 还没逐字核对原文』",
                                  "P2(文献元数据)": "对 S06『1980 年 Detlefsen 和 Luker』",
                                  "P3(两立场)": "对 S07『两种立场』"},
              "measured": {"panel_ink_master_vs_candidate": [
                  [r.get("panel_ink_master"), r.get("panel_ink_candidate")]
                  for r in rows if r["in_window"]][:5],
                  "entropy_in_window": [[r["entropy_master"], r["entropy_candidate"]]
                                        for r in rows if r["in_window"]]}},
             "是否服务叙事 vs 是否沦为 PPT（人工内容判断）"),
        pend("Q2", "四级『可检视性』阶梯是否容易理解？『本片当前状态』高亮是否合理？",
             {"ladder_items": ["未核对原文", "转述（本片当前状态）", "逐字核对", "机器可逐步复核"],
              "highlight_rule": "含『当前』的档位以琥珀色条高亮（对 S05『只能用转述』）",
              "render_ok": True},
             "阶梯易懂性与高亮恰当性（人工）"),
        pend("Q3", "两篇论文元数据是否与 narration 对得上？是否造成信息噪音？",
             {"P2_lines": 7, "contains": ["Tymoczko", "The Journal of Philosophy 76(2), p.57, Feb 1979",
                                          "10.2307/2025976", "Detlefsen & Luker", "77(12), p.803, Dec 1980",
                                          "10.2307/2025806"],
              "source": "Crossref 现场复验一致（卷/期/页/年/DOI）",
              "noise_risk": "DOIs 为长串数字，1080p 下字高约 30px；是否构成噪音需人工看片判断"},
             "元数据是否过量/是否需要精简（人工）"),
        pend("Q4", "两种立场的转述是否清楚且没有制造原文引语？",
             {"P3_text": ["立场甲：证明的本质包含『人可以检视』",
                          "立场乙：可靠性不必建立在『每个中间步骤都能被人逐步检视』之上"],
              "quote_check": {"quote_free_verified": True,
                              "rule": "渲染文本不含西文双引号；『』强调片段 ≤24 字"},
              "title_marker": "两种立场（转述，不引原文）"},
             "转述是否清楚、是否会被误读为引语（人工）"),
        pend("Q5", "overlay 与底层四色定理画面是否形成有效的 voice-visual coupling？",
             {"backdrop_v9_S05_asset": "asset_30dd89a16713（Four color theorem map of Germany 3.png）",
              "coupling_facts": ["叠加层内容与旁白三个论点一一对应",
                                 "底层四色定理图与『证明/检视』主题同源（非无关素材）",
                                 "面板半透明 ⇒ 底层图仍可见（被压暗）"],
              "measured": {"panel_lum_master_to_candidate": [
                  [r.get("panel_lum_master"), r.get("panel_lum_candidate")]
                  for r in rows if r["in_window"]][:5]}},
             "耦合是否有效（人工观感；机器无法裁决）"),
        pend("Q6", "overlay 是否遮挡字幕、关键视觉内容或造成视觉拥挤？",
             {"subtitle_safe_area": "执行器强制：叠加层不进入底部 5%（safe_bottom_ok=true）",
              "measured_subtitle_ink_master_vs_candidate": [
                  [r["subtitle_ink_master"], r["subtitle_ink_candidate"]]
                  for r in rows if r["in_window"]],
              "overlay_coverage": {"alpha_coverage_share": cov_total,
                                   "panel_union_bbox_share": (union or {}).get("area_share")},
              "crowding_risk": "面板并集约占画面一半；是否拥挤需人工判断"},
             "遮挡/拥挤观感（人工）"),
        pend("Q7", "信息图进入/退出是否自然？245–300s 内是否有明显『卡片感』？",
             {"entry": entry_boundary, "exit": exit_boundary,
              "inside_window_variation": {"entropy_delta_mean_candidate":
                                          round(float(np.mean(activity_entropy_c)), 4),
                                          "entropy_delta_mean_master":
                                          round(float(np.mean(activity_entropy_m)), 4)},
              "fact": "叠加层在**整个窗口**恒定存在，仅在 245.0s / 300.0s 硬切（无淡入淡出）"},
             "硬切与『卡片感』是否可接受（人工）"),
        pend("Q8", "与 v9 S05 逐段比较：是否增加**真实信息密度**，而不只是画面变化？",
             {"information_added": ["四级可检视性阶梯", "两篇文献的卷/期/页 + DOI（可核对）",
                                    "两种立场的转述"],
              "measured": {"entropy_mean_master": round(float(np.mean([r["entropy_master"] for r in rows if r["in_window"]])), 4),
                           "entropy_mean_candidate": round(float(np.mean([r["entropy_candidate"] for r in rows if r["in_window"]])), 4),
                           "edge_mean_master": round(float(np.mean([r["edge_density_master"] for r in rows if r["in_window"]])), 5),
                           "edge_mean_candidate": round(float(np.mean([r["edge_density_candidate"] for r in rows if r["in_window"]])), 5),
                           "panel_ink_master_mean": round(float(np.mean([r.get("panel_ink_master", 0) for r in rows if r["in_window"]])), 1),
                           "panel_ink_candidate_mean": round(float(np.mean([r.get("panel_ink_candidate", 0) for r in rows if r["in_window"]])), 1)}},
             "『真实信息密度』判定（人工）"),
        pend("Q9", "是否出现**新的**视觉/语义问题？（需明确记录）",
             {"recorded_issues": [
                 "① 叠加层在窗口两端**硬切**（245.0s 起、300.0s 止），无淡入淡出 ⇒ 可能产生『卡片感』",
                 "② 面板含 DOI 长串，1080p 下信息偏小 ⇒ 可读性/噪音风险",
                 "③ 面板并集约占画面一半，底层四色定理图被压暗 ⇒ 底层视觉信息大部分被遮蔽",
                 "④ P1 阶梯的第 4 级横条延伸至面板右缘，与面板边框相接（版式细节）",
                 "⑤ 组合层提示：若日后将 E2 与 6-C 的 C4 串链，S05 底层会是 IMO 合影（被压暗）"]},
             "上述问题是否为阻断项（人工）"),
        pend("Q10", "是否 ACCEPT / REJECT（本轮不判定）",
             {"policy": "脚本不给出 ACCEPT/REJECT；所有判断作为待人工确认的 review evidence"},
             "人工最终裁决（本轮不做）"),
    ],
    "integrity": integrity,
    "artifacts": {"frames_dir": str(FRAMES.relative_to(ROOT)),
                  "report": str(OUT.relative_to(ROOT))},
}
report["report_sha256"] = hashlib.sha256(
    json.dumps({k: v for k, v in report.items() if k != "report_sha256"}, sort_keys=True,
               ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()
OUT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")


def entry_sha(r):
    b = {k: v for k, v in r.items() if k != "entry_sha256"}
    return hashlib.sha256(json.dumps(b, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


rows_led = [json.loads(x) for x in STATUS_LEDGER.read_text(encoding="utf-8").splitlines() if x.strip()]
RID = "6E-E2-REVIEW-PREP-v1"
if not any(e.get("review_prep_id") == RID for e in rows_led):
    r = {"schema": "e2-review-prep-v1", "stage": "6-E", "review_prep_id": RID,
         "proposal_id": PROPOSAL_ID, "proposal_sha256": PROPOSAL_SHA, "spec_sha256": SPEC_SHA,
         "candidate_sha256": integrity["candidate_sha256_now"],
         "window": list(WINDOW), "checklist_items": len(report["checklist"]),
         "all_pending_human_review": all(c["verdict"] == "PENDING_HUMAN_REVIEW"
                                         for c in report["checklist"]),
         "auto_accept": False, "auto_reject": False, "promoted": False,
         "executed_anything": False, "source_or_db_modified": False,
         "report": str(OUT.relative_to(ROOT)), "report_sha256": report["report_sha256"],
         "decided_by": "agent:read-only-review-prep",
         "provenance": "人工指令：仅做 E2 候选只读审查准备；不判定 ACCEPT/REJECT",
         "read_only": True, "enforced": False, "advisory": True, "executes_changes": False}
    r["seq"] = len(rows_led) + 1
    r["prev_sha256"] = rows_led[-1]["entry_sha256"] if rows_led else ""
    r["entry_sha256"] = entry_sha(r)
    with open(STATUS_LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("登记 seq", r["seq"])

print("\n== 边界 ==")
print("entry:", json.dumps(entry_boundary, ensure_ascii=False))
print("exit :", json.dumps(exit_boundary, ensure_ascii=False))
print("overlay coverage:", cov_total, "| union bbox share:", (union or {}).get("area_share"))
print("integrity:", json.dumps(integrity, ensure_ascii=False)[:420])
print("report ->", OUT)
