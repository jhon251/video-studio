"""Part B evidence verifier: prove the ingested material really appears in the final video.

Chain evidence: media file -> asset_index -> retrieval_candidates -> render_output.material_used -> frames.
Deterministic checks only; frame correlation vs the source image AND vs a solid-color control.

Usage: python docs/regression_2x/verify_assembly.py <project_id>
"""
import hashlib
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
FFPROBE = ROOT / "bin" / "ffprobe.exe"
FFMPEG = ROOT / "bin" / "ffmpeg.exe"
TMP = Path(r"C:\Users\DUALAN~1\AppData\Local\Temp\v161audit")
TMP.mkdir(parents=True, exist_ok=True)
pid = sys.argv[1]

con = sqlite3.connect(str(ROOT / "projects" / "video_studio.db"))
con.row_factory = sqlite3.Row
arts = {}
for r in con.execute("select * from artifacts where project_id=?", (pid,)):
    arts.setdefault(r["type"], []).append(dict(r))
con.close()


def load(t):
    lst = arts.get(t) or []
    return json.loads(Path(lst[-1]["path"]).read_text(encoding="utf-8")) if lst else None


def gray(p, size=(32, 32)):
    im = Image.open(p).convert("L").resize(size)
    return np.asarray(im, dtype=np.float64)


def corr(a, b):
    a = a - a.mean()
    b = b - b.mean()
    d = (np.sqrt((a ** 2).sum()) * np.sqrt((b ** 2).sum()))
    return float((a * b).sum() / d) if d else 0.0


fails = []
ai, rc_, ren = load("asset_index"), load("retrieval_candidates"), load("render_output")
print("=" * 90)
print("Part B 本地素材装配证据链 |", pid)
print("=" * 90)

print("\n[1] 素材来源（本地 ingest，非外部 provider）")
files = (ai or {}).get("files", [])
print("  asset_index: mode={} files={} providers={}".format(
    (ai or {}).get("material_mode"), len(files), (ai or {}).get("material_providers")))
for f in files:
    p = ROOT / "projects" / pid / "media" / f["path"]
    print("   - {} {} bytes sha256:{} exists={}".format(
        f["path"], f["size"], f["sha256"], p.exists()))
    if not p.exists():
        fails.append("素材文件缺失:" + f["path"])

print("\n[2] retrieval 命中证据")
cands = (rc_ or {}).get("candidates") or []
print("  mode={} query_source={} index_source={} indexed_files={} candidates={}".format(
    (rc_ or {}).get("material_mode"), (rc_ or {}).get("query_source"),
    (rc_ or {}).get("index_source"), (rc_ or {}).get("indexed_files"), len(cands)))
for c in cands:
    print("   - {} score={} sha16={}".format(c.get("name"), c.get("match_score"), c.get("sha256")))
if not cands:
    fails.append("retrieval 未命中任何素材")

print("\n[3] editing/render 实际使用证据")
mu = (ren or {}).get("material_used")
print("  visual_source={} material_assembly={} material_candidates={}".format(
    (ren or {}).get("visual_source"), (ren or {}).get("material_assembly"),
    (ren or {}).get("material_candidates")))
print("  material_used =", json.dumps(mu, ensure_ascii=False))
print("  material_appearances =", json.dumps((ren or {}).get("material_appearances"),
                                              ensure_ascii=False))
if (ren or {}).get("material_assembly") != "SUCCEEDED" or not mu:
    fails.append("render 未标注素材装配成功")
    src_img = None
else:
    src_img = Path(mu["abs_path"])
    if not src_img.exists():
        fails.append("material_used 路径不存在")
        src_img = None
    else:
        h = hashlib.sha256(src_img.read_bytes()).hexdigest()[:16]
        print("  复用校验: sha256前16={} 与 material_used 记录一致={}".format(
            h, h == mu.get("sha256")))
        if h != mu.get("sha256"):
            fails.append("素材哈希与记录不一致")

print("\n[4] 成片中素材是否真的出现（抽帧 + 相关性对照）")
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
    print("  ffmpeg 解码 rc = {} {}".format(d.returncode, (d.stderr or "")[:100]))
    if d.returncode != 0:
        fails.append("解码失败")
    corrs, ctrl = [], []
    if src_img and src_img.exists():
        g_src = gray(src_img)
        solid = np.full((32, 32), 0.05)          # 对照：近纯色底（0x0b1226 亮度≈0.05）
        for t in (1, 5, 15, 30, 60, 120, 180, 240):
            fp = TMP / "asm_{}_{}.png".format(pid[-6:], t)
            r = subprocess.run([str(FFMPEG), "-y", "-v", "error", "-ss", str(t), "-i", str(v),
                                "-frames:v", "1", str(fp)], capture_output=True, text=True)
            if r.returncode != 0 or not fp.exists():
                continue
            c1 = corr(gray(fp), g_src)
            c2 = corr(gray(fp), solid)
            corrs.append((t, round(c1, 3), round(c2, 3), str(fp)))
            print("   t={:>3}s 与素材相关性 {:+.3f} | 与纯色对照 {:+.3f}".format(t, c1, c2))
        if corrs:
            mean_c = sum(c[1] for c in corrs) / len(corrs)
            mean_ctrl = sum(c[2] for c in corrs) / len(corrs)
            print("  平均：素材相关性 {:+.3f} vs 纯色对照 {:+.3f}".format(mean_c, mean_ctrl))
            if mean_c < 0.35:
                fails.append("抽帧与素材相关性过低（素材可能未真正上屏）")
            if mean_c <= mean_ctrl:
                fails.append("素材相关性未显著高于纯色对照")
        else:
            fails.append("未能抽出帧")

out = {"project": pid, "asset_index": ai, "retrieval": rc_, "render": ren,
       "video": str(vids[-1]) if vids else None,
       "frame_corr": corrs, "fails": fails,
       "verdict": "PASS" if not fails else "FAIL"}
(ROOT / "docs" / "regression_2x" / "logs" / "assembly_{}.json".format(pid)).write_text(
    json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print("\nVERDICT:", out["verdict"], "" if not fails else fails)
sys.exit(1 if fails else 0)
