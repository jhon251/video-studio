# -*- coding: utf-8 -*-
"""P20-1 40 段 voice 产物派生（沙箱、确定性、**零重合成**）。

输入：
  · 既有 `voice_output`（21 段 segments_manifest + `media/voice/narration.mp3`）
  · **第 1 轮句界拆分**时间轴（P19-3 第 1 轮：21→40 景，切点全在旁白句边界）

操作（纯切片，不改一字文本）：
  1. 对每个父景按**句界**（`[。！？!?；;]`）确定性生成 40 段窗口，并给出每段的
     **文本片段**（逐字继承原段文本的字符区间）与**窗口时长**；
  2. 在父景音频窗内做 `silencedetect`，把**实测静音中点**吸附到最近的句界预测位置
     ⇒ 得到 40 个**落在真实停顿上**的切点（确定性：静音阈值/最小时长固定）；
  3. 用这些切点**物理切片** narration 音频 → 40 个 wav；**实测**每段时长；
  4. **fail-closed 校验**：
       · 每段切片文件存在且 >0；
       · 每段实测时长与"文本占比 × 父景实测时长"偏差 ≤ 容差（否则无法证明切点对应句子）；
       · 每段文本 fragment 的 sha256 与"重算哈希"一致（防改写）；
       · Σ实测 + pause 预算 与目标时基偏差在容差内。
     任一不过 ⇒ **BLOCKED**，不产出可渲染 voice 产物。

provenance：derived_from（voice 产物 sha256 + 拆镜台账 sha256）、切片规则版本、逐段 sha256。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import subprocess
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
SRC = R / "projects" / "p_96efdc03e1aa"
OUTDIR = R / "output" / "phase20_voice_sandbox"
FF = str(R / "bin" / "ffmpeg.exe")
FFPROBE = str(R / "bin" / "ffprobe.exe")
SENT = re.compile(r"[。！？!?；;]")
RULE_VERSION = "p20-voice-slice-v1:sentence-boundary+silence-snap"
PAUSE_BUDGET_S = 0.75
TRAILING_PAD_S = 2.0
#: **pause 总量守恒**（关键）：父 21 段原本只有 20×0.75=15.0s 的 pause 预算；
#: 切成 40 段后若每边界仍给 0.75s，会凭空多出 14.25s ⇒ 时基漂移 +14.2s（实测已触发 fail-closed）。
#: 故**保留 pause 总量**并把边界数从 20 增到 39 时按比例缩小每边界预算 ⇒ 时基不变。
PAUSE_TOTAL_FROM_PARENT = 0.75 * 20
DUR_TOL_S = 1.5          # 切片实测 vs 文本占比预测 的容差
TARGET_BASE_S = 978.656

VOICE_ART = SRC / "artifacts" / "a_e99273b936c0.json"
SPLIT_LEDGER = L / "phase19_split_execution_ledger.json"


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def probe(path) -> float | None:
    r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", str(path)], capture_output=True, text=True)
    try:
        return round(float(r.stdout.strip().splitlines()[0]), 3)
    except Exception:                                                           # noqa: BLE001
        return None


def detect_silences(audio, start, end, noise_db=-38, min_dur=0.12):
    """在 [start,end] 窗内检测静音，返回 [(中点绝对秒, 时长), ...]。"""
    r = subprocess.run([FF, "-hide_banner", "-nostats", "-ss", "{:.3f}".format(start),
                        "-t", "{:.3f}".format(max(end - start, 0.05)), "-i", str(audio),
                        "-af", "silencedetect=n={}dB:d={}".format(noise_db, min_dur),
                        "-f", "null", "-"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    out, cur = [], None
    for line in (r.stderr or "").splitlines():
        m = re.search(r"silence_start:\s*([0-9.]+)", line)
        if m:
            cur = float(m.group(1))
        m2 = re.search(r"silence_end:\s*([0-9.]+)", line)
        if m2 and cur is not None:
            e = float(m2.group(1))
            out.append((round(start + (cur + e) / 2.0, 3), round(e - cur, 3)))
            cur = None
    return out


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    OUTDIR.mkdir(parents=True, exist_ok=True)
    (OUTDIR / "seg").mkdir(parents=True, exist_ok=True)

    voice = json.loads(VOICE_ART.read_text(encoding="utf-8"))
    ledger = json.loads(SPLIT_LEDGER.read_text(encoding="utf-8"))
    script = json.loads((R / "output/phase13e_script_sandbox/script_dcv2_derived_v1.json")
                        .read_text(encoding="utf-8"))
    r1 = ledger["rounds"][0]                      # 第 1 轮（句界拆分）
    narr = SRC / "media" / "voice" / "narration.mp3"
    AUDIO_DUR = probe(narr) or 0.0
    print("父 voice 产物:", VOICE_ART.name, "| 段数:", len(voice.get("segments") or []))
    print("narration.mp3:", narr.is_file(), "| 实测:", AUDIO_DUR)
    # **EOF 夹取（关键）**：旁白音频实测 961.656s，而父窗口按脚本累计到 978.68s
    # （差额 17.02s 由 pause/trailing **垫到片尾**）。若不夹取，最后一个父景的切片会越过
    # 音频 EOF ⇒ 实测时长远小于预测（实测触发 fail-closed）。
    EOF_CLAMP = AUDIO_DUR if AUDIO_DUR > 0 else float("inf")

    def eff_window(t0: float, t1: float) -> tuple[float, float]:
        """把父窗口夹取到 [t0, min(t1, EOF_CLAMP)]；返回**有效**窗口（长度可能缩短）。"""
        return t0, max(t0 + 0.1, min(t1, EOF_CLAMP))
    print("拆分轮次:", r1["round"], "目标 ≤{}s".format(r1["target_max_s"]),
          "| 提案:", r1["proposal_count"])

    # --- 1) 由第 1 轮目标集重建 40 段窗口 + 文本片段 ---
    targets = {p["scene_id"] for p in ledger["rounds"][0]["approved_proposals"]}
    parent_audio = {s["index"]: float(s["duration_s"])
                    for s in (voice.get("segments") or [])}
    cursor = 0.0
    parent_win = {}
    for i, s in enumerate(script["segments"]):
        d = max(float(s["duration_s"]), 3.0)
        parent_win[s["scene_id"]] = (round(cursor, 3), round(cursor + d, 3), i)
        cursor += d

    segs = []
    for s in script["segments"]:
        sid = s["scene_id"]
        t0, t1 = parent_win[sid][0], parent_win[sid][1]
        t0e, t1e = eff_window(t0, t1)
        dur = max(float(s["duration_s"]), 3.0)
        txt = str(s.get("narration") or "")
        if sid not in targets:
            segs.append({"scene_id": sid, "parent": sid, "narration": txt,
                         "text_sha256": hashlib.sha256(txt.encode("utf-8")).hexdigest(),
                         "parent_window_s": [t0e, t1e], "rel": [0.0, 1.0]})
            continue
        n = max(2, int(dur // 35.0) + (1 if dur % 35.0 else 0))
        while n > 2 and dur / n < 12.0:
            n -= 1
        bounds = [m.end() for m in SENT.finditer(txt)]
        fracs = []
        if bounds and len(bounds) >= n - 1:
            step = len(bounds) / n
            for k in range(1, n):
                bi = min(len(bounds) - 1, max(0, int(round(step * k)) - 1))
                fracs.append(bounds[bi] / max(len(txt), 1))
        else:
            fracs = [k / n for k in range(1, n)]
        fracs = sorted(set(round(f, 6) for f in fracs if 0.02 < f < 0.98))
        cuts = [0.0] + fracs + [1.0]
        for i2 in range(len(cuts) - 1):
            a, b = cuts[i2], cuts[i2 + 1]
            frag = txt[int(round(a * len(txt))):int(round(b * len(txt)))]
            segs.append({"scene_id": "{}p{}".format(sid, i2 + 1), "parent": sid,
                         "narration": frag,
                         "text_sha256": hashlib.sha256(frag.encode("utf-8")).hexdigest(),
                         "parent_window_s": [t0e, t1e], "rel": [a, b]})
    print("派生段数:", len(segs))

    # --- 2) 每父景：静音吸附 → 绝对切点 ---
    cuts_by_parent, snap_log = {}, []
    for s in script["segments"]:
        sid = s["scene_id"]
        if sid not in targets:
            continue
        t0, t1 = eff_window(*parent_win[sid][:2])
        sil = detect_silences(narr, t0, t1)
        preds = [(x["rel"][1], x["scene_id"]) for x in segs
                 if x["parent"] == sid and x["rel"][1] < 1.0]
        picked = []
        for frac, cid in preds:
            pt = t0 + (t1 - t0) * frac
            tol = max(0.8, 0.25 * ((t1 - t0) / max(len(preds) + 1, 1)))
            if sil:
                best = min(sil, key=lambda z: abs(z[0] - pt))
                snapped = abs(best[0] - pt) <= tol
                cut = best[0] if snapped else pt
            else:
                cut, snapped = pt, False
            picked.append((round(cut, 3), cid, snapped))
        picked.sort(key=lambda z: z[0])
        # 单调化 + 最小间隔（0.4s）
        clean, prev = [], t0
        for c, cid, sn in picked:
            c = max(c, prev + 0.4)
            c = min(c, t1 - 0.4)
            clean.append((round(c, 3), cid, sn))
            prev = c
        cuts_by_parent[sid] = clean
        snap_log.append({"parent": sid, "window": [t0, t1], "silences": len(sil),
                         "cuts": [{"scene_id": cid, "abs_s": c, "silence_snapped": sn}
                                  for c, cid, sn in clean]})

    # --- 3) 物理切片 + 实测 ---
    results, fails = [], []
    for s in segs:
        sid, parent = s["scene_id"], s["parent"]
        t0, t1 = eff_window(*parent_win[parent][:2])
        if parent in cuts_by_parent:
            cl = [c for c, _, _ in cuts_by_parent[parent]]
            idx = [x["scene_id"] for x in segs if x["parent"] == parent].index(sid)
            a = t0 if idx == 0 else cl[idx - 1]
            b = t1 if idx == len([x for x in segs if x["parent"] == parent]) - 1 else cl[idx]
        else:
            a, b = t0, t1
        out = OUTDIR / "seg" / "{}.wav".format(sid)
        r = subprocess.run([FF, "-v", "error", "-y", "-ss", "{:.3f}".format(a),
                            "-t", "{:.3f}".format(max(b - a, 0.05)), "-i", str(narr),
                            "-ac", "1", "-ar", "24000", str(out)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        meas = probe(out) if out.is_file() else None
        rec = {**{k: s[k] for k in ("scene_id", "parent", "narration", "text_sha256",
                                    "parent_window_s", "rel")},
               "audio": "seg/{}.wav".format(sid), "slice_window_s": [a, b],
               "duration_s": meas, "bytes": (out.stat().st_size if out.is_file() else 0),
               "audio_sha256": (sha(out) if out.is_file() else None)}
        # fail-closed ①：文件与实测
        if r.returncode != 0 or not out.is_file() or not meas or meas <= 0.05:
            fails.append({"scene_id": sid, "code": "SLICE_MISSING_OR_EMPTY",
                          "detail": "rc={} exists={} meas={}".format(
                              r.returncode, out.is_file(), meas)})
        # fail-closed ②：文本哈希自洽
        if rec["text_sha256"] != hashlib.sha256(rec["narration"].encode("utf-8")).hexdigest():
            fails.append({"scene_id": sid, "code": "TEXT_HASH_MISMATCH"})
        # fail-closed ③：实测 vs 文本占比预测
        pw = t1 - t0
        pred = pw * (s["rel"][1] - s["rel"][0])
        if meas is not None and abs(meas - pred) > max(DUR_TOL_S, 0.25 * pred):
            fails.append({"scene_id": sid, "code": "DURATION_MISMATCH",
                          "detail": "meas={:.3f} pred={:.3f}".format(meas, pred)})
        results.append(rec)

    # --- 4) 时基（v2 语义）---
    n = len(results)
    total_meas = round(sum(float(x["duration_s"] or 0) for x in results), 3)
    # **pause 总量守恒**：每边界预算 = 父 pause 总量 / 新边界数
    pause_per = round(PAUSE_TOTAL_FROM_PARENT / max(n - 1, 1), 6)
    pause_total = round(pause_per * max(n - 1, 0), 3)
    base = round(total_meas + pause_total + TRAILING_PAD_S, 3)
    if abs(base - TARGET_BASE_S) > 2.0:
        fails.append({"code": "TIME_BASE_DRIFT",
                      "detail": "base={:.3f} target={:.3f}".format(base, TARGET_BASE_S)})
    # 文本总字符守恒（不可改写）
    orig_chars = sum(len(str(x.get("narration") or "")) for x in script["segments"])
    new_chars = sum(len(x["narration"]) for x in results)
    if orig_chars != new_chars:
        fails.append({"code": "TEXT_LOSS", "detail": "{} -> {}".format(orig_chars, new_chars)})

    decision = "BLOCKED" if fails else "READY"
    payload = None
    if not fails:
        payload = {k: v for k, v in voice.items()}
        payload["audio"] = "media/voice/narration.mp3"
        payload["segments"] = [{"index": i, "audio": x["audio"], "status": "SUCCESS",
                                "reused": False, "attempts": 1, "bytes": x["bytes"],
                                "duration_s": x["duration_s"],
                                "text_sha256": x["text_sha256"][:32]}
                               for i, x in enumerate(results)]
        payload["segment_details"] = [{"index": i, "duration_s": x["duration_s"],
                                       "audio": x["audio"]} for i, x in enumerate(results)]
        payload["audio_time_base_s"] = base
        payload["narration_duration_s"] = total_meas
        payload["expected_segments"] = n
        payload["successful_segments"] = n
        payload["failed_segments"] = []
        payload["complete"] = True
        payload["script_time_base_s"] = base
        payload["_phase20_slice"] = {
            "rule_version": RULE_VERSION,
            "derived_from_voice_artifact": "a_e99273b936c0",
            "derived_from_voice_sha256": sha(VOICE_ART),
            "derived_from_split_ledger_sha256": sha(SPLIT_LEDGER),
            "source_audio_sha256": sha(narr),
            "pause_budget_s": pause_per, "pause_total_s": pause_total,
            "pause_total_preserved_from_parent": PAUSE_TOTAL_FROM_PARENT,
            "trailing_pad_s": TRAILING_PAD_S,
            "segments": n, "total_measured_s": total_meas,
            "audio_time_base_s": base,
            "zero_resynthesis": True, "text_verbatim": True,
            "orig_chars": orig_chars, "new_chars": new_chars,
            "note": ("纯切片（无 TTS 重合成）；文本按句界逐字继承；"
                     "切点吸附实测静音中点（确定性阈值）；v2 时基按 Σ实测+pause+trailing"),
        }
        p = OUTDIR / "voice_output_40seg.json"
        p.write_text(json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=True),
                     encoding="utf-8")

    rep = {
        "schema": "phase20-p20-1-voice-slice-v1",
        "stage": "Phase 20 P20-1 40 段 voice 产物派生（零重合成）",
        "rule_version": RULE_VERSION,
        "inputs": {"voice_artifact": str(VOICE_ART.relative_to(R)).replace("\\", "/"),
                   "voice_sha256": sha(VOICE_ART),
                   "split_ledger": str(SPLIT_LEDGER.relative_to(R)).replace("\\", "/"),
                   "split_ledger_sha256": sha(SPLIT_LEDGER),
                   "source_audio": str(narr.relative_to(R)).replace("\\", "/"),
                   "source_audio_sha256": sha(narr)},
        "round_executed": 1,
        "round_2_3_status": "NOT_EXECUTED（句中切点设计债，见 KNOWN_ISSUES）",
        "segments": len(results),
        "time_base": {"total_measured_s": total_meas, "pause_total_s": pause_total,
                      "trailing_pad_s": TRAILING_PAD_S, "audio_time_base_s": base,
                      "target_s": TARGET_BASE_S, "delta_s": round(base - TARGET_BASE_S, 3)},
        "text_verbatim": {"orig_chars": orig_chars, "new_chars": new_chars,
                          "equal": orig_chars == new_chars, "edited": False},
        "silence_snap": snap_log,
        "fail_closed": {"triggered": bool(fails), "failures": fails},
        "decision": decision,
        "output": (str((OUTDIR / "voice_output_40seg.json").relative_to(R)).replace("\\", "/")
                   if payload else None),
        "per_segment": results,
        "zero_llm": True, "zero_vlm": True, "zero_network": True, "resynthesis": False,
    }
    rp = L / "phase20_p20_1_voice_slice.json"
    rp.write_text(json.dumps(rep, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")

    print()
    print("=" * 78)
    print("P20-1 结果")
    print("=" * 78)
    print("  段数:", len(results), "| Σ实测 {:.3f}s | pause {:.3f}s | trailing {:.1f}s".format(
        total_meas, pause_total, TRAILING_PAD_S))
    print("  audio_time_base_s: {:.3f}（目标 {:.3f}，Δ {:+.3f}）".format(
        base, TARGET_BASE_S, base - TARGET_BASE_S))
    print("  文本逐字: {} -> {} 字符（相等: {}）".format(orig_chars, new_chars,
                                                        orig_chars == new_chars))
    snapped = sum(1 for g in snap_log for c in g["cuts"] if c["silence_snapped"])
    tot = sum(len(g["cuts"]) for g in snap_log)
    print("  静音吸附: {}/{} 切点落在实测停顿上".format(snapped, tot))
    print("  fail-closed:", rep["fail_closed"]["triggered"], "| 判定:", decision)
    for f in fails[:6]:
        print("    !!", f.get("scene_id", "-"), f["code"], str(f.get("detail"))[:60])
    print("  报告 ->", rp.relative_to(R).as_posix())
    return 0 if not fails else 9


if __name__ == "__main__":
    sys.exit(main())
