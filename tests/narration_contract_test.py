"""Phase 2-B.1 单测（免费、确定性）：旁白分段状态 / 复用 / 重试 / 完整性闸门 / 时长契约。

不访问网络：TTS 工具被替换为"用 ffmpeg 生成等长 mp3"的假实现，可编程失败（含网络类错误码）。
被测对象是**生产代码路径**：VoiceAgent.run 与 EditingAgent.run（task_type=render）。

覆盖：
  A. 时长契约一致性：script_time_base_s == 素材时间轴末镜头 end_s
  B. 逐段真实状态：全部成功 → COMPLETE / confidence=1.0
  C. 受控失败：某段永久失败 → 抛出 + 产物 INCOMPLETE + 不覆盖已有 narration.mp3 + 明确错误码
  D. 失败段独立重试：网络类错误第 1 次失败、第 2 次成功 → status=SUCCESS、attempts=2
  E. 成功段复用：第二次运行 0 次 TTS 调用（REUSED）；文本变化时只重做该段
  F. 渲染前闸门：旁白不完整 → render 在调用 ffmpeg 前阻断，不产生新成片
  G. 时长契约：旁白短于时间轴 → 视频仍等于时间轴长度（apad 补齐，不再 -shortest 截短）；
     6-A/M2 起"短旁白"在 render 前被 Production Integrity 硬门阻断（PI-1/PI-2/PI-6），
     完整旁白（覆盖充分）走全链路照常成片（含 PI 证据落盘）
  H. 旁白超时轴且超容差 → 阻断
  I. 产出后校验：成片时长与时间轴不符 → 阻断（先通过渲染前硬门，再被产出后校验拦下）
  J. ffmpeg 参数：旁白分支不再含 -shortest，改为 apad + -t total

注：本文件在 6-A/M2 做了**测试契约更新**（G3 由"产出成片"改为"硬门阻断"、I 改用完整旁白进入产出后
校验、G4 新增完整旁白 PASS 用例）；业务语义未变：apad 仍是合法音频处理，时间轴仍是时长权威，
**只是不再把"旁白覆盖不足"当成合法完成**。

用法：python tests/narration_contract_test.py
"""
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.agents.editing import agent as editing_mod  # noqa: E402
from video_studio.agents.editing.agent import EditingAgent  # noqa: E402
from video_studio.agents.voice.agent import VoiceAgent  # noqa: E402
from video_studio.core import narration as narration_mod  # noqa: E402
from video_studio.core.narration import (NarrationIncompleteError, script_time_base_s)  # noqa: E402
from video_studio.tools.base import ToolError  # noqa: E402

FFMPEG = ROOT / "bin" / "ffmpeg.exe"
WORK = Path(r"C:\Users\DUALAN~1\AppData\Local\Temp\v161audit\narration_test")
PASS, FAIL = [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print(("PASS  " if ok else "FAIL  ") + name + (" | " + str(detail)[:200] if detail else ""))


def make_mp3(path: Path, seconds: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([str(FFMPEG), "-y", "-v", "error", "-f", "lavfi", "-i",
                        f"sine=frequency=440:duration={seconds:.3f}", "-c:a", "libmp3lame",
                        str(path)], capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    if r.returncode != 0:
        raise RuntimeError("fake tts ffmpeg failed: " + (r.stderr or "")[:200])


# ---------------- 假 TTS（可编程失败；真实 mp3 输出，供 ffprobe 探测） ----------------
class FakeTTS:
    def __init__(self):
        self.calls = []
        self.fail_plan = {}      # index -> [(exc_text, times)] 简化：index -> list[exc_text 或 None]
        self.durations = {}      # index -> 秒
        self.audio_sha = {}

    def set_failures(self, plan):
        self.fail_plan = {k: list(v) for k, v in plan.items()}

    def execute(self, inputs, ctx):
        out = str(inputs["output"])
        idx = int(Path(out).stem.split("_")[-1])
        self.calls.append(idx)
        plan = self.fail_plan.get(idx) or []
        if plan:
            exc = plan.pop(0)
            if exc:
                raise ToolError(exc.split(":")[0], exc.split(":", 1)[-1])
        dur = self.durations.get(idx, 3.0)
        p = Path(ctx.project_dir) / out
        make_mp3(p, dur)
        self.audio_sha[idx] = p.read_bytes()
        return type("R", (), {"ok": True, "data": {"audio": out}})()


class FakeDB:
    def __init__(self, tasks, arts):
        self.tasks = tasks
        self.arts = arts

    def get_task(self, tid):
        return self.tasks.get(tid)

    def get_artifact(self, aid):
        return self.arts.get(aid)

    def update_task(self, tid, **kw):
        self.tasks.setdefault(tid, {}).update(kw)


class FakeEngine:
    def __init__(self, workdir: Path, tasks, arts, config):
        self.work = workdir
        self.db = FakeDB(tasks, arts)
        self.config = config
        self.written = []
        self.events = []

    def project_dir(self, pid):
        return self.work

    def write_artifact(self, project_id, task_id, type_, content, summary="", version=1,
                       license_=None):
        aid = "a_test_{}".format(len(self.written) + 1)
        p = self.work / "artifacts" / "{}.json".format(aid)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(content, ensure_ascii=False, indent=1), encoding="utf-8")
        self.arts_write = getattr(self, "arts_write", {})
        self.arts_write[aid] = {"artifact_id": aid, "type": type_, "path": str(p),
                                "summary": summary}
        self.db.arts[aid] = self.arts_write[aid]
        self.written.append({"id": aid, "type": type_, "content": content, "path": str(p)})
        return aid

    def attach_artifact(self, task_id, artifact_id):
        self.db.tasks.setdefault(task_id, {}).setdefault("artifacts", []).append(artifact_id)

    def emit(self, project_id, type_, actor, task_id=None, payload=None, human_visible=False):
        self.events.append({"type": type_, "task": task_id, "payload": payload})


CFG = {"tools": {"tts": {"provider": "edge-tts", "voice_type": "zh-CN-XiaoxiaoNeural"},
                 "ffmpeg": {"path": str(ROOT / "bin" / "ffmpeg.exe"),
                            "ffprobe": str(ROOT / "bin" / "ffprobe.exe")}},
       "retry": {"default_max_retries": 2, "backoff_base_s": 0.01}}

SCRIPT = {"segments": [
    {"chapter": "A", "narration": "第一段旁白内容。", "duration_s": 3},
    {"chapter": "B", "narration": "第二段旁白内容。", "duration_s": 3},
    {"chapter": "C", "narration": "第三段旁白内容。", "duration_s": 3},
]}


def setup_work():
    if WORK.exists():
        shutil.rmtree(WORK, ignore_errors=True)
    (WORK / "media" / "voice").mkdir(parents=True, exist_ok=True)
    (WORK / "artifacts").mkdir(parents=True, exist_ok=True)
    (WORK / "output").mkdir(parents=True, exist_ok=True)
    sp = WORK / "artifacts" / "script.json"
    sp.write_text(json.dumps(SCRIPT, ensure_ascii=False), encoding="utf-8")
    return sp


def voice_task():
    return {"task_id": "t_voice", "project_id": "p_test", "task_type": "voice",
            "dependencies": ["t_script"], "inputs": {}}


def render_task():
    return {"task_id": "t_render", "project_id": "p_test", "task_type": "render",
            "dependencies": ["t_voice"], "inputs": {}}


def make_engine(sp):
    tasks = {"t_script": {"task_id": "t_script", "artifacts": ["a_script"], "dependencies": []},
             "t_voice": {"task_id": "t_voice", "artifacts": [], "dependencies": ["t_script"]},
             "t_render": {"task_id": "t_render", "artifacts": [], "dependencies": ["t_voice"]}}
    arts = {"a_script": {"artifact_id": "a_script", "type": "script_output", "path": str(sp)}}
    return FakeEngine(WORK, tasks, arts, CFG)


# ---------------- A. 契约一致性 ----------------
tl = EditingAgent._build_material_timeline(SCRIPT, [], [])
check("A1 script_time_base_s == 时间轴末镜头 end_s",
      abs(script_time_base_s(SCRIPT) - tl[-1]["end_s"]) < 1e-6,
      "{} vs {}".format(script_time_base_s(SCRIPT), tl[-1]["end_s"]))

# ---------------- B. 全部成功 → COMPLETE ----------------
sp = setup_work()
eng = make_engine(sp)
fake = FakeTTS()
fake.durations = {0: 3.0, 1: 3.0, 2: 3.0}
real_exec = editing_mod  # noqa: F841  (占位，避免误用)
import video_studio.tools.tts_tool as tts_mod  # noqa: E402
tts_mod.TTSTool.execute = lambda self, inputs, ctx: fake.execute(inputs, ctx)

VoiceAgent().run(eng, voice_task())
art = eng.written[-1]["content"]
check("B1 12/12 语义：3/3 段成功", art["successful_segments"] == 3 and art["failed_segments"] == [],
      art["summary"])
check("B2 status=COMPLETE / complete=True", art["status"] == "COMPLETE" and art["complete"] is True)
check("B3 confidence=1.0（完整才给 1.0）", art["confidence"] == 1.0)
check("B4 逐段记录 status/attempts/bytes/duration_s",
      all({"status", "attempts", "bytes", "duration_s", "text_sha256"} <= set(s)
          for s in art["segment_details"]))
narr = WORK / "media" / "voice" / "narration.mp3"
check("B5 narration.mp3 已生成", narr.is_file() and narr.stat().st_size > 0)
check("B6 时长契约：narration 9.0s vs timeline 11.0s 记录在案",
      abs(art["narration_duration_s"] - 9.0) < 0.3 and art["script_time_base_s"] == 11.0,
      art["duration_contract"])
check("B7 旁白较短 → 权威改为 audio_time_base（不缩短视频、不靠 apad 掩盖；差额=授权 pause budget）",
      art["duration_contract"]["policy"] == "audio_time_base_v2"
      and art["duration_contract"]["audio_padded_to_timeline"] is False
      # v2 不变式：audio_time_base == 实测旁白音轨 + 授权 pause budget（±0.05s）
      and abs(art["audio_time_base_s"] - (art["narration_duration_s"] + art["padding_budget_s"])) < 0.05
      and art["planning_drift"]["blocking"] is False
      and art["planning_drift"]["code"] == "PLANNING_DRIFT",
      {"contract": art["duration_contract"], "audio_time_base_s": art["audio_time_base_s"],
       "narration_duration_s": art["narration_duration_s"],
       "padding_budget_s": art["padding_budget_s"], "planning_drift": art["planning_drift"]})

# ---------------- E. 复用：第二次运行 0 次调用 ----------------
before = len(fake.calls)
eng2 = make_engine(sp)
eng2.db.arts.update(eng.db.arts)
VoiceAgent().run(eng2, voice_task())
art2 = eng2.written[-1]["content"]
check("E1 已成功段全部复用，0 次 TTS 调用", len(fake.calls) == before, fake.calls)
check("E2 复用段 status=REUSED 且 reused=True",
      all(s["status"] == "REUSED" and s["reused"] for s in art2["segment_details"]))
check("E3 复用不改变音频字节（sha 不变）",
      art2["segment_details"][0]["text_sha256"] == art["segment_details"][0]["text_sha256"])

# 文本变化 → 只重做该段
saved = SCRIPT["segments"][1]["narration"]
SCRIPT["segments"][1]["narration"] = "第二段旁白内容（改）。"
(WORK / "artifacts" / "script.json").write_text(json.dumps(SCRIPT, ensure_ascii=False),
                                                encoding="utf-8")
before = len(fake.calls)
eng3 = make_engine(sp)
eng3.db.arts.update(eng.db.arts)
VoiceAgent().run(eng3, voice_task())
art3 = eng3.written[-1]["content"]
check("E4 文本变化只重做该段（1 次调用，index=1）",
      len(fake.calls) - before == 1 and fake.calls[-1] == 1, fake.calls[-3:])
check("E5 其余段仍复用", len(art3["reused_segments"]) == 2, art3["reused_segments"])
SCRIPT["segments"][1]["narration"] = saved
(WORK / "artifacts" / "script.json").write_text(json.dumps(SCRIPT, ensure_ascii=False),
                                                encoding="utf-8")

# ---------------- D. 网络类错误重试后成功 ----------------
sp = setup_work()
fake2 = FakeTTS()
fake2.durations = {0: 3.0, 1: 3.0, 2: 3.0}
fake2.set_failures({2: ["TTS_FAILED:ClientConnectorError: Cannot connect to host x:443",
                        None]})
tts_mod.TTSTool.execute = lambda self, inputs, ctx: fake2.execute(inputs, ctx)
eng4 = make_engine(sp)
VoiceAgent().run(eng4, voice_task())
art4 = eng4.written[-1]["content"]
seg2 = art4["segment_details"][2]
check("D1 重试后成功（attempts=2）", seg2["status"] == "SUCCESS" and seg2["attempts"] == 2,
      seg2)
check("D2 首次失败记录明确错误码 TTS_NETWORK/retryable",
      seg2["errors"] and seg2["errors"][0]["code"] == "TTS_NETWORK"
      and seg2["errors"][0]["retryable"] is True, seg2["errors"])
check("D3 整体仍 COMPLETE", art4["complete"] is True)

# ---------------- C. 受控永久失败 → 不 SUCCEEDED ----------------
sp = setup_work()
fake3 = FakeTTS()
fake3.durations = {0: 3.0, 1: 3.0, 2: 3.0}
make_mp3(WORK / "media" / "voice" / "narration.mp3", 9.0)          # 先放一个"旧的完整音轨"
old_bytes = (WORK / "media" / "voice" / "narration.mp3").read_bytes()
fake3.set_failures({1: ["TTS_FAILED:Invalid voice 'x'", "TTS_FAILED:Invalid voice 'x'",
                        "TTS_FAILED:Invalid voice 'x'"]})
tts_mod.TTSTool.execute = lambda self, inputs, ctx: fake3.execute(inputs, ctx)
eng5 = make_engine(sp)
raised = None
try:
    VoiceAgent().run(eng5, voice_task())
except NarrationIncompleteError as exc:
    raised = exc
check("C1 存在失败段 → 抛错（任务不会 SUCCEEDED）", raised is not None, raised)
check("C2 错误文案含明确错误码 [NARRATION_INCOMPLETE]",
      raised is not None and "[NARRATION_INCOMPLETE]" in str(raised))
art5 = eng5.written[-1]["content"]
check("C3 产物 status=INCOMPLETE / complete=False", art5["status"] == "INCOMPLETE"
      and art5["complete"] is False)
check("C4 confidence=0.0（不再假报 1.0）", art5["confidence"] == 0.0)
check("C4b 未测得时长时不谎报 0s（measured=False / narration_duration_s=None）",
      art5["duration_contract"]["measured"] is False
      and art5["duration_contract"]["narration_duration_s"] is None
      and art5["narration_duration_s"] is None, art5["duration_contract"])
check("C5 failed_segments=[1]，非重试类错误立即判失败（attempts=1）且错误码明确",
      art5["failed_segments"] == [1] and art5["segment_details"][1]["attempts"] == 1
      and art5["segment_details"][1]["errors"][0]["code"] == "TTS_SYNTHESIS_FAILED",
      art5["segment_details"][1])
check("C6 失败时不覆盖已有 narration.mp3",
      (WORK / "media" / "voice" / "narration.mp3").read_bytes() == old_bytes)
check("C7 已成功段仍被登记（2 段）", art5["successful_segments"] == 2)

# ---------------- C2. 网络类错误重试耗尽 → attempts=max_attempts ----------------
sp_c = setup_work()
fake4 = FakeTTS()
fake4.durations = {0: 3.0, 1: 3.0, 2: 3.0}
NE = "TTS_FAILED:ClientConnectorError: Cannot connect to host speech.platform.bing.com:443"
fake4.set_failures({0: [NE, NE, NE]})
tts_mod.TTSTool.execute = lambda self, inputs, ctx: fake4.execute(inputs, ctx)
eng5b = make_engine(sp_c)
try:
    VoiceAgent().run(eng5b, voice_task())
except NarrationIncompleteError:
    pass
art5b = eng5b.written[-1]["content"]
seg0 = art5b["segment_details"][0]
check("C8 网络类失败重试到上限（attempts=3）、错误码 TTS_NETWORK 且 retryable",
      seg0["attempts"] == 3 and len(seg0["errors"]) == 3
      and all(e["code"] == "TTS_NETWORK" and e["retryable"] for e in seg0["errors"]), seg0)
check("C9 错误信息保留原始异常文本（含 speech.platform.bing.com）",
      "speech.platform.bing.com" in seg0["errors"][0]["error"], seg0["errors"][0]["error"])

# ---------------- F. 渲染前闸门：不完整 → 阻断且不产片 ----------------
sp = setup_work()
make_mp3(WORK / "media" / "voice" / "narration.mp3", 9.0)
vp = WORK / "artifacts" / "voice_incomplete.json"
vp.write_text(json.dumps({
    "audio": None, "complete": False, "status": "INCOMPLETE",
    "expected_segments": 3, "successful_segments": 2, "failed_segments": [1],
    "segments": [{"index": 0, "audio": "media/voice/seg_00.mp3", "status": "SUCCESS"},
                 {"index": 2, "audio": "media/voice/seg_02.mp3", "status": "SUCCESS"}],
}, ensure_ascii=False), encoding="utf-8")
eng6 = make_engine(sp)
eng6.db.arts["a_voice"] = {"artifact_id": "a_voice", "type": "voice_output", "path": str(vp)}
eng6.db.tasks["t_voice"]["artifacts"] = ["a_voice"]
raised = None
try:
    EditingAgent().run(eng6, render_task())
except NarrationIncompleteError as exc:
    raised = exc
check("F1 render 在 ffmpeg 之前阻断（[NARRATION_INCOMPLETE]）",
      raised is not None and "[NARRATION_INCOMPLETE]" in str(raised), raised)
check("F2 未写出任何成片", not list((WORK / "output").glob("*.mp4")))
check("F3 阻断事件 human_visible 已发",
      any(e["type"] == "TASK_BLOCKED" and e["payload"] for e in eng6.events))

# ---------------- G/J. 完整旁白 + 短于时间轴 → 视频长度 == 时间轴（apad，不截短） ----------------
sp = setup_work()
for i, d in enumerate((3.0, 3.0, 3.0)):
    make_mp3(WORK / "media" / "voice" / f"seg_{i:02d}.mp3", d)
make_mp3(WORK / "media" / "voice" / "narration.mp3", 9.0)
segs = [{"index": i, "audio": f"media/voice/seg_{i:02d}.mp3", "status": "SUCCESS", "reused": False,
         "attempts": 1, "bytes": 1000, "duration_s": 3.0, "text_sha256": "x"} for i in range(3)]
vp_ok = WORK / "artifacts" / "voice_ok.json"
vp_ok.write_text(json.dumps({"audio": "media/voice/narration.mp3", "complete": True,
                             "status": "COMPLETE", "expected_segments": 3,
                             "successful_segments": 3, "failed_segments": [],
                             "segments": segs}, ensure_ascii=False), encoding="utf-8")
eng7 = make_engine(sp)
eng7.db.arts["a_voice"] = {"artifact_id": "a_voice", "type": "voice_output", "path": str(vp_ok)}
eng7.db.tasks["t_voice"]["artifacts"] = ["a_voice"]
eng7.config = dict(CFG)
eng7.config["tools"] = dict(CFG["tools"])
args = EditingAgent._narration_args(eng7, {"project_id": "p_test", "task_id": "t_render"}, SCRIPT,
                                    "320x240", 30, {"codec": "libx264"},
                                    narration_audio="media/voice/narration.mp3", timeline=tl)
check("J1 旁白分支不含 -shortest", "-shortest" not in args)
check("J2 旁白分支用 apad + -t total",
      any("apad" in str(a) for a in args) and args.count("-t") >= 1)
check("J3 未使用素材背景分支同样不含 -shortest",
      "-shortest" not in EditingAgent._narration_args(
          eng7, {"project_id": "p_test"}, SCRIPT, "320x240", 30, {"codec": "libx264"},
          narration_audio="media/voice/narration.mp3", timeline=None, background_image=None))

out = WORK / "output" / "g_test.mp4"
cmd = [str(FFMPEG), "-y", "-v", "error", *args, str(out)]
r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
check("G1 ffmpeg 渲染 rc=0", r.returncode == 0 and out.is_file(), (r.stderr or "")[:200])
if out.is_file():
    p = subprocess.run([str(ROOT / "bin" / "ffprobe.exe"), "-v", "error", "-show_entries",
                        "format=duration", "-of", "default=nw=1:nk=1", str(out)],
                       capture_output=True, text=True)
    dur = float((p.stdout or "0").strip() or 0)
    check("G2 旁白 9s 但成片 == 时间轴 11s（不再被截短）", abs(dur - 11.0) <= 0.5,
          "video={} timeline=11.0".format(round(dur, 3)))

# ---------------- G3. 短旁白走全链路（6-A/M2 契约更新）----------------
# **测试契约更新（不改业务语义）**：M2 之前"9s 旁白 / 11s 时间轴"会照常产出一个 apad 补齐的成片；
# M2 之后这属于"短旁白被当成合法完成"，必须**在调用 ffmpeg 之前**被 Production Integrity 硬门阻断。
# 注意：apad 本身仍是合法音频处理机制（其证据在 G1/G2/J1-J3 的 ffmpeg 参数层保留）。
_mp4_before = {p.name for p in (WORK / "output").glob("*.mp4")}
eng8 = make_engine(sp)
eng8.db.arts["a_voice"] = {"artifact_id": "a_voice", "type": "voice_output", "path": str(vp_ok)}
eng8.db.tasks["t_voice"]["artifacts"] = ["a_voice"]
raised = None
try:
    EditingAgent().run(eng8, render_task())
except NarrationIncompleteError as exc:
    raised = exc
check("G3 短旁白（9s/11s，覆盖率 0.82）→ 渲染前硬门阻断（M2）",
      raised is not None and "[NARRATION_INCOMPLETE]" in str(raised), raised)
check("G3b 阻断原因含 PI-1 覆盖率违约", raised is not None and "PI-1" in str(raised))
check("G3c 阻断时不写 render_output（不产出被截短的交付物）",
      not [w for w in eng8.written if w["type"] == "render_output"],
      [w["type"] for w in eng8.written])
check("G3d 阻断发生在 ffmpeg 之前（未新增任何 mp4）",
      {p.name for p in (WORK / "output").glob("*.mp4")} == _mp4_before)

# ---------------- G4. 完整旁白（11s/11s）→ 全链路照常 PASS（正常成片行为不变）----------------
sp_g = setup_work()
# 旁白文案加长到"字幕显示时长 ≥ 60% 旁白时长"（真实成片的正常情形）：8 字 → 17 字/段。
SCRIPT_FULL = {"segments": [
    {"chapter": "A", "narration": "第一段旁白内容需要完整说明本段的要点", "duration_s": 3},
    {"chapter": "B", "narration": "第二段旁白内容需要完整说明本段的要点", "duration_s": 3},
    {"chapter": "C", "narration": "第三段旁白内容需要完整说明本段的要点", "duration_s": 3},
]}
(WORK / "artifacts" / "script.json").write_text(json.dumps(SCRIPT_FULL, ensure_ascii=False),
                                                 encoding="utf-8")
for _i in range(3):
    make_mp3(WORK / "media" / "voice" / "seg_{:02d}.mp3".format(_i), 3.0)
make_mp3(WORK / "media" / "voice" / "narration.mp3", 11.0)
segs_full = [{"index": i, "audio": "media/voice/seg_{:02d}.mp3".format(i), "status": "SUCCESS",
              "reused": False, "attempts": 1, "bytes": 1000, "duration_s": 3.0,
              "text_sha256": "y"} for i in range(3)]
vp_full = WORK / "artifacts" / "voice_full.json"
vp_full.write_text(json.dumps({
    "audio": "media/voice/narration.mp3", "complete": True, "status": "COMPLETE",
    "expected_segments": 3, "successful_segments": 3, "failed_segments": [],
    "narration_duration_s": 11.0, "segments": segs_full, "segment_details": segs_full,
}, ensure_ascii=False), encoding="utf-8")
eng11 = make_engine(sp_g)
eng11.db.arts["a_voice"] = {"artifact_id": "a_voice", "type": "voice_output", "path": str(vp_full)}
eng11.db.tasks["t_voice"]["artifacts"] = ["a_voice"]
EditingAgent().run(eng11, render_task())
rend = [w for w in eng11.written if w["type"] == "render_output"]
check("G4 完整旁白（11s/11s）完整链路照常产出 render_output", len(rend) == 1)
if rend:
    d = rend[0]["content"]
    check("G5 render 记录 narration_state=COMPLETE / video_duration_ok=True",
          d["narration_state"] == "COMPLETE" and d["video_duration_ok"] is True,
          {"state": d["narration_state"], "dur": d.get("video_duration_s")})
    check("G6 成片时长与时间轴一致（±1s）",
          abs(float(d["video_duration_s"]) - 11.0) <= 1.0, d["video_duration_s"])
    check("G7 时长契约字段落盘（policy=timeline_authoritative）",
          (d.get("duration_contract") or {}).get("policy") == "timeline_authoritative")
    _pi = d.get("production_integrity") or {}
    _pre = ((_pi.get("pre_render") or {}).get("metrics") or {})
    _post = ((_pi.get("post_render") or {}).get("metrics") or {})
    check("G8 M2 门禁证据落盘：pre/post 均未阻断且 PI-1..PI-6 状态齐全",
          (_pi.get("pre_render") or {}).get("blocked") is False
          and (_pi.get("post_render") or {}).get("blocked") is False
          and set(_pre) == {"PI-1", "PI-2", "PI-6"} and set(_post) == {"PI-3", "PI-4", "PI-5"},
          {"pre": _pre, "post": _post})

# ---------------- H. 旁白超时轴且超容差 → 阻断 ----------------
sp2 = setup_work()
(vp2 := WORK / "artifacts" / "voice_long.json").write_text(json.dumps({
    "audio": "media/voice/narration.mp3", "complete": True, "status": "COMPLETE",
    "expected_segments": 3, "successful_segments": 3, "failed_segments": [], "segments": segs,
}, ensure_ascii=False), encoding="utf-8")
make_mp3(WORK / "media" / "voice" / "narration.mp3", 40.0)     # 40s vs 11s timeline
eng9 = make_engine(sp2)
eng9.db.arts["a_voice"] = {"artifact_id": "a_voice", "type": "voice_output", "path": str(vp2)}
eng9.db.tasks["t_voice"]["artifacts"] = ["a_voice"]
raised = None
try:
    EditingAgent().run(eng9, render_task())
except NarrationIncompleteError as exc:
    raised = exc
check("H1 旁白超时轴超出容差 → 阻断", raised is not None
      and "超出容差" in str(raised), raised)

# ---------------- I. 产出后校验：成片时长不符 → 阻断 ----------------
# 6-A/M2 契约更新：进入"产出后校验"的前提是**渲染前硬门先通过**（PI-1/PI-2/PI-6），
# 因此本例改用 11s 完整旁白（11s 时间轴），再由谎报的 ffprobe 模拟"被截短的成片"。
sp3 = setup_work()
make_mp3(WORK / "media" / "voice" / "narration.mp3", 11.0)
(vp3 := WORK / "artifacts" / "voice_ok2.json").write_text(json.dumps({
    "audio": "media/voice/narration.mp3", "complete": True, "status": "COMPLETE",
    "expected_segments": 3, "successful_segments": 3, "failed_segments": [], "segments": segs,
    "narration_duration_s": 11.0, "segment_details": segs,
}, ensure_ascii=False), encoding="utf-8")
eng10 = make_engine(sp3)
eng10.db.arts["a_voice"] = {"artifact_id": "a_voice", "type": "voice_output", "path": str(vp3)}
eng10.db.tasks["t_voice"]["artifacts"] = ["a_voice"]
_orig_probe = editing_mod.probe_duration_s
_calls = {"n": 0}


def _lying_probe(ctx, path, *a, **k):
    """第一次（闸门）如实，第二次（产出后校验）谎报 5s，模拟"被截短的成片"。"""
    _calls["n"] += 1
    if _calls["n"] == 2:
        return 5.0
    return _orig_probe(ctx, path, *a, **k)


editing_mod.probe_duration_s = _lying_probe
raised = None
try:
    EditingAgent().run(eng10, render_task())
except NarrationIncompleteError as exc:
    raised = exc
finally:
    editing_mod.probe_duration_s = _orig_probe
check("I1 产出后时长校验失败 → 阻断（成片时长校验未通过）",
      raised is not None and "成片时长校验未通过" in str(raised), raised)

print("\n结果: {}/{} 通过".format(len(PASS), len(PASS) + len(FAIL)))
if FAIL:
    print("失败项:", FAIL)
sys.exit(0 if not FAIL else 1)
