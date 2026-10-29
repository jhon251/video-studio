"""记忆系统：7 层记忆的 V1 实现（repository + 上下文装配器）。

kind 约定：project / agent / rule / experience / user_pref / knowledge / task_note
"""

from __future__ import annotations

import json


def _as_list(v):
    """DB 里的 inputs/dependencies/artifacts 可能是 JSON 文本；统一成 list/dict。"""
    if isinstance(v, str):
        try:
            v = json.loads(v)
        except json.JSONDecodeError:
            return []
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def _as_dict(v):
    if isinstance(v, str):
        try:
            v = json.loads(v)
        except json.JSONDecodeError:
            return {}
    return v if isinstance(v, dict) else {}


class Memory:
    def __init__(self, db):
        self.db = db

    def put(self, project_id: str | None, kind: str, key: str, content: str,
            agent_role: str | None = None) -> int:
        return self.db.put_memory(project_id, kind, key, content, agent_role)

    def get(self, kind: str | None = None, project_id: str | None = None,
            agent_role: str | None = None, limit: int = 20) -> list[dict]:
        return self.db.get_memories(kind, project_id, agent_role, limit)

    # ---------------- 上下文装配器 ----------------
    def working_context(self, task: dict, engine, max_artifact_chars: int = 6000) -> str:
        """为一个任务装配上下文：项目摘要 + 输入产物（含内容）+ Agent 自我记忆。

        3.x Phase 1 修复（主题一致性）：
          ① 历史缺陷：任务 inputs 只带 {"phase": "..."}，没有任何产物引用，
             下游 agent 拿不到上游内容（structure 看不到 topic、script 看不到 structure…），
             只能靠项目目标与模型自造内容；
          ② 历史缺陷：agent 自我记忆用 project_id=None 取**跨项目**最近 3 条，
             上一项目的主题（实测为黑洞/脑机接口）会泄漏进本项目上下文，造成主题漂移；
          ③ 把 "p1_structure" 这类阶段名误当产物引用，产生 "(引用缺失)" 噪声。
        现在：依赖任务的产物内容按上限注入；自我记忆仅限本项目；只把 a_* 视作产物引用。
        """
        parts = []
        project = engine.db.get_project(task["project_id"])
        parts.append(f"# 项目目标\n{project['goal']}")
        # 相关已确认决策
        decisions = self.get("project", task["project_id"], limit=10)
        if decisions:
            parts.append("# 已确认决策摘要\n" + "\n".join(
                f"- {d['key']}: {d['content'][:120]}" for d in decisions))
        # 输入产物：显式引用（a_*）+ 依赖任务产物，内容按上限注入
        parts.append("# 输入产物")
        refs = []
        for v in _as_dict(task.get("inputs")).values():
            for ref in _as_list(v):
                if isinstance(ref, str) and ref.startswith("a_"):
                    refs.append(ref)
        dep_arts = []
        for dep in _as_list(task.get("dependencies")):
            dep_task = engine.db.get_task(dep)
            if dep_task:
                dep_arts.extend(a for a in _as_list(dep_task.get("artifacts"))
                                if isinstance(a, str))
        seen_art = set()
        for artifact_id in refs + dep_arts:
            if artifact_id in seen_art:
                continue
            seen_art.add(artifact_id)
            art = engine.db.get_artifact(artifact_id)
            if art is None:
                parts.append(f"- (引用缺失) {artifact_id}")
                continue
            parts.append(f"- [{artifact_id}] {art['type']} :: {(art.get('summary') or '')[:200]}")
            try:
                with open(art["path"], encoding="utf-8") as fh:
                    content = fh.read()[:max_artifact_chars]
                parts.append(f"<artifact id='{artifact_id}' type='{art['type']}'>\n{content}\n</artifact>")
            except (OSError, KeyError):
                pass
        # Agent 自我记忆：**仅本项目**（跨项目会带来主题污染）
        notes = self.get("agent_note", task["project_id"], task["agent_role"], limit=3)
        if notes:
            parts.append("# 我的经验（本项目）\n" + "\n".join(f"- {n['content'][:200]}" for n in notes))
        return "\n\n".join(parts)

    def project_milestone(self, engine, project_id: str) -> str:
        """审批闸门处生成里程碑摘要（替代全量历史）。"""
        tasks = engine.db.list_tasks(project_id)
        lines = []
        for t in tasks:
            if t["status"] in ("SUCCEEDED", "NEEDS_REVIEW"):
                lines.append(f"- [{t['status']}] {t['task_type']} ({t['agent_role']}) "
                             f"artifacts={len(t['artifacts'])} confidence={t['confidence']}")
        return "\n".join(lines) or "(尚无完成的任务)"
