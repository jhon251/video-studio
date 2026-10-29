"""Phase 2-B.1 受控故障注入驱动：证明"失败段不会整体 SUCCEEDED"+ 复用 + 完整性闸门。

在**真实项目**上运行（真实 TTS、真实引擎、真实 DB），只把 `TTSTool.execute` 换成"指定段必失败"
的包装（其余段走真工具原样合成）。注入只存在于本进程，不修改任何生产代码。

子命令：
  status <pid>                        打印 voice/render 等任务状态与逐段状态摘要
  redo <pid> <task_id>                重做某任务（走 CLI，保持既有语义）
  run <pid> [--inject N] [--cycles K]  在进程内跑调度循环；--inject N 表示第 N 段 TTS 永久失败
  segments <pid>                      打印 media/voice 分段与 narration.mp3 现状
  render-args <pid>                   打印渲染产物中的时长契约字段

用法示例：
  python docs/regression_2x/phase2b1_fault_inject.py run p_ab2b352e06b8 --inject 4 --cycles 4
"""
import json
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.agents.base import AGENTS  # noqa: E402
from video_studio.core.engine import Engine  # noqa: E402
from video_studio.db.schema import Database  # noqa: E402
from video_studio.llm.router import MockLLM, Router  # noqa: E402
from video_studio.tools.base import ToolError  # noqa: E402
from video_studio.tools.tts_tool import TTSTool  # noqa: E402

# Agent 需要被**导入**才会执行 @register（与 cli.py 的加载方式一致）
import video_studio.agents.analyst.agent  # noqa: E402,F401
import video_studio.agents.asset.agent  # noqa: E402,F401
import video_studio.agents.audio.agent  # noqa: E402,F401
import video_studio.agents.claim_extractor.agent  # noqa: E402,F401
import video_studio.agents.compliance.agent  # noqa: E402,F401
import video_studio.agents.conflict_detector.agent  # noqa: E402,F401
import video_studio.agents.critic.agent  # noqa: E402,F401
import video_studio.agents.editing.agent  # noqa: E402,F401
import video_studio.agents.evidence.agent  # noqa: E402,F401
import video_studio.agents.fact_check.agent  # noqa: E402,F401
import video_studio.agents.metadata.agent  # noqa: E402,F401
import video_studio.agents.orchestrator.agent  # noqa: E402,F401
import video_studio.agents.platform.agent  # noqa: E402,F401
import video_studio.agents.pm.agent  # noqa: E402,F401
import video_studio.agents.qa.agent  # noqa: E402,F401
import video_studio.agents.research.agent  # noqa: E402,F401
import video_studio.agents.retrieval.agent  # noqa: E402,F401
import video_studio.agents.script.agent  # noqa: E402,F401
import video_studio.agents.source_verify.agent  # noqa: E402,F401
import video_studio.agents.structure.agent  # noqa: E402,F401
import video_studio.agents.subtitle.agent  # noqa: E402,F401
import video_studio.agents.thumbnail.agent  # noqa: E402,F401
import video_studio.agents.topic.agent  # noqa: E402,F401
import video_studio.agents.visual.agent  # noqa: E402,F401
import video_studio.agents.voice.agent  # noqa: E402,F401

LOGS = ROOT / "docs" / "regression_2x" / "logs"
LOGS.mkdir(parents=True, exist_ok=True)
LOG = LOGS / "phase2b1_fault_inject.log"


def log(m):
    print(m, flush=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(str(m) + "\n")


def db():
    con = sqlite3.connect(str(ROOT / "projects" / "video_studio.db"))
    con.row_factory = sqlite3.Row
    return con


def task_rows(pid):
    con = db()
    rows = [dict(r) for r in con.execute(
        "select task_id, task_type, version, status, retry_count, error, artifacts "
        "from tasks where project_id=? order by task_type, version", (pid,))]
    con.close()
    return rows


def show_status(pid):
    log("\n--- 任务状态（现行最高版本）---")
    best = {}
    for r in task_rows(pid):
        if r["version"] >= best.get(r["task_type"], {}).get("version", 0):
            best[r["task_type"]] = r
    for t in sorted(best):
        r = best[t]
        err = (r["error"] or "").replace("\n", " ")[:110]
        log("  {:<14} {:<10} v{} retry={} {}".format(t, r["status"], r["version"],
                                                     r["retry_count"], err))
    return best


def voice_summary(pid):
    con = db()
    row = con.execute("select path from artifacts where project_id=? and type='voice_output' "
                      "order by created_at desc limit 1", (pid,)).fetchone()
    con.close()
    if not row:
        log("  （无 voice_output 产物）")
        return None
    d = json.loads(Path(row["path"]).read_text(encoding="utf-8"))
    log("  voice_output: status={} complete={} expected={} successful={} failed={} reused={}".format(
        d.get("status"), d.get("complete"), d.get("expected_segments"),
        d.get("successful_segments"), d.get("failed_segments"), d.get("reused_segments")))
    log("  narration={} dur={} timeline={} 契约={}".format(
        d.get("narration_path"), d.get("narration_duration_s"), d.get("script_time_base_s"),
        json.dumps(d.get("duration_contract"), ensure_ascii=False)))
    for s in d.get("segment_details") or []:
        codes = sorted({e.get("code") for e in (s.get("errors") or [])})
        log("    seg{:02d} {:<8} reused={} attempts={} bytes={} dur={} {}".format(
            s["index"], s["status"], s["reused"], s["attempts"], s["bytes"], s["duration_s"],
            codes or ""))
    return d


def show_segments(pid):
    media = ROOT / "projects" / pid / "media" / "voice"
    log("\n--- media/voice ---")
    for f in sorted(media.glob("*")):
        log("  {:<28} {:>9} bytes".format(f.name, f.stat().st_size))
    man = media / "segments_manifest.json"
    if man.is_file():
        d = json.loads(man.read_text(encoding="utf-8"))
        for k, v in sorted((d.get("segments") or {}).items(), key=lambda kv: int(kv[0])):
            log("  manifest seg{}: bytes={} dur={} generated_at={}".format(
                k, v.get("bytes"), v.get("duration_s"), round(v.get("generated_at") or 0, 1)))
    narr = media / "narration.mp3"
    if narr.is_file():
        p = subprocess.run([str(ROOT / "bin" / "ffprobe.exe"), "-v", "error", "-show_entries",
                            "format=duration", "-of", "default=nw=1:nk=1", str(narr)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        log("  narration.mp3 duration={}s sha256(first16)={}".format(
            (p.stdout or "").strip(), __import__("hashlib").sha256(
                narr.read_bytes()).hexdigest()[:16]))


def make_engine(pid):
    cfg = json.loads((ROOT / "config" / "config.real.json").read_text(encoding="utf-8"))
    rules = json.loads((ROOT / "config" / "rules.json").read_text(encoding="utf-8"))
    # MockLLM：voice 不调用 LLM；此处避免构造真实客户端
    return Engine(Database(ROOT / "projects" / "video_studio.db"),
                  Router(cfg["llm"], MockLLM({})), rules, ROOT / "projects", cfg, AGENTS)


def run_cycles(pid, cycles, inject=None):
    """在进程内跑调度循环；inject=N 时第 N 段 TTS 永久网络失败（其余段真合成）。"""
    calls = {"real": [], "injected": []}
    if inject is not None:
        real_execute = TTSTool.execute

        def patched(self, inputs, ctx):
            out = str(inputs.get("output") or "")
            idx = int(Path(out).stem.split("_")[-1]) if "_" in Path(out).stem else -1
            if idx == inject:
                calls["injected"].append(idx)
                raise ToolError("TTS_FAILED",
                                "ClientConnectorError: Cannot connect to host "
                                "speech.platform.bing.com:443（受控注入）")
            calls["real"].append(idx)
            return real_execute(self, inputs, ctx)

        TTSTool.execute = patched
    else:
        real_execute = TTSTool.execute

        def counting(self, inputs, ctx):
            out = str(inputs.get("output") or "")
            idx = int(Path(out).stem.split("_")[-1]) if "_" in Path(out).stem else -1
            calls["real"].append(idx)
            return real_execute(self, inputs, ctx)

        TTSTool.execute = counting
    try:
        eng = make_engine(pid)
        for i in range(1, cycles + 1):
            n = eng.run_cycle(pid, limit=20)
            log("  [cycle {}] 执行 {} 个任务（TTS 调用 real={} injected={}）".format(
                i, n, len(calls["real"]), len(calls["injected"])))
            if n == 0:
                break
            if not eng.dispatchable(pid):
                log("  [cycle {}] 无就绪任务".format(i))
                break
    finally:
        TTSTool.execute = real_execute
    return calls


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    cmd, pid = sys.argv[1], sys.argv[2]
    if cmd == "status":
        show_status(pid)
        voice_summary(pid)
    elif cmd == "segments":
        show_segments(pid)
    elif cmd == "redo":
        p = subprocess.run([sys.executable, "run.py", "--config", "config/config.real.json",
                            "redo", sys.argv[3]], cwd=str(ROOT), capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        log("redo -> " + ((p.stdout or "") + (p.stderr or "")).strip()[:200])
    elif cmd == "run":
        inject = None
        cycles = 4
        if "--inject" in sys.argv:
            inject = int(sys.argv[sys.argv.index("--inject") + 1])
        if "--cycles" in sys.argv:
            cycles = int(sys.argv[sys.argv.index("--cycles") + 1])
        log("\n=== run {} cycles={} inject={} ===".format(pid, cycles, inject))
        calls = run_cycles(pid, cycles, inject)
        log("  TTS 调用统计: real={} injected={}".format(len(calls["real"]), len(calls["injected"])))
        show_status(pid)
        voice_summary(pid)
    elif cmd == "render-args":
        con = db()
        row = con.execute("select path from artifacts where project_id=? and type='render_output' "
                          "order by created_at desc limit 1", (pid,)).fetchone()
        con.close()
        d = json.loads(Path(row["path"]).read_text(encoding="utf-8"))
        for k in ("narration_state", "narration_completeness", "duration_contract",
                  "video_duration_s", "video_duration_ok", "visual_source",
                  "material_assembly", "scene_count", "output"):
            log("{} = {}".format(k, json.dumps(d.get(k), ensure_ascii=False)))
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
