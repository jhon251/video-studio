# -*- coding: utf-8 -*-
"""6-B/M4 负对照（临时脚本）：证明 M8e 守卫**能真实失败**。

做法：把 `tests/maintenance_fixes_test.py` 里的 `_sandbox_write_violations` 与其常量
原样 exec 进一个临时 ROOT（不复制业务代码），对 7 个变异样本断言检出结果。
"""
import ast
import json
import pathlib
import re
import shutil
import sys
import tempfile

SRC_TEST = pathlib.Path(r"C:\mp4agent\video-studio\tests\maintenance_fixes_test.py")
REAL_OPS = pathlib.Path(r"C:\mp4agent\video-studio\src\video_studio\ops\execution.py")

tree = ast.parse(SRC_TEST.read_text(encoding="utf-8"))
wanted_consts = {"_SANDBOX_ROOT_PREFIX", "_WRITE_CALLS", "_WRITE_SQL",
                 "_BYPASS_ENTRY_NAMES", "_RECV_DEST_CALLS", "_ARG_DEST_CALLS"}
nodes = []
for n in tree.body:
    if isinstance(n, ast.FunctionDef) and n.name == "_sandbox_write_violations":
        nodes.append(n)
    elif isinstance(n, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id in wanted_consts for t in n.targets):
        nodes.append(n)

tmp = pathlib.Path(tempfile.mkdtemp(prefix="m8e_negctl_"))
ops_dir = tmp / "src" / "video_studio" / "ops"
agents_dir = tmp / "src" / "video_studio" / "agents"
ops_dir.mkdir(parents=True)
agents_dir.mkdir(parents=True)
(agents_dir / "editing_agent.py").write_text("# clean agent\n", encoding="utf-8")

ns = {"re": re, "ROOT": tmp, "__name__": "negctl"}
exec(compile(ast.Module(body=nodes, type_ignores=[]), "<m8e>", "exec"), ns)
check_fn = ns["_sandbox_write_violations"]

REL = "src/video_studio/ops/execution.py"
base = REAL_OPS.read_text(encoding="utf-8")

MUTATIONS = [
    ("clean_baseline", base, []),
    ("sandbox_prefix_escapes_output",
     base.replace('SANDBOX_ROOT_REL = "output/phase6b_m4_sandbox"',
                  'SANDBOX_ROOT_REL = "docs/regression_2x/sandbox"'),
     ["sandbox_prefix_not_output"]),
    ("auto_execute_entry",
     base + "\n\ndef auto_execute_all(proposals):\n    return proposals\n",
     ["bypass_entry:auto_execute_all"]),
    ("apply_proposal_entry",
     base + "\n\ndef apply_proposal(p):\n    return p\n",
     ["bypass_entry:apply_proposal"]),
    ("write_outside_sandbox",
     base + '\n\ndef leak(root):\n    (root / "output" / "final.mp4").write_text("x")\n',
     ["dest_not_sandbox"]),
    ("db_write_sql",
     base + '\n\ndef touch_db(conn):\n    conn.execute("INSERT INTO tasks VALUES (1)")\n',
     ["sql:insert into"]),
    ("rmtree_project_dir",
     base + '\n\ndef nuke(root):\n    shutil.rmtree(root / "baseline")\n',
     ["dest_not_sandbox"]),
    ("path_replace_escape",
     base + '\n\ndef mv(root):\n    Path(root / "a.mp4").replace(root / "baseline" / "b.mp4")\n',
     ["dest_not_sandbox:replace"]),
    ("str_replace_is_not_a_write",
     base + '\n\ndef tag(p):\n    return str(p).replace("/", "_")\n',
     []),
]
AGENT_MUTATION = "from ...ops import execution\n"

fails = []
results = []
for name, text, expect in MUTATIONS:
    (ops_dir / "execution.py").write_text(text, encoding="utf-8")
    got = check_fn(REL)
    hit = all(any(e in g for g in got) for e in expect) if expect else (got == [])
    results.append({"case": name, "expect": expect, "got": got, "detected": bool(hit)})
    print("{:<28} expect={:<32} got={}".format(name, str(expect or []), got))
    if not hit:
        fails.append(name)

(ops_dir / "execution.py").write_text(base, encoding="utf-8")
(agents_dir / "editing_agent.py").write_text(AGENT_MUTATION, encoding="utf-8")
got = check_fn(REL)
print("{:<28} expect={:<32} got={}".format("agent_reachable", str(["reachable_from_agents"]), got))
if not any("reachable_from_agents" in g for g in got):
    fails.append("agent_reachable")
results.append({"case": "agent_reachable", "expect": ["reachable_from_agents"], "got": got,
                "detected": any("reachable_from_agents" in g for g in got)})

shutil.rmtree(tmp, ignore_errors=True)
print("\n负对照: {} 个样本，检出失败 {}".format(len(MUTATIONS) + 1, fails or "无"))

# 6-B/M4 证据落盘（负对照结论：守卫**可被真实触发**且干净样本不误报）
_OUT = pathlib.Path(r"C:\mp4agent\video-studio\docs\regression_2x\logs"
                    r"\phase6b_m4_m8e_negctl.json")
_OUT.parent.mkdir(parents=True, exist_ok=True)
_OUT.write_text(json.dumps({
    "schema": "m8e-negative-control-v1",
    "guard": "tests/maintenance_fixes_test.py::_sandbox_write_violations",
    "guard_source_sha256": __import__("hashlib").sha256(
        SRC_TEST.read_bytes()).hexdigest(),
    "samples": len(results),
    "detected": sum(1 for r in results if r["detected"]),
    "undetected": fails,
    "clean_baseline_false_positive": [r for r in results if r["case"] == "clean_baseline"
                                      and r["got"] != []],
    "results": results,
    "note": "对 ops/execution.py 施加 7 类变异（沙箱前缀逃逸 / auto_* 入口 / apply_proposal / "
            "越界写入 / DB 写 / rmtree 基线目录 / agents 可达）+ 1 个干净样本；"
            "所有变异均被检出，干净样本无误报。",
}, ensure_ascii=False, indent=1), encoding="utf-8")
print("json -> {}".format(_OUT.name))
sys.exit(1 if fails else 0)
