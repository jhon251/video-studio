"""二进制真实性检查（3.x-Preflight 新增）：ffmpeg / ffprobe 必须真实可用且不得互相冒充。

用法：
  python scripts/check_binaries.py                 # 只校验二进制
  python scripts/check_binaries.py <某个.mp4>      # 额外做一次真实探测并打印 streams

退出码：0 = 全部通过；1 = 存在问题（同时打印明确原因）。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.tools.ffmpeg_tool import verify_ffprobe  # noqa: E402


def load_cfg() -> dict:
    p = ROOT / "config" / "config.json"
    if not p.exists():
        p = ROOT / "config" / "config.example.json"
    return json.loads(p.read_text(encoding="utf-8")).get("tools", {}).get("ffmpeg", {})


def main() -> int:
    cfg = load_cfg()
    ffmpeg = shutil.which(cfg.get("path", "ffmpeg"))
    ffprobe = shutil.which(cfg.get("ffprobe", "ffprobe"))
    fails = []

    print("config:", json.dumps(cfg, ensure_ascii=False))
    print("ffmpeg :", ffmpeg)
    print("ffprobe:", ffprobe)

    if not ffmpeg:
        fails.append("ffmpeg 未找到")
    else:
        out = subprocess.run([ffmpeg, "-version"], capture_output=True, text=True, timeout=60)
        head = ((out.stdout or "") + (out.stderr or ""))[:200].strip().splitlines()
        first = head[0] if head else ""
        print("ffmpeg -version:", first)
        if out.returncode != 0 or "ffmpeg" not in first.lower() or "ffprobe" in first.lower():
            fails.append("ffmpeg -version 自述异常: " + first)

    ok, why = verify_ffprobe(ffprobe, ffmpeg)
    print("ffprobe 真实性:", "OK" if ok else "FAIL — " + why)
    if not ok:
        fails.append("ffprobe 不可用: " + why)

    if len(sys.argv) > 1:
        target = Path(sys.argv[1])
        if not target.is_absolute():
            target = ROOT / target
        if not target.exists():
            fails.append(f"探测目标不存在: {target}")
        elif ok:
            out = subprocess.run([ffprobe, "-v", "error", "-print_format", "json",
                                  "-show_format", "-show_streams", str(target)],
                                 capture_output=True, text=True, timeout=120)
            if out.returncode != 0:
                fails.append("ffprobe 探测失败: " + (out.stderr or "")[:200])
            else:
                info = json.loads(out.stdout)
                fmt = info.get("format", {})
                print("probe:", target.name, "| format:", fmt.get("format_name"),
                      "| duration:", fmt.get("duration"), "| nb_streams:", len(info.get("streams", [])))
                for s in info.get("streams", []):
                    print("   stream {}: type={} codec={} {}x{} sr={} ch={} dur={}".format(
                        s.get("index"), s.get("codec_type"), s.get("codec_name"),
                        s.get("width"), s.get("height"), s.get("sample_rate"),
                        s.get("channels"), s.get("duration")))

    print()
    if fails:
        print("VERDICT: FAIL")
        for f in fails:
            print("  - " + f)
        return 1
    print("VERDICT: PASS（ffmpeg/ffprobe 均真实可用，且非同一二进制）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
