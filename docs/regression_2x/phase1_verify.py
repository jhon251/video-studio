"""3.x Phase 1 unified verifier for the three real-content runs (A/B/C) + distinctness.

Per project:
  - theme terms auto-derived from topic_output (+ --theme override), then measured across
    research/structure/script/visual_plan/subtitle  (internal theme consistency)
  - goal-keyword relevance (from the project goal string)
  - constraint checks per goal: B = 真实/实验/推测三态区分 ; C = 60s/受众/钩子/分镜/旁白/字幕/总结
  - subtitle <-> narration consistency; video probe + decode + content fingerprint
Distinctness: pairwise text similarity across the three runs (must be substantively different).

Usage: python docs/regression_2x/phase1_verify.py
"""
import hashlib
import json
import re
import sqlite3
import subprocess
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
FFPROBE = ROOT / "bin" / "ffprobe.exe"
FFMPEG = ROOT / "bin" / "ffmpeg.exe"

RUNS = {
    "A": {"pid": "p_314efdfbbeb2", "goal": "做一期介绍黑洞的短视频。",
          "theme": ["黑洞", "视界", "引力", "霍金", "奇点", "吸积", "史瓦西"],
          "goal_terms": ["黑洞"]},
    "B": {"pid": "p_e7a8b8020fb1",
          "goal": "做一期介绍脑机接口发展现状的视频，要求区分真实技术、实验阶段和未来推测。",
          "theme": ["脑机接口", "脑机", "神经", "电极", "植入", "皮层", "信号", "瘫痪",
                    "临床试验", "BCI", "Neuralink"],
          "goal_terms": ["脑机接口", "脑机"]},
    "C": {"pid": "p_8f054c227bd4",
          "goal": "制作一条60秒科技科普视频，面向普通观众，节奏适中，"
                  "包含开头钩子、分镜、旁白、字幕和结尾总结。",
          "theme": ["电池", "充电", "电量", "信号", "GHz", "GPS", "相对论", "微秒"],
          "goal_terms": []},   # C 的目标是形式约束、无具体主题；主题由 LLM 自选 → 只查链路一致性
}
STOP = {"视频", "内容", "观众", "结构", "开场", "本章", "我们", "一个", "可以", "需要", "这是"}
CAT = {
    "fact": ["已获批", "已上市", "临床应用", "已被证实", "目前已经", "已经实现", "获准", "用于临床"],
    "experiment": ["试验", "实验", "研究中", "正在测试", "早期", "临床前", "尚未大规模", "试点"],
    "speculation": ["推测", "未来", "可能", "设想", "预期", "有望", "如果", "尚未可知", "乐观估计"],
}


def db():
    con = sqlite3.connect(str(ROOT / "projects" / "video_studio.db"))
    con.row_factory = sqlite3.Row
    return con


def arts_of(pid):
    con = db()
    out = {}
    for r in con.execute("select * from artifacts where project_id=?", (pid,)):
        out.setdefault(r["type"], []).append(dict(r))
    con.close()
    return out


def load(arts, t):
    lst = arts.get(t) or []
    return json.loads(Path(lst[-1]["path"]).read_text(encoding="utf-8")) if lst else None


def norm(s):
    return re.sub(r"[\s，。、；：！？,.;:!?\"'“”‘’（）()\[\]—\-…]+", "", s or "")


def probe(v):
    p = subprocess.run([str(FFPROBE), "-v", "error", "-print_format", "json", "-show_format",
                        "-show_streams", str(v)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return json.loads(p.stdout or "{}")


# resolve latest project for C if not pinned
con = db()
if RUNS["C"]["pid"] is None:
    row = con.execute("select project_id from projects where name='testC_60s_real' "
                      "order by created_at desc limit 1").fetchone()
    RUNS["C"]["pid"] = row["project_id"] if row else None
con.close()

fails_all, summary, texts = {}, {}, {}
for key, cfg in RUNS.items():
    pid = cfg["pid"]
    print("=" * 94)
    print("Phase 1 验收 | {} | {} | {}".format(key, pid, cfg["goal"][:40]))
    print("=" * 94)
    if not pid:
        print("  项目缺失 → BLOCKED")
        fails_all[key] = ["项目缺失"]
        continue
    arts = arts_of(pid)
    topic, res, stru = load(arts, "topic_output"), load(arts, "research_output"), load(arts, "structure_output")
    scr, vis, sub, ren = load(arts, "script_output"), load(arts, "visual_plan_output"), load(arts, "subtitle"), load(arts, "render_output")
    blobs = {"topic": json.dumps(topic, ensure_ascii=False),
             "research": json.dumps(res, ensure_ascii=False),
             "structure": json.dumps(stru, ensure_ascii=False),
             "script": json.dumps(scr, ensure_ascii=False),
             "visual_plan": json.dumps(vis, ensure_ascii=False),
             "subtitle": json.dumps(sub, ensure_ascii=False)}
    fails = []

    # 主题词：显式给定优先，否则从 topic_output 自动派生
    theme = cfg["theme"]
    if not theme:
        toks = re.findall(r"[\u4e00-\u9fff]{2,4}", blobs["topic"])
        theme = [t for t, _ in Counter(t for t in toks if t not in STOP).most_common(6)]
    print("\n[1] 主题一致性（主题词：{}）".format("、".join(theme[:6])))
    for k, b in blobs.items():
        h = {w: b.count(w) for w in theme if w in b}
        print("  {:12s} 命中 {:4d} 次 {}".format(k, sum(h.values()), list(h)[:5]))
        if sum(h.values()) == 0:
            fails.append("主题缺失:" + k)

    print("\n[2] 选材相关性（goal 关键词）")
    gk = cfg.get("goal_terms") or []
    if not gk:
        print("  （本组目标为形式约束、无具体主题 → 跳过 goal 词检查，改由 [1] 验证链路主题一致性）")
    else:
        hits = {w: blobs["script"].count(w) + blobs["topic"].count(w) + blobs["structure"].count(w)
                for w in gk}
        print("  goal 词命中:", hits)
        if not any(hits.values()):
            fails.append("goal 关键词全未命中")

    print("\n[3] 约束遵循")
    if key == "B":
        for cat, words in CAT.items():
            n = sum(blobs["script"].count(w) + blobs["structure"].count(w) + blobs["subtitle"].count(w)
                    for w in words)
            print("  {:12s} 标记命中 {:3d} 次（{}）".format(cat, n, words[:3]))
            if n == 0:
                fails.append("三态区分缺失:" + cat)
    elif key == "C":
        segs = (scr or {}).get("segments", [])
        chaps = (stru or {}).get("chapters", [])
        shots = (vis or {}).get("shots", [])
        srt = (sub or {}).get("srt", "") or ""
        target = sum(float(c.get("duration_s") or 0) for c in chaps)
        vids = sorted((ROOT / "projects" / pid / "output").glob("*.mp4"))
        dur = None
        if vids:
            info = probe(vids[-1])
            dur = float((info.get("format") or {}).get("duration") or 0)
        checks = {
            "开头钩子": bool(chaps) and any(("钩子" in str(c.get("title", "")) or
                                        "开场" in str(c.get("title", ""))) for c in chaps),
            "分镜": len(shots) > 0,
            "旁白": len(segs) > 0,
            "字幕": len(re.findall(r"-->\s", srt)) > 0,
            "结尾总结": bool(chaps) and any(("收" in str(c.get("title", "")) or
                                        "总结" in str(c.get("title", "")) or
                                        "结尾" in str(c.get("title", ""))) for c in chaps),
            "面向普通观众(受众字段)": any(("大众" in str(p.get("audience", "")) or
                                    "普通" in str(p.get("audience", "")) or
                                    "泛" in str(p.get("audience", "")))
                                   for p in (topic or {}).get("proposals", [])),
        }
        for k2, v2 in checks.items():
            print("  {:22s} {}".format(k2, "满足" if v2 else "未满足"))
            if not v2:
                fails.append("约束未满足:" + k2)
        print("  时长：结构目标 {:.0f}s | 成片实测 {}s（60s 目标偏差 {:.0%}）".format(
            target, round(dur) if dur else "n/a",
            abs((dur or 0) - 60) / 60 if dur else 0))
        if dur and abs(dur - 60) / 60 > 0.5:
            fails.append("时长偏离 60s 目标 >50%")

    print("\n[4] 字幕 ↔ 旁白 一致性")
    segs = (scr or {}).get("segments", [])
    cues = re.findall(r"\d+\s*\n[\d:,]+\s*-->\s*[\d:,]+\s*\n(.+?)(?=\n\s*\n|\Z)",
                      (sub or {}).get("srt", "") or "", re.S)
    nar = [norm(s.get("narration", "")) for s in segs]
    ok_n = sum(1 for c in cues if any(norm(c) in n or n in norm(c) for n in nar))
    print("  cue {} 条 | 与旁白包含关系一致 {} 条".format(len(cues), ok_n))
    if cues and ok_n / len(cues) < 0.8:
        fails.append("字幕与旁白不一致")

    print("\n[5] 成片")
    vids = sorted((ROOT / "projects" / pid / "output").glob("*.mp4"))
    if not vids:
        print("  无成片")
        fails.append("无成片")
    else:
        v = vids[-1]
        info = probe(v)
        st = info.get("streams", [])
        d = subprocess.run([str(FFMPEG), "-v", "error", "-i", str(v), "-f", "null", "-"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        print("  {} | {} bytes | {}s | streams {}".format(
            v.name, v.stat().st_size, (info.get("format") or {}).get("duration"), len(st)))
        for s in st:
            print("    {} {} {}x{}".format(s.get("codec_type"), s.get("codec_name"),
                                           s.get("width"), s.get("height")))
        print("  ffmpeg 解码 rc = {}".format(d.returncode))
        if d.returncode != 0 or len(st) != 2:
            fails.append("成片校验失败")

    fp = hashlib.sha256(norm((sub or {}).get("srt", "")).encode()).hexdigest()
    texts[key] = norm((sub or {}).get("srt", ""))
    summary[key] = {"pid": pid, "theme": theme, "text_sha256": fp, "chars": len(texts[key]),
                    "scene_sha256": hashlib.sha256(json.dumps(scr, ensure_ascii=False).encode()).hexdigest(),
                    "render": {"visual_source": (ren or {}).get("visual_source"),
                               "material_assembly": (ren or {}).get("material_assembly")},
                    "fails": fails}
    print("\n  VERDICT:", "PASS" if not fails else "FAIL " + str(fails))

print("\n" + "=" * 94)
print("三组区分度（成片字幕文本两两 2-gram Jaccard，需显著不同）")
print("=" * 94)


def grams(s):
    return {s[i:i + 2] for i in range(len(s) - 1)}


keys = [k for k in ("A", "B", "C") if k in texts and texts[k]]
for i in range(len(keys)):
    for j in range(i + 1, len(keys)):
        a, b = texts[keys[i]], texts[keys[j]]
        ga, gb = grams(a), grams(b)
        jac = len(ga & gb) / max(1, len(ga | gb))
        same = summary[keys[i]]["text_sha256"] == summary[keys[j]]["text_sha256"]
        print("  {}-{}: Jaccard {:.1%} | 文本完全相同: {} | 样本A[{}] 样本B[{}]".format(
            keys[i], keys[j], jac, same, a[:18], b[:18]))
        if same or jac > 0.5:
            summary.setdefault("distinct_fails", []).append("{}-{}".format(keys[i], keys[j]))
print("\n  区分度判定:", "PASS（三组互不相同）" if not summary.get("distinct_fails")
      else "FAIL " + str(summary["distinct_fails"]))

(ROOT / "docs" / "regression_2x" / "logs" / "phase1_verify.json").write_text(
    json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
print("\n记录:", ROOT / "docs" / "regression_2x" / "logs" / "phase1_verify.json")
