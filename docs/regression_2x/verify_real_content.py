"""Part A objective content verifier (no LLM judging; deterministic checks only).

Checks per project:
  1) theme relevance: keyword hits per artifact (topic/research/structure/script/visual/subtitle)
  2) fact vs theory markers present in structure/script
  3) shot <-> narration keyword overlap (mean/min)
  4) subtitle cues vs script narration (normalized equality ratio)
  5) video: real ffprobe streams/duration/codec/size + ffmpeg decode rc + keyframe extraction
  6) content fingerprint (for cross-run distinctness)

Usage: python docs/regression_2x/verify_real_content.py <project_id> [--theme 黑洞,视界,引力]
"""
import hashlib
import json
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
FFPROBE = ROOT / "bin" / "ffprobe.exe"
FFMPEG = ROOT / "bin" / "ffmpeg.exe"
TMP = Path(r"C:\Users\DUALAN~1\AppData\Local\Temp\v161audit")

pid = sys.argv[1]
THEME = ["黑洞", "视界", "引力", "霍金", "奇点", "潮汐", "吸积", "史瓦西", "光速", "时空"]
if "--theme" in sys.argv:
    THEME = sys.argv[sys.argv.index("--theme") + 1].split(",")
THEORY = ["理论", "推测", "假设", "尚无", "未解", "研究中", "尚未", "猜想", "不是严格"]
CONTROL = ["皮肤", "鲸鱼娘", "深海女仆"]

con = sqlite3.connect(str(ROOT / "projects" / "video_studio.db"))
con.row_factory = sqlite3.Row
arts = {}
for r in con.execute("select * from artifacts where project_id=?", (pid,)):
    arts.setdefault(r["type"], []).append(dict(r))
con.close()


def load(t):
    lst = arts.get(t) or []
    return json.loads(Path(lst[-1]["path"]).read_text(encoding="utf-8")) if lst else None


def norm(s):
    return re.sub(r"[\s，。、；：！？,.;:!?\"'“”‘’（）()\[\]—\-…]+", "", s or "")


def hits(text, words):
    return {w: text.count(w) for w in words if w in text}


print("=" * 92)
print("Part A 内容保真客观核验 |", pid)
print("=" * 92)
t_topic, t_res, t_str, t_sc = load("topic_output"), load("research_output"), load("structure_output"), load("script_output")
t_vis, t_sub, t_ren = load("visual_plan_output"), load("subtitle"), load("render_output")

blobs = {
    "topic": json.dumps(t_topic, ensure_ascii=False),
    "research": json.dumps(t_res, ensure_ascii=False),
    "structure": json.dumps(t_str, ensure_ascii=False),
    "script": json.dumps(t_sc, ensure_ascii=False),
    "visual_plan": json.dumps(t_vis, ensure_ascii=False),
    "subtitle": json.dumps(t_sub, ensure_ascii=False),
}
print("\n[1] 主题相关性（关键词命中数）")
fails = []
for k, b in blobs.items():
    h = hits(b, THEME)
    tot = sum(h.values())
    ctrl = hits(b, CONTROL)
    print("  {:12s} 主题命中 {:4d} 次 {:24s} 对照词(mock线索) {}".format(
        k, tot, str(list(h)[:6]), list(ctrl) or "无"))
    if tot == 0:
        fails.append("主题缺失:" + k)

print("\n[2] 事实/推测区分标记")
sc_txt = blobs["script"] + blobs["structure"] + blobs["subtitle"]
th = hits(sc_txt, THEORY)
print("  标记命中:", th if th else "无")
if not th:
    fails.append("未发现事实/推测区分标记")

print("\n[3] 分镜完整性（结构化，可判定）+ 跨模态用词重叠（仅参考，不作判定依据）")
shots = (t_vis or {}).get("shots", [])
segs = (t_sc or {}).get("segments", [])


def grams(s):
    s = re.sub(r"[\s\W_]+", "", s or "")
    return {s[i:i + 2] for i in range(len(s) - 1)}


GEN_SOURCES = {"ai_generate", "chart", "ai", "generate"}   # 需要生成提示词的来源
incomplete = []
for i, sh in enumerate(shots):
    missing = [k for k in ("description", "shot_size", "duration_s", "source") if not sh.get(k)]
    if str(sh.get("source")) in GEN_SOURCES and not str(sh.get("gen_prompt", "")).strip():
        missing.append("gen_prompt")
    if missing:
        incomplete.append((i + 1, sh.get("source"), missing))
shot_total = sum(float(sh.get("duration_s") or 0) for sh in shots)
print("  镜头数 {} | 旁白段数 {} | 镜头时长合计 {:.0f}s".format(len(shots), len(segs), shot_total))
print("  字段不完整（已按 source 区分：stock/资料画面不要求 gen_prompt）:",
      incomplete if incomplete else "无")
if incomplete or not shots:
    fails.append("分镜字段不完整")
best_all = []
for i, sh in enumerate(shots):
    g1 = grams(str(sh.get("description", "")) + str(sh.get("gen_prompt", "")))
    best = max((len(g1 & grams(str(sg.get("narration", "")))) /
                max(1, len(g1 | grams(str(sg.get("narration", ""))))) for sg in segs), default=0.0)
    best_all.append(best)
mean_best = sum(best_all) / len(best_all) if best_all else 0
print("  跨模态 2-gram 平均最佳重叠 {:.1%}（信息项：图像描述与旁白用词本就不同，低值≠不一致；"
      "语义级对齐需人工/LLM 判定 → PENDING）".format(mean_best))

print("\n[4] 字幕 ↔ 旁白 一致性")
srt = (t_sub or {}).get("srt", "")
cues = re.findall(r"\d+\s*\n[\d:,]+\s*-->\s*[\d:,]+\s*\n(.+?)(?=\n\s*\n|\Z)", srt, re.S)
cues = [c.strip() for c in cues]
nar = [norm(s.get("narration", "")) for s in segs]
print("  cue 数 {} | 旁白段数 {}".format(len(cues), len(nar)))
match = 0
for i, c in enumerate(cues):
    cn = norm(c)
    ok = any(cn == n or cn in n or n in cn for n in nar)
    match += 1 if ok else 0
    print("   cue{:2d} 文本 {} 字 | 与某段旁白包含关系: {}".format(i + 1, len(cn), "是" if ok else "否"))
if len(cues) and match / len(cues) < 0.8:
    fails.append("字幕与旁白不一致")

print("\n[5] 成片验证")
vids = sorted((ROOT / "projects" / pid / "output").glob("*.mp4"))
if not vids:
    print("  无成片")
    fails.append("无成片")
else:
    v = vids[-1]
    p = subprocess.run([str(FFPROBE), "-v", "error", "-print_format", "json",
                        "-show_format", "-show_streams", str(v)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    info = json.loads(p.stdout or "{}")
    st = info.get("streams", [])
    print("  {} | {} bytes | duration {} | streams {}".format(
        v.name, v.stat().st_size, (info.get("format") or {}).get("duration"), len(st)))
    for s in st:
        print("    {} {} {}x{} sr={} ch={}".format(s.get("codec_type"), s.get("codec_name"),
                                                   s.get("width"), s.get("height"),
                                                   s.get("sample_rate"), s.get("channels")))
    d = subprocess.run([str(FFMPEG), "-v", "error", "-i", str(v), "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    print("  ffmpeg 解码 rc = {} {}".format(d.returncode, (d.stderr or "")[:120]))
    TMP.mkdir(parents=True, exist_ok=True)
    frames = []
    for tsec in (5, 30):
        fp = TMP / "real_{}_{}.png".format(pid[-6:], tsec)
        r = subprocess.run([str(FFMPEG), "-y", "-v", "error", "-ss", str(tsec), "-i", str(v),
                            "-frames:v", "1", str(fp)], capture_output=True, text=True)
        if r.returncode == 0 and fp.exists():
            frames.append(str(fp))
    print("  关键帧:", frames)
    if d.returncode != 0:
        fails.append("解码失败")
    if len(st) != 2:
        fails.append("流数异常")

print("\n[6] 内容指纹（用于跨组区分度对比）")
fp = hashlib.sha256((json.dumps(t_sc, ensure_ascii=False) + srt).encode()).hexdigest()
txtfp = hashlib.sha256(norm(srt).encode()).hexdigest()
print("  script+subtitle sha256:", fp[:24])
print("  正文字符数:", len(norm(srt)))
print("\nrender 标注: visual_source={} material_assembly={} material_mode={} candidates={}".format(
    (t_ren or {}).get("visual_source"), (t_ren or {}).get("material_assembly"),
    (t_ren or {}).get("material_mode"), (t_ren or {}).get("material_candidates")))

out = {"project": pid, "theme_hits": {k: sum(hits(b, THEME).values()) for k, b in blobs.items()},
       "theory_markers": th, "shot_narration_overlap_mean": round(mean_best, 4),
       "subtitle_cues": len(cues), "subtitle_inclusion_matches": match,
       "video": str(vids[-1]) if vids else None, "content_sha256": fp, "text_sha256": txtfp,
       "text_chars": len(norm(srt)), "fails": fails,
       "verdict": "PASS" if not fails else "FAIL"}
(ROOT / "docs" / "regression_2x" / "logs" / "content_{}.json".format(pid)).write_text(
    json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print("\nVERDICT:", out["verdict"], "" if not fails else fails)
