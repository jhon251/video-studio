"""2.x baseline regression driver (ASCII source only; prompts come from UTF-8 JSON).

Per round: approve pending claims (V2 claim gate) -> approve task gates -> redo BLOCKED once -> run.
Finally: locate the produced draft.mp4 per project and verify it with ffprobe + sha256.

Usage: python docs/regression_2x/run_all_tests.py
"""
import hashlib
import json
import re
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
LOGS = ROOT / "docs" / "regression_2x" / "logs"
LOGS.mkdir(parents=True, exist_ok=True)
FFPROBE = ROOT / "bin" / "ffprobe.exe"
PROMPTS = json.loads((ROOT / "docs" / "regression_2x" / "prompts.json").read_text(encoding="utf-8"))
redone = set()


def log(msg, prefix):
    line = str(msg)
    print(line, flush=True)
    with (LOGS / "{}_loop2.log".format(prefix)).open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


MOCK_CFG = "config/config.mock.json"   # 5-L：机械 E2E 离线用例显式 mock（生产默认不含 llm.mock）

# ---------------- 6-A/M2：机械 E2E 改用「配音计划模式」--------------
# 背景：mock 脚本计划 15 s/段，而真实 TTS 只产出约 4.2 s ⇒ 成片会有约 13 s 尾静音
# （实测见 logs/phase6a_m2_shortfilm_probe.json：同类历史成片尾静音 13.26 s/78%），
# 属 6-A/M2 授权点名的「短旁白 / 成片静音」违约类，渲染前硬门按设计会阻断。
# 机械 E2E 验证的是**任务生命周期与管线接线**，故在**临时配置**（不动基线 config）里
# 把 TTS provider 设为 none，走产线既有的配音计划模式：渲染仍真实发生（占位音轨全长），
# 成片与 2 流探测等断言照旧；旁白完整性由专门用例与证据步骤覆盖。
_CFG_TMP = Path(tempfile.mkdtemp(prefix="vs_e2e_cfg_")) / "config.mock.planonly.json"
_cfg = json.loads((ROOT / MOCK_CFG).read_text(encoding="utf-8"))
_cfg.setdefault("tools", {}).setdefault("tts", {})["provider"] = "none"
_CFG_TMP.write_text(json.dumps(_cfg, ensure_ascii=False, indent=1), encoding="utf-8")
MOCK_CFG = str(_CFG_TMP)


def cli(*args):
    p = subprocess.run([sys.executable, "run.py", "--config", MOCK_CFG, *args], cwd=str(ROOT),
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def rows(text, prefix_char):
    out = []
    for ln in text.splitlines():
        if re.match(r"^\|\s*" + prefix_char, ln):
            out.append([c.strip() for c in ln.split("|")])
    return out


def claim_gate(pid, prefix):
    rc, out = cli("claims", pid)
    (LOGS / "{}_claims_last.log".format(prefix)).write_text(out, encoding="utf-8")
    approved = []
    for f in rows(out, "c_"):
        if len(f) >= 9 and f[7]:                      # col 7 = 待人工
            rc2, o2 = cli("approve-claim", f[1], "--comment", "2.x baseline regression")
            approved.append("{}|{}|{}".format(f[1], f[4], o2.strip().splitlines()[-1][:60]))
    if approved:
        log("  approve-claim: " + " ; ".join(approved), prefix)
    return len(approved)


def loop(pid, prefix, max_rounds=40):
    log("=== [{}] project={} start ===".format(prefix, pid), prefix)
    for i in range(1, max_rounds + 1):
        claim_gate(pid, prefix)
        rc, out = cli("status", pid)
        (LOGS / "{}_status2_r{}.log".format(prefix, i)).write_text(out, encoding="utf-8")
        review, blocked, active, ok = [], [], 0, 0
        for f in rows(out, "t_"):
            if len(f) < 6:
                continue
            st = f[4]
            if st == "NEEDS_REVIEW":
                review.append(f[1])
            elif st in ("PENDING", "READY", "RUNNING", "DISPATCHED"):
                active += 1
            elif st == "SUCCEEDED":
                ok += 1
            elif st in ("BLOCKED", "FAILED"):
                blocked.append("{}|{}|{}".format(f[1], st, f[8] if len(f) > 8 else ""))
        log("[round {}] succeeded={} needs_review={} active={} blocked={}".format(
            i, ok, len(review), active, len(blocked)), prefix)
        if review:
            for t in review:
                rc2, o2 = cli("approve", t, "approve", "--comment", "2.x baseline regression")
                log("  approve {} -> {}".format(t, o2.strip().splitlines()[-1][:70]), prefix)
            continue
        if blocked:
            stop = False
            for b in blocked:
                tid = b.split("|")[0]
                if tid not in redone:
                    redone.add(tid)
                    rc2, o2 = cli("redo", tid)
                    log("  redo {} ({}) -> {}".format(tid, b, o2.strip().splitlines()[-1][:70]), prefix)
                else:
                    log("  BLOCKED and already redone, stop: " + b, prefix)
                    stop = True
            if stop:
                return "BLOCKED"
            continue
        if active == 0:
            log("  settled: no active tasks", prefix)
            return "SETTLED"
        rc2, o2 = cli("run", pid)
        log("  run -> " + o2.strip().splitlines()[-1][:80], prefix)
    return "MAXROUNDS"


def new_test(key, prefix):
    spec = PROMPTS[key]
    name = spec["name"] + ("_fresh" if prefix.endswith("F") else "")
    rc, out = cli("init", spec["prompt"], "--name", name)
    log("=== [{}] init -> {}".format(prefix, out.strip()), prefix)
    m = re.search(r"p_[0-9a-f]+", out)
    if not m:
        return "NOID"
    pid = m.group(0)
    rc2, o2 = cli("plan", pid)
    log("  plan -> " + o2.strip(), prefix)
    r = loop(pid, prefix)
    log("  loop result: " + r, prefix)
    return "{}|{}".format(pid, r)


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def probe(p):
    p2 = subprocess.run([str(FFPROBE), "-v", "error", "-show_entries",
                         "format=duration,size:stream=codec_type,codec_name,width,height,sample_rate,channels",
                         "-of", "default=nw=1", str(p)], capture_output=True, text=True,
                        encoding="utf-8", errors="replace")
    return (p2.stdout or "").strip().replace("\n", " ")


results = {}
FRESH = "--fresh" in sys.argv          # 改动后回归：三组都用全新项目重跑
SFX = "2" if FRESH else ""
pre = ("AF", "BF", "CF") if FRESH else ("A", "B", "C")
if not FRESH:
    A = PROMPTS["A"]["existing_project"]
    results["A"] = "{}|{}".format(A, loop(A, pre[0]))
else:
    results["A"] = new_test("A", pre[0])
results["B"] = new_test("B", pre[1])
results["C"] = new_test("C", pre[2])

print("\n" + "=" * 90)
print("成品核验（每个项目必须真实产出 mp4）")
print("=" * 90)
ver = {}
for key in ("A", "B", "C"):
    pid = results[key].split("|")[0]
    vids = sorted((ROOT / "projects" / pid / "output").glob("*.mp4")) if pid.startswith("p_") else []
    if not vids:
        print("[{}] {} -> NO MP4  (loop={})".format(key, pid, results[key]))
        ver[key] = None
        continue
    for v in vids:
        print("[{}] {} -> {}  {} bytes  sha256={}".format(key, pid, v.name, v.stat().st_size, sha(v)[:24]))
        print("      ffprobe: " + probe(v))
        ver[key] = {"project": pid, "path": str(v), "bytes": v.stat().st_size, "sha256": sha(v)}

# stored prompt evidence
print("\n" + "=" * 90)
print("项目库中记录的输入选材（UTF-8 保真核验）")
print("=" * 90)
con = sqlite3.connect(str(ROOT / "projects" / "video_studio.db"))
con.row_factory = sqlite3.Row
for key in ("A", "B", "C"):
    pid = results[key].split("|")[0]
    try:
        r = con.execute("select * from projects where project_id=?", (pid,)).fetchone()
        d = dict(r) if r else {}
        txt = d.get("brief") or d.get("title") or d.get("idea") or json.dumps(d, ensure_ascii=False)[:200]
        print("[{}] {} brief={}".format(key, pid, str(txt)[:120]))
    except Exception as e:
        print("[{}] {} db read failed: {}".format(key, pid, e))
con.close()

(LOGS / ("run_all_result{}.json".format("_fresh" if FRESH else ""))).write_text(json.dumps(
    {"mode": "fresh" if FRESH else "append", "loop": results, "videos": ver,
     "prompts": {k: PROMPTS[k]["prompt"] for k in PROMPTS}},
    ensure_ascii=False, indent=1), encoding="utf-8")
print("\nRESULT:", json.dumps(results, ensure_ascii=False))
print("videos:", json.dumps({k: (v["path"] if v else None) for k, v in ver.items()}, ensure_ascii=False))
