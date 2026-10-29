"""Phase 17 / P17-1：渲染后核验度量 —— **归因诊断纯函数模块**（确定性、零 LLM、零网络）。

背景：冻结的渲染后核验度量 `corr_48 = frame_corr(gray48(asset), gray48(frame))`（阈值 0.30）
已积累三类误报证据。本模块对**单景**做多假设归因，输出结论：

  · `crop_artifact`      —— 素材被 1920×1080 模板中心裁切后与全图差异过大（多面板/非 16:9 构图）
  · `density_artifact`   —— 提高重采样分辨率后 corr 显著回升（稀疏图在 48×48 下塌陷）
  · `motion_artifact`    —— 运动层裁切窗口与展示窗口不一致（运动启用的场景）
  · `subtitle_artifact`  —— 剔除字幕带后 corr 显著回升
  · `possible_real_mismatch` —— 以上假设均不成立（应如实报错配）

设计纪律（沿用 Phase 11 先例：修误报、不松真门）：
  · 本模块**只诊断、不改度量、不改阈值、不做渲染**；
  · 全部证据为可复算数值（无时间戳/随机量 ⇒ artifact 可确定性复现）；
  · `possible_real_mismatch` **不得**被下游裁定为"在屏"。
"""
from __future__ import annotations

import math
import pathlib
from pathlib import Path

#: 诊断用多分辨率（P17-1b 密度假设）
RES_LADDER = (48, 96, 192, 384)

#: 诊断用裁切尺度（相对画面宽高，P17-1a 裁切假设）
CROP_SCALES = (1.00, 0.90, 0.80, 0.70, 0.60, 0.50)

#: 诊断用中心偏移（相对画面宽高，±）
CROP_OFFSETS = (0.00, 0.05, 0.10, 0.20)

#: 冻结阈值（**不修改**；仅供判定口径引用）
FROZEN_MIN_CORR = 0.30

#: 判定显著性阈值（诊断用；与门禁阈值无关）
SIG_GAIN = 0.10            # corr 提升 ≥ 0.10 视为"显著回升"
SIG_ABS = 0.30             # 或绝对达到冻结阈值

# ---------------------------------------------------------------- bank 子窗口库
#: v1（**冻结、默认**）：探针 48、尺度 5 档、5×5 网格。**不得修改**（历史可比性）。
BANK_VERSION_V1 = "bank-derived-v1"
BANK_SCALES = (1.0, 0.8, 0.6, 0.45, 0.35)
BANK_GRID = 5

#: v2：探针分辨率 48 → **192**、网格**按 192 尺度重排**（步进 ≤170px）。
#: 依据（KNOWN_ISSUES #80 §80.11）：v1 在 1404×696（2.02:1）素材上，16:9 子窗口被真实宽高比限制
#: 到 ≤0.8 宽，且 x 步距 ≈281px ⇒ 取不到真实呈现窗口（≈72% 宽、x0≈246）。
BANK_VERSION_V2 = "bank-derived-v2"
BANK_RES_V2 = 192
BANK_SCALES_V2 = (1.0, 0.9, 0.8, 0.72, 0.65, 0.6, 0.5, 0.45, 0.35)
BANK_GRID_V2 = 11
BANK_STEP_PX_V2 = 170      # 运行前写死的步进上限（x 与 y 各自满足）

#: 外部配置文件（**不改被基线钉定的 config.json**；沿用 render_motion.json 同款三级链）
EXTERNAL_CONFIG_REL = "config/frame_match.json"


def _gray(path, size: int):
    """读图为 size×size 灰度 ndarray（复用 PIL，确定性 LANCZOS 由 PIL 默认决定）。"""
    import numpy as np
    from PIL import Image
    with Image.open(path) as im:
        return np.asarray(im.convert("L").resize((size, size)), dtype=np.float64)


def _corr(a, b) -> float:
    import numpy as np
    a = a - a.mean()
    b = b - b.mean()
    d = float(np.sqrt((a ** 2).sum()) * np.sqrt((b ** 2).sum()))
    return float((a * b).sum() / d) if d else 0.0


def center_crop_array(img, w: int, h: int, scale: float = 1.0,
                      dx: float = 0.0, dy: float = 0.0):
    """按生产口径取中心裁切：`scale` 为保留比例，(dx,dy) 为相对宽高的中心偏移。

    返回裁切后的 ndarray（未缩放）。偏移会被夹取到合法范围。
    """
    import numpy as np
    H, W = img.shape[:2]
    cw = max(2, int(round(W * scale)))
    ch = max(2, int(round(H * scale)))
    cx = W / 2.0 + dx * W
    cy = H / 2.0 + dy * H
    x0 = int(round(min(max(cx - cw / 2.0, 0), W - cw)))
    y0 = int(round(min(max(cy - ch / 2.0, 0), H - ch)))
    return img[y0:y0 + ch, x0:x0 + cw]


def _to_gray_size(arr, size: int):
    import numpy as np
    from PIL import Image
    im = Image.fromarray(arr.astype("uint8"))
    return np.asarray(im.convert("L").resize((size, size)), dtype=np.float64)


def crop_hypothesis(frame_gray48, asset_path, res: int = 48) -> dict:
    """P17-1a：corr(成片帧, 素材多尺度/多偏移中心裁切) 的最大值。"""
    from PIL import Image
    import numpy as np
    with Image.open(asset_path) as im:
        full = np.asarray(im.convert("L"), dtype=np.float64)
    best = {"corr": -2.0, "scale": None, "dx": None, "dy": None}
    rows = []
    for sc in CROP_SCALES:
        for dx in (0.0, -0.10, 0.10) if sc >= 0.9 else CROP_OFFSETS:
            for dy in (0.0, -0.10, 0.10) if sc >= 0.9 else CROP_OFFSETS:
                crop = center_crop_array(full, 0, 0, scale=sc, dx=dx, dy=dy)
                g = _to_gray_size(crop, res)
                c = round(_corr(frame_gray48, g), 4)
                rows.append({"scale": sc, "dx": dx, "dy": dy, "corr": c})
                if c > best["corr"]:
                    best = {"corr": c, "scale": sc, "dx": dx, "dy": dy}
    return {"best": best, "rows": rows,
            "at_1.0_center": next((r["corr"] for r in rows
                                   if r["scale"] == 1.0 and r["dx"] == 0.0
                                   and r["dy"] == 0.0), None)}


def density_hypothesis(frame_path, asset_path, ladder=RES_LADDER) -> dict:
    """P17-1b：corr 随重采样分辨率的塌陷曲线（同口径逐级提高分辨率）。"""
    curve = []
    for r in ladder:
        fg = _gray(frame_path, r)
        ag = _gray(asset_path, r)
        curve.append({"res": r, "corr": round(_corr(fg, ag), 4)})
    base = curve[0]["corr"]
    mx = max(c["corr"] for c in curve)
    return {"curve": curve, "corr_48": base, "corr_max": mx,
            "gain": round(mx - base, 4),
            "crosses_at": next((c["res"] for c in curve
                                if c["corr"] >= FROZEN_MIN_CORR), None)}


def subtitle_hypothesis(frame_path, asset_path, bottom_ratio: float = 0.16,
                        res: int = 48) -> dict:
    """P17-1d：剔除底部字幕带后重算 corr。"""
    import numpy as np
    from PIL import Image
    with Image.open(frame_path) as im:
        f = np.asarray(im.convert("L"), dtype=np.float64)
    H = f.shape[0]
    keep = f[:max(2, int(H * (1.0 - bottom_ratio))), :]
    fg = _to_gray_size(keep, res)
    ag = _gray(asset_path, res)
    c_masked = round(_corr(fg, ag), 4)
    c_full = round(_corr(_gray(frame_path, res), ag), 4)
    return {"corr_full": c_full, "corr_masked": c_masked,
            "gain": round(c_masked - c_full, 4), "bottom_ratio": bottom_ratio}


def region_hypothesis(frame_path, asset_path, grid: int = 5, res: int = 48) -> dict:
    """P17-1e：素材内滑动窗口最佳相关（画面到底对上了素材哪一块）。"""
    import numpy as np
    from PIL import Image
    with Image.open(asset_path) as im:
        full = np.asarray(im.convert("L"), dtype=np.float64)
    H, W = full.shape[:2]
    fg = _gray(frame_path, res)
    # 窗口宽高比 = 画面宽高比（成片为 16:9；此处用 16/9 近似）
    win_h = max(2, int(H / 3))
    win_w = max(2, min(W, int(round(win_h * 16.0 / 9.0))))
    best = {"corr": -2.0, "x0": None, "y0": None, "w": win_w, "h": win_h}
    rows = []
    for gy in range(grid):
        for gx in range(grid):
            x0 = int(round(gx * (W - win_w) / max(grid - 1, 1))) if grid > 1 else 0
            y0 = int(round(gy * (H - win_h) / max(grid - 1, 1))) if grid > 1 else 0
            win = full[y0:y0 + win_h, x0:x0 + win_w]
            c = round(_corr(fg, _to_gray_size(win, res)), 4)
            rows.append({"x0": x0, "y0": y0, "corr": c})
            if c > best["corr"]:
                best = {"corr": c, "x0": x0, "y0": y0, "w": win_w, "h": win_h}
    return {"best": best, "grid": grid, "windows": rows,
            "asset_wh": [W, H],
            "best_region_ratio": (round(best["corr"] - _corr(fg, _gray(asset_path, res)), 4)
                                  if best["corr"] > -2 else None)}


def motion_check(scene_id: str, motion_evidence: dict | None,
                 plan_rects: dict | None = None) -> dict:
    """P17-1c：运动叠加假设的**只读**核查。

    本阶段不渲染（授权明令"不做渲染成片"），故不做静态对照渲染；
    改为核对运动近似参数与展示窗口是否**几何自洽**：
    运动窗口的裁切矩形是否始终落在素材有效区域内、缩放是否改变有效视场。
    """
    ev = (motion_evidence or {}).get(scene_id)
    if not ev:
        return {"motion_enabled": False, "note": "该景未启用运动 ⇒ 运动假设不适用"}
    p = ev.get("params") or {}
    rect = (plan_rects or {}).get(scene_id)
    out = {"motion_enabled": True, "motion_type": ev.get("motion_type"),
           "n_frames": ev.get("n_frames"), "params": p,
           "zoom_start": p.get("zoom_start"), "zoom_end": p.get("zoom_end"),
           "pan_px": p.get("pan_px"), "w_start": p.get("w_start"),
           "w_end": p.get("w_end"), "h_start": p.get("h_start"),
           "h_end": p.get("h_end")}
    if rect:
        out["rect"] = rect
        # 几何自洽：裁切窗口必须 ≥ 输出尺寸（否则会放大采样）
        out["rect_ge_output"] = bool(rect[2] >= 1920 and rect[3] >= 1080
                                     if len(rect) == 4 else None)
    return out


#: 子窗口库参数（P18-1 修复口径；与 P17 原型一致）
BANK_SCALES = (1.00, 0.80, 0.60, 0.45, 0.35)
BANK_GRID = 5


def bank_score(frame_gray, asset_path, *, res: int = 48,
               scales=BANK_SCALES, grid=BANK_GRID) -> dict:
    """**画面 vs 素材子窗口库** 的最大 corr（P18-1 修复的核心口径）。

    从素材取各尺度、各位置的 **16:9 子窗口**，与画面比较取最大。
    与「画面 vs 素材**全图**」相比，该口径对**局部化/裁切/放大**呈现不会结构性失效
    （P17 实证：全图口径把 S08/S13 误判为非 argmax）。**这不是放宽**：
    反门负例（画面 vs 无关素材）同样按此口径比较，取最大仍为低分（P17 实测 55 对中仅 2 对达 0.35）。
    """
    import numpy as np
    from PIL import Image
    with Image.open(asset_path) as im:
        A = np.asarray(im.convert("L"), dtype=np.float64)
    H, W = A.shape[:2]
    best = {"corr": -2.0, "scale": None, "x0": None, "y0": None, "w": None, "h": None}
    for sc in scales:
        w = max(4, int(round(W * sc)))
        h = max(4, int(round(w * 9.0 / 16.0)))
        if h > H:
            h = H
            w = max(4, int(round(h * 16.0 / 9.0)))
        if w > W:
            continue
        for j in range(grid):
            y0 = int(round(j * (H - h) / max(grid - 1, 1)))
            for i in range(grid):
                x0 = int(round(i * (W - w) / max(grid - 1, 1)))
                c = _corr(frame_gray, _to_gray_size(A[y0:y0 + h, x0:x0 + w], res))
                if c > best["corr"]:
                    best = {"corr": round(c, 4), "scale": sc, "x0": x0, "y0": y0,
                            "w": w, "h": h}
    return best


def _windows_16x9(W: int, H: int, scales):
    """枚举 16:9 子窗口几何（宽 = W·scale，高 = min(round(w·9/16), H)）。

    **只产出几何、不产出分数** —— 供 v1/v2 与"步进上限"断言共用同一口径。
    """
    out = []
    for sc in scales:
        w = max(4, int(round(W * sc)))
        h = max(4, int(round(w * 9.0 / 16.0)))
        if h > H:
            h = H
            w = max(4, int(round(h * 16.0 / 9.0)))
        if w > W or w < 8 or h < 8:
            continue
        out.append((sc, w, h))
    return out


def _grid_positions(span: int, extent: int, grid: int):
    """网格起点（含 0 与 `span-extent` 两端）——与 v1 `_round(i·(W-w)/(grid-1))` 同式。"""
    return [int(round(i * (span - extent) / max(grid - 1, 1))) for i in range(grid)]


def min_grid_for_step(span: int, extent: int, limit_px: int = BANK_STEP_PX_V2) -> int:
    """满足**步进 ≤ limit_px** 所需的最小网格数（两端对齐 ⇒ 步进 = (span-extent)/(n-1)）。"""
    if span <= extent:
        return 2
    n = int(math.ceil((span - extent) / float(limit_px))) + 1
    return max(n, 2)


def adaptive_grid(W: int, H: int, *, scales=BANK_SCALES_V2,
                  limit_px: int = BANK_STEP_PX_V2) -> int:
    """对给定素材，求**覆盖全部窗口尺寸**所需的网格数（取各尺寸最大值）。

    运行前写死的纪律：v2 必须保证 **x/y 步进 ≤ limit_px**，故网格随素材尺寸自适应
    （大图用更密网格），而不是固定 `BANK_GRID_V2`。
    """
    g = 2
    for _sc, w, h in _windows_16x9(W, H, scales):
        g = max(g, min_grid_for_step(W, w, limit_px), min_grid_for_step(H, h, limit_px))
    return g


class _Grids:
    """素材尺寸 → 自适应网格数（进程内缓存，避免重复开图）。"""

    _cache: dict = {}

    @classmethod
    def of(cls, asset_path, *, scales=BANK_SCALES_V2,
           limit_px: int = BANK_STEP_PX_V2) -> int:
        import numpy as _np
        from PIL import Image as _Image
        key = (str(asset_path), tuple(scales), int(limit_px))
        hit = cls._cache.get(key)
        if hit is None:
            with _Image.open(asset_path) as im:
                W, H = im.size
            hit = adaptive_grid(W, H, scales=scales, limit_px=limit_px)
            cls._cache[key] = hit
        return hit


def grid_step_px(W: int, H: int, *, scales=BANK_SCALES_V2, grid=None,
                 limit_px: int = BANK_STEP_PX_V2) -> dict:
    """运行前写死的**步进断言**用数据：各窗口尺寸下的 x/y 实际步进（px）。

    `grid=None` ⇒ 用 `adaptive_grid` 自适应网格；v2 要求 **max_step_px ≤ limit_px**。
    """
    if grid is None:
        grid = adaptive_grid(W, H, scales=scales, limit_px=limit_px)
    rows = []
    for sc, w, h in _windows_16x9(W, H, scales):
        xs = _grid_positions(W, w, grid)
        ys = _grid_positions(H, h, grid)
        dx = max((xs[i + 1] - xs[i] for i in range(len(xs) - 1)), default=0)
        dy = max((ys[i + 1] - ys[i] for i in range(len(ys) - 1)), default=0)
        rows.append({"scale": sc, "w": w, "h": h, "w_frac": round(w / W, 4),
                     "h_frac": round(h / H, 4), "step_x_px": dx, "step_y_px": dy})
    mx = max([r["step_x_px"] for r in rows] + [r["step_y_px"] for r in rows] + [0])
    return {"rows": rows, "max_step_px": mx, "limit_px": limit_px,
            "ok": mx <= limit_px, "grid": grid, "scales": list(scales)}


def bank_score_v2(frame_gray, asset_path, *, res: int = BANK_RES_V2,
                  scales=BANK_SCALES_V2, grid=None,
                  limit_px: int = BANK_STEP_PX_V2) -> dict:
    """**bank-derived-v2**：与 `bank_score` 同一语义（画面 vs 素材 16:9 子窗口库取最大 corr），
    但**探针 48→192**、**网格自适应加密**（保证步进 ≤ `limit_px`，默认 170px）。

    **语义不变**：仍是"素材子窗口库的最大 corr"，**阈值不变（0.30）**；
    池内其它素材仍以同一 v2 口径比较 ⇒ 反门（负例）照跑，**不放宽**。
    """
    import numpy as np
    from PIL import Image
    if grid is None:
        grid = _Grids.of(asset_path, scales=scales, limit_px=limit_px)
    with Image.open(asset_path) as im:
        A = np.asarray(im.convert("L"), dtype=np.float64)
    H, W = A.shape[:2]
    best = {"corr": -2.0, "scale": None, "x0": None, "y0": None, "w": None, "h": None,
            "res": res, "grid": grid, "version": BANK_VERSION_V2}
    for sc, w, h in _windows_16x9(W, H, scales):
        for y0 in _grid_positions(H, h, grid):
            for x0 in _grid_positions(W, w, grid):
                c = _corr(frame_gray, _to_gray_size(A[y0:y0 + h, x0:x0 + w], res))
                if c > best["corr"]:
                    best = {"corr": round(c, 4), "scale": sc, "x0": x0, "y0": y0,
                            "w": w, "h": h, "res": res, "grid": grid,
                            "version": BANK_VERSION_V2}
    return best


def resolve_config(config: dict | None, *, root=None) -> tuple[dict, str]:
    """解析**帧匹配**配置（沿用 P10/P13 三级链，**不改被基线钉定的 config.json**）：

      1) `config["tools"]["frame_match"]`（若存在——运行时注入或未来重钉基线后写入；**内置默认**）
      2) **可选外部文件** `config/frame_match.json`（同 `render_motion.json` 模式）
      3) 内置默认 `{"bank_derived": False}` ⇒ 关闭时行为与既有**逐字节一致**（走 v1 原路径）

    `bank_derived` 语义：`False`/缺失 ⇒ 关闭；`True` 或 `"v1"` ⇒ `bank-derived-v1`（冻结口径）；
    `"v2"` ⇒ `bank-derived-v2`（P32-2 双门通过后采纳）。返回 `(cfg, source)`。
    """
    import json as _json
    import pathlib as _pathlib
    tools = ((config or {}).get("tools") or {})
    inline = tools.get("frame_match")
    if isinstance(inline, dict) and inline:
        return {"bank_derived": False, **inline}, "config.tools.frame_match（内存/未来基线）"
    base = _pathlib.Path(root) if root else _pathlib.Path(".")
    ext = base / EXTERNAL_CONFIG_REL
    if ext.is_file():
        try:
            j = _json.loads(ext.read_text(encoding="utf-8"))
            block = j.get("frame_match") if isinstance(j, dict) else None
            block = block if isinstance(block, dict) else (j if isinstance(j, dict) else None)
            if isinstance(block, dict) and block:
                return {"bank_derived": False, **block}, str(ext)
        except (UnicodeDecodeError, ValueError):
            return {"bank_derived": False}, "{}（损坏 ⇒ 保守回落 off）".format(ext)
    return {"bank_derived": False}, "default（无配置 ⇒ bank_derived 关闭）"


def bank_version_of(bank_derived) -> str:
    """把 `bank_derived` 取值规约为版本标签（`""` = 关闭）。"""
    if bank_derived is True:
        return BANK_VERSION_V1
    v = str(bank_derived or "").strip().lower()
    if v in ("v1", "bank-derived-v1", "1"):
        return BANK_VERSION_V1
    if v in ("v2", "bank-derived-v2", "2"):
        return BANK_VERSION_V2
    return ""


def _as_res(frame_gray, res: int):
    """把探针帧规整到 `res×res`（生产链传的是 `gray48` ⇒ v2 需要 192，必须补齐）。

    若已是目标尺寸则**原样返回**（零拷贝、零重采样 ⇒ v1 路径逐字节不变）。
    """
    import numpy as _np
    a = _np.asarray(frame_gray, dtype=_np.float64)
    if a.ndim == 2 and a.shape == (res, res):
        return a
    from PIL import Image as _Image
    img = _Image.fromarray(a.astype("uint8"))
    return _np.asarray(img.convert("L").resize((res, res)), dtype=_np.float64)


def bank_score_of(frame_gray, asset_path, version: str, *, res: int | None = None):
    """按**版本**取 bank 分数（`""` ⇒ 关闭，返回 None）。

    **探针分辨率自动规整**：生产链统一传 `gray48`（48×48）；v1 直接用，
    v2 先上采样到 192×192（`_as_res`）。这样调用方无需知道版本细节，
    而 v1 路径（已是 48×48）**逐字节不变**。
    """
    if version == BANK_VERSION_V2:
        r = BANK_RES_V2 if res is None else res
        return bank_score_v2(_as_res(frame_gray, r), asset_path, res=r)
    if version == BANK_VERSION_V1:
        r = 48 if res is None else res
        return bank_score(_as_res(frame_gray, r), asset_path, res=r)
    return None


def present_test(frame_path, asset_path, pool: dict | None = None,
                 res: int = 48, *, bank: bool = True) -> dict:
    """「素材是否在屏」判定（**P18-1 修复版**）。

    **缺陷（P17 实证）**：旧版以「画面 vs 素材**全图**」比较，
    对**局部化/裁切/放大**呈现**结构性失效**（S08/S13 因画面只是素材的一块而被判非 argmax）。

    **修复**：比较基准改为 **多尺度子窗口 bank**（`bank_score`），池内其它素材同样按 bank 比较
    ⇒ 「局部画面 vs 局部库」，对局部化呈现公平；**反门负例照跑**（不放宽）。

    `bank=False` 保留旧全图口径，供对照与回归复现（**不作为默认**）。
    """
    fg = _gray(frame_path, res)

    def score_of(p) -> dict:
        full = round(_corr(fg, _gray(p, res)), 4)
        bk = bank_score(fg, p, res=res) if bank else {"corr": full, "scale": None,
                                                     "x0": None, "y0": None,
                                                     "w": None, "h": None}
        return {"corr": bk["corr"], "corr_full": full, "bank": bk}

    want = score_of(asset_path)
    scores = [{"name": pathlib.Path(asset_path).name, "corr": want["corr"],
               "corr_full": want["corr_full"], "is_assigned": True}]
    for n, p in (pool or {}).items():
        if pathlib.Path(p) == pathlib.Path(asset_path):
            continue
        try:
            s = score_of(p)
            scores.append({"name": n, "corr": s["corr"], "corr_full": s["corr_full"],
                           "is_assigned": False})
        except Exception:                                                   # noqa: BLE001
            continue
    ranked = sorted(scores, key=lambda x: -x["corr"])
    rank = next((i + 1 for i, x in enumerate(ranked) if x["is_assigned"]), None)
    runner = next((x["corr"] for x in ranked if not x["is_assigned"]), None)
    return {"res": res, "basis": ("subwindow_bank" if bank else "full_image"),
            "corr_assigned": want["corr"], "corr_full": want["corr_full"],
            "rank_of_assigned": rank, "pool_size": len(scores),
            "is_argmax": rank == 1,
            "margin_over_runner_up": (round(want["corr"] - runner, 4)
                                      if runner is not None else None),
            "best_window": want["bank"], "top3": ranked[:3]}


def attribute_scene(*, scene_id: str, frame_path, asset_path,
                    motion_evidence: dict | None = None,
                    plan_rects: dict | None = None,
                    pool: dict | None = None,
                    corr_gate: float | None = None) -> dict:
    """单景归因：跑全部假设并给出结论（确定性）。

    **判定秩序（关键）**：
      0) `region_match`：若「素材是否在屏」检验显示被分配素材在同一分辨率下
         **为 argmax**（画面与它最匹配）⇒ 低 corr 属**度量伪影**，再细分为
         crop / density / subtitle / region；**不**判为错配。
      1) 若素材**不是** argmax（画面更像别的素材）⇒ 属**真实错配候选**，如实报
         `possible_real_mismatch`（不得裁定为在屏）。
      2) 若被分配素材既非 argmax、且所有伪影假设也不成立 ⇒ 同样报 `possible_real_mismatch`。
    """
    gate = FROZEN_MIN_CORR if corr_gate is None else float(corr_gate)
    fg48 = _gray(frame_path, 48)
    present = present_test(frame_path, asset_path, pool=pool, res=48)
    crop = crop_hypothesis(fg48, asset_path, res=48)
    dens = density_hypothesis(frame_path, asset_path)
    subs = subtitle_hypothesis(frame_path, asset_path)
    regn = region_hypothesis(frame_path, asset_path)
    mot = motion_check(scene_id, motion_evidence, plan_rects)

    base = present["corr_assigned"]
    reasons = []
    sub_kind, verdict = None, None

    # --- 伪影细分（仅在"素材在屏"成立时才有意义）---
    if dens["corr_max"] >= gate and (dens["corr_max"] - base) >= SIG_GAIN:
        sub_kind = "density_artifact"
    elif crop["best"]["corr"] >= gate and (crop["best"]["corr"] - base) >= SIG_GAIN:
        sub_kind = "crop_artifact"
    elif subs["corr_masked"] >= gate and (subs["corr_masked"] - base) >= SIG_GAIN:
        sub_kind = "subtitle_artifact"
    elif regn["best"]["corr"] >= gate and (regn["best"]["corr"] - base) >= SIG_GAIN:
        sub_kind = "region_artifact"

    if present["is_argmax"]:
        # 画面与"被分配素材"最匹配 ⇒ 素材确实在屏 ⇒ 伪影
        verdict = sub_kind or ("crop_artifact"
                               if present["rank_of_assigned"] == 1 else "possible_real_mismatch")
        if sub_kind:
            reasons.append("素材在屏（同分辨率 argmax，corr {:.4f}）且细分假设命中：{}".format(
                base, sub_kind))
        else:
            reasons.append("素材在屏（同分辨率 argmax，corr {:.4f}）；"
                           "未命中任一细分假设 ⇒ 判为**分辨率/取样伪影**（度量伪影）".format(base))
            verdict = sub_kind or "sampling_artifact"
        if mot.get("motion_enabled"):
            reasons.append("该景启用运动（{}）⇒ 画面为运动裁切窗口，"
                           "与全图相关性天然低于静态".format(mot.get("motion_type")))
    else:
        verdict = "possible_real_mismatch"
        reasons.append("素材**不是**同分辨率 argmax（rank {}/{}，corr {:.4f}，"
                       "最高为 {} corr {:.4f}）⇒ **可能是真实错配，不得裁定为在屏**".format(
                           present["rank_of_assigned"], present["pool_size"], base,
                           present["top3"][0]["name"][:36], present["top3"][0]["corr"]))

    return {
        "schema": "p17-scene-attribution-v1",
        "scene_id": scene_id,
        "verdict": verdict, "sub_kind": sub_kind, "reasons": reasons,
        "frozen_gate": gate,
        "corr_48_original": base,
        "on_screen_evidence": present,
        "hypotheses": {"crop": crop, "density": dens, "subtitle": subs,
                       "region": regn, "motion": mot},
        "evidence": {"frame": str(frame_path), "asset": str(asset_path)},
    }
