"""任务状态机与消息总线（V1：SQLite 驱动的同步调度）。

- 事件表即总线：append-only，可重放、可审计。
- 状态机：PENDING→DISPATCHED→RUNNING→SUCCEEDED/FAILED/BLOCKED/NEEDS_REVIEW，
  失败按 max_retries 自动重试，超限进入 BLOCKED 等待人工。
- 回退：以任务 lineage 定位，下游全部标记 SUPERSEDED，锚点任务以 version+1 重派。
- 崩溃恢复：recover() 把 RUNNING/DISPATCHED 标记 INTERRUPTED 并回队。
"""

from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path

from .ids import new_id

# 合法状态与转移规则
STATUSES = {
    "PENDING", "DISPATCHED", "RUNNING", "SUCCEEDED", "FAILED", "BLOCKED",
    "NEEDS_REVIEW", "SUPERSEDED", "INTERRUPTED",
}

TRANSITIONS = {
    "PENDING": {"DISPATCHED"},
    "DISPATCHED": {"RUNNING", "INTERRUPTED"},
    "RUNNING": {"SUCCEEDED", "FAILED", "NEEDS_REVIEW", "INTERRUPTED"},
    "FAILED": {"PENDING", "BLOCKED"},          # PENDING = 重试
    "BLOCKED": {"PENDING", "FAILED"},
    "NEEDS_REVIEW": {"SUCCEEDED", "FAILED", "PENDING"},   # 批/拒/改
    "SUPERSEDED": set(),
    "INTERRUPTED": {"PENDING"},
    "SUCCEEDED": set(),
}


class EngineError(Exception):
    pass


class Engine:
    """总调度核心：任务生命周期 + 派单 + 重试 + 回退 + 恢复。"""

    def __init__(self, db, router, rules: dict, workspace_root: Path, config: dict,
                 agent_registry: dict):
        self.db = db
        self.router = router
        self.rules = rules
        self.workspace_root = Path(workspace_root)
        self.config = config
        self.agents = agent_registry  # role -> Agent 实例

    # ---------------- 事件 ----------------
    def emit(self, project_id: str, type_: str, actor: str, task_id: str | None = None,
             payload: dict | None = None, human_visible: bool = False) -> int:
        return self.db.append_event(project_id, type_, actor, task_id, payload, human_visible)

    # ---------------- 项目 ----------------
    def create_project(self, goal: str, name: str | None = None) -> str:
        project_id = new_id("p")
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        project_dir = self.workspace_root / project_id
        for sub in ("artifacts", "media", "output"):
            (project_dir / sub).mkdir(parents=True, exist_ok=True)
        self.db.create_project(project_id, name or goal[:32], goal)
        self.emit(project_id, "PROJECT_CREATED", "human", payload={"goal": goal})
        self._write_manifest(project_id)
        return project_id

    def project_dir(self, project_id: str) -> Path:
        return self.workspace_root / project_id

    def _write_manifest(self, project_id: str) -> None:
        tasks = self.db.list_tasks(project_id)
        summary = {}
        for t in tasks:
            summary[t["status"]] = summary.get(t["status"], 0) + 1
        project = self.db.get_project(project_id)
        manifest = {
            "project_id": project_id,
            "name": project["name"],
            "goal": project["goal"],
            "status": project["status"],
            "task_summary": summary,
            "updated_at": project["updated_at"],
        }
        path = self.project_dir(project_id) / "manifest.json"
        path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---------------- 任务 ----------------
    def create_task(self, project_id: str, task_type: str, agent_role: str,
                    dependencies: list[str] | None = None, inputs: dict | None = None,
                    expected_output: dict | None = None, requires_approval: bool = False,
                    parent_task_id: str | None = None, lineage: list[str] | None = None,
                    max_retries: int | None = None, version: int = 1) -> str:
        if agent_role not in self.agents:
            raise EngineError(f"未知 agent_role: {agent_role}")
        task_id = new_id("t")
        retry_cfg = self.config.get("retry", {})
        self.db.insert_task({
            "task_id": task_id,
            "project_id": project_id,
            "parent_task_id": parent_task_id,
            "lineage": lineage or [],
            "task_type": task_type,
            "agent_role": agent_role,
            "status": "PENDING",
            "dependencies": dependencies or [],
            "inputs": inputs or {},
            "expected_output": expected_output or {},
            "requires_approval": requires_approval,
            "max_retries": max_retries if max_retries is not None else retry_cfg.get("default_max_retries", 2),
            "version": version,
        })
        self.emit(project_id, "TASK_CREATED", agent_role, task_id, {"task_type": task_type})
        self._write_manifest(project_id)
        return task_id

    def get_task(self, task_id: str) -> dict | None:
        return self.db.get_task(task_id)

    def transition(self, task_id: str, target: str, error: str | None = None) -> None:
        task = self.db.get_task(task_id)
        if task is None:
            raise EngineError(f"任务不存在: {task_id}")
        if target not in TRANSITIONS.get(task["status"], set()):
            raise EngineError(f"非法状态转移: {task['status']} -> {target} (task {task_id})")
        self.db.set_task_status(task_id, target, error)
        self.emit(task["project_id"], f"TASK_{target}", task["agent_role"], task_id,
                  {"from": task["status"], "error": error}, human_visible=target in ("BLOCKED", "NEEDS_REVIEW"))

    # ---------------- 产物 ----------------
    def write_artifact(self, project_id: str, task_id: str | None, type_: str,
                       content: dict | list | str, summary: str = "", version: int = 1,
                       license_: str | None = None) -> str:
        artifact_id = new_id("a")
        raw = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False, indent=2)
        suffix = "json"
        if isinstance(content, str) and not content.lstrip().startswith(("{", "[")):
            suffix = "md"
        path = self.project_dir(project_id) / "artifacts" / f"{artifact_id}.{suffix}"
        path.write_text(raw, encoding="utf-8")
        sha = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
        self.db.insert_artifact({
            "artifact_id": artifact_id,
            "project_id": project_id,
            "task_id": task_id,
            "type": type_,
            "path": str(path),
            "sha256": sha,
            "size": len(raw.encode("utf-8")),
            "provenance": {"agent": self.db.get_task(task_id)["agent_role"] if task_id else None},
            "license": license_,
            "version": version,
            "summary": summary,
        })
        self.emit(project_id, "ARTIFACT_CREATED", self.db.get_task(task_id)["agent_role"] if task_id else "system",
                  task_id, {"artifact_id": artifact_id, "type": type_})
        return artifact_id

    def attach_artifact(self, task_id: str, artifact_id: str) -> None:
        task = self.db.get_task(task_id)
        artifacts = list(task["artifacts"])
        if artifact_id not in artifacts:
            artifacts.append(artifact_id)
            self.db.update_task(task_id, artifacts=artifacts)

    # ---------------- 调度 ----------------
    # V2 第五阶段：Claim 审核闸门。存在 NEEDS_HUMAN 的 claim 时，
    # 以下生产环节任务不得派发——未经人工审核的 Claim 不能进入生产。
    CLAIM_GATE_BLOCKED = {
        "visual_plan", "asset_audit", "retrieval", "editing_plan",
        "voice", "subtitle", "audio_mix", "render", "thumbnail",
        "qa", "compliance", "critic_final", "platform", "metadata", "analytics",
    }

    def claim_gate_open(self, project_id: str) -> bool:
        """仅当项目内全部 claim 处于 PASSED 状态（VERIFIED/REJECTED）时放行。

        REJECTED = 人类已裁决（其重做链产生的新 claims 另行审核）；
        其余状态（NEEDS_HUMAN/UNVERIFIED/CHECKING/DISPUTED/UNSUPPORTED/FALSE）
        一律视为未通过审核，阻塞生产环节。
        """
        passed = {"VERIFIED", "REJECTED"}
        for claim in self.db.list_claims(project_id):
            if claim["status"] not in passed:
                return False
        return True

    def dispatchable(self, project_id: str) -> list[dict]:
        tasks = self.db.list_tasks(project_id)
        by_id = {t["task_id"]: t for t in tasks}
        gate_open = None
        ready = []
        for t in tasks:
            if t["status"] != "PENDING":
                continue
            deps_ok = all(by_id.get(d) is not None and by_id[d]["status"] == "SUCCEEDED" for d in t["dependencies"])
            if not deps_ok:
                continue
            if t["task_type"] in self.CLAIM_GATE_BLOCKED:
                if gate_open is None:
                    gate_open = self.claim_gate_open(project_id)
                if not gate_open:
                    continue  # 未审核 Claim 阻塞生产环节
            ready.append(t)
        return ready

    def run_cycle(self, project_id: str, limit: int = 20) -> int:
        """同步调度一轮：派发所有就绪任务并执行。返回本轮执行的任务数。"""
        count = 0
        for task in self.dispatchable(project_id):
            if count >= limit:
                break
            self.run_one(task["task_id"])
            count += 1
        self._write_manifest(project_id)
        return count

    def run_one(self, task_id: str) -> None:
        task = self.db.get_task(task_id)
        agent = self.agents.get(task["agent_role"])
        if agent is None:
            self.db.set_task_status(task_id, "FAILED", f"未注册 agent: {task['agent_role']}")
            return
        self.transition(task_id, "DISPATCHED")
        self.transition(task_id, "RUNNING")
        self.emit(task["project_id"], "TASK_STARTED", task["agent_role"], task_id)
        try:
            agent.run(self, task)
            current = self.db.get_task(task_id)
            # Agent 可能已自行处置本任务（如 Critic 回退把自己 SUPERSEDED）
            if current["status"] != "RUNNING":
                self._write_manifest(task["project_id"])
                return
            # 审批闸门：agent 完成后若需要审批 → NEEDS_REVIEW
            if task["requires_approval"]:
                self.transition(task_id, "NEEDS_REVIEW")
                self.emit(task["project_id"], "REVIEW_REQUESTED", task["agent_role"], task_id,
                          human_visible=True)
            else:
                self.transition(task_id, "SUCCEEDED")
        except Exception as exc:  # noqa: BLE001 —— 任何失败进入统一恢复策略
            self._handle_failure(task_id, str(exc))

    def _handle_failure(self, task_id: str, message: str) -> None:
        task = self.db.get_task(task_id)
        self.db.set_task_status(task_id, "FAILED", message[:2000])
        self.emit(task["project_id"], "TASK_FAILED", task["agent_role"], task_id,
                  {"error": message[:500]}, human_visible=True)
        if task["retry_count"] < task["max_retries"]:
            self.db.update_task(task_id, retry_count=task["retry_count"] + 1)
            self.db.set_task_status(task_id, "PENDING")
            self.emit(task["project_id"], "TASK_RETRYING", task["agent_role"], task_id,
                      {"retry_count": task["retry_count"] + 1})
        else:
            self.db.set_task_status(task_id, "BLOCKED")
            self.emit(task["project_id"], "TASK_BLOCKED", task["agent_role"], task_id,
                      {"error": message[:500]}, human_visible=True)

    # ---------------- 人工审批 ----------------
    def approve(self, task_id: str, state: str, comment: str = "", made_by: str = "human") -> None:
        """state: APPROVED / REJECTED / CHANGES_REQUESTED"""
        task = self.db.get_task(task_id)
        if task["status"] != "NEEDS_REVIEW":
            raise EngineError(f"任务不在待审状态: {task['status']}")
        self.db.update_task(task_id, approval={"state": state, "by": made_by, "comment": comment})
        self.db.insert_decision({
            "decision_id": new_id("d"),
            "project_id": task["project_id"],
            "node": f"{task['task_type']}_{state}",
            "made_by": made_by,
            "state": state,
            "rationale": comment,
            "artifact_snapshot": task["artifacts"],
        })
        self.emit(task["project_id"], "REVIEW_DECIDED", made_by, task_id, {"state": state})
        if state == "APPROVED":
            self.transition(task_id, "SUCCEEDED")
        elif state == "REJECTED":
            self.db.set_task_status(task_id, "BLOCKED", f"人工拒绝: {comment[:200]}")
        else:  # CHANGES_REQUESTED：原任务标 FAILED，新版本任务 PENDING 重做
            self.db.set_task_status(task_id, "FAILED", f"人工要求修改: {comment[:200]}")
            self.emit(task["project_id"], "TASK_ROLLED_BACK", "human", task_id, {"reason": comment[:200]})
            self.redo(task_id)

    def redo(self, task_id: str) -> str:
        """以 version+1 重建同一任务（回退重做的核心）。原任务记录保持不变。

        3.x Phase 1 修复：原实现只建新任务，**没有把下游任务的 dependencies 指过去**，
        于是旧任务停在 BLOCKED/FAILED，下游 `deps_ok` 永远为假 → 链路永久停摆
        （真实复现：C 组 render 重做成功后 7 个下游任务 40 轮不派发）。
        现在同步重连下游依赖：old task_id → new task_id（不改变任何闸门语义）。
        """
        task = self.db.get_task(task_id)
        new_id = self.create_task(
            task["project_id"], task["task_type"], task["agent_role"],
            dependencies=task["dependencies"], inputs=task["inputs"],
            expected_output=task["expected_output"],
            requires_approval=bool(task["requires_approval"]),
            parent_task_id=task["parent_task_id"], lineage=list(task["lineage"]),
            max_retries=task["max_retries"], version=task["version"] + 1,
        )
        self.rewire_dependents(task["project_id"], task_id, new_id)
        return new_id

    def rewire_dependents(self, project_id: str, old_id: str, new_id: str) -> int:
        """把指向 old_id 的下游依赖改指 new_id（返回改动条数）。"""
        changed = 0
        for t in self.db.list_tasks(project_id):
            deps = t.get("dependencies") or []
            if old_id in deps:
                self.db.update_task(t["task_id"],
                                    dependencies=[new_id if d == old_id else d for d in deps])
                self.emit(project_id, "TASK_DEPENDENCY_REWIRED", "orchestrator", t["task_id"],
                          {"old": old_id, "new": new_id})
                changed += 1
        return changed

    def rollback_to(self, task_id: str) -> None:
        """锚点任务重做，其全部下游标记 SUPERSEDED。"""
        anchor = self.db.get_task(task_id)
        for t in self.db.list_tasks(anchor["project_id"]):
            if t["task_id"] == task_id:
                continue
            if task_id in t["lineage"] or task_id in t["dependencies"]:
                self.db.set_task_status(t["task_id"], "SUPERSEDED")
                self.emit(t["project_id"], "TASK_ROLLED_BACK", "orchestrator", t["task_id"],
                          {"anchor": task_id})
        self.redo(task_id)

    # ---------------- 崩溃恢复 ----------------
    def recover(self, project_id: str | None = None) -> int:
        """重启后调用：把中断任务回队（幂等重跑由 agent 保证）。"""
        recovered = 0
        tasks = self.db.list_tasks(project_id) if project_id else [
            t for p in self._all_projects() for t in self.db.list_tasks(p["project_id"])
        ]
        for t in tasks:
            if t["status"] in ("DISPATCHED", "RUNNING"):
                self.db.set_task_status(t["task_id"], "INTERRUPTED")
                self.db.set_task_status(t["task_id"], "PENDING")
                self.emit(t["project_id"], "TASK_INTERRUPTED", "system", t["task_id"])
                recovered += 1
        return recovered

    def _all_projects(self) -> list[dict]:
        return [dict(r) for r in self.db.conn.execute("SELECT * FROM projects").fetchall()]
