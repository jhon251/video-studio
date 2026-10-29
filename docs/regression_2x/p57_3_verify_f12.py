# -*- coding: utf-8 -*-
"""Phase 57 / P57-3：**F12 烧录 ASS 四门验证**（独立口径，禁止循环）。

授权书 §3（运行前写死，全部以**烧录 ASS / 成片混音**为测对象）：
  · 独立语音运行：对**最终混音** silencedetect（-35dB / d=0.28）——仅作语音段测量，
    **不作 cue 时序来源**；
  · 门① 覆盖 ≥95% 语音时长（cue 并集 ∩ 语音段 / Σ 语音段）；
  · 门② 时长 median ≥3s 且 =1.0s±0.1 的 cue = 0；
  · 门③ 排他／重叠 = 0（0.1s 步进同时活跃 ≤1）；
  · 门④ 同步：句起点（音频锚定 = words_manifest WordBoundary 首词发音时刻）与
    最近 **烧录** cue 起点偏差 median ≤0.35s 且 >1s = 0；
  · 帧检：开场 10s / 中段 / 结尾各抽 1 帧验证字幕带（另存 PNG 供人工复核）。

循环论证禁令：F6–F10.1 的字幕门测的是**构建器输出**（erratum 第四例登记在案）；
本脚本只读两样东西：`_captions_t_<task>.ass`（libass 实际烧录文件）与**成片本身**。

运行: python docs/regression_2x/p57_3_verify_f12.py
"""
from __future__ import annotations

import json
import pathlib
import re
import statistics
import subprocess
import sys
import time

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
FF = str(R / "bin" / "ffmpeg.exe")
FFPROBE = str(R / "bin" / "ffprobe.exe")
P = "p_3e9292101f10"
PDIR = R / "projects" / P

# ---- 门限（授权书 §3，运行前写死）----
G_COVER_MIN = 0.95
G_MEDIAN_MIN_S = 3.0
G_CLAMP_1S_MAX = 0          # 时长 =1.0s±0.1 的 cue 允许数
G_OVERLAP_MAX = 0
G_SYNC_MEDIAN_MAX_S = 0.35
G_SYNC_OVER_1S_MAX = 0
SENT_RE = re.compile(r"[^。！？]*[。！？]|[^。！？]+$")


def log(m):
    print(m, flush=True)


def dur(p):
    r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", str(p)],
                       capture_output=True, text=True)
    v = (r.stdout or "").strip().splitlines()
    return round(float(v[0]), 3) if v and v[0] else None


def parse_ass(p: pathlib.Path):
    """解析烧录 ASS：[(start, end, text)]。"""
    rows = []
    for m in re.finditer(r"Dialogue: 0,([0-9:.]+),([0-9:.]+),Cap,,0,0,0,,(.*)",
                         p.read_text(encoding="utf-8")):
        def sec(ts):
            h, mm, rest = ts.split(":")
            return int(h) * 3600 + int(mm) * 60 + float(rest)
        rows.append((sec(m.group(1)), sec(m.group(2)),
                     m.group(3).replace("\\N", "")))
    return rows


def speech_runs(film: pathlib.Path, noise="-35dB", d=0.28):
    """对**最终混音** silencedetect ⇒ 语音段 [(start,end)]（静音的补集）。"""
    r = subprocess.run([FF, "-v", "info", "-i", str(film), "-af",
                        "silencedetect=noise={}:d={}".format(noise, d),
                        "-f", "null", "-"], capture_output=True, text=True,
                       encoding="utf-8", errors="ignore")
    txt = (r.stderr or "") + (r.stdout or "")
    sil = [(float(a), float(b)) for a, b in zip(
        re.findall(r"silence_start:\s*([0-9.]+)", txt),
        re.findall(r"silence_end:\s*([0-9.]+)", txt))]
    total = dur(film) or 0.0
    runs, cur = [], 0.0
    for a, b in sil:
        if a > cur:
            runs.append((cur, a))
        cur = max(cur, b)
    if cur < total - 0.05:
        runs.append((cur, total))
    return [(round(a, 3), round(b, 3)) for a, b in runs if b - a > 0.02]


def union(ivs):
    out = []
    for a, b in sorted(ivs):
        if out and a <= out[-1][1] + 1e-9:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def intersect_len(a_list, b_list):
    tot, i, j = 0.0, 0, 0
    a_list, b_list = union(a_list), union(b_list)
    while i < len(a_list) and j < len(b_list):
        a0, a1 = a_list[i]
        b0, b1 = b_list[j]
        lo, hi = max(a0, b0), min(a1, b1)
        if hi > lo:
            tot += hi - lo
        if a1 < b1:
            i += 1
        else:
            j += 1
    return tot


def norm_cmp(s: str) -> str:
    return re.sub(r"[\s。！？，、；：""''（）()《》〈〉…—\-·.,;:!?\"'\[\]{}]",
                  "", str(s or ""))


def anchored_sentence_starts():
    """**音频锚定句起点**：words_manifest WordBoundary（独立于构建器运行）。

    句定义与生产**同源**：`normalize(strip_claims(narration))`（与构建器的
    para_text 处理逐字一致——空格差异会改变 `_merge_short` 的句长判定，
    实测 110 vs 101 句 ⇒ 9 个假性 >1s 偏差）。
    """
    from video_studio.core.strip import strip_claims
    from video_studio.core import captions as C
    script = None
    for f in sorted((PDIR / "artifacts").glob("a_*.json")):
        try:
            j = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        segs = j.get("segments") or []
        if segs and isinstance(segs[0], dict) and segs[0].get("audio_window_s")                 and "narration" in segs[0]:
            script = j
            break
    if script is None:
        script = json.loads((PDIR / "artifacts" / "a_aec6a870612e.json")
                            .read_text(encoding="utf-8"))
    wm = {p["para"]: p for p in json.loads(
        (PDIR / "media" / "voice" / "words_manifest.json")
        .read_text(encoding="utf-8")).get("paras") or []}
    by_para = {}
    for s in script["segments"]:
        by_para.setdefault(str(s["scene_id"]).split("_")[0], []).append(s)
    out = []                                                    # [(abs_start, text)]
    for para, lst in sorted(by_para.items()):
        lst = sorted(lst, key=lambda x: x["index"])
        para_start = float(lst[0]["audio_window_s"][0])
        words = (wm.get(para) or {}).get("words") or []
        if not words:
            continue
        para_text = "".join(C.normalize(strip_claims(str(s.get("narration") or "")))
                            for s in lst)
        sents = [m.group(0) for m in SENT_RE.finditer(para_text) if m.group(0).strip()]
        sents = C._merge_short(sents, 8)                        # 句定义与生产同源（P52 登记）
        wnorm = [norm_cmp(w.get("text")) for w in words]
        # 游走（与生产 `_walk_match` 同规则、**独立实现**）：主循环 + P57-1c 尾句重分
        tgt = [norm_cmp(st) for st in sents]
        groups, wi, si, acc = [], 0, 0, ""
        while wi < len(words) and si < len(tgt):
            acc += wnorm[wi]
            want = tgt[si]
            if want and (acc == want
                         or (len(acc) >= len(want) and acc.endswith(want))
                         or len(acc) >= len(want)):
                groups.append((groups[-1][1] + 1 if groups else 0, wi))
                si += 1
                acc = ""
            wi += 1
        if si < len(tgt) and groups:
            # 与生产 P57-1c 同规则：先把末组延伸到真正的最后一词，再重分
            last = (groups[-1][0], len(words) - 1)
            span_words = last[1] - last[0] + 1
            n_rem = len(tgt) - si
            n_groups = 1 + n_rem
            if span_words >= n_groups:
                chars = ([max(len(tgt[len(groups) - 1]), 1)]
                         + [max(len(tgt[si + k]), 1) for k in range(n_rem)])
                tot = sum(chars)
                alloc = [max(1, int(round(span_words * c / tot))) for c in chars]
                while sum(alloc) > span_words:
                    _i = alloc.index(max(alloc))
                    alloc[_i] -= 1
                while sum(alloc) < span_words:
                    alloc[-1] += 1
                new_groups, idx = [], last[0]
                for k in range(n_groups):
                    end = idx + alloc[k] - 1
                    new_groups.append((idx, end))
                    idx = end + 1
                groups[-1:] = new_groups
            else:
                groups[-1] = (groups[-1][0], len(words) - 1)
        elif si < len(tgt) and words:
            groups.append((0, len(words) - 1))
        for gi, (g0, _g1) in enumerate(groups):
            if g0 < len(words):
                out.append((round(para_start + float(words[g0]["start_s"]), 3),
                            sents[gi][:16]))
    return sorted(out)


def frame_band_check(film: pathlib.Path, ts, tag, outdir: pathlib.Path):
    """抽帧 + 字幕带检测（底部 76%–94% 高度带内白字描边的对比度）。"""
    png = outdir / "f12_frame_{}.png".format(tag)
    subprocess.run([FF, "-y", "-v", "error", "-ss", "{:.2f}".format(ts), "-i",
                    str(film), "-frames:v", "1", str(png)], check=True)
    band_lo, band_hi = 0.76, 0.94
    try:
        from PIL import Image
        im = Image.open(png).convert("L")
        w, h = im.size
        band = im.crop((int(w * 0.08), int(h * band_lo), int(w * 0.92),
                        int(h * band_hi)))
        px = list(band.getdata())
        px.sort()
        p3, p97 = px[int(len(px) * 0.03)], px[int(len(px) * 0.97)]
        contrast = p97 - p3
        mean = sum(px) / len(px)
        return {"t": ts, "png": str(png.relative_to(R)), "band_contrast": contrast,
                "band_mean": round(mean, 1), "band_p3": p3, "band_p97": p97}
    except Exception as exc:                                                    # noqa: BLE001
        return {"t": ts, "png": str(png), "error": "{}: {}".format(
            type(exc).__name__, str(exc)[:120])}


def main() -> int:
    global PDIR
    fx_path = (sys.argv[1] if len(sys.argv) > 1
               else "output/phase36_p36_4_sandbox/fixture_f12.json")
    out_name = (sys.argv[2] if len(sys.argv) > 2 else "p57_3_four_gates.json")
    fx = json.loads((R / fx_path).read_text(encoding="utf-8"))
    PDIR = R / "projects" / fx["sandbox_project_id"]
    te, final = fx["editing_task"], R / "output" / ".." / "projects" / P / "output" / fx["final"]
    final = PDIR / "output" / fx["final"]
    ass = PDIR / "artifacts" / "_captions_{}.ass".format(te)
    log("== P57-3 F12 四门验证（烧录 ASS 口径）==")
    log("对象: {} | 成片: {} ({:.3f}s)".format(ass.name, final.name, dur(final) or 0))
    rows = parse_ass(ass)
    PASS, FAIL = [], []

    def check(name, ok, detail=None):
        (PASS if ok else FAIL).append(name)
        log("{}  {} {}".format("PASS" if ok else "FAIL", name,
                               "" if ok else json.dumps(detail, ensure_ascii=False,
                                                        default=str)[:260]))

    # ---- 独立语音测量（最终混音 silencedetect）----
    runs = speech_runs(final)
    speech_total = sum(b - a for a, b in runs)
    log("独立语音测量: {} 个语音段 / Σ {:.3f}s（-35dB, d=0.28，最终混音）".format(
        len(runs), speech_total))

    # ---- 门① 覆盖 ----
    cue_ivs = [(s, e) for s, e, _t in rows]
    cov = intersect_len(cue_ivs, runs) / speech_total if speech_total else 0.0
    check("门① 字幕覆盖语音时长 ≥{:.0%}（实测 {:.1%}）".format(G_COVER_MIN, cov),
          cov >= G_COVER_MIN, {"coverage": round(cov, 4)})

    # ---- 门② 时长 ----
    durs = [round(e - s, 3) for s, e, _t in rows]
    med = statistics.median(durs)
    clamped1s = sum(1 for d in durs if abs(d - 1.0) <= 0.1)
    check("门② 时长 median ≥{:.0f}s（实测 {:.3f}s）".format(G_MEDIAN_MIN_S, med),
          med >= G_MEDIAN_MIN_S, {"median": med})
    check("门②b =1.0s±0.1 的 cue = 0（实测 {}）".format(clamped1s),
          clamped1s <= G_CLAMP_1S_MAX, {"clamped": clamped1s})

    # ---- 门③ 排他 ----
    step = 0.1
    samples = int(max((e for _, e, _t in rows), default=0) / step) + 1
    max_conc, ov_moments = 0, 0
    ends = sorted(e for _s, e, _t in rows)
    import bisect
    starts = sorted(s for s, _e, _t in rows)
    for k in range(samples):
        t = k * step
        conc = bisect.bisect_right(starts, t) - bisect.bisect_right(ends, t)
        max_conc = max(max_conc, conc)
        if conc > 1:
            ov_moments += 1
    check("门③ 排他：同时活跃 ≤1（max={}）且重叠时刻 = 0（实测 {}）".format(
        max_conc, ov_moments), max_conc <= 1 and ov_moments <= G_OVERLAP_MAX,
        {"max_concurrent": max_conc, "overlap_moments": ov_moments})

    # ---- 门④ 同步（句起点 = 音频锚定 WordBoundary）----
    anchors = anchored_sentence_starts()
    cue_starts = sorted(s for s, _e, _t in rows)
    devs = []
    for a, _txt in anchors:
        nearest = min(cue_starts, key=lambda x: abs(x - a)) if cue_starts else None
        if nearest is not None:
            devs.append(round(abs(nearest - a), 4))
    dmed = statistics.median(devs) if devs else -1
    over1 = sum(1 for x in devs if x > 1.0)
    check("门④ 句起点↔最近烧录 cue 起点 median ≤{:.2f}s（实测 {:.4f}s，句 {}）".format(
        G_SYNC_MEDIAN_MAX_S, dmed, len(anchors)),
        dmed <= G_SYNC_MEDIAN_MAX_S, {"median": dmed})
    check("门④b 偏差 >1s 的句 = 0（实测 {}）".format(over1),
          over1 <= G_SYNC_OVER_1S_MAX, {"over_1s": over1,
                                        "worst": max(devs) if devs else None})

    # ---- 帧检（3 景字幕带）----
    fdir = R / "output" / "p57_frames"
    fdir.mkdir(parents=True, exist_ok=True)
    total = dur(final) or 0
    # P59-6：帧检取样改取**覆盖该时刻的 cue 中点**（原固定 t 可能落在 cue 间隙 ⇒
    # 无字幕帧被误判为对比度不足）。
    def _cue_mid(t):
        best = None
        for s0, e0, _t2 in rows:
            if s0 <= t <= e0 or (best is None and s0 > t):
                if s0 <= t <= e0:
                    return round((s0 + e0) / 2, 2)
                best = best or round((s0 + e0) / 2, 2)
        return best if best is not None else t
    for tag, ts in (("open10s", _cue_mid(10.0)), ("mid", _cue_mid(round(total * 0.5, 1))),
                    ("ending", _cue_mid(round(total - 12, 1)))):
        fr = frame_band_check(final, ts, tag, fdir)
        check("帧检 {} t={:.1f}s 字幕带对比度（白字描边）".format(tag, fr.get("t", ts)),
              isinstance(fr.get("band_contrast"), int) and fr["band_contrast"] >= 60,
              fr)

    rec = {"schema": "p57-3-four-gates-v1", "recorded_at":
           time.strftime("%Y-%m-%dT%H:%M:%S"),
           "editing_task": te, "final": fx["final"],
           "speech_runs": {"count": len(runs), "total_s": round(speech_total, 3),
                           "params": "-35dB/d=0.28 on final mix"},
           "coverage": round(cov, 4), "median_dur": med, "clamped_1s": clamped1s,
           "max_concurrent": max_conc, "overlap_moments": ov_moments,
           "sync_median_s": dmed, "sync_over_1s": over1,
           "sentences": len(anchors),
           "pass": len(PASS), "fail": len(FAIL)}
    (R / "docs/regression_2x/logs" / out_name).write_text(
        json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    log("=" * 74)
    log("p57_3_four_gates: {} PASS / {} FAIL".format(len(PASS), len(FAIL)))
    log("=" * 74)
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
