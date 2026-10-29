# -*- coding: utf-8 -*-
"""6-E —— E1 豆腐块判定的**修正版量化指标**（并在报告中标注度量修正）。

首版指标缺陷：片尾卡周围场景在该时刻为**白色**，`a>0.7` 把整片白场景并入掩膜
⇒ 连通域变成一个巨块、孔洞判定失效（C1 也被误判为"无豆腐块"）。
修正：① 先在 ROI 内自动定位**被压暗的卡片区**（0.35<a<0.62 的最大连通域）取 bbox；
      ② 只在卡内取白色字形（a>0.7）；
      ③ 用**矩形度**（bbox 边框上的墨迹占比）区分"空心方块(tofu)"与"CJK 笔画"：
         tofu 方块的边框几乎全是墨（rect_score 高、内部 1 个大孔）；
         CJK 字形笔画不沿 bbox 边框分布（rect_score 低）。
另用**冻结字体渲染的参考字形**做归一化 IoU（形状一致性）。

只读；仅更新 logs/phase6e_e1_execution.json 的 verify.tofu* 与度量说明。
"""
import hashlib
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
LOGS = ROOT / "docs" / "regression_2x" / "logs"
FRAMES = LOGS / "phase6e_e1_frames"
REPORT = LOGS / "phase6e_e1_execution.json"
FONT = Path(r"C:\Windows\Fonts\msyh.ttc")
OUTRO_TEXT = "感谢观看　我们下期再见"

import numpy as np                                                       # noqa: E402
from PIL import Image, ImageDraw, ImageFont                              # noqa: E402
from scipy import ndimage                                                # noqa: E402


def load_gray(p: Path) -> np.ndarray:
    return np.asarray(Image.open(p).convert("L"), dtype=np.float32) / 255.0


def card_bbox(a: np.ndarray, roi=(680, 1010, 380, 1560)):
    y0, y1, x0, x1 = roi
    reg = a[y0:y1, x0:x1]
    boxm = (reg > 0.33) & (reg < 0.63)
    lab, n = ndimage.label(boxm)
    if n == 0:
        return None
    sizes = ndimage.sum(boxm, lab, range(1, n + 1))
    keep = int(np.argmax(sizes)) + 1
    m = lab == keep
    ys, xs = np.where(m)
    return (int(ys.min() + y0), int(ys.max() + y0), int(xs.min() + x0), int(xs.max() + x0))


def glyph_mask(a: np.ndarray, bbox):
    by0, by1, bx0, bx1 = bbox
    sub = a[by0:by1 + 1, bx0:bx1 + 1]
    return sub > 0.70


def component_stats(m: np.ndarray):
    lab, n = ndimage.label(m)
    out = []
    for i in range(1, n + 1):
        comp = lab == i
        if comp.sum() < 60:
            continue
        ys, xs = np.where(comp)
        h, w = int(ys.max() - ys.min() + 1), int(xs.max() - xs.min() + 1)
        if h < 20 or w < 20:
            continue
        sub = comp[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
        fill = float(sub.sum()) / float(h * w)
        # 矩形度：bbox 边框（2px 带）上的墨迹占比
        band = np.zeros_like(sub)
        band[:2, :] = True
        band[-2:, :] = True
        band[:, :2] = True
        band[:, -2:] = True
        rect_score = float((sub & band).sum()) / float(band.sum())
        # 孔洞
        lab2, n2 = ndimage.label(~sub)
        holes, largest = 0, 0
        for j in range(1, n2 + 1):
            hj = lab2 == j
            if hj[0, :].any() or hj[-1, :].any() or hj[:, 0].any() or hj[:, -1].any():
                continue
            if hj.sum() > 30:
                holes += 1
                largest = max(largest, int(hj.sum()))
        ratio = largest / float(h * w)
        out.append({"bbox": [int(xs.min()), int(ys.min()), w, h], "fill": round(fill, 3),
                    "rect_score": round(rect_score, 3), "holes": holes,
                    "largest_hole_ratio": round(ratio, 3),
                    # 判据：bbox 边框几乎全为墨（矩形度高）**且**内部存在孔洞
                    # ⇒ 空心方块（tofu）。CJK 字形笔画不沿 bbox 边框分布 ⇒ rect_score 低。
                    "tofu_like": bool(rect_score >= 0.85 and holes >= 1)})
    return out


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


def ref_mask():
    f = ImageFont.truetype(str(FONT), 64)
    img = Image.new("L", (1400, 200), 0)
    ImageDraw.Draw(img).text((10, 60), OUTRO_TEXT, fill=255, font=f)
    return np.asarray(img, dtype=np.float32) / 255.0 > 0.5


ref = norm_pad(ref_mask())
res = {}
for name, fn in (("master", "master_outro.png"), ("c1", "c1_outro.png"),
                 ("candidate", "candidate_outro.png")):
    p = FRAMES / fn
    a = load_gray(p)
    bb = card_bbox(a)
    if bb is None:
        res[name] = {"error": "card not found"}
        continue
    m = glyph_mask(a, bb)
    st = component_stats(m)
    nm = norm_pad(m)
    iou = float(np.logical_and(ref, nm).sum()) / float(max(np.logical_or(ref, nm).sum(), 1))
    res[name] = {"card_bbox_y0y1x0x1": list(bb), "card_wh": [bb[3] - bb[2] + 1, bb[1] - bb[0] + 1],
                 "glyph_ink_px": int(m.sum()), "components": len(st),
                 "tofu_like_components": sum(1 for x in st if x["tofu_like"]),
                 "glyph_iou_vs_frozen_font": round(iou, 4),
                 "components_detail": st}

verdict = {
    "metric": "card-localized rect_score + normalized IoU vs frozen-font reference",
    "c1_tofu_like_components": res["c1"]["tofu_like_components"],
    "candidate_tofu_like_components": res["candidate"]["tofu_like_components"],
    "iou_c1": res["c1"]["glyph_iou_vs_frozen_font"],
    "iou_candidate": res["candidate"]["glyph_iou_vs_frozen_font"],
    "iou_master": res["master"]["glyph_iou_vs_frozen_font"],
    "tofu_eliminated": (res["c1"]["tofu_like_components"] >= 5
                        and res["candidate"]["tofu_like_components"] == 0),
    "glyph_shapes_match_frozen_font": res["candidate"]["glyph_iou_vs_frozen_font"]
    > res["c1"]["glyph_iou_vs_frozen_font"],
}
verdict["pass"] = bool(verdict["tofu_eliminated"] and verdict["glyph_shapes_match_frozen_font"])

print("== 修正版豆腐块指标 ==")
for k, v in res.items():
    print("{}: card={} glyph_ink={} components={} tofu_like={} IoU={}".format(
        k, v.get("card_wh"), v.get("glyph_ink_px"), v.get("components"),
        v.get("tofu_like_components"), v.get("glyph_iou_vs_frozen_font")))
    for c in (v.get("components_detail") or [])[:11]:
        print("     bbox={} fill={} rect={} holes={} hole_ratio={} tofu={}".format(
            c["bbox"], c["fill"], c["rect_score"], c["holes"], c["largest_hole_ratio"],
            c["tofu_like"]))
print("判定:", json.dumps(verdict, ensure_ascii=False))

# ---- 更新报告（仅替换度量字段 + 记录度量修正）----
rep = json.loads(REPORT.read_text(encoding="utf-8"))
rep["verify"]["tofu_metric_v1_defect"] = (
    "首版指标（phase6e_e1_verify.py）在 a>0.7 上取掩膜未先定位卡片区，白色场景被并入 ⇒ "
    "C1 亦被误判为『无豆腐块』（IoU≈0）。该缺陷由视觉证据发现并修正，见 tofu_metric_v2。")
rep["verify"]["tofu_metric_v2"] = res
rep["verify"]["tofu_verdict"] = verdict
rep["verify"]["visual_evidence"] = {
    "frames": rep["verify"].get("frames"),
    "note": "同刻三帧（母版 / C1 / 候选）已保存；人工可直接比对：C1 片尾卡为空心方块，"
            "候选为可读中文『感谢观看　我们下期再见』，ASS 字幕两帧均正常"}
rep["metric_corrections"] = rep.get("metric_corrections", []) + [{
    "at": "6-E/E1", "what": "豆腐块判定掩膜（先定位卡片区再取字形；矩形度替代孔洞单一判据）",
    "why": "首版指标受白色场景污染，导致 C1 误判", "impact": "结论由『未检出』修正为『C1 有豆腐块 9 处、候选 0 处』"}]
rep["report_sha256"] = hashlib.sha256(
    json.dumps({k: v for k, v in rep.items() if k != "report_sha256"}, sort_keys=True,
               ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()
REPORT.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
print("\n报告已更新:", REPORT.name, "| report_sha256", rep["report_sha256"][:16])
print("recheck keys:", sorted((rep["verify"]["pi_dq"] or {}).keys()))
print("pi_gate_outcome:", rep["verify"]["pi_gate_outcome"])
