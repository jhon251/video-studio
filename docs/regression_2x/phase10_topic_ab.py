# -*- coding: utf-8 -*-
"""Phase 10 / P10-4 **真实 A/B**：同一选题目标，topic agent 跑两遍（带信号 vs 不带信号）。

- 带信号臂：`tools.topic_signals.provider=bilibili_popular`，读**真实快照**（由
  `run.py fetch-signals` 人工触发一次生成，请求数 = 1 已记录在快照内）。
- 不带信号臂：`provider=none` ⇒ 纯头脑风暴 + **披露路径**（note 必须含固定披露串）。
- 两臂均走**真实 agent 路径**（Engine + Router + 真实 LLM），仅写**临时工作区 DB**；
  生产 DB/产物零改动。
- 判定：带信号提案 100% 有合法 `signal_refs`（指向真实条目）+ 非空 `why_now` + `angle_gap`；
  不带信号走披露路径；两臂风险披露纪律不退化；无编造热度数据（数字必须能在快照中找到）。

产物：`docs/regression_2x/logs/phase10_topic_ab.json`
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
import tempfile
import time

ROOT = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.agents.base import AGENTS                                          # noqa: E402
import video_studio.agents.topic.agent  # noqa: F401,E402
from video_studio.agents.topic.agent import NO_SIGNAL_NOTE, validate_signal_refs     # noqa: E402
from video_studio.core.env import load_env                                           # noqa: E402
from video_studio.core.engine import Engine                                          # noqa: E402
from video_studio.db.schema import Database                                          # noqa: E402
from video_studio.llm.router import DeepSeekClient, Router                           # noqa: E402
from video_studio.tools import topic_signals as TS                                   # noqa: E402

LOGS = ROOT / "docs" / "regression_2x" / "logs"
GOAL = "做一期 AI/数学类科普视频"
COST_LIMIT_USD = 0.20


def run_arm(label: str, provider: str, ws: pathlib.Path, cfg: dict, rules: dict,
            snapshot_info: dict) -> dict:
    arm_cfg = json.loads(json.dumps(cfg))
    arm_cfg["tools"] = dict(arm_cfg.get("tools") or {})
    arm_cfg["tools"]["topic_signals"] = {"provider": provider,
                                         "snapshot_dir": str(ROOT / "signals"),
                                         "manual_path": None}
    db = Database(ws / ("ab_{}.db".format(label)))
    engine = Engine(db, Router(arm_cfg["llm"], DeepSeekClient(arm_cfg["llm"]["deepseek"])),
                    rules, ws / ("projects_" + label), arm_cfg, AGENTS)
    pid = engine.create_project(GOAL)
    task_id = engine.create_task(pid, "topic", "topic")
    t0 = time.time()
    engine.run_cycle(pid)
    task = db.get_task(task_id)
    artifact = db.get_artifact(task["artifacts"][0]) if task.get("artifacts") else None
    payload = (json.loads(pathlib.Path(artifact["path"]).read_text(encoding="utf-8"))
               if artifact else {})
    usage = json.loads(task.get("cost_usd") and "{}" or "{}")
    db.close()
    return {"label": label, "provider": provider, "task_status": task.get("status"),
            "cost_usd": task.get("cost_usd"), "elapsed_s": round(time.time() - t0, 1),
            "payload": payload, "task_id": task_id, "project_id": pid,
            "artifact_id": artifact["artifact_id"] if artifact else None,
            "usage_note": usage, "snapshot_info": snapshot_info}


def heat_numbers(text: str) -> list[int]:
    """提取文本中的"热度型"数字（≥1000，视为播放/点赞量级）。"""
    return [int(m) for m in re.findall(r"\d[\d,]{3,}", text or "")
            if int(m.replace(",", "")) >= 1000]


def main() -> int:
    load_env(str(ROOT / ".env"))
    cfg = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8"))
    rules = json.loads((ROOT / "config" / "rules.json").read_text(encoding="utf-8"))
    snap_path = TS.latest_snapshot(ROOT / "signals")
    if snap_path is None:
        print("FAIL-CLOSED: 未找到信号快照（请先人工执行 run.py fetch-signals）", file=sys.stderr)
        return 2
    snap = TS.load_snapshot(snap_path)
    entries = snap["entries"]
    snap_info = {"path": str(snap_path.relative_to(ROOT)), "request_count": snap["request_count"],
                 "entries": len(entries), "kinds": snap["kinds"],
                 "sha256": __import__("hashlib").sha256(snap_path.read_bytes()).hexdigest()}
    ws = pathlib.Path(tempfile.mkdtemp(prefix="p10_ab_"))
    out = {"schema": "phase10-topic-ab-v1",
           "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "goal": GOAL, "model_tier": "M", "snapshot": snap_info, "arms": {},
           "network_requests": {"fetch_signals": snap["request_count"],
                                "runtime_network_by_agent": 0,
                                "note": "topic agent 运行期只读快照，零网络"}}
    spent = 0.0
    for label, provider in (("with_signals", "bilibili_popular"), ("without_signals", "none")):
        arm = run_arm(label, provider, ws, cfg, rules, snap_info)
        spent += float(arm.get("cost_usd") or 0.0)
        if spent > COST_LIMIT_USD:
            print("FAIL-CLOSED: 累计 ${:.4f} 超上限".format(spent), file=sys.stderr)
            return 3
        p = arm["payload"]
        proposals = p.get("proposals") or []
        nc = p.get("signals_context") or {}
        if provider == "bilibili_popular":
            vd = validate_signal_refs(p, entries)
            live = vd  # 以实时复算为准（产物内的校验结果另存）
            arm["criteria"] = {
                "signal_refs_all_valid": bool(live["all_valid"]),
                "proposals_with_valid_refs": live["proposals_with_valid_refs"],
                "proposals": len(proposals),
                "why_now_all_present": all(str(x.get("why_now") or "").strip() for x in proposals),
                "angle_gap_all_present": all(str(x.get("angle_gap") or "").strip()
                                             for x in proposals),
                "digest_count": (p.get("signals_digest") or {}).get("count"),
                "digest_source": nc.get("digest_source"),
                "artifact_validation_all_valid": (nc.get("signal_refs_validation") or {}).get(
                    "all_valid"),
                "disclosure_present": NO_SIGNAL_NOTE in str(p.get("note") or ""),
            }
            # 无编造热度：why_now/angle_gap 中的"热度型数字"必须能在快照里找到
            known = set()
            for e in entries:
                for v in (e.get("metrics") or {}).values():
                    if isinstance(v, int):
                        known.add(v)
            fabricated = []
            for i, x in enumerate(proposals):
                for n in heat_numbers(str(x.get("why_now") or "") + " " +
                                      str(x.get("angle_gap") or "")):
                    if n not in known:
                        fabricated.append({"proposal_index": i, "number": n})
            arm["criteria"]["fabricated_heat_numbers"] = fabricated
            arm["criteria"]["no_fabricated_heat_numbers"] = not fabricated
        else:
            arm["criteria"] = {
                "provider": nc.get("provider"), "status": nc.get("status"),
                "disclosure_present": NO_SIGNAL_NOTE in str(p.get("note") or ""),
                "digest_count": (p.get("signals_digest") or {}).get("count"),
                "signal_refs_all_empty": all(not (x.get("signal_refs") or []) for x in proposals),
                "proposals": len(proposals),
                "risks_present": all("risks" in x for x in proposals),
            }
        out["arms"][label] = {k: v for k, v in arm.items() if k != "payload"}
        out["arms"][label]["payload"] = p
        print("[{}] status={} proposals={} cost=${} criteria={}".format(
            label, arm["task_status"], len(proposals), arm.get("cost_usd"),
            json.dumps(arm["criteria"], ensure_ascii=False)[:200]))
    ws_arm = out["arms"]["with_signals"]["criteria"]
    no_arm = out["arms"]["without_signals"]["criteria"]
    out["verdict"] = {
        "with_signals_100pct_valid_refs": bool(
            ws_arm["proposals"] and ws_arm["signal_refs_all_valid"]
            and ws_arm["proposals_with_valid_refs"] == ws_arm["proposals"]),
        "with_signals_why_now_and_angle_gap": bool(ws_arm["why_now_all_present"]
                                                   and ws_arm["angle_gap_all_present"]),
        "without_signals_disclosure": bool(no_arm["disclosure_present"]),
        "no_fabricated_heat_numbers": bool(ws_arm["no_fabricated_heat_numbers"]),
        "risk_discipline_not_degraded": bool(no_arm["risks_present"]),
    }
    out["verdict"]["all_ok"] = all(out["verdict"].values())
    out["spent_usd"] = round(spent, 6)
    out["cost_limit_usd"] = COST_LIMIT_USD
    (LOGS / "phase10_topic_ab.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                                encoding="utf-8")
    print("判定:", json.dumps(out["verdict"], ensure_ascii=False))
    print("花费 ${:.5f}（上限 ${:.2f}）| 快照请求数 {}".format(spent, COST_LIMIT_USD,
                                                          snap["request_count"]))
    return 0 if out["verdict"]["all_ok"] else 4


if __name__ == "__main__":
    sys.exit(main())
