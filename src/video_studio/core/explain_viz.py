# -*- coding: utf-8 -*-
"""P60：**解释级可视化生成器 MVP**（`core/explain_viz.py`）。

能力（P59 审计缺口 #1/#2 的最小可验证模块）：
  输入 = 旁白 cue 时间轴（真实 WordBoundary 派生）+ **语义节拍计划**
  （上游脚本阶段产物：每拍记录对应旁白、语义标签、解释目标、预期理解）
  → 校验/投影/决策 → 模板渲染（着色/计数/清单/坍缩/时间轴 + hold）→ mp4。

设计边界（P59 审计结论的诚实落点）：
  · **语义映射来自上游显式标注，不是本模块的关键词猜测**——本模块自主完成
    校验、时序投影、模板执行、失败回退，并把每个决定记录在案；
  · 任何校验失败 ⇒ 返回 fallback（含原因），**绝不伪装成解释动画**；
  · 输出 = 普通视频文件，走既有「视频素材消费」通道（P58-2），管线零改动；
  · 确定性：同输入 ⇒ 同输出（seed 固定，无随机、无网络、LLM $0）。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import random
import subprocess
import time
from PIL import Image, ImageDraw, ImageFont

TEMPLATES = ("coloring", "counting", "checklist", "collapse", "timeline", "hold")
MAX_GAP_S = 3.0

# ---- P0（2026-10-20）：字幕安全区 + 卡内文字去重 ------------------------------
# 审计实测（§4-⑥/⑧）：卡内标题与底部烧录字幕常是**同一句话的两种改写**，
# 画面里同一信息出现两次；且部分模板把文字放到 0.78–0.82 高度，被字幕压住。
# 这里约定：**底部 18%（0.82–1.0）保留给烧录字幕**，卡内文字一律不进入该带。
SAFE_BOTTOM_Y = 0.82
#: 卡内 caption 与旁白相似度 ≥ 此值 ⇒ 判定"重复"，不再绘制（字幕会承担）
DUP_RATIO = 0.55


def _norm_text(s: str) -> str:
    out = []
    for ch in str(s or ""):
        if ch.isalnum():
            out.append(ch.lower())
    return "".join(out)


def caption_duplicates_narration(caption: str, narration: str) -> bool:
    """卡内说明是否与旁白重复（去标点后按字符序列相似度判定，确定性）。"""
    a, b = _norm_text(caption), _norm_text(narration)
    if not a or not b:
        return False
    if a in b:
        return True
    import difflib
    sm = difflib.SequenceMatcher(None, a, b)
    if sm.real_quick_ratio() < DUP_RATIO or sm.quick_ratio() < DUP_RATIO:
        return False
    return sm.ratio() >= DUP_RATIO


# ---------------------------------------------------------------- 契约与校验

def load_beat_plan(path) -> dict:
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def validate_beat_plan(plan: dict, cues: list[dict]) -> tuple[list[str], list[dict]]:
    """校验语义节拍计划。返回 (errors, projected_beats)。

    projected_beats = 按音频时间投影后的节拍（越界裁剪、决策标记）。
    errors 非空 ⇒ 调用方必须回退，不得渲染。
    """
    errors: list[str] = []
    win = plan.get("window") or [0.0, 0.0]
    w0, w1 = float(win[0]), float(win[1])
    if w1 <= w0:
        return ["window 非法"], []
    beats = sorted(plan.get("beats") or [], key=lambda b: float(b.get("start", 0)))
    projected = []
    prev_end = w0
    for b in beats:
        s = max(float(b.get("start", 0)), w0)
        e = min(float(b.get("end", 0)), w1)
        if e <= s:
            continue
        tpl = b.get("template")
        if tpl not in TEMPLATES:
            errors.append("未知模板: {}".format(tpl))
            prev_end = e
            continue
        narr = str(b.get("narration") or "")
        cover = next((c for c in cues if c["start"] - 0.01 <= s < c["end"]), None)
        if narr and cover is not None and narr[:12] not in cover["text"]:
            errors.append("旁白引用与 cue 不符: {} vs {}".format(
                narr[:20], cover["text"][:20]))
            prev_end = e
            continue
        goal = str(b.get("explanation_goal") or "").strip()
        animate = tpl != "hold"
        if animate and not goal:
            errors.append("解释节拍缺少 explanation_goal（{}-{:.2f}）".format(s, e))
        if s - prev_end > MAX_GAP_S:
            errors.append("节拍间 {:.2f}s 未解释空隙（{:.2f} → {:.2f}）".format(
                s - prev_end, prev_end, s))
        p = dict(b)
        p["start"], p["end"] = round(s, 3), round(e, 3)
        p["decision"] = "animate" if animate else "no_animation"
        projected.append(p)
        prev_end = e
    if projected and w1 - projected[-1]["end"] > MAX_GAP_S:
        errors.append("尾部 {:.2f}s 未解释空隙".format(w1 - projected[-1]["end"]))
    return errors, projected


# ---------------------------------------------------------------- 渲染器

class Renderer:
    """确定性帧渲染器：同 plan ⇒ 同输出（无随机、无网络）。"""

    def __init__(self, plan: dict, width=1920, height=1080, font_dir=None):
        self.W, self.H = width, height
        self.dark = bool((plan.get("style") or {}).get("dark", True))
        self.pal = (plan.get("style") or {}).get("palette") or [
            (228, 87, 46), (61, 139, 216), (243, 167, 18), (93, 169, 161)]
        self.fdir = font_dir or (plan.get("style") or {}).get("font_dir") or "C:/Windows/Fonts/"
        self._fc = {}
        self._map_cache = {}

    def f(self, name, size):
        key = (name, size)
        if key not in self._fc:
            self._fc[key] = ImageFont.truetype(self.fdir + name, size)
        return self._fc[key]

    def frame(self, beat: dict, t: float) -> Image.Image:
        im = Image.new("RGB", (self.W, self.H),
                       (16, 20, 24) if self.dark else (245, 245, 245))
        dr = ImageDraw.Draw(im)
        fg = (235, 235, 235) if self.dark else (30, 30, 30)
        yel = (255, 214, 90)
        u = min(1.0, max(0.0, (t - beat["start"]) / max(beat["end"] - beat["start"], 0.1)))
        tpl = beat["template"]
        pr = dict(beat.get("params") or {})
        # P0：卡内 caption 与旁白重复 ⇒ 不画（底部字幕已承担同一条信息）。
        # `hold` 例外：它是整屏标题卡，caption 就是唯一内容，去掉会黑屏。
        if tpl != "hold":
            _narr = str(beat.get("narration") or "")
            for _k in ("caption", "caption1"):
                if pr.get(_k) and caption_duplicates_narration(str(pr[_k]), _narr):
                    pr.pop(_k, None)
        fn = getattr(self, "_tpl_" + tpl)
        b2 = dict(beat)
        b2["params"] = pr
        fn(dr, b2, pr, t, u, fg, yel)
        return im

    def _center(self, dr, y, text, fnt, fill, stroke=0, sc=(0, 0, 0)):
        w = dr.textlength(text, font=fnt)
        dr.text(((self.W - w) / 2, y), text, font=fnt, fill=fill,
                stroke_width=stroke, stroke_fill=sc)

    # -- coloring：网格地图逐块四色着色 + 相邻约束冲突拍 --
    def _tpl_coloring(self, dr, beat, pr, t, u, fg, yel):
        regions, colors, order = self._map_spec(pr)
        n = len(regions)
        conflict_t = float(beat.get("params", {}).get("conflict_at", 0) or 0)
        conflict_end = float(beat.get("params", {}).get("conflict_end", 0) or 0)
        pair = beat.get("params", {}).get("conflict_pair") or []
        colored = int(min(1.0, u * 1.15) * n)
        for rid, _col, poly in regions:
            fill = (226, 220, 205) if self.dark else (210, 210, 210)
            if rid < colored:
                fill = self.pal[colors[rid] % 4]
            if conflict_t <= t < conflict_end and rid in pair:
                fill = self.pal[pair[0] % 4]          # 冲突：两块同色
            dr.polygon(poly, fill=fill, outline=(40, 40, 40), width=3)
        if conflict_t and conflict_t <= t < conflict_end and pair:
            for rid, _col, poly in regions:
                if rid in pair:
                    dr.polygon(poly, outline=(228, 60, 46), width=8)
        cap = beat.get("params", {}).get("caption")
        if cap:                                   # 顶部说明（避开底部烧录字幕带）
            self._center(dr, int(self.H * 0.06), cap,
                         self.f("msyhbd.ttc", 60),
                         (235, 235, 235) if self.dark else (30, 30, 30), 3)

    def _map_spec(self, pr):
        key = (pr.get("map_seed", 20261015), pr.get("cols", 5), pr.get("rows", 2))
        if key in self._map_cache:
            return self._map_cache[key]
        cols, rows, seed = key[1], key[2], key[0]
        rng = random.Random(seed)
        W, H = self.W, self.H
        x0, y0, x1, y1 = int(W*0.19), int(H*0.17), int(W*0.81), int(H*0.83)
        G = [[(x0 + (x1-x0)*c/cols + rng.randint(-int(W*0.014), int(W*0.014)),
               y0 + (y1-y0)*r/rows + rng.randint(-int(H*0.011), int(H*0.011)))
              for c in range(cols+1)] for r in range(rows+1)]
        G[0][0], G[0][cols], G[rows][0], G[rows][cols] = (x0, y0), (x1, y0), (x0, y1), (x1, y1)
        regions, idx, colors = [], {}, {}
        for r in range(rows):
            for c in range(cols):
                rid = len(regions)
                idx[(r, c)] = rid
                banned = {colors[idx[n]] for n in
                          ((r, c-1), (r-1, c)) if n in idx}
                col = next(k for k in range(4) if k not in banned)
                colors[rid] = col
                poly = [G[r][c], G[r][c+1], G[r+1][c+1], G[r+1][c]]
                regions.append((rid, col, poly))
        # 邻接（供 conflict/审计）：共享边的区域对
        adj = {rid: [] for rid, _col, _poly in regions}
        for (rid, col, poly), (rid2, col2, poly2) in [
                (a, b) for a in regions for b in regions if a[0] < b[0]]:
            edges1 = {tuple(sorted((poly[i], poly[(i+1) % 4]))) for i in range(4)}
            edges2 = {tuple(sorted((poly2[i], poly2[(i+1) % 4]))) for i in range(4)}
            if edges1 & edges2:
                adj[rid].append(rid2)
                adj[rid2].append(rid)
        self._map_cache[key] = (regions, colors, adj)
        return self._map_cache[key]

    def _tpl_counting(self, dr, beat, pr, t, u, fg, yel):
        v = str(pr.get("value_text") or "")
        size = int(min(self.W * 0.9 / max(len(v), 1) / 0.62, self.H * 0.24))
        f = ImageFont.truetype(self.fdir + "msyhbd.ttc", size)
        self._center(dr, int(self.H*0.32), v, f, yel, 6)
        cap = pr.get("caption")
        if cap:
            self._center(dr, int(self.H*0.62), cap, self.f("msyh.ttc", 52), fg, 2)

    def _tpl_checklist(self, dr, beat, pr, t, u, fg, yel):
        cap = pr.get("caption") or ""
        self._center(dr, int(self.H*0.10), cap, self.f("msyhbd.ttc", 72), fg, 3)
        pattern = pr.get("item_pattern") or "item {:03d} ... OK"
        n = int(pr.get("items", 30))
        rate = float(pr.get("items_per_s", 12))
        done = int(min(u * rate * (float(beat["end"]) - float(beat["start"])), n))
        fmono = self.f("consola.ttf", 34)
        for i in range(done):
            y = int(self.H*0.26) + (i % 15) * int(self.H*0.033)
            x = int(self.W*0.30) if i < 15 else int(self.W*0.58)
            dr.text((x, y), pattern.format(i + 1), font=fmono, fill=(106, 191, 105))
        if done >= n:
            self._center(dr, int(self.H*0.76), pr.get("done_text", "OK"),
                         self.f("msyhbd.ttc", 96), yel, 5)

    def _tpl_collapse(self, dr, beat, pr, t, u, fg, yel):
        t1 = float(pr.get("phase1_end", 0.5))
        bins = list(pr.get("bins") or [])
        mini = int(pr.get("mini_maps", 24))
        if u < t1:
            shown = int(u / t1 * mini)
            cols = 6
            for i in range(shown):
                x = int(self.W*0.08) + (i % cols) * int(self.W*0.14)
                y = int(self.H*0.24) + (i // cols) * int(self.H*0.10)
                dr.rounded_rectangle((x, y, x + int(self.W*0.11), y + int(self.H*0.085)),
                                     radius=8, fill=(28, 34, 42),
                                     outline=(120, 120, 120), width=2)
            self._center(dr, int(self.H*0.14), pr.get("caption1") or "",
                         self.f("msyh.ttc", 48), fg, 2)
        else:
            for i, lab in enumerate((pr.get("bins") or [])[:3]):
                x0 = int(self.W*0.14) + i * int(self.W*0.25)
                y0 = int(self.H*0.42)
                dr.rounded_rectangle((x0, y0, x0 + int(self.W*0.20), y0 + int(self.H*0.24)),
                                     radius=14, fill=(28, 34, 42), outline=yel, width=3)
                dr.text((x0 + 24, y0 + 18), lab, font=self.f("msyhbd.ttc", 44), fill=yel)
            self._center(dr, int(self.H*0.74), pr.get("caption") or "",
                         self.f("msyh.ttc", 46), fg, 2)

    def _tpl_timeline(self, dr, beat, pr, t, u, fg, yel):
        y = int(self.H*0.55)
        dr.line((int(self.W*0.12), y, int(self.W*0.88), y), fill=fg, width=4)
        marker = str(pr.get("marker") or "")
        mx = int(self.W*0.12) + int(self.W*0.76 * float(pr.get("marker_u", 0.5)))
        dr.ellipse((mx - 14, y - 14, mx + 14, y + 14), fill=yel)
        self._center(dr, y - int(self.H*0.16), marker,
                     self.f("msyhbd.ttc", int(self.H*0.11)), (255, 255, 255), 5)
        cap = pr.get("caption")
        if cap:
            self._center(dr, y + int(self.H*0.06), cap,
                         self.f("msyh.ttc", 48), fg, 2)

    def _tpl_hold(self, dr, beat, pr, t, u, fg, yel):
        cap = pr.get("caption")
        if cap:
            self._center(dr, int(self.H*0.42), cap,
                         self.f("msyhbd.ttc", 88), yel, 5)


# ---------------------------------------------------------------- 渲染入口

def render_animation(plan: dict, cues: list[dict], out_path, *,
                     ffmpeg: str = "ffmpeg", audio_path=None, fps: int = 25,
                     font_dir=None) -> dict:
    """校验 → 逐帧渲染 → mp4。返回证据 dict；校验/渲染失败 ⇒ ok=False + fallback 原因。"""
    t0 = time.time()
    errors, projected = validate_beat_plan(plan, cues)
    ev = {"schema": "p60-explain-viz-v1", "ok": False, "errors": errors,
          "beats": len(projected), "seed": plan.get("seed", 20261015)}
    if errors:
        ev["fallback"] = "beat_plan_invalid"
        ev["render_s"] = round(time.time() - t0, 1)
        return ev
    out = pathlib.Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fr = out.parent / (out.stem + "_frames")
    fr.mkdir(parents=True, exist_ok=True)
    for f in fr.glob("f_*.png"):
        f.unlink()
    rnd = Renderer(plan, *(plan.get("canvas") or [1920, 1080]), font_dir=font_dir)
    total = float(plan["window"][1])
    n = int(total * fps)
    for i in range(n):
        t = i / fps
        beat = next((b for b in projected if b["start"] <= t < b["end"]),
                    projected[-1] if projected else None)
        rnd.frame(beat, t).save(fr / "f_{:05d}.png".format(i), compress_level=1)
    cmd = [str(ffmpeg), "-y", "-v", "error", "-framerate", str(fps),
           "-i", str(fr / "f_%05d.png")]
    if audio_path:
        cmd += ["-i", str(audio_path), "-map", "0:v", "-map", "1:a:0", "-shortest",
                "-c:a", "aac", "-b:a", "160k"]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-pix_fmt", "yuv420p", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True, errors="ignore")
    ev["render_s"] = round(time.time() - t0, 1)
    ev["ok"] = r.returncode == 0 and out.is_file() and out.stat().st_size > 0
    ev["output"] = str(out)
    ev["output_sha256"] = (hashlib.sha256(out.read_bytes()).hexdigest()
                           if out.is_file() else None)
    ev["frames"] = n
    if not ev["ok"]:
        ev["fallback"] = "render_failed: " + (r.stderr or "")[:160]
    return ev
