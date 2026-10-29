"""4.x Phase 4-F：可选 BGM + 旁白 ducking（**默认关闭**、确定性、可复算）。

本模块只做三件事，且都**不改变既有音频链**（BGM 关闭时链路一字不变）：

  1. **BGM 校验**（`verify_bgm`）：来源 / sha256 / 音频流 / 解码 / 时长 / 响度 / 静音 / 异常响度 /
     **许可门禁** / **attribution 必填** —— 任一不满足即 `ok=False` 并给出明确错误码；
     调用方必须 fail-closed（**不得**静默降级成"没有 BGM 的成片"）。
  2. **ducking 规则**（`narration_intervals` / `duck_amount_at` / `volume_expression`）：
     · 旁白时间段由 voice 产物的**逐段真实时长**顺序累加得到（可复算，不猜）；
     · 旁白期间 BGM 音量 = `duck_db`，旁白之外 = `bed_db`；边界各做 `ramp_ms` **线性**过渡；
     · 旁白开始时**提前** `ramp_ms` 进入 duck（保证旁白不被盖住），结束时恢复；
     · 相邻/重叠时间段取 `max`（重叠时保持 duck，不会在句中抬起）。
     → 纯函数：同一 (intervals, 参数) 必然给出同一增益曲线与同一 ffmpeg 表达式（可测、可复算）。
  3. **混音装配**（`mix_filters`）：给出 ffmpeg 滤镜片段（BGM 音量包络 → 截断 → 补静音 → `amix`），
     由渲染侧拼进 `filter_complex`；**母带链仍在其后**，因此 -16 LUFS / TP ≤ -1.5 dBTP 契约不变。

纪律：
  · BGM 关闭（默认）→ 本模块不产生任何滤镜/输入，既有输出行为不变；
  · 旁白优先：BGM 增益恒为负（`bed_db`/`duck_db` 默认 -20 / -26 dB），且 `amix` 用 `normalize=0`
    （避免 ffmpeg 自动等权混合改变旁白电平）；
  · 不做音乐推荐、不做 loop 循环拼接、不做节奏改时长、不做语义判断——全部是显式参数与机械规则。
"""
from __future__ import annotations

from pathlib import Path

from .audio import measure_loudness, resolve_ffmpeg
from .materials import classify_license, license_block_reason

# ---------------- 配置（默认关闭） ----------------
BGM_DEFAULTS = {
    "enabled": False,              # **默认关闭**：不配置即完全不启用
    "source": None,                # 文件路径（相对项目目录或绝对路径）
    "provider": None,              # 来源标识（本地自备填 "local_bgm"；外部素材填 provider 名）
    "source_id": None,             # 来源条目 id / 文件名（用于追溯）
    "license": None,               # 许可证声明（原样记录，机械判类：见 core.materials）
    "attribution": None,           # 归属文本（**必填**，缺失即拒绝）
    "sha256": None,                # 期望 sha256（给出则必须一致，否则拒绝）
    "bed_db": -20.0,               # 旁白之外的 BGM 增益
    "duck_db": -26.0,              # 旁白期间的 BGM 增益（必须 ≤ bed_db）
    "ramp_ms": 250,                # duck/恢复的线性过渡时长
    "min_lufs": -45.0,             # 低于此视为静音（拒绝）
    "max_lufs": -8.0,              # 高于此视为异常响度（拒绝）
    "max_peak_dbtp": -1.0,         # 真峰高于此视为异常（拒绝）
    "min_duration_s": 1.0,         # 短于此视为不可用（拒绝）
    "license_required": True,      # 与素材门禁同口径
}
BGM_ERRORS = (
    "BGM_NOT_CONFIGURED",          # enabled=true 但没给 source
    "BGM_SOURCE_UNKNOWN",          # 没有 provider/source_id，来源不明
    "BGM_FILE_MISSING",
    "BGM_EMPTY_FILE",
    "BGM_HASH_MISMATCH",
    "BGM_NOT_AUDIO",               # 没有音频流
    "BGM_DECODE_FAILED",
    "BGM_TOO_SHORT",
    "BGM_LOUDNESS_NOT_MEASURED",
    "BGM_SILENT",
    "BGM_ABNORMAL_LOUDNESS",
    "BGM_LICENSE_MISSING",
    "BGM_LICENSE_UNCLEAR",
    "BGM_LICENSE_RESTRICTED",
    "BGM_ATTRIBUTION_MISSING",
    "BGM_PARAM_INVALID",
    "BGM_MIX_FAILED",
)


class BgmRejectedError(Exception):
    """BGM 不可用——**必须 fail-closed**：不得产出"未声明地没有 BGM"的成片。"""

    def __init__(self, code: str, detail: str = ""):
        super().__init__("[BGM_REJECTED] {}: {}".format(code, detail))
        self.code = code
        self.detail = detail


def bgm_settings(config: dict | None = None) -> dict:
    """读 `tools.bgm`；缺省 = 关闭。非法参数回退默认并标记（不猜测、不放松）。"""
    raw = ((config or {}).get("tools") or {}).get("bgm") or {}
    s = dict(BGM_DEFAULTS)
    notes = []
    for k, v in raw.items():
        if k in ("bed_db", "duck_db", "min_lufs", "max_lufs", "max_peak_dbtp", "min_duration_s"):
            try:
                s[k] = float(v)
            except (TypeError, ValueError):
                notes.append("参数 {}={!r} 非法，保留默认 {}".format(k, v, s[k]))
        elif k == "ramp_ms":
            try:
                s[k] = max(0, int(v))
            except (TypeError, ValueError):
                notes.append("参数 ramp_ms={!r} 非法，保留默认 {}".format(v, s[k]))
        elif k == "license_required":
            s[k] = bool(v)
        else:
            s[k] = v
    s["enabled"] = bool(raw.get("enabled", False))
    if s["ramp_ms"] < 0:
        s["ramp_ms"] = BGM_DEFAULTS["ramp_ms"]
    if s["duck_db"] > s["bed_db"]:
        notes.append("duck_db({}) > bed_db({})：旁白优先原则要求 duck 不高于 bed，已按 bed 取值"
                     .format(s["duck_db"], s["bed_db"]))
        s["duck_db"] = s["bed_db"]
    s["_notes"] = notes
    s["_source"] = "tools.bgm" if raw else "default(disabled)"
    return s


# ---------------- 旁白时间段（可复算） ----------------
def narration_intervals(voice_payload: dict | None, limit_s: float | None = None) -> list[dict]:
    """由 voice 产物的**逐段真实时长**顺序累加得到旁白时间段。

    只统计 `status` 为成功（或非失败）且 `duration_s > 0` 的段落；与 voice agent 拼接旁白音轨的
    顺序一致。返回 [{"index","start_s","end_s","duration_s"}]（时间轴权威：不改变任何时长）。
    """
    segs = list((voice_payload or {}).get("segments") or [])
    out, cursor = [], 0.0
    for s in segs:
        st = str(s.get("status") or "")
        if st.upper() in ("FAILED", "PENDING", "SKIPPED"):
            continue
        try:
            d = float(s.get("duration_s") or 0.0)
        except (TypeError, ValueError):
            d = 0.0
        if d <= 0:
            continue
        start, end = cursor, cursor + d
        if limit_s is not None and start >= float(limit_s):
            break
        if limit_s is not None:
            end = min(end, float(limit_s))
        out.append({"index": s.get("index"), "start_s": round(start, 3),
                    "end_s": round(end, 3), "duration_s": round(d, 3)})
        cursor = end
    return out


def _merge(intervals: list[tuple[float, float]], ramp_s: float) -> list[tuple[float, float]]:
    """按开始时间排序并合并重叠（含 ramp 前后的重叠）；保证 duck 区间单调、无空洞抖动。"""
    iv = sorted((float(a), float(b)) for a, b in intervals if b > a)
    merged: list[tuple[float, float]] = []
    for a, b in iv:
        if merged and a <= merged[-1][1] + 1e-9:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    return merged


def duck_amount_at(t: float, intervals: list[dict] | list[tuple], ramp_s: float) -> float:
    """t 时刻的 duck 程度 ∈ [0,1]（1 = 完全 duck）。纯函数，与 ffmpeg 表达式同构。"""
    pairs = [((i["start_s"], i["end_s"]) if isinstance(i, dict) else (i[0], i[1]))
             for i in intervals]
    r = max(0.0, float(ramp_s))
    best = 0.0
    for a, b in _merge(pairs, r):
        if r <= 0:
            v = 1.0 if a <= t <= b else 0.0
        elif t < a - r or t > b + r:
            v = 0.0
        elif t < a:
            v = (t - (a - r)) / r
        elif t <= b:
            v = 1.0
        else:
            v = ((b + r) - t) / r
        best = max(best, min(1.0, max(0.0, v)))
    return round(best, 9)


def gain_db_at(t: float, intervals, *, bed_db: float, duck_db: float, ramp_s: float) -> float:
    """t 时刻 BGM 增益（dB）：旁白期间 = duck_db，之外 = bed_db，边界线性过渡。"""
    d = duck_amount_at(t, intervals, ramp_s)
    return round(float(bed_db) + (float(duck_db) - float(bed_db)) * d, 6)


def gain_curve(intervals, *, bed_db: float, duck_db: float, ramp_s: float,
               total_s: float, step_s: float = 0.1) -> list[dict]:
    """采样增益曲线（用于证据/绘图/断言；`step_s` 固定即结果可复算）。"""
    n = int(max(0.0, float(total_s)) / max(1e-3, float(step_s))) + 1
    return [{"t": round(i * step_s, 3),
             "gain_db": gain_db_at(i * step_s, intervals, bed_db=bed_db, duck_db=duck_db,
                                   ramp_s=ramp_s)}
            for i in range(n)]


def _n(x: float) -> str:
    f = float(x)
    return str(int(f)) if f == int(f) else ("{:.3f}".format(f).rstrip("0").rstrip("."))


def _trapezoid(a: float, b: float, r: float) -> str:
    """ffmpeg 表达式：区间 [a,b] 内为 1，两侧各 r 秒线性过渡（0→1 / 1→0）。"""
    if r <= 0:
        return "if(between(t,{},{}),1,0)".format(_n(a), _n(b))
    lo, hi = _n(a - r), _n(b + r)
    return ("if(lt(t,{lo}),0,if(lt(t,{a}),((t-({lo}))/{r}),if(lt(t,{b}),1,"
            "if(lt(t,{hi}),(({hi})-t)/{r},0))))").format(lo=lo, hi=hi, a=_n(a), b=_n(b), r=_n(r))


def volume_expression(intervals, *, bed_db: float, duck_db: float, ramp_s: float) -> str:
    """生成 ffmpeg `volume` 滤镜的**线性**增益表达式（`eval=frame` 使用）。

    与 `gain_db_at` 同构：`10^((bed + (duck-bed)*D(t))/20)`，`D(t)=max(各区间梯形)`。
    """
    pairs = [((i["start_s"], i["end_s"]) if isinstance(i, dict) else (i[0], i[1]))
             for i in intervals]
    merged = _merge(pairs, max(0.0, float(ramp_s)))
    if not merged:
        return "pow(10,({})/20)".format(_n(bed_db))
    terms = [_trapezoid(a, b, max(0.0, float(ramp_s))) for a, b in merged]
    # `max()` 需要 ≥2 个参数：只有一个区间时直接用该区间表达式（ffmpeg 会报
    # "Error when evaluating the volume expression" 如果写成 max(单参数)）
    amount = terms[0] if len(terms) == 1 else "max({})".format(",".join(terms))
    delta = float(duck_db) - float(bed_db)
    return "pow(10,({}+({})*{})/20)".format(_n(bed_db), _n(delta), amount)


# ---------------- BGM 校验（来源/字节/许可/归属/响度） ----------------
def _probe_audio(ctx, path: Path, config: dict | None = None) -> tuple[dict | None, str | None]:
    """探测音频流：优先用工具层（有 ctx），否则回退到配置里的 ffprobe（无 ctx 也能用）。"""
    if ctx is not None:
        from ..tools.base import ToolError
        from ..tools.ffmpeg_tool import FFmpegTool
        try:
            res = FFmpegTool().execute({"op": "probe", "inputs": [str(path)]}, ctx)
            streams = (res.data or {}).get("streams") or []
            audio = [s for s in streams if str(s.get("codec_type")) == "audio"]
            if audio:
                return audio[0], None
            return None, "NO_AUDIO_STREAM"
        except ToolError:
            pass                                   # 工具层报错 → 回退 ffprobe 直调（下文）
        except AttributeError:
            pass
    import json as _json
    import shutil as _shutil
    import subprocess
    exe = (((config or {}).get("tools") or {}).get("ffmpeg") or {}).get("ffprobe") \
        or _shutil.which("ffprobe")
    if not exe:
        return None, "FFPROBE_MISSING"
    try:
        r = subprocess.run([exe, "-v", "error", "-select_streams", "a", "-show_streams",
                            "-of", "json", str(path)], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=120)
    except (OSError, subprocess.SubprocessError) as exc:
        return None, "PROBE_FAILED: {}".format(type(exc).__name__)
    if r.returncode != 0:
        return None, "PROBE_RC={}".format(r.returncode)
    try:
        streams = (_json.loads(r.stdout or "{}") or {}).get("streams") or []
    except ValueError:
        return None, "PROBE_PARSE_FAILED"
    if not streams:
        return None, "NO_AUDIO_STREAM"
    return streams[0], None


def _decode_ok(config: dict | None, path: Path) -> tuple[bool, str | None]:
    import subprocess
    exe = resolve_ffmpeg(config)
    if not exe:
        return False, "FFMPEG_MISSING"
    try:
        r = subprocess.run([exe, "-v", "error", "-i", str(path), "-f", "null", "-"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=300)
    except (OSError, subprocess.SubprocessError) as exc:
        return False, "{}: {}".format(type(exc).__name__, str(exc)[:120])
    if r.returncode != 0:
        return False, "rc={} {}".format(r.returncode, (r.stderr or "")[:120])
    return True, None


def verify_bgm(path: str | Path | None, settings: dict, *, ctx=None,
               config: dict | None = None) -> dict:
    """全量校验 BGM 素材。返回证据块（含错误码），**绝不抛异常**给调用方（由调用方决定 fail-closed）。"""
    import hashlib
    s = {**BGM_DEFAULTS, **(settings or {})}
    out = {"ok": False, "code": None, "detail": None, "file": (str(path) if path else None),
           "sha256": None, "bytes": None, "duration_s": None, "lufs": None,
           "true_peak_dbtp": None, "sample_rate": None, "channels": None, "codec": None,
           "license": s.get("license"), "license_class": None, "license_cleared": False,
           "attribution": s.get("attribution"), "provider": s.get("provider"),
           "source_id": s.get("source_id"), "decode_ok": None, "notes": list(s.get("_notes") or [])}
    if not path:
        out.update(code="BGM_NOT_CONFIGURED", detail="enabled=true 但未提供 source")
        return out
    p = Path(path)
    if not p.is_file():
        out.update(code="BGM_FILE_MISSING", detail=str(p))
        return out
    data_hash = hashlib.sha256(p.read_bytes()).hexdigest()
    out["sha256"] = data_hash
    out["bytes"] = p.stat().st_size
    if out["bytes"] <= 0:
        out.update(code="BGM_EMPTY_FILE", detail="0 字节")
        return out
    expected = s.get("sha256")
    if expected and str(expected).lower() != data_hash:
        out.update(code="BGM_HASH_MISMATCH",
                   detail="期望 {} 实际 {}".format(str(expected)[:16], data_hash[:16]))
        return out
    stream, err = _probe_audio(ctx, p, config)
    if err == "NO_AUDIO_STREAM":
        out.update(code="BGM_NOT_AUDIO", detail="ffprobe 未发现音频流")
        return out
    if stream is None:
        out.update(code="BGM_NOT_AUDIO", detail=err or "探测失败")
        return out
    out["sample_rate"] = stream.get("sample_rate")
    out["channels"] = stream.get("channels")
    out["codec"] = stream.get("codec_name")
    ok_dec, derr = _decode_ok(config, p)
    out["decode_ok"] = bool(ok_dec)
    if not ok_dec:
        out.update(code="BGM_DECODE_FAILED", detail=derr)
        return out
    exe = resolve_ffmpeg(config)
    meas = measure_loudness(p, exe=exe)
    if not meas.get("ok"):
        out.update(code="BGM_LOUDNESS_NOT_MEASURED", detail=meas.get("error"))
        return out
    out["lufs"] = meas.get("lufs")
    out["true_peak_dbtp"] = meas.get("true_peak_dbtp")
    dur = None
    if exe:
        import re as _re
        import subprocess
        try:
            r = subprocess.run([exe, "-hide_banner", "-i", str(p)], capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=120)
            m = _re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", r.stderr or "")
            if m:
                dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
        except (OSError, subprocess.SubprocessError):
            dur = None
    out["duration_s"] = round(dur, 3) if dur is not None else None
    if dur is None:
        out.update(code="BGM_LOUDNESS_NOT_MEASURED", detail="时长不可探测")
        return out
    if dur < float(s["min_duration_s"]):
        out.update(code="BGM_TOO_SHORT", detail="{:.3f}s < {:.3f}s".format(dur, s["min_duration_s"]))
        return out
    if float(out["lufs"]) < float(s["min_lufs"]):
        out.update(code="BGM_SILENT", detail="I={:.1f} LUFS < 静音阈值 {:.1f}".format(
            float(out["lufs"]), float(s["min_lufs"])))
        return out
    if float(out["lufs"]) > float(s["max_lufs"]) or (
            out["true_peak_dbtp"] is not None
            and float(out["true_peak_dbtp"]) > float(s["max_peak_dbtp"])):
        out.update(code="BGM_ABNORMAL_LOUDNESS",
                   detail="I={:.1f} LUFS（上限 {:.1f}）/ TP={} dBTP（上限 {:.1f}）".format(
                       float(out["lufs"]), float(s["max_lufs"]), out["true_peak_dbtp"],
                       float(s["max_peak_dbtp"])))
        return out
    # ---- 来源 / 许可 / 归属（与素材许可门禁同口径，机械判定）----
    if not (str(s.get("provider") or "").strip() or str(s.get("source_id") or "").strip()):
        out.update(code="BGM_SOURCE_UNKNOWN", detail="既无 provider 也无 source_id：来源不明")
        return out
    klass, cleared = classify_license(s.get("license"))
    out["license_class"] = klass
    out["license_cleared"] = bool(cleared)
    block = license_block_reason({"license": s.get("license"), "license_class": klass,
                                  "license_cleared": cleared},
                                 require_license=bool(s.get("license_required", True)))
    if block:
        code = {"ASSET_LICENSE_RESTRICTED": "BGM_LICENSE_RESTRICTED",
                "ASSET_LICENSE_MISSING": "BGM_LICENSE_MISSING",
                "ASSET_LICENSE_UNCLEAR": "BGM_LICENSE_UNCLEAR"}.get(block, "BGM_LICENSE_UNCLEAR")
        out.update(code=code, detail="license={!r} class={}".format(s.get("license"), klass))
        return out
    if not str(s.get("attribution") or "").strip():
        out.update(code="BGM_ATTRIBUTION_MISSING", detail="许可合规但缺少 attribution 文本")
        return out
    out["ok"] = True
    return out


# ---------------- 混音装配（BGM 关闭时不产生任何片段） ----------------
def mix_filters(*, narration_label: str, bgm_label: str, master_chain: str | None,
                intervals, settings: dict, total_s: float, narration_audio_duration_s=None,
                bgm_duration_s: float | None = None,
                padding_budget_s: float | None = None) -> dict:
    """给渲染侧的滤镜片段 + 证据（不做 ffmpeg 调用，纯字符串构造）。

    片段顺序：旁白 `apad` → BGM `volume(包络)` → `atrim`（过长截断）→ `apad`（过短补静音）
              → `amix(normalize=0, duration=first)` → 母带链（`master_chain`，可为 None）。

    **Duration Contract v2**：`total_s` 应为 `audio_time_base`（Σ 实际 TTS + pause budget + trailing）。
    旁白 `apad` 的补齐量会被记录并与 `padding_budget_s` 比对（`narration_pad_within_budget`）：
    **不允许**用 `apad` 掩盖旁白短缺（超预算由渲染前门禁 fail-closed）。
    """
    s = {**BGM_DEFAULTS, **(settings or {})}
    total = float(total_s)
    expr = volume_expression(intervals, bed_db=float(s["bed_db"]), duck_db=float(s["duck_db"]),
                             ramp_s=float(s["ramp_ms"]) / 1000.0)
    bgm_chain = ("volume='{}':eval=frame".format(expr) +
                 ",atrim=0:{:.3f}".format(total) + ",asetpts=N/SR/TB,apad")
    parts = [f"[{narration_label}]apad[narr]",
             f"[{bgm_label}]{bgm_chain}[bed]",
             "[narr][bed]amix=inputs=2:duration=first:normalize=0:dropout_transition=0[mix]",
             "[mix]" + ((master_chain + ",") if master_chain else "") + "anull[aout]"]
    trimmed = bool(bgm_duration_s is not None and float(bgm_duration_s) > total + 1e-6)
    padded = bool(bgm_duration_s is not None and float(bgm_duration_s) < total - 1e-6)
    # v2：旁白补齐量 vs 授权预算（仅记录；超预算由渲染前门禁阻断）
    narr_pad = None
    pad_ok = None
    if narration_audio_duration_s is not None:
        try:
            narr_pad = round(max(total - float(narration_audio_duration_s), 0.0), 3)
        except (TypeError, ValueError):
            narr_pad = None
        if narr_pad is not None and padding_budget_s is not None:
            pad_ok = bool(narr_pad <= float(padding_budget_s) + 1e-6)
    return {
        "filters": parts,
        "volume_expression": expr,
        "evidence": {
            "applied": True,
            "bed_db": float(s["bed_db"]), "duck_db": float(s["duck_db"]),
            "duck_delta_db": round(float(s["duck_db"]) - float(s["bed_db"]), 3),
            "ramp_ms": int(s["ramp_ms"]),
            "narration_priority": True,
            "amix": {"inputs": 2, "normalize": 0, "duration": "first"},
            "intervals_used": [dict(i) for i in intervals],
            "duck_windows": [[round(max(0.0, i["start_s"] - s["ramp_ms"] / 1000.0), 3),
                              round(i["end_s"] + s["ramp_ms"] / 1000.0, 3)] for i in intervals],
            "total_s": round(total, 3),
            "bgm_duration_s": (round(float(bgm_duration_s), 3)
                               if bgm_duration_s is not None else None),
            "trimmed_to_film": trimmed,
            "padded_after_bgm_end": padded,
            # ---- Duration Contract v2：旁白补齐预算审计 ----
            "narration_audio_duration_s": (round(float(narration_audio_duration_s), 3)
                                           if narration_audio_duration_s is not None else None),
            "narration_pad_s": narr_pad,
            "padding_budget_s": (round(float(padding_budget_s), 3)
                                 if padding_budget_s is not None else None),
            "narration_pad_within_budget": pad_ok,
            "padding_policy": "apad 只覆盖显式 pause budget；不得掩盖旁白短缺",
            "rule": ("旁白时间段内 BGM 增益 = duck_db，之外 = bed_db；边界各做 ramp_ms 线性过渡；"
                     "旁白开始前提前 ramp_ms 进入 duck（旁白优先，不被覆盖）"),
        },
    }
