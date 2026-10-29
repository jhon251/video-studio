"""3.x Phase 3-B 失败路径（真实渲染 + 真实音频，绝不用 mock 数值）：

  1 mastering_off      关掉母带链（apply_mastering=false）→ 成片实测 -19.7 LUFS → **BLOCKED**
  2 impossible_tp      契约把真峰要求设成不可能达到（-40 dBTP）→ 限幅器上限 -3 dBFS → **BLOCKED**
  3 silent_narration   真实静音旁白（有合法时长）→ 测不到/严重超差 → **BLOCKED**（不产出成片）

每条都断言三件事：① 任务不是 SUCCEEDED；② 没有 render_output 交付物；③ 错误码/原因指向响度契约。
用法: python docs/regression_2x/phase3b_failure_paths.py
"""
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.agents.base import AGENTS  # noqa: E402
from video_studio.core.audio import contract_from_config, verify_file  # noqa: E402
from video_studio.core.engine import Engine  # noqa: E402
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
LOGS = ROOT / "docs" / "regression_2x" / "logs"
PASS, FAIL, ROWS = [], [], []

SCRIPT = {"segments": [
    {"chapter": "a", "narration": "虚拟现实 头显 佩戴 形态 展示", "duration_s": 6},
    {"chapter": "b", "narration": "手柄 追踪 定位 交互 演示", "duration_s": 6},
], "summary": "Phase 3-B failure path"}


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print(("PASS  " if ok else "FAIL  ") + name + (" | " + str(detail)[:200] if detail else ""))


def build(loudness_cfg: dict | None, silent_narration: bool, tag: str) -> dict:
    """跑一个真实渲染项目；返回 {status, error, render_output, film_probe}。"""
    cfg = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8"))
    rules = json.loads((ROOT / "config" / "rules.json").read_text(encoding="utf-8"))
    if loudness_cfg is not None:
        cfg.setdefault("tools", {}).setdefault("ffmpeg", {})["loudness"] = loudness_cfg
    eng = Engine(Database(ROOT / "projects" / "video_studio.db"),
                 Router(cfg["llm"], MockLLM(cfg["llm"].get("mock", {}).get("responses", {}),
                                            cfg["llm"].get("mock", {}).get("default", {}))),
                 rules, ROOT / "projects", cfg, AGENTS)
    pid = eng.create_project("phase3b_" + tag)
    proj = eng.project_dir(pid)
    (proj / "media" / "voice").mkdir(parents=True, exist_ok=True)
    narr = proj / "media" / "voice" / "narration.wav"
    if silent_narration:
        subprocess.run([str(FFMPEG), "-y", "-hide_banner", "-nostats", "-f", "lavfi",
                        "-i", "anullsrc=r=24000:cl=mono", "-t", "14", "-c:a", "pcm_s16le",
                        str(narr)], capture_output=True)
    else:
        subprocess.run([str(FFMPEG), "-y", "-hide_banner", "-nostats", "-ss", "20", "-t", "14",
                        "-i", str(REAL_NARRATION), "-vn", "-c:a", "pcm_s16le", str(narr)],
                       capture_output=True)
    t_script = eng.create_task(pid, "script", "script")
    aid = eng.write_artifact(pid, t_script, "script_output", SCRIPT, summary="脚本")
    eng.attach_artifact(t_script, aid)
    eng.db.set_task_status(t_script, "SUCCEEDED")
    t_voice = eng.create_task(pid, "voice", "voice", dependencies=[t_script])
    vpay = {"status": "COMPLETE", "complete": True, "audio": "media/voice/narration.wav",
            "narration_path": "media/voice/narration.wav", "narration_written": True,
            "narration_duration_s": 14.0, "provider": "fixture_real_tts",
            "segments": [{"index": i, "status": "SUCCESS", "audio": "media/voice/seg{}.mp3".format(i),
                          "text": SCRIPT["segments"][i]["narration"]} for i in (0, 1)]}
    aid = eng.write_artifact(pid, t_voice, "voice_output", vpay, summary="旁白")
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
    row = dict(con.execute("select status, error from tasks where task_id=?", (t_rend,)).fetchone())
    a = con.execute("select path from artifacts where task_id=? and type='render_output' "
                    "order by created_at desc limit 1", (t_rend,)).fetchone()
    con.close()
    films = sorted((proj / "output").glob("*.mp4"))
    case_contract = contract_from_config({"tools": {"ffmpeg": {"loudness": loudness_cfg or {}}}})
    return {"pid": pid, "task": t_rend, "status": row["status"], "error": row["error"],
            "render_output": bool(a), "contract": case_contract,
            "films": [{"path": str(p),
                       **{k: v for k, v in verify_file(
                           p, exe=str(FFMPEG), contract=case_contract).items()
                          if k in ("measured_lufs", "measured_true_peak_dbtp", "ok", "reasons")}}
                      for p in films]}


CASES = [
    ("1 mastering_off", {"apply_mastering": False}, False, ("LOUDNESS_OUT_OF_RANGE",)),
    ("2 impossible_tp", {"max_true_peak_dbtp": -40.0}, False, ("TRUE_PEAK_EXCEEDED",
                                                               "LOUDNESS_OUT_OF_RANGE")),
    ("3 silent_narration", None, True, ("LOUDNESS_NOT_MEASURED", "LOUDNESS_OUT_OF_RANGE",
                                        "TRUE_PEAK")),
]
for name, lcfg, silent, expected_codes in CASES:
    r = build(lcfg, silent, name.split()[1])
    ROWS.append({"case": name, **r, "expected_codes": list(expected_codes)})
    err = str(r["error"] or "")
    check(name + "：真实渲染被 fail-closed 阻断（非 SUCCEEDED）",
          r["status"] in ("BLOCKED", "FAILED"),
          "status={} error={}".format(r["status"], err[:120]))
    check(name + "：未交付 render_output 产物", not r["render_output"], r["render_output"])
    check(name + "：原因指向响度契约（{}）".format("/".join(expected_codes)),
          any(c in err for c in expected_codes),
          "error={} | films={}".format(err[:90], r["films"]))
    if r["films"]:
        check(name + "：落盘文件按**该用例契约**实测确为不合规（不是合规片被误拦）",
              all(not f["ok"] for f in r["films"]),
              [("I={} TP={} ok={}".format(f["measured_lufs"], f["measured_true_peak_dbtp"], f["ok"]))
               for f in r["films"]])

LOGS.mkdir(parents=True, exist_ok=True)
rec = {"rows": ROWS, "checks": {"pass": PASS, "fail": FAIL}}
(LOGS / "phase3b_failure_paths.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1,
                                                           default=str), encoding="utf-8")
print("\n结果: {}/{} 通过".format(len(PASS), len(PASS) + len(FAIL)))
if FAIL:
    print("失败项:", FAIL)
print("记录:", LOGS / "phase3b_failure_paths.json")
sys.exit(0 if not FAIL else 1)
