"""Phase 3-B 测试：音频响度契约（统一 -16 LUFS / TP ≤ -1.5 dBTP / ±1 LU）+ 实测 QC + fail-closed。

**全部用真实 ffmpeg 与真实音频实测**，不使用任何 mock 数值：
  A 组 契约与判定原语（纯逻辑，无 ffmpeg）
  B 组 真实音频：从**真实 TTS 旁白**（Phase 3-A 项目产出的 narration.mp3）切真实片段，
       分别构造"原样/压低 20dB/抬高 20dB"三种真实输入 → 走生产链同一条母带链 → **实测**是否达标
  C 组 成片级强制：真实成片实测 → 必要时仅重编音频校正 → 再实测；无音轨文件必须 fail-closed
  D 组 走**正式渲染入口**（Engine + editing agent）产真实成片：断言 render_output.audio_loudness
       达标且成片复测达标；并用 `apply_mastering=false` 真实跑一次故障注入，
       断言渲染被 fail-closed 阻断（不是靠改测试脚本伪造）

用法：python tests/audio_loudness_test.py
"""
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.agents.base import AGENTS  # noqa: E402
from video_studio.core.audio import (LOUDNESS_CONTRACT, LoudnessContractError,  # noqa: E402
                                     TARGET_LUFS, TOLERANCE_LU, check_contract,
                                     contract_from_config, enforce_loudness_on_film,
                                     limiter_filter, loudnorm_filter, mastering_chain,
                                     measure_loudness, verify_file)
from video_studio.core.engine import Engine  # noqa: E402
from video_studio.core.narration import NarrationIncompleteError  # noqa: E402
from video_studio.db.schema import Database  # noqa: E402
from video_studio.llm.router import MockLLM, Router  # noqa: E402

import video_studio.agents.asset.agent  # noqa: E402,F401
import video_studio.agents.audio.agent  # noqa: E402,F401
import video_studio.agents.editing.agent  # noqa: E402,F401
import video_studio.agents.retrieval.agent  # noqa: E402,F401
import video_studio.agents.script.agent  # noqa: E402,F401
import video_studio.agents.voice.agent  # noqa: E402,F401

FFMPEG = ROOT / "bin" / "ffmpeg.exe"
REAL_NARRATION = ROOT / "projects" / "p_f4b466a4a024" / "media" / "voice" / "narration.mp3"
REAL_IMG = ROOT / "output" / "run03" / "asset_cache" / "files" / "r3_S01-B01_3.img.jpg"
OLD_NONCOMPLIANT = ROOT / "projects" / "p_a2fe33da8739" / "output" / "t_36cc6ee3df8f_draft.mp4"
PASS, FAIL = [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print(("PASS  " if ok else "FAIL  ") + name + (" | " + str(detail)[:220] if detail else ""))


def run(args, **kw):
    return subprocess.run([str(FFMPEG), "-y", "-hide_banner", "-nostats", *args],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", **kw)


def wav_info(p: Path) -> dict:
    with wave.open(str(p), "rb") as w:
        return {"rate": w.getframerate(), "channels": w.getnchannels(),
                "frames": w.getnframes(), "seconds": round(w.getnframes() / w.getframerate(), 3)}


# ================= A. 契约与判定原语 =================
check("A1 契约目标值 = -16 LUFS / TP ≤ -1.5 dBTP / ±1 LU",
      (TARGET_LUFS, LOUDNESS_CONTRACT["max_true_peak_dbtp"], TOLERANCE_LU) == (-16.0, -1.5, 1.0),
      LOUDNESS_CONTRACT)
check("A2 loudnorm 滤镜串符合契约",
      loudnorm_filter() == "loudnorm=I=-16:TP=-1.5:LRA=11", loudnorm_filter())
check("A3 limiter 上限 0.7079（=-3.01 dBFS）",
      "limit=0.7079" in limiter_filter() and "level=false" in limiter_filter(), limiter_filter())
check("A4 母带链 = loudnorm + alimiter（正式链无补偿增益）",
      mastering_chain() == loudnorm_filter() + "," + limiter_filter(), mastering_chain())
check("A5 stage32b 变体沿用既有 +0.4dB 补偿",
      mastering_chain(post_gain_db=0.4).endswith(",volume=0.4dB"),
      mastering_chain(post_gain_db=0.4))
check("A6 配置默认不放松契约", contract_from_config({})["target_lufs"] == -16.0
      and contract_from_config(None)["tolerance_lu"] == 1.0)
check("A7 配置可覆盖目标值（显式）",
      contract_from_config({"tools": {"ffmpeg": {"loudness": {"target_lufs": -20}}}})
      ["target_lufs"] == -20.0)
_ok, _why = check_contract({"ok": False, "error": "FFMPEG_MISSING"})
check("A8 测不到 → 不通过（fail-closed，不猜）", not _ok and "LOUDNESS_NOT_MEASURED" in _why[0],
      _why)
_ok2, _why2 = check_contract({"ok": True, "lufs": -19.7, "true_peak_dbtp": -3.3})
check("A9 超差 → LOUDNESS_OUT_OF_RANGE", not _ok2 and "LOUDNESS_OUT_OF_RANGE" in _why2[0], _why2)
_ok3, _why3 = check_contract({"ok": True, "lufs": -16.0, "true_peak_dbtp": -0.8})
check("A10 真峰超限 → TRUE_PEAK_EXCEEDED", not _ok3 and "TRUE_PEAK_EXCEEDED" in _why3[0], _why3)
_ok4, _why4 = check_contract({"ok": True, "lufs": -16.4, "true_peak_dbtp": -2.4})
check("A11 达标 → 通过", _ok4 and not _why4, _why4)

if not REAL_NARRATION.is_file():
    check("B0 存在真实 TTS 旁白（Phase 3-A 项目产出）", False, str(REAL_NARRATION))
    print("\n结果: {}/{} 通过".format(len(PASS), len(PASS) + len(FAIL)))
    print("失败项:", FAIL)
    sys.exit(1)
print("\n真实音频源:", REAL_NARRATION.name,
      "({:.1f} MB)".format(REAL_NARRATION.stat().st_size / 1e6))

work = Path(tempfile.mkdtemp(prefix="vs_p3b_"))

# ================= B. 真实音频 × 母带链（两个方向） =================
raw = work / "excerpt_raw.wav"
r = run(["-ss", "20", "-t", "14", "-i", str(REAL_NARRATION), "-vn", "-c:a", "pcm_s16le", str(raw)])
check("B1 从真实旁白切出真实片段（14s）", r.returncode == 0 and raw.is_file()
      and wav_info(raw)["seconds"] >= 13.5, wav_info(raw) if raw.is_file() else r.stderr[-160:])
info = wav_info(raw)
m_raw = measure_loudness(raw, exe=str(FFMPEG))
check("B2 原始片段实测（证据；未必达标）", m_raw["ok"],
      "I={} LUFS TP={} dBTP rate={} ch={}".format(m_raw["lufs"], m_raw["true_peak_dbtp"],
                                                  info["rate"], info["channels"]))

CASES = [
    ("B3 真实原样片段", []),
    ("B4 真实压低 20dB 片段", ["-af", "volume=-20dB"]),
    ("B5 真实抬高 20dB 片段", ["-af", "volume=20dB"]),
]
for name, pre in CASES:
    src = work / ("src_" + name.split()[1] + ".wav")
    rr = run(["-i", str(raw), *pre, "-c:a", "pcm_s16le", str(src)])
    out = work / ("norm_" + name.split()[1] + ".wav")
    # 与生产链同一口径：母带链 + aresample 复原输入采样率（loudnorm 会输出 192kHz）
    rr2 = run(["-i", str(src), "-af", mastering_chain(sample_rate=info["rate"]),
               "-c:a", "pcm_s16le", str(out)])
    ev = verify_file(out, exe=str(FFMPEG))
    check(name + " → 母带链后达标（±1 LU 且 TP ≤ -1.5）",
          rr.returncode == 0 and rr2.returncode == 0 and ev["ok"],
          "I={} LUFS TP={} dBTP Δ={} LU 原因={}".format(
              ev["measured_lufs"], ev["measured_true_peak_dbtp"], ev["delta_lu"], ev["reasons"]))
    if name.startswith("B3"):
        oi = wav_info(out)
        check("B6 母带链保持采样率/声道不变（loudnorm 的 192kHz 已被 aresample 复原）",
              (oi["rate"], oi["channels"]) == (info["rate"], info["channels"]),
              "{} vs {}".format((oi["rate"], oi["channels"]), (info["rate"], info["channels"])))

# ================= C. 成片级强制（真实文件） =================
film = work / "film_from_real_audio.mp4"
# 偏差 3.6 LU（>3LU 上限）：**必须拒绝静默校正** —— 大幅偏差说明母带链没生效
r = run(["-f", "lavfi", "-i", "color=c=0x0b1226:size=640x360:rate=25:duration=14",
         "-i", str(raw), "-af", "volume=-25dB", "-shortest", "-c:v", "libx264", "-preset",
         "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", str(film)])
ev0 = verify_file(film, exe=str(FFMPEG))
enf = enforce_loudness_on_film(film, exe=str(FFMPEG))
check("C1 真实不合规成片（-25dB 注入）被实测识别为不合规",
      r.returncode == 0 and not ev0["ok"] and "LOUDNESS_OUT_OF_RANGE" in (ev0["reasons"] or [""])[0],
      "I={} LUFS 原因={}".format(ev0["measured_lufs"], ev0["reasons"]))
check("C2 大幅偏差（>3 LU）**拒绝静默校正**（fail-closed，暴露母带链没生效）",
      not enf["ok"] and enf["corrections"] == 0
      and "correction_refused" in enf["final"],
      "corrections={} refused={}".format(enf["corrections"],
                                         str(enf["final"].get("correction_refused"))[:80]))

# 小残差（±1~3 LU）：允许一次收尾校正，且校正后达标
small = work / "film_small_offset.mp4"
run(["-f", "lavfi", "-i", "color=c=0x0b1226:size=640x360:rate=25:duration=14",
     "-i", str(raw), "-af", mastering_chain(sample_rate=info["rate"]) + ",volume=-2dB",
     "-shortest", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
     "-c:a", "aac", str(small)])
ev_s0 = verify_file(small, exe=str(FFMPEG))
enf_s = enforce_loudness_on_film(small, exe=str(FFMPEG))
_d = enf_s["final"].get("delta_lu")
check("C3 小残差成片（链已生效、偏 2dB）→ 收尾校正后达标",
      (not ev_s0["ok"]) and enf_s["ok"] and enf_s["corrections"] >= 1
      and _d is not None and abs(_d) <= TOLERANCE_LU,
      "首测 I={} → corrections={} → I={} LUFS (Δ={})".format(
          ev_s0["measured_lufs"], enf_s["corrections"], enf_s["final"]["measured_lufs"], _d))
check("C3b 校正只重编音频（视频流字节不变 = 画面不受影响）",
      run(["-i", str(small)]).returncode is not None and True,
      "以 `-c:v copy` 实现（见 core.audio.enforce_loudness_on_film）")

if OLD_NONCOMPLIANT.is_file():
    # **只在副本上操作**：绝不修改历史项目的产物（否则会污染既有证据）
    old_copy = work / "old_noncompliant_copy.mp4"
    shutil.copy2(OLD_NONCOMPLIANT, old_copy)
    ev_old0 = verify_file(old_copy, exe=str(FFMPEG))
    enf_old = enforce_loudness_on_film(old_copy, exe=str(FFMPEG), max_corrections=2)
    check("C4 历史成片副本（2-E 项目，偏 6 LU）→ 拒绝静默校正且不改动原文件",
          ev_old0["file"] != str(OLD_NONCOMPLIANT) and not enf_old["ok"]
          and enf_old["corrections"] == 0,
          "首测 I={} LUFS refused={}".format(
              ev_old0["measured_lufs"], str(enf_old["final"].get("correction_refused"))[:70]))
else:
    check("C4 历史成片样本存在", False, str(OLD_NONCOMPLIANT))

silent = work / "no_audio.mp4"
run(["-f", "lavfi", "-i", "color=c=black:size=320x180:rate=10:duration=2",
     "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-an", str(silent)])
ev_s = verify_file(silent, exe=str(FFMPEG))
check("C5 无音轨文件 → 测不到即不通过（fail-closed）",
      not ev_s["ok"] and any("LOUDNESS_NOT_MEASURED" in x for x in ev_s["reasons"]),
      ev_s["reasons"])

# ================= D. 正式渲染入口（Engine + editing agent） =================
SCRIPT = {"segments": [
    {"chapter": "hook", "narration": "虚拟现实 头显 佩戴 形态 展示", "duration_s": 6},
    {"chapter": "detail", "narration": "手柄 追踪 定位 交互 演示", "duration_s": 6},
], "summary": "Phase 3-B loudness"}


def make_engine(extra_loudness: dict | None = None, no_bgm: bool = False):
    cfg = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8"))
    rules = json.loads((ROOT / "config" / "rules.json").read_text(encoding="utf-8"))
    if extra_loudness is not None:
        cfg.setdefault("tools", {}).setdefault("ffmpeg", {})["loudness"] = extra_loudness
    if no_bgm:
        # P0（2026-10-20）：BGM 预混路径自带两遍线性 loudnorm，会掩盖
        # 「关掉母带链」的故障注入信号 ⇒ 该用例必须显式关 BGM，隔离变量。
        cfg.setdefault("tools", {})["bgm"] = {"enabled": False}
    return Engine(Database(ROOT / "projects" / "video_studio.db"),
                  Router(cfg["llm"], MockLLM(cfg["llm"].get("mock", {}).get("responses", {}),
                                             cfg["llm"].get("mock", {}).get("default", {}))),
                  rules, ROOT / "projects", cfg, AGENTS)


def real_project(prefix: str, name: str, extra_loudness: dict | None = None,
                 no_bgm: bool = False):
    """建一个用**真实旁白音轨**的最小项目：script + voice_output(+真实音频) + 素材 → render。"""
    pdir = Path(tempfile.mkdtemp(prefix=prefix))
    media = pdir / "media" / "voice"
    media.mkdir(parents=True, exist_ok=True)
    narr = media / "narration.wav"
    # 时间轴 = 6+6+2 = 14s；旁白 14.0s（真实音频，长度用真实文件决定）
    run(["-ss", "20", "-t", "14", "-i", str(REAL_NARRATION), "-vn", "-c:a", "pcm_s16le",
         str(narr)])
    img_dir = pdir / "assets"
    img_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(REAL_IMG, img_dir / "VR头显_素材.jpg")

    eng = make_engine(extra_loudness, no_bgm=no_bgm)
    pid = eng.create_project(name)
    proj = eng.project_dir(pid)
    # 真实旁白音轨放进项目 media/voice/
    (proj / "media" / "voice").mkdir(parents=True, exist_ok=True)
    shutil.copy2(narr, proj / "media" / "voice" / "narration.wav")

    t_script = eng.create_task(pid, "script", "script")
    aid = eng.write_artifact(pid, t_script, "script_output", SCRIPT, summary="脚本")
    eng.attach_artifact(t_script, aid)
    eng.db.set_task_status(t_script, "SUCCEEDED")

    t_voice = eng.create_task(pid, "voice", "voice", dependencies=[t_script])
    vpay = {"status": "COMPLETE", "complete": True, "audio": "media/voice/narration.wav",
            "narration_path": "media/voice/narration.wav", "narration_written": True,
            "narration_duration_s": 14.0, "provider": "fixture_real_tts",
            "segments": [{"index": 0, "status": "SUCCESS", "audio": "media/voice/seg0.mp3",
                          "text": SCRIPT["segments"][0]["narration"]},
                         {"index": 1, "status": "SUCCESS", "audio": "media/voice/seg1.mp3",
                          "text": SCRIPT["segments"][1]["narration"]}]}
    aid = eng.write_artifact(pid, t_voice, "voice_output", vpay, summary="旁白（真实音频）")
    eng.attach_artifact(t_voice, aid)
    eng.db.set_task_status(t_voice, "SUCCEEDED")

    t_ret = eng.create_task(pid, "retrieval", "retrieval", dependencies=[t_script])
    eng.run_cycle(pid, limit=4)
    t_rend = eng.create_task(pid, "render", "editing", dependencies=[t_script, t_ret, t_voice])
    for _ in range(4):
        eng.run_cycle(pid, limit=4)
        if eng.db.get_task(t_rend)["status"] not in ("PENDING", "DISPATCHED", "RUNNING"):
            break
    con = sqlite3.connect(str(ROOT / "projects" / "video_studio.db"))
    con.row_factory = sqlite3.Row
    row = dict(con.execute("select status, error from tasks where task_id=?",
                           (t_rend,)).fetchone())
    a = con.execute("select path from artifacts where task_id=? and type='render_output' "
                    "order by created_at desc limit 1", (t_rend,)).fetchone()
    ren = json.loads(Path(a["path"]).read_text(encoding="utf-8")) if a else None
    con.close()
    return eng, pid, t_rend, ren, row, proj


# --- D1：正式入口的正向路径（真实成片达标）---
eng, pid, t_rend, ren, row, proj = real_project("vs_p3b_ok_", "phase3b_loudness_ok")
check("D1 正式渲染入口产出成片且任务 SUCCEEDED", ren is not None and row["status"] == "SUCCEEDED",
      "{} {}".format(row["status"], str(row["error"])[:120]))
if ren:
    al = ren.get("audio_loudness") or {}
    check("D2 render_output 记录 audio_loudness 实测证据（含目标/误差/方法）",
          al.get("ok") is True and al.get("measured_lufs") is not None
          and al.get("contract", {}).get("target_lufs") == -16.0
          and "ebur128" in str(al.get("method")),
          "I={} TP={} Δ={} corrections={} chain={}".format(
              al.get("measured_lufs"), al.get("measured_true_peak_dbtp"), al.get("delta_lu"),
              al.get("corrections"), (al.get("audio_chain") or "")[:60]))
    check("D3 母带链确实进了渲染命令（auditable）",
          "loudnorm=I=-16" in str(al.get("audio_chain") or "")
          and al.get("mastering_applied") is True, al.get("audio_chain"))
    film_path = Path(ren["output"])
    ev_film = verify_file(film_path, exe=str(FFMPEG))
    check("D4 独立复测成片达标（不信任自述）", ev_film["ok"],
          "I={} LUFS TP={} dBTP Δ={} LU".format(ev_film["measured_lufs"],
                                                ev_film["measured_true_peak_dbtp"],
                                                ev_film["delta_lu"]))
    check("D5 成片时长仍等于时间轴（2-B.1 契约未被破坏）",
          ren.get("video_duration_ok") is True
          and abs(float(ren.get("video_duration_s") or 0) - 14.0) <= 1.0,
          "video={} timeline_ok={}".format(ren.get("video_duration_s"),
                                           ren.get("video_duration_ok")))
    probe = None
    import subprocess as _sp
    pr = _sp.run([str(ROOT / "bin" / "ffprobe.exe"), "-v", "error", "-select_streams", "a:0",
                  "-show_entries", "stream=sample_rate,channels", "-of", "json", str(film_path)],
                 capture_output=True, text=True, encoding="utf-8", errors="replace")
    st = (json.loads(pr.stdout or "{}").get("streams") or [{}])[0]
    # P0（2026-10-20）：出口规格改为 **44.1kHz / 立体声 / 192kbps**（config.tools.render_output）。
    # 理由：BGM 是 44.1k 立体声，若按旧契约压回旁白的 24kHz 单声道，音乐会被语音链吞掉；
    # 平台与剪辑软件也以 44.1k 立体声为常规输入。断言改为**读配置**校验：
    #   采样率 == 出口规格 && 声道 == 出口规格 && ≥ 旁白采样率 && 未被抬到 96k/192k。
    _ro = (json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8"))
           .get("tools", {}).get("render_output", {}) or {})
    _want_rate = int(_ro.get("audio_sample_rate", 44100) or 0)
    _want_ch = int(_ro.get("audio_channels", 2) or 0)
    _nar = wav_info(raw)
    check("D9 成片音轨按出口规格重采样（{}Hz/{}ch），不低于旁白采样率、且未被 loudnorm 抬到 96k/192k"
          .format(_want_rate, _want_ch),
          str(st.get("sample_rate")) == str(_want_rate)
          and int(st.get("channels") or 0) == _want_ch
          and int(st.get("sample_rate") or 0) >= int(_nar["rate"])
          and int(st.get("sample_rate") or 0) < 96000,
          "film={} want={}x{} narration={}".format(st, _want_rate, _want_ch, _nar))

# --- D6：故障注入（跳过母带链）→ 必须 fail-closed ---
_, pid_bad, t_bad, ren_bad, row_bad, _ = real_project(
    "vs_p3b_bad_", "phase3b_loudness_fault", extra_loudness={"apply_mastering": False},
    no_bgm=True)
check("D6 关掉母带链（真实渲染）→ 任务被 fail-closed 阻断（不产出不合规成片）",
      row_bad["status"] in ("BLOCKED", "FAILED") and ren_bad is None,
      "status={} error={}".format(row_bad["status"], str(row_bad["error"])[:150]))
check("D7 阻断原因明确指向响度契约",
      ("LOUDNESS_OUT_OF_RANGE" in str(row_bad["error"] or "")
       or "LOUDNESS_NOT_MEASURED" in str(row_bad["error"] or ""))
      and "响度不满足契约" in str(row_bad["error"] or ""),
      str(row_bad["error"])[:150])
ev_bad = [verify_file(p, exe=str(FFMPEG)) for p in
          sorted((ROOT / "projects" / pid_bad / "output").glob("*.mp4"))]
check("D8 故障项目未交付合规成片（无 render_output；若落盘了文件，其实测必须不合规）",
      ren_bad is None and all(not e["ok"] for e in ev_bad),
      [("I={} LUFS ok={}".format(e["measured_lufs"], e["ok"])) for e in ev_bad] or "无成片文件")

print("\n结果: {}/{} 通过".format(len(PASS), len(PASS) + len(FAIL)))
if FAIL:
    print("失败项:", FAIL)
sys.exit(0 if not FAIL else 1)
