"""全管线集成测试：22 个 Agent 走标准生产生命周期（Mock LLM + 真实 ffmpeg）。

流程：项目创建 → 标准管线建任务 → 循环调度 + 自动批准闸门 → 断言全链路终态。
"""

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from video_studio.db.schema import Database  # noqa: E402
from video_studio.core.engine import Engine  # noqa: E402
from video_studio.llm.router import MockLLM, Router  # noqa: E402
from video_studio.hitl.service import HITL  # noqa: E402
from video_studio.pipeline.lifecycle import build_pipeline_task_specs  # noqa: E402

import video_studio.agents.orchestrator.agent  # noqa: F401,E402
import video_studio.agents.pm.agent  # noqa: F401,E402
import video_studio.agents.topic.agent  # noqa: F401,E402
import video_studio.agents.research.agent  # noqa: F401,E402
import video_studio.agents.source_verify.agent  # noqa: F401,E402
import video_studio.agents.structure.agent  # noqa: F401,E402
import video_studio.agents.script.agent  # noqa: F401,E402
import video_studio.agents.fact_check.agent  # noqa: F401,E402
import video_studio.agents.critic.agent  # noqa: F401,E402
import video_studio.agents.asset.agent  # noqa: F401,E402
import video_studio.agents.retrieval.agent  # noqa: F401,E402
import video_studio.agents.visual.agent  # noqa: F401,E402
import video_studio.agents.editing.agent  # noqa: F401,E402
import video_studio.agents.voice.agent  # noqa: F401,E402
import video_studio.agents.audio.agent  # noqa: F401,E402
import video_studio.agents.subtitle.agent  # noqa: F401,E402
import video_studio.agents.thumbnail.agent  # noqa: F401,E402
import video_studio.agents.platform.agent  # noqa: F401,E402
import video_studio.agents.metadata.agent  # noqa: F401,E402
import video_studio.agents.compliance.agent  # noqa: F401,E402
import video_studio.agents.qa.agent  # noqa: F401,E402
import video_studio.agents.analyst.agent  # noqa: F401,E402
import video_studio.agents.claim_extractor.agent  # noqa: F401,E402  V2
import video_studio.agents.evidence.agent  # noqa: F401,E402  V2
import video_studio.agents.conflict_detector.agent  # noqa: F401,E402  V2
import video_studio.agents.base  # noqa: F401,E402
from video_studio.agents.base import AGENTS  # noqa: E402

# ---------------- 6-A/M2：让 mock 管线产出**合规旁白** ----------------
# 背景：mock 配置的脚本计划 15 s/段，而真实 TTS 对该文本只产出约 4.2 s ⇒ 成片会在 17 s 时间轴里
# 留下约 13 s 尾静音 —— 实测证明这正属 6-A/M2 授权点名的「短旁白 / 成片静音」违约类
# （见 docs/regression_2x/logs/phase6a_m2_shortfilm_probe.json：历史同类成片尾静音 13.26 s / 78%）。
# 本用例验证的是**全管线接线**，故把 TTS 工具替换为"按计划时长合成的本地旁白"，
# 使成片本身合规（真实 TTS 路径由 phase2e/phase3a 证据步骤覆盖）。
# 这是 6-A/M2 的**测试契约更新**：旁白覆盖率必须达标，短旁白不再被当作合法完成。
import subprocess as _sp  # noqa: E402
import video_studio.tools.tts_tool as _tts_mod  # noqa: E402

_PLANNED_NARRATION_S = 16.0          # 时间轴 17 s（计划 15 s + 2 s 时间基），留 1 s 尾窗
_FFMPEG = str(ROOT / "bin" / "ffmpeg.exe")


def _fixture_tts_execute(self, inputs, ctx):
    out = Path(ctx.project_dir) / inputs["output"]
    out.parent.mkdir(parents=True, exist_ok=True)
    r = _sp.run([_FFMPEG, "-y", "-v", "error", "-f", "lavfi", "-i",
                 "sine=frequency=440:duration={:.3f}".format(_PLANNED_NARRATION_S),
                 "-c:a", "libmp3lame", str(out)],
                capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError("fixture TTS failed: " + (r.stderr or "")[:200])
    return type("R", (), {"ok": True, "data": {"audio": inputs["output"]}})()


_tts_mod.TTSTool.execute = _fixture_tts_execute


def main() -> int:
    workspace = Path(tempfile.mkdtemp(prefix="vs_pipe_"))
    db = Database(workspace / "state.db")
    # 5-L：离线全管线用例**显式**使用独立 mock 配置；生产默认 `config/config.json` 为真实 DeepSeek
    config = json.loads((ROOT / "config" / "config.mock.json").read_text(encoding="utf-8"))
    rules = json.loads((ROOT / "config" / "rules.json").read_text(encoding="utf-8"))
    mock = MockLLM(config["llm"]["mock"]["responses"], config["llm"]["mock"]["default"])
    engine = Engine(db, Router(config["llm"], mock), rules, workspace / "projects", config, AGENTS)
    hitl = HITL(engine, config)

    checks = []

    def check(name, cond, detail=""):
        checks.append((name, cond))
        print(f"{'PASS' if cond else 'FAIL'}  {name} {detail}")

    check("25 个 Agent 已注册", len(AGENTS) == 25, f"(实际 {len(AGENTS)})")

    pid = engine.create_project("做一期鲸鱼娘皮肤幕后视频", "pipeline-demo")

    # 按标准管线创建全部任务（V2：22 任务 + p2b 核查 4 任务 = 26）
    id_by_type = {}
    created = 0
    for spec in build_pipeline_task_specs(pid):
        deps = [id_by_type[d] for d in spec["depends_on"] if d in id_by_type]
        tid = engine.create_task(pid, spec["task_type"], spec["agent_role"],
                                 dependencies=deps, inputs={"phase": spec["phase"]},
                                 requires_approval=spec["requires_approval"])
        id_by_type[spec["task_type"]] = tid
        created += 1
    check("标准管线任务全部创建", created == 26, f"({created} 个)")

    # 调度循环 + 模拟人工批准全部闸门（任务级 + Claim 级）
    rounds = 0
    while rounds < 30:
        rounds += 1
        for t in db.list_tasks(pid, "NEEDS_REVIEW"):
            hitl.decide(t["task_id"], "approve", "集成测试自动批准")
        for c in db.list_claims(pid, "NEEDS_HUMAN"):
            hitl.decide_claim(c["claim_id"], "approve", "集成测试自动批准")
        n = engine.run_cycle(pid)
        if n == 0 and not db.list_tasks(pid, "NEEDS_REVIEW"):
            break

    # 终态断言
    tasks = db.list_tasks(pid)
    by_type = {t["task_type"]: t for t in tasks}
    succeeded = [t for t in tasks if t["status"] == "SUCCEEDED"]
    blocked = [t for t in tasks if t["status"] == "BLOCKED"]
    print(f"\n调度轮数: {rounds}，完成: {len(succeeded)}，阻塞: {len(blocked)}，总任务: {len(tasks)}")
    check("全部任务完成（无阻塞）", len(succeeded) == 26, f"(完成 {len(succeeded)}/26, 阻塞 {len(blocked)})")

    render = by_type.get("render")
    check("render 成功", render is not None and render["status"] == "SUCCEEDED")
    if render and render["status"] == "SUCCEEDED":
        art = db.get_artifact(render["artifacts"][0])
        with open(art["path"], encoding="utf-8") as fh:
            out_rel = json.load(fh)["output"]
        out_path = engine.project_dir(pid) / out_rel
        check("成片文件存在", out_path.exists(), f"({out_path.name})")
        check("成片大小合理", out_path.stat().st_size > 10000, f"({out_path.stat().st_size} bytes)")

    qa = by_type.get("qa")
    if qa and qa["artifacts"]:
        art = db.get_artifact(qa["artifacts"][0])
        with open(art["path"], encoding="utf-8") as fh:
            report = json.load(fh)
        check("QA 结论 pass", report.get("verdict") == "pass", f"({report.get('verdict')})")

    compliance = by_type.get("compliance")
    if compliance and compliance["artifacts"]:
        art = db.get_artifact(compliance["artifacts"][0])
        with open(art["path"], encoding="utf-8") as fh:
            report = json.load(fh)
        check("合规 pass", report.get("verdict") == "pass")

    subtitle = by_type.get("subtitle")
    if subtitle and subtitle["artifacts"]:
        art = db.get_artifact(subtitle["artifacts"][0])
        with open(art["path"], encoding="utf-8") as fh:
            check("字幕含 SRT 条目", "--> " in json.load(fh)["srt"])

    # 事件与记忆
    events = db.events_since(pid, 0)
    types = {e["type"] for e in events}
    check("审批事件存在", "REVIEW_REQUESTED" in types and "REVIEW_DECIDED" in types)
    lessons = db.get_memories("experience", pid)
    check("分析师经验入库", len(lessons) >= 1, f"({len(lessons)} 条)")

    # 决策留痕
    decisions = db.conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
    check("人工决策留痕", decisions >= 3, f"({decisions} 条)")

    # ---------- Phase 8（Creator Style v3）：管线级下游隔离守卫 ----------
    # 扫描全部产物中**用户可见文本**，断言 v3 留存元数据既未成字段、也未成文本泄漏。
    # 说明（诚实边界）：本夹具的 mock 脚本默认不含 v3 字段，因此本守卫验证的是
    # "管线不会把 v3 元数据字段名/取值搬进用户可见文本"（防回归）；
    # "带 v3 取值的脚本仍不泄漏"由 strip_v2_test 的哨兵用例证明。
    V3_FIELD_NAMES = ("emotion_beat", "retention_device", "cta_plan", "hook_map", "hook_type",
                      "at_segment", "hook_interval_ok")
    USER_VISIBLE = ("voice_output", "subtitle_output", "metadata_output", "render_output",
                    "publish_output", "export_output", "qa_output", "compliance_output")
    leaks = []
    for t in tasks:
        if t["task_type"] not in USER_VISIBLE:
            continue
        for aid in t["artifacts"] or []:
            a = db.get_artifact(aid)
            try:
                txt = Path(a["path"]).read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for name in V3_FIELD_NAMES:
                if name in txt:
                    leaks.append((t["task_type"], Path(a["path"]).name, name))
    check("v3 下游隔离：用户可见产物无 v3 元数据字段名", not leaks, f"({leaks[:3]})")
    ass_files = list((engine.project_dir(pid) / "artifacts").glob("_captions_*.ass"))
    ass_text = "\n".join(f.read_text(encoding="utf-8", errors="replace") for f in ass_files)
    check("v3 下游隔离：烧录字幕源（ASS）无 v3 元数据字段名",
          bool(ass_files) and not any(n in ass_text for n in V3_FIELD_NAMES))

    failed = [c for c in checks if not c[1]]
    print(f"\n结果: {len(checks) - len(failed)}/{len(checks)} 通过")
    db.close()
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
