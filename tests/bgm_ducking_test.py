"""4.x Phase 4-F 单测：可选 BGM + 旁白 ducking（**全离线、确定性**）。

覆盖授权要求的 10 条路径 + 验收项：
  A. BGM 关闭（默认）：设置缺省关闭、既有音频链/分支未变、渲染证据 applied=False
  B. ducking 规则与参数：时间段推导、增益曲线（纯函数）、ffmpeg 表达式（可复算）
  C. BGM 校验：缺失 / 空文件 / sha256 不符 / 非音频 / 解码失败 / 过短 / 静音 / 异常响度 /
     来源不明 / 许可缺失·不明·受限 / 缺 attribution
  D. 引擎级渲染：BGM 关闭、BGM 开启（过长截断、过短补静音）、静音被拒、受限许可被拒
  E. ducking 波形/响度证据：旁白窗口 vs 旁白之外实测差值 = duck 深度；旁白电平未被 BGM 抬高
  F. 契约：ffprobe（h264+aac）、旁白完整性闸门、最终响度 -16±1 / TP ≤ -1.5、时长=时间轴
  G. attribution / credits 与最终音频配置一致（开启才写 BGM 段）
  H. fail-closed 不污染：被拒时无成片 / 无 render_output / 台账零新增

用法：python tests/bgm_ducking_test.py
"""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.core import bgm as core_bgm  # noqa: E402
from video_studio.core import audio as core_audio  # noqa: E402

FFMPEG = ROOT / "bin" / "ffmpeg.exe"
FFPROBE = ROOT / "bin" / "ffprobe.exe"
REAL_JPG = ROOT / "output" / "run03" / "asset_cache" / "files" / "r3_S01-B01_3.img.jpg"
PASS, FAIL = [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print(("PASS  " if ok else "FAIL  ") + name + (" | " + str(detail)[:230] if detail else ""))


def run_ff(args, timeout=600):
    return subprocess.run([str(FFMPEG), "-y", "-hide_banner", "-nostats", *args],
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=timeout)


def mean_volume_db(path, ss, dur):
    """窗口平均电平（dB）——用 ffmpeg volumedetect 实测（与响度契约同一 ffmpeg）。"""
    r = run_ff(["-ss", str(ss), "-t", str(dur), "-i", str(path), "-af", "volumedetect",
                "-f", "null", "-"])
    for line in (r.stderr or "").splitlines():
        if "mean_volume:" in line:
            return float(line.split("mean_volume:")[1].split("dB")[0].strip())
    return None


WORK = Path(tempfile.mkdtemp(prefix="vs_4f_"))
(BGM_OK, BGM_SHORT, BGM_LONG, BGM_SILENT, BGM_LOUD) = (
    WORK / "bgm_ok.wav", WORK / "bgm_short.wav", WORK / "bgm_long.wav",
    WORK / "bgm_silent.wav", WORK / "bgm_loud.wav")
BGM_CORRUPT = WORK / "bgm_corrupt.mp3"
NARR = WORK / "narration.wav"


def build_fixtures():
    # 6-A/M2：旁白必须覆盖时间轴（14 s）的 ≥90%，否则成片会有长尾静音 —— 那正是 M2 授权点名的
    # 「短旁白 / 成片静音」违约类（实测同类历史成片尾静音 13.26 s/78%）。故旁白改为
    # 6.5s(440Hz) + 6.5s(660Hz) = 13.0s，与 voice 产物逐段时长一致，并在片尾留 1 s 释放窗
    # 供 ducking 恢复断言（E1/E4）使用。
    run_ff(["-f", "lavfi", "-t", "6.5", "-i", "sine=frequency=440:sample_rate=24000",
            "-af", "volume=-12dB", "-c:a", "pcm_s16le", str(WORK / "n0.wav")])
    run_ff(["-f", "lavfi", "-t", "6.5", "-i", "sine=frequency=660:sample_rate=24000",
            "-af", "volume=-12dB", "-c:a", "pcm_s16le", str(WORK / "n1.wav")])
    (WORK / "nlist.txt").write_text("file '{}'\nfile '{}'\n".format(
        (WORK / "n0.wav").as_posix(), (WORK / "n1.wav").as_posix()), encoding="utf-8")
    run_ff(["-f", "concat", "-safe", "0", "-i", str(WORK / "nlist.txt"),
            "-c:a", "pcm_s16le", str(NARR)])
    # BGM：不同长度/电平；一首 20s 正常、2s 过短、30s 过长、10s 静音、10s 异常响度
    # 注意：ffmpeg `sine` 源本身约 -22 LUFS（不是满刻度），故用 volume 调整到目标档位
    run_ff(["-f", "lavfi", "-t", "20", "-i", "sine=frequency=220:sample_rate=44100",
            "-af", "volume=-10dB", "-c:a", "pcm_s16le", str(BGM_OK)])
    run_ff(["-f", "lavfi", "-t", "2", "-i", "sine=frequency=220:sample_rate=44100",
            "-af", "volume=-10dB", "-c:a", "pcm_s16le", str(BGM_SHORT)])
    run_ff(["-f", "lavfi", "-t", "30", "-i", "sine=frequency=220:sample_rate=44100",
            "-af", "volume=-10dB", "-c:a", "pcm_s16le", str(BGM_LONG)])
    run_ff(["-f", "lavfi", "-t", "10", "-i", "anullsrc=r=44100:cl=mono",
            "-c:a", "pcm_s16le", str(BGM_SILENT)])
    run_ff(["-f", "lavfi", "-t", "10", "-i", "sine=frequency=220:sample_rate=44100",
            "-af", "volume=+16dB", "-c:a", "pcm_s16le", str(BGM_LOUD)])
    BGM_CORRUPT.write_bytes(b"\x00\x01\x02\x03" * 4096)


build_fixtures()
BGM_LIC = {"provider": "local_bgm", "source_id": "test_tone_v1", "license": "CC BY-SA 4.0",
           "attribution": "Test tone（自生成，仅用于测试；非真实音乐作品）"}


def st(**kw):
    base = {"enabled": True, **BGM_LIC, "ramp_ms": 250, "bed_db": -20.0, "duck_db": -26.0}
    base.update(kw)
    return {**core_bgm.BGM_DEFAULTS, **base}


# ============ A. 默认关闭 ============
print("== A. BGM 关闭（默认行为） ==")
default = core_bgm.bgm_settings({})
default2 = core_bgm.bgm_settings({"tools": {}})
check("A1 缺省配置 = 关闭（enabled=False），且不产生任何 BGM 输入/滤镜",
      default["enabled"] is False and default["_source"] == "default(disabled)"
      and default2["enabled"] is False, {"A": default["_source"], "B": default2["_source"]})
check("A2 duck/bed 默认参数为负增益（旁白优先的前提）",
      default["bed_db"] == -20.0 and default["duck_db"] == -26.0
      and default["duck_db"] <= default["bed_db"], default)
bad_par = core_bgm.bgm_settings({"tools": {"bgm": {"enabled": True, "bed_db": -10, "duck_db": -4,
                                                  "ramp_ms": "x"}}})
check("A3 非法参数不放松规则：duck>bed 时按 bed 收敛、非法 ramp 回退默认",
      bad_par["duck_db"] == -10.0 and bad_par["ramp_ms"] == core_bgm.BGM_DEFAULTS["ramp_ms"]
      and bad_par["_notes"], bad_par["_notes"])
agent_src = (ROOT / "src" / "video_studio" / "agents" / "editing" / "agent.py").read_text(
    encoding="utf-8")
check("A4 渲染侧仅在 BGM 开启时才做预混（关闭走原分支，逐字不变）",
      'if _bgm_settings.get("enabled"):' in agent_src
      and "narration_audio_render = narration_audio" in agent_src
      and 'bgm: dict | None = None' in agent_src)
audio_src = (ROOT / "src" / "video_studio" / "core" / "audio.py").read_text(encoding="utf-8")
check("A5 3-B 母带链与响度契约文件未被改动（无 BGM 相关改动）",
      "-16" in audio_src and "MAX_TRUE_PEAK_DBTP = -1.5" in audio_src and "bgm" not in audio_src)

# ============ B. ducking 规则 ============
print("== B. ducking 规则（确定性、可复算） ==")
VOICE = {"complete": True, "segments": [
    {"index": 0, "status": "SUCCESS", "audio": "media/voice/seg_00.wav", "duration_s": 6.5},
    {"index": 1, "status": "SUCCESS", "audio": "media/voice/seg_01.wav", "duration_s": 6.5}]}
IV = core_bgm.narration_intervals(VOICE)
check("B1 旁白时间段由逐段真实时长累加（不猜、不四舍五入到整秒）",
      IV == [{"index": 0, "start_s": 0.0, "end_s": 6.5, "duration_s": 6.5},
             {"index": 1, "start_s": 6.5, "end_s": 13.0, "duration_s": 6.5}], IV)
g = lambda t: core_bgm.gain_db_at(t, IV, bed_db=-20.0, duck_db=-26.0, ramp_s=0.25)
check("B2 旁白期间 = duck_db，旁白之外 = bed_db",
      g(1.0) == -26.0 and g(7.0) == -26.0 and g(13.5) == -20.0,
      {"t1": g(1.0), "t7": g(7.0), "t13.5": g(13.5)})
check("B3 边界线性过渡：提前 ramp 进入 duck、结束后 ramp 恢复",
      g(12.9) == -26.0 and abs(g(13.125) - (-23.0)) < 0.01 and g(13.25) == -20.0
      and g(0.0) == -26.0,                       # 旁白从 0 开始 → 开头即处于 duck（提前段在 t<0）
      {"t12.9": g(12.9), "t13.125": g(13.125), "t13.25": g(13.25), "t0.0": g(0.0)})
IV2 = [{"index": 0, "start_s": 6.0, "end_s": 8.0, "duration_s": 2.0}]
g2 = lambda t: core_bgm.gain_db_at(t, IV2, bed_db=-20.0, duck_db=-26.0, ramp_s=0.25)
check("B3b 中段旁白：t=5.75 尚未 duck（-20）、t=5.875 半档（-23）、t=6.0 全 duck（-26）",
      g2(5.75) == -20.0 and abs(g2(5.875) - (-23.0)) < 0.01 and g2(6.0) == -26.0,
      {"t5.75": g2(5.75), "t5.875": g2(5.875), "t6.0": g2(6.0)})
check("B4 相邻/重叠时间段合并 → 句中不会抬起",
      core_bgm.narration_intervals({"segments": [
          {"index": 0, "status": "SUCCESS", "duration_s": 2.0},
          {"index": 1, "status": "SUCCESS", "duration_s": 2.0}]})[1]["start_s"] == 2.0
      and core_bgm.duck_amount_at(2.0, core_bgm.narration_intervals({"segments": [
          {"index": 0, "status": "SUCCESS", "duration_s": 2.0},
          {"index": 1, "status": "SUCCESS", "duration_s": 2.0}]}), 0.25) == 1.0)
expr = core_bgm.volume_expression(IV, bed_db=-20.0, duck_db=-26.0, ramp_s=0.25)
check("B5 ffmpeg 增益表达式可复算（同参数同字符串，含 duck 差值 -6）",
      expr == core_bgm.volume_expression(IV, bed_db=-20.0, duck_db=-26.0, ramp_s=0.25)
      and "(-6)" in expr and "pow(10," in expr
      and ("max(" in expr or "if(lt(t," in expr), expr[:120])
check("B6 无旁白时间段 → 恒定 bed_db（不做 ducking，但仍是显式规则）",
      "-20" in core_bgm.volume_expression([], bed_db=-20.0, duck_db=-26.0, ramp_s=0.25)
      and "max(" not in core_bgm.volume_expression([], bed_db=-20.0, duck_db=-26.0, ramp_s=0.25))
mix = core_bgm.mix_filters(narration_label="0:a", bgm_label="1:a", master_chain="loudnorm=I=-16",
                           intervals=IV, settings=st(), total_s=12.0, bgm_duration_s=30.0)
check("B7 混音片段：amix normalize=0（不改变旁白电平）+ atrim（过长截断）+ apad（过短补静音）",
      "amix=inputs=2:duration=first:normalize=0" in " ".join(mix["filters"])
      and "atrim=0:12.000" in " ".join(mix["filters"])
      and "apad" in " ".join(mix["filters"])
      and mix["evidence"]["trimmed_to_film"] is True, mix["filters"])
check("B8 证据块：旁白优先 + duck 窗口 + 规则文本齐全",
      mix["evidence"]["narration_priority"] is True and mix["evidence"]["duck_delta_db"] == -6.0
      and mix["evidence"]["duck_windows"] == [[0.0, 6.75], [6.25, 13.25]]
      and "旁白" in mix["evidence"]["rule"], mix["evidence"]["duck_windows"])

# ============ C. BGM 校验（十类） ============
print("== C. BGM 校验（来源/字节/音频/响度/许可/归属） ==")
ctx = None


def v(path, **kw):
    return core_bgm.verify_bgm(path, st(**kw), ctx=ctx, config={"tools": {"ffmpeg": {
        "path": str(FFMPEG), "ffprobe": str(FFPROBE)}}})


r_ok = v(BGM_OK)
check("C1 合规 BGM：通过校验并给出 sha256/时长/响度/许可类别/归属",
      r_ok["ok"] and r_ok["license_class"] == "FREE_ATTRIBUTION"
      and r_ok["license_cleared"] is True and len(r_ok["sha256"]) == 64
      and r_ok["duration_s"] and r_ok["lufs"] is not None,
      {k: r_ok[k] for k in ("ok", "code", "license_class", "duration_s", "lufs")})
check("C2 未配置来源（enabled 但无 source）→ BGM_NOT_CONFIGURED",
      v(None)["code"] == "BGM_NOT_CONFIGURED", v(None)["code"])
check("C3 文件缺失 → BGM_FILE_MISSING",
      v(WORK / "nope.wav")["code"] == "BGM_FILE_MISSING")
check("C4 sha256 不符 → BGM_HASH_MISMATCH（不接受被替换的字节）",
      v(BGM_OK, sha256="deadbeef")["code"] == "BGM_HASH_MISMATCH")
check("C5 非音频文件 → BGM_NOT_AUDIO",
      v(BGM_CORRUPT)["code"] in ("BGM_NOT_AUDIO", "BGM_DECODE_FAILED"), v(BGM_CORRUPT)["code"])
check("C6 静音 BGM → BGM_SILENT（拒绝，不静默当作『没有 BGM』处理）",
      v(BGM_SILENT)["code"] == "BGM_SILENT", {"code": v(BGM_SILENT)["code"],
                                              "lufs": v(BGM_SILENT)["lufs"]})
check("C7 异常响度（满电平）→ BGM_ABNORMAL_LOUDNESS",
      v(BGM_LOUD)["code"] == "BGM_ABNORMAL_LOUDNESS",
      {"code": v(BGM_LOUD)["code"], "lufs": v(BGM_LOUD)["lufs"]})
check("C8 过短 BGM 仍可通过校验（由混音侧补静音，并如实记录）",
      v(BGM_SHORT)["ok"] is True and v(BGM_SHORT)["duration_s"] < 3.0,
      {"ok": v(BGM_SHORT)["ok"], "duration_s": v(BGM_SHORT)["duration_s"]})
check("C9 来源不明（无 provider/source_id）→ BGM_SOURCE_UNKNOWN",
      v(BGM_OK, provider=None, source_id=None)["code"] == "BGM_SOURCE_UNKNOWN")
for lic, want in ((None, "BGM_LICENSE_MISSING"), ("unknown", "BGM_LICENSE_UNCLEAR"),
                  ("fair use", "BGM_LICENSE_RESTRICTED")):
    rr = v(BGM_OK, license=lic)
    check("C10 许可 {} → {}（与素材门禁同口径，绝不放行）".format(lic, want),
          rr["code"] == want, {"code": rr["code"], "class": rr["license_class"]})
check("C11 许可合规但缺 attribution → BGM_ATTRIBUTION_MISSING",
      v(BGM_OK, attribution=None)["code"] == "BGM_ATTRIBUTION_MISSING")
check("C12 所有拒绝码都在登记表内（可解释、可检索）",
      all(v(BGM_OK, **kw)["code"] in core_bgm.BGM_ERRORS for kw in
          ({"license": None}, {"attribution": None}, {"provider": None, "source_id": None},
           {"sha256": "x"})) and
      all(c in core_bgm.BGM_ERRORS for c in
          ("BGM_NOT_CONFIGURED", "BGM_SILENT", "BGM_ABNORMAL_LOUDNESS", "BGM_MIX_FAILED")))

# ============ D–H. 引擎级渲染 ============
print("== D. 引擎级渲染（关闭 / 过长 / 过短 / 静音被拒 / 受限许可被拒） ==")
from video_studio.agents.base import AGENTS  # noqa: E402
from video_studio.core.engine import Engine  # noqa: E402
from video_studio.db.schema import Database  # noqa: E402
from video_studio.llm.router import MockLLM, Router  # noqa: E402
from video_studio.tools.base import ToolContext  # noqa: E402
from video_studio.agents.retrieval.agent import kw_tokens  # noqa: E402
from video_studio.tools.material_provider import MaterialQuery  # noqa: E402

import video_studio.agents.asset.agent  # noqa: E402,F401
import video_studio.agents.editing.agent  # noqa: E402,F401
import video_studio.agents.retrieval.agent  # noqa: E402,F401
import video_studio.agents.script.agent  # noqa: E402,F401
import video_studio.agents.voice.agent  # noqa: E402,F401

WS = Path(tempfile.mkdtemp(prefix="vs_4f_engine_"))
CAT = WS / "catalog"
CAT.mkdir(parents=True, exist_ok=True)
IMG1, IMG2 = WS / "vr_front.jpg", WS / "vr_side.jpg"
shutil.copy2(REAL_JPG, IMG1)
shutil.copy2(REAL_JPG, IMG2)
(CAT / "catalogue.json").write_text(json.dumps({"items": [
    {"source_id": "s_front", "name": "VR头显_正面_展示.jpg", "file": str(IMG1),
     "license": "CC BY-SA 4.0", "attribution": "T / CC BY-SA"},
    {"source_id": "s_side", "name": "VR头显_侧面_展示.jpg", "file": str(IMG2),
     "license": "CC BY-SA 4.0", "attribution": "T / CC BY-SA"},
]}, ensure_ascii=False), encoding="utf-8")
CONFIG = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8"))
RULES = json.loads((ROOT / "config" / "rules.json").read_text(encoding="utf-8"))
SCRIPT = {"segments": [{"chapter": "s1", "narration": "虚拟现实头显的正面展示", "duration_s": 6},
                       {"chapter": "s2", "narration": "头显的侧面与镜片细节", "duration_s": 6}],
          "summary": "4-F BGM ducking"}


def build_engine(label, bgm_cfg):
    cfg = json.loads(json.dumps(CONFIG))
    cfg["tools"]["material"] = {"provider": "local_catalog", "catalog": str(CAT), "timeout_s": 5,
                               "license_required": True}
    cfg["tools"]["retrieval"] = {"scoring": "v2", "query_expansion": True}
    if bgm_cfg is not None:
        cfg["tools"]["bgm"] = bgm_cfg
    db = Database(WS / "state_{}.db".format(label))
    eng = Engine(db, Router(cfg["llm"], MockLLM(cfg["llm"].get("mock", {}).get("responses", {}),
                                               cfg["llm"].get("mock", {}).get("default", {}))),
                 RULES, WS / "projects", cfg, AGENTS)
    return eng, db


def prepare_project(eng, label):
    pid = eng.create_project("4-F {}".format(label))
    pdir = eng.project_dir(pid)
    (pdir / "media" / "voice").mkdir(parents=True, exist_ok=True)
    shutil.copy2(NARR, pdir / "media" / "voice" / "narration.wav")
    for i in (0, 1):
        shutil.copy2(WORK / "n{}.wav".format(i), pdir / "media" / "voice" / "seg_0{}.wav".format(i))
    t_script = eng.create_task(pid, "script", "script")
    aid = eng.write_artifact(pid, t_script, "script_output", SCRIPT, summary="脚本")
    eng.attach_artifact(t_script, aid)
    eng.db.set_task_status(t_script, "SUCCEEDED")
    t_voice = eng.create_task(pid, "voice", "voice", dependencies=[t_script])
    voice_payload = {"complete": True, "audio": "media/voice/narration.wav",
                     "status": "COMPLETE", "expected_segments": 2, "successful_segments": 2,
                     "failed_segments": [], "narration_duration_s": 13.0, "duration_ok": True,
                     "segments": [
                         {"index": 0, "audio": "media/voice/seg_00.wav", "status": "SUCCESS",
                          "reused": False, "attempts": 1, "bytes": 312044,
                          "duration_s": 6.5, "text_sha256": "t0"},
                         {"index": 1, "audio": "media/voice/seg_01.wav", "status": "SUCCESS",
                          "reused": False, "attempts": 1, "bytes": 312044,
                          "duration_s": 6.5, "text_sha256": "t1"}]}
    av = eng.write_artifact(pid, t_voice, "voice_output", voice_payload, summary="旁白 2 段")
    eng.attach_artifact(t_voice, av)
    eng.db.set_task_status(t_voice, "SUCCEEDED")
    ctx = ToolContext(role="retrieval", project_id=pid, project_dir=pdir, db=eng.db,
                      config=eng.config)
    t_ret = eng.create_task(pid, "retrieval", "retrieval", dependencies=[t_script])
    eng.run_cycle(pid, limit=4)
    r_art = eng.db.conn.execute("select path from artifacts where task_id=? and "
                                "type='retrieval_candidates' order by created_at desc limit 1",
                                (t_ret,)).fetchone()
    return pid, pdir, t_script, t_voice, t_ret, (Path(r_art["path"]) if r_art else None), ctx


def render(eng, pid, deps):
    t_rend = eng.create_task(pid, "render", "editing", dependencies=list(deps))
    for _ in range(4):
        eng.run_cycle(pid, limit=5)
        if eng.db.get_task(t_rend)["status"] not in ("PENDING", "DISPATCHED", "RUNNING"):
            break
    t = eng.db.get_task(t_rend)
    films = sorted((eng.project_dir(pid) / "output").glob("*.mp4"))
    row = eng.db.conn.execute("select path from artifacts where task_id=? and type='render_output'"
                              " order by created_at desc limit 1", (t_rend,)).fetchone()
    data = json.loads(Path(row["path"]).read_text(encoding="utf-8")) if row else None
    attrib = eng.db.conn.execute("select path from artifacts where project_id=? and "
                                 "type='attribution' order by created_at desc limit 1",
                                 (pid,)).fetchone()
    return t, films, data, (json.loads(Path(attrib["path"]).read_text(encoding="utf-8"))
                            if attrib else None)


results = {}

# D1 BGM 关闭（默认）
eng, db = build_engine("off", None)
pid, pdir, t_s, t_v, t_r, ret_art, ctx = prepare_project(eng, "off")
t, films, data, attrib = render(eng, pid, [t_s, t_v, t_r])
results["off"] = {"task": t, "films": films, "data": data, "attrib": attrib, "pdir": pdir}
check("D1 BGM 关闭：渲染 SUCCEEDED + 产出成片，证据 bgm.applied=False、无预混",
      t["status"] == "SUCCEEDED" and len(films) == 1
      and (data or {}).get("bgm", {}).get("applied") is False
      and not (data or {}).get("bgm", {}).get("premix"),
      {"status": t["status"], "films": len(films),
       "bgm": (data or {}).get("bgm", {}).get("applied")})
check("D2 BGM 关闭：credits 不含 BGM 段、attribution payload bgm=None",
      attrib is not None and attrib.get("bgm") is None
      and "背景音乐" not in (attrib.get("credits_text") or ""))
db.close()

# D3 BGM 开启（BGM 20s > 片长 → 截断）
eng, db = build_engine("on_long", {"enabled": True, "source": "media/bgm.wav", **BGM_LIC})
pid, pdir, t_s, t_v, t_r, ret_art, ctx = prepare_project(eng, "on_long")
shutil.copy2(BGM_OK, pdir / "media" / "bgm.wav")
t, films, data, attrib = render(eng, pid, [t_s, t_v, t_r])
results["on_long"] = {"task": t, "films": films, "data": data, "attrib": attrib, "pdir": pdir}
bgm_ev = (data or {}).get("bgm") or {}
check("D3 BGM 开启（过长）：渲染 SUCCEEDED、bgm.applied=True、trimmed_to_film=True、有预混文件",
      t["status"] == "SUCCEEDED" and len(films) == 1 and bgm_ev.get("applied") is True
      and (bgm_ev.get("apply_plan") or {}).get("trimmed_to_film") is True
      and (bgm_ev.get("premix") or {}).get("file")
      and (pdir / (bgm_ev.get("premix") or {}).get("file", "x")).is_file(),
      {"status": t["status"], "applied": bgm_ev.get("applied"),
       "trimmed": (bgm_ev.get("apply_plan") or {}).get("trimmed_to_film")})
check("D4 BGM 开启：签名/许可/归属随证据落库（sha256 与源文件一致）",
      bgm_ev.get("verify", {}).get("sha256") == hashlib.sha256(BGM_OK.read_bytes()).hexdigest()
      and bgm_ev.get("verify", {}).get("license_class") == "FREE_ATTRIBUTION"
      and bgm_ev.get("verify", {}).get("attribution"), bgm_ev.get("verify", {}).get("source_id"))
loud = (data or {}).get("audio_loudness") or {}
check("D5 BGM 开启后最终母带仍满足契约：-16±1 LUFS 且 TP ≤ -1.5 dBTP",
      loud.get("ok") is True and abs(float(loud.get("measured_lufs", 99)) + 16.0) <= 1.0
      and loud.get("measured_true_peak_dbtp") is not None
      and float(loud["measured_true_peak_dbtp"]) <= -1.5,
      {k: loud.get(k) for k in ("ok", "measured_lufs", "measured_true_peak_dbtp")})
film = films[0] if films else None
if film:
    pr = subprocess.run([str(FFPROBE), "-v", "error", "-show_streams", "-show_format",
                         "-of", "json", str(film)], capture_output=True, text=True,
                        encoding="utf-8", errors="replace")
    meta = json.loads(pr.stdout or "{}")
    kinds = sorted((s.get("codec_type"), s.get("codec_name")) for s in meta.get("streams", []))
    check("D6 ffprobe：h264 + aac，时长 == 时间轴（14s）",
          ("audio", "aac") in kinds and ("video", "h264") in kinds
          and abs(float(meta.get("format", {}).get("duration", 0)) - 14.0) <= 1.0,
          {"streams": kinds, "duration": meta.get("format", {}).get("duration")})
    check("D7 旁白完整性：闸门与证据仍在（narration_state=COMPLETE、时长契约通过）",
          (data or {}).get("narration_state") == "COMPLETE"
          and (data or {}).get("video_duration_ok") is True,
          {"narration_state": (data or {}).get("narration_state"),
           "video_duration_ok": (data or {}).get("video_duration_ok")})
db.close()

# D8 BGM 过短（2s < 片长 → 补静音）
eng, db = build_engine("on_short", {"enabled": True, "source": "media/bgm.wav", **BGM_LIC})
pid, pdir, t_s, t_v, t_r, ret_art, ctx = prepare_project(eng, "on_short")
shutil.copy2(BGM_SHORT, pdir / "media" / "bgm.wav")
t, films, data, attrib = render(eng, pid, [t_s, t_v, t_r])
results["on_short"] = {"task": t, "films": films, "data": data, "attrib": attrib, "pdir": pdir}
check("D8 BGM 过短：补静音（padded_after_bgm_end=True）且渲染仍成功、契约仍满足",
      t["status"] == "SUCCEEDED" and len(films) == 1
      and ((data or {}).get("bgm", {}).get("apply_plan") or {}).get("padded_after_bgm_end") is True
      and ((data or {}).get("audio_loudness") or {}).get("ok") is True,
      {"status": t["status"],
       "plan": (data or {}).get("bgm", {}).get("apply_plan")})
db.close()

# D9 静音 BGM → fail-closed
eng, db = build_engine("silent", {"enabled": True, "source": "media/bgm.wav", **BGM_LIC})
pid, pdir, t_s, t_v, t_r, ret_art, ctx = prepare_project(eng, "silent")
shutil.copy2(BGM_SILENT, pdir / "media" / "bgm.wav")
before_tasks = len(db.list_tasks(pid))
t, films, data, attrib = render(eng, pid, [t_s, t_v, t_r])
results["silent"] = {"task": t, "films": films, "data": data, "attrib": attrib, "pdir": pdir}
check("D9 静音 BGM → 渲染 BLOCKED、无成片、无 render_output、error 带 BGM_SILENT（fail-closed）",
      t["status"] == "BLOCKED" and not films and data is None
      and "BGM_SILENT" in (t.get("error") or "") and "[BGM_REJECTED]" in (t.get("error") or ""),
      {"status": t["status"], "err": (t.get("error") or "")[:150]})
check("D10 被拒时不污染台账：无 attribution、decisions/changelog 零新增、任务数只增渲染任务",
      attrib is None
      and db.conn.execute("select count(*) from decisions").fetchone()[0] == 0
      and db.conn.execute("select count(*) from changelog").fetchone()[0] == 0
      and len(db.list_tasks(pid)) == before_tasks + 1,
      {"attrib": attrib is not None, "tasks": len(db.list_tasks(pid))})
db.close()

# D11 受限许可 BGM → fail-closed
eng, db = build_engine("fairuse", {"enabled": True, "source": "media/bgm.wav",
                                   **{**BGM_LIC, "license": "fair use"}})
pid, pdir, t_s, t_v, t_r, ret_art, ctx = prepare_project(eng, "fairuse")
shutil.copy2(BGM_OK, pdir / "media" / "bgm.wav")
t, films, data, attrib = render(eng, pid, [t_s, t_v, t_r])
results["fairuse"] = {"task": t, "films": films, "data": data, "attrib": attrib, "pdir": pdir}
check("D11 受限许可 BGM（fair use）→ BLOCKED + BGM_LICENSE_RESTRICTED，绝不入片",
      t["status"] == "BLOCKED" and not films and "BGM_LICENSE_RESTRICTED" in (t.get("error") or ""),
      {"status": t["status"], "err": (t.get("error") or "")[:130]})
db.close()

# ============ E. ducking 波形/响度证据（实测） ============
print("== E. ducking 实测（on_long 预混与 BGM 包络） ==")
on = results["on_long"]
plan = (on["data"] or {}).get("bgm", {}).get("apply_plan") or {}
expr = (on["data"] or {}).get("bgm", {}).get("volume_expression")
bgm_src = on["pdir"] / "media" / "bgm.wav"
ducked = WORK / "ducked_bgm.wav"
run_ff(["-i", str(bgm_src), "-af", "volume='{}':eval=frame".format(expr), "-t", "14",
        "-c:a", "pcm_s16le", str(ducked)])
inside = mean_volume_db(ducked, 1.0, 1.5)      # 旁白期间
outside = mean_volume_db(ducked, 13.4, 0.6)    # 旁白结束之后（片尾 1 s 释放窗）
check("E1 实测 BGM 包络：旁白期间比旁白之外低 {} dB（规则 -6 dB）".format(
    None if (inside is None or outside is None) else round(outside - inside, 2)),
    inside is not None and outside is not None and abs((outside - inside) - 6.0) <= 0.6,
    {"inside_db": inside, "outside_db": outside})
premix = on["pdir"] / ((on["data"] or {}).get("bgm", {}).get("premix") or {}).get("file", "x")
mix_in = mean_volume_db(premix, 1.0, 1.5)
narr_in = mean_volume_db(NARR, 1.0, 1.5)
check("E2 旁白优先：混音中旁白窗口电平与旁白单独电平几乎相同（差 ≤1 dB，BGM 未盖住旁白）",
      mix_in is not None and narr_in is not None and abs(mix_in - narr_in) <= 1.0,
      {"premix_in_db": mix_in, "narration_in_db": narr_in})
check("E3 duck 参数与时间窗随证据落库（ramp/区间/窗口齐全，可复算）",
      plan.get("ramp_ms") == 250 and plan.get("duck_delta_db") == -6.0
      and plan.get("intervals_used") and plan.get("duck_windows")
      and plan.get("narration_priority") is True, {"ramp": plan.get("ramp_ms"),
                                                   "windows": plan.get("duck_windows")})
after = mean_volume_db(ducked, 13.3, 0.6)
check("E4 旁白结束后的恢复：片尾窗口回到 bed_db 档（与 outside 同档，差 ≤0.6 dB）",
      after is not None and outside is not None and abs(after - outside) <= 0.6,
      {"tail_db": after, "outside_db": outside})

# ============ G. credits / attribution 一致性 ============
print("== G. attribution / credits 与最终音频配置一致 ==")
att = on["attrib"] or {}
credits_txt = att.get("credits_text") or ""
check("G1 BGM 开启：attribution payload 含 bgm 块（来源/sha256/许可/归属/duck 参数）",
      att.get("bgm") and att["bgm"]["sha256"] == hashlib.sha256(BGM_OK.read_bytes()).hexdigest()
      and att["bgm"]["license_class"] == "FREE_ATTRIBUTION" and att["bgm"]["duck_db"] == -26.0
      and att["bgm"]["bed_db"] == -20.0 and att["bgm"]["narration_priority"] is True,
      {k: (att.get("bgm") or {}).get(k) for k in ("provider", "source_id", "license_class")})
check("G2 credits 文本含 BGM 段（来源/许可/归属/sha256/ducking），且只在开启时出现",
      "背景音乐（BGM，可选扩展）" in credits_txt and "attribution" in credits_txt
      and "sha256" in credits_txt and "ducking" in credits_txt
      and "背景音乐" not in (results["off"]["attrib"].get("credits_text") or ""))
check("G3 许可类别统计包含 BGM 的许可类别（credits 与最终音频配置一致）",
      (att.get("license_classes_used") or {}).get("FREE_ATTRIBUTION", 0) >= 1,
      att.get("license_classes_used"))
check("G4 audio_config 块声明 bgm_applied 与 loudness 契约来源（不改变 3-B 契约）",
      (att.get("audio_config") or {}).get("bgm_applied") is True
      and (att.get("audio_config") or {}).get("narration_priority") is True
      and (att.get("audio_config") or {}).get("loudness_contract", {}).get("target_lufs") == -16.0
      and "core/audio.py" in (att.get("audio_config") or {}).get("source_of_truth", ""),
      att.get("audio_config", {}).get("loudness_contract"))
check("G5 关闭时 credits/payload 与既有 3-A 结构一致（bgm=None，无 BGM 文本行）",
      results["off"]["attrib"] is not None and results["off"]["attrib"].get("bgm") is None
      and "背景音乐" not in (results["off"]["attrib"].get("credits_text") or "")
      and results["off"]["attrib"].get("entry_count") is not None)

print("\n结果: {}/{} 通过".format(len(PASS), len(PASS) + len(FAIL)))
if FAIL:
    print("失败项:", FAIL)
sys.exit(1 if FAIL else 0)
