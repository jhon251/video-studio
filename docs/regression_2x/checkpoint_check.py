"""Checkpoint check: stuck tasks + DB readability + syntax of Phase 2-E files."""
import ast
import sqlite3
import sys
from pathlib import Path

ROOT = Path(r"C:\mp4agent\video-studio")
DB = ROOT / "projects" / "video_studio.db"
SQL = """select project_id, task_id, task_type, status, updated_at from tasks
         where status in ('RUNNING','DISPATCHED') order by updated_at desc"""
con = sqlite3.connect(str(DB))
con.row_factory = sqlite3.Row
stuck = [dict(r) for r in con.execute(SQL)]
print("db size MB: {:.1f}".format(DB.stat().st_size / 1e6))
print("stuck tasks (RUNNING/DISPATCHED):", len(stuck))
for r in stuck[:10]:
    print("   ", r["project_id"], r["task_id"], r["task_type"], r["status"])
n_proj = con.execute("select count(*) from projects").fetchone()[0]
n_task = con.execute("select count(*) from tasks").fetchone()[0]
n_art = con.execute("select count(*) from artifacts").fetchone()[0]
print("projects={} tasks={} artifacts={}".format(n_proj, n_task, n_art))
con.close()

print("\nsyntax check (Phase 2-E touched files):")
files = ["src/video_studio/tools/material_provider.py",
         "src/video_studio/tools/provider_wikimedia.py",
         "src/video_studio/agents/retrieval/agent.py",
         "src/video_studio/agents/editing/agent.py",
         "src/video_studio/core/materials.py",
         "tests/material_provider_test.py",
         "tests/material_taxonomy_test.py",
         "docs/regression_2x/phase2e_real_provider.py",
         "docs/regression_2x/phase2e_failure_paths.py",
         "docs/regression_2x/phase2d_boundary_matrix.py"]
bad = []
for f in files:
    try:
        ast.parse((ROOT / f).read_text(encoding="utf-8"))
        print("  OK  ", f)
    except SyntaxError as exc:
        bad.append(f)
        print("  FAIL", f, exc)
sys.exit(1 if bad else 0)
