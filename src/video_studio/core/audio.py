"""3.x Phase 3-B：音频响度契约（**单一事实源**）+ 真实测量 + 判定。

背景（Phase 3-B 审计实测）：
  · 正式 Agent 渲染链此前**只做 `apad`**，成片实测 **-19.7 LUFS**（目标 -16，超差 3.7 LU）；
  · `stage32b` 路径用 `loudnorm(I=-16:TP=-1.5:LRA=11) + alimiter + volume(+0.4dB)`；
  · 两条路径目标值相同但**没有共享定义**，也没有对成片做可复核的响度 QC。
本模块把契约与实现收口到一处，供正式链、`stage32b` 与测试共同引用。

契约（用户授权指定）：
  · Integrated loudness: **-16 LUFS**（允许 ±1 LU）
  · True peak: **≤ -1.5 dBTP**
  · 用**真实 ffmpeg** `loudnorm` 处理、`alimiter` 限幅；用 `ebur128=peak=true` **实测**成片判定。

**不做法律/语义判断，也不猜**：测不到就 `ok=False` 并给出原因（fail-closed）。
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

# ---------------- 契约（单一事实源） ----------------
TARGET_LUFS = -16.0
MAX_TRUE_PEAK_DBTP = -1.5
TOLERANCE_LU = 1.0
TARGET_LRA = 11.0
LIMITER_LIMIT = 0.7079          # 线性幅度 = -3.01 dBFS（与 stage32b 既有取值一致）
LIMITER_ATTACK_MS = 1
LIMITER_RELEASE_MS = 10
STAGE32B_POST_GAIN_DB = 0.4     # stage32b 既有的限幅补偿（保持其行为不变）

LOUDNESS_CONTRACT = {
    "target_lufs": TARGET_LUFS,
    "max_true_peak_dbtp": MAX_TRUE_PEAK_DBTP,
    "tolerance_lu": TOLERANCE_LU,
    "target_lra": TARGET_LRA,
    "method": "ffmpeg ebur128=peak=true（实测成片）",
    "policy": "loudness_contract_v1",
}


class LoudnessContractError(Exception):
    """成片响度不满足契约——**必须 fail-closed**，不得产出"成功但不达标"的成片。"""


# 测量失败（无 ffmpeg / 无音轨 / 解析失败）**不抛异常**，而是以 `ok=False + error` 返回，
# 由调用方按 fail-closed 处理——避免"异常被吞掉后当成通过"。


# ---------------- 滤镜构造（两条路径共用） ----------------
def loudnorm_filter(target_lufs: float = TARGET_LUFS, true_peak: float = MAX_TRUE_PEAK_DBTP,
                    lra: float = TARGET_LRA) -> str:
    """标准 `loudnorm` 滤镜串（单遍模式；`linear=false` 即 ffmpeg 默认动态模式）。"""
    return "loudnorm=I={}:TP={}:LRA={}".format(_num(target_lufs), _num(true_peak), _num(lra))


def limiter_filter(limit: float = LIMITER_LIMIT) -> str:
    """硬限幅：把真峰压在 `limit`（线性）以下，保证 TP 约束。"""
    return "alimiter=limit={}:attack={}:release={}:level=false".format(
        limit, LIMITER_ATTACK_MS, LIMITER_RELEASE_MS)


def mastering_chain(target_lufs: float = TARGET_LUFS, true_peak: float = MAX_TRUE_PEAK_DBTP,
                    lra: float = TARGET_LRA, post_gain_db: float = 0.0,
                    sample_rate: int | None = None) -> str:
    """统一母带链：`loudnorm` → `alimiter` [→ `volume` 补偿] [→ `aresample` 复原采样率]。

    `post_gain_db` 默认为 0（正式 Agent 链直接落在 -16 LUFS）；`stage32b` 沿用既有的
    +0.4 dB 限幅补偿（其限幅上限 -3 dBFS，补偿后最坏 TP ≈ -2.6 dBTP，仍在契约内）。

    **`sample_rate` 很重要**：ffmpeg `loudnorm` 内部按 192 kHz 处理并**输出 192 kHz**，
    不显式复原就会把成片音轨悄悄从 24 kHz 变成 192 kHz（实测踩到）。因此正式链会把
    输入音频的真实采样率传进来做 `aresample` 还原。
    """
    parts = [loudnorm_filter(target_lufs, true_peak, lra), limiter_filter()]
    if post_gain_db:
        parts.append("volume={}dB".format(_num(post_gain_db)))
    if sample_rate:
        parts.append("aresample={}".format(int(sample_rate)))
    return ",".join(parts)


def probe_audio_rate(ctx, path: str | Path) -> int | None:
    """探测音频采样率（Hz）；探测失败/无 ctx 返回 None（调用方自行决定默认值，不猜）。"""
    if ctx is None:
        return None
    from ..tools.base import ToolError
    from ..tools.ffmpeg_tool import FFmpegTool

    try:
        res = FFmpegTool().execute({"op": "probe", "inputs": [str(path)]}, ctx)
    except (ToolError, AttributeError):
        return None
    for s in (res.data or {}).get("streams") or []:
        if str(s.get("codec_type")) != "audio":
            continue
        try:
            return int(s.get("sample_rate"))
        except (TypeError, ValueError):
            return None
    return None


def _num(x: float) -> str:
    """数值格式化：整数不带小数点（-16 而不是 -16.0），与既有滤镜串保持一致。"""
    f = float(x)
    return str(int(f)) if f == int(f) else str(f)


# ---------------- 配置读取（默认 = 授权契约值；不改默认行为） ----------------
def contract_from_config(config: dict | None = None) -> dict:
    """从 `tools.ffmpeg.loudness` 读取契约；缺省即**授权契约值**（-16 / TP -1.5 / ±1 LU）。

    允许覆盖（便于跨平台/客户定制），但**默认绝不放松**；非法值忽略并保留默认（不猜测）。
    """
    c = dict(LOUDNESS_CONTRACT)
    raw = ((((config or {}).get("tools") or {}).get("ffmpeg") or {}).get("loudness") or {})
    for key, caster in (("target_lufs", float), ("max_true_peak_dbtp", float),
                        ("tolerance_lu", float), ("target_lra", float)):
        if key in raw:
            try:
                c[key] = caster(raw[key])
            except (TypeError, ValueError):
                pass
    return c


def mastering_enabled_from_config(config: dict | None = None) -> bool:
    """是否在渲染时应用母带链（默认 True）。

    `apply_mastering=false` **不会**关掉 QC——它只是跳过处理，因此渲染会被响度 QC
    fail-closed 拦下（仅用于故障注入验证，不能用来产出不合规成片）。
    """
    raw = ((((config or {}).get("tools") or {}).get("ffmpeg") or {}).get("loudness") or {})
    return bool(raw.get("apply_mastering", True))


# ---------------- 真实测量（ebur128） ----------------
def resolve_ffmpeg(config: dict | None = None) -> str | None:
    """按配置解析 ffmpeg 可执行文件（与渲染/抽帧同一口径）；找不到返回 None。"""
    configured = (((config or {}).get("tools") or {}).get("ffmpeg") or {}).get("path")
    return shutil.which(configured or "ffmpeg")


_I_SUMMARY = re.compile(r"Integrated loudness:\s*\n\s*I:\s*(-?[\d.]+)\s*LUFS")
_I_ANY = re.compile(r"I:\s*(-?[\d.]+)\s*LUFS")
_TP_SUMMARY = re.compile(r"True peak:\s*\n\s*Peak:\s*(-?[\d.]+)\s*dBFS", re.I)
_TP_ANY = re.compile(r"TPK:\s*(-?[\d.]+)\s*dBFS", re.I)


def measure_loudness(path: str | Path, exe: str | None = None,
                     timeout_s: float = 900.0) -> dict:
    """用真实 ffmpeg `ebur128=peak=true` 测量文件的**集成响度**与**真峰**。

    返回 {"lufs": float|None, "true_peak_dbtp": float|None, "ok": bool, "error": str|None,
          "method": "ffmpeg ebur128=peak=true", "ffmpeg": exe, "raw_tail": str}
    `ok=False` 表示**测不到**（无 ffmpeg / 无音轨 / 解析失败）——调用方必须按 fail-closed 处理。
    """
    p = Path(path)
    out = {"lufs": None, "true_peak_dbtp": None, "ok": False, "error": None,
           "method": "ffmpeg ebur128=peak=true", "ffmpeg": exe, "path": str(p),
           "raw_tail": ""}
    if exe is None:
        out["error"] = "FFMPEG_MISSING：找不到 ffmpeg，无法测量响度（不猜测）"
        return out
    if not p.is_file():
        out["error"] = "FILE_MISSING：{} 不存在".format(p)
        return out
    cmd = [exe, "-hide_banner", "-nostats", "-i", str(p),
           "-af", "ebur128=peak=true", "-f", "null", "-"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout_s)
    except (OSError, subprocess.TimeoutExpired) as exc:
        out["error"] = "MEASURE_FAILED：{}: {}".format(type(exc).__name__, str(exc)[:160])
        return out
    err = r.stderr or ""
    out["raw_tail"] = err[-600:]
    if r.returncode != 0:
        out["error"] = "MEASURE_RC={}：{}".format(r.returncode,
                                                  (err.strip().splitlines() or [""])[-1][:160])
        return out
    m_i = _I_SUMMARY.search(err) or _I_ANY.search(err)
    if m_i is None:
        out["error"] = "LOUDNESS_NOT_FOUND：ebur128 输出中没有集成响度（可能无音轨）"
        return out
    m_tp = _TP_SUMMARY.search(err) or _TP_ANY.search(err)
    out["lufs"] = float(m_i.group(1))
    out["true_peak_dbtp"] = float(m_tp.group(1)) if m_tp else None
    out["ok"] = True
    return out


def check_contract(measured: dict, contract: dict | None = None) -> tuple[bool, list[str]]:
    """判定实测值是否满足契约。返回 (ok, reasons[])；**测不到即不通过**。"""
    c = {**LOUDNESS_CONTRACT, **(contract or {})}
    reasons: list[str] = []
    if not measured.get("ok"):
        return False, ["LOUDNESS_NOT_MEASURED：{}".format(measured.get("error") or "未知原因")]
    lufs = measured.get("lufs")
    tp = measured.get("true_peak_dbtp")
    target = float(c["target_lufs"])
    tol = float(c["tolerance_lu"])
    if lufs is None:
        reasons.append("LOUDNESS_NOT_MEASURED：集成响度缺失")
    elif abs(float(lufs) - target) > tol:
        reasons.append("LOUDNESS_OUT_OF_RANGE：I={:.1f} LUFS，目标 {:.1f} LUFS ±{:.1f} LU"
                       .format(float(lufs), target, tol))
    if tp is None:
        reasons.append("TRUE_PEAK_NOT_MEASURED：真峰缺失")
    elif float(tp) > float(c["max_true_peak_dbtp"]) + 1e-9:
        reasons.append("TRUE_PEAK_EXCEEDED：TP={:.2f} dBTP > 上限 {:.2f} dBTP"
                       .format(float(tp), float(c["max_true_peak_dbtp"])))
    return (not reasons), reasons


def verify_file(path: str | Path, exe: str | None = None,
                contract: dict | None = None) -> dict:
    """测量 + 判定，返回可直接写进产物的证据块（含目标值/误差/fail-closed 结论）。"""
    c = {**LOUDNESS_CONTRACT, **(contract or {})}
    measured = measure_loudness(path, exe=exe)
    ok, reasons = check_contract(measured, c)
    return {
        "ok": ok,
        "reasons": reasons,
        "measured_lufs": measured.get("lufs"),
        "measured_true_peak_dbtp": measured.get("true_peak_dbtp"),
        "target_lufs": c["target_lufs"],
        "max_true_peak_dbtp": c["max_true_peak_dbtp"],
        "tolerance_lu": c["tolerance_lu"],
        "delta_lu": (None if measured.get("lufs") is None
                     else round(float(measured["lufs"]) - float(c["target_lufs"]), 3)),
        "method": measured["method"],
        "ffmpeg": measured.get("ffmpeg"),
        "file": str(path),
        "measure_error": measured.get("error"),
    }


def evidence_block(measured: dict) -> str:
    """一行可读摘要（写进日志/summary）。"""
    return json.dumps({"I": measured.get("lufs"), "TP": measured.get("true_peak_dbtp"),
                       "target": LOUDNESS_CONTRACT["target_lufs"],
                       "tol": LOUDNESS_CONTRACT["tolerance_lu"]}, ensure_ascii=False)


# ---------------- 两遍线性 loudnorm（4.x Phase 4-F 的 BGM 路径专用；既有路径不使用） ----------------
# 为什么需要它：**单遍动态** loudnorm 对"大动态"素材会系统性地低于目标（实测含 BGM 的混音
# LRA≈18 LU → 单遍结果为 -19.5 LUFS，偏差 3.5 LU，超过 3 LU 收尾校正上限 → 按契约 fail-closed）。
# 两遍法第一遍**测量**（input_i/lra/tp/thresh/offset），第二遍用 `linear=true` 精确应用，
# 实测可达 -15.9 LUFS（±1 内）。目标值仍是同一份契约常量，本函数**只**给 BGM 扩展路径使用；
# BGM 关闭时既有单遍链与全部行为不变。
_LOUDNORM_JSON = re.compile(r"\{[^{}]*\"input_i\"[^{}]*\}", re.S)


def measure_loudnorm_input(path: str | Path, exe: str | None, contract: dict | None = None,
                           timeout_s: float = 900.0) -> dict:
    """两遍法的第一遍：返回 ffmpeg loudnorm 的测量 JSON（失败即 `ok=False`，不猜）。"""
    c = {**LOUDNESS_CONTRACT, **(contract or {})}
    out = {"ok": False, "error": None, "measured": None}
    if exe is None:
        out["error"] = "FFMPEG_MISSING"
        return out
    af = "{}:print_format=json".format(loudnorm_filter(c["target_lufs"], c["max_true_peak_dbtp"],
                                                       c["target_lra"]))
    try:
        r = subprocess.run([exe, "-hide_banner", "-nostats", "-i", str(path), "-af", af,
                            "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout_s)
    except (OSError, subprocess.TimeoutExpired) as exc:
        out["error"] = "PASS1_FAILED: {}".format(type(exc).__name__)
        return out
    m = _LOUDNORM_JSON.search(r.stderr or "")
    if not m:
        out["error"] = "PASS1_NO_JSON: rc={}".format(r.returncode)
        return out
    try:
        data = json.loads(m.group(0))
    except ValueError:
        out["error"] = "PASS1_BAD_JSON"
        return out
    out["measured"] = data
    out["ok"] = True
    return out


def normalize_two_pass(src: str | Path, dst: str | Path, *, exe: str | None,
                       contract: dict | None = None, sample_rate: int | None = None,
                       timeout_s: float = 1800.0) -> dict:
    """两遍线性 loudnorm：测量 → 精确应用（同一契约常量 + `alimiter` + 可选 `aresample`）。

    返回证据块 {"ok","error","filter","measured_input","after","contract"}；**不做静默降级**。
    """
    c = {**LOUDNESS_CONTRACT, **(contract or {})}
    ev = {"ok": False, "error": None, "filter": None, "measured_input": None, "after": None,
          "contract": {k: c[k] for k in ("target_lufs", "max_true_peak_dbtp", "tolerance_lu",
                                         "target_lra")},
          "method": "loudnorm 两遍（linear=true）+ alimiter"}
    p1 = measure_loudnorm_input(src, exe, c, timeout_s=timeout_s)
    ev["measured_input"] = p1.get("measured")
    if not p1["ok"]:
        ev["error"] = p1.get("error")
        return ev
    d = p1["measured"]
    af = "{}:measured_I={}:measured_LRA={}:measured_TP={}:measured_thresh={}:offset={}:linear=true"\
        .format(loudnorm_filter(c["target_lufs"], c["max_true_peak_dbtp"], c["target_lra"]),
                d.get("input_i"), d.get("input_lra"), d.get("input_tp"), d.get("input_thresh"),
                d.get("target_offset"))
    parts = [af, limiter_filter()]
    if sample_rate:
        parts.append("aresample={}".format(int(sample_rate)))
    af = ",".join(parts)
    ev["filter"] = af
    cmd = [exe or "ffmpeg", "-y", "-hide_banner", "-nostats", "-i", str(src), "-af", af,
           "-c:a", "pcm_s16le"]
    if sample_rate:
        cmd += ["-ar", str(int(sample_rate))]
    cmd += [str(dst)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=timeout_s)
    except (OSError, subprocess.TimeoutExpired) as exc:
        ev["error"] = "PASS2_FAILED: {}".format(type(exc).__name__)
        return ev
    if r.returncode != 0 or not Path(dst).is_file():
        ev["error"] = "PASS2_RC={}: {}".format(r.returncode, (r.stderr or "")[-200:])
        return ev
    after = verify_file(dst, exe=exe, contract=c)
    ev["after"] = after
    ev["ok"] = bool(after["ok"])
    if not ev["ok"]:
        ev["error"] = "POST_CHECK_FAILED: {}".format("；".join(after.get("reasons") or []))
    return ev


# ---------------- 成片级强制（测量 → （小残差）收尾校正 → 再测量，fail-closed） ----------------
def enforce_loudness_on_film(film: str | Path, exe: str | None = None,
                             contract: dict | None = None,
                             max_corrections: int = 2,
                             max_correction_lu: float = 3.0) -> dict:
    """对**成片**执行响度契约：实测 → 小残差可做收尾校正（仅重编音频）→ 再实测。

    **fail-closed 语义（关键）**：
      · 偏差 ≤ `max_correction_lu`（默认 3 LU）→ 允许一次"收尾校正"（`volume`/`alimiter`，
        不改变采样率与时长），并把每次尝试写进 `passes[]`；
      · 偏差 > `max_correction_lu` → **不校正、直接判不合格**——大幅偏差意味着母带链根本没生效，
        静默"修好"会掩盖故障（例如 `apply_mastering=false` 的故障注入必须被阻断）。
      · 测不到（无音轨/无 ffmpeg）→ 不合格（绝不当作通过）。

    返回证据块：{"ok", "corrections", "final", "passes[]", "contract", "method"}。
    **不改变画面**（视频流复制），因此抽帧核验结论不受影响。
    """
    c = {**LOUDNESS_CONTRACT, **(contract or {})}
    film = Path(film)
    ev = verify_file(film, exe=exe, contract=c)
    passes = [ev]
    corrections = 0
    while not ev["ok"] and corrections < max(0, int(max_corrections)):
        if exe is None or ev.get("measured_lufs") is None:
            break                                   # 测不到 → 不做无依据的动作（fail-closed）
        lufs, tp = ev.get("measured_lufs"), ev.get("measured_true_peak_dbtp")
        delta = float(c["target_lufs"]) - float(lufs)
        if abs(delta) > float(max_correction_lu):
            ev = {**ev, "correction_refused": "偏差 {:.2f} LU 超过可校正上限 {:.2f} LU（母带链未生效？）"
                  .format(abs(delta), float(max_correction_lu))}
            passes[-1] = ev
            break
        # 校正**刻意不使用 loudnorm**：`volume`/`alimiter` 不改变采样率与时长，
        # 避免把成片音轨再从 24 kHz 变成 192 kHz（实测踩过这个坑）。
        if abs(delta) > float(c["tolerance_lu"]):
            af = "volume={}dB".format(round(max(-40.0, min(40.0, delta)), 3))
        elif tp is not None and float(tp) > float(c["max_true_peak_dbtp"]):
            af = limiter_filter()
        else:
            break
        tmp = film.with_name(film.stem + ".loudfix" + film.suffix)
        cmd = [exe, "-y", "-hide_banner", "-nostats", "-i", str(film),
               "-af", af, "-c:v", "copy", "-c:a", "aac", str(tmp)]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=1800)
        except (OSError, subprocess.TimeoutExpired) as exc:
            passes.append({"ok": False, "reasons": ["LOUDNESS_CORRECTION_FAILED：{}".format(exc)],
                           "measured_lufs": None, "measured_true_peak_dbtp": None})
            break
        if r.returncode != 0 or not tmp.is_file():
            passes.append({"ok": False,
                           "reasons": ["LOUDNESS_CORRECTION_FAILED：rc={}".format(r.returncode)],
                           "measured_lufs": None, "measured_true_peak_dbtp": None})
            break
        tmp.replace(film)
        corrections += 1
        ev = verify_file(film, exe=exe, contract=c)
        ev["applied_filter"] = af
        passes.append(ev)
    return {"ok": bool(ev["ok"]), "corrections": corrections, "final": ev, "passes": passes,
            "contract": {k: c[k] for k in ("target_lufs", "max_true_peak_dbtp", "tolerance_lu",
                                           "target_lra")},
            "method": ev.get("method")}
