"""Verify the working_context fix: upstream artifact content present, no cross-project notes."""
import json
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
from video_studio.memory.repo import Memory  # noqa: E402

pid = sys.argv[1] if len(sys.argv) > 1 else "p_5125df7514f3"
tt = sys.argv[2] if len(sys.argv) > 2 else "script"


class DB:
    def __init__(self, p):
        self.c = sqlite3.connect(p)
        self.c.row_factory = sqlite3.Row

    def get_project(self, i):
        return dict(self.c.execute("select * from projects where project_id=?", (i,)).fetchone())

    def get_task(self, i):
        r = self.c.execute("select * from tasks where task_id=?", (i,)).fetchone()
        return dict(r) if r else None

    def get_artifact(self, i):
        r = self.c.execute("select * from artifacts where artifact_id=?", (i,)).fetchone()
        return dict(r) if r else None

    def get_memories(self, kind=None, project_id=None, agent_role=None, limit=20):
        q, a = "select * from memories where 1=1", []
        if kind:
            q += " and kind=?"
            a.append(kind)
        if project_id:
            q += " and project_id=?"
            a.append(project_id)
        if agent_role:
            q += " and agent_role=?"
            a.append(agent_role)
        q += " order by rowid desc limit ?"
        a.append(limit)
        return [dict(r) for r in self.c.execute(q, a)]


class Eng:
    pass


db = DB(str(ROOT / "projects" / "video_studio.db"))
eng = Eng()
eng.db = db
t = [dict(r) for r in db.c.execute(
    "select * from tasks where project_id=? and task_type=?", (pid, tt))][0]
ctx = Memory(db).working_context(t, eng)
print("任务:", tt, "| 上下文长度:", len(ctx), "字符")
print("含 structure 产物内容:", "structure_output" in ctx)
print("含 cross-project 黑洞笔记:", "黑洞" in ctx)
print("含本项目目标片段:", ("普通观众" in ctx) or ("脑机接口" in ctx))
print()
print(ctx[:600])
