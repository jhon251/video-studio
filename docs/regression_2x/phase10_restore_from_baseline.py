# -*- coding: utf-8 -*-
"""Phase 10：从基线 ZIP 只读提取 config/config.json 原字节并复原（sha256 目标 7b03424846f1…）。"""
import hashlib
import pathlib
import sys
import zipfile

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")
TARGET = "7b03424846f15efc"
zip_path = R / "docs" / "regression_2x" / "baseline" / "5.x-post-final-maintenance-baseline.zip"
print("基线 ZIP:", zip_path.name, "| 存在:", zip_path.is_file())
if not zip_path.is_file():
    zips = sorted((R / "docs" / "regression_2x" / "baseline").glob("*.zip"))
    print("可用 ZIP:", [z.name for z in zips][-5:])
    sys.exit(2)
with zipfile.ZipFile(zip_path) as z:
    names = [n for n in z.namelist() if n.endswith("config.json") or "config/" in n]
    print("ZIP 内 config 相关条目:", names[:10])
    cand = [n for n in z.namelist() if n.endswith("config/config.json")]
    if not cand:
        print("ZIP 内无 config/config.json ⇒ 无法从基线复原")
        sys.exit(3)
    data = z.read(cand[0])
    h = hashlib.sha256(data).hexdigest()
    print("ZIP 内 config/config.json sha256:", h[:16], "| 与钉定一致:",
          h.startswith(TARGET), "| 字节数:", len(data))
    if h.startswith(TARGET):
        (R / "config" / "config.json").write_bytes(data)
        now = hashlib.sha256((R / "config" / "config.json").read_bytes()).hexdigest()
        print("已复原 config/config.json ⇒ sha256:", now[:16], "| 与钉定一致:",
              now.startswith(TARGET))
    ex = [n for n in z.namelist() if n.endswith("config/config.example.json")]
    if ex:
        d2 = z.read(ex[0])
        print("ZIP 内 config.example.json sha256:", hashlib.sha256(d2).hexdigest()[:16])
        (R / "config" / "config.example.json").write_bytes(d2)
        now2 = hashlib.sha256((R / "config" / "config.example.json").read_bytes()).hexdigest()
        print("已复原 config.example.json ⇒ sha256:", now2[:16])
