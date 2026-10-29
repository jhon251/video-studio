"""端到端冒烟测试（Mock LLM，无外部依赖）。

覆盖：项目创建 → 任务创建 → 调度执行（Topic 提案）→ 人工审批闸门 →
Critic 挑战（PASS 放行）→ 事件审计 → 崩溃恢复。
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

import video_studio.agents.orchestrator.agent  # noqa: F401,E402
import video_studio.agents.pm.agent  # noqa: F401,E402
import video_studio.agents.topic.agent  # noqa: F401,E402
import video_studio.agents.critic.agent  # noqa: F401,E402
from video_studio.agents.base import AGENTS  # noqa: E402

TOPIC_JSON = {
    "proposals": [
        {"title": "鲸鱼娘的一天：深海女仆工坊幕后",
         "angle": "以皮肤作者视角讲述创作过程",
         "audience": "DSH 用户与二次元爱好者",
         "value_proposition": "稀缺幕后内容 + 角色亲和力",
         "feasibility": "high",
         "risks": ["素材授权需确认"],
         "research_needs": ["皮肤制作流程资料"]},
    ],
    "summary": "选题提案",
    "confidence": 0.8,
    "note": "首次选题任务",
}
CRITIC_PASS = {
    "verdict": "PASS",
    "issues": [
        {"severity": "minor", "category": "omission",
         "claim": "选题未提及发布时间窗",
         "challenge": "是否与热点窗口冲突？",
         "required_action": "evidence"},
    ],
    "meta_note": "",
    "summary": "总体可放行，minor 项留档",
    "confidence": 0.7,
    "note": "挑战任务",
}

def main() -> int:
    workspace = Path(tempfile.mkdtemp(prefix="vs_smoke_"))
    db = Database(workspace / "state.db")
    mock = MockLLM(
        responses={
            "挑战报告": CRITIC_PASS,   # 顺序敏感：critic 消息里也含"选题"二字
            "选题": TOPIC_JSON,
        },
        default={"summary": "默认输出", "confidence": 0.5, "note": ""},
    )
    config = json.loads((ROOT / "config" / "config.example.json").read_text(encoding="utf-8"))
    rules = json.loads((ROOT / "config" / "rules.json").read_text(encoding="utf-8"))
    router = Router(config["llm"], mock)
    engine = Engine(db, router, rules, workspace / "projects", config, AGENTS)
    hitl = HITL(engine, config)

    checks = []

    def check(name: str, cond: bool, detail: str = ""):
        checks.append((name, cond, detail))
        print(f"{'PASS' if cond else 'FAIL'}  {name} {detail}")

    # 1. 项目创建
    pid = engine.create_project("做一期鲸鱼娘皮肤幕后视频", "smoke")
    project = db.get_project(pid)
    check("项目创建", project is not None and project["goal"].startswith("做一期"))

    # 2. 选题任务（闸门任务）
    t_topic = engine.create_task(pid, "topic", "topic", requires_approval=True,
                                 inputs={"direction": "鲸鱼娘皮肤幕后"})
    check("选题任务创建", db.get_task(t_topic)["status"] == "PENDING")

    # 3. 调度一轮：topic 运行 → NEEDS_REVIEW
    n = engine.run_cycle(pid)
    t = db.get_task(t_topic)
    check("调度执行选题", t["status"] == "NEEDS_REVIEW", f"(status={t['status']})")
    check("产物落盘", len(t["artifacts"]) == 1, f"({t['artifacts']})")
    art = db.get_artifact(t["artifacts"][0])
    check("产物文件存在", Path(art["path"]).exists())
    check("成本已记录", t["model_used"] is not None and t["cost_usd"] >= 0)

    # 4. 人工审批：approve
    hitl.decide(t_topic, "approve", "方向OK")
    t = db.get_task(t_topic)
    check("审批通过", t["status"] == "SUCCEEDED", f"(status={t['status']})")
    check("决策留痕", len(db.conn.execute("SELECT 1 FROM decisions").fetchall()) == 1)

    # 5. Critic 挑战（依赖 topic，目标=选题产物）
    t_critic = engine.create_task(pid, "critic", "critic", dependencies=[t_topic],
                                  inputs={"target_artifacts": t["artifacts"]})
    engine.run_cycle(pid)
    tc = db.get_task(t_critic)
    check("Critic 放行", tc["status"] == "SUCCEEDED", f"(status={tc['status']})")

    # 6. 事件审计
    events = db.events_since(pid, 0)
    types = [e["type"] for e in events]
    check("事件齐全", all(k in types for k in
                          ["PROJECT_CREATED", "TASK_CREATED", "TASK_RUNNING", "TASK_SUCCEEDED",
                           "TASK_NEEDS_REVIEW", "REVIEW_DECIDED", "CHALLENGE_RAISED", "ARTIFACT_CREATED"]),
          f"({len(events)} 条)")

    # 7. 崩溃恢复：人为制造中断任务
    t2 = engine.create_task(pid, "topic", "topic", requires_approval=True,
                            inputs={"direction": "第二个选题"})
    db.set_task_status(t2, "RUNNING")
    n = engine.recover(pid)
    check("崩溃恢复", n >= 1 and db.get_task(t2)["status"] == "PENDING", f"(恢复{n}个)")

    # 8. manifest 存在
    check("manifest.json", (engine.project_dir(pid) / "manifest.json").exists())

    failed = [c for c in checks if not c[1]]
    print(f"\n结果: {len(checks) - len(failed)}/{len(checks)} 通过")
    db.close()
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
